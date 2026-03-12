from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from api.models.web_ui_models import User
from api.models.company_models import (
    CompanyCreateRequest, CompanyUpdateRequest,
    CompanyResponse, CompanyListResponse
)
from api.models.error_models import ErrorCode
from api.exceptions import NotFoundException, ValidationException
from api.services.audit_log import record_audit_log
from api.repositories.company_repository import CompanyRepository, CompanyCreate, CompanyUpdate

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
    repo = CompanyRepository(db)
    company = repo.create(CompanyCreate(name=data.name, phone=data.phone, email=data.email))
    record_audit_log(db, current_user.id, "company_created", "company", company.id, f"Created company {company.name}")
    return company


@router.get("/companies", response_model=CompanyListResponse)
def list_companies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CompanyRepository(db)
    companies = repo.list_all()
    return CompanyListResponse(companies=companies)


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CompanyRepository(db)
    company = repo.get_by_id(company_id)
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
    repo = CompanyRepository(db)
    company = repo.update(company_id, CompanyUpdate(name=data.name, phone=data.phone, email=data.email))
    if not company:
        raise NotFoundException(message=f"Company {company_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    record_audit_log(db, current_user.id, "company_updated", "company", company.id, f"Updated company {company.name}")
    return company


@router.delete("/companies/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CompanyRepository(db)
    company = repo.get_by_id(company_id)
    if not company:
        raise NotFoundException(message=f"Company {company_id} not found", code=ErrorCode.NOT_FOUND_RESOURCE)
    record_audit_log(db, current_user.id, "company_deleted", "company", company.id, f"Deleted company {company.name}")
    repo.delete(company_id)
