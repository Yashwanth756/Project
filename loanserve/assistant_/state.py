import operator
from typing import Annotated, Any, TypedDict
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class AssistantState(TypedDict):
    """The central state schema for the LoanServe assistant workflow graph."""

    question: str
    messages: Annotated[list[AnyMessage], add_messages]
    steps: Annotated[list[str], operator.add]
    category: str | None
    urgency: str | None
    plan: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    draft: str | None
    citations: list[str]
    confidence: float | None
    needs_approval: bool
    approved: bool | None
    refused: str | None
    answer: str | None


def new_assistant_state(question: str) -> AssistantState:
    """Creates a fresh, unpolluted AssistantState dictionary for a customer question."""
    return {
        "question": question,
        "messages": [],
        "steps": [],
        "category": None,
        "urgency": None,
        "plan": [],
        "tool_results": [],
        "draft": None,
        "citations": [],
        "confidence": None,
        "needs_approval": False,
        "approved": None,
        "refused": None,
        "answer": "",
    }
