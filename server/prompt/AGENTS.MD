# Rancangan POS Kafe Hybrid dengan QR Ordering

Untuk proyek POS kamu yang sudah menggunakan Flutter untuk Windows/Android dan FastAPI sebagai backend, saya menyarankan arsitektur Local-first Hybrid POS: transaksi utama tetap berjalan di jaringan lokal kafe, sedangkan server cloud menangani sinkronisasi antarperangkat, backup, lisensi, dan laporan jarak jauh.

Prinsip utamanya: kita menambahkan fitur QR ordering ke aplikasi yang sudah ada, bukan membangun ulang POS dari nol. Struktur kode lama, database SQLite, autentikasi lokal, dan modul kasir tetap dipertahankan selama memungkinkan.

## 1. Gambaran sistem

QR Code di setiap meja

Pelanggan scan dengan kamera HP, tanpa perlu instal aplikasi

Web menu kafe — Flutter Web atau web responsif

Pilih menu, variasi, jumlah, catatan, lalu kirim pesanan

API melalui jaringan lokal

Server lokal kafe

FastAPI + SQLite saat ini, dengan jalur migrasi ke PostgreSQL jika dibutuhkan

Kasir Windows

Transaksi dan pembayaran

Layar dapur/barista

Antrean dan status pesanan

POS Android

Perangkat kasir tambahan

Database lokal

Pesanan, stok, dan pembayaran

Sinkronisasi saat internet tersedia

Server cloud

Sinkronisasi, backup, lisensi, dan laporan multi-outlet

Catatan penting: pelanggan yang terhubung melalui QR hanya bisa menjangkau server lokal jika HP berada di jaringan yang dapat mengakses server kafe. Jika pelanggan menggunakan jaringan seluler atau Wi-Fi tamu yang terisolasi, pemesanan lokal tidak akan otomatis berfungsi. Solusinya adalah mengatur Wi-Fi khusus yang aman atau menggunakan endpoint cloud untuk pemesanan online.

## 2. Modul yang perlu ditambahkan

Saya membagi sistem menjadi modul yang dapat dikembangkan bertahap. Nama di bawah adalah usulan modul baru, bukan asumsi bahwa file tersebut sudah ada di proyek kamu.

A. QR Table Ordering

- Membuat QR unik untuk setiap outlet dan meja.
- Membuka menu berdasarkan identitas meja.
- Mendukung kategori, varian, topping, catatan pesanan, dan keranjang.
- Mengirim pesanan dengan nomor referensi unik agar tidak terjadi pesanan ganda.

B. Order Management

- Menyatukan pesanan QR dan pesanan kasir.
- Menyimpan snapshot nama produk, harga, diskon, pajak, dan jumlah saat transaksi.
- Mendukung dine-in, takeaway, pembatalan, dan pengembalian dana.
- Mengatur status pesanan serta antrean dapur/barista.

C. Payment Management

- Tunai: input uang diterima dan hitung kembalian.
- QRIS: pembayaran melalui penyedia pembayaran yang mendukung QRIS dinamis.
- Transfer: catat metode, referensi, dan bukti atau hasil verifikasi.
- Mendukung pembayaran sebagian atau beberapa metode dalam satu transaksi jika aturan bisnis mengizinkan.

D. Kitchen Display System (KDS)

- Layar antrean pesanan.
- Pemisahan pesanan minuman dan makanan berdasarkan stasiun produksi.
- Tombol mulai proses, siap, dan selesai.
- Pembaruan status ke kasir dan pelanggan.

E. Local–Cloud Sync

- Antrean sinkronisasi saat internet putus.
- Pengiriman ulang otomatis dan aman dari duplikasi.
- Sinkronisasi produk, harga, stok, transaksi, dan status sesuai kebijakan.
- Penanganan konflik, audit, serta indikator status koneksi.

## 3. Arsitektur backend dan database

Ada dua tingkat penyimpanan yang berbeda: database operasional lokal dan database cloud.

