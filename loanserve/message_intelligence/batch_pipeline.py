from pathlib import Path
import pandas as pd

from config.constants import MAXIMUM_MESSAGE_CHARACTERS
from loanserve.core.exceptions import LoanServeError
from loanserve.data_access.database_loader import ApplicationDatabase
from loanserve.message_intelligence.entity_extraction import (
    extract_amounts,
    extract_dates,
    extract_references,
    link_references,
)
from loanserve.message_intelligence.injection_guard import is_safe_to_send
from loanserve.message_intelligence.message_classifier import classify_message
from loanserve.risk_models.baseline_model import load_model


class UnusableMessage(LoanServeError):
    """Raised when an incoming message is corrupted, blank, oversized, or an injection attempt."""


def check_message(message_text):
    """Validates message readability, length, encoding, and injection safety."""
    if message_text is None or pd.isna(message_text) or not isinstance(message_text, str):
        raise UnusableMessage("Message is not a valid text string")

    stripped = message_text.strip()
    if not stripped:
        raise UnusableMessage("Message is blank")

    if len(message_text) > MAXIMUM_MESSAGE_CHARACTERS:
        raise UnusableMessage("Message is too long")

    if "\ufffd" in message_text or "\x00" in message_text:
        raise UnusableMessage("Message contains corrupted replacement characters")

    if not is_safe_to_send(message_text):
        raise UnusableMessage("Message contains prompt injection")


def process_message(message_text, models, database):
    """Processes a single raw message through validation, classification, and entity extraction."""
    check_message(message_text)

    classified = classify_message(models, message_text)
    refs = extract_references(message_text)
    found, not_found = link_references(refs, database)
    amounts = extract_amounts(message_text)
    dates = extract_dates(message_text)

    return {
        "category": classified.get("category", ""),
        "urgency": classified.get("urgency", ""),
        "references_found": " ".join(found),
        "references_not_found": " ".join(not_found),
        "amounts": " ".join(str(a) for a in amounts),
        "dates": " ".join(dates),
    }


def run_batch(messages_file_path, models_path, database_path, output_path, batch_size=500):
    """Runs batch pipeline over messages corpus and writes message_pipeline.csv."""
    df = pd.read_csv(messages_file_path)
    if batch_size is not None and batch_size > 0:
        batch_df = df.tail(batch_size).reset_index(drop=True)
    else:
        batch_df = df.reset_index(drop=True)

    models = load_model(models_path)
    database = ApplicationDatabase(database_path)

    records = []
    for _, row in batch_df.iterrows():
        msg_id = str(row["message_id"])
        msg_text = row.get("message_text", "")

        try:
            res = process_message(msg_text, models, database)
            records.append(
                {
                    "message_id": msg_id,
                    "status": "processed",
                    "failure": "",
                    "category": res["category"],
                    "urgency": res["urgency"],
                    "references_found": res["references_found"],
                    "references_not_found": res["references_not_found"],
                    "amounts": res["amounts"],
                    "dates": res["dates"],
                }
            )
        except UnusableMessage as err:
            records.append(
                {
                    "message_id": msg_id,
                    "status": "failed",
                    "failure": str(err),
                    "category": "",
                    "urgency": "",
                    "references_found": "",
                    "references_not_found": "",
                    "amounts": "",
                    "dates": "",
                }
            )

    out_df = pd.DataFrame(records)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, index=False)

    return len(out_df)


if __name__ == "__main__":
    messages_path = "data/customer_messages.csv"
    models_path = "artifacts/message_classifier.pkl"
    db_path = "database/loanserve.db"
    out_path = "output/message_pipeline.csv"

    n_proc = run_batch(messages_path, models_path, db_path, out_path, batch_size=500)
    print(f"batch completed: {n_proc} messages processed")
