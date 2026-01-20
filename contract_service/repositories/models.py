from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func, text

from ..db import Base


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = {"schema": "contracts"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    contract_type: Mapped[str] = mapped_column(String(100), nullable=False)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'DRAFT'")
    )
    metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    versions = relationship(
        "ContractVersion", back_populates="contract", cascade="all, delete-orphan"
    )
    parties = relationship(
        "ContractParty", back_populates="contract", cascade="all, delete-orphan"
    )
    activity_logs = relationship(
        "ActivityLog", back_populates="contract", cascade="all, delete-orphan"
    )


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    __table_args__ = {"schema": "contracts"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("contracts.contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    contract = relationship("Contract", back_populates="versions")


class ContractParty(Base):
    __tablename__ = "contract_parties"
    __table_args__ = {"schema": "contracts"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("contracts.contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    signature_status: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default=text("'PENDING'")
    )
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signing_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    contract = relationship("Contract", back_populates="parties")


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    __table_args__ = {"schema": "contracts"}

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("contracts.contracts.id", ondelete="CASCADE"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    contract = relationship("Contract", back_populates="activity_logs")
