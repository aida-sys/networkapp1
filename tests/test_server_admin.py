from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from server.app.config import Settings
from server.app.main import create_app


@pytest.fixture
def admin_client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{tmp_path / 'billing.db'}",
        admin_email="admin@example.com",
        admin_password="adminrahasia123",
    )
    app = create_app(settings)
    with TestClient(app, follow_redirects=False) as test_client:
        yield test_client


def test_admin_seeded_on_startup(admin_client):
    response = admin_client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "adminrahasia123"},
    )
    assert response.status_code == 303, response.text
    assert response.headers["location"] == "/admin"


def test_admin_dashboard_requires_login(admin_client):
    response = admin_client.get("/admin")
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_home_download_page_lists_operating_systems(admin_client):
    home = admin_client.get("/")
    assert 'href="/download"' in home.text
    assert 'href="/download/installer"' not in home.text

    response = admin_client.get("/download")
    assert response.status_code == 200
    for operating_system in (
        "Windows",
        "macOS",
        "Linux",
        "Android",
        "iOS / iPadOS",
        "ChromeOS",
        "OS lainnya",
    ):
        assert operating_system in response.text
    assert 'data-os="windows"' in response.text


def test_floating_chatbot_is_available_on_shared_pages(admin_client):
    for path in ("/", "/download", "/login", "/admin/login"):
        response = admin_client.get(path)
        assert response.status_code == 200, path
        assert 'id="chatbotToggle"' in response.text, path
        assert 'id="chatbotWindow"' in response.text, path
        assert response.text.rfind("</style>") < response.text.index(
            'id="chatbotToggle"'
        ), path


def test_chatbot_redirects_to_configured_whatsapp_with_message(admin_client):
    message = "Halo Admin, saya butuh bantuan."
    response = admin_client.get(
        "/chat/whatsapp", params={"message": message}
    )

    assert response.status_code == 303
    target = urlsplit(response.headers["location"])
    assert target.scheme == "https"
    assert target.netloc == "wa.me"
    assert target.path == f"/{admin_client.app.state.settings.admin_whatsapp}"
    assert parse_qs(target.query)["text"] == [message]


def _login_admin(admin_client):
    response = admin_client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "adminrahasia123"},
    )
    assert response.status_code == 303, response.text


def test_admin_dashboard_lists_customers(admin_client):
    # customer biasa
    response = admin_client.post(
        "/api/auth/register",
        json={
            "email": "toko@example.com",
            "password": "rahasia123",
            "store_name": "Toko Contoh",
        },
    )
    assert response.status_code == 200, response.text

    # customer biasa tidak boleh masuk area admin
    response = admin_client.post(
        "/admin/login",
        data={"email": "toko@example.com", "password": "rahasia123"},
    )
    assert response.status_code == 403

    # login admin lalu buka dashboard
    response = admin_client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "adminrahasia123"},
    )
    assert response.status_code == 303
    cookie = response.headers.get("set-cookie", "")
    assert "billing_session" in cookie

    response = admin_client.get("/admin")
    assert response.status_code == 200, response.text
    assert "Dashboard Admin" in response.text
    assert "toko@example.com" in response.text
    assert "Belum berlangganan" in response.text


def test_admin_create_and_delete_admin(admin_client):
    _login_admin(admin_client)

    response = admin_client.post(
        "/admin/admins/create",
        data={"email": "baru@example.com", "password": "barurahasia123"},
    )
    assert response.status_code == 303, response.text

    response = admin_client.get("/admin")
    assert response.status_code == 200
    assert "baru@example.com" in response.text
    assert "Tambah Admin" in response.text

    # login dengan admin baru
    response = admin_client.post(
        "/admin/login",
        data={"email": "baru@example.com", "password": "barurahasia123"},
    )
    assert response.status_code == 303

    # email duplikat ditolak
    _login_admin(admin_client)
    response = admin_client.post(
        "/admin/admins/create",
        data={"email": "baru@example.com", "password": "barurahasia123"},
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]

    # hapus admin baru via id yang terlihat di dashboard
    import re

    page = admin_client.get("/admin").text
    match = re.search(r'/admin/admins/(\d+)/delete', page)
    assert match, "tombol hapus admin harus ada"
    # jangan hapus akun sendiri: hapus id selain admin utama
    for candidate in re.findall(r'/admin/admins/(\d+)/delete', page):
        response = admin_client.post(f"/admin/admins/{candidate}/delete")
        assert response.status_code == 303
        break
    assert "baru@example.com" not in admin_client.get("/admin").text


