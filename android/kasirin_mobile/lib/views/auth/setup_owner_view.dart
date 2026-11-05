import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers.dart';
import '../owner/owner_widgets.dart';

class SetupOwnerView extends ConsumerStatefulWidget {
  const SetupOwnerView({super.key});

  @override
  ConsumerState<SetupOwnerView> createState() => _SetupOwnerViewState();
}

class _SetupOwnerViewState extends ConsumerState<SetupOwnerView> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _usernameController = TextEditingController();
  final _storeNameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _isPasswordVisible = false;
  bool _isLoading = false;
  bool _includeDemoData = true;
  String? _errorMessage;

  @override
  void dispose() {
    _fullNameController.dispose();
    _usernameController.dispose();
    _storeNameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _submitSetup() async {
    if (!_formKey.currentState!.validate()) return;

    if (_passwordController.text != _confirmPasswordController.text) {
      setState(() {
        _errorMessage = 'Konfirmasi password tidak cocok.';
      });
      return;
    }

    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final repository = await ref.read(repositoryFutureProvider.future);
      final ownerId = await repository.createOwner(
        username: _usernameController.text.trim(),
        fullName: _fullNameController.text.trim(),
        password: _passwordController.text,
        storeName: _storeNameController.text.trim().isEmpty
            ? 'Toko Kasirin'
            : _storeNameController.text.trim(),
      );

      String? demoDataError;
      if (_includeDemoData) {
        try {
          await repository.seedDemoData(ownerId);
        } catch (error) {
          // Keep first-run setup usable if demo records cannot be added.
          demoDataError = error.toString().replaceFirst('StateError: ', '');
        }
      }

      // Log in immediately
      ref
          .read(authNotifierProvider.notifier)
          .setAuthenticated(
            userId: ownerId,
            username: _usernameController.text.trim(),
            fullName: _fullNameController.text.trim(),
            role: 'OWNER',
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              demoDataError == null
                  ? (_includeDemoData
                        ? 'Akun dan data demo berhasil dibuat. Kasir demo: kasir_demo / kasir123.'
                        : 'Akun Pemilik berhasil dibuat! Selamat datang di Kasirin.')
                  : 'Akun dibuat, tetapi data demo gagal dimuat: $demoDataError',
            ),
            backgroundColor: demoDataError == null
                ? const Color(0xFF18794E)
                : const Color(0xFFB42318),
          ),
        );
        context.go('/');
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _errorMessage = e.toString().replaceFirst('StateError: ', '');
        });
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return OwnerFormTheme(
      child: Scaffold(
        backgroundColor: const Color(0xFFF4F6F8),
        appBar: AppBar(title: const Text('Setup Toko & Akun Pemilik')),
        bottomNavigationBar: const SafeArea(top: false, child: TrialBanner()),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: const BorderSide(color: Color(0xFFD7DEE5)),
                  ),
                  color: Colors.white,
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Form(
                      key: _formKey,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Row(
                            children: [
                              Container(
                                width: 48,
                                height: 48,
                                decoration: BoxDecoration(
                                  color: const Color(0xFF006EAE)
                                      .withValues(alpha: 0.1),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: const Icon(
                                  Icons.storefront_rounded,
                                  color: Color(0xFF006EAE),
                                  size: 28,
                                ),
                              ),
                              const SizedBox(width: 16),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      'Inisialisasi Toko',
                                      style: theme.textTheme.titleLarge
                                          ?.copyWith(
                                            fontWeight: FontWeight.bold,
                                            color: const Color(0xFF17212B),
                                          ),
                                    ),
                                    Text(
                                      'Buat akun pemilik pertama untuk mulai menggunakan Kasirin.',
                                      maxLines: 2,
                                      softWrap: true,
                                      style: theme.textTheme.bodyMedium
                                          ?.copyWith(
                                            color: const Color(0xFF586575),
                                          ),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 24),
                          const Divider(color: Color(0xFFD7DEE5)),
                          const SizedBox(height: 16),
                          if (_errorMessage != null) ...[
                            Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                color: const Color(0xFFB42318)
                                    .withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(8),
                                border: Border.all(
                                  color: const Color(0xFFB42318),
                                ),
                              ),
                              child: Row(
                                children: [
                                  const Icon(
                                    Icons.error_outline,
                                    color: Color(0xFFB42318),
                                    size: 20,
                                  ),
                                  const SizedBox(width: 8),
                                  Expanded(
                                    child: Text(
                                      _errorMessage!,
                                      style: const TextStyle(
                                        color: Color(0xFFB42318),
                                        fontSize: 13,
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(height: 16),
                          ],
                          const Text(
                            'Nama Toko',
                            style: TextStyle(
                              color: ownerInk,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _storeNameController,
                            decoration: const InputDecoration(
                              hintText: 'Contoh: Toko Berkah Sejahtera',
                              prefixIcon: Icon(Icons.business_outlined),
                            ),
                            textInputAction: TextInputAction.next,
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Nama toko wajib diisi.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Nama Lengkap Pemilik',
                            style: TextStyle(
                              color: ownerInk,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _fullNameController,
                            decoration: const InputDecoration(
                              hintText: 'Contoh: Ahmad Fadli',
                              prefixIcon: Icon(Icons.badge_outlined),
                            ),
                            textInputAction: TextInputAction.next,
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Nama lengkap wajib diisi.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Username',
                            style: TextStyle(
                              color: ownerInk,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _usernameController,
                            decoration: const InputDecoration(
                              hintText: 'Username untuk login',
                              prefixIcon: Icon(Icons.person_outline),
                            ),
                            textInputAction: TextInputAction.next,
                            validator: (value) {
                              if (value == null || value.trim().isEmpty) {
                                return 'Username wajib diisi.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Password',
                            style: TextStyle(
                              color: ownerInk,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _passwordController,
                            obscureText: !_isPasswordVisible,
                            decoration: InputDecoration(
                              prefixIcon: const Icon(Icons.lock_outline),
                              suffixIcon: IconButton(
                                icon: Icon(
                                  _isPasswordVisible
                                      ? Icons.visibility_off_outlined
                                      : Icons.visibility_outlined,
                                ),
                                onPressed: () {
                                  setState(() {
                                    _isPasswordVisible = !_isPasswordVisible;
                                  });
                                },
                              ),
                            ),
                            textInputAction: TextInputAction.next,
                            validator: (value) {
                              if (value == null || value.length < 8) {
                                return 'Password minimal 8 karakter.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 16),
                          const Text(
                            'Konfirmasi Password',
                            style: TextStyle(
                              color: ownerInk,
                              fontSize: 14,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const SizedBox(height: 6),
                          TextFormField(
                            controller: _confirmPasswordController,
                            obscureText: !_isPasswordVisible,
                            decoration: const InputDecoration(
                              prefixIcon: Icon(Icons.lock_reset_outlined),
                            ),
                            textInputAction: TextInputAction.done,
                            onFieldSubmitted: (_) => _submitSetup(),
                            validator: (value) {
                              if (value == null || value.isEmpty) {
                                return 'Konfirmasi password wajib diisi.';
                              }
                              return null;
                            },
                          ),
                          const SizedBox(height: 8),
                          CheckboxListTile(
                            contentPadding: EdgeInsets.zero,
                            value: _includeDemoData,
                            controlAffinity: ListTileControlAffinity.leading,
                            title: const Text(
                              'Isi data contoh untuk mencoba fitur',
                            ),
                            subtitle: const Text(
                              'Produk, stok rendah, pembelian, harga grosir, dan transaksi penjualan.',
                            ),
                            onChanged: _isLoading
                                ? null
                                : (value) => setState(
                                    () => _includeDemoData = value ?? false,
                                  ),
                          ),
                          const SizedBox(height: 28),
                          SizedBox(
                            height: 52,
                            child: ElevatedButton(
                              onPressed: _isLoading ? null : _submitSetup,
                              style: ElevatedButton.styleFrom(
                                backgroundColor: const Color(0xFF006EAE),
                                foregroundColor: Colors.white,
                                shape: RoundedRectangleBorder(
                                  borderRadius: BorderRadius.circular(10),
                                ),
                              ),
                              child: _isLoading
                                  ? const SizedBox(
                                      height: 22,
                                      width: 22,
                                      child: CircularProgressIndicator(
                                        strokeWidth: 2,
                                        valueColor: AlwaysStoppedAnimation(
                                          Colors.white,
                                        ),
                                      ),
                                    )
                                  : const Text(
                                      'Buat Akun & Mulai POS',
                                      style: TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
