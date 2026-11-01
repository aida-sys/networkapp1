import 'dart:math';

import 'package:drift/drift.dart';

import '../data/local_database.dart';
import '../domain/pos_repository_contract.dart';
import '../remote/pos_api_client.dart';

/// Implementasi repository yang memakai POS LAN API sebagai sumber data.
///
/// Aturan yang dijaga:
/// - Tidak ada penulisan ke database lokal.
/// - Tidak ada fallback diam-diam saat server mati: operasi gagal dengan pesan
///   yang jelas (`PosApiUnavailableException`).
/// - Harga dan stok selalu dihitung server; klien hanya menampilkan.
///
/// `mapper` adalah instance database lokal yang dipakai HANYA untuk membangun
/// `QueryRow` dari JSON (type mapping Drift), bukan sebagai sumber data.
class RemotePosRepository implements PosRepositoryContract {
  RemotePosRepository({required this.client, required this.mapper, this.onToken});

  final PosApiClient client;
  final KasirinDatabase mapper;

  /// Dipanggil setelah login berhasil supaya token bisa disimpan perangkat.
  final Future<void> Function(String token)? onToken;

  QueryRow _row(Map<String, dynamic> data) => QueryRow(data, mapper);

  List<QueryRow> _rows(List<Map<String, dynamic>> data) =>
      data.map(_row).toList(growable: false);

  // --- Setup & auth ----------------------------------------------------

  /// Mode LAN tidak punya konsep "setup owner di perangkat ini".
  /// Owner dibuat sekali di server pusat.
  @override
  Future<bool> setupRequired() async => false;

  @override
  Future<int> createOwner({
    required String username,
    required String fullName,
    required String password,
    String? storeName,
  }) async {
    throw StateError(
      'Pembuatan owner dilakukan sekali di server pusat, bukan dari perangkat. '
      'Hubungi admin toko.',
    );
  }

  @override
  Future<void> seedDemoData(int ownerId) async {
    throw StateError('Data demo hanya tersedia di mode standalone.');
  }

  @override
  Future<QueryRow> login(String username, String password) async {
    final payload = await client.login(username, password);
    final token = client.accessToken;
    if (token != null && token.isNotEmpty && onToken != null) {
      await onToken!(token);
    }
    final user = (payload['user'] as Map).cast<String, dynamic>();
    return _row({
      'id': user['id'],
      'username': user['username'],
      'full_name': user['full_name'],
      'role_name': user['role'],
      'is_active': user['is_active'] == true ? 1 : 0,
      'must_change_password': user['must_change_password'] == true ? 1 : 0,
    });
  }

  // --- Shift -----------------------------------------------------------

  @override
  Future<QueryRow?> openShiftFor(int cashierId) async {
    final shift = await client.currentShift();
    return shift == null ? null : _row(shift);
  }

  @override
  Future<int?> openShift({
    required int cashierId,
    required int openingCash,
  }) async {
    final shift = await client.openShift(openingCash);
    return shift['id'] as int?;
  }

  @override
  Future<void> closeShift({
    required int shiftId,
    required int cashierId,
    required int closingCash,
  }) async {
    await client.closeShift(closingCash);
  }

  @override
  Future<List<QueryRow>> getShiftHistory({int limit = 30}) async {
    return _rows(await client.shiftHistory(limit: limit));
  }

  // --- Katalog ---------------------------------------------------------

  @override
  Future<List<QueryRow>> products({String search = ''}) async {
    final data = await client.products(search: search);
    return _rows(
      data
          .map(
            (item) => {
              ...item,
              // Nama kolom disamakan dengan query lokal supaya view tidak
              // perlu tahu sumber datanya.
              'category_name': item['category_name'],
            },
          )
          .toList(),
    );
  }

  @override
  Future<int> unitPriceFor(int productId, int quantity) async {
    final payload = await client.productPrice(productId, quantity);
    return (payload['unit_price'] as num).toInt();
  }

  @override
  Future<int> createProduct({
    required String sku,
    required String name,
    required int purchasePrice,
    required int sellingPrice,
    required int initialStock,
    required int minimumStock,
    int? supplierId,
    String? barcode,
  }) async {
    final categories = await client.categories();
    final units = await client.units();
    if (categories.isEmpty || units.isEmpty) {
      throw StateError(
        'Kategori atau satuan belum tersedia di server. '
        'Lengkapi master data di server terlebih dahulu.',
      );
    }
    final created = await client.createProduct({
      'sku': sku,
      'name': name,
      'barcode': barcode ?? '',
      'category_id': categories.first['id'],
      'unit_id': units.first['id'],
      'purchase_price': purchasePrice,
      'selling_price': sellingPrice,
      'stock_qty': initialStock,
      'min_stock': minimumStock,
      'is_active': true,
      'supplier_id': ?supplierId,
    });
    return created['id'] as int;
  }

  @override
  Future<void> deleteProduct(int productId) async {
    await client.deleteProduct(productId);
  }

  // --- Harga khusus ----------------------------------------------------

