from pathlib import Path
import json
import numpy as np
import pandas as pd

from config.constants import (
    CREDIT_BAND_NAMES,
    CREDIT_SCORE_BAND_EDGES,
    ENGINEERED_CATEGORICAL_COLUMNS,
    ENGINEERED_NUMERIC_COLUMNS,
    INTEREST_RATE_PERCENT_BY_LOAN_TYPE,
    TARGET_COLUMN,
)
from loanserve.core.loan_calculations import calculate_monthly_installment
from loanserve.risk_models.cross_validation import score_across_folds
from loanserve.risk_models.feature_pipeline import split_for_modelling
from loanserve.risk_models.tree_models import build_random_forest


def add_engineered_features(records):
    """Adds monthly_installment_inr, installment_to_income, and credit_band to a copy of DataFrame."""
    df = records.copy()

    # Vectorized / row-wise calculation of monthly installment
    def calc_installment(row):
        loan_type = str(row["loan_type"]).strip().lower()
        rate = INTEREST_RATE_PERCENT_BY_LOAN_TYPE[loan_type]
        principal = float(row["loan_amount_inr"])
        tenure = int(row["tenure_months"])
        return round(calculate_monthly_installment(principal, rate, tenure), 2)

    df["monthly_installment_inr"] = df.apply(calc_installment, axis=1)
    df["installment_to_income"] = np.round(
        df["monthly_installment_inr"] / df["monthly_income_inr"].astype(float), 4
    )
    df["credit_band"] = pd.cut(
        df["credit_score"].astype(float),
        bins=list(CREDIT_SCORE_BAND_EDGES),
        labels=list(CREDIT_BAND_NAMES),
        right=True,
        include_lowest=True,
    ).astype(str)

    return df


def write_enriched_file(cleaned_file_path, output_path):
    """Enriches cleaned records and writes to output_path."""
    df = pd.read_csv(cleaned_file_path)
    enriched = add_engineered_features(df)
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(out_path, index=False)
    return len(enriched)


def default_rate_by_band(enriched_file_path):
    """Returns default rate for each credit score band in CREDIT_BAND_NAMES order."""
    df = pd.read_csv(enriched_file_path)
    rates = {}
    for band in CREDIT_BAND_NAMES:
        sub = df[df["credit_band"] == band]
        if len(sub) > 0:
            rate = round(float(sub[TARGET_COLUMN].mean()), 4)
        else:
            rate = 0.0
        rates[band] = rate
    return rates


def measure_the_lift(enriched_file_path, output_path):
    """Measures lift of engineered features on random forest cross-validation."""
    # Run without engineered features
    X_train_raw, _, y_train_raw, _ = split_for_modelling(enriched_file_path)
    rf_plain = build_random_forest()
    plain_res = score_across_folds(rf_plain, X_train_raw, y_train_raw)
    without_score = plain_res["mean_roc_auc"]

    # Run with engineered features
    X_train_eng, _, y_train_eng, _ = split_for_modelling(
        enriched_file_path,
        extra_numeric=ENGINEERED_NUMERIC_COLUMNS,
        extra_categorical=ENGINEERED_CATEGORICAL_COLUMNS,
    )
    rf_eng = build_random_forest(
        extra_numeric=ENGINEERED_NUMERIC_COLUMNS,
        extra_categorical=ENGINEERED_CATEGORICAL_COLUMNS,
    )
    eng_res = score_across_folds(rf_eng, X_train_eng, y_train_eng)
    with_score = eng_res["mean_roc_auc"]

    lift = round(float(with_score - without_score), 4)
    result = {
        "without_engineered": without_score,
        "with_engineered": with_score,
        "lift": lift,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    return result


if __name__ == "__main__":
    train_cleaned = "processed_data/loan_applications_cleaned.csv"
    predict_cleaned = "processed_data/loan_applications_predict_cleaned.csv"

    train_enriched = "processed_data/loan_applications_enriched.csv"
    predict_enriched = "processed_data/loan_applications_predict_enriched.csv"

    n_train = write_enriched_file(train_cleaned, train_enriched)
    print(f"loan_applications_enriched.csv {n_train} rows")

    n_predict = write_enriched_file(predict_cleaned, predict_enriched)
    print(f"loan_applications_predict_enriched.csv {n_predict} rows")

    band_rates = default_rate_by_band(train_enriched)
    print(f"default rate by band: {band_rates}")

    lift_res = measure_the_lift(train_enriched, "output/feature_lift.json")
    print(f"without the three columns: {lift_res['without_engineered']}")
    print(f"with them: {lift_res['with_engineered']} | lift: {lift_res['lift']}")
