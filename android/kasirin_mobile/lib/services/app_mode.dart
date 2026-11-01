import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Mode operasi aplikasi.
enum AppMode {
  /// Database SQLite lokal di perangkat. Ini default dan perilaku lama.
  standalone,

  /// Satu database di server LAN; perangkat menjadi klien API.
  lan,
}

/// Konfigurasi koneksi LAN yang tersimpan di perangkat.
class LanConnection {
  const LanConnection({required this.baseUrl, this.deviceId});

  final String baseUrl;
  final String? deviceId;

  bool get isConfigured => baseUrl.trim().isNotEmpty;

  LanConnection copyWith({String? baseUrl, String? deviceId}) {
    return LanConnection(
      baseUrl: baseUrl ?? this.baseUrl,
      deviceId: deviceId ?? this.deviceId,
    );
  }
}

/// Penyimpanan konfigurasi mode.
///
/// Disimpan di secure storage supaya token dan alamat server tidak ikut
/// tercatat di log atau file biasa.
class AppModeStore {
  AppModeStore(this._storage);

  static const _modeKey = 'pos.mode';
  static const _baseUrlKey = 'pos.lan.baseUrl';
  static const _deviceIdKey = 'pos.lan.deviceId';
  static const _tokenKey = 'pos.lan.token';

  final FlutterSecureStorage _storage;

  Future<AppMode> readMode() async {
    final raw = await _storage.read(key: _modeKey);
    return raw == AppMode.lan.name ? AppMode.lan : AppMode.standalone;
  }

  Future<void> writeMode(AppMode mode) async {
    await _storage.write(key: _modeKey, value: mode.name);
  }

  Future<LanConnection> readConnection() async {
    final baseUrl = await _storage.read(key: _baseUrlKey) ?? '';
    final deviceId = await _storage.read(key: _deviceIdKey);
    return LanConnection(baseUrl: baseUrl, deviceId: deviceId);
  }

  Future<void> writeConnection(LanConnection connection) async {
    await _storage.write(key: _baseUrlKey, value: connection.baseUrl);
    if (connection.deviceId != null) {
      await _storage.write(key: _deviceIdKey, value: connection.deviceId);
    }
  }

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<void> writeToken(String token) async {
    await _storage.write(key: _tokenKey, value: token);
  }

  Future<void> clearToken() async {
    await _storage.delete(key: _tokenKey);
  }
}

/// Status mode aplikasi saat ini.
class AppModeState {
  const AppModeState({
    required this.mode,
    required this.connection,
    this.ready = false,
  });

  final AppMode mode;
  final LanConnection connection;
  final bool ready;

  bool get isLan => mode == AppMode.lan;

  AppModeState copyWith({
    AppMode? mode,
    LanConnection? connection,
    bool? ready,
  }) {
    return AppModeState(
      mode: mode ?? this.mode,
      connection: connection ?? this.connection,
      ready: ready ?? this.ready,
    );
  }
}

class AppModeNotifier extends Notifier<AppModeState> {
  Completer<void>? _loaded;

  @override
  AppModeState build() {
    // Nilai awal standalone: aplikasi tidak pernah diam-diam masuk mode LAN.
    Future.microtask(_load);
    return const AppModeState(
      mode: AppMode.standalone,
      connection: LanConnection(baseUrl: ''),
    );
  }

  AppModeStore get _store => AppModeStore(const FlutterSecureStorage());

  /// Menunggu konfigurasi mode selesai dibaca dari secure storage.
  ///
  /// Dipakai `repositoryFutureProvider` supaya repository tidak pernah dibuat
  /// dari mode sementara (default sebelum storage selesai dibaca).
  Future<void> ensureLoaded() {
    if (state.ready) return Future<void>.value();
    return (_loaded ??= Completer<void>()).future;
  }

  Future<void> _load() async {
    final store = _store;
    final mode = await store.readMode();
    final connection = await store.readConnection();
    state = AppModeState(mode: mode, connection: connection, ready: true);
    _completeLoaded();
  }

  void _completeLoaded() {
    final completer = _loaded;
    if (completer != null && !completer.isCompleted) completer.complete();
  }

  Future<void> useStandalone() async {
    await _store.writeMode(AppMode.standalone);
    await _store.clearToken();
    state = state.copyWith(mode: AppMode.standalone, ready: true);
    _completeLoaded();
  }

  Future<void> useLan(LanConnection connection) async {
    await _store.writeConnection(connection);
    await _store.writeMode(AppMode.lan);
    state = state.copyWith(
      mode: AppMode.lan,
      connection: connection,
      ready: true,
    );
    _completeLoaded();
  }
}
