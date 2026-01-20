from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class PartyRole(str, Enum):
    HOST = "HOST"
    GUEST = "GUEST"
    WITNESS = "WITNESS"


class SignatureOut(BaseModel):
    id: str
    party_id: str = Field(alias="partyId")
    party_name: str = Field(alias="partyName")
    role: PartyRole
    signed_at: datetime = Field(alias="signedAt")
    ip_address: str = Field(alias="ipAddress")
    document_hash: str = Field(alias="documentHash")

    model_config = ConfigDict(populate_by_name=True)
