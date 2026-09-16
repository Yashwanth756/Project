import abc
import re
from loanserve.api.orm_models import Applicant, StoredApplication

STORED_COLUMNS = (
    "application_id",
    "applicant_name",
    "loan_type",
    "loan_amount_inr",
    "tenure_months",
    "monthly_income_inr",
    "age_years",
    "credit_score",
    "collateral_value_inr",
    "pan_number",
    "mobile_number",
    "email_address",
)


class ApplicationRepository(abc.ABC):
    """Abstract interface for storing and retrieving loan applications."""

    @abc.abstractmethod
    def save_application(self, application_record):
        """Stores a new application under a minted identifier and returns it."""
        pass

    @abc.abstractmethod
    def find_application(self, application_id):
        """Reads one stored application or returns None if not found."""
        pass

    @abc.abstractmethod
    def list_applications(self, loan_type, limit, offset):
        """Returns one page of applications and the total number that matched."""
        pass

    @abc.abstractmethod
    def replace_application(self, application_id, application_record):
        """Overwrites an existing application or returns None if not found."""
        pass

    @abc.abstractmethod
    def delete_application(self, application_id):
        """Deletes an application and returns True if removed, False otherwise."""
        pass


class InMemoryApplicationRepository(ApplicationRepository):
    """In-memory store for loan applications."""

    def __init__(self):
        self.stored_applications = {}
        self.applications_created = 0

    def save_application(self, application_record):
        self.applications_created += 1
        app_id = f"LA{self.applications_created:06d}"
        stored = dict(application_record)
        stored["application_id"] = app_id
        self.stored_applications[app_id] = stored
        return dict(stored)

    def find_application(self, application_id):
        stored = self.stored_applications.get(application_id)
        if stored is None:
            return None
        return dict(stored)

    def list_applications(self, loan_type, limit, offset):
        matching = []
        for app in self.stored_applications.values():
            if loan_type is None or app["loan_type"].lower() == loan_type.lower():
                matching.append(dict(app))

        matching.sort(key=lambda x: x["application_id"])
        total = len(matching)
        page = matching[offset : offset + limit]
        return page, total

    def replace_application(self, application_id, application_record):
        if application_id not in self.stored_applications:
            return None
        stored = dict(application_record)
        stored["application_id"] = application_id
        self.stored_applications[application_id] = stored
        return dict(stored)

    def delete_application(self, application_id):
        if application_id in self.stored_applications:
            del self.stored_applications[application_id]
            return True
        return False


class SqlApplicationRepository(ApplicationRepository):
    """SQLAlchemy backed store for loan applications."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def as_record(self, stored):
        return {col: getattr(stored, col) for col in STORED_COLUMNS}

    def _next_application_id(self, session):
        apps = session.query(StoredApplication.application_id).all()
        if not apps:
            return "LA000001"
        max_num = 0
        for (app_id,) in apps:
            match = re.search(r"(\d+)", app_id)
            if match:
                num = int(match.group(1))
                if num > max_num:
                    max_num = num
        return f"LA{max_num + 1:06d}"

    def save_application(self, application_record):
        with self.session_factory() as session:
            next_id = self._next_application_id(session)
            name = application_record["applicant_name"]
            applicant = session.get(Applicant, name)
            if applicant is None:
                applicant = Applicant(applicant_name=name)
                session.add(applicant)
                session.flush()

            stored_data = {
                k: application_record.get(k)
                for k in STORED_COLUMNS
                if k != "application_id" and k in application_record
            }
            stored_data["application_id"] = next_id

            stored = StoredApplication(**stored_data)
            session.add(stored)
            session.commit()
            return self.as_record(stored)

    def find_application(self, application_id):
        with self.session_factory() as session:
            stored = session.get(StoredApplication, application_id)
            if stored is None:
                return None
            return self.as_record(stored)

    def list_applications(self, loan_type, limit, offset):
        with self.session_factory() as session:
            query = session.query(StoredApplication)
            if loan_type is not None:
                query = query.filter(StoredApplication.loan_type == loan_type)

            total = query.count()
            rows = (
                query.order_by(StoredApplication.application_id)
                .offset(offset)
                .limit(limit)
                .all()
            )
            page = [self.as_record(r) for r in rows]
            return page, total

    def replace_application(self, application_id, application_record):
        with self.session_factory() as session:
            stored = session.get(StoredApplication, application_id)
            if stored is None:
                return None

            name = application_record.get("applicant_name", stored.applicant_name)
            applicant = session.get(Applicant, name)
            if applicant is None:
                applicant = Applicant(applicant_name=name)
                session.add(applicant)
                session.flush()

            for k in STORED_COLUMNS:
                if k != "application_id" and k in application_record:
                    setattr(stored, k, application_record[k])

            session.commit()
            return self.as_record(stored)

    def delete_application(self, application_id):
        with self.session_factory() as session:
            stored = session.get(StoredApplication, application_id)
            if stored is None:
                return False
            session.delete(stored)
            session.commit()
            return True
