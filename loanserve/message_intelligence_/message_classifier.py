from pathlib import Path
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from config.constants import HOLDOUT_SHARE, RANDOM_SEED
from loanserve.message_intelligence.text_cleaning import clean_message
from loanserve.risk_models.baseline_model import save_model


def build_message_classifier():
    """Builds unfitted text classifier pipeline with embedded clean_message preprocessor."""
    return Pipeline(
        [
            (
                "vectorise",
                TfidfVectorizer(
                    preprocessor=clean_message,
                    ngram_range=(1, 2),
                    min_df=3,
                    sublinear_tf=True,
                ),
            ),
            (
                "classify",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def labelled_messages(messages_file_path):
    """Reads message corpus and filters to messages with valid category and urgency labels."""
    df = pd.read_csv(messages_file_path)
    return df.dropna(subset=["category", "urgency"]).reset_index(drop=True)


def train_for_label(messages, label_column):
    """Trains text classifier for specific label and evaluates on holdout set."""
    X_train, X_holdout, y_train, y_holdout = train_test_split(
        messages["message_text"],
        messages[label_column],
        test_size=HOLDOUT_SHARE,
        stratify=messages[label_column],
        random_state=RANDOM_SEED,
    )

    model = build_message_classifier()
    model.fit(X_train, y_train)

    preds = model.predict(X_holdout)
    acc = round(float(accuracy_score(y_holdout, preds)), 4)
    macro_f1 = round(float(f1_score(y_holdout, preds, average="macro")), 4)
    vocab_size = len(model.named_steps["vectorise"].vocabulary_)

    metrics = {
        "accuracy": acc,
        "macro_f1": macro_f1,
        "vocabulary": vocab_size,
    }

    return model, metrics


def classify_message(models, message_text):
    """Predicts category and urgency for a single raw message."""
    res = {}
    for label, model in models.items():
        pred = model.predict([message_text])[0]
        res[label] = str(pred)
    return res


if __name__ == "__main__":
    messages_path = "data/customer_messages.csv"
    corpus = labelled_messages(messages_path)

    models = {}
    for label in ("category", "urgency"):
        m, metrics = train_for_label(corpus, label)
        models[label] = m
        print(f"{label} {metrics}")

    save_model(models, "artifacts/message_classifier.pkl")
    print("saved: artifacts/message_classifier.pkl")

    sample_msg = (
        "Dear sir, regarding TKT-482913, my emi was debited twice this month "
        "Thanks in advance.\n--\nRavi Kumar\nSent from my iPhone"
    )
    classified = classify_message(models, sample_msg)
    print(f"a raw message, uncleaned: {classified}")
