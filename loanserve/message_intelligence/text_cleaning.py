from pathlib import Path
import re
import pandas as pd

from config.constants import (
    APPLICATION_REFERENCE_PLACEHOLDER,
    TICKET_PLACEHOLDER,
    URL_PLACEHOLDER,
)

URL_PATTERN = re.compile(r"(?:https?://\S+|www\.\S+)", re.IGNORECASE)
APPLICATION_REFERENCE_PATTERN = re.compile(r"\b(?:LA|LP)\d{6}\b", re.IGNORECASE)
TICKET_PATTERN = re.compile(r"\b(?:TKT|REF|SR|CASE)[-#]\d{4,}\b", re.IGNORECASE)
QUOTED_REPLY_PATTERN = re.compile(
    r"(?:\r?\n|^)\s*(?:On\s+.+?wrote:|-----Original\s+Message-----)[\s\S]*$",
    re.IGNORECASE,
)
SIGNATURE_PATTERN = re.compile(
    r"(?:\r?\n|^)\s*(?:--(?:\s*\r?\n|\s*$)|Best\s+regards,?|Thanks\s+and\s+regards,?|Sent\s+from\s+my)[\s\S]*$",
    re.IGNORECASE,
)
GREETING_PATTERN = re.compile(
    r"^\s*(?:hi|hello|dear|respected|good\s+(?:morning|afternoon|evening))(?:\s+(?:sir|madam|team|all|customer|officer|user))?[\s,.:;!-]*",
    re.IGNORECASE,
)
SIGN_OFF_PATTERN = re.compile(
    r"[\s,.:;!-]+(?:thanks\s+in\s+advance|awaiti?ng\s+your\s+response|best\s+regards|thanks\s+and\s+regards|regards|thank\s+you|thanks)[\s,.:;!-]*$",
    re.IGNORECASE,
)


def mask_urls(message_text):
    """Replaces URLs with URL_PLACEHOLDER."""
    if not isinstance(message_text, str):
        return ""
    return URL_PATTERN.sub(URL_PLACEHOLDER, message_text)


def mask_application_references(message_text):
    """Replaces application references (LA/LP + 6 digits) with APPLICATION_REFERENCE_PLACEHOLDER."""
    if not isinstance(message_text, str):
        return ""
    return APPLICATION_REFERENCE_PATTERN.sub(
        APPLICATION_REFERENCE_PLACEHOLDER, message_text
    )


def mask_ticket_references(message_text):
    """Replaces ticket references (TKT/REF/SR/CASE-#1234) with TICKET_PLACEHOLDER."""
    if not isinstance(message_text, str):
        return ""
    return TICKET_PATTERN.sub(TICKET_PLACEHOLDER, message_text)


def strip_quoted_reply(message_text):
    """Removes quoted reply email threads from the end of the message."""
    if not isinstance(message_text, str):
        return ""
    return QUOTED_REPLY_PATTERN.sub("", message_text)


def strip_signature(message_text):
    """Removes signature blocks from the end of the message."""
    if not isinstance(message_text, str):
        return ""
    return SIGNATURE_PATTERN.sub("", message_text)


def strip_greeting(message_text):
    """Removes opening greeting politeness."""
    if not isinstance(message_text, str):
        return ""
    return GREETING_PATTERN.sub("", message_text)


def strip_sign_off(message_text):
    """Removes closing courtesy from the end of the message."""
    if not isinstance(message_text, str):
        return ""
    return SIGN_OFF_PATTERN.sub("", message_text)


def clean_message(message_text):
    """Applies all cleaning rules in correct order and normalizes whitespace/case."""
    if message_text is None or pd.isna(message_text) or not isinstance(message_text, str):
        return ""

    text = message_text
    text = strip_quoted_reply(text)
    text = strip_signature(text)
    text = strip_sign_off(text)
    text = strip_greeting(text)
    text = mask_urls(text)
    text = mask_application_references(text)
    text = mask_ticket_references(text)

    # Collapse multiple whitespaces and strip
    cleaned = re.sub(r"\s+", " ", text).strip().lower()
    return cleaned


def clean_corpus(messages_file_path, output_path):
    """Cleans an entire message CSV corpus and saves cleaned_text column."""
    df = pd.read_csv(messages_file_path)
    df["cleaned_text"] = df["message_text"].apply(clean_message)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_file, index=False)

    return len(df)


if __name__ == "__main__":
    raw_path = "data/customer_messages.csv"
    cleaned_path = "processed_data/messages_cleaned.csv"

    n_cleaned = clean_corpus(raw_path, cleaned_path)
    print(f"messages cleaned: {n_cleaned}")

    raw_df = pd.read_csv(raw_path)
    cleaned_df = pd.read_csv(cleaned_path)

    raw_chars = raw_df["message_text"].astype(str).str.len().sum()
    cleaned_chars = cleaned_df["cleaned_text"].astype(str).str.len().sum()
    removed = raw_chars - cleaned_chars
    pct = round(100 * removed / raw_chars, 1)
    print(f"characters removed: {removed} ({pct}%)")

    samples = [0, 4, 12]
    for idx in samples:
        if idx < len(raw_df):
            print(f"raw    : {repr(raw_df.iloc[idx]['message_text'][:80])}")
            print(f"cleaned: {repr(cleaned_df.iloc[idx]['cleaned_text'][:80])}")
