# Blueprint Layout, UI Components, & Content Copy: Applications & Store Management System

Dokumen ini berisi arsitektur visual, sistem komponen UI terpadu, struktur routing, serta **seluruh draf teks/konten (copywriting)** yang telah disesuaikan dengan produk aplikasi kasir dan manajemen toko dari **Anjay Software Solution** ("Solusi Digital Anda").

## 1. Identitas Perusahaan & Brand Tokens

* **Nama Perusahaan:** Anjay Software Solution
* **Brand Tagline / Slogan:** Solusi Digital Anda
* **Kontak Utama (WhatsApp):** 0878542117 (Direct WA Link: `https://wa.me/62878542117`)

## 2. Tech Stack & Dependensi yang Direkomendasikan

* **Framework Frontend:** Next.js (App Router, TypeScript)
* **Styling & CSS:** Tailwind CSS
* **UI Components Base:** Shadcn UI / Radix UI (Modal, Accordion, Dropdown, Toggle)
* **Iconography:** Lucide React / React Icons
* **Animation:** Framer Motion
* **Forms & Validation:** React Hook Form + Zod
* **Carousel / Slider:** Swiper.js / Embla Carousel

## 3. Design System & UI Tokens

### Warna (Color Palette)

* **Primary Brand:** `#0F172A` (Slate Dark) / `#2563EB` (Royal Blue) — Tombol utama, badge aktif, link highlight.
* **Accent Color:** `#10B981` (Emerald Green) — Indikator status online/cloud, WhatsApp CTA icon.
* **Neutral Light Background:** `#F8FAFC` — Background section bergantian.
* **Neutral Surface:** `#FFFFFF` — Surface card, modal, header.
* **Text Main:** `#0F172A` — Heading & Teks Utama.
* **Text Muted:** `#64748B` — Subtitle, meta text, placeholder.

## 4. Structural Peta Routing (Route Map)

```
/ (Home / Landing Page)
│
├── /produk (Overview Produk & Jenis Aplikasi)
│   ├── /produk/stand-alone         (Aplikasi Offline Single Device)
│   ├── /produk/jaringan-lokal      (Aplikasi Multi-Kasir LAN/Offline Local)
│   └── /produk/full-cloud          (Aplikasi Cloud Multi-Cabang & Remote Monitoring)
│
├── /fitur (Fitur Sistem Manajemen Toko)
│   ├── /fitur/penjualan-kasir      (Jendela Kasir & Transaksi Harian)
│   ├── /fitur/manajemen-stok       (Inventory & Multi-Gudang)
│   ├── /fitur/pembelian-pengeluaran(Manajemen Supplier & Biaya Operasional)
│   └── /fitur/pembayaran-fleksibel (Multipayment: QRIS, E-Wallet, Kartu, Tunai)
│
├── /solusi (Solusi Jenis Usaha)
│   ├── /solusi/retail-minimarket
│   ├── /solusi/restoran-kafe
│   └── /solusi/grosir-distribusi
│
├── /harga                          (Paket Langganan & Beli Putus)
├── /tentang-kami                   (Profil Perusahaan Anjay Software Solution)
├── /blog                           (Edukasi Bisnis & Retail)
├── /bantuan                        (Panduan Penggunaan & FAQ)
├── /kontak                         (Hubungi Tim Sales Anjay Software Solution)
└── /jadwal-demo                    (Form Pemesanan Demo Software)
```

## 5. Isi Konten Website Lengkap (Content Copywriting)

### A. Global Navigation Header

* **Brand Logo:** Anjay Software Solution
* **Tagline Display:** Solusi Digital Anda
* **Menu Navigation:**
  * **Produk & Arsitektur:** Stand Alone | Jaringan Lokal | Full Cloud
  * **Fitur Utama:** Penjualan Kasir | Manajemen Stok | Pembelian & Pengeluaran | Pembayaran Fleksibel
  * **Solusi Bisnis:** Retail & Toko | Restoran & Kafe | Grosir & Multi-Cabang
  * **Harga & Paket**
  * **Bantuan & Blog**
* **Right CTA Buttons:**
  * `Secondary (WA Callout)`: "Chat WA: 0878542117"
  * `Primary`: "Coba Demo Gratis"

### B. Halaman Beranda (`/`)

#### 1. Hero Section

