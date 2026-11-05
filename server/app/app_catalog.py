"""Katalog aplikasi yang dijual lewat halaman billing.

Sumber kebenaran tunggal untuk "aplikasi apa saja yang ada". Halaman
``/apps`` dan bagian "Aplikasi" di beranda membaca dari sini, jadi
menambah aplikasi baru cukup menambah satu entri di ``APPS`` — tidak
perlu menyentuh template.

Kenapa dipisah dari ``INSTALLER_PLATFORMS`` di ``main.py``:
``INSTALLER_PLATFORMS`` menjawab "installer untuk OS apa yang tersedia",
sedangkan modul ini menjawab "produk apa yang saya jual". Dua pertanyaan
berbeda. Satu aplikasi bisa jalan di beberapa OS, dan satu OS bisa
memiliki beberapa aplikasi (mis. Windows punya klien kasir DAN server LAN).

Status yang dipakai:

  ``available``    sudah bisa dipakai pelanggan, installer tersedia
  ``beta``         bisa dipakai, masih dalam pengawasan
  ``coming_soon``  belum dirilis; kartu tampil tapi tanpa tombol unduh

Field ``installer_platform`` menghubungkan entri ke katalog installer di
``main.py``. Bila ``None``, aplikasi belum punya installer dan tombol
unduh tidak dirender.
"""

from __future__ import annotations

from typing import Any

STATUS_LABELS = {
    "available": "Tersedia",
    "beta": "Beta",
    "coming_soon": "Segera hadir",
}

STATUS_BADGES = {
    "available": "active",
    "beta": "pending",
    "coming_soon": "none",
}

# Ikon memakai glyph teks agar tidak perlu aset gambar baru dan tetap
# konsisten dengan kartu arsitektur di beranda.
APPS: list[dict[str, Any]] = [
    {
        "id": "standalone",
        "name": "Kasirin Stand Alone",
        "kicker": "SATU PERANGKAT",
        "tagline": "Kasir lengkap dalam satu komputer, tanpa jaringan.",
        "description": (
            "Aplikasi kasir desktop yang berjalan mandiri di satu perangkat. "
            "Seluruh data transaksi, stok, dan laporan tersimpan lokal, "
            "sehingga tetap dapat dipakai saat internet padam."
        ),
        "status": "available",
        "icon": "\u25a3",
        "icon_class": "standalone-icon",
        "highlight": False,
        "architecture": "Stand Alone",
        "platforms": ["Windows 10 / 11"],
        "installer_platform": "windows",
        "features": [
            "Transaksi kasir dengan barcode dan cetak struk",
            "Manajemen stok dan produk",
            "Pembelian, pengeluaran, dan laporan harian",
            "Pembayaran tunai, QRIS, kartu, dan tempo",
        ],
        "best_for": "Toko tunggal dan UMKM",
        "requirements": "Windows 10 atau lebih baru, RAM 4 GB",
        "hero": {
            "eyebrow": "APLIKASI KASIR STAND ALONE",
            "headline": "Satu kasir, satu komputer, tanpa jaringan",
            "lead": (
                "Aplikasi kasir yang berjalan mandiri di satu perangkat. "
                "Seluruh data transaksi, stok, dan laporan tersimpan di "
                "komputer itu sendiri, sehingga toko tetap bisa melayani "
                "pembeli saat internet padam."
            ),
            "points": [
                "Untuk satu meja kasir",
                "Tidak butuh internet maupun server",
                "Pasang sekali, langsung dipakai",
            ],
            "image": "kasirin-kasir.png",
            "visual": "single",
        },
    },
    {
        "id": "lan",
        "name": "Kasirin Jaringan Lokal",
        "kicker": "BEBERAPA PERANGKAT",
        "tagline": "Satu server toko, banyak kasir dalam satu jaringan.",
        "description": (
            "Server lokal menyimpan satu database toko, lalu beberapa "
            "perangkat kasir terhubung lewat jaringan WiFi atau kabel. "
            "Cocok untuk toko dengan lebih dari satu meja kasir atau "
            "pemisahan bagian gudang."
        ),
        "status": "available",
        "icon": "\u2318",
        "icon_class": "lan-icon",
        "highlight": True,
        "highlight_label": "PALING BANYAK DIPAKAI",
        "architecture": "Jaringan Lokal",
        "platforms": ["Windows (server)", "Windows (kasir)", "Android (kasir)"],
        "installer_platform": "windows",
        "features": [
            "Satu database toko untuk semua kasir",
            "Server berjalan sebagai aplikasi Windows",
            "Klien kasir Windows dan Android",
            "Backup database dari menu server",
        ],
        "best_for": "Minimarket dan toko besar",
        "requirements": "Satu PC sebagai server, jaringan lokal stabil",
        "hero": {
            "eyebrow": "APLIKASI KASIR NETWORKING",
            "headline": "Beberapa kasir, satu database toko",
            "lead": (
                "Satu komputer bertindak sebagai server toko, lalu beberapa "
                "perangkat kasir terhubung lewat jaringan lokal WiFi atau "
                "kabel. Semua kasir melihat stok dan harga yang sama, dan "
                "pemilik bisa memantau seluruh transaksi dari satu tempat."
            ),
            "points": [
                "Untuk beberapa meja kasir sekaligus",
                "Stok dan harga selalu sama di semua kasir",
                "Berjalan di jaringan lokal, tanpa biaya bulanan",
            ],
            "image": "kasirin-produk-stok.png",
            "visual": "network",
        },
    },
    {
        "id": "mobile",
        "name": "Kasirin Mobile",
        "kicker": "KASIR DI GENGGAMAN",
        "tagline": "Kasir Android untuk toko yang berpindah-pindah.",
        "description": (
            "Aplikasi kasir Android yang memakai data toko yang sama dengan "
            "versi desktop. Dirancang untuk lapak, bazar, dan toko dengan "
            "meja kasir berpindah."
        ),
        "status": "coming_soon",
        "icon": "\u25a4",
        "icon_class": "violet-icon",
        "highlight": False,
        "architecture": "Mobile",
        "platforms": ["Android"],
        "installer_platform": None,
        "features": [
            "Kasir Android dengan data toko yang sama",
            "Mode luring saat jaringan padam",
            "Sinkronisasi otomatis saat kembali daring",
        ],
        "best_for": "Lapak, bazar, dan toko berpindah",
        "requirements": "Android 9 atau lebih baru",
    },
    {
        "id": "cloud",
        "name": "Kasirin Cloud",
        "kicker": "AKSES JARAK JAUH",
        "tagline": "Pantau semua cabang dari mana saja.",
        "description": (
            "Ringkasan penjualan, stok, dan aktivitas kasir dari beberapa "
            "cabang dikumpulkan ke satu dashboard. Pemilik dapat memantau "
            "usaha tanpa harus berada di lokasi."
        ),
        "status": "coming_soon",
        "icon": "\u2601",
        "icon_class": "cloud-icon",
        "highlight": False,
        "architecture": "Full Cloud",
        "platforms": ["Web", "Android", "iOS"],
        "installer_platform": None,
        "features": [
            "Ringkasan penjualan antar cabang",
            "Pantau stok dan aktivitas kasir",
            "Akses dari browser dan ponsel",
        ],
        "best_for": "Bisnis multi-cabang",
        "requirements": "Koneksi internet di setiap cabang",
        "hero": {
            "eyebrow": "APLIKASI FULL CLOUD",
            "headline": "Banyak kasir di setiap cabang, dipantau dari mana saja",
            "lead": (
                "Setiap cabang menjalankan kasirnya sendiri, dan seluruh "
                "ringkasan penjualan, stok, serta aktivitas kasir "
                "dikumpulkan ke satu dashboard. Pemilik dapat memeriksa "
                "semua cabang dari ponsel tanpa harus datang ke lokasi."
            ),
            "points": [
                "Banyak kasir di banyak cabang",
                "Pantau penjualan dan stok dari mana saja",
                "Ringkasan antar cabang dalam satu tampilan",
            ],
            "image": "kasirin-dashboard.png",
            "visual": "cloud",
        },
    },
]

