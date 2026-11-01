"""Router health: dipakai klien untuk "Uji Koneksi" sebelum menyimpan alamat."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from lan_server.config import settings
from lan_server.deps import get_db
from lan_server.schemas import HealthOut
from lan_server.serializers import utcnow

router = APIRouter(tags=["health"])

API_VERSION = "1.0.0"


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    """Tanpa auth: klien perlu tahu server hidup sebelum punya token."""
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "error"
    return HealthOut(
        status="ok" if database_status == "ok" else "degraded",
        app=settings.app_name,
        version=API_VERSION,
        database=database_status,
        server_time=utcnow(),
    )