* **Badge/Tag Top:** "Anjay Software Solution — Solusi Digital Anda"
* **Headline:** "Aplikasi Kasir & Sistem Manajemen Toko Terlengkap untuk Pertumbuhan Bisnis Anda"
* **Sub-headline:** "Kelola penjualan harian, pantau stok barang real-time, catat pembelian & pengeluaran, serta terima berbagai jenis pembayaran secara fleksibel. Solusi digital tepercaya dalam pilihan sistem Stand Alone, Jaringan Lokal, hingga Full Cloud."
* **CTA Button Group:**
  * `Primary`: "Jadwalkan Demo Gratis"
  * `Secondary (WhatsApp)`: "Konsultasi via WA (0878542117)"
* **Hero Visual:** Mockup antarmuka POS Kasir Anjay Software Solution di Layar Monitor/Tablet dengan dashboard analitik cloud di background.

#### 2. Section Jenis Aplikasi (Architecture Options)

* **Section Title:** "3 Pilihan Arsitektur Sistem Sesuai Kebutuhan Usaha Anda"
* **Section Subtitle:** "Anjay Software Solution menghadirkan fleksibilitas infrastruktur yang dapat disesuaikan dengan skala dan kendala operasional toko Anda."
* **Grid 3 Kolom:**
  1. **Aplikasi Stand Alone (Offline Mode)**
     * *Deskripsi:* "Bekerja 100% tanpa jaringan internet. Sangat stabil, cepat, dan data tersimpan langsung di komputer/perangkat kasir Anda. Bebas hambatan saat internet mati."
     * *Cocok Untuk:* Toko tunggal, UMKM, atau area dengan koneksi internet terbatas.
  2. **Aplikasi Jaringan Lokal (LAN Mode)**
     * *Deskripsi:* "Hubungkan beberapa komputer kasir dan bagian gudang dalam satu lokasi toko menggunakan jaringan lokal tanpa tergantung internet eksternal."
     * *Cocok Untuk:* Minimarket, supermarket, atau toko dengan banyak mesin kasir dalam satu lokasi.
  3. **Aplikasi Full Cloud (Remote & Multi-Cabang)**
     * *Deskripsi:* "Database aman terjamin di server cloud. Pemilik toko dapat memantau laporan penjualan, stok, dan kasir secara real-time dari jarak jauh kapan saja."
     * *Cocok Untuk:* Bisnis franchise, usaha multi-cabang, dan pemilik bisnis dengan mobilitas tinggi.

#### 3. Section Fitur Utama Manajemen Toko

* **Section Title:** "Fitur Lengkap Kendalikan Seluruh Operasional Toko"
* **Grid 4 Card:**
  1. **Jendela Kasir & Penjualan Harian**
     * Transaksi kasir cepat dengan antarmuka intuitif.
     * Disediakan tombol pintas barcode, diskon produk, dan cetak struk/nota digital.
  2. **Manajemen Stok Barang**
     * Monitoring stok masuk-keluar secara akurat.
     * Sistem peringatan stok menipis (*low stock alert*) dan manajemen varian barang.
  3. **Pembelian & Pengeluaran**
     * Pencatatan order pembelian (*Purchase Order*) ke supplier.
     * Rekap operasional dan pengeluaran harian toko agar arus kas (*cashflow*) tetap sehat.
  4. **Sistem Pembayaran Fleksibel**
     * Menerima pembayaran Tunai, QRIS, E-Wallet, Kartu Kredit/Debit, hingga Pembayaran Piutang/Tempo.

#### 4. Section Pemantauan Jarak Jauh (Cloud Monitoring Showcase)

* **Headline:** "Pantau Banyak Cabang Langsung dari Smartphone Anda"
* **Deskripsi Teks:** "Bersama Anjay Software Solution, pemilik bisnis multi-cabang mendapatkan jaminan keamanan data server dan dasbor pemantauan jarak jauh. Akses rekap penjualan harian, kontrol margin keuntungan, dan performa kasir tanpa harus hadir di lokasi toko."
* **Visual:** Dashboard grafik penjualan interaktif di perangkat tablet dan smartphone.

#### 5. Section Form Demo & Kontak

