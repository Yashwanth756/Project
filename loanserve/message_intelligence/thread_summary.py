from pathlib import Path
import re
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from loanserve.message_intelligence.attention import scaled_dot_product_attention
from loanserve.message_intelligence.text_cleaning import clean_message

PLACEHOLDERS_ONLY = {"url", "ticket", "application_ref", "<url>", "<ticket>", "<application_ref>"}


def split_into_sentences(messages):
    """Cleans and splits a sequence of thread messages into meaningful sentences."""
    sentences = []
    for msg in messages:
        if not msg or pd.isna(msg):
            continue
        cleaned = clean_message(str(msg))
        if not cleaned:
            continue
        # Split on punctuation (. ? !) or newlines
        parts = re.split(r"[.?!]+|\n+", cleaned)
        for part in parts:
            s = part.strip()
            if not s:
                continue
            # Drop if sentence is ONLY a placeholder
            if s.strip("<>-. ") in {"url", "ticket", "application_ref"}:
                continue
            sentences.append(s)
    return sentences


def score_sentences(sentences):
    """Scores sentences by the total attention each receives across the thread."""
    if not sentences:
        return np.array([])
    if len(sentences) == 1:
        return np.array([1.0])

    vectorizer = TfidfVectorizer()
    try:
        X = vectorizer.fit_transform(sentences).toarray()
    except ValueError:
        # If vocabulary is empty (e.g. only stopwords), return uniform scores
        return np.ones(len(sentences), dtype=np.float64)

    if X.shape[1] == 0:
        return np.ones(len(sentences), dtype=np.float64)

    _, weights = scaled_dot_product_attention(X, X, X)
    # Total attention received is column sum (axis=0)
    scores = weights.sum(axis=0)
    return scores


def summarise_thread(messages, max_sentences=3):
    """Selects top sentences by attention score and preserves original writing order."""
    sentences = split_into_sentences(messages)
    if len(sentences) <= max_sentences:
        return sentences

    scores = score_sentences(sentences)
    # Pick indices of top scores
    top_indices = np.argsort(scores)[-max_sentences:]
    ordered_indices = sorted(top_indices)

    return [sentences[i] for i in ordered_indices]


def summarise_corpus(threads_file_path, output_path):
    """Summarises every thread in the threads dataset and writes output."""
    df = pd.read_csv(threads_file_path).sort_values(["thread_id", "turn"])
    records = []

    for thread_id, group in df.groupby("thread_id", sort=False):
        msgs = list(group["message_text"])
        sentences = split_into_sentences(msgs)
        summary_sentences = summarise_thread(msgs, 3)
        summary_text = ". ".join(summary_sentences)
        if summary_text and not summary_text.endswith("."):
            summary_text += "."

        records.append(
            {
                "thread_id": thread_id,
                "messages": len(msgs),
                "sentences": len(sentences),
                "summary": summary_text,
            }
        )

    out_df = pd.DataFrame(records)
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_file, index=False)

    return len(out_df)


if __name__ == "__main__":
    threads_path = "data/message_threads.csv"
    output_path = "output/thread_summaries.csv"

    n_threads = summarise_corpus(threads_path, output_path)
    print(f"threads summarised: {n_threads}")
