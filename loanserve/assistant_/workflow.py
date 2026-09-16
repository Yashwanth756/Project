from pathlib import Path
import os
from langgraph.checkpoint.sqlite import SqliteSaver

from config.constants import CHECKPOINT_DATABASE_PATH, LOW_CONFIDENCE_REFUSAL
from loanserve.assistant.graph import build_assistant_graph
from loanserve.assistant.state import new_assistant_state


def run_assistant(question, thread_id="default-thread", checkpoint_path=None):
    """Runs the assistant graph against a customer question with SQLite state checkpointing."""
    db_file = checkpoint_path or os.environ.get(
        "LOANSERVE_CHECKPOINTS", CHECKPOINT_DATABASE_PATH
    )
    p = Path(db_file)
    p.parent.mkdir(parents=True, exist_ok=True)

    config = {"configurable": {"thread_id": thread_id}}

    with SqliteSaver.from_conn_string(str(p)) as saver:
        graph = build_assistant_graph(checkpointer=saver)
        init_state = new_assistant_state(question)
        final_state = graph.invoke(init_state, config)

    waiting_for_approval = "__interrupt__" in final_state

    # If refused, ensure answer is LOW_CONFIDENCE_REFUSAL
    if final_state.get("refused") and not final_state.get("answer"):
        final_state["answer"] = LOW_CONFIDENCE_REFUSAL

    return final_state, waiting_for_approval


if __name__ == "__main__":
    q = "what is the monthly instalment on a 15 lakh loan at 9.5 percent over 120 months"
    state, waiting = run_assistant(q, "test-cli-run")
    print(f"steps: {state['steps']}")
    print(f"answer: {state['answer']}")
