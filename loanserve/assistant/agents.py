import re
from contextvars import ContextVar
from loanserve.message_intelligence.llm_client import LanguageModelError, generate_json
from loanserve.retrieval.grounded_answer import check_citations, UngroundedAnswer
from loanserve.assistant.tools import predict_default_risk, ToolError

PLANNER_KEYS = ("steps",)
RESOLVER_KEYS = ("draft", "needs_approval")
RESPONDER_KEYS = ("answer", "confidence")
ALLOWED_TOOLS = {
    "calculate_installment",
    "lookup_application",
    "predict_default_risk",
    "search_policy_documents",
}
_runtime_llm = ContextVar("loanserve_runtime_llm", default=None)


def set_runtime_llm(llm):
    """Set the request-scoped LLM used by graph nodes and return a reset token."""
    return _runtime_llm.set(llm)


def reset_runtime_llm(token):
    _runtime_llm.reset(token)


def runtime_llm():
    return _runtime_llm.get()

PLANNER_PROMPT = """You are the planner agent for LoanServe.
Given the customer's question, category: {category}, and urgency: {urgency}, select which tool to call and formulate its arguments.

Available Tools:
1. calculate_installment: Takes arguments {{"principal_inr": float, "annual_interest_rate_percent": float, "tenure_months": int}}
2. lookup_application: Takes arguments {{"application_id": str}}
3. predict_default_risk: Takes arguments {{"application": dict}}
4. search_policy_documents: Takes arguments {{"question": str, "how_many": int}}

For multi-step work (for example application lookup followed by risk scoring), return all steps
in execution order. Use "$previous.application" as the application argument when a prior lookup
provides it. Respond in JSON with the exact key "steps", where each step has "tool", "arguments", and "why"."""

RESPONDER_PROMPT = """You are the responder agent for LoanServe.
Format the final customer response based on the draft, changing no figure from the calculation or policy.
Assess your confidence as a float between 0.0 and 1.0."""


def _fallback_plan(question):
    """Selects appropriate tool and extracts arguments based on question, category, and urgency."""
    q_lower = question.lower()

    calc_match = re.search(
        r"(?:instalment|installment|emi).*?([0-9]+(?:\.[0-9]+)?)\s*(lakh|lakhs|crore|crores|million)?"
        r".*?([0-9]+(?:\.[0-9]+)?)\s*(?:%|percent).*?([0-9]+)\s*months",
        q_lower,
    )
    if calc_match:
        principal = float(calc_match.group(1))
        multiplier = {"lakh": 100000, "lakhs": 100000, "crore": 10000000,
                      "crores": 10000000, "million": 1000000}.get(calc_match.group(2), 1)
        return [{
                "tool": "calculate_installment",
                "arguments": {
                    "principal_inr": principal * multiplier,
                    "annual_interest_rate_percent": float(calc_match.group(3)),
                    "tenure_months": int(calc_match.group(4)),
                },
                "why": "Calculate loan installment based on requested terms.",
            }]

    # Check for application lookup
    ref_match = re.search(r"\b(LA\d{6}|LP\d{6})\b", question, flags=re.IGNORECASE)
    if ref_match:
        steps = [{
            "tool": "lookup_application",
            "arguments": {"application_id": ref_match.group(1).upper()},
            "why": "Retrieve stored loan application record.",
        }]
        if any(word in q_lower for word in ("risk", "default", "probability")):
            steps.append({"tool": "predict_default_risk",
                          "arguments": {"application": "$previous.application"},
                          "why": "Score the retrieved application with the champion model."})
        return steps

    # Check for policy questions
    return [{
        "tool": "search_policy_documents",
        "arguments": {"question": question, "how_many": 3},
        "why": "Search lending policy documents to answer policy inquiry.",
    }]


