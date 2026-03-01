import os
import time
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, Query, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import date
from urllib.parse import urlparse

from app.database import get_db, DATABASE_URL

router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

_rate_limit: dict = defaultdict(list)
_RATE_WINDOW = 60
_RATE_MAX = 30


def _check_token(x_admin_token: str = Header(None)):
    if not ADMIN_TOKEN or not x_admin_token or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _check_rate(request: Request):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < _RATE_WINDOW]
    if len(_rate_limit[ip]) >= _RATE_MAX:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    _rate_limit[ip].append(now)


def _no_store_response(data):
    return JSONResponse(content=data, headers={"Cache-Control": "no-store"})


@router.get("/db-info", summary="Prod DB identity and stats")
def db_info(request: Request, db: Session = Depends(get_db), _auth=Depends(_check_token)):
    _check_rate(request)
    parsed = urlparse(DATABASE_URL)
    dialect = parsed.scheme.split("+")[0] if "+" in parsed.scheme else parsed.scheme

    identity = db.execute(text("SELECT current_database(), version()")).fetchone()
    stats = db.execute(text("SELECT MAX(id), COUNT(*) FROM lift_sets")).fetchone()
    seq = db.execute(text("SELECT last_value, is_called FROM lift_sets_id_seq")).fetchone()

    return _no_store_response({
        "db_name": identity[0],
        "dialect": dialect,
        "host": parsed.hostname,
        "pg_version": identity[1][:60],
        "lift_sets_max_id": stats[0],
        "lift_sets_row_count": stats[1],
        "sequence_last_value": seq[0],
        "sequence_is_called": seq[1],
    })


@router.get("/lift-sets", summary="Query lift sets by date range")
def admin_lift_sets(
    request: Request,
    db: Session = Depends(get_db),
    _auth=Depends(_check_token),
    from_date: Optional[date] = Query(None, alias="from", examples=["2026-02-28"]),
    to_date: Optional[date] = Query(None, alias="to", examples=["2026-03-01"]),
    limit: int = Query(50, ge=1, le=200),
):
    _check_rate(request)
    q = "SELECT id, performed_at, exercise_id, weight, reps, tonnage FROM lift_sets"
    conditions = []
    params = {}
    if from_date:
        conditions.append("performed_at >= :from_date")
        params["from_date"] = from_date
    if to_date:
        conditions.append("performed_at <= :to_date")
        params["to_date"] = to_date
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY id DESC LIMIT :lim"
    params["lim"] = limit

    rows = db.execute(text(q), params).fetchall()
    return _no_store_response([
        {"id": r[0], "performed_at": str(r[1]), "exercise_id": r[2], "weight": float(r[3]), "reps": r[4], "tonnage": float(r[5])}
        for r in rows
    ])


@router.get("/lift-sets/by-id", summary="Lookup a lift set by id")
def admin_lift_set_by_id(
    request: Request,
    id: int = Query(...),
    db: Session = Depends(get_db),
    _auth=Depends(_check_token),
):
    _check_rate(request)
    row = db.execute(
        text("SELECT id, performed_at, exercise_id, weight, reps, tonnage, notes, source FROM lift_sets WHERE id = :id"),
        {"id": id},
    ).fetchone()
    if not row:
        return _no_store_response({"found": False, "id": id})
    return _no_store_response({
        "found": True,
        "id": row[0],
        "performed_at": str(row[1]),
        "exercise_id": row[2],
        "weight": float(row[3]),
        "reps": row[4],
        "tonnage": float(row[5]),
        "notes": row[6],
        "source": row[7],
    })
