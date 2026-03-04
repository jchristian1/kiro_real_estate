from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from gmail_lead_sync.models import Company
from api.models.web_ui_models import User
from api.models.company_models import (
    CompanyCreateRequest, CompanyUpdateRequest,
    CompanyResponse, CompanyListResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import NotFoundException, ValidationException
from api.services.audit_log import record_audit_log

router = APIRouter()


def get_db():
    from api.main import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    from api.auth import get_current_user as auth_get_current_user
    return auth_get_current_user(request, db)


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    data: CompanyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = Company(name=data.name, phone=data.phone, email=data.email)
    db.add(company)
    db.commit()
    db.refresh(company)
    record_audit_log(db, current_user.id, "company_created", "company", company.id, f"Created company {company.name}")
    return company


@router.get("/companies", response_model=CompanyListResponse)
def list_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    companies = db.query(Company).order_by(Company.name).all()
    return CompanyListResponse(companies=companies)


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise NotFoundException(message=f"Company {company_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    return company


@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    data: CompanyUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise NotFoundException(message=f"Company {company_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    if data.name is not None:
        company.name = data.name
    if data.phone is not None:
        company.phone = data.phone
    if data.email is not None:
        company.email = data.email
    db.commit()
    db.refresh(company)
    record_audit_log(db, current_user.id, "company_updated", "company", company.id, f"Updated company {company.name}")
    return company


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise NotFoundException(message=f"Company {company_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    record_audit_log(db, current_user.id, "company_deleted", "company", company.id, f"Deleted company {company.name}")
    db.delete(company)
    db.commit()
