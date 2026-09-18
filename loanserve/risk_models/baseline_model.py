from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline

from config.constants import RANDOM_SEED
from loanserve.risk_models.feature_pipeline import (
    build_feature_pipeline,
    select_modelling_columns,
    split_for_modelling,
)


def _patch_sklearn_object(obj):
    """Recursively patches missing compatibility attributes on unpickled sklearn estimators/transformers across versions."""
    if obj is None:
        return

    # If dict of models (e.g. message_classifier.pkl)
    if isinstance(obj, dict):
        for v in obj.values():
            _patch_sklearn_object(v)
        return

    # If Pipeline
    if hasattr(obj, "steps"):
        for _, step in obj.steps:
            _patch_sklearn_object(step)

    # If ColumnTransformer
    if hasattr(obj, "transformers_"):
        for item in obj.transformers_:
            if isinstance(item, tuple) and len(item) >= 2:
                _patch_sklearn_object(item[1])
    if hasattr(obj, "transformers"):
        for item in obj.transformers:
            if isinstance(item, tuple) and len(item) >= 2:
                _patch_sklearn_object(item[1])

    # SimpleImputer compatibility for scikit-learn 1.4+ / 1.5+
    if hasattr(obj, "statistics_"):
        if not hasattr(obj, "_fill_dtype"):
            try:
                obj._fill_dtype = obj.statistics_.dtype
            except Exception:
                obj._fill_dtype = np.dtype("float64")
        if not hasattr(obj, "keep_empty_features"):
            obj.keep_empty_features = False


def build_baseline_model():
    """Builds unfitted logistic baseline pipeline."""
    return Pipeline(
        [
            ("prepare", build_feature_pipeline()),
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


def train_baseline_model(cleaned_file_path):
    """Trains baseline logistic regression model and computes holdout ROC-AUC."""
    X_train, X_holdout, y_train, y_holdout = split_for_modelling(cleaned_file_path)
    model = build_baseline_model()
    model.fit(X_train, y_train)

    holdout_probs = model.predict_proba(X_holdout)[:, 1]
    score = round(float(roc_auc_score(y_holdout, holdout_probs)), 4)
    return model, score


def save_model(model, model_path):
    """Saves fitted pipeline to disk."""
    _patch_sklearn_object(model)
    out_path = Path(model_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, str(out_path))
    return str(out_path)


def load_model(model_path):
    """Loads fitted pipeline from disk and patches cross-version attributes."""
    obj = joblib.load(str(model_path))
    _patch_sklearn_object(obj)
    return obj


def predict_default_probability(model, records):
    """Returns probability of default for input records."""
    _patch_sklearn_object(model)
    # Determine features expected by pipeline
    if hasattr(model, "named_steps") and "prepare" in model.named_steps:
        prepare_step = model.named_steps["prepare"]
        transformers = getattr(prepare_step, "transformers_", getattr(prepare_step, "transformers", []))
        extra_num = []
        extra_cat = []
        for name, _trans, cols in transformers:
            if name == "numeric":
                extra_num = [c for c in cols if c not in ["age_years", "monthly_income_inr", "credit_score", "debt_to_income_ratio", "existing_loan_count", "late_payments_last_12_months", "loan_amount_inr", "tenure_months"]]
            elif name == "categorical":
                extra_cat = [c for c in cols if c not in ["employment_type", "loan_type"]]
        X = select_modelling_columns(records, extra_numeric=extra_num, extra_categorical=extra_cat)
    else:
        X = select_modelling_columns(records)
    return model.predict_proba(X)[:, 1]


def write_predictions(model, prediction_file_path, output_path):
    """Scores waiting applications and writes predictions.csv."""
    df = pd.read_csv(prediction_file_path)
    probs = predict_default_probability(model, df)
    out_df = pd.DataFrame(
        {
            "application_id": df["application_id"],
            "default_probability": np.round(probs, 6),
        }
    )
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(out_path, index=False)
    return len(out_df)


if __name__ == "__main__":
    train_path = "processed_data/loan_applications_cleaned.csv"
    predict_path = "processed_data/loan_applications_predict_cleaned.csv"

    model, score = train_baseline_model(train_path)
    saved_path = save_model(model, "artifacts/baseline_model.pkl")
    print(f"holdout ROC-AUC: {score} | saved: {saved_path}")

    loaded = load_model(saved_path)
    count = write_predictions(loaded, predict_path, "output/predictions.csv")
    print(f"predicted: {count} applications")