| Komponen       | Teknologi               | Tanggung jawab                                             |
| -------------- | ----------------------- | ---------------------------------------------------------- |
| Aplikasi kasir | Flutter Windows/Android | UI kasir, pembayaran, stok, laporan                        |
| Menu pelanggan | Web responsif           | Scan QR, menu, keranjang, status pesanan                   |
| Backend lokal  | FastAPI                 | Validasi transaksi dan layanan untuk semua perangkat lokal |
| Database lokal | SQLite yang sudah ada   | Data operasional dan transaksi offline                     |
| Database cloud | PostgreSQL              | Sinkronisasi, data terpusat, laporan jarak jauh            |
| Komunikasi     | REST API + WebSocket    | Permintaan API dan pembaruan status secara real-time       |
| Pembayaran     | Adapter penyedia QRIS   | Pembuatan tagihan dan verifikasi status pembayaran         |

### SQLite atau PostgreSQL di server lokal?

Untuk tahap awal, pertahankan SQLite yang sudah ada. Namun, jangan membuka satu file SQLite melalui jaringan dari banyak perangkat. Semua perangkat harus berkomunikasi melalui FastAPI. SQLite tetap dapat digunakan di server lokal dengan akses database terpusat melalui satu proses backend.

Jika jumlah kasir, outlet, atau transaksi bertambah, PostgreSQL di server lokal bisa menjadi tahap berikutnya. PostgreSQL cloud tetap menjadi penyimpanan terpusat untuk sinkronisasi dan akses jarak jauh.

### Struktur tabel yang dibutuhkan

Nama berikut merupakan rancangan logis. Struktur tabel lama perlu diperiksa terlebih dahulu agar kita tidak membuat duplikat atau merusak relasi yang sudah ada.

### Data master

`outlets`, `dining_tables`, `products`, `product_variants`, `categories`, `recipes`, `users`, `roles`

Menyimpan identitas outlet/meja, katalog menu, varian, resep atau komposisi bahan, dan hak akses staf.

### Pesanan dan pembayaran

`orders`, `order_items`, `payments`, `payment_events`, `receipts`, `kitchen_tickets`

Memisahkan pesanan, detail barang, pembayaran, peristiwa pembayaran, struk, dan tiket dapur.

### Inventori dan akuntansi

`stock_items`, `stock_movements`, `stock_reservations`, `cash_sessions`, `cash_movements`, `journal_entries`, `journal_lines`

Mencatat pergerakan stok, reservasi bahan, kas masuk/keluar, serta jurnal keuangan jika modul akuntansi sudah diaktifkan.

### Sinkronisasi dan audit

`sync_outbox`, `sync_cursors`, `sync_conflicts`, `audit_logs`, `devices`

Menyimpan event yang belum tersinkron, posisi sinkronisasi, konflik, catatan audit, dan identitas perangkat.

Prinsip desain database:

- Gunakan UUID atau ID global yang unik untuk data yang dibuat di perangkat berbeda.
- Simpan `outlet_id`, `device_id`, waktu pembuatan, waktu perubahan, dan status sinkronisasi pada entitas yang relevan.
- Harga transaksi harus disalin ke `order_items` ketika pesanan dikonfirmasi. Perubahan harga menu berikutnya tidak boleh mengubah tagihan lama.
- Gunakan transaksi database untuk perubahan stok dan status pesanan yang harus konsisten.
- Simpan riwayat pergerakan stok, bukan hanya angka stok terakhir.
- Untuk data keuangan yang sudah final, gunakan pembatalan atau transaksi koreksi yang tercatat, bukan menghapus riwayat secara langsung.

## 4. Alur transaksi dari scan QR sampai selesai

1. Pelanggan scan QR meja

   QR berisi tautan HTTPS dengan token meja yang tidak mudah ditebak. Server memvalidasi outlet, meja, dan apakah pemesanan sedang diizinkan.
2. Pelanggan memilih menu

   Menu menampilkan harga, ukuran, topping, ketersediaan, dan catatan khusus. Keranjang disimpan sementara pada perangkat pelanggan.
3. Server memvalidasi pesanan

   FastAPI memeriksa ulang harga, diskon, ketersediaan, batas jumlah, serta status meja. Total dihitung server, bukan dipercaya dari HP pelanggan.
4. Pesanan dicatat secara atomik

   Server membuat `order_id`, menyimpan detail barang, dan mencatat event pesanan. Pengiriman ulang permintaan yang sama tidak boleh membuat pesanan kedua.
