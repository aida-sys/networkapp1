2# Prompt Proyek Mobile Kasirin (Flutter)

Salin prompt di bawah ini ke coding agent saat bekerja dari folder `android/`.

---

## Prompt

Kamu adalah senior Flutter engineer yang bertugas membuat **proyek baru aplikasi POS Kasirin untuk Android dan iOS**. Gunakan `android/` sebagai folder kerja panduan, dan buat root proyek Flutter di `android/kasirin_mobile/`. Repository desktop pada folder induk (`../`) adalah spesifikasi perilaku dan data yang harus dipelajari, bukan folder yang boleh dimodifikasi. Struktur Flutter di `android/kasirin_mobile/` akan memiliki subfolder platform `android/` dan `ios/`; jangan membuat proyek native Android Kotlin terpisah.

### Tujuan

Port aplikasi POS desktop Kasirin dari Python/PySide6 menjadi aplikasi Flutter/Dart lintas platform Android dan iOS yang nyaman untuk layar sentuh, tetap offline-first, dan mempertahankan perilaku bisnis, aturan validasi, struktur data, serta alur yang benar-benar sudah ada di aplikasi desktop.

Jangan menganggap bahwa mengemas ulang aplikasi PySide6 atau mengganti ekstensi installer menjadi APK/IPA sudah cukup. Port aturan bisnis ke Dart dan ganti semua integrasi khusus desktop dengan implementasi mobile yang sesuai.

### Teknologi dan batas proyek

- Flutter stable dan Dart stable; gunakan Material 3, Flutter Navigator/router yang terstruktur (misalnya `go_router`), dan satu pola state management yang konsisten (misalnya Riverpod). Jangan mencampur beberapa pola tanpa kebutuhan.
- Gunakan Drift sebagai lapisan SQLite lokal dengan migrasi versi dan test schema. Gunakan repository/domain/use-case yang memisahkan aturan bisnis dari widget. Jalankan operasi database berat di luar UI thread sesuai pola Flutter/Drift.
- Pin dependency Flutter/Dart di `pubspec.yaml` dan commit `pubspec.lock` untuk aplikasi. Tambahkan package hanya bila diperlukan dan catat alasannya; evaluasi dukungan Android+iOS, lisensi, maintenance, dan permission package sebelum mengadopsinya.
- Buat struktur feature-first yang mudah diuji, misalnya `lib/core/`, `lib/data/`, `lib/domain/`, `lib/features/`, `lib/platform/`; letakkan generator Drift dalam alur build yang terdokumentasi.
- Tentukan Android `applicationId`/`minSdk`, iOS bundle identifier/deployment target, ikon, nama aplikasi Kasirin, theme, permission, konfigurasi debug/release, serta build flavors bila diperlukan. Jangan memasukkan Android signing key, iOS certificate, provisioning profile, atau secrets ke repository.
- Gunakan bahasa Indonesia untuk UI dan format Rupiah lokal. Desain touch-first, responsif untuk ponsel/tablet, keyboard eksternal/scanner, safe areas/insets, rotasi yang wajar, aksesibilitas, dan navigasi Back sesuai platform.
- Satu codebase Flutter boleh memakai plugin package yang tersedia untuk kedua platform; untuk fungsi yang tidak tercakup, buat adapter platform terpisah dengan federated plugin/platform channel, bukan conditional logic yang tersebar di widget.
- Gunakan **billing_server FastAPI yang sudah ada di `../server/`** sebagai satu-satunya server untuk akun pelanggan, paket, checkout/perpanjangan, status subscription, registrasi perangkat, dan distribusi lisensi. Jangan membuat backend billing kedua, Firebase, atau layanan cloud baru.
- Server billing yang sama **bukan** database transaksi POS. Penjualan, stok, kasir, pembelian, dan laporan operasional tetap disimpan di Drift/SQLite lokal pada Android atau iOS. Jangan mengirim/sinkronkan transaksi ke server kecuali API sinkronisasi bisnis dirancang dan disetujui secara eksplisit.
- Audit dan gunakan kontrak endpoint billing yang benar-benar ada sebelum menulis klien. Bila dukungan lisensi Android membutuhkan perubahan server, perubahan hanya boleh dilakukan pada `../server/`, wajib backward-compatible untuk desktop yang sudah dirilis, mempunyai migrasi aman dan test desktop+Android, serta jangan menyentuh implementasi POS desktop di `../app/`.

### Sumber kebenaran dan tahap analisis

Sebelum menulis implementasi, petakan repository induk. Prioritaskan kode aktif dan test atas dokumentasi yang mungkin sudah tertinggal:

