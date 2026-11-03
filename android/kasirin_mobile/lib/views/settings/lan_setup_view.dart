import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers.dart';
import '../owner/owner_widgets.dart';
import '../../remote/pos_api_client.dart';
import '../../services/app_mode.dart';

/// Layar setup koneksi ke server POS LAN.
///
/// Alamat server tidak pernah di-hard-code: pengguna mengetik alamat komputer
/// server (mis. `http://192.168.1.10:8002`), lalu menekan "Uji Koneksi" yang
/// benar-benar memanggil `/health` sebelum disimpan.
class LanSetupView extends ConsumerStatefulWidget {
  const LanSetupView({super.key});

  @override
  ConsumerState<LanSetupView> createState() => _LanSetupViewState();
}

class _LanSetupViewState extends ConsumerState<LanSetupView> {
  final _urlController = TextEditingController();
  bool _testing = false;
  bool _saving = false;
  String? _statusMessage;
  bool _statusOk = false;

  @override
  void initState() {
    super.initState();
    final connection = ref.read(appModeProvider).connection;
    _urlController.text = connection.baseUrl;
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  String _normalize(String raw) {
    var value = raw.trim();
    if (value.isEmpty) return '';
    if (!value.startsWith('http://') && !value.startsWith('https://')) {
      value = 'http://$value';
    }
    return value.replaceAll(RegExp(r'/+$'), '');
  }

  Future<void> _testConnection() async {
    final url = _normalize(_urlController.text);
    if (url.isEmpty) {
      setState(() {
        _statusOk = false;
        _statusMessage = 'Alamat server wajib diisi.';
      });
      return;
    }

    setState(() {
      _testing = true;
      _statusMessage = null;
    });

    final client = PosApiClient(baseUrl: url);
    try {
      final health = await client.health();
      final database = health['database'] ?? 'unknown';
      setState(() {
        _statusOk = database == 'ok';
        _statusMessage = _statusOk
            ? 'Server terhubung. Database: $database. Versi: ${health['version'] ?? '-'}'
            : 'Server menjawab tetapi database bermasalah ($database).';
      });
    } on PosApiUnavailableException catch (error) {
      setState(() {
        _statusOk = false;
        _statusMessage = error.message;
      });
    } on PosApiException catch (error) {
      setState(() {
        _statusOk = false;
        _statusMessage = error.message;
      });
    } finally {
      client.close();
      if (mounted) setState(() => _testing = false);
    }
  }

  Future<void> _save() async {
    final url = _normalize(_urlController.text);
    if (url.isEmpty) {
      setState(() {
        _statusOk = false;
        _statusMessage = 'Alamat server wajib diisi.';
      });
      return;
    }

    setState(() => _saving = true);
    try {
      await ref
          .read(appModeProvider.notifier)
          .useLan(LanConnection(baseUrl: url, deviceId: 'mobile'));
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Mode LAN aktif. Silakan login.'),
          backgroundColor: Color(0xFF18794E),
        ),
      );
      Navigator.of(context).pop(true);
    } finally {
      if (mounted) setState(() => _saving = false);
    }
  }

  Future<void> _useStandalone() async {
    await ref.read(appModeProvider.notifier).useStandalone();
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Mode standalone aktif (database lokal).'),
        backgroundColor: Color(0xFF18794E),
      ),
    );
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final modeState = ref.watch(appModeProvider);

    return OwnerFormTheme(
      child: Scaffold(
        appBar: AppBar(title: const Text('Koneksi Server')),
        body: ListView(
          padding: const EdgeInsets.all(20),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Mode aplikasi', style: theme.textTheme.titleLarge),
                    const SizedBox(height: 8),
                    Text(
                      modeState.isLan
                          ? 'Saat ini: LAN — data dari server pusat.'
                          : 'Saat ini: Standalone — data di perangkat ini.',
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      'Mode standalone tetap berjalan seperti biasa. '
                      'Berpindah ke LAN tidak memindahkan data lama secara '
                      'otomatis; migrasi dilakukan sekali di komputer server.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurface.withValues(
                          alpha: 0.7,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Alamat server POS',
                      style: theme.textTheme.titleLarge,
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _urlController,
                      keyboardType: TextInputType.url,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Alamat server',
                        hintText: 'http://192.168.1.10:8002',
                        helperText:
                            'IP komputer server di jaringan toko, port 8002.',
                      ),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        OutlinedButton.icon(
                          onPressed: _testing ? null : _testConnection,
                          icon: _testing
                              ? const SizedBox(
                                  width: 16,
                                  height: 16,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.wifi_tethering),
                          label: const Text('Uji Koneksi'),
                        ),
                        const SizedBox(width: 12),
                        FilledButton.icon(
                          onPressed: _saving ? null : _save,
                          icon: const Icon(Icons.save),
                          label: const Text('Simpan & Pakai LAN'),
                        ),
                      ],
                    ),
                    if (_statusMessage != null) ...[
                      const SizedBox(height: 12),
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Icon(
                            _statusOk
                                ? Icons.check_circle
                                : Icons.error_outline,
                            color: _statusOk
                                ? const Color(0xFF18794E)
                                : theme.colorScheme.error,
                            size: 20,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _statusMessage!,
                              style: theme.textTheme.bodyMedium,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Kembali ke standalone',
                      style: theme.textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Data lokal di perangkat ini tidak diubah dan tetap bisa '
                      'dipakai seperti sebelumnya.',
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: _useStandalone,
                      icon: const Icon(Icons.phone_android),
                      label: const Text('Pakai Standalone'),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
