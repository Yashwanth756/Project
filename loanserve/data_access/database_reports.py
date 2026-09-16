from pathlib import Path
import sqlite3


class DatabaseReports:
    """SQL aggregation reports over the loan_applications table."""

    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.connection = sqlite3.connect(str(self.database_path))
        self.connection.row_factory = sqlite3.Row

    def default_rate_by_product(self):
        cursor = self.connection.cursor()
        query = """
            SELECT 
                loan_type,
                COUNT(*) AS applications,
                SUM(defaulted) AS defaults,
                ROUND(CAST(SUM(defaulted) AS FLOAT) / COUNT(*), 4) AS default_rate
            FROM loan_applications
            GROUP BY loan_type
            ORDER BY loan_type
        """
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def volume_by_year(self):
        cursor = self.connection.cursor()
        query = """
            SELECT 
                SUBSTR(application_date, 1, 4) AS application_year,
                COUNT(*) AS applications,
                SUM(loan_amount_inr) AS total_amount_inr
            FROM loan_applications
            GROUP BY application_year
            ORDER BY application_year
        """
        cursor.execute(query)
        return [dict(row) for row in cursor.fetchall()]

    def exposure_by_city(self, minimum_applications):
        cursor = self.connection.cursor()
        query = """
            SELECT 
                applicant_city,
                COUNT(*) AS applications,
                SUM(loan_amount_inr) AS total_amount_inr,
                ROUND(CAST(SUM(defaulted) AS FLOAT) / COUNT(*), 4) AS default_rate
            FROM loan_applications
            GROUP BY applicant_city
            HAVING COUNT(*) >= ?
            ORDER BY total_amount_inr DESC
        """
        cursor.execute(query, (minimum_applications,))
        return [dict(row) for row in cursor.fetchall()]


if __name__ == "__main__":
    reports = DatabaseReports("database/loanserve.db")
    products = reports.default_rate_by_product()
    years = reports.volume_by_year()
    cities = reports.exposure_by_city(1250)
    print(products)
    print(years)
    if cities:
        print(cities[0])