1. Model dan skema: `../app/models/entities.py`, `../app/core/database.py`, `../migrations/versions/`, `../DATABASE.md`.
2. Aturan bisnis: seluruh modul di `../app/services/` dan repository di `../app/repositories/`.
3. Alur UI dan role: `../app/ui/main_window.py`, `../app/ui/views/`, dan `../app/ui/widgets.py`.
4. Perilaku yang dapat diuji: seluruh `../tests/`, terutama test checkout/kasir, master data, purchase, inventory, financial, attendance, report, login/user, license/trial, store settings, dan payment wizard.
5. Hardware, konfigurasi, dan packaging: `../app/hardware/`, `../app/core/config.py`, `../app/services/license_service.py`, `../app/services/trial_service.py`, `../app/services/online_activation.py`, `../app/services/billing_client.py`, `../README.md`, dan `../ARCHITECTURE.md`.

Dokumentasi jumlah tabel tidak konsisten. Jangan mengandalkan angka jumlah tabel dari README/DATABASE.md. Inventarisasi `Base.metadata`, model, dan revisi Alembic terbaru, lalu dokumentasikan tabel, kolom, constraint, index, foreign key, soft-delete, serta revisi sumber di `docs/database-parity.md` sebelum membuat skema Drift.

Buat `docs/desktop-parity-matrix.md` berisi setiap fitur/alur desktop, service dan test sumbernya, layar Android yang mengimplementasikannya, serta status: belum, berjalan, atau terverifikasi. Jangan mengklaim parity selesai hanya karena nama menu sudah tersedia.

### Kontrak database dan integritas transaksi

- Gunakan Drift/SQLite, bukan database cloud. Pertahankan makna, nama tabel/kolom, relasi, nullable/default, unique/check constraints, index, soft-delete, dan foreign key dari skema desktop sedekat mungkin. Catat setiap perbedaan Flutter/SQLite secara eksplisit.
- Pertahankan uang sebagai integer Rupiah (`int` Dart / SQLite INTEGER 64-bit); jangan gunakan `double` untuk uang. Timestamp disimpan/diproses konsisten sebagai UTC dan dikonversi ke zona lokal hanya untuk tampilan. Boolean harus dipetakan konsisten ke SQLite INTEGER.
- Pertahankan tabel yang ditemukan pada skema aktif, termasuk domain user/role/permission, toko, kategori/satuan/produk, shift, pelanggan/supplier, penjualan/item/payment, stock movement, harga bertingkat/price list/promotion, pembelian dan item, opname dan item, kasir harian, attendance/login history, inventaris, expenses, akun, financial settings, journal entries/lines, financial payments, cash transactions, audit logs, serta payment settings/wizard. Nama sebenarnya dan kolom final wajib diambil dari model dan migrasi, bukan daftar ringkas ini.
- Semua checkout dan perubahan stok harus menggunakan transaksi database atomik. Pertahankan urutan bisnis desktop: simpan sale, item, pembayaran, update stok, stock movement, dan audit log; jika salah satu tahap gagal, rollback seluruh transaksi. Pastikan retry/double-tap tidak menggandakan sale atau pergerakan stok.
- Buat Drift schema migration berurutan dan test migrasi di Android serta iOS. Jangan memakai destructive migration atau menghapus database saat upgrade. Pastikan tipe affinity, foreign keys, transaction behavior, dan migrasi berjalan pada SQLite kedua platform.
- Database desktop `%LOCALAPPDATA%\\POSApp\\data\\pos.db` dan database mobile app-private adalah file lokal berbeda; jangan mengklaim keduanya otomatis satu database atau tersinkron. billing_server hanya menyimpan data akun/langganan/perangkat/pembayaran/lisensi, bukan database transaksi POS. Sediakan rencana import/export dan dokumentasikan kompatibilitas data. Sinkronisasi real-time transaksi hanya boleh dibuat bila API kontrak, konflik, autentikasi, dan kebijakannya disetujui secara eksplisit.
- Buat data demo hanya untuk debug/test. Instalasi production baru harus kosong dan menyediakan setup OWNER pertama kali sesuai perilaku desktop.

### Modul dan alur yang harus dipetakan

Implementasikan sebagai vertical slices: model/domain → Drift DAO/repository → use case/service → provider/state notifier → Flutter feature/widget → test.

