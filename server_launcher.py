"""Launcher server POS LAN untuk build installer (KasirinServer.exe).

Tujuan: satu exe yang bisa dijalankan pemilik toko tanpa Python, venv, atau
repo. Launcher ini:

1. Menyiapkan skema database pusat + data dasar (idempoten, aman diulang).
2. Menjalankan uvicorn dengan --workers 1 (wajib untuk SQLite).
3. Menampilkan alamat LAN yang harus diisi di perangkat kasir.
4. Menyediakan menu sederhana: buka browser, backup, buka folder data, keluar.

Sengaja TIDAK memakai GUI: server berjalan di PC toko dan cukup jendela konsol
yang bisa ditinggal. Ini juga membuat log mudah dibaca saat ada masalah.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _lan_ip_addresses() -> list[str]:
    """Alamat IPv4 non-loopback yang bisa dipakai perangkat lain."""
    addresses: list[str] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = info[4][0]
            if address.startswith("127.") or address.startswith("169.254."):
                continue
            if address not in addresses:
                addresses.append(address)
    except OSError:
        pass
    return addresses


def _port_is_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def _prepare_database() -> bool:
    """Buat skema + data dasar. Return False bila gagal."""
    from lan_server import idempotency  # noqa: F401  (registrasi tabel server)
    from lan_server.bootstrap import bootstrap
    from lan_server.config import settings
    from lan_server.database import LanBase, SessionLocal, engine
    from app.core.database import Base
    import app.models.entities  # noqa: F401  (registrasi tabel POS)

    print(f"Database pusat : {settings.resolved_database_path}")
    Base.metadata.create_all(bind=engine)
    LanBase.metadata.create_all(bind=engine)

    with SessionLocal() as session:
        report = bootstrap(session)
    print(f"Data dasar     : {report.describe()}")
    return True


def _print_banner(port: int) -> None:
    addresses = _lan_ip_addresses()
    line = "=" * 62
    print()
    print(line)
    print("            SERVER POS KASIRIN - SIAP DIPAKAI")
    print(line)
    print(f"  Di komputer ini   : http://127.0.0.1:{port}")
    if addresses:
        for address in addresses:
            print(f"  Jaringan LAN      : http://{address}:{port}")
        print()
        print("  Isi alamat Jaringan LAN di atas pada layar")
        print("  'Koneksi Server LAN' di aplikasi kasir, lalu Uji Koneksi.")
    else:
        print("  [!] Tidak ada alamat LAN terdeteksi. Pastikan PC ini")
        print("      terhubung ke jaringan toko (Wi-Fi/kabel).")
    print()
    print("  JANGAN tutup jendela ini. Menutup jendela = kasir berhenti.")
    print(line)
    print()


def _open_browser(port: int) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/docs")


def _run_backup() -> None:
    try:
        from lan_server.backup_restore import database_path, make_backup

        target = make_backup(database_path())
        print(f"[backup] Selesai: {target}")
    except Exception as exc:  # noqa: BLE001  (menu interaktif)
        print(f"[backup] Gagal: {exc}")


def _open_data_folder() -> None:
    from lan_server.config import settings

    folder = settings.data_dir
    try:
        os.startfile(str(folder))  # type: ignore[attr-defined]
    except OSError as exc:
        print(f"[folder] Tidak bisa membuka {folder}: {exc}")


def _menu_loop(port: int, stop_event: threading.Event) -> None:
    """Menu sederhana di thread terpisah supaya server tetap jalan."""
    options = {
        "1": ("Buka dokumentasi API di browser", lambda: _open_browser(port)),
        "2": ("Backup database sekarang", _run_backup),
        "3": ("Buka folder data", _open_data_folder),
        "4": ("Hentikan server", stop_event.set),
    }
    while not stop_event.is_set():
        print()
        for key, (label, _) in options.items():
            print(f"  [{key}] {label}")
        try:
            choice = input("  Pilih menu (Enter untuk diamkan): ").strip()
        except (EOFError, KeyboardInterrupt):
            # stdin tertutup (mis. dijalankan sebagai service atau lewat
            # redirect). Jangan hentikan server hanya karena tidak ada input:
            # pemilik toko tidak akan tahu kenapa kasir mati.
            print("\n  Tidak ada input konsol; server tetap berjalan.")
            _idle_until_stopped(stop_event)
            return
        if not choice:
            continue
        entry = options.get(choice)
        if entry is None:
            print("  Pilihan tidak dikenal.")
            continue
        entry[1]()


def _idle_until_stopped(stop_event: threading.Event) -> None:
    """Tanpa konsol interaktif (mis. dijalankan sebagai service).

    Jangan memanggil input(): stdin yang tertutup langsung menghasilkan EOF dan
    server akan berhenti sendiri. Cukup tunggu sampai proses dihentikan.
    """
    print("  Mode tanpa konsol: server berjalan sampai proses dihentikan.")
    try:
        while not stop_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        stop_event.set()


def main() -> int:
    from lan_server.config import settings

    # Shortcut Start Menu "Buka Folder Data Server" memanggil exe dengan flag
    # ini. Tanpa penanganan di sini, shortcut itu malah menyalakan server
    # kedua dan gagal karena port sudah dipakai.
    if "--open-data" in sys.argv[1:]:
        _open_data_folder()
        return 0

    port = settings.port
    host = settings.host

    print("=" * 62)
    print("            SERVER POS KASIRIN")
    print("=" * 62)

    if _port_is_open("127.0.0.1", port):
        print(f"[X] Port {port} sudah dipakai proses lain.")
        print("    Tutup aplikasi lain itu, atau ubah LAN_PORT.")
        input("Tekan Enter untuk keluar...")
        return 1

    try:
        _prepare_database()
    except Exception as exc:  # noqa: BLE001  (pesan ramah untuk pemilik toko)
        print(f"[X] Database tidak dapat disiapkan: {exc}")
        input("Tekan Enter untuk keluar...")
        return 1

    import uvicorn

    from lan_server.main import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        workers=1,
        log_level="info",
        access_log=True,
    )
    server = uvicorn.Server(config)

    stop_event = threading.Event()
    thread = threading.Thread(
        target=server.run, name="uvicorn", daemon=True
    )
    thread.start()

    # Tunggu server benar-benar menerima koneksi sebelum memberi alamat.
    for _ in range(60):
        if _port_is_open("127.0.0.1", port):
            break
        if not thread.is_alive():
            print("[X] Server berhenti saat start. Periksa pesan di atas.")
            input("Tekan Enter untuk keluar...")
            return 1
        time.sleep(0.5)
    else:
        print(f"[X] Server tidak merespons di port {port}.")
        input("Tekan Enter untuk keluar...")
        return 1

    _print_banner(port)
    if sys.stdin is not None and sys.stdin.isatty():
        _menu_loop(port, stop_event)
    else:
        _idle_until_stopped(stop_event)

    print("\nMenghentikan server...")
    server.should_exit = True
    thread.join(timeout=15)
    print("Server berhenti. Data tetap tersimpan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
