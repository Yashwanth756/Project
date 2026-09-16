from datetime import datetime
from pathlib import Path
import re
import pandas as pd

from loanserve.data_access.database_loader import ApplicationDatabase


def extract_references(text):
    """Extracts and canonicalizes application references (LA/LP + 6 digits)."""
    if not isinstance(text, str):
        return []

    matches = re.findall(r"\b(?:la|lp)\d{6}\b", text, flags=re.IGNORECASE)
    seen = set()
    result = []
    for m in matches:
        upp = m.upper()
        if upp not in seen:
            seen.add(upp)
            result.append(upp)
    return result


def extract_amounts(text):
    """Extracts rupee amounts preceded by INR, Rs, or ₹ symbol."""
    if not isinstance(text, str):
        return []

    # Currency pattern: Rs., Rs, INR, ₹ followed by numbers with optional commas and decimals
    pattern = re.compile(
        r"(?:Rs\.?|INR|₹)\s*([0-9]+(?:,[0-9]+)*(?:\.[0-9]+)?)",
        re.IGNORECASE,
    )
    amounts = []
    for match in pattern.finditer(text):
        num_str = match.group(1).replace(",", "")
        try:
            val = float(num_str)
            amounts.append(val)
        except ValueError:
            pass
    return amounts


def extract_dates(text):
    """Extracts and validates dates, returning YYYY-MM-DD format with day-first parsing."""
    if not isinstance(text, str):
        return []

    # Matches DD/MM/YYYY, DD-MM-YYYY, DD/MM/YY, DD-MM-YY, YYYY-MM-DD
    pattern = re.compile(
        r"\b([0-3]?[0-9][/-][0-1]?[0-9][/-](?:[12][0-9])?[0-9]{2}|[12][0-9]{3}-[0-1]?[0-9]-[0-3]?[0-9])\b"
    )
    valid_dates = []

    for match in pattern.finditer(text):
        raw_date = match.group(1)
        parsed = None
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(raw_date, fmt)
                if dt.year < 100:
                    dt = dt.replace(year=2000 + dt.year)
                parsed = dt.strftime("%Y-%m-%d")
                break
            except ValueError:
                continue

        if parsed:
            valid_dates.append(parsed)

    return valid_dates


def link_references(references, database):
    """Separates extracted references into found (in DB) and not_found."""
    found = []
    not_found = []
    for ref in references:
        app = database.find_application(ref)
        if app is not None:
            found.append(ref)
        else:
            not_found.append(ref)
    return found, not_found


def extract_entities_from_corpus(messages_file_path, database_path, output_path):
    """Extracts references, amounts, and dates from entire corpus and links references."""
    df = pd.read_csv(messages_file_path)
    database = ApplicationDatabase(database_path)

    records = []
    for _, row in df.iterrows():
        msg_id = str(row["message_id"])
        text = str(row.get("message_text", ""))

        refs = extract_references(text)
        found, not_found = link_references(refs, database)
        amounts = extract_amounts(text)
        dates = extract_dates(text)

        # Only keep rows carrying at least one entity
        if found or not_found or amounts or dates:
            records.append(
                {
                    "message_id": msg_id,
                    "references_found": " ".join(found),
                    "references_not_found": " ".join(not_found),
                    "amounts": " ".join(str(a) for a in amounts),
                    "dates": " ".join(dates),
                }
            )

    out_df = pd.DataFrame(records)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, index=False)

    return len(out_df)


if __name__ == "__main__":
    messages_path = "data/customer_messages.csv"
    db_path = "database/loanserve.db"
    out_path = "output/message_entities.csv"

    n_entities = extract_entities_from_corpus(messages_path, db_path, out_path)
    print(f"message entities extracted: {n_entities}")
