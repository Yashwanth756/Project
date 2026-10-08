from langgraph.graph import END, START, StateGraph

from loanserve.assistant.nodes import (
    approval,
    critic,
    draft,
    plan,
    respond,
    run_tools,
    triage,
)
from loanserve.assistant.state import AssistantState


def still_going(state):
    """Routing condition that immediately halts workflow execution if state contains a refusal."""
    if state.get("refused"):
        return "stop"
    return "go"


def build_assistant_graph(checkpointer=None):
    """Constructs and compiles the seven-node Assistant StateGraph."""
    builder = StateGraph(AssistantState)

    builder.add_node("triage", triage)
    builder.add_node("plan", plan)
    builder.add_node("tools", run_tools)
    builder.add_node("draft", draft)
    builder.add_node("approval", approval)
    builder.add_node("critic", critic)
    builder.add_node("respond", respond)

    builder.add_edge(START, "triage")
    builder.add_conditional_edges("triage", still_going, {"go": "plan", "stop": END})
    builder.add_conditional_edges("plan", still_going, {"go": "tools", "stop": END})
    builder.add_edge("tools", "draft")
    builder.add_conditional_edges("draft", still_going, {"go": "approval", "stop": END})
    builder.add_edge("approval", "critic")
    builder.add_conditional_edges("critic", still_going, {"go": "respond", "stop": END})
    builder.add_edge("respond", END)

    return builder.compile(checkpointer=checkpointer)
