"""Build installer server POS LAN (KasirinServer.exe).

Menghasilkan satu installer yang bisa dipasang pemilik toko tanpa Python:
server FastAPI + uvicorn dibungkus jadi exe, dijalankan lewat server_launcher.py.

Berbeda dari build_installer.py (aplikasi kasir):

  build_installer.py  -> Kasirin.exe        (aplikasi kasir, klien)
  build_server_installer.py -> KasirinServer.exe (server LAN, satu per toko)

Jalankan:
    .\\venv\\Scripts\\python.exe scripts\\build_server_installer.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_VERSION = "0.5.0"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.code_signing import sign_or_warn  # noqa: E402


def find_inno_setup_compiler() -> Path:
    configured_path = os.environ.get("ISCC")
    if configured_path:
        compiler = Path(configured_path)
        if compiler.is_file():
            return compiler
        raise FileNotFoundError(f"ISCC yang ditentukan tidak ditemukan: {compiler}")

    path_compiler = shutil.which("ISCC.exe")
    if path_compiler:
        return Path(path_compiler)

    install_roots = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    ]
    for root in install_roots:
        for version in ("7", "6"):
            compiler = root / f"Inno Setup {version}" / "ISCC.exe"
            if compiler.is_file():
                return compiler

    raise FileNotFoundError(
        "Inno Setup tidak ditemukan. Instal Inno Setup 6/7 atau atur "
        "environment variable ISCC ke lokasi ISCC.exe."
    )


def build_executable() -> Path:
    """Bungkus server_launcher.py + lan_server + app jadi satu folder exe."""
    arguments = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        # Server harus punya konsol: menu, log, dan alamat LAN ditampilkan
        # di sana. Tanpa konsol pemilik toko tidak tahu harus mengisi apa.
        "--console",
        "--onedir",
        "--name",
        "KasirinServer",
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build" / "pyinstaller-server"),
        "--specpath",
        str(PROJECT_ROOT / "build"),
        # Router dimuat dinamis oleh FastAPI, jadi tidak terdeteksi otomatis.
        "--hidden-import",
        "lan_server.routers.auth",
        "--hidden-import",
        "lan_server.routers.catalog",
        "--hidden-import",
        "lan_server.routers.health",
        "--hidden-import",
        "lan_server.routers.purchases",
        "--hidden-import",
        "lan_server.routers.reports",
        "--hidden-import",
        "lan_server.routers.sales",
        "--hidden-import",
        "lan_server.routers.shifts",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.loops.asyncio",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.http.h11_impl",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "app.models.entities",
        # PySide6 tidak dipakai server; jangan ikut dibundel (hemat ~200 MB).
        "--exclude-module",
        "PySide6",
        "--exclude-module",
        "shiboken6",
        str(PROJECT_ROOT / "server_launcher.py"),
    ]
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)
    executable = PROJECT_ROOT / "dist" / "KasirinServer" / "KasirinServer.exe"
    if not executable.is_file():
        raise FileNotFoundError(f"Hasil build server tidak ditemukan: {executable}")
    return executable


def main() -> None:
    compiler = find_inno_setup_compiler()

    print("[1/2] Membangun executable server...")
    executable = build_executable()
    print(f"      Executable: {executable}")

    distribution = executable.parent
    installer_script = PROJECT_ROOT / "scripts" / "installer_server.iss"
    output_dir = PROJECT_ROOT / "build" / "installer_server"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[2/2] Membuat installer...")
    subprocess.run(
        [
            str(compiler),
            "/Qp",
            f"/DAppVersion={APP_VERSION}",
            f"/DSourceDir={distribution}",
            f"/DOutputDir={output_dir}",
            str(installer_script),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    installer = output_dir / "KasirinServer.exe"
    if not installer.is_file():
        raise FileNotFoundError(f"Hasil build installer tidak ditemukan: {installer}")

    # KasirinServer.exe dijalankan sebagai admin di PC toko, jadi SmartScreen
    # yang memblokirnya akan sangat mengganggu saat pemasangan.
    sign_or_warn([executable, installer])

    print(f"Installer selesai: {installer}")
    print("Database server disimpan di %LOCALAPPDATA%\\KasirinServer\\data.")


if __name__ == "__main__":
    main()
