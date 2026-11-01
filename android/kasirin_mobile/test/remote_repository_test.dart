import 'dart:convert';

import 'package:drift/drift.dart' show QueryRow;
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:kasirin_mobile/data/local_database.dart';
import 'package:kasirin_mobile/domain/pos_repository.dart';
import 'package:kasirin_mobile/remote/pos_api_client.dart';
import 'package:kasirin_mobile/remote/remote_pos_repository.dart';

/// Transport palsu: tidak ada server sungguhan, tetapi jalur HTTP, header,
/// dan parsing JSON benar-benar dieksekusi.
class _FakeTransport extends http.BaseClient {
  _FakeTransport(this.handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request) handler;
  final List<http.BaseRequest> requests = [];
  final List<String> bodies = [];

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) {
    requests.add(request);
    if (request is http.Request) bodies.add(request.body);
    return handler(request);
  }
}

http.StreamedResponse _json(Object payload, {int status = 200}) {
  final bytes = utf8.encode(jsonEncode(payload));
  return http.StreamedResponse(
    Stream.value(bytes),
    status,
    headers: {'content-type': 'application/json'},
  );
}

void main() {
  late KasirinDatabase mapper;

  setUpAll(() async {
    mapper = KasirinDatabase.memory();
  });

  tearDownAll(() async {
    await mapper.close();
  });

  group('PosApiClient', () {
    test('health memanggil /api/v1/health tanpa token', () async {
      final transport = _FakeTransport(
        (_) async => _json({'status': 'ok', 'database': 'ok', 'version': '1.0'}),
      );
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002/',
        httpClient: transport,
      );

      final health = await client.health();

      expect(health['database'], 'ok');
      expect(transport.requests.single.url.toString(),
          'http://192.168.1.10:8002/api/v1/health');
      expect(transport.requests.single.headers.containsKey('Authorization'),
          isFalse);
    });

    test('login menyimpan access token dan mengirimkannya di request berikutnya',
        () async {
      final transport = _FakeTransport((request) async {
        if (request.url.path.endsWith('/auth/login')) {
          return _json({
            'access_token': 'token-abc',
            'user': {
              'id': 7,
              'username': 'kasir1',
              'full_name': 'Kasir Satu',
              'role': 'CASHIER',
              'is_active': true,
            },
          });
        }
        return _json([]);
      });
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      );

      final payload = await client.login('kasir1', 'rahasia');
      expect(payload['access_token'], 'token-abc');
      expect(client.accessToken, 'token-abc');

      await client.products();
      expect(transport.requests.last.headers['Authorization'],
          'Bearer token-abc');
    });

    test('request tanpa token ditolak sebelum menyentuh jaringan', () async {
      final transport = _FakeTransport((_) async => _json([]));
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      );

      expect(
        () => client.products(),
        throwsA(isA<PosApiException>()),
      );
      expect(transport.requests, isEmpty);
    });

    test('server mati memunculkan PosApiUnavailableException, bukan fallback',
        () async {
      final transport = _FakeTransport(
        (_) async => throw const SocketExceptionStub(),
      );
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      );

      expect(
        () => client.health(),
        throwsA(
          isA<PosApiUnavailableException>().having(
            (error) => error.message,
            'message',
            contains('tidak dapat dihubungi'),
          ),
        ),
      );
    });

    test('error 4xx memakai detail dari server', () async {
      final transport = _FakeTransport(
        (_) async => _json({'detail': 'Stok tidak mencukupi.'}, status: 409),
      );
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      )..setToken('token-abc');

      expect(
        () => client.checkout(
          idempotencyKey: 'INV-1',
          items: const [],
          payments: const [],
        ),
        throwsA(
          isA<PosApiException>()
              .having((error) => error.message, 'message', 'Stok tidak mencukupi.')
              .having((error) => error.statusCode, 'statusCode', 409),
        ),
      );
    });

    test('checkout mengirim Idempotency-Key', () async {
      final transport = _FakeTransport(
        (_) async => _json({
          'id': 91,
          'invoice_no': 'INV-2026-0001',
          'grand_total': 25000,
        }),
      );
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      )..setToken('token-abc');

      final sale = await client.checkout(
        idempotencyKey: 'INV-2026-0001',
        items: [
          {'product_id': 3, 'qty': 2},
        ],
        payments: [
          {'method': 'CASH', 'amount': 50000},
        ],
      );

      expect(sale['grand_total'], 25000);
      expect(transport.requests.last.headers['Idempotency-Key'],
          'INV-2026-0001');
      expect(transport.requests.last.url.path, '/api/v1/sales/checkout');
    });
  });

  group('RemotePosRepository', () {
    test('login mengembalikan QueryRow yang bisa dibaca view', () async {
      final transport = _FakeTransport(
        (_) async => _json({
          'access_token': 'token-abc',
          'user': {
            'id': 7,
            'username': 'kasir1',
            'full_name': 'Kasir Satu',
            'role': 'CASHIER',
            'is_active': true,
          },
        }),
      );
      final client = PosApiClient(
        baseUrl: 'http://192.168.1.10:8002',
        httpClient: transport,
      );
      String? savedToken;
      final repository = RemotePosRepository(
        client: client,
        mapper: mapper,
        onToken: (token) async => savedToken = token,
      );

      final QueryRow row = await repository.login('kasir1', 'rahasia');

      expect(row.read<int>('id'), 7);
      expect(row.read<String>('role_name'), 'CASHIER');
      expect(row.read<String>('full_name'), 'Kasir Satu');
      expect(savedToken, 'token-abc');
    });

    test('products mengembalikan QueryRow dengan kolom yang dipakai view',
        () async {
      final transport = _FakeTransport(
        (_) async => _json([
          {
            'id': 3,
            'sku': 'KOPI-01',
            'name': 'Kopi Susu',
            'barcode': '899123',
            'selling_price': 18000,
            'purchase_price': 12000,
            'stock_qty': 40,
            'min_stock': 5,
            'is_active': true,
            'category_name': 'Minuman',
          },
        ]),
      );
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: transport,
        )..setToken('token-abc'),
        mapper: mapper,
      );

      final rows = await repository.products(search: 'kopi');

      expect(rows, hasLength(1));
      expect(rows.single.read<int>('id'), 3);
      expect(rows.single.read<String>('name'), 'Kopi Susu');
      expect(rows.single.read<int>('selling_price'), 18000);
      expect(rows.single.read<String?>('category_name'), 'Minuman');
      expect(transport.requests.single.url.queryParameters['search'], 'kopi');
    });

    test('unitPriceFor memakai harga dari server, bukan hitungan lokal',
        () async {
      final transport = _FakeTransport(
        (_) async => _json({'unit_price': 15000, 'quantity': 12}),
      );
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: transport,
        )..setToken('token-abc'),
        mapper: mapper,
      );

      final price = await repository.unitPriceFor(3, 12);

      expect(price, 15000);
      expect(transport.requests.single.url.queryParameters['qty'], '12');
    });

    test('checkout memakai nomor invoice sebagai kunci idempotency', () async {
      final transport = _FakeTransport(
        (_) async => _json({
          'id': 91,
          'invoice_no': 'INV-2026-0001',
          'grand_total': 25000,
        }),
      );
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: transport,
        )..setToken('token-abc'),
        mapper: mapper,
      );

      final result = await repository.checkout(
        invoiceNo: 'INV-2026-0001',
        cashierId: 7,
        shiftId: 2,
        items: const [CartItemInput(productId: 3, quantity: 2)],
        paymentMethod: 'CASH',
        paymentAmount: 50000,
      );

      expect(result.saleId, 91);
      expect(result.total, 25000);
      expect(result.change, 25000);
      expect(transport.requests.single.headers['Idempotency-Key'],
          'INV-2026-0001');
      final body = jsonDecode(transport.bodies.single) as Map<String, dynamic>;
      expect(body['items'], [
        {'product_id': 3, 'qty': 2},
      ]);
      expect(body['payments'], [
        {'method': 'CASH', 'amount': 50000},
      ]);
    });

    test('checkout keranjang kosong ditolak sebelum request', () async {
      final transport = _FakeTransport((_) async => _json({}));
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: transport,
        )..setToken('token-abc'),
        mapper: mapper,
      );

      expect(
        () => repository.checkout(
          invoiceNo: 'INV-1',
          cashierId: 7,
          shiftId: 2,
          items: const [],
          paymentMethod: 'CASH',
          paymentAmount: 0,
        ),
        throwsA(isA<StateError>()),
      );
      expect(transport.requests, isEmpty);
    });

    test('mode LAN tidak pernah meminta setup owner di perangkat', () async {
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: _FakeTransport((_) async => _json({})),
        ),
        mapper: mapper,
      );

      expect(await repository.setupRequired(), isFalse);
      expect(
        () => repository.createOwner(
          username: 'owner',
          fullName: 'Owner',
          password: 'rahasia123',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('operasi khusus server ditolak dengan pesan jelas', () async {
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: _FakeTransport((_) async => _json([])),
        )..setToken('token-abc'),
        mapper: mapper,
      );

      expect(() => repository.getUsers(), throwsA(isA<StateError>()));
      expect(
        () => repository.addUser(
          username: 'kasir2',
          fullName: 'Kasir Dua',
          password: 'rahasia123',
          role: 'CASHIER',
        ),
        throwsA(isA<StateError>()),
      );
    });

    test('getStockReport memakai stok dari server', () async {
      final transport = _FakeTransport(
        (_) async => _json([
          {
            'id': 3,
            'sku': 'KOPI-01',
            'name': 'Kopi Susu',
            'stock_qty': 2,
            'min_stock': 5,
            'purchase_price': 12000,
            'selling_price': 18000,
          },
        ]),
      );
      final repository = RemotePosRepository(
        client: PosApiClient(
          baseUrl: 'http://192.168.1.10:8002',
          httpClient: transport,
        )..setToken('token-abc'),
        mapper: mapper,
      );

      final rows = await repository.getStockReport();

      expect(rows.single.read<int>('stock_qty'), 2);
      expect(rows.single.read<int>('min_stock'), 5);
    });
  });
}

/// Meniru kegagalan jaringan tanpa bergantung pada `dart:io`, supaya test ini
/// juga bisa dijalankan di lingkungan web.
class SocketExceptionStub implements Exception {
  const SocketExceptionStub();
}
