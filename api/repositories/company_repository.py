"""
Company repository — all SQLAlchemy queries for the Company domain.

Requirements: 7.1, 7.2
"""

from typing import Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Company


class CompanyCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class CompanyRepository:
    """Data-access layer for Company records."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, company_id: int) -> Optional[Company]:
        """Return the company with the given primary key, or None."""
        return self._db.query(Company).filter(Company.id == company_id).first()

    def get_by_name(self, name: str) -> Optional[Company]:
        """Return the company with the given name, or None."""
        return self._db.query(Company).filter(Company.name == name).first()

    def list_all(self) -> list[Company]:
        """Return all companies ordered by name."""
        return self._db.query(Company).order_by(Company.name).all()

    def create(self, data: CompanyCreate) -> Company:
        """Create and persist a new company."""
        company = Company(name=data.name, phone=data.phone, email=data.email)
        self._db.add(company)
        self._db.commit()
        self._db.refresh(company)
        return company

    def update(self, company_id: int, data: CompanyUpdate) -> Optional[Company]:
        """Update a company. Returns the updated record, or None if not found."""
        company = self.get_by_id(company_id)
        if company is None:
            return None
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(company, field, value)
        self._db.commit()
        self._db.refresh(company)
        return company

    def delete(self, company_id: int) -> Optional[Company]:
        """Delete a company. Returns the deleted record, or None if not found."""
        company = self.get_by_id(company_id)
        if company is None:
            return None
        self._db.delete(company)
        self._db.commit()
        return company