5. Kasir dan dapur menerima pesanan

   Kasir melihat tagihan; dapur atau barista menerima tiket sesuai stasiun produksi. Gunakan WebSocket untuk pembaruan cepat, dengan polling sebagai cadangan.
6. Pelanggan membayar

   Pembayaran dapat dilakukan di kasir dengan tunai, melalui QRIS dinamis, atau transfer yang diverifikasi sesuai kebijakan toko. Status pembayaran dicatat terpisah dari status produksi.
7. Transaksi selesai dan tersinkron

   Sistem mengunci hasil transaksi final, mencatat stok serta kas yang relevan, membuat struk, dan memasukkan event yang diperlukan ke antrean sinkronisasi cloud.

### Contoh status pesanan dan pembayaran

Jangan menggunakan satu status untuk semua proses.

| Jenis status | Contoh                                                              |
| ------------ | ------------------------------------------------------------------- |
| Pesanan      | `pending`, `confirmed`, `cancelled`                                 |
| Produksi     | `queued`, `preparing`, `ready`, `served`                            |
| Pembayaran   | `unpaid`, `pending`, `partially_paid`, `paid`, `failed`, `refunded` |
| Sinkronisasi | `local_only`, `sync_pending`, `synced`, `sync_error`                |

Dengan pemisahan ini, pesanan dapat mulai diproses ketika pembayaran masih menunggu, jika kebijakan kafe memang mengizinkannya. Kasir tetap bisa melihat bahwa pembayaran belum lunas.

### Catatan penting untuk QRIS

QR Code meja bukan QRIS. Keduanya memiliki fungsi berbeda.

- QR meja: mengidentifikasi meja dan membuka menu pemesanan.
- QRIS dinamis: merepresentasikan tagihan pembayaran tertentu melalui penyedia pembayaran.
- Konfirmasi pembayaran: gunakan callback/webhook yang tervalidasi atau mekanisme verifikasi resmi penyedia. Jangan menganggap pelanggan sudah membayar hanya karena menekan tombol “Saya sudah bayar”.
- Tunai dan transfer: tetap memiliki pencatatan pembayaran yang konsisten dengan transaksi QRIS.

Jika internet terputus, transaksi tunai dapat tetap diproses di server lokal. QRIS dan transfer online tidak boleh dianggap berhasil tanpa konfirmasi yang sah. Untuk QRIS dinamis, ikuti aturan penyedia mengenai masa berlaku tagihan dan status pembayaran.

## 5. Sinkronisasi lokal ke cloud

Ini bagian paling penting agar transaksi tidak hilang atau terduplikasi.

Transaksi disimpan di database lokal

Transaksi lokal tetap berjalan tanpa internet

`sync_outbox` mencatat event

Contoh: order.created, payment.confirmed, stock.changed

Worker sinkronisasi mengirim event

Retry, ID event unik, autentikasi perangkat, dan acknowledgment server

Cloud menyimpan dan mengakui event

Event yang sudah diterima tidak diproses ulang sebagai transaksi baru

### Aturan sinkronisasi yang disarankan

1. Local-first untuk operasional: pesanan dan pembayaran tunai yang disahkan lokal tetap bisa disimpan ketika offline.
2. Idempotensi: setiap event dan perintah transaksi memiliki ID unik. Server menyimpan kunci yang sudah diproses agar retry aman.
3. Transactional outbox: event sinkronisasi dicatat dalam transaksi database yang sama dengan perubahan bisnis. Ini mencegah transaksi tersimpan tetapi event-nya hilang.
4. Konflik tidak boleh diselesaikan dengan menimpa data begitu saja. Perubahan harga, pembayaran, stok, dan transaksi final memerlukan aturan berbeda.
5. Cloud bukan sumber kebenaran tunggal untuk transaksi yang dibuat ketika outlet offline. Event lokal yang sudah sah harus tetap dapat direkonsiliasi ketika koneksi pulih.
6. Status koneksi terlihat di UI: misalnya “Lokal aktif”, “Sinkronisasi tertunda”, atau “Semua data tersinkron”.

Untuk versi pertama, gunakan satu server lokal sebagai otoritas transaksi outlet. Jangan izinkan beberapa perangkat membuat transaksi final secara independen lalu menggabungkannya tanpa aturan. Ini jauh lebih mudah dijaga konsistensinya.