APPS_BY_ID = {app["id"]: app for app in APPS}


def _decorate(app: dict[str, Any]) -> dict[str, Any]:
    """Tambahkan label status dan badge agar template tetap bersih."""
    return {
        **app,
        "status_label": STATUS_LABELS.get(app["status"], app["status"]),
        "status_badge": STATUS_BADGES.get(app["status"], "none"),
        "is_available": app["status"] in ("available", "beta"),
        "highlight": bool(app.get("highlight")),
        "highlight_label": app.get("highlight_label", ""),
    }


def all_apps() -> list[dict[str, Any]]:
    """Semua aplikasi, urut sesuai definisi (yang tersedia lebih dulu)."""
    return [_decorate(app) for app in APPS]


def available_apps() -> list[dict[str, Any]]:
    """Hanya aplikasi yang sudah bisa dipakai pelanggan."""
    return [app for app in all_apps() if app["is_available"]]


def upcoming_apps() -> list[dict[str, Any]]:
    """Aplikasi yang belum dirilis."""
    return [app for app in all_apps() if not app["is_available"]]


def hero_slides() -> list[dict[str, Any]]:
    """Aplikasi yang punya konten hero, untuk slider di beranda.

    Hanya aplikasi dengan field ``hero`` yang tampil. Urutannya mengikuti
    ``APPS``, jadi mengatur urutan slide cukup dengan mengatur urutan
    definisi aplikasi.
    """
    return [app for app in all_apps() if app.get("hero")]


def app_by_id(app_id: str) -> dict[str, Any] | None:
    app = APPS_BY_ID.get(app_id)
    return _decorate(app) if app else None


def count_by_status() -> dict[str, int]:
    counts = {status: 0 for status in STATUS_LABELS}
    for app in APPS:
        counts[app["status"]] = counts.get(app["status"], 0) + 1
    return counts


__all__ = [
    "APPS",
    "APPS_BY_ID",
    "STATUS_BADGES",
    "STATUS_LABELS",
    "all_apps",
    "app_by_id",
    "available_apps",
    "count_by_status",
    "hero_slides",
    "upcoming_apps",
]
