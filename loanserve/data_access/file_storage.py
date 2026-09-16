import csv
from pathlib import Path

from loanserve.core.entities import create_loan_application
from loanserve.core.exceptions import StorageError


class ApplicationFileStorage:
    """Stores application records as CSV and loads them back."""

    def __init__(self, storage_directory):
        self.storage_directory = Path(storage_directory)
        self.storage_directory.mkdir(parents=True, exist_ok=True)

    def save_csv(self, application_records, file_name):
        if not application_records:
            raise StorageError("No application records given to save.")

        file_path = self.storage_directory / file_name
        fieldnames = list(application_records[0].keys())

        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(application_records)

        return str(file_path)

    def load_csv(self, file_name):
        file_path = self.storage_directory / file_name
        if not file_path.exists():
            raise StorageError(f"File not found: {file_name}")

        try:
            with open(file_path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                return list(reader)
        except FileNotFoundError as exc:
            raise StorageError(f"File not found: {file_name}") from exc

    def load_applications(self, file_name):
        records = self.load_csv(file_name)
        return [create_loan_application(record) for record in records]


if __name__ == "__main__":
    storage = ApplicationFileStorage("output/day03_storage")
    gold_record = [
        {
            "loan_type": "gold",
            "loan_amount_inr": "400000",
            "tenure_months": "24",
            "monthly_income_inr": "90000",
            "age_years": "41",
            "collateral_value_inr": "600000",
        }
    ]
    storage.save_csv(gold_record, "applications.csv")
    loaded = storage.load_csv("applications.csv")
    print(f"{len(loaded)} row(s) read back")
    apps = storage.load_applications("applications.csv")
    print([type(a).__name__ for a in apps])