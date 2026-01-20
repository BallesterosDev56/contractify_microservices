from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from math import ceil
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories import contracts_repository as repo
from ..schemas.activity import ActivityAction
from ..schemas.contracts import (
    ContractDetailOut,
    ContractFilters,
    ContractListResponse,
    ContractOut,
    ContractStatsOut,
    ContractVersionOut,
    PaginationOut,
    PublicContractViewOut,
    UpdateContractContentRequest,
    UpdateContractRequest,
    UpdateContractStatusRequest,
)
from ..schemas.parties import AddPartyRequest, ContractPartyOut
from ..schemas.signatures import SignatureOut


@dataclass(frozen=True)
class UserContext:
    user_id: str
    user_email: str
    user_role: str | None = None

    @property
    def user_name(self) -> str:
        return self.user_email


class ServiceError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    "DRAFT": ["GENERATED", "CANCELLED", "EXPIRED"],
    "GENERATED": ["SIGNING", "CANCELLED", "EXPIRED"],
    "SIGNING": ["SIGNED", "CANCELLED", "EXPIRED"],
    "SIGNED": [],
    "CANCELLED": [],
    "EXPIRED": [],
}

STATUS_ACTION = {
    "GENERATED": ActivityAction.GENERATED,
    "SIGNING": ActivityAction.SENT,
    "SIGNED": ActivityAction.SIGNED,
    "CANCELLED": ActivityAction.CANCELLED,
    "EXPIRED": ActivityAction.UPDATED,
    "DRAFT": ActivityAction.UPDATED,
}


async def list_contracts(
    session: AsyncSession, user: UserContext, filters: ContractFilters
) -> ContractListResponse:
    from_date = (
        datetime.combine(filters.from_date, datetime.min.time())
        if filters.from_date
        else None
    )
    to_date = (
        datetime.combine(filters.to_date, datetime.max.time())
        if filters.to_date
        else None
    )
    contracts, total = await repo.list_contracts(
        session=session,
        owner_user_id=user.user_id,
        status=filters.status.value if filters.status else None,
        search=filters.search,
        template_id=filters.template_id,
        from_date=from_date,
        to_date=to_date,
        sort_by=filters.sort_by,
        sort_order=filters.sort_order,
        page=filters.page,
        page_size=filters.page_size,
    )
    total_pages = ceil(total / filters.page_size) if total else 1
    return ContractListResponse(
        data=[ContractOut.model_validate(contract) for contract in contracts],
        pagination=PaginationOut(
            page=filters.page,
            pageSize=filters.page_size,
            totalPages=total_pages,
            totalItems=total,
        ),
    )


async def create_contract(
    session: AsyncSession, user: UserContext, payload: dict[str, Any]
) -> ContractOut:
    contract = await repo.create_contract(
        session=session,
        title=payload["title"],
        contract_type=payload["contract_type"],
        template_id=payload["template_id"],
        owner_user_id=user.user_id,
        metadata={},
    )
    await repo.log_activity(
        session=session,
        contract_id=contract.id,
        action=ActivityAction.CREATED,
        user_id=user.user_id,
        user_name=user.user_name,
        details={},
    )
    await session.commit()
    return ContractOut.model_validate(contract)


async def get_contract_detail(
    session: AsyncSession, user: UserContext, contract_id: str
) -> ContractDetailOut:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    latest_version = await repo.get_latest_version(session, contract_id)
    parties = await repo.list_parties(session, contract_id)
    content = latest_version.content if latest_version else ""
    return ContractDetailOut(
        **ContractOut.model_validate(contract).model_dump(by_alias=True),
        content=content,
        parties=[ContractPartyOut.model_validate(party) for party in parties],
        signatures=[],
        documentUrl=None,
        documentHash=None,
    )


async def update_contract(
    session: AsyncSession, user: UserContext, contract_id: str, payload: UpdateContractRequest
) -> ContractOut:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    update_fields: dict[str, Any] = {}
    details: dict[str, Any] = {}
    if payload.title is not None:
        update_fields["title"] = payload.title
        details["title"] = payload.title

    await repo.update_contract_fields(session, contract_id, update_fields)
    if update_fields:
        await repo.log_activity(
            session=session,
            contract_id=contract_id,
            action=ActivityAction.UPDATED,
            user_id=user.user_id,
            user_name=user.user_name,
            details={"changedFields": details},
        )
    await session.commit()
    updated = await repo.get_contract(session, contract_id)
    return ContractOut.model_validate(updated)


