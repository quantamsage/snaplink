import io
from datetime import datetime, timezone
from typing import Annotated, Literal

import segno
from fastapi import APIRouter, Path, Query, Response

from .. import repository
from ..deps import AppSettings, CurrentUser, DbConn
from ..errors import AppError
from ..schemas import Link, LinkCreate, LinkList, LinkStats, LinkUpdate

router = APIRouter(prefix="/api/links", tags=["links"])

LinkId = Annotated[int, Path(ge=1)]


def _to_link(row: dict, base_url: str) -> Link:
    reason = repository.inactive_reason(row, datetime.now(timezone.utc))
    return Link(**row, short_url=f"{base_url}/r/{row['code']}", active=reason is None, inactive_reason=reason)


def _get_owned_link(conn, user_id: int, link_id: int) -> dict:
    # Someone else's link and a missing link both give 404, so IDs can't be probed.
    row = repository.get_link(conn, user_id, link_id)
    if row is None:
        raise AppError(404, "not_found", "Link not found.")
    return row


@router.get("", response_model=LinkList)
def list_links(
    user: CurrentUser,
    conn: DbConn,
    settings: AppSettings,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    rows, total = repository.list_links(conn, user["id"], limit, offset)
    return LinkList(items=[_to_link(r, settings.public_base_url) for r in rows], total=total)


@router.post("", response_model=Link, status_code=201)
def create_link(body: LinkCreate, user: CurrentUser, conn: DbConn, settings: AppSettings):
    try:
        row = repository.create_link(
            conn, user["id"], str(body.target_url), body.custom_code, body.expires_at, body.max_clicks
        )
    except repository.CodeTaken:
        raise AppError(409, "conflict", "That short code is already taken. Try another one.")
    return _to_link(row, settings.public_base_url)


@router.get("/{link_id}", response_model=Link)
def get_link(link_id: LinkId, user: CurrentUser, conn: DbConn, settings: AppSettings):
    return _to_link(_get_owned_link(conn, user["id"], link_id), settings.public_base_url)


@router.patch("/{link_id}", response_model=Link)
def update_link_limits(link_id: LinkId, body: LinkUpdate, user: CurrentUser, conn: DbConn, settings: AppSettings):
    changes = body.model_dump(include=body.model_fields_set)
    row = repository.update_limits(conn, user["id"], link_id, changes)
    if row is None:
        raise AppError(404, "not_found", "Link not found.")
    return _to_link(row, settings.public_base_url)


@router.get(
    "/{link_id}/qr",
    response_class=Response,
    responses={200: {"content": {"image/svg+xml": {}, "image/png": {}}}},
)
def link_qr_code(
    link_id: LinkId,
    user: CurrentUser,
    conn: DbConn,
    settings: AppSettings,
    format: Literal["svg", "png"] = "svg",
):
    """A QR code that opens the short URL (not the target), so scans are counted."""
    row = _get_owned_link(conn, user["id"], link_id)
    qr = segno.make(f"{settings.public_base_url}/r/{row['code']}", error="m")
    buffer = io.BytesIO()
    if format == "png":
        qr.save(buffer, kind="png", scale=10, border=4)
        media_type = "image/png"
    else:
        qr.save(buffer, kind="svg", scale=10, border=4, xmldecl=False, svgns=True)
        media_type = "image/svg+xml"
    return Response(
        content=buffer.getvalue(),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{row["code"]}-qr.{format}"'},
    )


@router.delete("/{link_id}", status_code=204)
def delete_link(link_id: LinkId, user: CurrentUser, conn: DbConn):
    if not repository.delete_link(conn, user["id"], link_id):
        raise AppError(404, "not_found", "Link not found.")
    return Response(status_code=204)


@router.get("/{link_id}/stats", response_model=LinkStats)
def link_stats(
    link_id: LinkId,
    user: CurrentUser,
    conn: DbConn,
    days: Annotated[int, Query(ge=1, le=90)] = 30,
):
    _get_owned_link(conn, user["id"], link_id)  # ownership check first
    return repository.link_stats(conn, link_id, days)