### Bagaimana jika server lokal mati?

Aplikasi kasir tidak boleh menganggap database lokal di setiap HP sebagai database bersama. Jika server lokal mati, perangkat lain tidak otomatis dapat membaca transaksi terbaru.

Rencana pemulihan awal:

- Simpan backup database lokal secara terjadwal.
- Jalankan FastAPI sebagai layanan yang bisa dimulai ulang.
- Simpan transaksi yang memang dibuat offline di perangkat dengan ID unik dan antrean lokal.
- Tentukan prosedur pemulihan server serta rekonsiliasi sebelum mengaktifkan transaksi offline multi-perangkat.

Fitur transaksi mandiri di setiap perangkat adalah tahap lanjutan karena memerlukan penanganan konflik stok, pembayaran, dan transaksi ganda yang lebih rumit.

## 6. Struktur folder tanpa merusak proyek lama

Untuk proyek yang saat ini berada di `E:\POS\KASIR`, pertahankan struktur Flutter, backend FastAPI, serta database SQLite yang sudah ada. Struktur berikut adalah target penataan secara bertahap, bukan instruksi untuk memindahkan atau mengganti semua folder sekarang.

E:\POS\KASIR\\

mobile/

Proyek Flutter yang sudah ada; sesuaikan dengan lokasi sebenarnya

backend/

FastAPI dan modul layanan bisnis

data/

SQLite lokal dan salinan database pengembangan

web_ordering/

Web menu pelanggan dan halaman status pesanan

docs/

Dokumentasi API, skema database, dan aturan bisnis

scripts/

Backup, migrasi, pemeriksaan kesehatan, dan deployment

tests/

Tes transaksi, pembayaran, QR ordering, dan sinkronisasi

Di dalam backend, modul baru dapat dibagi seperti berikut:

```
backend/
  app/
    api/
      routes/
        menu.py
        tables.py
        orders.py
        payments.py
        kitchen.py
        sync.py
    models/
    schemas/
    repositories/
    services/
      ordering_service.py
      payment_service.py
      inventory_service.py
      sync_service.py
    integrations/
      qris_provider.py
    database.py
    main.py
  tests/
```

Jangan membuat file-file ini secara massal sebelum struktur FastAPI yang aktif diperiksa. Jika proyek sudah memiliki `routers`, `models`, `schemas`, atau `services`, gunakan struktur yang ada dan tambahkan hanya yang belum tersedia.

Untuk Flutter, pertahankan modul login, billing, database lokal, dan repository yang sudah ada. Tambahkan halaman serta layanan QR ordering secara terpisah. Hindari menulis ulang autentikasi dan konfigurasi lisensi hanya demi fitur baru.

## 7. Tahapan implementasi

Saya menyarankan tujuh tahap, dengan setiap tahap memiliki hasil yang bisa diuji sebelum berlanjut.

Tahap 1 — Audit proyek dan database

Prioritas pertama

- Temukan entry point Flutter dan FastAPI yang benar-benar digunakan.
- Periksa tabel SQLite, foreign key, repository, dan migrasi yang tersedia.
- Identifikasi transaksi, produk, stok, pembayaran, lisensi, dan autentikasi yang sudah berfungsi.
- Buat salinan database untuk pengembangan dan backup sebelum perubahan skema.

Hasil: peta kode lama dan daftar perubahan minimal.

Tahap 2 — Fondasi menu kafe

Tambahkan kategori menu, varian, meja, ketersediaan, serta konfigurasi dine-in. Pastikan harga dan stok divalidasi backend. Uji tanpa cloud terlebih dahulu.

Tahap 3 — QR ordering MVP

Buat QR untuk tiap meja, halaman menu responsif, keranjang, pengiriman pesanan, dan tampilan pesanan masuk di kasir. Fokus pada satu outlet dan satu server lokal.

Tahap 4 — Dapur dan pembayaran

Tambahkan KDS, antrean barista, status produksi, pembayaran tunai dan transfer, lalu integrasi QRIS dinamis. Uji callback, tagihan kedaluwarsa, dan pembayaran ganda.

Tahap 5 — Sinkronisasi cloud

