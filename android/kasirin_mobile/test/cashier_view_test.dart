import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:kasirin_mobile/data/local_database.dart';
import 'package:kasirin_mobile/domain/password_hasher.dart';
import 'package:kasirin_mobile/domain/pos_repository.dart';
import 'package:kasirin_mobile/providers.dart';
import 'package:kasirin_mobile/services/trial_service.dart';
import 'package:kasirin_mobile/views/cashier/cashier_view.dart';

class _TestPasswordHasher extends PasswordHasher {
  @override
  Future<String> hash(String password) async => 'test-hash:$password';

  @override
  Future<bool> verify(String password, String encoded) async =>
      encoded == 'test-hash:$password';
}

/// The real TrialService reads FlutterSecureStorage, which has no plugin in a
/// widget test. Checkout gates on the trial, so the test needs an active one.
class _ActiveTrialService extends TrialService {
  _ActiveTrialService() : super(const FlutterSecureStorage());

  @override
  Future<TrialStatus> status({DateTime Function()? now}) async {
    final start = DateTime.utc(2026, 11, 1);
    return TrialStatus(
      active: true,
      startedAt: start,
      endsAt: start.add(const Duration(days: 7)),
      remaining: const Duration(days: 4),
    );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late KasirinDatabase database;
  late PosRepository repository;
  late ProviderContainer container;

  setUp(() async {
    database = KasirinDatabase.memory();
    repository = PosRepository(database, _TestPasswordHasher());
    final cashierId = await repository.createOwner(
      username: 'kasir',
      fullName: 'Siti Kasir',
      password: 'password-rahasia',
    );
    await repository.createStore('Toko Contoh');
    await repository.createProduct(
      sku: 'TEST-001',
      name: 'Kopi Test',
      purchasePrice: 5000,
      sellingPrice: 10000,
      initialStock: 10,
      minimumStock: 1,
    );
    await repository.openShift(cashierId: cashierId, openingCash: 50000);

    container = ProviderContainer(
      overrides: [
        repositoryFutureProvider.overrideWith((ref) async => repository),
        trialServiceProvider.overrideWithValue(_ActiveTrialService()),
      ],
    );
    container
        .read(authNotifierProvider.notifier)
        .setAuthenticated(
          userId: cashierId,
          username: 'kasir',
          fullName: 'Siti Kasir',
          role: 'CASHIER',
        );
  });

  tearDown(() async {
    container.dispose();
    await database.close();
  });

  testWidgets(
    'menampilkan kasir, memilih produk, dan mengubah jumlah di keranjang',
    (tester) async {
      tester.view.physicalSize = const Size(400, 850);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container,
          child: MediaQuery(
            // Keep the real view metrics; only disable animations so the trial
            // banner marquee does not block pumpAndSettle.
            data: MediaQueryData.fromView(tester.view)
                .copyWith(disableAnimations: true),
            child: const MaterialApp(home: CashierView()),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Cashier Register'), findsOneWidget);
      expect(find.text('Kopi Test'), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.tap(find.text('Kopi Test'));
      await tester.pumpAndSettle();
      expect(find.text('OK'), findsOneWidget);
      expect(find.text('Batal'), findsOneWidget);

      await tester.enterText(find.widgetWithText(TextField, 'Jumlah'), '3');
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();
      expect(find.text('1 Produk'), findsOneWidget);
      expect(tester.takeException(), isNull);

      await tester.tap(find.text('Keranjang'));
      await tester.pumpAndSettle();
      expect(find.text('Daftar Belanja (1)'), findsOneWidget);
      expect(find.text('3'), findsOneWidget);
      expect(find.text('Rp 30.000'), findsWidgets);

      // The cart table scrolls inside the sheet; bring the row action into view
      // before tapping it.
      final addIcon = find.byIcon(Icons.add).last;
      await tester.ensureVisible(addIcon);
      await tester.pumpAndSettle();
      await tester.tap(addIcon);
      await tester.pumpAndSettle();
      expect(find.text('4'), findsOneWidget);
      expect(find.text('Rp 40.000'), findsWidgets);

      final payButton = find.text('Lanjut ke pembayaran');
      await tester.ensureVisible(payButton);
      await tester.pumpAndSettle();
      await tester.tap(payButton);
      await tester.pumpAndSettle();
      expect(find.text('Pembayaran Tunai'), findsOneWidget);

      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text('1 Produk'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
