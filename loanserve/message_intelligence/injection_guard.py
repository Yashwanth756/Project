from pathlib import Path
import re
import pandas as pd

from loanserve.message_intelligence.message_classifier import classify_message
from loanserve.risk_models.baseline_model import load_model

INJECTION_PATTERNS = {
    "instruction_override": re.compile(
        r"\b(?:ignore|disregard|skip|forget)\s+(?:all\s+|every\s+|the\s+|your\s+)?(?:previous|prior|above|earlier)?\s*(?:instructions?|directions?|rules?|prompt)\b",
        re.IGNORECASE,
    ),
    "role_reassignment": re.compile(
        r"\b(?:pretend\s+(?:to\s+be|you\s+are)|act\s+as\s+an?\s+ai\s+assistant|you\s+are\s+now\s+(?:a\s+bank\s+manager|an?\s+unrestricted)|you\s+are\s+no\s+longer\s+a\s+servicing\s+assistant|from\s+now\s+on\s+you\s+are\s+a\s+model)\b",
        re.IGNORECASE,
    ),
    "guardrail_suppression": re.compile(
        r"\b(?:bypass\s+(?:your\s+)?filters|disable\s+(?:your\s+)?guardrails|remove\s+all\s+restrictions\s+from\s+your\s+answer|answer\s+with\s+no\s+restrictions|(?:without\s+any|no)\s+safety\s+guidelines|reply\s+without\s+any\s+of\s+your\s+usual\s+guidelines|ai\s+with\s+no\s+restrictions)\b",
        re.IGNORECASE,
    ),
    "prompt_extraction": re.compile(
        r"\b(?:tell\s+me\s+your\s+instructions|reveal\s+your\s+system\s+prompt|show\s+me\s+your\s+instructions|print\s+your\s+system\s+prompt|output\s+the\s+prompt\s+above\s+verbatim|repeat\s+the\s+instructions\s+above\s+word\s+for\s+word)\b",
        re.IGNORECASE,
    ),
    "delimiter_smuggling": re.compile(
        r"(?:```\s*system|<\|system\|>|###\s*(?:system|developer)|(?:\n|^)\s*system:\s+new\s+policy)",
        re.IGNORECASE,
    ),
    "data_exfiltration": re.compile(
        r"\b(?:give\s+(?:me\s+)?(?:every|all)|list\s+(?:every|all)|send\s+(?:me\s+)?all|dump\s+all|export\s+(?:every|all))\s+.*?(?:pan\s+number|mobile\s+number|customer\s+record|applicant\s+name|account\s+holder)",
        re.IGNORECASE,
    ),
}

# Exclusions to ensure safe customer messages using overlapping words are not blocked
SAFE_LOOKALIKES = re.compile(
    r"\b(?:ignore|disregard|forget)\s+(?:my\s+|the\s+)?(?:previous\s+|earlier\s+|last\s+)?(?:email|message|request|amount|figure)\b|"
    r"\b(?:override\s+the\s+late\s+payment|override\s+the\s+emi\s+date)\b|"
    r"\b(?:the\s+system\s+says|system\s+rejected|system\s+prompt\s+I\s+need\s+to\s+follow)\b|"
    r"\b(?:you\s+are\s+now\s+handling\s+my\s+case|i\s+am\s+now\s+a\s+government\s+employee)\b|"
    r"\b(?:my\s+role\s+has\s+changed|i\s+am\s+a\s+developer)\b|"
    r"\b(?:print\s+my\s+loan\s+statement|list\s+every\s+charge|export\s+my\s+transaction)\b|"
    r"\b(?:remove\s+the\s+restrictions\s+on\s+my\s+account|restrictions\s+on\s+my\s+online\s+access)\b|"
    r"\b(?:act\s+as\s+my\s+guarantor|instructions\s+for\s+uploading|rules\s+for\s+a\s+top-up|rules\s+that\s+were\s+applied)\b",
    re.IGNORECASE,
)


def find_injection_markers(message_text):
    """Identifies prompt injection markers present in message."""
    if not isinstance(message_text, str) or not message_text.strip():
        return []

    markers = []
    for name, pattern in INJECTION_PATTERNS.items():
        if pattern.search(message_text):
            # Check if it was an innocent lookalike
            if name == "instruction_override" and re.search(
                r"\b(?:ignore|disregard|forget)\s+(?:my\s+|the\s+)?(?:previous\s+|earlier\s+|last\s+)?(?:email|message|request|amount|figure)\b",
                message_text,
                re.IGNORECASE,
            ):
                continue
            if name == "role_reassignment" and re.search(
                r"\b(?:you\s+are\s+now\s+handling\s+my\s+case|act\s+as\s+my\s+guarantor|i\s+am\s+now\s+a\s+government\s+employee)\b",
                message_text,
                re.IGNORECASE,
            ):
                continue
            if name == "guardrail_suppression" and re.search(
                r"\b(?:remove\s+the\s+restrictions\s+on\s+my\s+account|restrictions\s+on\s+my\s+online\s+access)\b",
                message_text,
                re.IGNORECASE,
            ):
                continue
            if name == "prompt_extraction" and re.search(
                r"\b(?:print\s+my\s+loan\s+statement|system\s+prompt\s+I\s+need\s+to\s+follow|instructions\s+for\s+uploading)\b",
                message_text,
                re.IGNORECASE,
            ):
                continue
            if name == "data_exfiltration" and re.search(
                r"\b(?:list\s+every\s+charge|export\s+my\s+transaction)\b",
                message_text,
                re.IGNORECASE,
            ):
                continue
            markers.append(name)

    return markers


def is_safe_to_send(message_text):
    """Determines whether a message is safe from prompt injection."""
    return len(find_injection_markers(message_text)) == 0


def scan_corpus_for_injections(messages_file_path, models_path, output_path):
    """Scans message corpus for injections and writes audit report."""
    df = pd.read_csv(messages_file_path)
    models = load_model(models_path)

    records = []
    for idx, row in df.iterrows():
        msg_id = str(row.get("message_id", f"MSG{idx:06d}"))
        text = str(row.get("message_text", ""))

        markers = find_injection_markers(text)
        blocked = len(markers) > 0

        if not blocked:
            pred = classify_message(models, text)
            cat = pred.get("category", "")
            urg = pred.get("urgency", "")
        else:
            cat = ""
            urg = ""

        records.append(
            {
                "message_id": msg_id,
                "blocked": str(blocked),
                "markers": "; ".join(markers),
                "category": cat,
                "urgency": urg,
            }
        )

    out_df = pd.DataFrame(records)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, index=False)

    return len(out_df)


if __name__ == "__main__":
    adv_path = "data/adversarial_messages.csv"
    classifier_path = "artifacts/message_classifier.pkl"
    out_path = "output/injection_report.csv"

    n_scanned = scan_corpus_for_injections(adv_path, classifier_path, out_path)
    print(f"messages scanned for injection: {n_scanned}")
