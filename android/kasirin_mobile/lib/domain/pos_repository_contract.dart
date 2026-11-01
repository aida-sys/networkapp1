/// Kontrak repository POS.
///
/// Ada dua implementasi:
/// - `PosRepository` (Drift/SQLite lokal) — mode standalone, default.
/// - `RemotePosRepository` (POS LAN API) — mode LAN, satu database di server.
///
/// View hanya boleh bergantung pada kontrak ini, bukan pada implementasinya.
///
/// Catatan penting: beberapa method mengembalikan `QueryRow` milik Drift.
/// Itu disengaja — `QueryRow` hanyalah pembungkus `Map<String, dynamic>` +
/// type mapping, sehingga implementasi remote bisa membangunnya dari JSON
/// server tanpa membuka database lokal. Dengan begitu tidak ada satu pun view
/// yang perlu diubah saat aplikasi berjalan di mode LAN.
library;

import 'package:drift/drift.dart';

import '../data/local_database.dart';

/// Hasil checkout. Sama untuk mode lokal dan LAN.
class CheckoutResult {
  const CheckoutResult({
    required this.saleId,
    required this.invoiceNo,
    required this.total,
    required this.change,
    required this.wasExisting,
  });

  final int saleId;
  final String invoiceNo;
  final int total;
  final int change;
  final bool wasExisting;
}

/// Satu baris keranjang yang dikirim ke server.
class CartItemInput {
  const CartItemInput({required this.productId, required this.quantity});

  final int productId;
  final int quantity;
}

/// Kontrak yang harus dipenuhi kedua implementasi repository.
abstract class PosRepositoryContract {
  Future<bool> setupRequired();

  Future<int> createOwner({
    required String username,
    required String fullName,
    required String password,
    String? storeName,
  });

  Future<void> seedDemoData(int ownerId);

  Future<QueryRow> login(String username, String password);

  Future<QueryRow?> openShiftFor(int cashierId);

  Future<int> unitPriceFor(int productId, int quantity);

  Future<List<QueryRow>> products({String search = ''});

  Future<int> createProduct({
    required String sku,
    required String name,
    required int purchasePrice,
    required int sellingPrice,
    required int initialStock,
    required int minimumStock,
    int? supplierId,
    String? barcode,
  });

  Future<void> deleteProduct(int productId);

  Future<List<QueryRow>> getSpecialPriceRules();

  Future<void> saveSpecialPriceRule({
    int? ruleId,
    required int productId,
    required int quantityThreshold,
    required int specialPrice,
    int multipleQuantityThreshold = 0,
    int? multipleSpecialPrice,
  });

  Future<void> deleteSpecialPriceRule(int ruleId);

  Future<List<QueryRow>> getSuppliers();

  Future<int> createSupplier({
    required String name,
    String? phone,
    String? address,
  });

  Future<void> updateSupplier({
    required int supplierId,
    required String name,
    String? phone,
    String? address,
  });

  Future<List<QueryRow>> getPurchaseOrders();

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
  });

  Future<void> receivePurchaseOrder({
    required int orderId,
    required int actorId,
  });

  Future<int> payPurchaseOrder({
    required int orderId,
    required int amount,
    required int actorId,
  });

  Future<List<QueryRow>> getStockReport();

  Future<Map<String, dynamic>> getFinancialReport();

  Future<List<QueryRow>> getShiftHistory({int limit = 30});

  Future<Map<String, bool>> getPaymentSettings();

  Future<void> savePaymentSettings(Map<String, bool> settings);

  Future<int?> openShift({required int cashierId, required int openingCash});

  Future<CheckoutResult> checkout({
    required String invoiceNo,
    required int cashierId,
    required int shiftId,
    required List<CartItemInput> items,
    required String paymentMethod,
    required int paymentAmount,
  });

  Future<void> closeShift({
    required int shiftId,
    required int cashierId,
    required int closingCash,
  });

  Future<List<QueryRow>> getUsers();

  Future<int> addUser({
    required String username,
    required String fullName,
    required String password,
    required String role,
    String? whatsapp,
  });

  Future<void> updateUser({
    required int userId,
    required String username,
    required String fullName,
    required String role,
    String? whatsapp,
    String? newPassword,
  });

  Future<void> setUserActive({
    required int userId,
    required int actorId,
    required bool active,
  });

  Future<void> deleteUser({required int userId, required int actorId});

  Future<QueryRow?> getStore();

  Future<void> updateStore({
    required String name,
    String? slogan,
    String? address,
    String? whatsapp,
    String? logoPath,
    String? bannerPath,
  });

  Future<void> updateOwnerName({
    required int userId,
    required String fullName,
  });

  Future<Map<String, dynamic>> getDashboardStats();

  Future<List<QueryRow>> getRecentSales({int limit = 10});
}

/// Dipakai implementasi remote untuk membangun `QueryRow` dari JSON.
///
/// `QueryRow` butuh `DatabaseConnectionUser` untuk type mapping; instance
/// database lokal dipakai hanya sebagai mapper, bukan sebagai sumber data.
QueryRow queryRowFromMap(KasirinDatabase mapper, Map<String, dynamic> data) {
  return QueryRow(data, mapper);
}
