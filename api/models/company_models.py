from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CompanyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)


class CompanyUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    email: Optional[str] = Field(None, max_length=255)
    active_form_version_id: Optional[int] = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    active_form_version_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CompanyListResponse(BaseModel):
    companies: list[CompanyResponse]