def plan_tools(question, category, urgency, llm=None):
    """Uses Gemini to plan tool calls, with validated extraction fallback."""
    prompt = PLANNER_PROMPT.format(category=category, urgency=urgency)
    prompt += f"\nCustomer question: {question}"
    try:
        planned = generate_json(prompt, PLANNER_KEYS, llm=llm or runtime_llm())
        steps = planned["steps"]
        if not isinstance(steps, list) or not steps:
            raise ValueError("Planner returned no steps.")
        if any(
            not isinstance(step, dict)
            or step.get("tool") not in ALLOWED_TOOLS
            or not isinstance(step.get("arguments", {}), dict)
            for step in steps
        ):
            raise ValueError("Planner returned an unavailable tool.")
        return steps[0]
    except (LanguageModelError, ValueError, TypeError, KeyError):
        return _fallback_plan(question)[0]


def draft_response(question, tool_results, plan=None, llm=None):
    """Drafts proposed resolution and flags if human manager approval is required."""
    q_lower = question.lower()
    needs_approval = "waive" in q_lower or "override" in q_lower or "exception" in q_lower

    if not tool_results or not isinstance(tool_results, list):
        return {
            "draft": "I could not find specific information to answer your request.",
            "needs_approval": needs_approval,
        }

    first_result = tool_results[0]
    if "tool_error" in first_result:
        return {
            "draft": f"Unable to process request: {first_result['tool_error']}",
            "needs_approval": needs_approval,
        }

    if any(word in q_lower for word in ("risk", "default", "probability")) and "applicant_name" in first_result:
        try:
            risk_result = predict_default_risk({"application": first_result})
        except ToolError as err:
            return {
                "draft": f"Unable to calculate default risk: {err}",
                "needs_approval": needs_approval,
            }
        probability = risk_result["default_probability"]
        return {
            "draft": f"The predicted probability of default is {probability:.6f}.",
            "needs_approval": needs_approval,
        }

    prompt = (
        f"{RESPONDER_PROMPT}\nQuestion: {question}\nTool results: {tool_results}\n"
        'Respond with JSON {"draft": "...", "needs_approval": false}.'
    )
    try:
        generated = generate_json(prompt, RESOLVER_KEYS, llm=llm or runtime_llm())
        if "passages" in first_result:
            check_citations(generated["draft"], first_result["passages"])
        return {
            "draft": str(generated["draft"]),
            "needs_approval": needs_approval or bool(generated["needs_approval"]),
        }
    except (LanguageModelError, ValueError, TypeError, KeyError, UngroundedAnswer):
        pass

    if "monthly_installment_inr" in first_result:
        amt = first_result["monthly_installment_inr"]
        draft = f"The fixed monthly instalment for this loan is INR {amt:.2f}."
        return {"draft": draft, "needs_approval": False}

    if "applicant_name" in first_result:
        name = first_result["applicant_name"]
        app_id = first_result["application_id"]
        status = first_result.get("status")
        if status:
            draft = f"Application {app_id} for {name} is currently {status}."
        else:
            draft = (
                f"Application {app_id} for {name} was found, but its current status "
                "is not available in the application record."
            )
        return {"draft": draft, "needs_approval": needs_approval}

    if "default_probability" in first_result:
        probability = float(first_result["default_probability"])
        draft = f"The predicted probability of default is {probability:.6f}."
        return {"draft": draft, "needs_approval": needs_approval}

    if "passages" in first_result:
        passages = first_result["passages"]
        if passages:
            best = passages[0]
            draft = f"{best['text']} [{best['chunk_id']}]"
            return {"draft": draft, "needs_approval": needs_approval}

    return {
        "draft": "Your request has been recorded.",
        "needs_approval": needs_approval,
    }


def write_response(question, draft, citations=None, llm=None):
    """Produces finalized customer-facing answer and confidence score."""
    if not draft:
        return {
            "answer": "I could not answer that reliably. A colleague has been asked to look at your question and will come back to you.",
            "confidence": float(0.0),
        }

    prompt = f"{RESPONDER_PROMPT}\nQuestion: {question}\nDraft: {draft}\n"
    prompt += 'Respond with JSON {"answer": "...", "confidence": 0.0}.'
    try:
        return generate_json(prompt, RESPONDER_KEYS, llm=llm or runtime_llm())
    except (LanguageModelError, ValueError, TypeError, KeyError):
        return {"answer": draft, "confidence": 0.95}