async def delete_contract(session: AsyncSession, user: UserContext, contract_id: str) -> None:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")
    if contract.status == "SIGNED":
        raise ServiceError(409, "No se puede eliminar un contrato firmado.")

    await repo.soft_delete_contract(session, contract_id)
    await repo.log_activity(
        session=session,
        contract_id=contract_id,
        action=ActivityAction.UPDATED,
        user_id=user.user_id,
        user_name=user.user_name,
        details={"softDelete": True},
    )
    await session.commit()


async def duplicate_contract(
    session: AsyncSession, user: UserContext, contract_id: str
) -> ContractOut:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    new_contract = await repo.create_contract(
        session=session,
        title=contract.title,
        contract_type=contract.contract_type,
        template_id=contract.template_id,
        owner_user_id=user.user_id,
        metadata=contract.metadata or {},
    )

    latest_version = await repo.get_latest_version(session, contract_id)
    if latest_version:
        await repo.add_version(
            session=session,
            contract_id=new_contract.id,
            version=1,
            content=latest_version.content,
            source="USER",
            created_by=user.user_id,
        )

    parties = await repo.list_parties(session, contract_id)
    for party in parties:
        await repo.add_party(
            session=session,
            contract_id=new_contract.id,
            role=party.role,
            name=party.name,
            email=party.email,
            signing_order=party.signing_order,
        )

    await repo.log_activity(
        session=session,
        contract_id=new_contract.id,
        action=ActivityAction.CREATED,
        user_id=user.user_id,
        user_name=user.user_name,
        details={"duplicatedFrom": contract_id},
    )
    await session.commit()
    return ContractOut.model_validate(new_contract)


async def update_content(
    session: AsyncSession,
    user: UserContext,
    contract_id: str,
    payload: UpdateContractContentRequest,
) -> None:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    next_version = await repo.get_next_version_number(session, contract_id)
    await repo.add_version(
        session=session,
        contract_id=contract_id,
        version=next_version,
        content=payload.content,
        source=payload.source,
        created_by=user.user_id,
    )

    action = ActivityAction.GENERATED if payload.source == "AI" else ActivityAction.UPDATED
    await repo.log_activity(
        session=session,
        contract_id=contract_id,
        action=action,
        user_id=user.user_id,
        user_name=user.user_name,
        details={"version": next_version, "source": payload.source},
    )
    await session.commit()


async def list_versions(
    session: AsyncSession, user: UserContext, contract_id: str
) -> list[ContractVersionOut]:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    versions = await repo.list_versions(session, contract_id)
    return [ContractVersionOut.model_validate(version) for version in versions]


async def update_status(
    session: AsyncSession,
    user: UserContext,
    contract_id: str,
    payload: UpdateContractStatusRequest,
) -> None:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    current_status = contract.status
    new_status = payload.status.value
    if new_status == current_status:
        raise ServiceError(400, "El contrato ya tiene ese estado.")
    if new_status not in ALLOWED_TRANSITIONS.get(current_status, []):
        raise ServiceError(400, "Transición de estado no permitida.")
    if new_status == "CANCELLED" and not payload.reason:
        raise ServiceError(400, "El estado CANCELLED requiere reason.")
    if new_status == "SIGNED":
        parties = await repo.list_parties(session, contract_id)
        if not parties:
            raise ServiceError(409, "No hay partes firmantes registradas.")
        if not await repo.all_parties_signed(session, contract_id):
            raise ServiceError(409, "Todas las partes deben estar SIGNED.")

    update_fields: dict[str, Any] = {"status": new_status}
    if new_status == "SIGNED":
        update_fields["signed_at"] = datetime.utcnow()
    else:
        update_fields["signed_at"] = None

    await repo.update_contract_fields(session, contract_id, update_fields)
    await repo.log_activity(
        session=session,
        contract_id=contract_id,
        action=STATUS_ACTION.get(new_status, ActivityAction.UPDATED),
        user_id=user.user_id,
        user_name=user.user_name,
        details={"previousStatus": current_status, "newStatus": new_status, "reason": payload.reason},
    )
    await session.commit()


async def get_transitions(
    session: AsyncSession, user: UserContext, contract_id: str
) -> dict[str, Any]:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")
    return {
        "currentStatus": contract.status,
        "allowedTransitions": ALLOWED_TRANSITIONS.get(contract.status, []),
    }


