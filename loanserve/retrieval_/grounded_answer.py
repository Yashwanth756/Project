import re
from loanserve.core.exceptions import LoanServeError


class UngroundedAnswer(LoanServeError):
    """Raised when an answer lacks valid citations or cites unretrieved passages."""


def build_prompt(question, retrieved_chunks):
    """Constructs prompt containing numbered/labeled passages for grounded answer generation."""
    passages = []
    for chunk in retrieved_chunks:
        chunk_id = chunk["chunk_id"]
        text = chunk["text"]
        passages.append(f"[{chunk_id}] {text}")

    passages_block = "\n\n".join(passages)
    prompt = (
        "Answer the customer question based ONLY on the following policy passages.\n"
        "Include the chunk identifier in square brackets (e.g. [CHUNK_ID]) for every fact cited.\n\n"
        f"Policy Passages:\n{passages_block}\n\n"
        f"Customer Question: {question}\n\n"
        "Grounded Answer:"
    )
    return prompt


def cited_chunk_ids(answer_text):
    """Extracts unique cited chunk identifiers in square brackets matching chunk id syntax."""
    if not isinstance(answer_text, str):
        return []

    # Matches [CH0007], [TNC-HOM-013_001], [DOC_001], etc.
    # Excludes plain numbers like [4] or non-identifier words like [note]
    matches = re.findall(r"\[([A-Za-z0-9_-]+(?:_[0-9]+)?)\]", answer_text)
    result = []
    seen = set()

    for m in matches:
        # Ignore if it is purely numeric like '4' or lowercase non-id words like 'note'
        if m.isdigit():
            continue
        if m.islower() and "_" not in m and not any(c.isdigit() for c in m):
            continue
        if m not in seen:
            seen.add(m)
            result.append(m)

    return result


def check_citations(answer_text, retrieved_chunks):
    """Validates that answer contains valid citations and all citations belong to retrieved chunks."""
    citations = cited_chunk_ids(answer_text)
    if not citations:
        raise UngroundedAnswer("Answer does not contain any policy citations.")

    valid_ids = {c["chunk_id"] for c in retrieved_chunks}
    for cid in citations:
        if cid not in valid_ids:
            raise UngroundedAnswer(f"Cited passage [{cid}] was not among retrieved passages.")

    return citations


if __name__ == "__main__":
    sample_chunks = [
        {"chunk_id": "CH0007", "text": "Income proof may be waived for self-employed."},
        {"chunk_id": "CH0012", "text": "Foreclosure letters issued within five days."},
    ]
    p = build_prompt("can i get a loan without salary slip", sample_chunks)
    print("prompt built:")
    print(p[:150] + "...")
