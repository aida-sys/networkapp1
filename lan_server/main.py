"""POS LAN API.

Server transaksi POS untuk jaringan lokal toko. Terpisah total dari
`server/` (billing/lisensi): modul ini tidak mengimpor apa pun dari billing
dan tidak pernah menyentuh `billing.db`.

Jalankan dengan SATU worker:

    uvicorn lan_server.main:app --host 0.0.0.0 --port 8002 --workers 1

SQLite tidak boleh ditulis dari beberapa proses sekaligus. Menambah worker
akan menyebabkan error "database is locked" pada saat ramai.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from lan_server.config import settings
from lan_server.idempotency import ApiIdempotency  # noqa: F401  (registrasi tabel)
from lan_server.routers import auth, catalog, health, purchases, reports, sales, shifts

logger = logging.getLogger("pos.lan")

API_PREFIX = "/api/v1"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "API transaksi POS untuk jaringan lokal. "
            "Billing/lisensi ada di server terpisah dan tidak tercampur di sini."
        ),
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    origins = settings.allowed_origins
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["Idempotency-Key"],
        )

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(catalog.router, prefix=API_PREFIX)
    app.include_router(shifts.router, prefix=API_PREFIX)
    app.include_router(sales.router, prefix=API_PREFIX)
    app.include_router(purchases.router, prefix=API_PREFIX)
    app.include_router(reports.reports_router, prefix=API_PREFIX)
    app.include_router(reports.settings_router, prefix=API_PREFIX)

    web_dir = settings.resolved_web_build_dir
    if web_dir is not None:
        # Flutter web disajikan dari server yang sama supaya URL API dan CORS
        # sederhana: klien memanggil origin yang sama.
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error pada %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Terjadi kesalahan internal pada server POS LAN.",
                "path": request.url.path,
            },
        )

    return app


app = create_app()