- **Setup dan login:** setup OWNER pada database kosong; validasi username/password; autentikasi lokal; role routing; user aktif/nonaktif, failed login/lockout, ganti password wajib, riwayat login, dan manajemen pengguna sesuai service/test desktop. Jangan membuat akun demo production.
- **Role dan akses:** pertahankan role/permission dan batas aksi dari kode desktop. OWNER, ADMIN, SUPERVISOR, dan CASHIER tidak boleh mendapat akses lebih hanya karena UI menyembunyikan tombol; aturan tetap ditegakkan pada use case.
- **Kasir dan shift:** buka/tutup shift, modal kas, status shift, pencarian produk SKU/barcode/nama/kategori, scanner keyboard wedge, keranjang, ubah qty, diskon, harga khusus grosir bertingkat, customer, konfirmasi pembayaran, kembalian, struk, transaksi harian, dan laporan harian kasir. Pertahankan shortcut desktop sebagai kemudahan tambahan bila sesuai, tetapi sediakan kontrol sentuh yang jelas.
- **Produk/master data:** kategori, unit, produk, SKU/barcode unik, harga beli/jual, stok/minimum stok, supplier pilihan, harga khusus bertingkat, penambahan stok dengan stock movement, soft-delete, import spreadsheet, validasi dan transaksi batch.
- **Pembelian/supplier:** supplier, purchase order, daftar dan penerimaan pembelian, harga beli yang mengubah margin sesuai aturan layanan, kondisi PAID/TEMPO/DP, due date, pembayaran sebagian, pelunasan, hutang, stock movement, serta pembuatan produk cepat sesuai implementasi desktop.
- **Persediaan:** nilai stok, stok minimum, riwayat stock movement, inventaris toko non-jual, dan stock opname; simpan selisih sebagai pergerakan yang dapat diaudit.
- **Keuangan/pembukuan:** initialization date dan saldo awal, akun, jurnal double-entry yang seimbang, penjualan dan HPP, pembelian/hutang, expenses tunai/hutang/DP, pembayaran sebagian, akun kas/bank, cash transactions, financial payments, dan report periode. Validasi keseimbangan debit/kredit pada layer domain/service, bukan hanya UI.
- **Laporan:** laporan penjualan, produk, persediaan/nilai stok, attendance, kasir harian, hutang/piutang yang memang tersedia di service, Laba Rugi, Neraca, Arus Kas, Neraca Saldo, dan Jurnal Umum. Pertahankan aturan periode dan sumber angka pada service desktop. Ekspor PDF/DOCX atau format Android yang disetujui lewat Android Storage Access Framework.
- **Pengaturan toko:** profil, nama, slogan, alamat, WhatsApp, logo, format struk, metode pembayaran, status konfigurasi wizard, dan aset media di app storage.
- **Payment wizard/integrasi:** port status dan validasi wizard yang ada. Simpan token/rahasia lokal menggunakan secure storage plugin yang memakai Android Keystore dan iOS Keychain. Jangan pernah memasukkan server key, private key, token, password produksi, atau secret ke source, asset, log, APK, atau IPA. Pertahankan batas antara metode yang benar-benar terintegrasi dan metode simulasi.
- **billing_server bersama:** implementasikan klien Android yang memakai base URL HTTPS dari konfigurasi build/runtime yang aman dan DTO yang cocok dengan API FastAPI di `../server/app/main.py`. Kontrak desktop saat ini mencakup:
	- `POST /api/auth/register` dengan email/password/nama toko untuk akun web billing.
	- `POST /api/auth/login` yang mengembalikan customer bearer token.
	- `POST /api/pos/register` dengan `Authorization: Bearer <customer-token>` dan dokumen `posreq`; respons berisi `device_token`.
	- `GET /api/pos/license` dan `GET /api/pos/status` dengan `Authorization: Bearer <device-token>` untuk polling dokumen lisensi, roadmap, paket, dan status subscription.
	- `GET /api/licenses/me`, `POST /api/licenses/{license_pk}/renew`, dan `POST /api/checkout/create` dengan customer bearer token untuk daftar lisensi, perpanjangan, dan checkout.
	- Ikuti payload, status HTTP, validasi, response/error shape, dan auth dari implementasi/test server yang sebenarnya; daftar ini bukan izin untuk mengubah kontrak tanpa migrasi/backward compatibility.
- Pisahkan akun pelanggan web billing dari akun lokal OWNER/ADMIN/SUPERVISOR/CASHIER. Jangan mengirim password lokal karyawan ke billing_server. Simpan customer/device token di secure storage lintas platform (Android Keystore/iOS Keychain), jangan log token, dan hapus token lokal saat logout/revoke yang sesuai.
- Operasi POS lokal harus tetap berjalan offline. Registrasi/aktivasi/pembayaran/langganan memerlukan jaringan; tampilkan status dan retry dengan backoff tanpa menggandakan checkout atau registrasi perangkat. Jangan menahan transaksi lokal sambil menunggu billing_server.

