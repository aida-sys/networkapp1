"""Test katalog aplikasi billing.

Fokus pada hal yang mudah rusak saat menambah aplikasi baru: id duplikat,
status tidak dikenal, dan tombol unduh yang muncul untuk aplikasi yang
belum dirilis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.app import app_catalog
from server.app.main import create_app

VALID_STATUSES = {"available", "beta", "coming_soon"}


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_app_ids_are_unique():
    ids = [app["id"] for app in app_catalog.APPS]
    assert len(ids) == len(set(ids)), f"id aplikasi duplikat: {ids}"


def test_every_app_has_required_fields():
    required = {
        "id",
        "name",
        "kicker",
        "tagline",
        "description",
        "status",
        "icon",
        "architecture",
        "platforms",
        "features",
        "best_for",
        "requirements",
    }
    for app in app_catalog.APPS:
        missing = required - app.keys()
        assert not missing, f"{app.get('id')} kurang field: {missing}"


def test_every_status_is_known():
    for app in app_catalog.APPS:
        assert app["status"] in VALID_STATUSES, (
            f"{app['id']} memakai status tidak dikenal: {app['status']}"
        )


def test_status_labels_and_badges_exist_for_all_statuses():
    for status in VALID_STATUSES:
        assert status in app_catalog.STATUS_LABELS
        assert status in app_catalog.STATUS_BADGES


def test_available_and_upcoming_partition_the_catalog():
    available = app_catalog.available_apps()
    upcoming = app_catalog.upcoming_apps()
    assert len(available) + len(upcoming) == len(app_catalog.APPS)
    assert not ({a["id"] for a in available} & {a["id"] for a in upcoming})


def test_app_by_id_returns_none_for_unknown():
    assert app_catalog.app_by_id("tidak-ada") is None


def test_app_by_id_decorates_status():
    app = app_catalog.app_by_id("lan")
    assert app is not None
    assert app["status_label"] == "Tersedia"
    assert app["status_badge"] == "active"
    assert app["is_available"] is True


def test_count_by_status_totals_match_catalog():
    counts = app_catalog.count_by_status()
    assert sum(counts.values()) == len(app_catalog.APPS)


def test_apps_page_renders_every_app(client):
    response = client.get("/apps")
    assert response.status_code == 200
    body = response.text
    for app in app_catalog.APPS:
        assert app["name"] in body, f"{app['name']} tidak tampil di /apps"


def test_apps_page_does_not_offer_download_for_upcoming(client):
    """Aplikasi yang belum rilis tidak boleh punya tombol unduh aktif."""
    body = client.get("/apps").text
    for app in app_catalog.upcoming_apps():
        marker = f'id="app-{app["id"]}"'
        assert marker in body
        # Potong kartu aplikasi ini saja, lalu pastikan tidak ada ajakan unduh.
        card = body.split(marker, 1)[1].split("</article>", 1)[0]
        assert "Unduh installer" not in card, (
            f"{app['name']} belum rilis tetapi menampilkan tombol unduh"
        )
        assert "Belum tersedia" in card


def test_homepage_shows_every_app(client):
    """Beranda memakai nama pendek ("Stand Alone"), nama lengkap ada di
    aria-label supaya pembaca layar tetap menyebut nama produk utuh."""
    body = client.get("/").text
    for app in app_catalog.APPS:
        assert f'aria-label="{app["name"]}"' in body, (
            f'{app["name"]} tidak ada di beranda'
        )


def test_homepage_links_to_apps_page(client):
    assert 'href="/apps"' in client.get("/").text


def test_download_page_still_works(client):
    response = client.get("/download")
    assert response.status_code == 200
    assert "Pilih sistem operasi" in response.text
