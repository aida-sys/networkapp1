import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

/// Error yang bisa ditampilkan langsung ke pengguna.
///
/// Pesannya sengaja berbahasa Indonesia dan berorientasi tindakan, sama seperti
/// error dari repository lokal (`StateError`), supaya view tidak perlu diubah.
class PosApiException implements Exception {
  PosApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

/// Server LAN tidak dapat dihubungi.
///
/// Ini BUKAN kondisi untuk diam-diam memakai database lokal. Aplikasi menolak
/// operasi tulis dan memberi tahu pengguna, sesuai aturan mode LAN.
class PosApiUnavailableException extends PosApiException {
  PosApiUnavailableException(super.message);
}

/// Klien HTTP untuk POS LAN API.
class PosApiClient {
  PosApiClient({
    required this.baseUrl,
    http.Client? httpClient,
    this.timeout = const Duration(seconds: 15),
  }) : _http = httpClient ?? http.Client();

  /// Contoh: `http://192.168.1.10:8002`
  final String baseUrl;
  final Duration timeout;
  final http.Client _http;

  String? _accessToken;
  String? _deviceId;

  String? get accessToken => _accessToken;

  String get _root => '${baseUrl.replaceAll(RegExp(r'/+$'), '')}/api/v1';

  void setToken(String? token) => _accessToken = token;

  void setDeviceId(String? deviceId) => _deviceId = deviceId;

  void close() => _http.close();

  /// Uji koneksi ke `/health`. Dipakai layar setup sebelum menyimpan alamat.
  Future<Map<String, dynamic>> health() async {
    return _sendMap('GET', '/health', authenticated: false);
  }

  Future<Map<String, dynamic>> login(String username, String password) async {
    final payload = await _sendMap(
      'POST',
      '/auth/login',
      body: {
        'username': username,
        'password': password,
        if (_deviceId != null) 'device_id': _deviceId,
      },
      authenticated: false,
    );
    final token = payload['access_token'];
    if (token is String && token.isNotEmpty) {
      _accessToken = token;
    }
    return payload;
  }

  Future<Map<String, dynamic>> me() => _sendMap('GET', '/auth/me');

  // --- Katalog ---------------------------------------------------------

  Future<List<Map<String, dynamic>>> products({
    String search = '',
    bool includeInactive = false,
  }) async {
    final query = <String, String>{
      if (search.trim().isNotEmpty) 'search': search.trim(),
      if (includeInactive) 'include_inactive': 'true',
    };
    final result = await _sendList('GET', '/catalog/products', query: query);
    return result;
  }

  Future<Map<String, dynamic>> productPrice(int productId, int qty) async {
    return _sendMap(
      'GET',
      '/catalog/products/$productId/price',
      query: {'qty': '$qty'},
    );
  }

  Future<Map<String, dynamic>> createProduct(Map<String, dynamic> body) async {
    return _sendMap('POST', '/catalog/products', body: body);
  }

  Future<Map<String, dynamic>> updateProduct(
    int productId,
    Map<String, dynamic> body,
  ) async {
    return _sendMap('PUT', '/catalog/products/$productId', body: body);
  }

  Future<void> deleteProduct(int productId) async {
    await _send('DELETE', '/catalog/products/$productId');
  }

  Future<List<Map<String, dynamic>>> categories() async {
    return _sendList('GET', '/catalog/categories');
  }

  Future<List<Map<String, dynamic>>> units() async {
    return _sendList('GET', '/catalog/units');
  }

  Future<List<Map<String, dynamic>>> suppliers() async {
    return _sendList('GET', '/catalog/suppliers');
  }

  // --- Shift -----------------------------------------------------------

