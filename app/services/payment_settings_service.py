from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError
from app.models import PaymentSettings, User


class PaymentSettingsService:
    def __init__(self, session: Session):
        self.session = session

    def get_settings(self) -> PaymentSettings:
        settings = self.session.scalar(
            select(PaymentSettings).order_by(PaymentSettings.id).limit(1)
        )
        if settings is None:
            settings = PaymentSettings(
                cash_enabled=True,
                qris_dana_enabled=False,
                qris_midtrans_enabled=False,
                transfer_enabled=False,
            )
            self.session.add(settings)
            self.session.commit()
            self.session.refresh(settings)
        return settings

    def wizard_status(self) -> dict[str, str]:
        """Status wizard per metode bayar, dipakai untuk menentukan metode aktif."""
        from app.models import PaymentWizardState

        return {
            row.method: row.status
            for row in self.session.scalars(select(PaymentWizardState))
        }

    def enabled_methods(self) -> list[str] | None:
        """Metode bayar yang aktif, atau None bila belum pernah dikonfigurasi.

        `None` berarti "belum ada pengaturan"; pemanggil (UI) yang menentukan
        daftar default, supaya daftar metode tidak diduplikasi di dua tempat.
        """
        settings = self.session.scalar(
            select(PaymentSettings).order_by(PaymentSettings.id).limit(1)
        )
        if settings is None:
            return None
        status = self.wizard_status()

        def ready(method: str) -> bool:
            return status.get(method) == "active"

        enabled: list[str] = []
        if settings.cash_enabled:
            enabled.append("CASH")
        if settings.qris_dana_enabled and ready("QRIS_DANA"):
            enabled.append("QRIS_DANA")
        if settings.qris_midtrans_enabled and ready("QRIS_MIDTRANS"):
            enabled.append("QRIS_MIDTRANS")
        if settings.transfer_enabled and ready("BANK"):
            enabled.append("BANK")
        return enabled or ["CASH"]


    def save(
        self,
        actor: User,
        *,
        cash_enabled: bool,
        qris_dana_enabled: bool,
        qris_midtrans_enabled: bool,
        transfer_enabled: bool,
    ) -> PaymentSettings:
        self._require_owner(actor)
        settings = self.get_settings()
        settings.cash_enabled = cash_enabled
        settings.qris_dana_enabled = qris_dana_enabled
        settings.qris_midtrans_enabled = qris_midtrans_enabled
        settings.transfer_enabled = transfer_enabled
        self.session.commit()
        self.session.refresh(settings)
        return settings

    @staticmethod
    def _require_owner(actor: User):
        if actor.role.name.upper() != "OWNER":
            raise AuthorizationError(
                "Hanya OWNER yang dapat mengubah pengaturan pembayaran."
            )
