import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'data/local_database.dart';
import 'domain/password_hasher.dart';
import 'domain/pos_repository.dart';
import 'remote/pos_api_client.dart';
import 'remote/remote_pos_repository.dart';
import 'services/app_mode.dart';
import 'services/billing_client.dart';
import 'services/billing_config.dart';
import 'services/trial_service.dart';
import 'views/auth/auth_state.dart';
import 'views/auth/login_view.dart';
import 'views/auth/license_view.dart';
import 'views/auth/setup_owner_view.dart';
import 'views/settings/lan_setup_view.dart';
import 'views/owner/dashboard_view.dart';
import 'views/cashier/cashier_view.dart';
import 'views/owner/user_management_view.dart';
import 'views/owner/master_data_view.dart';
import 'views/owner/special_prices_view.dart';
import 'views/owner/purchase_view.dart';
import 'views/reports/report_center_view.dart';
import 'views/owner/store_settings_view.dart';

// --- Riverpod providers ---

final databaseProvider = FutureProvider<KasirinDatabase>((ref) async {
  final db = await openKasirinDatabase();
  ref.onDispose(db.close);
  return db;
});

final passwordHasherProvider = Provider<PasswordHasher>(
  (ref) => PasswordHasher(),
);

/// Mode aplikasi (standalone atau LAN). Default standalone.
final appModeProvider = NotifierProvider<AppModeNotifier, AppModeState>(
  AppModeNotifier.new,
);

/// Klien POS LAN. Hanya dibuat saat mode LAN aktif.
final posApiClientProvider = Provider<PosApiClient>((ref) {
  final connection = ref.watch(appModeProvider).connection;
  final client = PosApiClient(baseUrl: connection.baseUrl);
  ref.onDispose(client.close);
  return client;
});

/// Satu titik pemilihan implementasi repository.
///
/// - standalone (default): `PosRepository` dengan Drift/SQLite lokal.
/// - lan: `RemotePosRepository` lewat POS LAN API.
///
/// Tidak ada dual-write dan tidak ada fallback diam-diam antar mode.
final repositoryFutureProvider = FutureProvider<PosRepositoryContract>((ref) async {
  // Tunggu mode selesai dibaca supaya tidak pernah memilih implementasi dari
  // nilai default sementara.
  await ref.read(appModeProvider.notifier).ensureLoaded();
  final modeState = ref.watch(appModeProvider);

  if (modeState.isLan) {
    final database = await ref.watch(databaseProvider.future);
    final client = ref.watch(posApiClientProvider);
    final store = AppModeStore(ref.watch(secureStorageProvider));
    final token = await store.readToken();
    if (token != null && token.isNotEmpty) {
      client.setToken(token);
    }
    client.setDeviceId(modeState.connection.deviceId);
    return RemotePosRepository(
      client: client,
      mapper: database,
      onToken: store.writeToken,
    );
  }

  final database = await ref.watch(databaseProvider.future);
  return PosRepository(database, ref.read(passwordHasherProvider));
});

final billingConfigProvider = Provider<BillingConfig>((ref) {
  return BillingConfig(
    baseUrl: const String.fromEnvironment(
      'BILLING_BASE_URL',
      defaultValue: 'https://trimester-slaw-papaya.ngrok-free.dev',
    ),
    apiPrefix: '',
  );
});

final billingClientProvider = Provider<BillingClient>((ref) {
  return BillingClient(ref.watch(billingConfigProvider));
});

final billingLicenseActiveProvider = FutureProvider<bool>((ref) async {
  final token = await ref
      .watch(secureStorageProvider)
      .read(key: 'billing.device_token');
  if (token == null || token.isEmpty) return false;
  try {
    final result =
        await ref.watch(billingClientProvider).checkLicense(bearerToken: token)
            as Map;
    return result['status'] == 'active';
  } catch (_) {
    return false;
  }
});

final secureStorageProvider = Provider<FlutterSecureStorage>(
  (ref) => const FlutterSecureStorage(),
);
final trialServiceProvider = Provider<TrialService>(
  (ref) => TrialService(ref.watch(secureStorageProvider)),
);
final trialStatusProvider = FutureProvider<TrialStatus>(
  (ref) => ref.watch(trialServiceProvider).status(),
);

// --- Auth ---

