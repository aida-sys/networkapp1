import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:go_router/go_router.dart';

import '../../platform/billing_platform.dart';
import '../../providers.dart';
import '../owner/owner_widgets.dart';

class LicenseView extends ConsumerStatefulWidget {
  const LicenseView({super.key});
  @override
  ConsumerState<LicenseView> createState() => _LicenseViewState();
}

class _LicenseViewState extends ConsumerState<LicenseView>
    with WidgetsBindingObserver {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _store = TextEditingController(text: 'Toko Kasirin');
  bool _register = false;
  bool _busy = false;
  String? _message;
  String? _deviceToken;
  String? _customerToken;
  int? _devicePk;
  String? _selectedPlan;
  List<Map<String, dynamic>> _plans = [];
  Map<String, dynamic>? _license;
  Map<String, dynamic>? _subscription;
  Timer? _pollTimer;

  FlutterSecureStorage get _storage => ref.read(secureStorageProvider);

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _restoreBillingSession();
    _loadPlans();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _deviceToken != null) {
      _refreshLicense();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    _email.dispose();
    _password.dispose();
    _store.dispose();
    super.dispose();
  }

  Future<void> _restoreBillingSession() async {
    final values = await Future.wait([
      _storage.read(key: 'billing.customer_token'),
      _storage.read(key: 'billing.device_token'),
      _storage.read(key: 'billing.device_pk'),
      _storage.read(key: 'billing.email'),
    ]);
    if (!mounted) return;
    setState(() {
      _customerToken = values[0];
      _deviceToken = values[1];
      _devicePk = int.tryParse(values[2] ?? '');
      _email.text = values[3] ?? '';
    });
    if (_deviceToken != null) _refreshLicense();
  }

  Future<String> _installationId() async {
    var id = await _storage.read(key: 'billing.installation_id');
    if (id != null && id.isNotEmpty) return id;
    final bytes = List<int>.generate(16, (_) => Random.secure().nextInt(256));
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    final hex = bytes.map((b) => b.toRadixString(16).padLeft(2, '0')).join();
    id =
        '${hex.substring(0, 8)}-${hex.substring(8, 12)}-${hex.substring(12, 16)}-${hex.substring(16, 20)}-${hex.substring(20)}';
    await _storage.write(key: 'billing.installation_id', value: id);
    return id;
  }

  Future<String> _deviceId(String installationId) async {
    var id = await _storage.read(key: 'billing.device_id');
    if (id != null && RegExp(r'^[0-9a-f]{64}$').hasMatch(id)) return id;
    id = sha256
        .convert(utf8.encode('Kasirin POS Retail Android:$installationId'))
        .toString();
    await _storage.write(key: 'billing.device_id', value: id);
    return id;
  }

  Future<String?> _savePosRequestFile() async {
    final storeName = _store.text.trim().isEmpty
        ? 'Toko Kasirin'
        : _store.text.trim();
    final installationId = await _installationId();
    final deviceId = await _deviceId(installationId);
    final request = jsonEncode({
      'schema_version': 1,
      'product': 'POS Retail',
      'installation_id': installationId,
      'device_id': deviceId,
      'store_name': storeName,
      'requested_at': DateTime.now().toUtc().toIso8601String(),
    });
    return savePosRequest(
      filename: 'permintaan-lisensi.posreq',
      content: request,
    );
  }

  Future<void> _openBillingDashboard() async {
    final baseUrl = ref.read(billingConfigProvider).baseUrl;
    final dashboardUri = Uri.parse(baseUrl)
        .replace(path: '/dashboard', query: null, fragment: null);
    await openExternalUrl(dashboardUri.toString());
  }

  Future<void> _saveRequestAndOpenDashboard() async {
    setState(() {
      _busy = true;
      _message = 'Menyiapkan permintaan lisensi…';
    });
    try {
      final savedUri = await _savePosRequestFile();
      if (savedUri == null) {
        _showActivationMessage('Penyimpanan permintaan dibatalkan.');
        return;
      }
      await _openBillingDashboard();
      _showActivationMessage(
        'File .posreq tersimpan. Masuk ke dashboard billing dan unggah file tersebut. Setelah pembayaran, unduh .poslic lalu kembali ke aplikasi.',
      );
    } catch (e) {
      _showActivationMessage(_cleanError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _loadPlans() async {
    try {
      final response = await ref.read(billingClientProvider).getPlans() as Map;
      final plans = ((response['plans'] as List?) ?? [])
          .whereType<Map>()
          .map((p) => Map<String, dynamic>.from(p))
          .toList();
      if (!mounted) return;
      setState(() {
        _plans = plans;
        if (_selectedPlan == null && plans.isNotEmpty) {
          _selectedPlan = plans.first['code']?.toString();
        }
        if (_message?.startsWith('Tidak dapat memuat paket') == true) {
          _message = null;
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _message = 'Tidak dapat memuat paket: ${_cleanError(e)}');
    }
  }

  void _showActivationMessage(String message) {
    if (!mounted) return;
    setState(() => _message = message);
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  Future<void> _authenticate() async {
    if (_email.text.trim().isEmpty || _password.text.isEmpty) {
      _showActivationMessage('Email dan password billing wajib diisi.');
      return;
    }
    if (_register && _store.text.trim().isEmpty) {
      _showActivationMessage('Nama toko wajib diisi untuk pendaftaran.');
      return;
    }
    setState(() {
      _busy = true;
      _message = _register ? 'Membuat akun billing…' : 'Masuk ke akun billing…';
    });
    try {
      final client = ref.read(billingClientProvider);
      if (_register) {
        await client.registerCustomer(
          email: _email.text.trim(),
          password: _password.text,
          storeName: _store.text.trim(),
        );
      }
      if (mounted) setState(() => _message = 'Menghubungkan perangkat…');
      final response = await client.loginCustomer(
        email: _email.text.trim(),
        password: _password.text,
      ) as Map;
      final token = response['token']?.toString();
      if (token == null || token.isEmpty) {
        throw Exception('Server tidak mengembalikan token akun billing.');
      }
      await _storage.write(key: 'billing.customer_token', value: token);
      await _storage.write(key: 'billing.email', value: _email.text.trim());
      _customerToken = token;
      await _registerDevice();
      if (mounted) {
        setState(() => _message = 'Perangkat terhubung. Memeriksa lisensi…');
      }
      await _refreshLicense();
      final requestUri = await _savePosRequestFile();
      await _openBillingDashboard();
      _showActivationMessage(
        requestUri == null
            ? 'Akun dan perangkat terhubung. Masuk ke dashboard billing untuk melanjutkan; Anda dapat membuat file .posreq dari tombol di bawah.'
            : 'Akun dan perangkat terhubung. File .posreq tersimpan; masuk ke dashboard billing untuk mengunggahnya dan memilih langganan.',
      );
    } catch (e) {
      _showActivationMessage(_cleanError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _registerDevice() async {
    final customerToken = _customerToken;
    if (customerToken == null) return;
    final installationId = await _installationId();
    final deviceId = await _deviceId(installationId);
    final response =
        await ref
                .read(billingClientProvider)
                .registerDevice(
                  installationId: installationId,
                  deviceId: deviceId,
                  storeName: _store.text.trim().isEmpty
                      ? 'Toko Kasirin'
                      : _store.text.trim(),
                  customerToken: customerToken,
                )
            as Map;
    final deviceToken = response['device_token']?.toString();
    final devicePk = int.tryParse(response['device_pk']?.toString() ?? '');
    if (deviceToken == null || devicePk == null) {
      throw Exception('Server tidak mengembalikan data perangkat.');
    }
    await _storage.write(key: 'billing.device_token', value: deviceToken);
    await _storage.write(key: 'billing.device_pk', value: '$devicePk');
    _deviceToken = deviceToken;
    _devicePk = devicePk;
  }

  Future<void> _refreshLicense() async {
    final token = _deviceToken;
    if (token == null) return;
    try {
      final client = ref.read(billingClientProvider);
      final result = await client.checkLicense(bearerToken: token) as Map;
      final status = result['status']?.toString() ?? 'none';
      if (status == 'active') {
        ref.invalidate(billingLicenseActiveProvider);
      }
      final document = result['document'];
      final deviceStatus =
          await client.getDeviceStatus(bearerToken: token) as Map;
      if (!mounted) return;
      setState(() {
        _license = {
          'status': status,
          if (document is Map) 'document': Map<String, dynamic>.from(document),
        };
        _subscription = deviceStatus['subscription'] is Map
            ? Map<String, dynamic>.from(deviceStatus['subscription'])
            : null;
        _message = status == 'active'
            ? 'Langganan aktif dan diverifikasi server.'
            : null;
      });
      if (status == 'active') _pollTimer?.cancel();
    } catch (e) {
      if (mounted) {
        setState(
          () => _message =
              'Status lisensi belum dapat diperiksa: ${_cleanError(e)}',
        );
      }
    }
  }

  Future<void> _checkout() async {
    if (_customerToken == null) {
      setState(
        () => _message = 'Masuk ke akun billing sebelum membeli langganan.',
      );
      return;
    }
    if (_devicePk == null || _selectedPlan == null) {
      setState(() => _message = 'Pilih paket langganan terlebih dahulu.');
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final result =
          await ref
                  .read(billingClientProvider)
                  .createLicenseCheckout(
                    customerToken: _customerToken!,
                    devicePk: _devicePk!,
                    planCode: _selectedPlan!,
                  )
              as Map;
      final paymentUrl = result['payment_url']?.toString();
      if (paymentUrl == null || paymentUrl.isEmpty) {
        throw Exception(
          'Server belum menyediakan tautan pembayaran Midtrans untuk pesanan ini.',
        );
      }
      final uri = Uri.tryParse(paymentUrl);
      if (uri == null || uri.scheme != 'https') {
        throw Exception('Tautan pembayaran dari server tidak valid.');
      }
      await openExternalUrl(uri.toString());
      _pollTimer?.cancel();
      _pollTimer = Timer.periodic(
        const Duration(seconds: 10),
        (_) => _refreshLicense(),
      );
      setState(
        () => _message =
            'Pesanan ${result['order_code'] ?? ''} dibuat. Selesaikan pembayaran; status akan diperiksa oleh server.',
      );
    } catch (e) {
      if (mounted) setState(() => _message = _cleanError(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  String _cleanError(Object error) =>
      error.toString().replaceFirst('Exception: ', '');
  String _duration(Duration d) {
    if (d.inDays > 0) return '${d.inDays} hari';
    if (d.inHours > 0) return '${d.inHours} jam';
    return '${d.inMinutes} menit';
  }

  @override
  Widget build(BuildContext context) {
    final trial = ref.watch(trialStatusProvider);
    return OwnerFormTheme(
      child: Scaffold(
        backgroundColor: const Color(0xFFF4F6F8),
        appBar: AppBar(
          title: const Text('Lisensi & Langganan'),
          leading: IconButton(
            icon: const Icon(Icons.arrow_back),
            onPressed: () => context.go('/'),
          ),
        ),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _license?['status'] == 'active'
                          ? 'Status: Lisensi Aktif'
                          : 'Status: ${trial.when(data: (t) => t.active ? 'Trial' : 'Trial berakhir', loading: () => 'Memeriksa trial…', error: (_, _) => 'Trial tidak dapat diperiksa')} ',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    trial.when(
                      data: (t) => Text(
                        t.active
                            ? 'Trial 7 hari · sisa ${_duration(t.remaining)} · berakhir ${t.endsAt.toLocal().toString().substring(0, 10)}'
                            : 'Trial berakhir ${t.endsAt.toLocal().toString().substring(0, 10)}. Aktivasi berbayar diperlukan.',
                      ),
                      loading: () => const LinearProgressIndicator(),
                      error: (e, _) => Text('Gagal membaca trial: $e'),
                    ),
                    const SizedBox(height: 10),
                    const Text(
                      'File .posreq adalah permintaan untuk diunggah ke dashboard billing. File .poslic diterbitkan server setelah pembayaran dan diunduh dari dashboard.',
                    ),
                    if (_subscription != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        'Langganan server: ${(_subscription!['plan'] is Map ? (_subscription!['plan']['name'] ?? _subscription!['plan']['code']) : null) ?? _subscription!['status'] ?? 'aktif'} · ${_subscription!['plan'] is Map ? (_subscription!['plan']['remaining_text'] ?? '') : ''}',
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      _customerToken == null
                          ? 'Akun Billing'
                          : 'Akun Billing Terhubung',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    if (_customerToken == null) ...[
                      const SizedBox(height: 12),
                      TextField(
                        controller: _email,
                        keyboardType: TextInputType.emailAddress,
                        decoration: const InputDecoration(
                          labelText: 'Email akun billing',
                        ),
                      ),
                      TextField(
                        controller: _password,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Password',
                        ),
                      ),
                      if (_register)
                        TextField(
                          controller: _store,
                          decoration: const InputDecoration(
                            labelText: 'Nama toko',
                          ),
                        ),
                      TextButton(
                        onPressed: _busy
                            ? null
                            : () => setState(() => _register = !_register),
                        child: Text(
                          _register
                              ? 'Sudah punya akun? Masuk'
                              : 'Belum punya akun? Daftar',
                        ),
                      ),
                      FilledButton(
                        onPressed: _busy ? null : _authenticate,
                        child: Text(
                          _busy
                              ? 'Menghubungkan…'
                              : _register
                              ? 'Daftar dan Hubungkan Perangkat'
                              : 'Masuk dan Hubungkan Perangkat',
                        ),
                      ),
                      if (_message != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          _message!,
                          style: TextStyle(
                            color: _message!.contains('aktif')
                                ? Colors.green.shade800
                                : Colors.blueGrey.shade200,
                          ),
                        ),
                      ],
                    ] else ...[
                      const SizedBox(height: 8),
                      Text(_email.text),
                      if (_devicePk == null) ...[
                        TextField(
                          controller: _store,
                          decoration: const InputDecoration(
                            labelText: 'Nama toko',
                          ),
                        ),
                        FilledButton(
                          onPressed: _busy
                              ? null
                              : () async {
                                  setState(() {
                                    _busy = true;
                                    _message = null;
                                  });
                                  try {
                                    await _registerDevice();
                                    await _refreshLicense();
                                  } catch (e) {
                                    if (mounted) {
                                      setState(() => _message = _cleanError(e));
                                    }
                                  } finally {
                                    if (mounted) setState(() => _busy = false);
                                  }
                                },
                          child: const Text('Hubungkan perangkat'),
                        ),
                      ],
                      OutlinedButton(
                        onPressed: _busy
                            ? null
                            : () async {
                                await _storage.delete(
                                  key: 'billing.customer_token',
                                );
                                await _storage.delete(
                                  key: 'billing.device_token',
                                );
                                await _storage.delete(key: 'billing.device_pk');
                                if (mounted) {
                                  setState(() {
                                    _customerToken = null;
                                    _deviceToken = null;
                                    _devicePk = null;
                                    _license = null;
                                  });
                                }
                              },
                        child: const Text('Putuskan akun billing'),
                      ),
                    ],
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: _busy ? null : _saveRequestAndOpenDashboard,
                      icon: const Icon(Icons.upload_file),
                      label: const Text(
                        'Buat .posreq & buka dashboard billing',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      'Paket Langganan',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 10),
                    if (_plans.isEmpty)
                      OutlinedButton.icon(
                        onPressed: _loadPlans,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Muat ulang paket'),
                      )
                    else ...[
                      DropdownButtonFormField<String>(
                        initialValue: _selectedPlan,
                        decoration: const InputDecoration(
                          labelText: 'Pilih paket',
                        ),
                        items: _plans
                            .map(
                              (p) => DropdownMenuItem(
                                value: p['code']?.toString(),
                                child: Text(
                                  '${p['name']} · Rp ${p['price_idr']}',
                                ),
                              ),
                            )
                            .toList(),
                        onChanged: (v) => setState(() => _selectedPlan = v),
                      ),
                      const SizedBox(height: 12),
                      FilledButton.icon(
                        onPressed: _busy ? null : _checkout,
                        icon: const Icon(Icons.lock_open),
                        label: const Text('Lanjutkan ke pembayaran'),
                      ),
                    ],
                    OutlinedButton.icon(
                      onPressed: _deviceToken == null || _busy
                          ? null
                          : _refreshLicense,
                      icon: const Icon(Icons.sync),
                      label: const Text('Periksa aktivasi dari server'),
                    ),
                  ],
                ),
              ),
            ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(
                  _message!,
                  style: TextStyle(
                    color: _message!.contains('aktif')
                        ? Colors.green.shade800
                        : Colors.blueGrey.shade800,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