### Adaptasi platform yang wajib, bukan stub

- **Lisensi dan trial:** kode desktop membaca Windows `MachineGuid` dan secara eksplisit menolak OS selain Windows. Jangan memanggil `winreg` atau menonaktifkan lisensi pada target mobile. Android/iOS wajib menggunakan billing_server yang sama untuk customer login, registrasi device, polling status, dan penerimaan signed license document. Kontrak server sekarang menerima `installation_id` UUID dan `device_id` hex 64 karakter, tetapi request/licensing desktop belum membawa identitas platform dan verifikasi desktop memakai fingerprint Windows. Karena itu, sebelum aktivasi mobile dianggap berfungsi, rancang serta implementasikan kontrak platform-aware pada server (misalnya platform/OS, versi skema, installation ID, dan device binding yang privasi-sesuai) serta format payload lisensi bertanda tangan yang dapat diverifikasi oleh klien desktop lama dan klien Flutter. Pertahankan kompatibilitas format/registrasi Windows lama, buat migrasi database non-destruktif bila diperlukan, dan tambahkan test untuk perangkat Windows lama serta Android/iOS. Gunakan hanya public key yang memang didistribusikan di `../app/core/license_public_key.pem`; private signing key tidak pernah masuk proyek mobile atau APK/IPA. Tentukan identitas instalasi/perangkat per platform secara stabil dan privasi-sesuai, gunakan API platform yang diizinkan, dan dokumentasikan batasnya. Port semantik trial 7×24 jam, mulai pada peluncuran pertama, state lokal, clock rollback/high-water mark, lisensi aktif/kedaluwarsa, aktivasi online/offline yang memang didukung. Jangan mengubah hasil verifikasi lisensi untuk mempermudah test; buat key/test fixture khusus test.
- **Barcode:** dukung scanner eksternal sebagai keyboard input. Untuk kamera, pilih package Flutter yang aktif dirawat dan mendukung CameraX di Android serta AVFoundation di iOS; tangani permission runtime, lifecycle, torch, dan fallback pencarian manual. Jangan meminta akses kamera sebelum fitur dipakai.
- **Printer:** `QPrinter`/`QPrintDialog` tidak dipakai pada Flutter. Definisikan interface printer Dart dan adapter per platform. Evaluasi dukungan Android Print Framework/Bluetooth ESC/POS dan iOS AirPrint/Bluetooth/MFi secara terpisah; gunakan platform channel/federated plugin jika perlu. Uji model printer, permission, encoding, ukuran kertas, status koneksi, dan cash drawer pada perangkat nyata; jangan menyamakan kemampuan Android dan iOS tanpa bukti.
- **File dan backup:** gunakan direktori app-private untuk database/state; pilih file/document picker dan sharing package yang mendukung Android Storage Access Framework serta iOS document picker/files. Minta permission seminimal mungkin; jangan menyimpan data di lokasi yang dapat dibaca bebas aplikasi lain.
- **Jaringan:** gunakan billing_server existing untuk alur akun/langganan/lisensi seperti kontrak di atas. Fitur offline POS tetap dapat dipakai tanpa koneksi kecuali aksi billing yang memang memerlukan server. Gunakan HTTPS dan konfigurasi base URL per build/flavor; jangan memasukkan private key, Midtrans server key, token admin, atau secret server ke klien. Tentukan loading/error/retry dan hindari request checkout/registrasi duplikat saat koneksi putus atau retry.

### UI/UX Android

Gunakan pola POS touch-first, hierarki jelas, tombol pembayaran utama mudah dijangkau, target sentuh besar, keypad numerik untuk nominal/qty, pencarian yang cepat, keranjang yang mudah diperiksa, dan ringkasan total selalu terbaca. Adaptasikan dashboard/menu desktop menjadi navigasi Flutter yang sesuai pada Android dan iOS, bukan mengecilkan window desktop menjadi layar ponsel. Pertahankan istilah/domain Indonesia yang sudah digunakan aplikasi. Tambahkan state loading, kosong, validasi, gagal, sukses, offline, lisensi/trial, serta konfirmasi untuk aksi destruktif. Pisahkan domain/state dari widget.

### Keamanan dan privasi

