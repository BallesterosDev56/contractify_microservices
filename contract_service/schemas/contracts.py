from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .parties import ContractPartyOut
from .signatures import SignatureOut


class ContractStatus(str, Enum):
    DRAFT = "DRAFT"
    GENERATED = "GENERATED"
    SIGNING = "SIGNING"
    SIGNED = "SIGNED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class CreateContractRequest(BaseModel):
    title: str
    template_id: str = Field(alias="templateId")
    contract_type: str = Field(alias="contractType")

    model_config = ConfigDict(populate_by_name=True)


class UpdateContractRequest(BaseModel):
    title: str | None = None


class UpdateContractContentRequest(BaseModel):
    content: str
    source: Literal["AI", "USER"]


class UpdateContractStatusRequest(BaseModel):
    status: ContractStatus
    reason: str | None = None


class ContractFilters(BaseModel):
    status: ContractStatus | None = None
    search: str | None = None
    template_id: str | None = Field(default=None, alias="templateId")
    from_date: date | None = Field(default=None, alias="fromDate")
    to_date: date | None = Field(default=None, alias="toDate")
    page: int = 1
    page_size: int = Field(default=20, alias="pageSize")
    sort_by: Literal["createdAt", "updatedAt", "title", "status"] = Field(
        default="createdAt", alias="sortBy"
    )
    sort_order: Literal["asc", "desc"] = Field(default="desc", alias="sortOrder")

    model_config = ConfigDict(populate_by_name=True)


class BulkDownloadRequest(BaseModel):
    contract_ids: list[str] = Field(alias="contractIds")

    model_config = ConfigDict(populate_by_name=True)


class ContractOut(BaseModel):
    id: str
    title: str
    status: ContractStatus
    template_id: str = Field(alias="templateId")
    contract_type: str = Field(alias="contractType")
    owner_user_id: str = Field(alias="ownerUserId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    signed_at: datetime | None = Field(default=None, alias="signedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContractDetailOut(ContractOut):
    content: str
    parties: list[ContractPartyOut]
    signatures: list[SignatureOut]
    document_url: str | None = Field(default=None, alias="documentUrl")
    document_hash: str | None = Field(default=None, alias="documentHash")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContractVersionOut(BaseModel):
    version: int
    content: str
    source: Literal["AI", "USER"]
    created_at: datetime = Field(alias="createdAt")
    created_by: str = Field(alias="createdBy")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ContractListResponse(BaseModel):
    data: list[ContractOut]
    pagination: "PaginationOut"


class PaginationOut(BaseModel):
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
    total_items: int = Field(alias="totalItems")

    model_config = ConfigDict(populate_by_name=True)


class ContractStatsOut(BaseModel):
    total: int
    by_status: dict[str, int] = Field(alias="byStatus")
    pending_signatures: int = Field(alias="pendingSignatures")
    signed_this_month: int = Field(alias="signedThisMonth")

    model_config = ConfigDict(populate_by_name=True)


class PublicContractViewOut(BaseModel):
    id: str
    title: str
    content: str
    party: ContractPartyOut
    document_url: str | None = Field(default=None, alias="documentUrl")

    model_config = ConfigDict(populate_by_name=True)
