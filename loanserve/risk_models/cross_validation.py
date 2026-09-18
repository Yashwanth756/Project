from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from config.constants import CROSS_VALIDATION_FOLDS, RANDOM_SEED
from loanserve.risk_models.baseline_model import build_baseline_model
from loanserve.risk_models.feature_pipeline import (
    build_feature_pipeline,
    split_for_modelling,
)
from loanserve.risk_models.tree_models import (
    build_decision_tree,
    build_random_forest,
)


def build_linear_svm():
    """Builds unfitted LinearSVC pipeline."""
    return Pipeline(
        [
            ("prepare", build_feature_pipeline()),
            (
                "classify",
                LinearSVC(
                    C=0.1,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                    max_iter=3000,
                ),
            ),
        ]
    )


def every_model():
    """Returns freshly built unfitted candidate pipelines."""
    return {
        "logistic_baseline": build_baseline_model(),
        "decision_tree": build_decision_tree(),
        "random_forest": build_random_forest(),
        "linear_svm": build_linear_svm(),
    }


def score_across_folds(model, features, target):
    """Measures model across stratified folds using ROC-AUC."""
    skf = StratifiedKFold(
        n_splits=CROSS_VALIDATION_FOLDS,
        shuffle=True,
        random_state=RANDOM_SEED,
    )
    fold_scores = []

    for train_idx, val_idx in skf.split(features, target):
        m = clone(model)
        X_tr = features.iloc[train_idx] if hasattr(features, "iloc") else features[train_idx]
        y_tr = target.iloc[train_idx] if hasattr(target, "iloc") else target[train_idx]
        X_val = features.iloc[val_idx] if hasattr(features, "iloc") else features[val_idx]
        y_val = target.iloc[val_idx] if hasattr(target, "iloc") else target[val_idx]

        m.fit(X_tr, y_tr)
        if hasattr(m, "predict_proba"):
            scores = m.predict_proba(X_val)[:, 1]
        else:
            scores = m.decision_function(X_val)

        auc = round(float(roc_auc_score(y_val, scores)), 4)
        fold_scores.append(auc)

    mean_roc_auc = round(float(np.mean(fold_scores)), 4)
    spread = round(float(max(fold_scores) - min(fold_scores)), 4)

    return {
        "fold_scores": fold_scores,
        "mean_roc_auc": mean_roc_auc,
        "spread": spread,
    }


def training_against_holdout(model, cleaned_file_path):
    """Computes ROC-AUC on training rows vs holdout rows."""
    X_train, X_holdout, y_train, y_holdout = split_for_modelling(cleaned_file_path)
    model.fit(X_train, y_train)

    if hasattr(model, "predict_proba"):
        train_scores = model.predict_proba(X_train)[:, 1]
        holdout_scores = model.predict_proba(X_holdout)[:, 1]
    else:
        train_scores = model.decision_function(X_train)
        holdout_scores = model.decision_function(X_holdout)

    train_auc = round(float(roc_auc_score(y_train, train_scores)), 4)
    holdout_auc = round(float(roc_auc_score(y_holdout, holdout_scores)), 4)

    return train_auc, holdout_auc


def compare_across_folds(cleaned_file_path, output_path):
    """Runs fold comparison across all 4 models and records results."""
    X_train, _, y_train, _ = split_for_modelling(cleaned_file_path)
    candidates = every_model()

    results = {}
    for name, model in candidates.items():
        results[name] = score_across_folds(model, X_train, y_train)

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    return results


if __name__ == "__main__":
    cleaned_file = "processed_data/loan_applications_cleaned.csv"
    results = compare_across_folds(cleaned_file, "output/fold_scores.json")

    print(f"{'model':<20} {'folds':<15} {'mean':<8} {'spread':<8} {'training':<10} {'holdout':<8}")
    for name, model in every_model().items():
        res = results[name]
        tr_auc, ho_auc = training_against_holdout(model, cleaned_file)
        folds_str = f"{res['fold_scores'][0]}..{res['fold_scores'][-1]}"
        print(
            f"{name:<20} {folds_str:<15} {res['mean_roc_auc']:<8} {res['spread']:<8} {tr_auc:<10} {ho_auc:<8}"
        )

    best_name = max(results, key=lambda k: results[k]["mean_roc_auc"])
    print(f"best over five folds: {best_name} {results[best_name]['mean_roc_auc']}")
