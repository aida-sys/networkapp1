"""Pemilihan sumber data: lokal (standalone) atau POS LAN API.

Satu-satunya tempat di aplikasi desktop yang memutuskan jalur mana yang
dipakai. View meminta service lewat factory ini, bukan membuat sendiri.

Aturan yang dijaga di sini:
- Default tetap standalone; perilaku lama tidak berubah.
- Mode LAN tidak membuka engine database lokal sama sekali.
- Tidak ada dual-write dan tidak ada fallback diam-diam.
"""

from __future__ import annotations

import logging

from app.core.config import settings
from app.lan.config import LanConfig, LanConfigError, MODE_LAN, load_config
from app.lan.client import LanClient

logger = logging.getLogger("pos.lan")


class ServiceFactory:
    """Bangun service sesuai mode yang dikonfigurasi."""

    def __init__(self, config: LanConfig | None = None, *, session=None):
        self.config = config or load_config()
        self._session = session
        self._client: LanClient | None = None

    # --- Status -------------------------------------------------------

    @property
    def is_lan(self) -> bool:
        return self.config.is_lan

    @property
    def is_standalone(self) -> bool:
        return self.config.is_standalone

    def describe(self) -> str:
        if self.is_lan:
            return f"Mode LAN — server {self.config.api_url}"
        return "Mode standalone — database lokal"

    # --- Klien LAN ----------------------------------------------------

    @property
    def client(self) -> LanClient:
        if self._client is None:
            if not self.is_lan:
                raise LanConfigError(
                    "Klien LAN diminta padahal aplikasi berjalan di mode standalone."
                )
            self._client = LanClient(self.config)
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    # --- Service ------------------------------------------------------

    def sales(self):
        if self.is_lan:
            from app.lan.services import LanSalesService

            return LanSalesService(self.client)
        from app.services.sales_service import SalesService

        return SalesService(self.session)

    def master_data(self):
        if self.is_lan:
            from app.lan.services import LanMasterDataService

            return LanMasterDataService(self.client)
        from app.services.master_data_service import MasterDataService

        return MasterDataService(self.session)

    def shifts(self):
        if self.is_lan:
            from app.lan.services import LanShiftService

            return LanShiftService(self.client)
        from app.repositories.shift_repository import ShiftRepository
        from app.services.shift_service import ShiftService

        return ShiftService(self.session, ShiftRepository(self.session))

    def store_settings(self):
        if self.is_lan:
            from app.lan.services import LanStoreSettingsService

            return LanStoreSettingsService(self.client)
        from app.services.store_settings_service import StoreSettingsService

        return StoreSettingsService(self.session)

    def reports(self):
        if self.is_lan:
            from app.lan.services import LanReportService

            return LanReportService(self.client)
        from app.services.report_service import ReportService

        return ReportService(self.session)

    def pricing(self):
        if self.is_lan:
            from app.lan.services import LanPricingService

            return LanPricingService(self.client)
        from app.services.bulk_pricing_service import BulkPricingService

        return BulkPricingService(self.session)

    def product_repository(self):
        if self.is_lan:
            from app.lan.services import LanProductRepository

            return LanProductRepository(self.client)
        from app.repositories.product_repository import ProductRepository

        return ProductRepository(self.session)

    def daily_reports(self):
        if self.is_lan:
            from app.lan.services import LanDailyReportService

            return LanDailyReportService(self.client)
        from app.services.cashier_daily_report_service import CashierDailyReportService

        return CashierDailyReportService(self.session)

    def auth(self):
        if self.is_lan:
            from app.lan.auth import LanAuthService

            return LanAuthService(self.client)
        from app.repositories.user_repository import UserRepository
        from app.services.auth_service import AuthService

        return AuthService(UserRepository(self.session))

    # --- Session ------------------------------------------------------

    @property
    def session(self):
        if self.is_lan:
            raise LanConfigError(
                "Mode LAN tidak memiliki Session database lokal. "
                "Gunakan service LAN, bukan akses database langsung."
            )
        if self._session is None:
            from app.core.database import get_session

            self._session = get_session()
        return self._session


def build_factory(*, session=None) -> ServiceFactory:
    """Factory untuk aplikasi berjalan. Gagal keras bila konfigurasi LAN salah."""
    config = load_config()
    logger.info("Mode aplikasi: %s", config.mode)
    return ServiceFactory(config, session=session)


__all__ = ["ServiceFactory", "build_factory"]