async def list_activity(
    session: AsyncSession, user: UserContext, contract_id: str
) -> list[Any]:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    logs = await repo.list_activity_logs(session, contract_id)
    return logs


async def list_parties(
    session: AsyncSession, user: UserContext, contract_id: str
) -> list[ContractPartyOut]:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")

    parties = await repo.list_parties(session, contract_id)
    return [ContractPartyOut.model_validate(party) for party in parties]


async def add_party(
    session: AsyncSession, user: UserContext, contract_id: str, payload: AddPartyRequest
) -> None:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")
    if contract.status == "SIGNED":
        raise ServiceError(409, "No se pueden agregar partes a un contrato firmado.")

    signing_order = payload.order
    if signing_order is None:
        signing_order = (await repo.max_signing_order(session, contract_id)) + 1

    await repo.add_party(
        session=session,
        contract_id=contract_id,
        role=payload.role.value,
        name=payload.name,
        email=payload.email,
        signing_order=signing_order,
    )
    await repo.log_activity(
        session=session,
        contract_id=contract_id,
        action=ActivityAction.UPDATED,
        user_id=user.user_id,
        user_name=user.user_name,
        details={"partyAdded": payload.email},
    )
    await session.commit()


async def remove_party(
    session: AsyncSession, user: UserContext, contract_id: str, party_id: str
) -> None:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")
    if contract.owner_user_id != user.user_id:
        raise ServiceError(403, "No tienes acceso a este contrato.")
    if contract.status == "SIGNED":
        raise ServiceError(409, "No se puede remover una parte de un contrato firmado.")

    deleted = await repo.remove_party(session, contract_id, party_id)
    if deleted == 0:
        raise ServiceError(404, "Parte no encontrada.")

    await repo.log_activity(
        session=session,
        contract_id=contract_id,
        action=ActivityAction.UPDATED,
        user_id=user.user_id,
        user_name=user.user_name,
        details={"partyRemoved": party_id},
    )
    await session.commit()


async def list_recent_contracts(
    session: AsyncSession, user: UserContext
) -> list[ContractOut]:
    contracts = await repo.list_recent_contracts(session, user.user_id)
    return [ContractOut.model_validate(contract) for contract in contracts]


async def list_pending_contracts(
    session: AsyncSession, user: UserContext
) -> list[ContractOut]:
    contracts = await repo.list_pending_contracts(session, user.user_id)
    return [ContractOut.model_validate(contract) for contract in contracts]


async def stats(session: AsyncSession, user: UserContext) -> ContractStatsOut:
    status_counts = await repo.contract_status_counts(session, user.user_id)
    total = sum(status_counts.values())
    pending_signatures = await repo.count_pending_signatures(session, user.user_id)
    signed_this_month = await repo.count_signed_this_month(session, user.user_id)
    return ContractStatsOut(
        total=total,
        byStatus=status_counts,
        pendingSignatures=pending_signatures,
        signedThisMonth=signed_this_month,
    )


async def bulk_download(
    session: AsyncSession, user: UserContext, contract_ids: Iterable[str]
) -> bytes:
    contracts = await repo.list_contracts_by_ids(session, user.user_id, contract_ids)
    if len(contracts) != len(set(contract_ids)):
        raise ServiceError(404, "Uno o más contratos no fueron encontrados.")

    content_map: dict[str, str] = {}
    for contract in contracts:
        latest_version = await repo.get_latest_version(session, contract.id)
        content_map[contract.id] = latest_version.content if latest_version else ""

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for contract in contracts:
            filename = f"contract_{contract.id}.html"
            zip_file.writestr(filename, content_map.get(contract.id, ""))

    return buffer.getvalue()


async def public_view(
    session: AsyncSession, contract_id: str, token: str
) -> PublicContractViewOut:
    contract = await repo.get_contract(session, contract_id)
    if not contract:
        raise ServiceError(404, "Contrato no encontrado.")

    latest_version = await repo.get_latest_version(session, contract_id)
    parties = await repo.list_parties(session, contract_id)
    if not parties:
        raise ServiceError(404, "No hay partes registradas para este contrato.")

    selected_party = next(
        (party for party in parties if party.signature_status != "SIGNED"), parties[0]
    )
    return PublicContractViewOut(
        id=contract.id,
        title=contract.title,
        content=latest_version.content if latest_version else "",
        party=ContractPartyOut.model_validate(selected_party),
        documentUrl=None,
    )
