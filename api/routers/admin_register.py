"""
Public company registration endpoint.

Creates a new company + company_admin user in a single transaction.
No authentication required — this is the self-service signup flow.
Rate limited to prevent abuse.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
import re

from api.dependencies.db import get_db
from api.models.web_ui_models import User
from api.models.company_models import CompanyResponse
from gmail_lead_sync.models import Company
from api.auth import hash_password
from api.exceptions import ConflictException
from api.models.error_models import ErrorCode
from api.utils.rate_limiter import limiter

router = APIRouter()


class RegisterRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=255)
    company_email: str | None = Field(None, max_length=255)
    company_phone: str | None = Field(None, max_length=50)
    admin_username: str = Field(..., min_length=3, max_length=100)
    admin_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("admin_username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9_.-]+$', v):
            raise ValueError("Username may only contain letters, numbers, underscores, dots, and hyphens.")
        return v


class RegisterResponse(BaseModel):
    company: CompanyResponse
    username: str
    message: str


@router.post(
    "/auth/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Authentication"],
)
@limiter.limit("5/minute")
async def register_company(
    request: Request,
    body: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Self-service company registration.

    Creates a company and a company_admin user in one atomic transaction.
    The admin user can then log in and configure pipelines, templates, forms, etc.
    """
    # Check username not already taken
    existing_user = db.query(User).filter(User.username == body.admin_username).first()
    if existing_user:
        raise ConflictException(
            message="Username is already taken. Please choose another.",
            code=ErrorCode.CONFLICT_DUPLICATE,
        )

    # Check company name not already taken
    existing_company = db.query(Company).filter(Company.name == body.company_name).first()
    if existing_company:
        raise ConflictException(
            message="A company with that name already exists.",
            code=ErrorCode.CONFLICT_DUPLICATE,
        )

    # Create company
    company = Company(
        name=body.company_name,
        email=body.company_email,
        phone=body.company_phone,
    )
    db.add(company)
    db.flush()  # get company.id without committing

    # Create admin user linked to company
    user = User(
        username=body.admin_username,
        password_hash=hash_password(body.admin_password),
        role="company_admin",
        company_id=company.id,
    )
    db.add(user)
    db.commit()
    db.refresh(company)

    return RegisterResponse(
        company=CompanyResponse(
            id=company.id,
            name=company.name,
            email=company.email,
            phone=company.phone,
            created_at=company.created_at,
        ),
        username=user.username,
        message="Account created successfully. You can now sign in.",
    )
