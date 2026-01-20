from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy import and_, desc, func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ActivityLog, Contract, ContractParty, ContractVersion


async def get_contract(
    session: AsyncSession, contract_id: str, include_deleted: bool = False
) -> Contract | None:
    query = select(Contract).where(Contract.id == contract_id)
    if not include_deleted:
        query = query.where(Contract.deleted_at.is_(None))
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_contract(
    session: AsyncSession,
    title: str,
    contract_type: str,
    template_id: str,
    owner_user_id: str,
    metadata: dict,
) -> Contract:
    contract = Contract(
        title=title,
        contract_type=contract_type,
        template_id=template_id,
        owner_user_id=owner_user_id,
        metadata=metadata,
        status="DRAFT",
    )
    session.add(contract)
    await session.flush()
    return contract


async def update_contract_fields(
    session: AsyncSession, contract_id: str, fields: dict
) -> None:
    if not fields:
        return
    await session.execute(
        update(Contract)
        .where(Contract.id == contract_id)
        .values(**fields)
    )


async def soft_delete_contract(session: AsyncSession, contract_id: str) -> None:
    await session.execute(
        update(Contract)
        .where(Contract.id == contract_id)
        .values(deleted_at=datetime.utcnow())
    )


async def add_version(
    session: AsyncSession,
    contract_id: str,
    version: int,
    content: str,
    source: str,
    created_by: str,
) -> ContractVersion:
    contract_version = ContractVersion(
        contract_id=contract_id,
        version=version,
        content=content,
        source=source,
        created_by=created_by,
    )
    session.add(contract_version)
    await session.flush()
    return contract_version


async def get_latest_version(session: AsyncSession, contract_id: str) -> ContractVersion | None:
    result = await session.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(desc(ContractVersion.version))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_versions(session: AsyncSession, contract_id: str) -> list[ContractVersion]:
    result = await session.execute(
        select(ContractVersion)
        .where(ContractVersion.contract_id == contract_id)
        .order_by(desc(ContractVersion.version))
    )
    return list(result.scalars().all())


async def list_parties(session: AsyncSession, contract_id: str) -> list[ContractParty]:
    result = await session.execute(
        select(ContractParty)
        .where(ContractParty.contract_id == contract_id)
        .order_by(ContractParty.signing_order)
    )
    return list(result.scalars().all())


async def add_party(
    session: AsyncSession,
    contract_id: str,
    role: str,
    name: str,
    email: str,
    signing_order: int,
) -> ContractParty:
    party = ContractParty(
        contract_id=contract_id,
        role=role,
        name=name,
        email=email,
        signing_order=signing_order,
        signature_status="PENDING",
    )
    session.add(party)
    await session.flush()
    return party


async def remove_party(session: AsyncSession, contract_id: str, party_id: str) -> int:
    result = await session.execute(
        text(
            """
            DELETE FROM contracts.contract_parties
            WHERE contract_id = :contract_id AND id = :party_id
            """
        ),
        {"contract_id": contract_id, "party_id": party_id},
    )
    return result.rowcount or 0


async def get_next_version_number(session: AsyncSession, contract_id: str) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(ContractVersion.version), 0))
        .where(ContractVersion.contract_id == contract_id)
    )
    current_max = result.scalar_one()
    return int(current_max) + 1


async def log_activity(
    session: AsyncSession,
    contract_id: str,
    action: str,
    user_id: str,
    user_name: str,
    details: dict,
) -> ActivityLog:
    log = ActivityLog(
        contract_id=contract_id,
        action=action,
        user_id=user_id,
        user_name=user_name,
        details=details,
    )
    session.add(log)
    await session.flush()
    return log


async def list_activity_logs(session: AsyncSession, contract_id: str) -> list[ActivityLog]:
    result = await session.execute(
        select(ActivityLog)
        .where(ActivityLog.contract_id == contract_id)
        .order_by(desc(ActivityLog.timestamp))
    )
    return list(result.scalars().all())


