from datetime import datetime
from html import escape
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.config import settings
from app.models import Store
from app.services.license_service import LicenseService
from app.services.online_activation import CheckoutWorker, RenewalPollingWorker
from app.services.subscription_info import (
    ROADMAP_PREVIEW_LIMIT,
    SubscriptionInfoWorker,
    cycle_label,
    local_subscription_info,
)
from app.utils.browser import open_external_url
from app.utils.formatters import rupiah


class _DashboardPalette:
    def __init__(
        self,
        name: str,
        background: str,
        surface: str,
        surface_raised: str,
        text: str,
        muted: str,
        accent: str,
        accent_text: str,
        border: str,
        gradient_end: str,
    ):
        self.name = name
        self.background = background
        self.surface = surface
        self.surface_raised = surface_raised
        self.text = text
        self.muted = muted
        self.accent = accent
        self.accent_text = accent_text
        self.border = border
        self.gradient_end = gradient_end


_DASHBOARD_PALETTES = (
    _DashboardPalette(
        "Dark Emerald",
        "#0b1326",
        "#171f33",
        "#222a3d",
        "#dae2fd",
        "#bacbbe",
        "#6dffba",
        "#003822",
        "#3b4a41",
        "#222a3d",
    ),
    _DashboardPalette(
        "Ocean Blue",
        "#091722",
        "#12283a",
        "#1c354a",
        "#e7f5ff",
        "#b3cddc",
        "#55c8ff",
        "#062235",
        "#31536a",
        "#1c354a",
    ),
    _DashboardPalette(
        "Light Slate",
        "#f2f5f9",
        "#ffffff",
        "#e7edf4",
        "#1d2939",
        "#526174",
        "#0877b9",
        "#ffffff",
        "#d3dce7",
        "#e7edf4",
    ),
    _DashboardPalette(
        "Warm Amber",
        "#21170f",
        "#302116",
        "#45301e",
        "#fff3e0",
        "#d8c2a5",
        "#ffc266",
        "#382100",
        "#674b30",
        "#45301e",
    ),
    _DashboardPalette(
        "Plum Night",
        "#1b1426",
        "#2a1e3a",
        "#3a2b4f",
        "#f4eafe",
        "#c9b8db",
        "#d6a5ff",
        "#301344",
        "#59446f",
        "#3a2b4f",
    ),
)


