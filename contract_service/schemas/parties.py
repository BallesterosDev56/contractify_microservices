from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PartyRole(str, Enum):
    HOST = "HOST"
    GUEST = "GUEST"
    WITNESS = "WITNESS"


class SignatureStatus(str, Enum):
    PENDING = "PENDING"
    INVITED = "INVITED"
    SIGNED = "SIGNED"


class AddPartyRequest(BaseModel):
    role: PartyRole
    name: str
    email: str
    order: int | None = None


class ContractPartyOut(BaseModel):
    id: str
    role: PartyRole
    name: str
    email: str
    signature_status: SignatureStatus = Field(alias="signatureStatus")
    signed_at: datetime | None = Field(default=None, alias="signedAt")
    order: int = Field(alias="order", validation_alias="signing_order")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
