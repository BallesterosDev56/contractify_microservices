from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ActivityAction(str, Enum):
    CREATED = "CREATED"
    UPDATED = "UPDATED"
    GENERATED = "GENERATED"
    SIGNED = "SIGNED"
    SENT = "SENT"
    CANCELLED = "CANCELLED"


class ActivityLogOut(BaseModel):
    id: str
    action: ActivityAction
    user_id: str = Field(alias="userId")
    user_name: str = Field(alias="userName")
    details: dict[str, Any]
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
