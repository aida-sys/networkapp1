"""Test backup dan restore database POS LAN.

Fokus: backup konsisten (bukan copy file), restore mengembalikan isi lama,
dan restore selalu membackup dulu database yang sedang aktif.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from lan_server import backup_restore


def _create_db(path: Path, marker: str) -> None:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, note TEXT)")
    connection.execute("INSERT INTO probe (note) VALUES (?)", (marker,))
    connection.commit()
    connection.close()


def _read_marker(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return connection.execute("SELECT note FROM probe").fetchone()[0]
    finally:
        connection.close()


def test_backup_menyalin_isi_database(tmp_path: Path) -> None:
    db = tmp_path / "pos_lan.db"
    _create_db(db, "isi-asli")

    backup = backup_restore.make_backup(db, tmp_path / "backups")

    assert backup.is_file()
    assert _read_marker(backup) == "isi-asli"
    ok, message = backup_restore.verify(backup)
    assert ok, message


def test_backup_database_tidak_ada_ditolak(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        backup_restore.make_backup(tmp_path / "tidak-ada.db", tmp_path)


def test_restore_mengembalikan_isi_lama(tmp_path: Path) -> None:
    db = tmp_path / "pos_lan.db"
    _create_db(db, "versi-lama")
    backup = backup_restore.make_backup(db, tmp_path / "backups")

    # Ubah isi database setelah backup.
    connection = sqlite3.connect(db)
    connection.execute("UPDATE probe SET note = 'versi-baru'")
    connection.commit()
    connection.close()
    assert _read_marker(db) == "versi-baru"

    backup_restore.restore(backup, db)

    assert _read_marker(db) == "versi-lama"


def test_restore_membuat_backup_pengaman_dulu(tmp_path: Path) -> None:
    db = tmp_path / "pos_lan.db"
    _create_db(db, "versi-lama")
    backup = backup_restore.make_backup(db, tmp_path / "backups")

    connection = sqlite3.connect(db)
    connection.execute("UPDATE probe SET note = 'versi-baru'")
    connection.commit()
    connection.close()

    backup_restore.restore(backup, db)

    # Backup pengaman berisi keadaan sebelum restore.
    safety_files = [
        item
        for item in backup_restore.list_backups(backup_restore.backup_dir())
        if _read_marker(item) == "versi-baru"
    ]
    assert safety_files, "restore harus membackup database aktif terlebih dahulu"


def test_verify_menemukan_file_rusak(tmp_path: Path) -> None:
    broken = tmp_path / "rusak.db"
    broken.write_bytes(b"ini bukan sqlite")

    ok, message = backup_restore.verify(broken)

    assert not ok
    assert "valid" in message.lower() or "gagal" in message.lower()


def test_cli_backup_dan_list(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "pos_lan.db"
    _create_db(db, "cli")
    out = tmp_path / "backups"

    assert backup_restore.main(["backup", "--db", str(db), "--out", str(out)]) == 0
    assert backup_restore.main(["list", "--out", str(out)]) == 0

    printed = capsys.readouterr().out
    assert "Backup dibuat" in printed
    assert "pos_lan-" in printed
