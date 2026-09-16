from pathlib import Path
import re

from config.constants import POLICY_CHUNK_CHARACTERS
from loanserve.retrieval.document_loader import load_policy_documents


def looks_like_heading(line):
    """Determines whether a single line is a policy section heading."""
    if not isinstance(line, str):
        return False
    s = line.strip()
    if not s or len(s) < 3 or len(s) > 60:
        return False
    if s.endswith(".") or s.endswith("!") or s.endswith(";") or s.endswith(":"):
        return False
    if s.lower().startswith("document reference") or "effective" in s.lower() or "·" in s:
        return False
    if s[0].islower():
        return False
    words = s.split()
    if len(words) > 8:
        return False
    return True


def split_into_sections(text):
    """Splits policy text into list of (heading, body) tuples."""
    lines = text.splitlines()
    sections = []
    current_heading = None
    current_body = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if looks_like_heading(line):
            if current_heading and current_body:
                sections.append((current_heading, " ".join(current_body)))
            current_heading = line
            current_body = []
        else:
            if current_heading is not None:
                current_body.append(line)

    if current_heading and current_body:
        sections.append((current_heading, " ".join(current_body)))

    return sections


def split_without_breaking_words(text, limit=POLICY_CHUNK_CHARACTERS):
    """Splits text into chunks of at most limit characters without splitting words."""
    words = text.split()
    if not words:
        return []

    chunks = []
    current_chunk = []
    current_len = 0

    for word in words:
        w_len = len(word)
        if current_chunk and (current_len + 1 + w_len) > limit:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_len = w_len
        else:
            current_chunk.append(word)
            current_len = current_len + 1 + w_len if current_len > 0 else w_len

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def chunk_documents(documents, chunk_limit=POLICY_CHUNK_CHARACTERS):
    """Chunks all loaded policy documents into structured, identifiable passages."""
    all_chunks = []
    for doc in documents:
        doc_id = doc["document_id"]
        sections = split_into_sections(doc["text"])
        chunk_idx = 0
        for heading, body in sections:
            pieces = split_without_breaking_words(body, chunk_limit)
            for piece in pieces:
                all_chunks.append(
                    {
                        "chunk_id": f"{doc_id}_{chunk_idx:03d}",
                        "document_id": doc_id,
                        "heading": heading,
                        "text": piece,
                    }
                )
                chunk_idx += 1
    return all_chunks


if __name__ == "__main__":
    docs = load_policy_documents("data/policy_documents")
    chunks = chunk_documents(docs)
    print(f"total policy chunks: {len(chunks)}")
