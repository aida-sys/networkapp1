"""Dukungan mode POS Local Network pada aplikasi desktop.

Modul ini hanya aktif bila `POS_MODE=lan`. Pada mode default (standalone),
aplikasi berjalan persis seperti sebelumnya dan tidak menyentuh jaringan.
"""

from app.lan.config import (
    LanConfig,
    LanConfigError,
    MODE_LAN,
    MODE_STANDALONE,
    load_config,
    save_config,
)

__all__ = [
    "LanConfig",
    "LanConfigError",
    "MODE_LAN",
    "MODE_STANDALONE",
    "load_config",
    "save_config",
]
