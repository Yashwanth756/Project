from pathlib import Path
import json
import numpy as np
import pandas as pd

from loanserve.risk_models.baseline_model import (
    load_model,
    predict_default_probability,
)


def score_waiting_applications(champion, waiting_file_path):
    """Scores waiting applications with champion model and returns DataFrame."""
    df = pd.read_csv(waiting_file_path)
    probs = predict_default_probability(champion, df)

    res = pd.DataFrame(
        {
            "application_id": df["application_id"],
            "default_probability": np.round(probs, 6),
            "loan_amount_inr": df["loan_amount_inr"],
            "monthly_installment_inr": df["monthly_installment_inr"],
            "installment_to_income": df["installment_to_income"],
            "credit_band": df["credit_band"],
        }
    )
    return res


def build_work_queue(champion, waiting_file_path, threshold_path, output_path):
    """Builds prioritized work queue ordered riskiest first with refer/approve decisions."""
    scored_df = score_waiting_applications(champion, waiting_file_path)

    with open(threshold_path, "r", encoding="utf-8") as f:
        threshold_info = json.load(f)
    chosen_threshold = threshold_info["chosen_threshold"]

    # Decision: refer at or above threshold, approve below
    scored_df["decision"] = np.where(
        scored_df["default_probability"] >= chosen_threshold, "refer", "approve"
    )

    ordered_queue = (
        scored_df.sort_values(by="default_probability", ascending=False)
        .reset_index(drop=True)
    )

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    ordered_queue.to_csv(out_file, index=False)

    return ordered_queue


def queue_summary(queue_path):
    """Summarizes work queue counts, referred exposure, and share of exposure."""
    df = pd.read_csv(queue_path)
    waiting = len(df)
    referred = int((df["decision"] == "refer").sum())
    approved = int((df["decision"] == "approve").sum())

    exposure_referred_inr = int(
        df.loc[df["decision"] == "refer", "loan_amount_inr"].sum()
    )
    total_exposure = float(df["loan_amount_inr"].sum())

    if total_exposure > 0:
        share_of_exposure_referred = round(
            float(exposure_referred_inr / total_exposure), 4
        )
    else:
        share_of_exposure_referred = 0.0

    return {
        "waiting": waiting,
        "referred": referred,
        "approved": approved,
        "exposure_referred_inr": exposure_referred_inr,
        "share_of_exposure_referred": share_of_exposure_referred,
    }


if __name__ == "__main__":
    champion = load_model("artifacts/champion.pkl")
    predict_enriched = "processed_data/loan_applications_predict_enriched.csv"
    threshold_path = "output/threshold_choice.json"
    queue_path = "output/work_queue.csv"

    queue = build_work_queue(
        champion, predict_enriched, threshold_path, queue_path
    )
    print(queue.head(5).to_string(index=False))

    summary = queue_summary(queue_path)
    print(summary)

    top_row = queue.iloc[0]
    print(
        f"the officer starts at {top_row['application_id']} scored {top_row['default_probability']}"
    )
