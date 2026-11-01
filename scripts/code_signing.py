"""Penandatanganan Authenticode untuk installer Kasirin.

Dipakai oleh scripts/build_installer.py (klien) dan
scripts/build_server_installer.py (server).

Prinsip:

1. **Opsional, tapi berisik.** Tanpa sertifikat, build tetap jalan dan
   mencetak peringatan jelas bahwa hasilnya belum ditandatangani. Build
   tidak boleh gagal hanya karena sertifikat belum dibeli.
2. **Kalau dikonfigurasi lalu gagal, build GAGAL.** Jangan pernah diam-diam
   mengirim build tanpa tanda tangan padahal admin mengira sudah ditandatangani.
3. **Selalu pakai timestamp.** Tanpa timestamp, tanda tangan ikut kedaluwarsa
   saat sertifikat habis masa berlaku, dan installer lama akan mulai
   diperingatkan Windows lagi.

Konfigurasi lewat environment variable (jangan pernah ditulis ke repo):

  Dua cara memilih sertifikat, pilih salah satu:

  A. File PFX
     KASIRIN_SIGN_PFX        = C:\\sertifikat\\kasirin.pfx
     KASIRIN_SIGN_PFX_PASS   = <password>

  B. Sertifikat di Windows Certificate Store (lebih aman, tidak ada file)
     KASIRIN_SIGN_THUMBPRINT = <40 karakter SHA1 thumbprint>

  Opsional:
     KASIRIN_SIGN_TIMESTAMP  = http://timestamp.digicert.com  (default)
     SIGNTOOL                = path ke signtool.exe bila tidak terdeteksi

  KASIRIN_SIGN_REQUIRED=1 membuat build gagal bila sertifikat tidak ada.
  Pakai ini di mesin rilis supaya tidak pernah lupa menandatangani.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

DEFAULT_TIMESTAMP_URL = "http://timestamp.digicert.com"


class SigningError(RuntimeError):
    """Penandatanganan dikonfigurasi tetapi gagal."""


def find_signtool() -> Path | None:
    """Cari signtool.exe: env var, PATH, lalu Windows Kits terbaru."""
    configured = os.environ.get("SIGNTOOL")
    if configured:
        candidate = Path(configured)
        if candidate.is_file():
            return candidate
        raise SigningError(f"SIGNTOOL menunjuk ke file yang tidak ada: {candidate}")

    on_path = shutil.which("signtool.exe")
    if on_path:
        return Path(on_path)

    kits_root = Path(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    ) / "Windows Kits" / "10" / "bin"
    if kits_root.is_dir():
        # Versi SDK diurutkan menurun supaya yang terbaru dipakai lebih dulu.
        versions = sorted(
            (p for p in kits_root.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )
        for version_dir in versions:
            # Prefer arsitektur x64; signtool x86 juga bisa menandatangani
            # binary x64, jadi dipakai sebagai cadangan.
            for arch in ("x64", "x86"):
                candidate = version_dir / arch / "signtool.exe"
                if candidate.is_file():
                    return candidate
    return None


def _certificate_args() -> list[str] | None:
    """Argumen pemilih sertifikat, atau None bila tidak dikonfigurasi."""
    thumbprint = (os.environ.get("KASIRIN_SIGN_THUMBPRINT") or "").strip()
    if thumbprint:
        return ["/sha1", thumbprint]

    pfx = (os.environ.get("KASIRIN_SIGN_PFX") or "").strip()
    if pfx:
        pfx_path = Path(pfx).expanduser()
        if not pfx_path.is_file():
            raise SigningError(f"File sertifikat tidak ditemukan: {pfx_path}")
        password = os.environ.get("KASIRIN_SIGN_PFX_PASS", "")
        return ["/f", str(pfx_path), "/p", password]

    return None


def is_configured() -> bool:
    """True bila ada sertifikat yang dikonfigurasi lewat environment."""
    return bool(
        (os.environ.get("KASIRIN_SIGN_THUMBPRINT") or "").strip()
        or (os.environ.get("KASIRIN_SIGN_PFX") or "").strip()
    )


def sign_file(path: Path) -> bool:
    """Tandatangani satu file.

    Return True bila ditandatangani, False bila tidak dikonfigurasi.
    Raise SigningError bila dikonfigurasi tetapi gagal.
    """
    cert_args = _certificate_args()
    if cert_args is None:
        if os.environ.get("KASIRIN_SIGN_REQUIRED") == "1":
            raise SigningError(
                "KASIRIN_SIGN_REQUIRED=1 tetapi tidak ada sertifikat yang "
                "dikonfigurasi. Set KASIRIN_SIGN_PFX + KASIRIN_SIGN_PFX_PASS "
                "atau KASIRIN_SIGN_THUMBPRINT."
            )
        return False

    target = Path(path)
    if not target.is_file():
        raise SigningError(f"File yang akan ditandatangani tidak ada: {target}")

    _sign_with(signtool=_require_signtool(), cert_args=cert_args, target=target)
    return True


def _require_signtool() -> Path:
    signtool = find_signtool()
    if signtool is None:
        raise SigningError(
            "signtool.exe tidak ditemukan. Pasang Windows SDK (Signing Tools) "
            "atau set environment variable SIGNTOOL ke lokasi signtool.exe."
        )
    return signtool


def _sign_with(signtool: Path, cert_args: list[str], target: Path) -> None:
    timestamp_url = (
        os.environ.get("KASIRIN_SIGN_TIMESTAMP") or DEFAULT_TIMESTAMP_URL
    ).strip()

    command = [
        str(signtool),
        "sign",
        "/fd",
        "SHA256",
        "/td",
        "SHA256",
        "/tr",
        timestamp_url,
        *cert_args,
        str(target),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, errors="replace"
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise SigningError(
            f"signtool gagal menandatangani {target.name} "
            f"(exit {result.returncode}):\n{detail}"
        )
    print(f"      Ditandatangani: {target.name}")


def sign_or_warn(paths: list[Path]) -> None:
    """Tandatangani semua path, atau cetak peringatan yang tidak bisa dilewati.

    Konfigurasi divalidasi lebih dulu, sebelum menyentuh file apa pun. Kalau
    admin sudah mengonfigurasi sertifikat, build harus GAGAL saat ada masalah
    (signtool hilang, .pfx salah) daripada diam-diam menghasilkan build tanpa
    tanda tangan.
    """
    if not is_configured():
        if os.environ.get("KASIRIN_SIGN_REQUIRED") == "1":
            raise SigningError(
                "KASIRIN_SIGN_REQUIRED=1 tetapi tidak ada sertifikat yang "
                "dikonfigurasi. Set KASIRIN_SIGN_PFX + KASIRIN_SIGN_PFX_PASS "
                "atau KASIRIN_SIGN_THUMBPRINT."
            )
        print()
        print("  " + "!" * 58)
        print("  PERINGATAN: build ini BELUM DITANDATANGANI (unsigned).")
        print("  Windows SmartScreen akan memblokir installer di komputer")
        print("  pengguna sampai mereka menekan 'More info > Run anyway'.")
        print()
        print("  Untuk menandatangani, set salah satu:")
        print("    KASIRIN_SIGN_PFX + KASIRIN_SIGN_PFX_PASS   (file .pfx)")
        print("    KASIRIN_SIGN_THUMBPRINT                    (cert store)")
        print("  Lalu jalankan ulang build.")
        print("  " + "!" * 58)
        print()
        return

    # Validasi lengkap dulu: sertifikat terbaca dan signtool tersedia.
    cert_args = _certificate_args()
    if cert_args is None:  # pragma: no cover - dijaga is_configured()
        raise SigningError("Sertifikat tidak terbaca dari environment.")
    signtool = _require_signtool()

    for path in paths:
        target = Path(path)
        if not target.is_file():
            raise SigningError(
                f"File yang akan ditandatangani tidak ada: {target}"
            )
        _sign_with(signtool=signtool, cert_args=cert_args, target=target)


def verify(path: Path) -> tuple[bool, str]:
    """Cek status tanda tangan. Return (signed, keterangan)."""
    try:
        from cryptography import x509  # noqa: F401  (pastikan tersedia)
    except ImportError:
        pass

    target = Path(path)
    if not target.is_file():
        return False, "file tidak ditemukan"

    signtool = find_signtool()
    if signtool is None:
        return False, "signtool tidak tersedia untuk verifikasi"

    result = subprocess.run(
        [str(signtool), "verify", "/pa", "/q", str(target)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode == 0:
        return True, "tanda tangan valid"
    detail = (result.stderr or result.stdout or "").strip().splitlines()
    return False, detail[0] if detail else "tanda tangan tidak valid"


__all__ = [
    "DEFAULT_TIMESTAMP_URL",
    "SigningError",
    "find_signtool",
    "is_configured",
    "sign_file",
    "sign_or_warn",
    "verify",
]