  /// Aturan harga grosir dikelola di server. Endpoint daftar aturan belum
  /// diekspos di v1, jadi mode LAN menampilkan daftar kosong alih-alih
  /// menampilkan data lokal yang bisa menyesatkan.
  @override
  Future<List<QueryRow>> getSpecialPriceRules() async => const [];

  @override
  Future<void> saveSpecialPriceRule({
    int? ruleId,
    required int productId,
    required int quantityThreshold,
    required int specialPrice,
    int multipleQuantityThreshold = 0,
    int? multipleSpecialPrice,
  }) async {
    throw StateError(
      'Pengaturan harga khusus belum tersedia di mode LAN. '
      'Atur dari komputer server.',
    );
  }

  @override
  Future<void> deleteSpecialPriceRule(int ruleId) async {
    throw StateError(
      'Pengaturan harga khusus belum tersedia di mode LAN. '
      'Atur dari komputer server.',
    );
  }

  // --- Supplier & pembelian --------------------------------------------

  @override
  Future<List<QueryRow>> getSuppliers() async {
    return _rows(await client.suppliers());
  }

  @override
  Future<int> createSupplier({
    required String name,
    String? phone,
    String? address,
  }) async {
    throw StateError(
      'Tambah supplier dilakukan di komputer server pada mode LAN.',
    );
  }

  @override
  Future<void> updateSupplier({
    required int supplierId,
    required String name,
    String? phone,
    String? address,
  }) async {
    throw StateError(
      'Ubah supplier dilakukan di komputer server pada mode LAN.',
    );
  }

  @override
  Future<List<QueryRow>> getPurchaseOrders() async {
    return _rows(await client.purchases());
  }

  @override
  Future<int> completePurchase({
    int? supplierId,
    String? newSupplierName,
    int? productId,
    String? newProductName,
    int? newProductSellingPrice,
    int newProductMinimumStock = 5,
    required int quantity,
    required int unitCost,
    required int actorId,
    required String paymentType,
    int downPaymentAmount = 0,
  }) async {
    if (supplierId == null || productId == null) {
      throw StateError(
        'Pembelian di mode LAN memakai supplier dan produk yang sudah ada di '
        'server. Tambahkan data baru dari komputer server.',
      );
    }
    final result = await client.createPurchase(
      {
        'supplier_id': supplierId,
        'product_id': productId,
        'quantity': quantity,
        'unit_cost': unitCost,
        'payment_status': paymentType,
        'dp_amount': downPaymentAmount,
      },
      idempotencyKey: _newKey(),
    );
    return result['id'] as int;
  }

  @override
  Future<void> receivePurchaseOrder({
    required int orderId,
    required int actorId,
  }) async {
    // Di server, pencatatan pembelian langsung menerima barang (satu
    // transaksi). Jadi tidak ada langkah terpisah di mode LAN.
    throw StateError(
      'Penerimaan barang tercatat otomatis saat pembelian dibuat di mode LAN.',
    );
  }

  @override
  Future<int> payPurchaseOrder({
    required int orderId,
    required int amount,
    required int actorId,
  }) async {
    throw StateError(
      'Pembayaran hutang pembelian dilakukan di komputer server pada mode LAN.',
    );
  }

  // --- Laporan ---------------------------------------------------------

  @override
  Future<List<QueryRow>> getStockReport() async {
    final data = await client.products(includeInactive: false);
    return _rows(
      data
          .map(
            (item) => {
              'id': item['id'],
              'sku': item['sku'],
              'name': item['name'],
              'stock_qty': item['stock_qty'],
              'min_stock': item['min_stock'],
              'purchase_price': item['purchase_price'],
              'selling_price': item['selling_price'],
            },
          )
          .toList(),
    );
  }

  @override
  Future<Map<String, dynamic>> getFinancialReport() async {
    final report = await client.dailyReport();
    return {
      'sales_total': report['sales_total'] ?? 0,
      'sales_count': report['sales_count'] ?? 0,
      'profit_total': report['profit_total'] ?? 0,
      'cashier_breakdown': report['cashier_breakdown'] ?? const [],
    };
  }

  @override
  Future<Map<String, dynamic>> getDashboardStats() async {
    final report = await client.dailyReport();
    final products = await client.products();
    final lowStock = products
        .where(
          (item) =>
              (item['stock_qty'] as num? ?? 0) <= (item['min_stock'] as num? ?? 0),
        )
        .length;
    return {
      'product_count': products.length,
      'today_sales_total': report['sales_total'] ?? 0,
      'today_sales_count': report['sales_count'] ?? 0,
      'low_stock_count': lowStock,
    };
  }

  @override
  Future<List<QueryRow>> getRecentSales({int limit = 10}) async {
    final data = await client.sales();
    return _rows(data.take(limit).toList());
  }

  // --- Pengguna --------------------------------------------------------

  @override
  Future<List<QueryRow>> getUsers() async {
    throw StateError(
      'Manajemen pengguna dilakukan di komputer server pada mode LAN.',
    );
  }

  @override
  Future<int> addUser({
    required String username,
    required String fullName,
    required String password,
    required String role,
    String? whatsapp,
  }) async {
    throw StateError(
      'Tambah pengguna dilakukan di komputer server pada mode LAN.',
    );
  }

