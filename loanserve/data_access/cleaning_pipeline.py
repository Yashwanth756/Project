from pathlib import Path
import pandas as pd

from config.constants import (
    MAXIMUM_CREDIT_SCORE,
    MINIMUM_CREDIT_SCORE,
    MODELLING_COLUMNS,
)
from loanserve.core.decorators import measure_duration


class ApplicationCleaner:
    """Surveys application data for faults and separates clean rows from rejected rows."""

    def __init__(self, raw_file_path):
        self.raw_file_path = Path(raw_file_path)
        self.raw_records = pd.read_csv(self.raw_file_path)

    def fault_reasons(self):
        df = self.raw_records
        reasons = pd.Series("", index=df.index, dtype=object)

        # 1. duplicate_application_id
        dup_mask = df["application_id"].duplicated(keep="first")
        reasons[dup_mask & (reasons == "")] = "duplicate_application_id"

        # 2. missing_required_field
        missing_mask = df[list(MODELLING_COLUMNS)].isna().any(axis=1)
        reasons[missing_mask & (reasons == "")] = "missing_required_field"

        # 3. income_not_positive
        income_numeric = pd.to_numeric(df["monthly_income_inr"], errors="coerce")
        income_mask = income_numeric <= 0
        reasons[income_mask & (reasons == "")] = "income_not_positive"

        # 4. unparseable_application_date
        parsed_dates = pd.to_datetime(df["application_date"], format="mixed", errors="coerce")
        date_mask = parsed_dates.isna()
        reasons[date_mask & (reasons == "")] = "unparseable_application_date"

        # 5. credit_score_out_of_range
        cs_numeric = pd.to_numeric(df["credit_score"], errors="coerce")
        cs_mask = (cs_numeric < MINIMUM_CREDIT_SCORE) | (cs_numeric > MAXIMUM_CREDIT_SCORE)
        reasons[cs_mask & (reasons == "")] = "credit_score_out_of_range"

        return reasons

    @measure_duration
    def clean_data(self, output_path):
        faults = self.fault_reasons()
        clean_mask = faults == ""
        cleaned = self.raw_records[clean_mask].copy()

        # application_date to YYYY-MM-DD
        parsed_dates = pd.to_datetime(cleaned["application_date"], format="mixed")
        cleaned["application_date"] = parsed_dates.dt.strftime("%Y-%m-%d")

        # employment_type: lower case, trimmed
        cleaned["employment_type"] = (
            cleaned["employment_type"].astype(str).str.strip().str.lower()
        )

        # applicant_city: trimmed, case unchanged
        cleaned["applicant_city"] = cleaned["applicant_city"].astype(str).str.strip()

        # age_years, existing_loan_count, tenure_months: integer
        cleaned["age_years"] = cleaned["age_years"].astype("int64")
        cleaned["existing_loan_count"] = cleaned["existing_loan_count"].astype("int64")
        cleaned["tenure_months"] = cleaned["tenure_months"].astype("int64")

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned.to_csv(out_path, index=False)
        return len(cleaned)

    def save_rejected_records(self, output_path):
        faults = self.fault_reasons()
        rejected_mask = faults != ""
        rejected = self.raw_records[rejected_mask].copy()
        rejected["rejection_reason"] = faults[rejected_mask]

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        rejected.to_csv(out_path, index=False)
        return len(rejected)


if __name__ == "__main__":
    cleaner_train = ApplicationCleaner("data/loan_applications_train.csv")
    kept_train = cleaner_train.clean_data("processed_data/loan_applications_cleaned.csv")
    dur_train = cleaner_train.clean_data.last_duration_seconds
    print(f"loan_applications_train.csv kept {kept_train} in {dur_train:.2f}s")

    cleaner_pred = ApplicationCleaner("data/loan_applications_predict.csv")
    kept_pred = cleaner_pred.clean_data("processed_data/loan_applications_predict_cleaned.csv")
    dur_pred = cleaner_pred.clean_data.last_duration_seconds
    print(f"loan_applications_predict.csv kept {kept_pred} in {dur_pred:.2f}s")

    rejected_count = cleaner_train.save_rejected_records("output/rejected_records.csv")
    print(f"rejected {rejected_count}")
