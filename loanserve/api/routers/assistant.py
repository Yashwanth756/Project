import uuid
from fastapi import APIRouter, Request

from loanserve.api import schemas
from loanserve.assistant.workflow import run_assistant

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/ask", response_model=schemas.AssistantResponse)
def ask_assistant(submitted: schemas.AssistantRequest, request: Request):
    """Processes a question through the multi-agent graph."""
    thread_id = submitted.thread_id or f"thread-{uuid.uuid4().hex[:8]}"
    state, waiting = run_assistant(submitted.question, thread_id)

    narration = [str(m.content) for m in state.get("messages", []) if hasattr(m, "content")]

    return schemas.AssistantResponse(
        question=submitted.question,
        answer=state.get("answer", ""),
        steps=state.get("steps", []),
        refused=state.get("refused"),
        narration=narration,
        waiting_for_approval=waiting,
    )
