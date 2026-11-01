import 'dart:math';

import 'package:drift/drift.dart';
import 'package:sqlite3/common.dart' show SqliteException;

import '../data/local_database.dart';
import 'password_hasher.dart';
import 'pos_repository_contract.dart';

// `CartItemInput` dan `CheckoutResult` didefinisikan di kontrak supaya kedua
// implementasi (lokal dan LAN) memakai tipe yang sama. Re-export di sini
// menjaga semua import lama tetap bekerja tanpa perubahan.
export 'pos_repository_contract.dart'
    show CartItemInput, CheckoutResult, PosRepositoryContract;

class PosRepository implements PosRepositoryContract {
  PosRepository(this.database, this.passwordHasher);

  final KasirinDatabase database;
  final PasswordHasher passwordHasher;

  Future<void> _statement(String sql, List<Variable<Object>> variables) =>
      database.customStatement(
        sql,
        variables.map((variable) => variable.value).toList(),
      );

  @override
  Future<bool> setupRequired() async =>
      await database
          .customSelect('SELECT id FROM users LIMIT 1')
          .getSingleOrNull() ==
      null;

  @override
  Future<int> createOwner({
    required String username,
    required String fullName,
    required String password,
    String? storeName,
  }) async {
    final normalizedUsername = username.trim();
    final normalizedName = fullName.trim();
    if (normalizedUsername.isEmpty || normalizedUsername.length > 80) {
      throw StateError('Username wajib diisi dan maksimal 80 karakter.');
    }
    if (normalizedName.isEmpty || normalizedName.length > 150) {
      throw StateError('Nama lengkap wajib diisi dan maksimal 150 karakter.');
    }
    if (password.length < 8) {
      throw StateError('Password minimal 8 karakter.');
    }
    final normalizedStoreName = storeName?.trim();
    if (normalizedStoreName != null &&
        (normalizedStoreName.isEmpty || normalizedStoreName.length > 150)) {
      throw StateError('Nama toko wajib diisi dan maksimal 150 karakter.');
    }
    final hash = await passwordHasher.hash(password);
    return database.transaction(() async {
      final existing = await database
          .customSelect('SELECT id FROM users LIMIT 1')
          .getSingleOrNull();
      if (existing != null) throw StateError('Akun OWNER sudah pernah dibuat.');
      final now = _now();
      for (final role in const ['OWNER', 'ADMIN', 'SUPERVISOR', 'CASHIER']) {
        await _statement(
          'INSERT OR IGNORE INTO roles(name, description, created_at, updated_at) VALUES (?, ?, ?, ?)',
          [
            Variable.withString(role),
            Variable.withString('Role $role'),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      final roleRow = await database
          .customSelect("SELECT id FROM roles WHERE name = 'OWNER'")
          .getSingle();
      try {
        await _statement(
          'INSERT INTO users(username, full_name, password_hash, role_id, is_active, failed_login_count, must_change_password, created_at, updated_at) VALUES (?, ?, ?, ?, 1, 0, 0, ?, ?)',
          [
            Variable.withString(normalizedUsername),
            Variable.withString(normalizedName),
            Variable.withString(hash),
            Variable.withInt(roleRow.read<int>('id')),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      } on SqliteException catch (error) {
        throw StateError(
          error.message.contains('UNIQUE')
              ? 'Username sudah digunakan.'
              : 'Akun OWNER tidak dapat dibuat.',
        );
      }
      if (normalizedStoreName != null) {
        await _statement(
          'INSERT INTO stores(code, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
          [
            Variable.withString('MAIN'),
            Variable.withString(normalizedStoreName),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      final user = await database
          .customSelect(
            'SELECT id FROM users WHERE username = ?',
            variables: [Variable.withString(normalizedUsername)],
          )
          .getSingle();
      return user.read<int>('id');
    });
  }

  /// Adds a small, clearly marked data set to this device's local database.
  /// Safe to call more than once: the demo SKU is used as the seed marker.
  @override
  Future<void> seedDemoData(int ownerId) async {
    final marker = await database
        .customSelect("SELECT id FROM products WHERE sku = 'DEMO-BRS-001'")
        .getSingleOrNull();
    if (marker != null) return;

    final now = _now();
    const categoryNames = [
      'Sembako',
      'Minuman',
      'Makanan Instan',
      'Perawatan Rumah',
    ];
    const units = [('Piece', 'pcs'), ('Pack', 'pack'), ('Liter', 'L')];
    const suppliers = [
      ('DEMO-SUP-01', 'Supplier Sembako Demo', '0812-0000-1001'),
      ('DEMO-SUP-02', 'Distributor Minuman Demo', '0812-0000-1002'),
    ];
    const products = [
      (
        'DEMO-BRS-001',
        'Beras Premium 5 kg',
        '2000000001001',
        'Sembako',
        'Pack',
        'DEMO-SUP-01',
        65000,
        72000,
        20,
        3,
      ),
      (
        'DEMO-GUL-001',
        'Gula Pasir 1 kg',
        '2000000001002',
        'Sembako',
        'Piece',
        'DEMO-SUP-01',
        15500,
        18000,
        18,
        4,
      ),
      (
        'DEMO-MNY-001',
        'Minyak Goreng 1 L',
        '2000000001003',
        'Sembako',
        'Liter',
        'DEMO-SUP-01',
        16500,
        19000,
        16,
        4,
      ),
      (
        'DEMO-MIE-001',
        'Mi Instan Goreng',
        '2000000001004',
        'Makanan Instan',
        'Piece',
        'DEMO-SUP-01',
        2500,
        3500,
        30,
        6,
      ),
      (
        'DEMO-AIR-001',
        'Air Mineral 600 ml',
        '2000000001005',
        'Minuman',
        'Piece',
        'DEMO-SUP-02',
        2500,
        4000,
        24,
        5,
      ),
      (
        'DEMO-TEH-001',
        'Teh Celup 25 kantong',
        '2000000001006',
        'Minuman',
        'Pack',
        'DEMO-SUP-02',
        8500,
        11000,
        12,
        3,
      ),
      (
        'DEMO-SAB-001',
        'Sabun Mandi',
        '2000000001007',
        'Perawatan Rumah',
        'Piece',
        'DEMO-SUP-01',
        3500,
        5000,
        2,
        5,
      ),
      (
        'DEMO-LOW-001',
        'Stok Rendah Demo',
        '2000000001008',
        'Makanan Instan',
        'Piece',
        'DEMO-SUP-01',
        9000,
        12000,
        1,
        5,
      ),
    ];

    await database.transaction(() async {
      for (final name in categoryNames) {
        await _statement(
          'INSERT OR IGNORE INTO categories(name, created_at, updated_at) VALUES (?, ?, ?)',
          [
            Variable.withString(name),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      for (final unit in units) {
        await _statement(
          'INSERT OR IGNORE INTO units(name, symbol, created_at, updated_at) VALUES (?, ?, ?, ?)',
          [
            Variable.withString(unit.$1),
            Variable.withString(unit.$2),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      for (final supplier in suppliers) {
        await _statement(
          'INSERT OR IGNORE INTO suppliers(code, name, phone, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
          [
            Variable.withString(supplier.$1),
            Variable.withString(supplier.$2),
            Variable.withString(supplier.$3),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      for (final product in products) {
        final category = await database
            .customSelect(
              'SELECT id FROM categories WHERE name = ?',
              variables: [Variable.withString(product.$4)],
            )
            .getSingle();
        final unit = await database
            .customSelect(
              'SELECT id FROM units WHERE name = ?',
              variables: [Variable.withString(product.$5)],
            )
            .getSingle();
        final supplier = await database
            .customSelect(
              'SELECT id FROM suppliers WHERE code = ?',
              variables: [Variable.withString(product.$6)],
            )
            .getSingle();
        await _statement(
          '''INSERT INTO products(sku, barcode, name, category_id, unit_id, supplier_id,
               purchase_price, selling_price, stock_qty, min_stock, is_active, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)''',
          [
            Variable.withString(product.$1),
            Variable.withString(product.$3),
            Variable.withString(product.$2),
            Variable.withInt(category.read<int>('id')),
            Variable.withInt(unit.read<int>('id')),
            Variable.withInt(supplier.read<int>('id')),
            Variable.withInt(product.$7),
            Variable.withInt(product.$8),
            Variable.withInt(product.$9),
            Variable.withInt(product.$10),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
        final productId =
            (await database
                    .customSelect('SELECT last_insert_rowid() AS id')
                    .getSingle())
                .read<int>('id');
        if (product.$9 > 0) {
          await _statement(
            '''INSERT INTO stock_movements(product_id, movement_type, stock_before, qty,
                 stock_after, reference_type, reference_id, note, created_at, updated_at)
               VALUES (?, 'INITIAL_STOCK', 0, ?, ?, 'PRODUCT', ?, 'Stok awal data demo.', ?, ?)''',
            [
              Variable.withInt(productId),
              Variable.withInt(product.$9),
              Variable.withInt(product.$9),
              Variable.withInt(productId),
              Variable.withString(now),
              Variable.withString(now),
            ],
          );
        }
      }

      final rice = await database
          .customSelect("SELECT id FROM products WHERE sku = 'DEMO-BRS-001'")
          .getSingle();
      final riceId = rice.read<int>('id');
      await _statement(
        '''INSERT INTO bulk_price_rules(product_id, quantity_threshold, discount_percent,
             special_price, pricing_mode, created_at, updated_at)
           VALUES (?, 5, 5, 68000, 'PRICE', ?, ?)''',
        [
          Variable.withInt(riceId),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );

      final cashierRole = await database
          .customSelect("SELECT id FROM roles WHERE name = 'CASHIER'")
          .getSingle();
      final cashierHash = await passwordHasher.hash('kasir123');
      await _statement(
        '''INSERT OR IGNORE INTO users(username, full_name, password_hash, role_id,
             is_active, failed_login_count, must_change_password, created_at, updated_at)
           VALUES ('kasir_demo', 'Kasir Demo', ?, ?, 1, 0, 0, ?, ?)''',
        [
          Variable.withString(cashierHash),
          Variable.withInt(cashierRole.read<int>('id')),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final cashier = await database
          .customSelect("SELECT id FROM users WHERE username = 'kasir_demo'")
          .getSingle();
      final cashierId = cashier.read<int>('id');

      final supplier = await database
          .customSelect("SELECT id FROM suppliers WHERE code = 'DEMO-SUP-01'")
          .getSingle();
      final milk = await database
          .customSelect("SELECT id FROM products WHERE sku = 'DEMO-MNY-001'")
          .getSingle();
      final receivedOrder = await createPurchaseOrder(
        supplierId: supplier.read<int>('id'),
        productId: milk.read<int>('id'),
        quantity: 10,
        unitCost: 16500,
        actorId: ownerId,
        dueDate: DateTime.now()
            .add(const Duration(days: 14))
            .toIso8601String()
            .substring(0, 10),
        notes: 'Pembelian contoh: sudah diterima',
      );
      await receivePurchaseOrder(orderId: receivedOrder, actorId: ownerId);
      await createPurchaseOrder(
        supplierId: supplier.read<int>('id'),
        productId: riceId,
        quantity: 5,
        unitCost: 65000,
        actorId: ownerId,
        dueDate: DateTime.now()
            .add(const Duration(days: 14))
            .toIso8601String()
            .substring(0, 10),
        notes: 'Pembelian contoh: draft untuk dicoba',
      );

      final shiftId = await openShift(
        cashierId: cashierId,
        openingCash: 500000,
      );
      if (shiftId == null) throw StateError('Shift demo tidak dapat dibuat.');
      final saleSkus = [
        ('DEMO-MIE-001', 3),
        ('DEMO-BRS-001', 1),
        ('DEMO-AIR-001', 2),
        ('DEMO-GUL-001', 1),
      ];
      for (var i = 0; i < saleSkus.length; i++) {
        final product = await database
            .customSelect(
              'SELECT id FROM products WHERE sku = ?',
              variables: [Variable.withString(saleSkus[i].$1)],
            )
            .getSingle();
        await checkout(
          invoiceNo: 'DEMO-${DateTime.now().toUtc().millisecondsSinceEpoch}-$i',
          cashierId: cashierId,
          shiftId: shiftId,
          items: [
            CartItemInput(
              productId: product.read<int>('id'),
              quantity: saleSkus[i].$2,
            ),
          ],
          paymentMethod: 'CASH',
          paymentAmount: 1000000,
        );
      }
    });
  }

  @override
  Future<QueryRow> login(String username, String password) async {
    final normalizedUsername = username.trim();
    final row = await database
        .customSelect(
          '''SELECT users.*, roles.name AS role_name
         FROM users JOIN roles ON roles.id = users.role_id
         WHERE users.username = ? AND users.deleted_at IS NULL''',
          variables: [Variable.withString(normalizedUsername)],
        )
        .getSingleOrNull();
    if (row == null || row.read<int>('is_active') != 1) {
      throw StateError('Username atau password salah.');
    }
    final lockedUntil = DateTime.tryParse(
      row.read<String?>('locked_until') ?? '',
    );
    if (lockedUntil != null && lockedUntil.isAfter(DateTime.now().toUtc())) {
      throw StateError('Akun sedang terkunci.');
    }
    final valid = await passwordHasher.verify(
      password,
      row.read<String>('password_hash'),
    );
    final now = _now();
    if (!valid) {
      final attempts = row.read<int>('failed_login_count') + 1;
      final lock = attempts >= 5
          ? DateTime.now()
                .toUtc()
                .add(const Duration(minutes: 15))
                .toIso8601String()
          : null;
      await _statement(
        'UPDATE users SET failed_login_count = ?, locked_until = ?, updated_at = ? WHERE id = ?',
        [
          Variable.withInt(attempts),
          Variable<String>(lock),
          Variable.withString(now),
          Variable.withInt(row.read<int>('id')),
        ],
      );
      throw StateError('Username atau password salah.');
    }
    await database.transaction(() async {
      await _statement(
        'UPDATE users SET failed_login_count = 0, locked_until = NULL, last_login_at = ?, updated_at = ? WHERE id = ?',
        [
          Variable.withString(now),
          Variable.withString(now),
          Variable.withInt(row.read<int>('id')),
        ],
      );
      await _statement(
        'INSERT INTO login_history(user_id, login_at) VALUES (?, ?)',
        [Variable.withInt(row.read<int>('id')), Variable.withString(now)],
      );
    });
    return row;
  }

  Future<int> createStore(String name) async {
    final normalizedName = name.trim();
    if (normalizedName.isEmpty || normalizedName.length > 150) {
      throw StateError('Nama toko wajib diisi dan maksimal 150 karakter.');
    }
    final now = _now();
    await _statement(
      'INSERT INTO stores(code, name, created_at, updated_at) VALUES (?, ?, ?, ?)',
      [
        Variable.withString('MAIN'),
        Variable.withString(normalizedName),
        Variable.withString(now),
        Variable.withString(now),
      ],
    );
    return (await database
            .customSelect('SELECT last_insert_rowid() AS id')
            .getSingle())
        .read<int>('id');
  }

  @override
  Future<QueryRow?> openShiftFor(int cashierId) async => database
      .customSelect(
        "SELECT * FROM shifts WHERE cashier_id = ? AND status = 'OPEN' AND closed_at IS NULL ORDER BY id DESC LIMIT 1",
        variables: [Variable.withInt(cashierId)],
      )
      .getSingleOrNull();

  @override
  Future<int> unitPriceFor(int productId, int quantity) async {
    if (quantity <= 0) throw StateError('Qty harus lebih dari 0.');
    final product = await database
        .customSelect(
          'SELECT selling_price FROM products WHERE id = ? AND deleted_at IS NULL AND is_active = 1',
          variables: [Variable.withInt(productId)],
        )
        .getSingleOrNull();
    if (product == null) throw StateError('Produk tidak ditemukan.');
    return _unitPrice(product.read<int>('selling_price'), productId, quantity);
  }

  @override
  Future<List<QueryRow>> products({String search = ''}) => database
      .customSelect(
        '''SELECT products.*, categories.name AS category_name
           FROM products LEFT JOIN categories ON categories.id = products.category_id
           WHERE products.deleted_at IS NULL AND products.is_active = 1
             AND (? = '' OR products.name LIKE ? OR products.sku LIKE ? OR products.barcode LIKE ?)
           ORDER BY products.name, products.sku''',
        variables: [
          Variable.withString(search.trim()),
          Variable.withString('%${search.trim()}%'),
          Variable.withString('%${search.trim()}%'),
          Variable.withString('%${search.trim()}%'),
        ],
      )
      .get();

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
    if (sku.trim().isEmpty || sku.trim().length > 80) {
      throw StateError('SKU wajib diisi dan maksimal 80 karakter.');
    }
    if (name.trim().isEmpty || name.trim().length > 200) {
      throw StateError('Nama produk wajib diisi dan maksimal 200 karakter.');
    }
    if ([
      purchasePrice,
      sellingPrice,
      initialStock,
      minimumStock,
    ].any((value) => value < 0)) {
      throw StateError('Harga dan stok tidak boleh bernilai negatif.');
    }
    final now = _now();
    return database.transaction(() async {
      final result = await database
          .customSelect(
            "SELECT id FROM categories WHERE lower(name) = 'umum' AND deleted_at IS NULL",
          )
          .getSingleOrNull();
      var categoryId = result?.read<int>('id');
      if (categoryId == null) {
        await _statement(
          'INSERT INTO categories(name, created_at, updated_at) VALUES (?, ?, ?)',
          [
            Variable.withString('Umum'),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
        categoryId =
            (await database
                    .customSelect('SELECT last_insert_rowid() AS id')
                    .getSingle())
                .read<int>('id');
      }
      await _statement(
        '''INSERT INTO products(sku, barcode, name, category_id, supplier_id,
             purchase_price, selling_price, stock_qty, min_stock, is_active,
             created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)''',
        [
          Variable.withString(sku.trim()),
          Variable<String>(
            barcode?.trim().isEmpty ?? true ? null : barcode!.trim(),
          ),
          Variable.withString(name.trim()),
          Variable.withInt(categoryId),
          Variable<int>(supplierId),
          Variable.withInt(purchasePrice),
          Variable.withInt(sellingPrice),
          Variable.withInt(initialStock),
          Variable.withInt(minimumStock),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final productId =
          (await database
                  .customSelect('SELECT last_insert_rowid() AS id')
                  .getSingle())
              .read<int>('id');
      if (initialStock > 0) {
        await _statement(
          '''INSERT INTO stock_movements(product_id, movement_type, stock_before, qty, stock_after, reference_type, reference_id, note, created_at, updated_at)
             VALUES (?, 'INITIAL_STOCK', 0, ?, ?, 'PRODUCT', ?, 'Stok awal saat membuat produk.', ?, ?)''',
          [
            Variable.withInt(productId),
            Variable.withInt(initialStock),
            Variable.withInt(initialStock),
            Variable.withInt(productId),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      return productId;
    });
  }

  @override
  Future<List<QueryRow>> getSpecialPriceRules() => database.customSelect(
    '''SELECT bulk_price_rules.*, products.name AS product_name,
              products.sku AS product_sku, products.selling_price AS regular_price
       FROM bulk_price_rules
       JOIN products ON products.id = bulk_price_rules.product_id
       WHERE products.deleted_at IS NULL AND products.is_active = 1
         AND bulk_price_rules.pricing_mode = 'PRICE'
       ORDER BY products.name, bulk_price_rules.quantity_threshold''',
  ).get();

  @override
  Future<void> saveSpecialPriceRule({
    int? ruleId,
    required int productId,
    required int quantityThreshold,
    required int specialPrice,
    int multipleQuantityThreshold = 0,
    int? multipleSpecialPrice,
  }) async {
    if (quantityThreshold < 1) {
      throw StateError('Jumlah minimum harus minimal 1.');
    }
    if (multipleSpecialPrice != null &&
        multipleQuantityThreshold <= quantityThreshold) {
      throw StateError(
        'Jumlah tingkat harga ketiga harus lebih besar dari tingkat kedua.',
      );
    }
    if (specialPrice <= 0) {
      throw StateError('Harga spesial harus lebih dari 0.');
    }
    if (multipleSpecialPrice != null && multipleSpecialPrice <= 0) {
      throw StateError('Harga spesial kelipatan harus lebih dari 0.');
    }

    final product = await database
        .customSelect(
          'SELECT selling_price FROM products WHERE id = ? AND deleted_at IS NULL AND is_active = 1',
          variables: [Variable.withInt(productId)],
        )
        .getSingleOrNull();
    if (product == null) throw StateError('Produk tidak ditemukan.');
    if (specialPrice > product.read<int>('selling_price')) {
      throw StateError('Harga spesial tidak boleh melebihi harga normal.');
    }
    if (multipleSpecialPrice != null &&
        multipleSpecialPrice > product.read<int>('selling_price')) {
      throw StateError(
        'Harga spesial kelipatan tidak boleh melebihi harga normal.',
      );
    }

    final now = _now();
    final basePrice = product.read<int>('selling_price');
    final discountPercent = basePrice <= 0
        ? 100.0
        : ((basePrice - specialPrice) * 100 / basePrice).clamp(0.01, 100.0);
    try {
      if (ruleId == null) {
        await _statement(
          '''INSERT INTO bulk_price_rules(
               product_id, quantity_threshold, discount_percent, special_price,
               quantity_multiplier, multiple_special_price, multiple_quantity_threshold, pricing_mode,
               created_at, updated_at
             ) VALUES (?, ?, ?, ?, 2, ?, ?, 'PRICE', ?, ?)''',
          [
            Variable.withInt(productId),
            Variable.withInt(quantityThreshold),
            Variable.withReal(discountPercent),
            Variable.withInt(specialPrice),
            Variable.withInt(multipleSpecialPrice ?? 0),
            Variable.withInt(multipleQuantityThreshold),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      } else {
        await _statement(
          '''UPDATE bulk_price_rules
             SET product_id = ?, quantity_threshold = ?, discount_percent = ?,
                 special_price = ?, quantity_multiplier = 2,
                 multiple_special_price = ?, multiple_quantity_threshold = ?,
                 pricing_mode = 'PRICE', updated_at = ?
             WHERE id = ?''',
          [
            Variable.withInt(productId),
            Variable.withInt(quantityThreshold),
            Variable.withReal(discountPercent),
            Variable.withInt(specialPrice),
            Variable.withInt(multipleSpecialPrice ?? 0),
            Variable.withInt(multipleQuantityThreshold),
            Variable.withString(now),
            Variable.withInt(ruleId),
          ],
        );
      }
    } on SqliteException catch (error) {
      if (error.message.contains('UNIQUE')) {
        throw StateError(
          'Produk ini sudah memiliki aturan pada jumlah tersebut.',
        );
      }
      rethrow;
    }
  }

  @override
  Future<void> deleteSpecialPriceRule(int ruleId) => _statement(
    'DELETE FROM bulk_price_rules WHERE id = ?',
    [Variable.withInt(ruleId)],
  );

  @override
  Future<List<QueryRow>> getSuppliers() => database
      .customSelect(
        'SELECT * FROM suppliers WHERE deleted_at IS NULL ORDER BY name',
      )
      .get();

  @override
  Future<int> createSupplier({
    required String name,
    String? phone,
    String? address,
  }) async {
    final normalizedName = name.trim();
    if (normalizedName.isEmpty) throw StateError('Nama supplier wajib diisi.');
    final now = _now();
    final code = 'SUP-${DateTime.now().toUtc().microsecondsSinceEpoch}';
    await _statement(
      '''INSERT INTO suppliers(code, name, phone, address, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)''',
      [
        Variable.withString(code),
        Variable.withString(normalizedName),
        Variable<String>(phone?.trim().isEmpty ?? true ? null : phone!.trim()),
        Variable<String>(
          address?.trim().isEmpty ?? true ? null : address!.trim(),
        ),
        Variable.withString(now),
        Variable.withString(now),
      ],
    );
    return (await database
            .customSelect('SELECT last_insert_rowid() AS id')
            .getSingle())
        .read<int>('id');
  }

  @override
  Future<void> updateSupplier({
    required int supplierId,
    required String name,
    String? phone,
    String? address,
  }) async {
    final normalizedName = name.trim();
    if (normalizedName.isEmpty) throw StateError('Nama supplier wajib diisi.');
    final existing = await database
        .customSelect(
          'SELECT id FROM suppliers WHERE id = ? AND deleted_at IS NULL',
          variables: [Variable.withInt(supplierId)],
        )
        .getSingleOrNull();
    if (existing == null) throw StateError('Supplier tidak ditemukan.');
    await _statement(
      '''UPDATE suppliers SET name = ?, phone = ?, address = ?, updated_at = ?
         WHERE id = ?''',
      [
        Variable.withString(normalizedName),
        Variable<String>(phone?.trim().isEmpty ?? true ? null : phone!.trim()),
        Variable<String>(
          address?.trim().isEmpty ?? true ? null : address!.trim(),
        ),
        Variable.withString(_now()),
        Variable.withInt(supplierId),
      ],
    );
  }

  @override
  Future<List<QueryRow>> getPurchaseOrders() => database.customSelect(
    '''SELECT purchase_orders.*, suppliers.name AS supplier_name,
              suppliers.phone AS supplier_phone, users.full_name AS creator_name,
              (SELECT group_concat(products.name || ' × ' || purchase_order_items.ordered_qty, ', ')
                 FROM purchase_order_items
                 JOIN products ON products.id = purchase_order_items.product_id
                WHERE purchase_order_items.purchase_order_id = purchase_orders.id) AS item_summary
       FROM purchase_orders
       JOIN suppliers ON suppliers.id = purchase_orders.supplier_id
       JOIN users ON users.id = purchase_orders.created_by
       ORDER BY purchase_orders.id DESC''',
  ).get();

  Future<void> _postJournalPair({
    required String now,
    required String sourceType,
    required int sourceId,
    required String memo,
    required int actorId,
    required int debitAccountId,
    required int creditAccountId,
    required int amount,
    required String debitDescription,
    required String creditDescription,
  }) async {
    if (amount <= 0) return;
    await _statement(
      '''INSERT INTO journal_entries(
           entry_date, source_type, source_id, memo, posted_by, created_at, updated_at
         ) VALUES (?, ?, ?, ?, ?, ?, ?)''',
      [
        Variable.withString(now.substring(0, 10)),
        Variable.withString(sourceType),
        Variable.withInt(sourceId),
        Variable.withString(memo),
        Variable.withInt(actorId),
        Variable.withString(now),
        Variable.withString(now),
      ],
    );
    final journalId =
        (await database
                .customSelect('SELECT last_insert_rowid() AS id')
                .getSingle())
            .read<int>('id');
    for (final line in [
      (
        accountId: debitAccountId,
        debit: amount,
        credit: 0,
        description: debitDescription,
      ),
      (
        accountId: creditAccountId,
        debit: 0,
        credit: amount,
        description: creditDescription,
      ),
    ]) {
      await _statement(
        '''INSERT INTO journal_lines(
             journal_entry_id, account_id, debit, credit, description, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?, ?)''',
        [
          Variable.withInt(journalId),
          Variable.withInt(line.accountId),
          Variable.withInt(line.debit),
          Variable.withInt(line.credit),
          Variable.withString(line.description),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
    }
  }

  Future<int> createPurchaseOrder({
    required int supplierId,
    required int productId,
    required int quantity,
    required int unitCost,
    required int actorId,
    required String dueDate,
    String? notes,
  }) async {
    if (quantity < 1) throw StateError('Jumlah pembelian minimal 1.');
    if (unitCost <= 0) throw StateError('Harga modal harus lebih dari 0.');
    final store = await getStore();
    if (store == null) {
      throw StateError('Lengkapi profil toko terlebih dahulu.');
    }
    final supplier = await database
        .customSelect(
          'SELECT id FROM suppliers WHERE id = ? AND deleted_at IS NULL',
          variables: [Variable.withInt(supplierId)],
        )
        .getSingleOrNull();
    if (supplier == null) throw StateError('Supplier tidak ditemukan.');
    final product = await database
        .customSelect(
          'SELECT id FROM products WHERE id = ? AND deleted_at IS NULL AND is_active = 1',
          variables: [Variable.withInt(productId)],
        )
        .getSingleOrNull();
    if (product == null) throw StateError('Produk tidak ditemukan.');

    final now = _now();
    final total = quantity * unitCost;
    final orderNo = 'PO-${DateTime.now().toUtc().microsecondsSinceEpoch}';
    return database.transaction(() async {
      await _statement(
        '''INSERT INTO purchase_orders(
             order_no, supplier_id, store_id, created_by, status, ordered_at,
             expected_at, subtotal, payment_status, due_date, paid_amount,
             notes, created_at, updated_at
           ) VALUES (?, ?, ?, ?, 'DRAFT', ?, ?, ?, 'TEMPO', ?, 0, ?, ?, ?)''',
        [
          Variable.withString(orderNo),
          Variable.withInt(supplierId),
          Variable.withInt(store.read<int>('id')),
          Variable.withInt(actorId),
          Variable.withString(now),
          Variable.withString(dueDate),
          Variable.withInt(total),
          Variable.withString(dueDate),
          Variable<String>(
            notes?.trim().isEmpty ?? true ? null : notes!.trim(),
          ),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final orderId =
          (await database
                  .customSelect('SELECT last_insert_rowid() AS id')
                  .getSingle())
              .read<int>('id');
      await _statement(
        '''INSERT INTO purchase_order_items(
             purchase_order_id, product_id, ordered_qty, received_qty,
             unit_cost, created_at, updated_at
           ) VALUES (?, ?, ?, 0, ?, ?, ?)''',
        [
          Variable.withInt(orderId),
          Variable.withInt(productId),
          Variable.withInt(quantity),
          Variable.withInt(unitCost),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      return orderId;
    });
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
    if (quantity < 1) throw StateError('Jumlah pembelian minimal 1.');
    if (unitCost <= 0) throw StateError('Harga modal harus lebih dari 0.');
    if (!const {'CASH', 'TEMPO', 'DP'}.contains(paymentType)) {
      throw StateError('Pilih metode pembayaran yang valid.');
    }
    if (newProductMinimumStock < 0) {
      throw StateError('Stok minimum tidak boleh negatif.');
    }

    return database.transaction(() async {
      final resolvedSupplierId =
          supplierId ?? await createSupplier(name: newSupplierName ?? '');
      final supplier = await database
          .customSelect(
            'SELECT id FROM suppliers WHERE id = ? AND deleted_at IS NULL',
            variables: [Variable.withInt(resolvedSupplierId)],
          )
          .getSingleOrNull();
      if (supplier == null) throw StateError('Supplier tidak ditemukan.');

      late final int resolvedProductId;
      if (productId != null) {
        final product = await database
            .customSelect(
              'SELECT supplier_id FROM products WHERE id = ? AND deleted_at IS NULL AND is_active = 1',
              variables: [Variable.withInt(productId)],
            )
            .getSingleOrNull();
        if (product == null) throw StateError('Produk tidak ditemukan.');
        final currentSupplierId = product.read<int?>('supplier_id');
        if (currentSupplierId != null &&
            currentSupplierId != resolvedSupplierId) {
          throw StateError('Produk ini terdaftar pada supplier lain.');
        }
        if (currentSupplierId == null) {
          await _statement(
            'UPDATE products SET supplier_id = ?, updated_at = ? WHERE id = ?',
            [
              Variable.withInt(resolvedSupplierId),
              Variable.withString(_now()),
              Variable.withInt(productId),
            ],
          );
        }
        resolvedProductId = productId;
      } else {
        final productName = newProductName?.trim() ?? '';
        final sellingPrice = newProductSellingPrice ?? 0;
        if (productName.isEmpty) {
          throw StateError('Nama produk baru wajib diisi.');
        }
        if (sellingPrice <= 0) {
          throw StateError('Harga jual produk baru harus lebih dari 0.');
        }
        resolvedProductId = await createProduct(
          sku: 'BELANJA-${DateTime.now().toUtc().microsecondsSinceEpoch}',
          name: productName,
          purchasePrice: unitCost,
          sellingPrice: sellingPrice,
          initialStock: 0,
          minimumStock: newProductMinimumStock,
          supplierId: resolvedSupplierId,
        );
      }

      final dueDate = DateTime.now()
          .toUtc()
          .add(const Duration(days: 30))
          .toIso8601String()
          .substring(0, 10);
      final orderId = await createPurchaseOrder(
        supplierId: resolvedSupplierId,
        productId: resolvedProductId,
        quantity: quantity,
        unitCost: unitCost,
        actorId: actorId,
        dueDate: dueDate,
      );
      await receivePurchaseOrder(orderId: orderId, actorId: actorId);

      final total = quantity * unitCost;
      final paidAmount = switch (paymentType) {
        'CASH' => total,
        'TEMPO' => 0,
        'DP' => downPaymentAmount,
        _ => 0,
      };
      if (paymentType == 'DP' && (paidAmount <= 0 || paidAmount >= total)) {
        throw StateError(
          'Nominal DP harus lebih dari 0 dan kurang dari total.',
        );
      }
      if (paidAmount > 0) {
        await payPurchaseOrder(
          orderId: orderId,
          amount: paidAmount,
          actorId: actorId,
        );
      }
      return orderId;
    });
  }

  @override
  Future<void> receivePurchaseOrder({
    required int orderId,
    required int actorId,
  }) async {
    await database.transaction(() async {
      final order = await database
          .customSelect(
            'SELECT status, subtotal FROM purchase_orders WHERE id = ?',
            variables: [Variable.withInt(orderId)],
          )
          .getSingleOrNull();
      if (order == null) throw StateError('Pesanan tidak ditemukan.');
      if (order.read<String>('status') != 'DRAFT') {
        throw StateError('Hanya pesanan draft yang dapat diterima.');
      }
      final items = await database
          .customSelect(
            '''SELECT purchase_order_items.*, products.stock_qty
           FROM purchase_order_items
           JOIN products ON products.id = purchase_order_items.product_id
           WHERE purchase_order_id = ?''',
            variables: [Variable.withInt(orderId)],
          )
          .get();
      if (items.isEmpty) throw StateError('Pesanan tidak memiliki produk.');

      final now = _now();
      await _ensureFinancialBaseline(actorId, now);
      for (final item in items) {
        final productId = item.read<int>('product_id');
        final qty = item.read<int>('ordered_qty');
        final before = item.read<int>('stock_qty');
        final after = before + qty;
        await _statement(
          '''UPDATE products SET stock_qty = ?, purchase_price = ?, updated_at = ?
             WHERE id = ?''',
          [
            Variable.withInt(after),
            Variable.withInt(item.read<int>('unit_cost')),
            Variable.withString(now),
            Variable.withInt(productId),
          ],
        );
        await _statement(
          '''UPDATE purchase_order_items SET received_qty = ordered_qty, updated_at = ?
             WHERE id = ?''',
          [Variable.withString(now), Variable.withInt(item.read<int>('id'))],
        );
        await _statement(
          '''INSERT INTO stock_movements(
               product_id, movement_type, stock_before, qty, stock_after,
               reference_type, reference_id, note, created_at, updated_at
             ) VALUES (?, 'PURCHASE', ?, ?, ?, 'PURCHASE_ORDER', ?, ?, ?, ?)''',
          [
            Variable.withInt(productId),
            Variable.withInt(before),
            Variable.withInt(qty),
            Variable.withInt(after),
            Variable.withInt(orderId),
            Variable.withString('Penerimaan pesanan pembelian.'),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      await _statement(
        "UPDATE purchase_orders SET status = 'RECEIVED', updated_at = ? WHERE id = ?",
        [Variable.withString(now), Variable.withInt(orderId)],
      );
      await _postJournalPair(
        now: now,
        sourceType: 'PURCHASE',
        sourceId: orderId,
        memo: 'Penerimaan pesanan pembelian $orderId',
        actorId: actorId,
        debitAccountId: await _accountId('1200'),
        creditAccountId: await _accountId('2000'),
        amount: order.read<int>('subtotal'),
        debitDescription: 'Penambahan persediaan',
        creditDescription: 'Hutang supplier',
      );
      await _statement(
        '''INSERT INTO audit_logs(user_id, action, entity_type, entity_id, detail, created_at, updated_at)
           VALUES (?, 'PURCHASE_RECEIVED', 'PurchaseOrder', ?, 'Stok diterima', ?, ?)''',
        [
          Variable.withInt(actorId),
          Variable.withInt(orderId),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
    });
  }

  @override
  Future<int> payPurchaseOrder({
    required int orderId,
    required int amount,
    required int actorId,
  }) async {
    if (amount <= 0) throw StateError('Nominal pembayaran harus lebih dari 0.');
    final now = _now();
    return database.transaction(() async {
      final order = await database
          .customSelect(
            'SELECT status, subtotal, paid_amount FROM purchase_orders WHERE id = ?',
            variables: [Variable.withInt(orderId)],
          )
          .getSingleOrNull();
      if (order == null) throw StateError('Pesanan tidak ditemukan.');
      if (order.read<String>('status') != 'RECEIVED') {
        throw StateError('Terima barang sebelum mencatat pembayaran supplier.');
      }
      final subtotal = order.read<int>('subtotal');
      final paid = order.read<int>('paid_amount');
      final newPaid = paid + amount;
      if (newPaid > subtotal) {
        throw StateError('Pembayaran melebihi sisa tagihan.');
      }

      await _ensureFinancialBaseline(actorId, now);
      final cashAccountId = await _accountId('1000');
      await _statement(
        '''INSERT INTO financial_payments(
             purchase_order_id, expense_id, account_id, amount, payment_method,
             paid_at, created_by, created_at, updated_at
           ) VALUES (?, NULL, ?, ?, 'CASH', ?, ?, ?, ?)''',
        [
          Variable.withInt(orderId),
          Variable.withInt(cashAccountId),
          Variable.withInt(amount),
          Variable.withString(now),
          Variable.withInt(actorId),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final paymentId =
          (await database
                  .customSelect('SELECT last_insert_rowid() AS id')
                  .getSingle())
              .read<int>('id');
      await _postJournalPair(
        now: now,
        sourceType: 'PURCHASE_PAYMENT',
        sourceId: paymentId,
        memo: 'Pembayaran pesanan pembelian $orderId',
        actorId: actorId,
        debitAccountId: await _accountId('2000'),
        creditAccountId: cashAccountId,
        amount: amount,
        debitDescription: 'Pembayaran hutang supplier',
        creditDescription: 'Pengeluaran kas',
      );
      final status = newPaid == subtotal ? 'PAID' : 'DP';
      await _statement(
        'UPDATE purchase_orders SET paid_amount = ?, payment_status = ?, updated_at = ? WHERE id = ?',
        [
          Variable.withInt(newPaid),
          Variable.withString(status),
          Variable.withString(now),
          Variable.withInt(orderId),
        ],
      );
      return subtotal - newPaid;
    });
  }

  @override
  Future<List<QueryRow>> getStockReport() => database.customSelect(
    '''SELECT id, sku, name, stock_qty, min_stock, purchase_price, selling_price
       FROM products WHERE deleted_at IS NULL AND is_active = 1
       ORDER BY CASE WHEN stock_qty <= min_stock THEN 0 ELSE 1 END, name''',
  ).get();

  @override
  Future<Map<String, dynamic>> getFinancialReport() async {
    final today = DateTime.now().toUtc().toIso8601String().substring(0, 10);
    final period = await database
        .customSelect(
          '''SELECT COALESCE(
               (SELECT substr(created_at, 1, 10) FROM stores
                ORDER BY created_at LIMIT 1),
               (SELECT MIN(entry_date) FROM journal_entries),
               ?
             ) AS period_start''',
          variables: [Variable.withString(today)],
        )
        .getSingle();
    final startDate = period.read<String>('period_start');
    final accounts = await database
        .customSelect(
          '''SELECT accounts.code, accounts.name, accounts.account_type,
                    COALESCE(SUM(journal_lines.debit), 0) AS debit,
                    COALESCE(SUM(journal_lines.credit), 0) AS credit,
                    CASE
                      WHEN accounts.account_type IN ('ASSET', 'EXPENSE')
                        THEN COALESCE(SUM(journal_lines.debit), 0) - COALESCE(SUM(journal_lines.credit), 0)
                      ELSE COALESCE(SUM(journal_lines.credit), 0) - COALESCE(SUM(journal_lines.debit), 0)
                    END AS balance
             FROM accounts
             LEFT JOIN journal_entries
               ON journal_entries.entry_date >= ?
              AND journal_entries.entry_date <= ?
             LEFT JOIN journal_lines
               ON journal_lines.account_id = accounts.id
              AND journal_lines.journal_entry_id = journal_entries.id
             WHERE accounts.is_active = 1
             GROUP BY accounts.id
             ORDER BY accounts.code''',
          variables: [
            Variable.withString(startDate),
            Variable.withString(today),
          ],
        )
        .get();

    int totalFor(String type) => accounts
        .where((account) => account.read<String>('account_type') == type)
        .fold<int>(0, (sum, account) => sum + account.read<int>('balance'));

    final revenue = totalFor('REVENUE');
    final expenses = totalFor('EXPENSE');
    return {
      'startDate': startDate,
      'endDate': today,
      'revenue': revenue,
      'expenses': expenses,
      'netProfit': revenue - expenses,
      'assets': totalFor('ASSET'),
      'liabilities': totalFor('LIABILITY'),
      'equity': totalFor('EQUITY'),
      'accounts': accounts,
    };
  }

  @override
  Future<List<QueryRow>> getShiftHistory({int limit = 30}) => database
      .customSelect(
        '''SELECT shifts.*, users.full_name AS cashier_name,
              COALESCE(SUM(CASE WHEN sales.status = 'PAID' THEN sales.grand_total ELSE 0 END), 0) AS sales_total,
              COUNT(CASE WHEN sales.status = 'PAID' THEN sales.id END) AS sales_count
       FROM shifts
       JOIN users ON users.id = shifts.cashier_id
       LEFT JOIN sales ON sales.shift_id = shifts.id
       GROUP BY shifts.id
       ORDER BY shifts.id DESC LIMIT ?''',
        variables: [Variable.withInt(limit)],
      )
      .get();

  @override
  Future<Map<String, bool>> getPaymentSettings() async {
    final row = await database
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
    final now = _now();
    final row = await database
        .customSelect('SELECT id FROM payment_settings ORDER BY id LIMIT 1')
        .getSingleOrNull();
    final values = [
      Variable.withInt(settings['cash'] == true ? 1 : 0),
      Variable.withInt(settings['qrisDana'] == true ? 1 : 0),
      Variable.withInt(settings['qrisMidtrans'] == true ? 1 : 0),
      Variable.withInt(settings['transfer'] == true ? 1 : 0),
    ];
    if (row == null) {
      await _statement(
        '''INSERT INTO payment_settings(
             cash_enabled, qris_dana_enabled, qris_midtrans_enabled,
             transfer_enabled, created_at, updated_at
           ) VALUES (?, ?, ?, ?, ?, ?)''',
        [...values, Variable.withString(now), Variable.withString(now)],
      );
    } else {
      await _statement(
        '''UPDATE payment_settings SET cash_enabled = ?, qris_dana_enabled = ?,
             qris_midtrans_enabled = ?, transfer_enabled = ?, updated_at = ? WHERE id = ?''',
        [
          ...values,
          Variable.withString(now),
          Variable.withInt(row.read<int>('id')),
        ],
      );
    }
  }

  @override
  Future<int?> openShift({
    required int cashierId,
    required int openingCash,
  }) async {
    if (openingCash < 0) throw StateError('Modal awal tidak boleh negatif.');
    final existing = await database
        .customSelect(
          "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'OPEN' AND closed_at IS NULL",
          variables: [Variable.withInt(cashierId)],
        )
        .getSingleOrNull();
    if (existing != null) return existing.read<int>('id');
    final store = await database
        .customSelect(
          'SELECT id FROM stores WHERE deleted_at IS NULL ORDER BY id LIMIT 1',
        )
        .getSingleOrNull();
    if (store == null) throw StateError('Data toko belum tersedia.');
    final now = _now();
    await _statement(
      '''INSERT INTO shifts(store_id, cashier_id, opened_at, opening_cash, status, created_at, updated_at)
         VALUES (?, ?, ?, ?, 'OPEN', ?, ?)''',
      [
        Variable.withInt(store.read<int>('id')),
        Variable.withInt(cashierId),
        Variable.withString(now),
        Variable.withInt(openingCash),
        Variable.withString(now),
        Variable.withString(now),
      ],
    );
    return (await database
            .customSelect('SELECT last_insert_rowid() AS id')
            .getSingle())
        .read<int>('id');
  }

  @override
  Future<CheckoutResult> checkout({
    required String invoiceNo,
    required int cashierId,
    required int shiftId,
    required List<CartItemInput> items,
    required String paymentMethod,
    required int paymentAmount,
  }) async {
    if (items.isEmpty) throw StateError('Keranjang penjualan masih kosong.');
    if (paymentAmount < 0) throw StateError('Nominal pembayaran tidak valid.');
    return database.transaction(() async {
      final prior = await database
          .customSelect(
            'SELECT id, grand_total FROM sales WHERE invoice_no = ?',
            variables: [Variable.withString(invoiceNo)],
          )
          .getSingleOrNull();
      if (prior != null) {
        final total = prior.read<int>('grand_total');
        return CheckoutResult(
          saleId: prior.read<int>('id'),
          invoiceNo: invoiceNo,
          total: total,
          change: max(0, paymentAmount - total),
          wasExisting: true,
        );
      }
      final shift = await database
          .customSelect(
            "SELECT store_id FROM shifts WHERE id = ? AND cashier_id = ? AND status = 'OPEN' AND closed_at IS NULL",
            variables: [Variable.withInt(shiftId), Variable.withInt(cashierId)],
          )
          .getSingleOrNull();
      if (shift == null) {
        throw StateError('Buka shift sebelum menyelesaikan penjualan.');
      }

      final now = _now();
      final entries =
          <({QueryRow product, int quantity, int unitPrice, int lineTotal})>[];
      var total = 0;
      for (final item in items) {
        if (item.quantity <= 0) throw StateError('Qty harus lebih dari 0.');
        final product = await database
            .customSelect(
              'SELECT * FROM products WHERE id = ? AND deleted_at IS NULL AND is_active = 1',
              variables: [Variable.withInt(item.productId)],
            )
            .getSingleOrNull();
        if (product == null) throw StateError('Produk tidak ditemukan.');
        final stock = product.read<int>('stock_qty');
        if (stock < item.quantity) {
          throw StateError(
            'Stok ${product.read<String>('name')} tidak mencukupi.',
          );
        }
        final unitPrice = await _unitPrice(
          product.read<int>('selling_price'),
          item.productId,
          item.quantity,
        );
        final lineTotal = item.quantity * unitPrice;
        total += lineTotal;
        entries.add((
          product: product,
          quantity: item.quantity,
          unitPrice: unitPrice,
          lineTotal: lineTotal,
        ));
      }
      if (paymentAmount < total) throw StateError('Pembayaran belum lunas.');

      await _ensureFinancialBaseline(cashierId, now);
      await _statement(
        '''INSERT INTO sales(invoice_no, store_id, shift_id, cashier_id, subtotal, discount, tax, grand_total, status, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 0, 0, ?, 'PAID', ?, ?)''',
        [
          Variable.withString(invoiceNo),
          Variable.withInt(shift.read<int>('store_id')),
          Variable.withInt(shiftId),
          Variable.withInt(cashierId),
          Variable.withInt(total),
          Variable.withInt(total),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final saleId =
          (await database
                  .customSelect('SELECT last_insert_rowid() AS id')
                  .getSingle())
              .read<int>('id');
      final lines =
          <({int accountId, int debit, int credit, String description})>[];
      var remainingPayment = total;
      final accountCode = paymentMethod == 'CASH' ? '1000' : '1010';
      final paymentAccount = await _accountId(accountCode);
      lines.add((
        accountId: paymentAccount,
        debit: total,
        credit: 0,
        description: 'Penerimaan penjualan',
      ));
      final salesAccount = await _accountId('4000');
      lines.add((
        accountId: salesAccount,
        debit: 0,
        credit: total,
        description: 'Penjualan',
      ));
      var costTotal = 0;

      for (final entry in entries) {
        final product = entry.product;
        final productId = product.read<int>('id');
        final stockBefore = product.read<int>('stock_qty');
        final purchasePrice = product.read<int>('purchase_price');
        final int? unitCost = purchasePrice > 0 ? purchasePrice : null;
        final stockAfter = stockBefore - entry.quantity;
        final cost = (unitCost ?? 0) * entry.quantity;
        costTotal += cost;
        await _statement(
          '''INSERT INTO sale_items(sale_id, product_id, qty, unit_price, unit_cost, discount, line_total, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)''',
          [
            Variable.withInt(saleId),
            Variable.withInt(productId),
            Variable.withInt(entry.quantity),
            Variable.withInt(entry.unitPrice),
            Variable<int>(unitCost),
            Variable.withInt(entry.lineTotal),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
        await _statement(
          'UPDATE products SET stock_qty = ?, updated_at = ? WHERE id = ?',
          [
            Variable.withInt(stockAfter),
            Variable.withString(now),
            Variable.withInt(productId),
          ],
        );
        await _statement(
          '''INSERT INTO stock_movements(product_id, movement_type, stock_before, qty, stock_after, reference_type, reference_id, created_at, updated_at)
             VALUES (?, 'SALE', ?, ?, ?, 'SALE', ?, ?, ?)''',
          [
            Variable.withInt(productId),
            Variable.withInt(stockBefore),
            Variable.withInt(-entry.quantity),
            Variable.withInt(stockAfter),
            Variable.withInt(saleId),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      await _statement(
        'INSERT INTO payments(sale_id, method, amount, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        [
          Variable.withInt(saleId),
          Variable.withString(paymentMethod),
          Variable.withInt(paymentAmount),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      if (costTotal > 0) {
        final cogs = await _accountId('5000');
        final inventory = await _accountId('1200');
        lines.add((
          accountId: cogs,
          debit: costTotal,
          credit: 0,
          description: 'Harga pokok penjualan',
        ));
        lines.add((
          accountId: inventory,
          debit: 0,
          credit: costTotal,
          description: 'Pengurangan persediaan',
        ));
      }
      remainingPayment -= total;
      if (remainingPayment != 0) {
        throw StateError('Nilai pembayaran tidak menutup total penjualan.');
      }
      final debit = lines.fold<int>(0, (sum, line) => sum + line.debit);
      final credit = lines.fold<int>(0, (sum, line) => sum + line.credit);
      if (debit != credit) throw StateError('Jurnal penjualan tidak seimbang.');
      await _statement(
        '''INSERT INTO journal_entries(entry_date, source_type, source_id, memo, posted_by, created_at, updated_at)
           VALUES (?, 'SALE', ?, ?, ?, ?, ?)''',
        [
          Variable.withString(now.substring(0, 10)),
          Variable.withInt(saleId),
          Variable.withString('Penjualan $invoiceNo'),
          Variable.withInt(cashierId),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final journalId =
          (await database
                  .customSelect('SELECT last_insert_rowid() AS id')
                  .getSingle())
              .read<int>('id');
      for (final line in lines) {
        await _statement(
          '''INSERT INTO journal_lines(journal_entry_id, account_id, debit, credit, description, created_at, updated_at)
             VALUES (?, ?, ?, ?, ?, ?, ?)''',
          [
            Variable.withInt(journalId),
            Variable.withInt(line.accountId),
            Variable.withInt(line.debit),
            Variable.withInt(line.credit),
            Variable.withString(line.description),
            Variable.withString(now),
            Variable.withString(now),
          ],
        );
      }
      await _statement(
        '''INSERT INTO audit_logs(user_id, action, entity_type, entity_id, detail, created_at, updated_at)
           VALUES (?, 'SALE_COMPLETED', 'Sale', ?, ?, ?, ?)''',
        [
          Variable.withInt(cashierId),
          Variable.withInt(saleId),
          Variable.withString('Invoice $invoiceNo; total $total'),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      return CheckoutResult(
        saleId: saleId,
        invoiceNo: invoiceNo,
        total: total,
        change: paymentAmount - total,
        wasExisting: false,
      );
    });
  }

  Future<void> _ensureFinancialBaseline(int actorId, String now) async {
    final settings = await database
        .customSelect(
          'SELECT effective_from FROM financial_settings WHERE id = 1',
        )
        .getSingleOrNull();
    if (settings?.read<String?>('effective_from') == null) {
      await _statement(
        '''INSERT OR REPLACE INTO financial_settings(id, effective_from, initialized_by, initialized_at, created_at, updated_at)
           VALUES (1, ?, ?, ?, ?, ?)''',
        [
          Variable.withString(now.substring(0, 10)),
          Variable.withInt(actorId),
          Variable.withString(now),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
    }
    const accounts = <(String, String, String)>[
      ('1000', 'Kas', 'ASSET'),
      ('1010', 'Bank', 'ASSET'),
      ('1200', 'Persediaan', 'ASSET'),
      ('2000', 'Hutang Usaha', 'LIABILITY'),
      ('3000', 'Modal Pemilik', 'EQUITY'),
      ('3100', 'Saldo Awal', 'EQUITY'),
      ('4000', 'Penjualan', 'REVENUE'),
      ('5000', 'Harga Pokok Penjualan', 'EXPENSE'),
    ];
    for (final account in accounts) {
      await _statement(
        '''INSERT OR IGNORE INTO accounts(code, name, account_type, is_active, is_system, created_at, updated_at)
           VALUES (?, ?, ?, 1, 1, ?, ?)''',
        [
          Variable.withString(account.$1),
          Variable.withString(account.$2),
          Variable.withString(account.$3),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
    }
  }

  Future<int> _accountId(String code) async =>
      (await database
              .customSelect(
                'SELECT id FROM accounts WHERE code = ?',
                variables: [Variable.withString(code)],
              )
              .getSingle())
          .read<int>('id');

  Future<int> _unitPrice(int basePrice, int productId, int quantity) async {
    final rules = await database
        .customSelect(
          '''SELECT quantity_threshold, discount_percent, special_price,
                    quantity_multiplier, multiple_special_price,
                    multiple_quantity_threshold, pricing_mode
         FROM bulk_price_rules WHERE product_id = ? AND quantity_threshold <= ?
         ORDER BY quantity_threshold DESC LIMIT 1''',
          variables: [Variable.withInt(productId), Variable.withInt(quantity)],
        )
        .getSingleOrNull();
    if (rules == null) return basePrice;
    if (rules.read<String>('pricing_mode') == 'PRICE') {
      final multiplePrice = rules.read<int>('multiple_special_price');
      if (multiplePrice > 0 &&
          quantity >= rules.read<int>('multiple_quantity_threshold')) {
        return multiplePrice;
      }
      return rules.read<int>('special_price');
    }
    final percent = rules.read<num>('discount_percent');
    return (basePrice * (100 - percent) / 100).round();
  }

  static String _now() => DateTime.now().toUtc().toIso8601String();

  @override
  Future<void> closeShift({
    required int shiftId,
    required int cashierId,
    required int closingCash,
  }) async {
    if (closingCash < 0) throw StateError('Kas akhir tidak boleh negatif.');
    final now = _now();
    await _statement(
      '''UPDATE shifts SET status = 'CLOSED', closed_at = ?, closing_cash = ?, updated_at = ?
         WHERE id = ? AND cashier_id = ? AND status = 'OPEN' ''',
      [
        Variable.withString(now),
        Variable.withInt(closingCash),
        Variable.withString(now),
        Variable.withInt(shiftId),
        Variable.withInt(cashierId),
      ],
    );
  }

  @override
  Future<List<QueryRow>> getUsers() =>
      database.customSelect('''SELECT users.*, roles.name AS role_name
       FROM users JOIN roles ON roles.id = users.role_id
       WHERE users.deleted_at IS NULL ORDER BY users.id''').get();

  @override
  Future<int> addUser({
    required String username,
    required String fullName,
    required String password,
    required String role,
    String? whatsapp,
  }) async {
    final normalizedUsername = username.trim();
    final normalizedName = fullName.trim();
    if (normalizedUsername.isEmpty || normalizedUsername.length > 80) {
      throw StateError('Username wajib diisi dan maksimal 80 karakter.');
    }
    if (normalizedName.isEmpty || normalizedName.length > 150) {
      throw StateError('Nama lengkap wajib diisi dan maksimal 150 karakter.');
    }
    if (password.length < 8) {
      throw StateError('Kata sandi minimal 8 karakter.');
    }
    if (!const {'CASHIER', 'ADMIN', 'SUPERVISOR'}.contains(role)) {
      throw StateError('Peran pengguna tidak valid.');
    }
    final roleRow = await database
        .customSelect(
          "SELECT id FROM roles WHERE name = ?",
          variables: [Variable.withString(role)],
        )
        .getSingleOrNull();
    if (roleRow == null) throw StateError('Role $role tidak valid.');
    final hash = await passwordHasher.hash(password);
    final now = _now();
    try {
      await _statement(
        '''INSERT INTO users(username, full_name, whatsapp, password_hash, role_id, is_active, failed_login_count, must_change_password, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, 1, 0, 0, ?, ?)''',
        [
          Variable.withString(normalizedUsername),
          Variable.withString(normalizedName),
          Variable<String>(
            whatsapp?.trim().isEmpty ?? true ? null : whatsapp!.trim(),
          ),
          Variable.withString(hash),
          Variable.withInt(roleRow.read<int>('id')),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
      final idRow = await database
          .customSelect('SELECT last_insert_rowid() AS id')
          .getSingle();
      return idRow.read<int>('id');
    } on SqliteException catch (error) {
      throw StateError(
        error.message.contains('UNIQUE')
            ? 'Username sudah digunakan.'
            : 'Gagal menambahkan pengguna.',
      );
    }
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
    final normalizedUsername = username.trim();
    final normalizedName = fullName.trim();
    if (normalizedUsername.isEmpty || normalizedUsername.length > 80) {
      throw StateError('Username wajib diisi dan maksimal 80 karakter.');
    }
    if (normalizedName.isEmpty || normalizedName.length > 150) {
      throw StateError('Nama lengkap wajib diisi dan maksimal 150 karakter.');
    }
    if (!const {'CASHIER', 'ADMIN', 'SUPERVISOR'}.contains(role)) {
      throw StateError('Peran pengguna tidak valid.');
    }
    if (newPassword != null &&
        newPassword.isNotEmpty &&
        newPassword.length < 8) {
      throw StateError('Kata sandi baru minimal 8 karakter.');
    }
    final target = await database
        .customSelect(
          '''SELECT users.id, roles.name AS role_name FROM users
         JOIN roles ON roles.id = users.role_id WHERE users.id = ? AND users.deleted_at IS NULL''',
          variables: [Variable.withInt(userId)],
        )
        .getSingleOrNull();
    if (target == null) throw StateError('Akun pengguna tidak ditemukan.');
    if (target.read<String>('role_name') == 'OWNER') {
      throw StateError('Akun pemilik tidak dapat diubah dari menu karyawan.');
    }
    final roleRow = await database
        .customSelect(
          'SELECT id FROM roles WHERE name = ?',
          variables: [Variable.withString(role)],
        )
        .getSingleOrNull();
    if (roleRow == null) throw StateError('Peran pengguna tidak tersedia.');

    final now = _now();
    final normalizedWhatsapp = whatsapp?.trim().isEmpty ?? true
        ? null
        : whatsapp!.trim();
    final hash = newPassword == null || newPassword.isEmpty
        ? null
        : await passwordHasher.hash(newPassword);
    try {
      if (hash == null) {
        await _statement(
          '''UPDATE users SET username = ?, full_name = ?, whatsapp = ?, role_id = ?, updated_at = ?
             WHERE id = ? AND deleted_at IS NULL''',
          [
            Variable.withString(normalizedUsername),
            Variable.withString(normalizedName),
            Variable<String>(normalizedWhatsapp),
            Variable.withInt(roleRow.read<int>('id')),
            Variable.withString(now),
            Variable.withInt(userId),
          ],
        );
      } else {
        await _statement(
          '''UPDATE users SET username = ?, full_name = ?, whatsapp = ?, role_id = ?,
             password_hash = ?, failed_login_count = 0, locked_until = NULL, updated_at = ?
             WHERE id = ? AND deleted_at IS NULL''',
          [
            Variable.withString(normalizedUsername),
            Variable.withString(normalizedName),
            Variable<String>(normalizedWhatsapp),
            Variable.withInt(roleRow.read<int>('id')),
            Variable.withString(hash),
            Variable.withString(now),
            Variable.withInt(userId),
          ],
        );
      }
    } on SqliteException catch (error) {
      throw StateError(
        error.message.contains('UNIQUE')
            ? 'Username sudah digunakan akun lain.'
            : 'Perubahan akun tidak dapat disimpan.',
      );
    }
  }

  @override
  Future<void> setUserActive({
    required int userId,
    required int actorId,
    required bool active,
  }) async {
    if (userId == actorId) {
      throw StateError('Akun yang sedang digunakan tidak dapat dinonaktifkan.');
    }
    final target = await database
        .customSelect(
          '''SELECT users.id, roles.name AS role_name FROM users
         JOIN roles ON roles.id = users.role_id WHERE users.id = ? AND users.deleted_at IS NULL''',
          variables: [Variable.withInt(userId)],
        )
        .getSingleOrNull();
    if (target == null) throw StateError('Akun pengguna tidak ditemukan.');
    if (target.read<String>('role_name') == 'OWNER') {
      throw StateError('Akun pemilik tidak dapat dinonaktifkan.');
    }
    if (!active) {
      final openShift = await database
          .customSelect(
            "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'OPEN' AND closed_at IS NULL LIMIT 1",
            variables: [Variable.withInt(userId)],
          )
          .getSingleOrNull();
      if (openShift != null) {
        throw StateError('Tutup shift pengguna sebelum menonaktifkan akunnya.');
      }
    }
    await _statement(
      'UPDATE users SET is_active = ?, failed_login_count = 0, locked_until = NULL, updated_at = ? WHERE id = ?',
      [
        Variable.withInt(active ? 1 : 0),
        Variable.withString(_now()),
        Variable.withInt(userId),
      ],
    );
  }

  /// Soft-deletes a staff account so sales, shifts, and audit history remain linked.
  @override
  Future<void> deleteUser({required int userId, required int actorId}) async {
    if (userId == actorId) {
      throw StateError('Akun yang sedang digunakan tidak dapat dihapus.');
    }
    final target = await database
        .customSelect(
          '''SELECT users.id, roles.name AS role_name FROM users
         JOIN roles ON roles.id = users.role_id WHERE users.id = ? AND users.deleted_at IS NULL''',
          variables: [Variable.withInt(userId)],
        )
        .getSingleOrNull();
    if (target == null) throw StateError('Akun pengguna tidak ditemukan.');
    if (target.read<String>('role_name') == 'OWNER') {
      throw StateError('Akun pemilik tidak dapat dihapus.');
    }
    final openShift = await database
        .customSelect(
          "SELECT id FROM shifts WHERE cashier_id = ? AND status = 'OPEN' AND closed_at IS NULL LIMIT 1",
          variables: [Variable.withInt(userId)],
        )
        .getSingleOrNull();
    if (openShift != null) {
      throw StateError('Tutup shift pengguna sebelum menghapus akunnya.');
    }
    final now = _now();
    await _statement(
      'UPDATE users SET is_active = 0, deleted_at = ?, failed_login_count = 0, locked_until = NULL, updated_at = ? WHERE id = ?',
      [
        Variable.withString(now),
        Variable.withString(now),
        Variable.withInt(userId),
      ],
    );
  }

  @override
  Future<QueryRow?> getStore() => database
      .customSelect(
        'SELECT * FROM stores WHERE deleted_at IS NULL ORDER BY id LIMIT 1',
      )
      .getSingleOrNull();

  @override
  Future<void> updateStore({
    required String name,
    String? slogan,
    String? address,
    String? whatsapp,
    String? logoPath,
    String? bannerPath,
  }) async {
    final normalizedName = name.trim();
    if (normalizedName.isEmpty) throw StateError('Nama toko wajib diisi.');
    final store = await getStore();
    final now = _now();
    if (store != null) {
      await _statement(
        '''UPDATE stores SET name = ?, slogan = ?, address = ?, whatsapp = ?,
           logo_path = COALESCE(?, logo_path), banner_path = COALESCE(?, banner_path), updated_at = ?
           WHERE id = ?''',
        [
          Variable.withString(normalizedName),
          Variable<String>(
            slogan?.trim().isEmpty ?? true ? null : slogan!.trim(),
          ),
          Variable<String>(
            address?.trim().isEmpty ?? true ? null : address!.trim(),
          ),
          Variable<String>(
            whatsapp?.trim().isEmpty ?? true ? null : whatsapp!.trim(),
          ),
          Variable<String>(logoPath),
          Variable<String>(bannerPath),
          Variable.withString(now),
          Variable.withInt(store.read<int>('id')),
        ],
      );
    } else {
      await _statement(
        '''INSERT INTO stores(code, name, slogan, address, whatsapp, logo_path, banner_path, created_at, updated_at)
           VALUES ('MAIN', ?, ?, ?, ?, ?, ?, ?, ?)''',
        [
          Variable.withString(normalizedName),
          Variable<String>(
            slogan?.trim().isEmpty ?? true ? null : slogan!.trim(),
          ),
          Variable<String>(
            address?.trim().isEmpty ?? true ? null : address!.trim(),
          ),
          Variable<String>(
            whatsapp?.trim().isEmpty ?? true ? null : whatsapp!.trim(),
          ),
          Variable<String>(logoPath),
          Variable<String>(bannerPath),
          Variable.withString(now),
          Variable.withString(now),
        ],
      );
    }
  }

  @override
  Future<void> updateOwnerName({
    required int userId,
    required String fullName,
  }) async {
    final name = fullName.trim();
    if (name.isEmpty) throw StateError('Nama owner wajib diisi.');
    await _statement(
      'UPDATE users SET full_name = ?, updated_at = ? WHERE id = ? AND deleted_at IS NULL',
      [
        Variable.withString(name),
        Variable.withString(_now()),
        Variable.withInt(userId),
      ],
    );
  }

  @override
  Future<Map<String, dynamic>> getDashboardStats() async {
    final productCountRow = await database
        .customSelect(
          'SELECT COUNT(*) AS c FROM products WHERE deleted_at IS NULL AND is_active = 1',
        )
        .getSingle();
    final productCount = productCountRow.read<int>('c');

    final today = DateTime.now().toUtc().toIso8601String().substring(0, 10);
    final todaySalesRow = await database
        .customSelect(
          "SELECT COALESCE(SUM(grand_total), 0) AS total, COUNT(*) AS count FROM sales WHERE substr(created_at, 1, 10) = ? AND status = 'PAID'",
          variables: [Variable.withString(today)],
        )
        .getSingle();
    final todaySales = todaySalesRow.read<int>('total');
    final todayCount = todaySalesRow.read<int>('count');

    final activeShiftRow = await database
        .customSelect(
          "SELECT COUNT(*) AS c FROM shifts WHERE status = 'OPEN' AND closed_at IS NULL",
        )
        .getSingle();
    final activeShifts = activeShiftRow.read<int>('c');

    final lowStockRow = await database
        .customSelect(
          'SELECT COUNT(*) AS c FROM products WHERE deleted_at IS NULL AND is_active = 1 AND stock_qty <= min_stock',
        )
        .getSingle();
    final lowStockCount = lowStockRow.read<int>('c');
    final demoDataRow = await database
        .customSelect(
          "SELECT EXISTS(SELECT 1 FROM products WHERE sku = 'DEMO-BRS-001') AS present",
        )
        .getSingle();

    return {
      'productCount': productCount,
      'todaySales': todaySales,
      'todayCount': todayCount,
      'activeShifts': activeShifts,
      'lowStockCount': lowStockCount,
      'demoDataPresent': demoDataRow.read<int>('present') == 1,
    };
  }

  @override
  Future<List<QueryRow>> getRecentSales({int limit = 10}) => database
      .customSelect(
        '''SELECT sales.*, users.full_name AS cashier_name
       FROM sales LEFT JOIN users ON users.id = sales.cashier_id
       WHERE sales.status = 'PAID'
       ORDER BY sales.id DESC LIMIT ?''',
        variables: [Variable.withInt(limit)],
      )
      .get();

  @override
  Future<void> deleteProduct(int productId) async {
    final now = _now();
    await _statement(
      'UPDATE products SET deleted_at = ?, is_active = 0, updated_at = ? WHERE id = ?',
      [
        Variable.withString(now),
        Variable.withString(now),
        Variable.withInt(productId),
      ],
    );
  }
}
