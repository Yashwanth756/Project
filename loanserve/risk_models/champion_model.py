from pathlib import Path
import json
import numpy as np
import pandas as pd
from sklearn.model_selection import GridSearchCV, StratifiedKFold

from config.constants import (
    COST_OF_A_MISSED_DEFAULT_INR,
    COST_OF_A_REFUSED_GOOD_APPLICANT_INR,
    CROSS_VALIDATION_FOLDS,
    RANDOM_SEED,
)
from loanserve.risk_models.baseline_model import build_baseline_model, save_model
from loanserve.risk_models.feature_pipeline import split_for_modelling
from loanserve.risk_models.tree_models import build_random_forest


def candidate_grids():
    """Returns candidate models and their search grids."""
    return {
        "random_forest": (
            build_random_forest(),
            {
                "classify__max_depth": [6, 8],
                "classify__min_samples_leaf": [10, 20],
            },
        ),
        "logistic_baseline": (
            build_baseline_model(),
            {
                "classify__C": [0.01, 0.1, 1.0],
            },
        ),
    }


def search_for_the_champion(cleaned_file_path, output_path):
    """Searches for champion model across folds and records results."""
    X_train, _, y_train, _ = split_for_modelling(cleaned_file_path)
    grids = candidate_grids()
    skf = StratifiedKFold(
        n_splits=CROSS_VALIDATION_FOLDS,
        shuffle=True,
        random_state=RANDOM_SEED,
    )

    candidates_info = {}
    json_candidates = {}

    for name, (model, grid) in grids.items():
        search = GridSearchCV(
            estimator=model,
            param_grid=grid,
            cv=skf,
            scoring="roc_auc",
            refit=True,
        )
        search.fit(X_train, y_train)

        best_score = round(float(search.best_score_), 4)
        candidates_info[name] = {
            "model": search.best_estimator_,
            "settings": search.best_params_,
            "mean_roc_auc": best_score,
        }
        json_candidates[name] = {
            "settings": search.best_params_,
            "mean_roc_auc": best_score,
        }

    champion_name = max(candidates_info, key=lambda k: candidates_info[k]["mean_roc_auc"])

    record = {
        "champion": champion_name,
        "candidates": json_candidates,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)

    return champion_name, candidates_info


def cost_of_a_threshold(default_scores, actual_outcomes, threshold):
    """Prices one threshold choice based on missed defaults and refused good applicants."""
    scores = np.asarray(default_scores)
    outcomes = np.asarray(actual_outcomes)

    missed_defaults = int(((outcomes == 1) & (scores < threshold)).sum())
    refused_good_applicants = int(((outcomes == 0) & (scores >= threshold)).sum())

    total_cost = (
        missed_defaults * COST_OF_A_MISSED_DEFAULT_INR
        + refused_good_applicants * COST_OF_A_REFUSED_GOOD_APPLICANT_INR
    )

    return {
        "threshold": round(float(threshold), 2),
        "missed_defaults": missed_defaults,
        "refused_good_applicants": refused_good_applicants,
        "total_cost_inr": total_cost,
    }


def choose_threshold_on_cost(champion, cleaned_file_path, output_path):
    """Sweeps threshold on holdout set and chooses cheapest threshold."""
    _, X_holdout, _, y_holdout = split_for_modelling(cleaned_file_path)
    default_scores = champion.predict_proba(X_holdout)[:, 1]
    outcomes = y_holdout.to_numpy()

    swept = []
    # Sweep from 0.05 to 0.95 in steps of 0.05
    for t_val in np.arange(0.05, 0.96, 0.05):
        t = round(float(t_val), 2)
        swept.append(cost_of_a_threshold(default_scores, outcomes, t))

    cheapest = min(swept, key=lambda row: row["total_cost_inr"])
    cost_at_half = next(row["total_cost_inr"] for row in swept if row["threshold"] == 0.5)

    result = {
        "chosen_threshold": cheapest["threshold"],
        "cost_at_chosen_inr": cheapest["total_cost_inr"],
        "cost_at_half_inr": cost_at_half,
        "swept": swept,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    cleaned_file = "processed_data/loan_applications_cleaned.csv"
    champion_name, candidates = search_for_the_champion(
        cleaned_file, "output/champion_search.json"
    )

    for name, info in candidates.items():
        print(f"{name} {info['mean_roc_auc']} {info['settings']}")

    champion_model = candidates[champion_name]["model"]
    save_model(champion_model, "artifacts/champion.pkl")
    print(f"champion: {champion_name} | saved: artifacts/champion.pkl")

    choice = choose_threshold_on_cost(
        champion_model, cleaned_file, "output/threshold_choice.json"
    )
    diff = choice["cost_at_half_inr"] - choice["cost_at_chosen_inr"]
    print(
        f"threshold chosen on cost: {choice['chosen_threshold']} costing {choice['cost_at_chosen_inr']}"
    )
    print(
        f"the habitual 0.5 costs {choice['cost_at_half_inr']} — a difference of {diff}"
    )
