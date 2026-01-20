from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..schemas.activity import ActivityLogOut
from ..schemas.contracts import (
    BulkDownloadRequest,
    ContractDetailOut,
    ContractFilters,
    ContractListResponse,
    ContractOut,
    ContractStatsOut,
    ContractVersionOut,
    CreateContractRequest,
    PublicContractViewOut,
    UpdateContractContentRequest,
    UpdateContractRequest,
    UpdateContractStatusRequest,
)
from ..schemas.parties import AddPartyRequest, ContractPartyOut
from ..services import contracts_service as service

router = APIRouter()


def get_user_context(
    x_user_id: Annotated[str | None, Header(alias="X-User-Id")] = None,
    x_user_email: Annotated[str | None, Header(alias="X-User-Email")] = None,
    x_user_role: Annotated[str | None, Header(alias="X-User-Role")] = None,
) -> service.UserContext:
    if not x_user_id or not x_user_email:
        raise HTTPException(status_code=401, detail="Faltan credenciales de usuario.")
    return service.UserContext(user_id=x_user_id, user_email=x_user_email, user_role=x_user_role)


@router.get("/contracts", response_model=ContractListResponse)
async def list_contracts(
    filters: Annotated[ContractFilters, Depends()],
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractListResponse:
    try:
        return await service.list_contracts(session, user, filters)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/contracts", response_model=ContractOut, status_code=201)
async def create_contract(
    payload: CreateContractRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractOut:
    try:
        return await service.create_contract(session, user, payload.model_dump())
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/stats", response_model=ContractStatsOut)
async def get_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractStatsOut:
    try:
        return await service.stats(session, user)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/recent", response_model=list[ContractOut])
async def recent_contracts(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> list[ContractOut]:
    try:
        return await service.list_recent_contracts(session, user)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/pending", response_model=list[ContractOut])
async def pending_contracts(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> list[ContractOut]:
    try:
        return await service.list_pending_contracts(session, user)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}", response_model=ContractDetailOut)
async def get_contract(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractDetailOut:
    try:
        return await service.get_contract_detail(session, user, contract_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/contracts/{contract_id}", response_model=ContractOut)
async def update_contract(
    contract_id: str,
    payload: UpdateContractRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractOut:
    try:
        return await service.update_contract(session, user, contract_id, payload)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/contracts/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        await service.delete_contract(session, user, contract_id)
        return Response(status_code=204)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/contracts/{contract_id}/duplicate", response_model=ContractOut, status_code=201)
async def duplicate_contract(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> ContractOut:
    try:
        return await service.duplicate_contract(session, user, contract_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/contracts/{contract_id}/content", status_code=200)
async def update_content(
    contract_id: str,
    payload: UpdateContractContentRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        await service.update_content(session, user, contract_id, payload)
        return Response(status_code=200)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}/versions", response_model=list[ContractVersionOut])
async def get_versions(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> list[ContractVersionOut]:
    try:
        return await service.list_versions(session, user, contract_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.patch("/contracts/{contract_id}/status", status_code=200)
async def update_status(
    contract_id: str,
    payload: UpdateContractStatusRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        await service.update_status(session, user, contract_id, payload)
        return Response(status_code=200)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}/transitions")
async def get_transitions(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> dict[str, object]:
    try:
        return await service.get_transitions(session, user, contract_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}/history", response_model=list[ActivityLogOut])
async def get_history(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> list[ActivityLogOut]:
    try:
        logs = await service.list_activity(session, user, contract_id)
        return [ActivityLogOut.model_validate(log) for log in logs]
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}/parties", response_model=list[ContractPartyOut])
async def get_parties(
    contract_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> list[ContractPartyOut]:
    try:
        return await service.list_parties(session, user, contract_id)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/contracts/{contract_id}/parties", status_code=201)
async def add_party(
    contract_id: str,
    payload: AddPartyRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        await service.add_party(session, user, contract_id, payload)
        return Response(status_code=201)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.delete("/contracts/{contract_id}/parties/{party_id}", status_code=204)
async def delete_party(
    contract_id: str,
    party_id: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        await service.remove_party(session, user, contract_id, party_id)
        return Response(status_code=204)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.post("/contracts/bulk-download", status_code=200)
async def bulk_download(
    payload: BulkDownloadRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[service.UserContext, Depends(get_user_context)],
) -> Response:
    try:
        if not payload.contract_ids:
            raise HTTPException(status_code=400, detail="contractIds es requerido.")
        zip_bytes = await service.bulk_download(session, user, payload.contract_ids)
        return Response(content=zip_bytes, media_type="application/zip")
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc


@router.get("/contracts/{contract_id}/public", response_model=PublicContractViewOut)
async def public_contract_view(
    contract_id: str,
    token: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicContractViewOut:
    try:
        return await service.public_view(session, contract_id, token)
    except service.ServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