  @override
  Future<void> updateUser({
    required int userId,
    required String username,
    required String fullName,
    required String role,
    String? whatsapp,
    String? newPassword,
  }) async {
    throw StateError(
      'Ubah pengguna dilakukan di komputer server pada mode LAN.',
    );
  }

  @override
  Future<void> setUserActive({
    required int userId,
    required int actorId,
    required bool active,
  }) async {
    throw StateError(
      'Status pengguna diatur di komputer server pada mode LAN.',
    );
  }

  @override
  Future<void> deleteUser({required int userId, required int actorId}) async {
    throw StateError(
      'Hapus pengguna dilakukan di komputer server pada mode LAN.',
    );
  }

  // --- Toko ------------------------------------------------------------

  @override
  Future<QueryRow?> getStore() async {
    final store = await client.store();
    return store == null ? null : _row(store);
  }

  @override
  Future<void> updateStore({
    required String name,
    String? slogan,
    String? address,
    String? whatsapp,
    String? logoPath,
    String? bannerPath,
  }) async {
    await client.updateStore({
      'name': name,
      'address': address ?? '',
      'whatsapp': whatsapp ?? '',
      'slogan': slogan ?? '',
    });
  }

  @override
  Future<void> updateOwnerName({
    required int userId,
    required String fullName,
  }) async {
    throw StateError(
      'Nama pengguna diubah di komputer server pada mode LAN.',
    );
  }

  // --- Pengaturan pembayaran -------------------------------------------

  /// Pengaturan pembayaran (termasuk kredensial QRIS) tetap milik perangkat
  /// ini, bukan data produk, jadi tetap dibaca dari database lokal.
  @override
  Future<Map<String, bool>> getPaymentSettings() async {
    final row = await mapper
        .customSelect('SELECT * FROM payment_settings ORDER BY id LIMIT 1')
        .getSingleOrNull();
    return {
      'cash': row?.read<int>('cash_enabled') != 0,
      'qrisDana': row?.read<int>('qris_dana_enabled') == 1,
      'qrisMidtrans': row?.read<int>('qris_midtrans_enabled') == 1,
      'transfer': row?.read<int>('transfer_enabled') == 1,
    };
  }

  @override
  Future<void> savePaymentSettings(Map<String, bool> settings) async {
    if (settings.values.every((enabled) => !enabled)) {
      throw StateError('Aktifkan minimal satu metode pembayaran.');
    }
    final now = DateTime.now().toUtc().toIso8601String();
    final existing = await mapper
        .customSelect('SELECT id FROM payment_settings ORDER BY id LIMIT 1')
        .getSingleOrNull();
    if (existing == null) {
      await mapper.customStatement(
        'INSERT INTO payment_settings(cash_enabled, qris_dana_enabled, '
        'qris_midtrans_enabled, transfer_enabled, created_at, updated_at) '
        'VALUES (?, ?, ?, ?, ?, ?)',
        [
          settings['cash'] == true ? 1 : 0,
          settings['qrisDana'] == true ? 1 : 0,
          settings['qrisMidtrans'] == true ? 1 : 0,
          settings['transfer'] == true ? 1 : 0,
          now,
          now,
        ],
      );
      return;
    }
    await mapper.customStatement(
      'UPDATE payment_settings SET cash_enabled = ?, qris_dana_enabled = ?, '
      'qris_midtrans_enabled = ?, transfer_enabled = ?, updated_at = ? '
      'WHERE id = ?',
      [
        settings['cash'] == true ? 1 : 0,
        settings['qrisDana'] == true ? 1 : 0,
        settings['qrisMidtrans'] == true ? 1 : 0,
        settings['transfer'] == true ? 1 : 0,
        now,
        existing.read<int>('id'),
      ],
    );
  }

  // --- Checkout --------------------------------------------------------

  @override
  Future<CheckoutResult> checkout({
    required String invoiceNo,
    required int cashierId,
    required int shiftId,
    required List<CartItemInput> items,
    required String paymentMethod,
    required int paymentAmount,
  }) async {
    if (items.isEmpty) {
      throw StateError('Keranjang penjualan masih kosong.');
    }
    if (paymentAmount < 0) {
      throw StateError('Nominal pembayaran tidak valid.');
    }

    // Nomor invoice lokal dipakai sebagai kunci idempotency: retry dengan
    // invoice yang sama tidak akan membuat transaksi kedua di server.
    final sale = await client.checkout(
      idempotencyKey: invoiceNo,
      items: [
        for (final item in items)
          {'product_id': item.productId, 'qty': item.quantity},
      ],
      payments: [
        {'method': paymentMethod, 'amount': paymentAmount},
      ],
    );

    final total = (sale['grand_total'] as num? ?? 0).toInt();
    return CheckoutResult(
      saleId: (sale['id'] as num).toInt(),
      invoiceNo: (sale['invoice_no'] ?? invoiceNo) as String,
      total: total,
      change: max(0, paymentAmount - total),
      wasExisting: false,
    );
  }

  String _newKey() {
    final random = Random.secure();
    final bytes = List<int>.generate(16, (_) => random.nextInt(256));
    return bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
  }
}