* **Form Header:** "Siap Meningkatkan Efisiensi Operasional Toko Anda bersama Anjay Software Solution?"
* **Sub-header:** "Hubungi Tim Sales kami di WhatsApp **0878542117** atau isi formulir di bawah ini untuk mendapatkan akun demo gratis."
* **Form Inputs:**
  * Nama Lengkap
  * No. WhatsApp / HP
  * Nama Toko / Bisnis
  * Pilih Jenis Sistem (Stand Alone / Jaringan Lokal / Full Cloud)
  * Jumlah Cabang Toko
* **Button:** "Kirim & Dapatkan Akun Demo"

### C. Detail Halaman Produk & Fitur

#### 1. Halaman Aplikasi Stand Alone (`/produk/stand-alone`)

* **Hero Headline:** "Solusi Kasir Stand Alone: Cepat, Mandiri, dan Tanpa Kuota Internet"
* **Keunggulan Utama:**
  * Tanpa biaya langganan bulanan (Pilihan Beli Putus / Lifetime).
  * Kecepatan transaksi maksimal tanpa delay koneksi.
  * Backup data lokal yang mudah dan mandiri.

#### 2. Halaman Aplikasi Jaringan Lokal (`/produk/jaringan-lokal`)

* **Hero Headline:** "Sistem Kasir Jaringan Lokal: Sinkronisasi Multi-Kasir Tanpa Internet"
* **Keunggulan Utama:**
  * Menghubungkan Kasir Utama, Kasir Tambahan, dan Gudang dalam 1 LAN.
  * Pembagian beban kerja toko skala menengah-besar secara efisien.
  * Server lokal mandiri dengan performa tinggi.

#### 3. Halaman Aplikasi Full Cloud (`/produk/full-cloud`)

* **Hero Headline:** "Aplikasi Kasir Full Cloud: Kontrol Penuh Toko & Multi-Cabang Dari Mana Saja"
* **Keunggulan Utama:**
  * Database terenkripsi dan otomatis ter-backup di server cloud terjamin.
  * Laporan konsolidasi otomatis untuk semua cabang toko.
  * Akses dasbor pemilik bisnis real-time dari HP / Laptop.

### D. Halaman Harga (`/harga`)

* **Hero Headline:** "Pilih Paket Aplikasi Kasir Sesuai Skala Bisnis Anda"
* **Tabel Komparasi Paket:**

| Fitur | Stand Alone | Jaringan Lokal | Full Cloud | 
| ----- | ----- | ----- | ----- | 
| **Tipe Lisensi** | Per Perangkat / Lifetime | Per Toko (Local Server) | Langganan (Bulanan/Tahunan) | 
| **Penjualan Kasir Harian** | Ya | Ya | Ya | 
| **Manajemen Stok** | Ya | Ya (Multi-Gudang) | Ya (Real-time Multi-Cabang) | 
| **Pembelian & Pengeluaran** | Ya | Ya | Ya | 
| **Pantauan Jarak Jauh (HP)** | Tidak | Tidak | **Ya (Real-time)** | 
| **Koneksi Internet** | Tidak Perlu | Hanya LAN | Wajib Internet | 
| **Dukungan Support Anjay** | Garansi & Panduan Lokal | Bantuan Setup LAN | Full Support Cloud 24/7 |
| **Cocok Untuk** | Toko Tunggal | Minimarket / Toko Besar | Franchise / Multi-Cabang | 

### E. Global Footer

* **Kolom 1:** 
  * **Brand Title:** Anjay Software Solution
  * **Slogan:** Solusi Digital Anda
  * **Deskripsi:** "Penyedia aplikasi kasir dan sistem manajemen toko terlengkap. Menghadirkan efisiensi transaksi, kerapihan stok, dan kemudahan kontrol operasional usaha Anda."
* **Kolom 2 (Jenis Aplikasi):** Stand Alone | Jaringan Lokal | Full Cloud
* **Kolom 3 (Fitur Sistem):** Penjualan Kasir | Manajemen Stok | Pembelian & Pengeluaran | Opsi Pembayaran
* **Kolom 4 (Hubungi Kami):** 
  * WhatsApp Direct: **0878542117**
  * Layanan Support: Senin - Sabtu (08.00 - 17.00 WIB)
  * Pusat Bantuan & FAQ
* **Bottom Bar:** © 2026 **Anjay Software Solution** (Solusi Digital Anda). All rights reserved.
```

Dokumen blueprint kini telah memuat identitas perusahaan Anda secara konsisten di seluruh bagian layout dan copy. Apakah ada bagian lain yang ingin ditambahkan atau disesuaikan?