Tambahkan outbox, retry, idempotensi, rekonsiliasi konflik, backup cloud, serta tampilan status sinkronisasi. Mulai dari sinkronisasi satu arah yang terkontrol sebelum membuka perubahan dua arah.

Tahap 6 — Keamanan dan pengujian

Uji isolasi outlet, otorisasi kasir, validasi harga, akses QR, pembayaran palsu, pemutusan internet, pemulihan database, dan transaksi ganda.

Tahap 7 — Deployment dan ekspansi

Jalankan FastAPI sebagai layanan lokal, buat installer desktop, konfigurasi jaringan kafe, lalu aktifkan dashboard cloud, multi-outlet, dan migrasi PostgreSQL sesuai kebutuhan.

## 8. Pengujian wajib sebelum digunakan di kafe

| Skenario                                | Hasil yang diharapkan                                  |
| --------------------------------------- | ------------------------------------------------------ |
| Scan QR meja A                          | Menu terbuka dengan identitas meja yang benar          |
| Pelanggan mengirim pesanan dua kali     | Tidak tercipta pesanan ganda dari permintaan yang sama |
| Harga berubah ketika menu terbuka       | Server memakai harga sah saat pesanan dikonfirmasi     |
| Internet terputus                       | Kasir lokal dan transaksi tunai tetap berjalan         |
| Pembayaran QRIS belum dikonfirmasi      | Transaksi tidak ditandai lunas                         |
| Server lokal restart                    | Data yang telah disimpan tetap tersedia                |
| Internet tersambung kembali             | Event tertunda tersinkron tanpa menggandakan transaksi |
| Dua kasir memesan stok terakhir         | Stok tidak terjual melebihi aturan yang ditetapkan     |
| Pelanggan mencoba mengakses meja lain   | Akses dibatasi sesuai kebijakan keamanan               |
| Pembayaran dibatalkan atau dikembalikan | Riwayat transaksi dan keuangan tetap dapat diaudit     |

## 9. Keputusan teknis yang saya rekomendasikan

- Flutter: tetap untuk aplikasi kasir Windows dan Android.
- QR ordering: web responsif agar pelanggan tidak perlu menginstal aplikasi.
- FastAPI lokal: pusat transaksi untuk seluruh perangkat di outlet.
- SQLite: pertahankan database yang sudah ada untuk tahap awal.
- PostgreSQL cloud: gunakan untuk data terpusat dan sinkronisasi.
- QRIS: gunakan integrasi penyedia resmi dengan verifikasi pembayaran.
- Sinkronisasi: gunakan transactional outbox, ID unik, dan retry yang idempoten.
- Pengembangan: tambah modul bertahap dengan migrasi database yang dapat diuji dan dibatalkan.

Satu batasan arsitektur perlu ditegaskan: sistem ini dapat tetap beroperasi secara lokal ketika internet mati, tetapi pembayaran elektronik online, akses cloud, dan sinkronisasi jarak jauh bergantung pada koneksi atau mekanisme penyedia masing-masing.

## 10. Langkah berikutnya: audit kode lama

Sebelum membuat modul baru, langkah yang paling aman adalah memetakan struktur proyek aktual dan skema database agar rancangan ini bisa disesuaikan dengan implementasi yang sudah ada.

## Konfigurasi awal implementasi

Pilih kondisi proyek saat ini. Ini membantu menentukan langkah audit dan migrasi yang paling aman.

Backend FastAPI

Sudah berjalan dan digunakan aplikasi Flutter

Sudah ada, tetapi beberapa endpoint belum selesai

Belum yakin backend mana yang aktif

Database operasional

SQLite yang sudah ada

Sudah menggunakan PostgreSQL lokal

SQLite lokal dan database cloud sudah tersedia

Web menu pelanggan

Belum ada, perlu dibuat sebagai modul baru

Ingin memakai Flutter Web

Sudah ada halaman web pemesanan

Lanjutkan ke audit proyek

Setelah kondisi proyek teridentifikasi, urutan implementasi pertama yang paling masuk akal adalah QR meja → menu → keranjang → pesanan masuk ke kasir lokal. Integrasi QRIS dan sinkronisasi cloud menyusul setelah alur transaksi lokal terbukti konsisten. Dengan cara ini, kita bisa menguji fitur baru tanpa mempertaruhkan fungsi kasir yang sudah berjalan.&#x20;