async def list_contracts(
    session: AsyncSession,
    owner_user_id: str,
    status: str | None,
    search: str | None,
    template_id: str | None,
    from_date: datetime | None,
    to_date: datetime | None,
    sort_by: str,
    sort_order: str,
    page: int,
    page_size: int,
) -> tuple[list[Contract], int]:
    latest_versions = (
        select(
            ContractVersion.contract_id,
            func.max(ContractVersion.version).label("max_version"),
        )
        .group_by(ContractVersion.contract_id)
        .subquery()
    )

    latest_content = (
        select(ContractVersion.contract_id, ContractVersion.content)
        .join(
            latest_versions,
            and_(
                ContractVersion.contract_id == latest_versions.c.contract_id,
                ContractVersion.version == latest_versions.c.max_version,
            ),
        )
        .subquery()
    )

    query = (
        select(Contract)
        .outerjoin(latest_content, Contract.id == latest_content.c.contract_id)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
    )

    if status:
        query = query.where(Contract.status == status)
    if template_id:
        query = query.where(Contract.template_id == template_id)
    if from_date:
        query = query.where(Contract.created_at >= from_date)
    if to_date:
        query = query.where(Contract.created_at <= to_date)
    if search:
        search_like = f"%{search}%"
        query = query.where(
            or_(
                Contract.title.ilike(search_like),
                latest_content.c.content.ilike(search_like),
            )
        )

    sort_column = {
        "createdAt": Contract.created_at,
        "updatedAt": Contract.updated_at,
        "title": Contract.title,
        "status": Contract.status,
    }.get(sort_by, Contract.created_at)

    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    count_query = select(func.count(func.distinct(Contract.id))).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    return list(result.scalars().all()), int(total)


async def list_recent_contracts(session: AsyncSession, owner_user_id: str) -> list[Contract]:
    result = await session.execute(
        select(Contract)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .order_by(desc(Contract.created_at))
        .limit(10)
    )
    return list(result.scalars().all())


async def list_pending_contracts(session: AsyncSession, owner_user_id: str) -> list[Contract]:
    unsigned_party_exists = (
        select(ContractParty.id)
        .where(ContractParty.contract_id == Contract.id)
        .where(ContractParty.signature_status != "SIGNED")
        .exists()
    )
    result = await session.execute(
        select(Contract)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .where(Contract.status == "SIGNING")
        .where(unsigned_party_exists)
        .order_by(desc(Contract.updated_at))
    )
    return list(result.scalars().all())


async def count_pending_signatures(session: AsyncSession, owner_user_id: str) -> int:
    unsigned_party_exists = (
        select(ContractParty.id)
        .where(ContractParty.contract_id == Contract.id)
        .where(ContractParty.signature_status != "SIGNED")
        .exists()
    )
    result = await session.execute(
        select(func.count())
        .select_from(Contract)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .where(Contract.status == "SIGNING")
        .where(unsigned_party_exists)
    )
    return int(result.scalar_one())


async def contract_status_counts(session: AsyncSession, owner_user_id: str) -> dict[str, int]:
    result = await session.execute(
        select(Contract.status, func.count())
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .group_by(Contract.status)
    )
    return {row[0]: int(row[1]) for row in result.all()}


async def count_signed_this_month(session: AsyncSession, owner_user_id: str) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(Contract)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .where(Contract.status == "SIGNED")
        .where(Contract.signed_at >= func.date_trunc("month", func.now()))
    )
    return int(result.scalar_one())


async def list_contracts_by_ids(
    session: AsyncSession, owner_user_id: str, contract_ids: Iterable[str]
) -> list[Contract]:
    result = await session.execute(
        select(Contract)
        .where(Contract.owner_user_id == owner_user_id)
        .where(Contract.deleted_at.is_(None))
        .where(Contract.id.in_(list(contract_ids)))
    )
    return list(result.scalars().all())


async def all_parties_signed(session: AsyncSession, contract_id: str) -> bool:
    result = await session.execute(
        select(func.count())
        .select_from(ContractParty)
        .where(ContractParty.contract_id == contract_id)
        .where(ContractParty.signature_status != "SIGNED")
    )
    unsigned_count = int(result.scalar_one())
    return unsigned_count == 0


async def max_signing_order(session: AsyncSession, contract_id: str) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(ContractParty.signing_order), 0))
        .where(ContractParty.contract_id == contract_id)
    )
    return int(result.scalar_one())