Jangan pernah membaca, menyalin, mencetak, atau memasukkan file `../server/.env`, `.env`, database lokal, token ngrok, signing private key, atau credential lain ke proyek/prompt/output. Gunakan `.env.example`/local config hanya sebagai dokumentasi nama konfigurasi; rahasia production diberikan melalui mekanisme aman saat deployment. Password hash existing harus dianalisis formatnya: jangan simpan plaintext atau mereset user diam-diam. Jika hash desktop Argon2 tidak dapat diverifikasi secara kompatibel, rancang migrasi login yang aman setelah autentikasi berhasil dan dokumentasikan dampaknya.

### Strategi pengerjaan

1. Buat inventaris fitur, skema, API billing existing, dependency/platform gap Android+iOS, serta parity matrix sebelum coding.
2. Buat skeleton Flutter di `android/kasirin_mobile/` (`pubspec.yaml`, `lib/`, `test/`, `integration_test/`, serta host folders `android/` dan `ios/`), konfigurasi endpoint billing per flavor/environment, app shell, navigasi, theme, serta persistence dasar.
3. Port database dan migrasi Drift; verifikasi tabel/constraint dengan test schema.
4. Implementasikan autentikasi lokal/setup OWNER dan master data; buat klien billing terpisah untuk akun web, device token, subscription, dan lisensi.
5. Implementasikan shift dan checkout sebagai vertical slice lokal, lalu verifikasi transaksi rollback, stock movement, harga grosir, pembayaran, dan struk.
6. Implementasikan perubahan server minimal yang diperlukan untuk platform-aware lisensi secara backward-compatible; test API desktop lama dan Android baru sebelum mengandalkan aktivasi Android.
7. Implementasikan purchase, inventory, finance, attendance, reports, settings, payment, dan license secara bertahap; perbarui parity matrix setiap slice.
8. Uji pada emulator/perangkat fisik Android serta simulator/perangkat iOS. Uji scanner/printer nyata secara terpisah pada kedua platform; jangan menyatakan dukungan platform/hardware hanya dari compile sukses.
9. Sediakan README mobile yang berisi Flutter/Dart, Android Studio/SDK, Xcode/macOS untuk build iOS, konfigurasi base URL billing, `flutter pub get`, `flutter analyze`, `flutter test`, integration test, permission, build flavor, backup, migrasi data, batas fitur, serta cara menghasilkan APK/AAB dan archive/IPA. Tegaskan bahwa build/signing iOS final memerlukan macOS + Xcode. Jangan membuat release keystore/certificate atau menandatangani release memakai secret di repository.

### Acceptance criteria

- Proyek Flutter dapat dianalisis dan di-build untuk Android dengan toolchain yang terdokumentasi; target iOS terkonfigurasi dan dapat diuji di macOS/Xcode. Build IPA final tidak boleh diklaim telah diuji dari Windows.
- Aplikasi fresh install masuk ke setup OWNER tanpa demo data; sesudah setup login mengarahkan role ke area yang benar.
- Test membuktikan aturan service desktop penting tetap sama, khususnya validasi produk, threshold harga grosir, satu checkout atomik, pembayaran, perubahan stok sekali saja, rollback kegagalan, shift, pembelian PAID/TEMPO/DP, pembayaran sebagian, jurnal seimbang, trial/license, dan otorisasi role.
- Drift migrations mempertahankan data di Android dan iOS; tidak ada destructive reset; import/export kompatibel diuji dengan fixture SQLite yang disanitasi.
- Aplikasi POS dasar tetap berfungsi offline tanpa mengirim transaksi lokal; billing_server existing berfungsi untuk login akun web, registrasi perangkat, checkout/subscription, dan polling lisensi pada kedua platform mobile.
- Perubahan API/schema server untuk Android/iOS tetap backward-compatible dan test membuktikan aktivasi desktop Windows lama tidak rusak.
- Tidak ada kredensial rahasia tertanam, tidak ada backend billing duplikat, dan tidak ada klaim sinkronisasi data transaksi tanpa fitur/kontrak yang disetujui.
- UI nyaman pada ponsel/tablet Android dan iPhone/iPad, dapat dipakai dengan sentuhan, dan menangani lifecycle serta perubahan konfigurasi pada kedua platform.
- Laporan parity menyebut secara jujur fitur yang sudah setara, yang belum, dan alasan perbedaan platform. Jangan mengklaim seluruh fitur desktop selesai sampai test dan matriks parity mendukung klaim tersebut.

Mulai dengan menganalisis repository dan menghasilkan `docs/desktop-parity-matrix.md`, `docs/database-parity.md`, serta rencana implementasi yang terurut. Setelah itu implementasikan proyek Flutter di `android/kasirin_mobile/` secara bertahap. Jangan mengubah source desktop di `../`.
