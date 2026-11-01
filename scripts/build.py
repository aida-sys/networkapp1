import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# scripts/ bukan package saat dijalankan langsung, jadi tambahkan ke sys.path.
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.code_signing import sign_or_warn  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the POS application.")
    parser.add_argument(
        "--debug-console",
        action="store_true",
        help="Build with a console window for application debug logs.",
    )
    options = parser.parse_args()

    migrations = PROJECT_ROOT / "migrations"
    alembic_config = PROJECT_ROOT / "alembic.ini"
    if not migrations.is_dir() or not alembic_config.is_file():
        raise FileNotFoundError("File migrasi database tidak ditemukan.")
    public_key = PROJECT_ROOT / "app" / "core" / "license_public_key.pem"
    if not public_key.is_file():
        raise SystemExit(
            "Kunci publik lisensi belum dibuat. Jalankan perintah berikut "
            "dengan passphrase minimal 12 karakter:\n"
            "  .\\venv\\Scripts\\python.exe "
            "scripts\\build_license_publisher.py --generate-key"
        )

    arguments = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--console" if options.debug_console else "--windowed",
        "--onedir",
        "--exclude-module",
        "anyio",
        "--hidden-import",
        "logging.config",
        "--name",
        "POS",
        "--distpath",
        str(PROJECT_ROOT / "dist"),
        "--workpath",
        str(PROJECT_ROOT / "build" / "pyinstaller"),
        "--specpath",
        str(PROJECT_ROOT / "build"),
        "--add-data",
        f"{alembic_config};.",
        "--add-data",
        f"{migrations};migrations",
        "--add-data",
        f"{public_key};app\\core",
        str(PROJECT_ROOT / "main.py"),
    ]
    rotated_public_key = (
        PROJECT_ROOT / "app" / "core" / "license_public_key_v2.pem"
    )
    if rotated_public_key.is_file():
        script_argument = str(PROJECT_ROOT / "main.py")
        script_index = arguments.index(script_argument)
        arguments[script_index:script_index] = [
            "--add-data",
            f"{rotated_public_key};app\\core",
        ]
    subprocess.run(arguments, cwd=PROJECT_ROOT, check=True)
    executable = PROJECT_ROOT / "dist" / "POS" / "POS.exe"
    print(f"Build selesai: {executable}")

    # POS.exe ikut ditandatangani supaya file yang dijalankan pengguna juga
    # tepercaya, bukan hanya installernya.
    sign_or_warn([executable])

    print("Database runtime dibuat terpisah di %LOCALAPPDATA%\\POSApp\\data.")


if __name__ == "__main__":
    main()
