"""Autentikasi untuk mode LAN.

`LoginView` menerima objek dengan method `.login(username, password)` yang
mengembalikan objek user. Kelas ini memenuhi kontrak itu dengan memanggil
POS LAN API, sehingga layar login tidak perlu diubah.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.lan.client import LanClient


@dataclass
class LanUser:
    """User ringan hasil login LAN, cukup untuk routing role di UI."""

    id: int
    username: str
    full_name: str
    role_name: str
    is_active: bool = True
    must_change_password: bool = False

    @property
    def role(self) -> "LanRole":
        return LanRole(name=self.role_name)


@dataclass
class LanRole:
    name: str


class LanAuthService:
    """Padanan `AuthService` yang memakai server LAN sebagai sumber kebenaran."""

    def __init__(self, client: LanClient):
        self.client = client

    def login(self, username: str, password: str) -> LanUser:
        payload = self.client.login(username, password)
        user = payload.get("user") or {}
        return LanUser(
            id=int(user.get("id") or 0),
            username=user.get("username", username),
            full_name=user.get("full_name", username),
            role_name=user.get("role", ""),
            is_active=bool(user.get("is_active", True)),
            must_change_password=bool(user.get("must_change_password", False)),
        )

    def logout(self) -> None:
        self.client.logout()


__all__ = ["LanAuthService", "LanRole", "LanUser"]