def test_admin_cannot_delete_self(admin_client):
    _login_admin(admin_client)
    page = admin_client.get("/admin").text
    # akun sendiri tidak punya tombol hapus (hanya penanda "Anda")
    assert "Anda" in page
    # id 1 adalah admin utama hasil seed (= akun yang sedang login),
    # penghapusan diri sendiri harus ditolak dan akun tetap ada
    response = admin_client.post("/admin/admins/1/delete")
    assert response.status_code == 303
    # admin utama tetap bisa login
    response = admin_client.post(
        "/admin/login",
        data={"email": "admin@example.com", "password": "adminrahasia123"},
    )
    assert response.status_code == 303


def test_admin_upload_and_download_installer(admin_client, tmp_path):
    _login_admin(admin_client)

    installer_path = tmp_path / "build" / "installer_v3" / "Kasirin.exe"
    admin_client.app.state.settings.installer_path = installer_path

    response = admin_client.post(
        "/admin/upload-installer",
        data={"platform": "windows"},
        files={"installer": ("Kasirin.exe", b"fake-exe-content", "application/octet-stream")},
    )
    assert response.status_code == 303, response.text
    assert "notice=" in response.headers["location"]
    uploaded_path = installer_path.parent / "platform-installers" / "windows.exe"
    assert uploaded_path.is_file()
    assert uploaded_path.read_bytes() == b"fake-exe-content"

    download = admin_client.get("/download/installer")
    assert download.status_code == 200, download.text
    assert download.content == b"fake-exe-content"
    # Nama unduhan dibranding "Kasirin" oleh installer_download_filename().
    assert download.headers["content-disposition"].endswith('Kasirin.exe"')

    platform_download = admin_client.get("/download/installer/windows")
    assert platform_download.status_code == 200
    assert platform_download.content == b"fake-exe-content"


def test_admin_upload_syncs_platform_availability(admin_client, tmp_path):
    _login_admin(admin_client)
    admin_client.app.state.settings.installer_path = (
        tmp_path / "build" / "installer_v3" / "Kasirin.exe"
    )

    upload = admin_client.post(
        "/admin/upload-installer",
        data={"platform": "android"},
        files={"installer": ("Kasirin.apk", b"fake-apk", "application/octet-stream")},
    )
    assert upload.status_code == 303

    dashboard = admin_client.get("/admin")
    assert "Android" in dashboard.text
    assert "android.apk" in dashboard.text

    download_page = admin_client.get("/download")
    assert 'data-os="android"' in download_page.text
    assert 'data-available="true"' in download_page.text.split('data-os="android"', 1)[1].split(">", 1)[0]

    download = admin_client.get("/download/installer/android")
    assert download.status_code == 200
    assert download.content == b"fake-apk"


def test_admin_create_and_delete_customer(admin_client):
    _login_admin(admin_client)

    response = admin_client.post(
        "/admin/customers/create",
        data={
            "email": "pelanggan@example.com",
            "password": "pelanggan123",
            "store_name": "Toko Pelanggan",
        },
    )
    assert response.status_code == 303, response.text
    assert "notice=" in response.headers["location"]

    page = admin_client.get("/admin").text
    assert "pelanggan@example.com" in page
    assert "Tambah Customer" in page

    import re

    match = re.search(r'/admin/customers/(\d+)/delete', page)
    assert match, "tombol hapus customer harus ada"
    response = admin_client.post(f"/admin/customers/{match.group(1)}/delete")
    assert response.status_code == 303
    assert "pelanggan@example.com" not in admin_client.get("/admin").text
