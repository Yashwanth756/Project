from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from config.constants import RANDOM_SEED
from loanserve.risk_models.baseline_model import save_model
from loanserve.risk_models.feature_pipeline import (
    build_feature_pipeline,
    split_for_modelling,
)


def build_decision_tree():
    """Builds unfitted decision tree pipeline."""
    return Pipeline(
        [
            ("prepare", build_feature_pipeline()),
            (
                "classify",
                DecisionTreeClassifier(
                    max_depth=6,
                    min_samples_leaf=20,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def build_random_forest(extra_numeric=(), extra_categorical=()):
    """Builds unfitted random forest pipeline."""
    return Pipeline(
        [
            ("prepare", build_feature_pipeline(extra_numeric=extra_numeric, extra_categorical=extra_categorical)),
            (
                "classify",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=8,
                    min_samples_leaf=20,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def train_and_score(model, cleaned_file_path):
    """Fits model on fitting rows and returns (fitted_model, holdout_roc_auc)."""
    X_train, X_holdout, y_train, y_holdout = split_for_modelling(cleaned_file_path)
    model.fit(X_train, y_train)
    probs = model.predict_proba(X_holdout)[:, 1]
    score = round(float(roc_auc_score(y_holdout, probs)), 4)
    return model, score


def feature_importances(fitted_model):
    """Returns ranked feature importances DataFrame."""
    prep = fitted_model.named_steps["prepare"]
    feature_names = prep.get_feature_names_out()
    importances = fitted_model.named_steps["classify"].feature_importances_
    df = pd.DataFrame(
        {
            "feature": feature_names,
            "importance": np.round(importances, 4),
        }
    )
    return df.sort_values(by="importance", ascending=False).reset_index(drop=True)


def compare_class_weighting(cleaned_file_path, output_path):
    """Compares random forest with and without class weighting."""
    X_train, X_holdout, y_train, y_holdout = split_for_modelling(cleaned_file_path)

    forest_balanced = build_random_forest()
    forest_balanced.fit(X_train, y_train)
    probs_b = forest_balanced.predict_proba(X_holdout)[:, 1]
    preds_b = forest_balanced.predict(X_holdout)
    auc_b = round(float(roc_auc_score(y_holdout, probs_b)), 4)
    recall_b = round(float(recall_score(y_holdout, preds_b)), 4)

    forest_none = Pipeline(
        [
            ("prepare", build_feature_pipeline()),
            (
                "classify",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=8,
                    min_samples_leaf=20,
                    class_weight=None,
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )
    forest_none.fit(X_train, y_train)
    probs_n = forest_none.predict_proba(X_holdout)[:, 1]
    preds_n = forest_none.predict(X_holdout)
    auc_n = round(float(roc_auc_score(y_holdout, probs_n)), 4)
    recall_n = round(float(recall_score(y_holdout, preds_n)), 4)

    comparison = {
        "balanced": {"roc_auc": auc_b, "defaulters_caught": recall_b},
        "none": {"roc_auc": auc_n, "defaulters_caught": recall_n},
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison, f, indent=2)

    return comparison


if __name__ == "__main__":
    cleaned_file = "processed_data/loan_applications_cleaned.csv"
    dt, dt_score = train_and_score(build_decision_tree(), cleaned_file)
    rf, rf_score = train_and_score(build_random_forest(), cleaned_file)

    print(f"decision tree holdout ROC-AUC: {dt_score}")
    print(f"random forest holdout ROC-AUC: {rf_score}")

    save_model(dt, "artifacts/decision_tree.pkl")
    print("saved: artifacts/decision_tree.pkl")
    save_model(rf, "artifacts/random_forest.pkl")
    print("saved: artifacts/random_forest.pkl")

    importances = feature_importances(rf)
    print(importances.head(5).to_string(index=False))

    comp = compare_class_weighting(cleaned_file, "output/class_weight_comparison.json")
    print(comp)