class DashboardView(QWidget):
    logout_requested = Signal()
    manage_users_requested = Signal()
    sales_report_requested = Signal()
    financial_report_requested = Signal()
    # Kartu "Laporan" gabungan: penjualan + keuangan + absensi karyawan.
    report_requested = Signal()
    master_data_requested = Signal()
    store_settings_requested = Signal()
    suppliers_requested = Signal()
    activation_requested = Signal()

    def __init__(
        self,
        user,
        parent=None,
        store: Store | None = None,
        *,
        licensed: bool = False,
        license_service: LicenseService | None = None,
    ):
        super().__init__(parent)
        role_name = user.role.name.upper()
        self.store = store
        self._licensed = bool(licensed)
        self._license_service = license_service
        self._subscription_worker: SubscriptionInfoWorker | None = None
        self._checkout_worker: CheckoutWorker | None = None
        self._renewal_worker: RenewalPollingWorker | None = None
        self.subscription_info: dict | None = None
        self._activation_card: QFrame | None = None
        self._subscription_card: QFrame | None = None
        self.subscription_title_label: QLabel | None = None
        self.subscription_desc_label: QLabel | None = None
        self.subscription_roadmap_label: QLabel | None = None
        self._settings = QSettings("Kasirin", settings.app_name, self)
        saved_palette_name = self._settings.value(
            "dashboard/palette",
            _DASHBOARD_PALETTES[0].name,
            type=str,
        )
        self._palette = next(
            (
                palette
                for palette in _DASHBOARD_PALETTES
                if palette.name == saved_palette_name
            ),
            _DASHBOARD_PALETTES[0],
        )
        self._dashboard_cards: list[QFrame] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 18, 28, 22)
        root.setSpacing(10)

        heading_row = QHBoxLayout()
        heading_row.addStretch(1)
        self.theme_button = QToolButton()
        self.theme_button.setText("Tema Dashboard")
        self.theme_button.setToolTip("Ubah warna dashboard owner")
        self.theme_button.setVisible(role_name == "OWNER")
        self.theme_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        theme_menu = QMenu(self.theme_button)
        for palette in _DASHBOARD_PALETTES:
            action = theme_menu.addAction(palette.name)
            action.setData(palette.name)
            action.setCheckable(True)
            action.setChecked(palette.name == self._palette.name)
            action.triggered.connect(self._on_theme_action_triggered)
        self.theme_button.setMenu(theme_menu)
        heading_row.addWidget(self.theme_button)

        self.logout_button = QPushButton("Keluar")
        self.logout_button.clicked.connect(self.logout_requested.emit)
        self.logout_button.setStyleSheet(
            "QPushButton { background: #dc2626; color: white; border: none; "
            "border-radius: 8px; padding: 9px 16px; font-weight: 600; }"
            "QPushButton:hover { background: #ef4444; }"
        )
        heading_row.addWidget(self.logout_button)
        root.addLayout(heading_row)

        self.store_profile = QWidget()
        store_profile_layout = QVBoxLayout(self.store_profile)
        store_profile_layout.setContentsMargins(0, 0, 0, 0)
        store_profile_layout.setSpacing(2)
        self.store_logo_label = QLabel()
        self.store_logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_logo_label.setFixedSize(90, 58)
        self.store_name_label = QLabel()
        self.store_name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_name_label.setStyleSheet(
            "font-size: 25px; font-weight: 700; color: #89b4fa;"
        )
        self.store_slogan_label = QLabel()
        self.store_slogan_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_slogan_label.setStyleSheet(
            "font-size: 18px; font-weight: 600; color: #89b4fa;"
        )
        self.store_address_label = QLabel()
        self.store_address_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_address_label.setStyleSheet(
            "font-size: 16px; color: #89b4fa;"
        )
        self.store_whatsapp_label = QLabel()
        self.store_whatsapp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.store_whatsapp_label.setStyleSheet(
            "font-size: 16px; color: #89b4fa;"
        )
        store_profile_layout.addWidget(
            self.store_logo_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        store_profile_layout.addWidget(self.store_name_label)
        store_profile_layout.addWidget(self.store_slogan_label)
        store_profile_layout.addWidget(self.store_address_label)
        store_profile_layout.addWidget(self.store_whatsapp_label)
        root.addWidget(self.store_profile, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.update_store_profile(store)

        welcome_row = QHBoxLayout()
        self.welcome_label = QLabel(f"Selamat datang, {user.full_name}")
        welcome_row.addWidget(self.welcome_label)
        welcome_row.addStretch(1)

        self.role_label = QLabel(role_name)
        self.role_label.setMaximumWidth(150)
        welcome_row.addWidget(self.role_label)
        root.addLayout(welcome_row)

        self.menu_grid = QGridLayout()
        self.menu_grid.setSpacing(10)
        root.addLayout(self.menu_grid, 1)

        if role_name == "OWNER":
            self.menu_grid.addWidget(
                self._create_card(
                    "Manajemen Toko",
                    "Kelola pengguna, inventaris, pengaturan toko, "
                    "dan pembayaran kasir.",
                    "Kelola Toko",
                    self.manage_users_requested.emit,
                ),
                0,
                0,
            )
            self.menu_grid.addWidget(
                self._create_card(
                    "Laporan",
                    "Penjualan, keuangan, dan absensi karyawan.",
                    "Lihat Laporan",
                    self.report_requested.emit,
                ),
                0,
                1,
            )
            self.menu_grid.addWidget(
                self._create_card(
                    "Master Data",
                    "Kelola produk, kategori, barcode, harga, dan stok awal.",
                    "Kelola Data",
                    self.master_data_requested.emit,
                ),
                0,
                2,
            )
            self.menu_grid.addWidget(
                self._create_card(
                    "Belanja dan Supplier",
                    "Catat barang masuk, stok, harga modal, dan status pembayaran; "
                    "kelola data pemasok.",
                    "Catat Belanja",
                    self.suppliers_requested.emit,
                ),
                1,
                0,
            )
            self._add_license_card()
        else:
            self.menu_grid.addWidget(
                self._create_card(
                    "Operasional Toko",
                    "Akses modul operasional sesuai peran Anda.",
                    "Buka Operasional",
                    self._show_placeholder,
                ),
                0,
                0,
            )
            self.menu_grid.addWidget(
                self._create_card(
                    "Laporan Penjualan",
                    "Ringkasan transaksi dan stok toko.",
                    "Lihat Laporan",
                    self._show_placeholder,
                ),
                0,
                1,
            )
        for column in range(3 if role_name == "OWNER" else 2):
            self.menu_grid.setColumnStretch(column, 1)
        self._apply_dashboard_palette()

    def _select_dashboard_palette(self, palette: _DashboardPalette) -> None:
        self._palette = palette
        for action in self.theme_button.menu().actions():
            action.setChecked(action.data() == palette.name)
        self._apply_dashboard_palette()
        self._settings.setValue("dashboard/palette", palette.name)
        self._settings.sync()
        if self._settings.status() != QSettings.Status.NoError:
            QMessageBox.warning(
                self,
                "Tema Dashboard",
                "Tema diterapkan, tetapi pilihan tidak dapat disimpan.",
            )

    def _on_theme_action_triggered(self, checked: bool = False) -> None:
        action = self.sender()
        if not isinstance(action, QAction):
            return
        palette = next(
            (item for item in _DASHBOARD_PALETTES if item.name == action.data()),
            None,
        )
        if palette is not None:
            self._select_dashboard_palette(palette)

    def _apply_dashboard_palette(self) -> None:
        palette = self._palette
        self.setObjectName("ownerDashboard")
        self.setStyleSheet(
            f"QWidget#ownerDashboard {{ background-color: {palette.background}; }}"
        )
        self.store_name_label.setStyleSheet(
            f"font-size: 25px; font-weight: 700; color: {palette.accent};"
        )
        self.store_slogan_label.setStyleSheet(
            f"font-size: 18px; font-weight: 600; color: {palette.accent};"
        )
        self.store_address_label.setStyleSheet(
            f"font-size: 16px; color: {palette.accent};"
        )
        self.store_whatsapp_label.setStyleSheet(
            f"font-size: 16px; color: {palette.accent};"
        )
        self.welcome_label.setStyleSheet(
            f"font-size: 14px; color: {palette.muted};"
        )
        self.role_label.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {palette.accent}; "
            f"background: {palette.surface_raised}; padding: 4px 8px; "
            "border-radius: 8px;"
        )
        for card in self._dashboard_cards:
            card.setStyleSheet(
                f"QFrame#dashboardCard {{ background: {palette.surface}; "
                f"border: 1px solid {palette.border}; border-radius: 14px; }}"
                "QLabel { border: none; background: transparent; }"
            )
            card.title_label.setStyleSheet(
                f"font-size: 15px; font-weight: 700; color: {palette.text};"
            )
            card.description_label.setStyleSheet(
                f"font-size: 12px; color: {palette.muted};"
            )
        if self.subscription_roadmap_label is not None:
            self.subscription_roadmap_label.setStyleSheet(
                f"font-size: 12px; color: {palette.muted};"
            )

    def _create_card(
        self,
        title,
        description,
        action,
        callback,
        accent="#007acc",
        accent_hover="#0098ff",
        extra_widget=None,
    ):
        card = QFrame()
        card.setObjectName("dashboardCard")
        palette = self._palette
        card.setStyleSheet(
            f"QFrame#dashboardCard {{ background: {palette.surface}; "
            f"border: 1px solid {palette.border}; border-radius: 14px; }}"
            "QLabel { border: none; background: transparent; }"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {palette.text};"
        )
        description_label = QLabel(description)
        description_label.setWordWrap(True)
        description_label.setStyleSheet(
            f"font-size: 12px; color: {palette.muted};"
        )
        action_button = QPushButton(action)
        action_button.setObjectName("cardActionButton")
        action_button.setStyleSheet(
            f"QPushButton {{ background: {accent}; color: white; border: none; "
            "border-radius: 7px; padding: 7px 10px; font-weight: 600; }"
            f"QPushButton:hover {{ background: {accent_hover}; }}"
        )
        action_button.clicked.connect(callback)
        layout.addWidget(title_label)
        layout.addWidget(description_label)
        if extra_widget is not None:
            layout.addWidget(extra_widget)
        layout.addStretch(1)
        layout.addWidget(action_button, alignment=Qt.AlignmentFlag.AlignLeft)
        card.setMinimumHeight(125)
        # Referensi label agar kartu bisa diperbarui tanpa query anak.
        card.title_label = title_label
        card.description_label = description_label
        card.action_button = action_button
        self._dashboard_cards.append(card)
        return card

    # ------------------------------------------------------ kartu lisensi

    def _add_license_card(self) -> None:
        """Kartu slot (1,1): Aktivasi bila belum, info langganan bila sudah."""
        if self._subscription_card is not None or self._activation_card is not None:
            return
        card = (
            self._create_subscription_card()
            if self._licensed
            else self._create_activation_card()
        )
        self.menu_grid.addWidget(card, 1, 1)

    def _create_activation_card(self) -> QFrame:
        card = self._create_card(
            "Aktivasi Lisensi",
            "Aktifkan atau perpanjang langganan POS Retail agar "
            "aplikasi berfungsi penuh.",
            "Buka Aktivasi",
            self.activation_requested.emit,
            accent="#b45309",
            accent_hover="#d97706",
        )
        self._activation_card = card
        self._subscription_card = None
        return card

    def _create_subscription_card(self) -> QFrame:
        roadmap_label = QLabel("")
        roadmap_label.setWordWrap(True)
        roadmap_label.setObjectName("subscriptionRoadmapLabel")
        roadmap_label.setStyleSheet(
            f"font-size: 12px; color: {self._palette.muted};"
        )
        card = self._create_card(
            "Langganan & Pengembangan",
            "Memeriksa langganan…",
            "Detail Langganan",
            self._show_subscription_detail,
            accent="#0f766e",
            accent_hover="#14b8a6",
            extra_widget=roadmap_label,
        )
        card.action_button.setToolTip(
            "Lihat sisa masa berlaku, daftar paket, dan fitur berikutnya."
        )
        self._subscription_card = card
        self._activation_card = None
        self.subscription_title_label = card.title_label
        self.subscription_desc_label = card.description_label
        self.subscription_roadmap_label = roadmap_label
        self.apply_subscription_info(
            local_subscription_info(self._get_license_service())
        )
        self._start_subscription_refresh()
        return card

    def _get_license_service(self) -> LicenseService | None:
        if self._license_service is None:
            try:
                self._license_service = LicenseService()
            except Exception:  # noqa: BLE001 — kartu tetap tampil tanpa lisensi
                return None
        return self._license_service

    def set_licensed(self, licensed: bool) -> None:
        """Tukar kartu Aktivasi ↔ info langganan tanpa membangun ulang UI."""
        licensed = bool(licensed)
        if licensed == self._licensed:
            if licensed:
                self.refresh_subscription()
            return
        self._licensed = licensed
        stale = self._activation_card if licensed else self._subscription_card
        if stale is not None:
            self.menu_grid.removeWidget(stale)
            stale.deleteLater()
        self._activation_card = None
        self._subscription_card = None
        self.subscription_title_label = None
        self.subscription_desc_label = None
        self.subscription_roadmap_label = None
        self.subscription_info = None
        card = (
            self._create_subscription_card()
            if licensed
            else self._create_activation_card()
        )
        self.menu_grid.addWidget(card, 1, 1)

    def _start_subscription_refresh(self) -> None:
        if not self._licensed:
            return
        worker = self._subscription_worker
        if worker is not None and worker.isRunning():
            return
        worker = SubscriptionInfoWorker(
            settings.billing_server_url or "",
            self._get_license_service(),
            parent=self,
        )
        worker.succeeded.connect(self._on_subscription_info)
        worker.failed.connect(self._on_subscription_error)
        self._subscription_worker = worker
        worker.start()

    def refresh_subscription(self) -> None:
        """Ambil ulang info langganan dari server (dipanggil dari MainWindow)."""
        self._start_subscription_refresh()

    def shutdown(self) -> None:
        """Tunggu worker info langganan selesai sebelum jendela dihancurkan."""
        worker = self._subscription_worker
        if worker is not None and worker.isRunning():
            worker.wait(3000)
        renewal = self._renewal_worker
        if renewal is not None and renewal.isRunning():
            renewal.stop()
            renewal.wait(3000)
        checkout = self._checkout_worker
        if checkout is not None and checkout.isRunning():
            checkout.wait(3000)

    def _on_subscription_info(self, info: object) -> None:
        if isinstance(info, dict):
            self.apply_subscription_info(info)

    def _on_subscription_error(self, message: str) -> None:
        self.apply_subscription_info(
            local_subscription_info(
                self._get_license_service(),
                note=message or "Info langganan tidak tersedia.",
            )
        )

    def apply_subscription_info(self, info: dict) -> None:
        """Tulis sisa langganan + pratinjau fitur berikutnya ke kartu."""
        if self.subscription_desc_label is None:
            # Kartu tidak sedang aktif (belum berlisensi / sudah ditukar).
            return
        self.subscription_info = info
        plan = info.get("plan") or {}
        if plan:
            status_line = (
                f"{plan.get('name') or cycle_label(plan.get('cycle', ''))}"
                f" · {plan.get('remaining_text') or '—'}"
            )
            expires_at = plan.get("expires_at")
            if expires_at:
                status_line += f" · berakhir {self._format_date(expires_at)}"
            self.subscription_desc_label.setText(status_line)
        else:
            self.subscription_desc_label.setText(
                "Belum ada langganan aktif untuk perangkat ini."
            )
        if self.subscription_roadmap_label is not None:
            self.subscription_roadmap_label.setText(
                self._roadmap_preview(info.get("roadmap") or [])
            )

    @staticmethod
    def _roadmap_preview(roadmap: list) -> str:
        if not roadmap:
            return "Fitur berikutnya menyusul dari server pengembang."
        shown = roadmap[:ROADMAP_PREVIEW_LIMIT]
        lines = ["Fitur berikutnya:"]
        lines.extend(
            f"• {escape(str(item.get('title') or ''))}" for item in shown
        )
        remaining = len(roadmap) - len(shown)
        if remaining > 0:
            lines.append(f"+{remaining} fitur lagi di Detail Langganan")
        return "\n".join(lines)

    @staticmethod
    def _format_date(value: str) -> str:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return value
        return parsed.strftime("%d %b %Y")

    def _build_subscription_dialog(self, info: dict) -> QDialog:
        dialog = QDialog(self)
        dialog.setWindowTitle("Langganan & Pengembangan")
        dialog.setObjectName("subscriptionDetailDialog")
        dialog.setMinimumSize(480, 420)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        body = QLabel()
        body.setObjectName("subscriptionDetailBody")
        body.setTextFormat(Qt.TextFormat.RichText)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setText(self._subscription_detail_html(info))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        layout.addWidget(scroll, 1)

        renew_button = QPushButton("Perpanjang Langganan")
        renew_button.setObjectName("renewSubscriptionButton")
        renew_button.setStyleSheet(
            "QPushButton { background: #0f766e; color: white; border: none; "
            "border-radius: 7px; padding: 8px 14px; font-weight: 600; }"
            "QPushButton:hover { background: #14b8a6; }"
        )
        renew_button.clicked.connect(self._renew_subscription)
        close_button = QPushButton("Tutup")
        close_button.setObjectName("closeSubscriptionButton")
        close_button.clicked.connect(dialog.accept)
        buttons = QHBoxLayout()
        buttons.addWidget(renew_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        return dialog

    def _show_subscription_detail(self) -> None:
        info = self.subscription_info or local_subscription_info(
            self._get_license_service()
        )
        self._build_subscription_dialog(info).exec()

    def _renew_subscription(self) -> None:
        """Start hosted checkout when this installation has a billing session."""
        service = self._get_license_service()
        base_url = (settings.billing_server_url or "").strip()
        if service is None or not base_url:
            self.activation_requested.emit()
            return
        data_dir = service.data_dir
        try:
            customer_token = (data_dir / "billing-customer-token.txt").read_text(
                encoding="utf-8"
            ).strip()
            device_pk = int((data_dir / "billing-device-id.txt").read_text(
                encoding="utf-8"
            ).strip())
            device_token = (data_dir / "billing-device-token.txt").read_text(
                encoding="utf-8"
            ).strip()
        except (OSError, ValueError):
            # Existing web checkout remains available for older installations.
            open_external_url(base_url)
            return
        plans = (self.subscription_info or {}).get("plans") or []
        if not plans:
            open_external_url(base_url)
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Pilih Paket Langganan")
        dialog.setMinimumWidth(380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Pilih paket yang ingin dibeli:"))
        plan_input = QComboBox()
        for plan in plans:
            if not isinstance(plan, dict) or not plan.get("code"):
                continue
            label = f"{plan.get('name') or plan['code']} · {rupiah(int(plan.get('price_idr') or 0))}"
            duration = plan.get("duration_days")
            if duration:
                label += f" · {duration} hari"
            plan_input.addItem(label, str(plan["code"]))
        layout.addWidget(plan_input)
        buttons = QHBoxLayout()
        buy_button = QPushButton("Lanjut ke Pembayaran")
        cancel_button = QPushButton("Batal")
        buy_button.setEnabled(bool(plan_input.count()))
        buttons.addWidget(buy_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        cancel_button.clicked.connect(dialog.reject)
        buy_button.clicked.connect(dialog.accept)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        plan_code = str(plan_input.currentData() or "")
        if not plan_code:
            return
        baseline = service.license_payload() or {}
        self._begin_checkout(
            base_url, customer_token, device_pk, device_token, plan_code, baseline
        )

    def _begin_checkout(
        self, base_url: str, customer_token: str, device_pk: int,
        device_token: str, plan_code: str, baseline: dict,
    ) -> None:
        worker = CheckoutWorker(
            base_url, customer_token, device_pk, plan_code, parent=self
        )
        worker.succeeded.connect(
            lambda result: self._on_renewal_checkout_ready(
                result, base_url, device_token, baseline
            )
        )
        worker.failed.connect(self._on_renewal_checkout_failed)
        self._checkout_worker = worker
        worker.start()

    def _on_renewal_checkout_ready(
        self, result: object, base_url: str, device_token: str, baseline: dict
    ) -> None:
        if not isinstance(result, dict) or not result.get("payment_url"):
            QMessageBox.warning(self, "Pembayaran", "Server tidak mengembalikan tautan pembayaran.")
            return
        if not open_external_url(str(result["payment_url"])):
            QMessageBox.warning(self, "Pembayaran", "Tautan pembayaran gagal dibuka.")
            return
        QMessageBox.information(
            self, "Pembayaran dibuka",
            "Selesaikan pembayaran di browser. POS akan memeriksa lisensi "
            "secara otomatis setelah pembayaran terkonfirmasi.",
        )
        previous = self._renewal_worker
        if previous is not None and previous.isRunning():
            previous.stop()
            previous.wait(1000)
        worker = RenewalPollingWorker(base_url, device_token, baseline, parent=self)
        worker.succeeded.connect(self._on_renewal_license_updated)
        self._renewal_worker = worker
        worker.start()

    def _on_renewal_checkout_failed(self, message: str) -> None:
        QMessageBox.warning(self, "Pembayaran gagal", message)

    def _on_renewal_license_updated(self, document: object) -> None:
        service = self._get_license_service()
        if service is None or not isinstance(document, dict):
            return
        try:
            service.activate_from_document(document)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Lisensi", f"Lisensi baru tidak dapat dipasang: {exc}")
            return
        self.refresh_subscription()
        QMessageBox.information(self, "Langganan diperbarui", "Lisensi POS berhasil diperbarui.")

    def _subscription_detail_html(self, info: dict) -> str:
        plan = info.get("plan") or {}
        parts = [
            f"<h3 style='color:{self._palette.accent}; margin-bottom:4px;'>"
            "Langganan Aktif</h3>"
        ]
        if plan:
            status = "Aktif" if info.get("activated") else "Tidak aktif"
            expires = plan.get("expires_at")
            parts.append(
                "<p style='margin-top:2px;'>"
                f"Status: <b>{escape(status)}</b><br/>"
                f"Paket: <b>{escape(str(plan.get('name') or '—'))}</b>"
                f" ({escape(cycle_label(str(plan.get('cycle') or '')))})<br/>"
                f"Berakhir: {escape(DashboardView._format_date(expires) if expires else 'tanpa batas waktu')}<br/>"
                f"Sisa waktu: <b>{escape(str(plan.get('remaining_text') or '—'))}</b>"
                "</p>"
            )
        else:
            parts.append("<p style='margin-top:2px;'>Belum ada langganan aktif.</p>")

        plans = info.get("plans") or []
        if plans:
            parts.append(
                f"<h3 style='color:{self._palette.accent}; margin-bottom:4px;'>"
                "Paket Langganan</h3><ul>"
            )
            for item in plans:
                duration = item.get("duration_days")
                duration_text = f"{duration} hari" if duration else "tanpa batas waktu"
                parts.append(
                    "<li>"
                    f"<b>{escape(str(item.get('name') or item.get('code') or ''))}</b>"
                    f" — {escape(rupiah(int(item.get('price_idr') or 0)))}"
                    f" · {escape(duration_text)}"
                    "</li>"
                )
            parts.append("</ul>")

        roadmap = info.get("roadmap") or []
        if roadmap:
            parts.append(
                f"<h3 style='color:{self._palette.accent}; margin-bottom:4px;'>"
                "Fitur Berikutnya (Rencana Pengembangan)</h3><ul>"
            )
            for item in roadmap:
                title = escape(str(item.get("title") or ""))
                eta = str(item.get("eta") or "").strip()
                description = str(item.get("description") or "").strip()
                line = f"<li><b>{title}</b>"
                if eta:
                    line += (
                        f" <span style='color:{self._palette.muted};'>"
                        f"({escape(eta)})</span>"
                    )
                if description:
                    line += f"<br/>{escape(description)}"
                parts.append(line + "</li>")
            parts.append("</ul>")
        else:
            parts.append(
                "<p>Daftar fitur berikutnya hanya tersedia saat webserver "
                "terjangkau.</p>"
            )

        note = str(info.get("note") or "").strip()
        if note:
            parts.append(
                f"<p style='color:{self._palette.muted}; font-size:12px;'>"
                f"{escape(note)}</p>"
            )
        return "".join(parts)

    def _show_placeholder(self):
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "Belum tersedia",
            "Modul ini akan dikembangkan pada tahap berikutnya.",
        )

    def update_store_profile(self, store: Store | None) -> None:
        self.store = store
        self.store_name_label.setText(store.name if store else "")
        self.store_slogan_label.setText(
            (store.slogan or "") if store else ""
        )
        self.store_address_label.setText(
            (store.address or "") if store else ""
        )
        self.store_whatsapp_label.setText(
            f"WhatsApp: {store.whatsapp}" if store and store.whatsapp else ""
        )
        self.store_slogan_label.setVisible(bool(store and store.slogan))
        self.store_address_label.setVisible(bool(store and store.address))
        self.store_whatsapp_label.setVisible(bool(store and store.whatsapp))

        self.store_logo_label.clear()
        self.store_logo_label.setVisible(False)
        if store and store.logo_path and Path(store.logo_path).is_file():
            pixmap = QPixmap(store.logo_path)
            if not pixmap.isNull():
                self.store_logo_label.setPixmap(
                    pixmap.scaled(
                        self.store_logo_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self.store_logo_label.setVisible(True)