final authNotifierProvider = NotifierProvider<AuthNotifier, AuthState>(() {
  return AuthNotifier();
});

// --- Theme ---

final themeProvider = Provider(
  (ref) => ThemeData(
    useMaterial3: true,
    brightness: Brightness.dark,
    scaffoldBackgroundColor: const Color(0xFF0B1326),
    colorScheme: const ColorScheme.dark(
      primary: Color(0xFF6DFFBA),
      onPrimary: Color(0xFF003822),
      primaryContainer: Color(0xFF00E599),
      secondary: Color(0xFFC0C1FF),
      surface: Color(0xFF0B1326),
      error: Color(0xFFFFB4AB),
      onSurface: Color(0xFFDAE2FD),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Color(0xFF060E20),
      foregroundColor: Color(0xFFDAE2FD),
      surfaceTintColor: Colors.transparent,
      elevation: 0,
    ),
    cardTheme: CardThemeData(
      color: const Color(0xFF171F33),
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
    textTheme:
        const TextTheme(
          displayLarge: TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
          titleLarge: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
          bodyLarge: TextStyle(fontSize: 16),
          bodyMedium: TextStyle(fontSize: 14),
          labelLarge: TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
        ).apply(
          fontFamily: 'Inter',
          bodyColor: const Color(0xFFDAE2FD),
          displayColor: const Color(0xFFDAE2FD),
        ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: const Color(0xFF131B2E),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF3B4A41)),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF3B4A41)),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(8),
        borderSide: const BorderSide(color: Color(0xFF6DFFBA), width: 2),
      ),
    ),
  ),
);

// --- GoRouter ---

final routerProvider = Provider<GoRouter>((ref) {
  final authState = ref.watch(authNotifierProvider);
  return GoRouter(
    initialLocation: authState.isAuthenticated ? '/' : '/login',
    redirect: (context, state) {
      final authState = ref.read(authNotifierProvider);
      if (!authState.isAuthenticated &&
          state.matchedLocation != '/login' &&
          state.matchedLocation != '/setup' &&
          state.matchedLocation != '/license') {
        return '/login';
      }
      if (authState.isAuthenticated &&
          authState.isCashier &&
          state.matchedLocation != '/cashier') {
        return '/cashier';
      }
      if (authState.isAuthenticated &&
          !authState.isCashier &&
          state.matchedLocation == '/cashier' &&
          !authState.isOwner) {
        return '/';
      }
      if (authState.isAuthenticated && state.matchedLocation == '/login') {
        return '/';
      }
      return null;
    },
    routes: [
      GoRoute(path: '/login', builder: (context, state) => const LoginView()),
      GoRoute(
        path: '/setup',
        builder: (context, state) => const SetupOwnerView(),
      ),
      GoRoute(
        path: '/license',
        builder: (context, state) => const LicenseView(),
      ),
      GoRoute(
        path: '/connection',
        builder: (context, state) => const LanSetupView(),
      ),
      GoRoute(
        path: '/',
        builder: (context, state) => const DashboardView(),
        routes: [
          GoRoute(
            path: 'cashier',
            builder: (context, state) => const CashierView(),
          ),
          GoRoute(
            path: 'user-management',
            builder: (context, state) => const UserManagementView(),
          ),
          GoRoute(
            path: 'master-data',
            builder: (context, state) => const MasterDataView(),
          ),
          GoRoute(
            path: 'special-prices',
            builder: (context, state) => const SpecialPricesView(),
          ),
          GoRoute(
            path: 'purchase',
            builder: (context, state) => PurchaseView(
              openNewOrderOnLoad:
                  state.uri.queryParameters['newOrder'] == 'true',
              initialTab: state.uri.queryParameters['tab'] == 'supplier'
                  ? 1
                  : 0,
            ),
          ),
          GoRoute(
            path: 'report-center',
            builder: (context, state) => const ReportCenterView(),
          ),
          GoRoute(
            path: 'store-settings',
            builder: (context, state) => const StoreSettingsView(),
          ),
        ],
      ),
    ],
    errorBuilder: (context, state) => Scaffold(
      appBar: AppBar(title: const Text('Halaman tidak ditemukan')),
      body: Center(child: Text('Halaman tidak ditemukan: ${state.error}')),
    ),
  );
});
