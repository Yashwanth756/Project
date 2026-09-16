from pathlib import Path
import sqlite3
import pandas as pd

from loanserve.core.exceptions import StorageError


class ApplicationDatabase:
    """SQLite database for storing and querying cleaned loan applications."""

    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.database_path))
        self.connection.row_factory = sqlite3.Row

    def load_from_csv(self, cleaned_file_path):
        cleaned_path = Path(cleaned_file_path)
        if not cleaned_path.exists():
            raise StorageError(f"Cleaned file not found: {cleaned_file_path}")

        df = pd.read_csv(cleaned_path)
        df.to_sql("loan_applications", self.connection, if_exists="replace", index=False)
        self.connection.commit()
        return len(df)

    def find_application(self, application_id):
        cursor = self.connection.cursor()
        cursor.execute("SELECT * FROM loan_applications WHERE application_id = ?", (application_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def delete_application(self, application_id):
        cursor = self.connection.cursor()
        cursor.execute("DELETE FROM loan_applications WHERE application_id = ?", (application_id,))
        self.connection.commit()
        return cursor.rowcount


if __name__ == "__main__":
    db = ApplicationDatabase("database/loanserve.db")
    count = db.load_from_csv("processed_data/loan_applications_cleaned.csv")
    print(f"Loaded {count} applications")
    sample = db.find_application("LA000001")
    if sample:
        print(f"Sample: {sample['loan_type']}")
