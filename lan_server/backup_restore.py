"""Backup dan restore database pusat POS LAN.

Memakai API `.backup` bawaan SQLite, bukan menyalin file saat database hidup.
Menyalin file `pos.db` yang sedang dipakai bisa menghasilkan backup rusak
karena ada WAL yang belum di-checkpoint.

Pemakaian:

    # Backup ke lan_server/data/backups/ (nama berstempel waktu)
    python lan_server/backup_restore.py backup

    # Backup ke folder lain
    python lan_server/backup_restore.py backup --out D:\\backup-pos

    # Lihat daftar backup
    python lan_server/backup_restore.py list

    # Restore (otomatis membackup dulu yang sekarang)
    python lan_server/backup_restore.py restore --file lan_server/data/backups/pos_lan-20260101-120000.db

    # Verifikasi integritas database
    python lan_server/backup_restore.py verify
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def database_path() -> Path:
    from lan_server.config import settings

    return settings.resolved_database_path


def backup_dir() -> Path:
    from lan_server.config import settings

    path = settings.data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_backup(target: Path, out_dir: Path | None = None) -> Path:
    """Salin database secara konsisten memakai API backup SQLite."""
    if not target.is_file():
        raise FileNotFoundError(f"Database tidak ditemukan: {target}")

    folder = out_dir or backup_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destination_path = folder / f"{target.stem}-{stamp}.db"

    source = sqlite3.connect(str(target))
    destination = sqlite3.connect(str(destination_path))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return destination_path


def verify(path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"File tidak ditemukan: {path}"
    try:
        connection = sqlite3.connect(str(path))
    except sqlite3.Error as error:
        return False, f"Tidak bisa dibuka sebagai database: {error}"
    try:
        result = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
    except sqlite3.DatabaseError as error:
        return False, f"Bukan database SQLite yang valid: {error}"
    finally:
        connection.close()
    if result == "ok":
        return True, f"Integritas OK, {tables} tabel."
    return False, f"Integritas GAGAL: {result}"


def restore(backup_path: Path, target: Path) -> Path:
    """Pulihkan backup ke database aktif, setelah membackup yang sekarang."""
    if not backup_path.is_file():
        raise FileNotFoundError(f"File backup tidak ditemukan: {backup_path}")

    safety: Path | None = None
    if target.is_file():
        safety = make_backup(target)
        print(f"  Database saat ini dibackup dulu ke: {safety}")

    # Hapus file WAL/SHM lama supaya tidak bercampur dengan isi backup.
    for suffix in ("-wal", "-shm"):
        sidecar = target.with_name(target.name + suffix)
        if sidecar.exists():
            sidecar.unlink()

    source = sqlite3.connect(str(backup_path))
    destination = sqlite3.connect(str(target))
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return safety or backup_path


def list_backups(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(folder.glob("*.db"), key=lambda item: item.stat().st_mtime, reverse=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup/restore database POS LAN.")
    parser.add_argument("action", choices=["backup", "restore", "list", "verify"])
    parser.add_argument("--file", help="File backup untuk restore atau verify")
    parser.add_argument("--out", help="Folder tujuan backup")
    parser.add_argument("--db", help="Path database aktif (default dari konfigurasi LAN)")
    args = parser.parse_args(argv)

    target = Path(args.db).expanduser().resolve() if args.db else database_path()

    if args.action == "backup":
        print(f"Database: {target}")
        path = make_backup(target, Path(args.out).expanduser() if args.out else None)
        size = path.stat().st_size
        print(f"Backup dibuat: {path} ({size:,} byte)")
        ok, message = verify(path)
        print(f"Verifikasi   : {message}")
        return 0 if ok else 1

    if args.action == "list":
        folder = Path(args.out).expanduser() if args.out else backup_dir()
        items = list_backups(folder)
        if not items:
            print(f"Belum ada backup di {folder}")
            return 0
        print(f"Backup di {folder}:")
        for item in items:
            stamp = datetime.fromtimestamp(item.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            print(f"  {item.name:<40} {item.stat().st_size:>12,} byte  {stamp}")
        return 0

    if args.action == "verify":
        path = Path(args.file).expanduser() if args.file else target
        ok, message = verify(path)
        print(f"{path}: {message}")
        return 0 if ok else 1

    # restore
    if not args.file:
        print("[X] Restore butuh --file")
        return 2
    backup_path = Path(args.file).expanduser().resolve()
    print(f"Restore {backup_path} -> {target}")
    restore(backup_path, target)
    ok, message = verify(target)
    print(f"Verifikasi: {message}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