  Future<Map<String, dynamic>?> currentShift() async {
    final result = await _send('GET', '/shifts/current');
    if (result == null) return null;
    return (result as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> openShift(int openingCash) async {
    return _sendMap('POST', '/shifts/open', body: {'opening_cash': openingCash});
  }

  Future<Map<String, dynamic>> closeShift(int closingCash) async {
    return _sendMap(
      'POST',
      '/shifts/close',
      body: {'closing_cash': closingCash},
    );
  }

  Future<List<Map<String, dynamic>>> shiftHistory({int limit = 30}) async {
    return _sendList('GET', '/shifts', query: {'limit': '$limit'});
  }

  // --- Penjualan -------------------------------------------------------

  /// Checkout. `idempotencyKey` wajib: retry jaringan tidak boleh membuat
  /// transaksi ganda.
  Future<Map<String, dynamic>> checkout({
    required String idempotencyKey,
    required List<Map<String, dynamic>> items,
    required List<Map<String, dynamic>> payments,
  }) async {
    return _sendMap(
      'POST',
      '/sales/checkout',
      body: {'items': items, 'payments': payments},
      headers: {'Idempotency-Key': idempotencyKey},
    );
  }

  Future<List<Map<String, dynamic>>> sales({String? date}) async {
    final query = <String, String>{};
    if (date != null) query['date'] = date;
    return _sendList('GET', '/sales', query: query);
  }

  // --- Pembelian -------------------------------------------------------

  Future<List<Map<String, dynamic>>> purchases() async {
    return _sendList('GET', '/purchases');
  }

  Future<Map<String, dynamic>> createPurchase(
    Map<String, dynamic> body, {
    required String idempotencyKey,
  }) async {
    return _sendMap(
      'POST',
      '/purchases',
      body: body,
      headers: {'Idempotency-Key': idempotencyKey},
    );
  }

  // --- Laporan ---------------------------------------------------------

  Future<Map<String, dynamic>> dailyReport({String? date}) async {
    final query = <String, String>{};
    if (date != null) query['date'] = date;
    return _sendMap('GET', '/reports/daily', query: query);
  }

  Future<Map<String, dynamic>> rangeReport({
    required String start,
    required String end,
  }) async {
    return _sendMap(
      'GET',
      '/reports/range',
      query: {'start': start, 'end': end},
    );
  }

  Future<List<Map<String, dynamic>>> lowStock({int threshold = 5}) async {
    return _sendList(
      'GET',
      '/reports/low-stock',
      query: {'threshold': '$threshold'},
    );
  }

  // --- Toko ------------------------------------------------------------

  Future<Map<String, dynamic>?> store() async {
    final result = await _send('GET', '/settings/store');
    if (result == null) return null;
    return (result as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> updateStore(Map<String, dynamic> body) async {
    return _sendMap('PUT', '/settings/store', body: body);
  }

  // --- Helper bertipe --------------------------------------------------

  Future<Map<String, dynamic>> _sendMap(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
    Map<String, String>? headers,
    bool authenticated = true,
  }) async {
    final result = await _send(
      method,
      path,
      body: body,
      query: query,
      headers: headers,
      authenticated: authenticated,
    );
    if (result is Map) return result.cast<String, dynamic>();
    throw PosApiException('Respons server tidak sesuai format yang diharapkan.');
  }

  Future<List<Map<String, dynamic>>> _sendList(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
    Map<String, String>? headers,
    bool authenticated = true,
  }) async {
    final result = await _send(
      method,
      path,
      body: body,
      query: query,
      headers: headers,
      authenticated: authenticated,
    );
    if (result is List) {
      return result
          .whereType<Map>()
          .map((item) => item.cast<String, dynamic>())
          .toList(growable: false);
    }
    throw PosApiException('Respons server tidak sesuai format yang diharapkan.');
  }

  // --- Inti request ----------------------------------------------------

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    Map<String, String>? query,
    Map<String, String>? headers,
    bool authenticated = true,
  }) async {
    final uri = Uri.parse('$_root$path').replace(queryParameters: query);

    final requestHeaders = <String, String>{
      'Accept': 'application/json',
      if (body != null) 'Content-Type': 'application/json',
      ...?headers,
    };
    if (authenticated) {
      final token = _accessToken;
      if (token == null || token.isEmpty) {
        throw PosApiException('Belum login ke server POS LAN.');
      }
      requestHeaders['Authorization'] = 'Bearer $token';
    }

    http.Response response;
    try {
      final request = http.Request(method, uri)..headers.addAll(requestHeaders);
      if (body != null) request.body = jsonEncode(body);
      final streamed = await _http.send(request).timeout(timeout);
      response = await http.Response.fromStream(streamed);
    } on TimeoutException {
      throw PosApiUnavailableException(
        'Server POS LAN tidak merespons dalam ${timeout.inSeconds} detik. '
        'Periksa jaringan dan pastikan server menyala.',
      );
    } catch (error) {
      throw PosApiUnavailableException(
        'Server POS LAN tidak dapat dihubungi ($baseUrl). '
        'Periksa kabel/WiFi dan pastikan server menyala.',
      );
    }

    if (response.statusCode == 204) return null;

    dynamic decoded;
    if (response.body.isNotEmpty) {
      try {
        decoded = jsonDecode(response.body);
      } catch (_) {
        decoded = null;
      }
    }

    if (response.statusCode >= 400) {
      throw _mapError(response.statusCode, decoded);
    }
    return decoded;
  }

  PosApiException _mapError(int statusCode, dynamic decoded) {
    var detail = '';
    if (decoded is Map && decoded['detail'] != null) {
      final raw = decoded['detail'];
      detail = raw is List ? raw.join('; ') : '$raw';
    }
    if (detail.isEmpty) {
      detail = 'Permintaan ke server gagal (HTTP $statusCode).';
    }
    if (statusCode == 401) {
      return PosApiException(detail, statusCode: statusCode);
    }
    return PosApiException(detail, statusCode: statusCode);
  }
}
