from sqlalchemy import Column, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Applicant(Base):
    __tablename__ = "applicants"

    applicant_name = Column(String, primary_key=True)
    applications = relationship(
        "StoredApplication",
        back_populates="applicant",
        cascade="all, delete-orphan",
    )


class StoredApplication(Base):
    __tablename__ = "applications"

    application_id = Column(String, primary_key=True)
    applicant_name = Column(String, ForeignKey("applicants.applicant_name"), nullable=False)
    loan_type = Column(String, nullable=False)
    loan_amount_inr = Column(Float, nullable=False)
    tenure_months = Column(Integer, nullable=False)
    monthly_income_inr = Column(Float, nullable=False)
    age_years = Column(Integer, nullable=False)
    credit_score = Column(Integer, nullable=True)
    collateral_value_inr = Column(Float, nullable=True, default=0.0)
    pan_number = Column(String, nullable=False)
    mobile_number = Column(String, nullable=False)
    email_address = Column(String, nullable=False)

    applicant = relationship("Applicant", back_populates="applications")


def create_session_factory(database_url):
    """Creates tables and returns a SQLAlchemy sessionmaker."""
    if database_url == "sqlite://" or database_url == "sqlite:///:memory:":
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
        )

    Base.metadata.create_all(bind=engine)
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


if __name__ == "__main__":
    session_factory = create_session_factory("sqlite://")
    with session_factory() as session:
        applicant = Applicant(
            applicant_name="Aarav Nair",
            applications=[
                StoredApplication(
                    application_id="LA000001",
                    applicant_name="Aarav Nair",
                    loan_type="personal",
                    pan_number="ABCDE1234F",
                    mobile_number="9876543210",
                    email_address="aarav@example.com",
                    loan_amount_inr=500000.0,
                    tenure_months=36,
                    monthly_income_inr=60000.0,
                    age_years=32,
                    credit_score=760,
                    collateral_value_inr=0.0,
                )
            ],
        )
        session.add(applicant)
        session.commit()

        re_applicant = session.get(Applicant, "Aarav Nair")
        print(f"{len(re_applicant.applications)} application(s)")
