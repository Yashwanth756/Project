from pathlib import Path
import pandas as pd

from config.constants import (
    LARGE_EXPOSURE_INR,
    UNHAPPY_SENTIMENTS,
    VERY_LARGE_EXPOSURE_INR,
)
from loanserve.data_access.database_loader import ApplicationDatabase
from loanserve.message_intelligence.entity_extraction import extract_references
from loanserve.message_intelligence.message_classifier import classify_message
from loanserve.risk_models.baseline_model import load_model


def escalation_reasons(urgency, sentiment, exposure_inr):
    """Evaluates three potential escalation signals and returns list of reason descriptions."""
    reasons = []

    urg = str(urgency).strip().lower()
    sent = str(sentiment).strip().lower()
    exp = float(exposure_inr)

    if urg == "high":
        reasons.append("high urgency")

    if sent in [s.lower() for s in UNHAPPY_SENTIMENTS]:
        reasons.append(f"{sent} customer")

    if exp >= LARGE_EXPOSURE_INR:
        reasons.append(f"large exposure of Rs {int(exp):,}")

    return reasons


def must_be_seen_by_a_person(reasons, exposure_inr):
    """Determines if a case must be escalated to a human officer."""
    exp = float(exposure_inr)
    if exp >= VERY_LARGE_EXPOSURE_INR:
        return True
    return len(reasons) >= 2


def exposure_for(application_id, database):
    """Looks up application in database and returns loan amount as integer, or 0 if not found."""
    if not application_id:
        return 0
    app = database.find_application(application_id)
    if app and "loan_amount_inr" in app and app["loan_amount_inr"] is not None:
        return int(float(app["loan_amount_inr"]))
    return 0


def generate_escalation_report(
    threads_path,
    classifier_path,
    database_path,
    output_path,
    sample_size=50,
):
    """Reviews message threads for escalation and writes escalation_report.csv."""
    threads_df = pd.read_csv(threads_path)
    models = load_model(classifier_path)
    database = ApplicationDatabase(database_path)

    records = []
    # Sample threads
    unique_threads = threads_df["thread_id"].unique()[:sample_size]

    for t_id in unique_threads:
        t_group = threads_df[threads_df["thread_id"] == t_id].sort_values("turn")
        first_msg = str(t_group.iloc[0]["message_text"])
        all_text = " ".join(t_group["message_text"].astype(str))

        # Check references
        refs = extract_references(all_text)
        exp = 0
        if refs:
            for r in refs:
                e = exposure_for(r, database)
                if e > 0:
                    exp = e
                    break

        pred = classify_message(models, first_msg)
        urg = pred.get("urgency", "low")

        # Determine sentiment: assign unhappy for specific words or fallback to neutral
        text_lower = all_text.lower()
        if "angry" in text_lower or "unacceptable" in text_lower or "fraud" in text_lower or "terrible" in text_lower or "dispute" in text_lower:
            sent = "angry"
        elif "worried" in text_lower or "anxious" in text_lower or "concern" in text_lower or "help" in text_lower or "bounced" in text_lower:
            sent = "worried"
        else:
            sent = "neutral"

        reasons = escalation_reasons(urg, sent, exp)
        escalate = must_be_seen_by_a_person(reasons, exp)

        records.append(
            {
                "thread_id": t_id,
                "urgency": urg,
                "sentiment": sent,
                "exposure_inr": exp,
                "escalate": escalate,
                "reasons": "; ".join(reasons),
            }
        )

    out_df = pd.DataFrame(records)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, index=False)

    return len(out_df)


if __name__ == "__main__":
    threads_path = "data/message_threads.csv"
    classifier_path = "artifacts/message_classifier.pkl"
    database_path = "database/loanserve.db"
    out_path = "output/escalation_report.csv"

    n_report = generate_escalation_report(
        threads_path, classifier_path, database_path, out_path, sample_size=50
    )
    print(f"escalation report generated: {n_report} threads reviewed")
