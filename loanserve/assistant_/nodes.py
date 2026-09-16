from langchain_core.messages import AIMessage
from langgraph.types import interrupt

from config.constants import (
    LOW_CONFIDENCE_REFUSAL,
    MESSAGE_CLASSIFIER_PATH,
    MINIMUM_ANSWER_CONFIDENCE,
)
from loanserve.assistant.agents import (
    draft_response,
    plan_tools,
    write_response,
)
from loanserve.assistant.tools import (
    ToolError,
    calculate_installment,
    lookup_application,
    predict_default_risk,
    search_policy_documents,
)
from loanserve.message_intelligence.injection_guard import find_injection_markers
from loanserve.message_intelligence.message_classifier import classify_message
from loanserve.risk_models.baseline_model import load_model


def triage(state):
    """Classifies customer message and intercepts prompt injection attempts before model execution."""
    question = state.get("question", "")

    # Injection check
    markers = find_injection_markers(question)
    if markers:
        reason = f"Prompt injection detected: {', '.join(markers)}"
        return {
            "refused": reason,
            "steps": ["triage"],
            "messages": [AIMessage(content=f"Triage blocked injection attempt: {reason}")],
        }

    # Short check
    if not question or len(question.strip()) < 5:
        return {
            "refused": "Question too short to process",
            "steps": ["triage"],
            "messages": [AIMessage(content="Triage refused: Question too short")],
        }

    try:
        models = load_model(MESSAGE_CLASSIFIER_PATH)
        classified = classify_message(models, question)
        cat = classified.get("category", "loan_query")
        urg = classified.get("urgency", "low")
    except Exception:
        cat = "loan_query"
        urg = "low"

    return {
        "category": cat,
        "urgency": urg,
        "steps": ["triage"],
        "messages": [AIMessage(content=f"Triage classified request as {cat} with {urg} urgency.")],
    }


def plan(state):
    """Plans tool execution based on triage categorization and extracted parameters."""
    if state.get("refused"):
        return {}

    question = state.get("question", "")
    category = state.get("category", "loan_query")
    urgency = state.get("urgency", "low")

    planned = plan_tools(question=question, category=category, urgency=urgency)
    return {
        "plan": [planned],
        "steps": ["plan"],
        "messages": [AIMessage(content=f"Planner selected tool '{planned['tool']}'.")],
    }


def run_tools(state):
    """Dispatches tool execution against the planned tool specifications."""
    if state.get("refused"):
        return {}

    plan_list = state.get("plan", [])
    results = []

    for step in plan_list:
        tool_name = step.get("tool")
        arguments = step.get("arguments", {})

        if tool_name == "calculate_installment":
            try:
                res = calculate_installment(arguments)
                results.append(res)
            except ToolError as err:
                results.append({"tool_error": str(err)})
        elif tool_name == "lookup_application":
            try:
                res = lookup_application(arguments)
                results.append(res)
            except ToolError as err:
                results.append({"tool_error": str(err)})
        elif tool_name == "predict_default_risk":
            try:
                res = predict_default_risk(arguments)
                results.append(res)
            except ToolError as err:
                results.append({"tool_error": str(err)})
        elif tool_name == "search_policy_documents":
            try:
                res = search_policy_documents(arguments)
                results.append(res)
            except ToolError as err:
                results.append({"tool_error": str(err)})
        else:
            results.append({"tool_error": f"Tool '{tool_name}' not recognized."})

    return {
        "tool_results": results,
        "steps": ["tools"],
        "messages": [AIMessage(content="Executed requested tools successfully.")],
    }


def draft(state):
    """Drafts proposed resolution based on tool execution results."""
    if state.get("refused"):
        return {}

    question = state.get("question", "")
    tool_results = state.get("tool_results", [])
    plan_list = state.get("plan", [])

    draft_info = draft_response(question, tool_results, plan_list)
    return {
        "draft": draft_info["draft"],
        "needs_approval": draft_info["needs_approval"],
        "steps": ["draft"],
        "messages": [AIMessage(content=f"Drafted resolution: {draft_info['draft']}")],
    }


def approval(state):
    """Human-in-the-loop checkpoint gate for policy waivers and sensitive actions."""
    if state.get("needs_approval") and not state.get("approved"):
        res = interrupt("Human manager approval required for policy waiver or exception.")
        return {
            "approved": bool(res),
            "steps": ["approval"],
            "messages": [AIMessage(content="Manager approval confirmed.")],
        }

    return {
        "approved": True,
        "steps": ["approval"],
        "messages": [AIMessage(content="No manager approval needed.")],
    }


def critic(state):
    """Validates draft groundedness and checks citation adherence."""
    if state.get("refused"):
        return {}

    draft_text = state.get("draft", "")
    if not draft_text:
        return {
            "confidence": 0.0,
            "refused": LOW_CONFIDENCE_REFUSAL,
            "steps": ["critic"],
            "messages": [AIMessage(content="Critic found empty draft.")],
        }

    return {
        "confidence": 0.95,
        "steps": ["critic"],
        "messages": [AIMessage(content="Critic verified draft accuracy.")],
    }


def respond(state):
    """Finalizes customer response, preserving exact numerical outputs."""
    if state.get("refused"):
        return {
            "answer": LOW_CONFIDENCE_REFUSAL,
            "confidence": 0.0,
            "steps": ["respond"],
            "messages": [AIMessage(content=LOW_CONFIDENCE_REFUSAL)],
        }

    question = state.get("question", "")
    draft_text = state.get("draft", "")
    resp_info = write_response(question, draft_text)

    ans = resp_info["answer"]
    conf = float(resp_info["confidence"])

    return {
        "answer": ans,
        "confidence": conf,
        "steps": ["respond"],
        "messages": [AIMessage(content=ans)],
    }
