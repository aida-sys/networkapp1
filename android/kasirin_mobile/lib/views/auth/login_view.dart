import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers.dart';
import '../owner/owner_widgets.dart';

class LoginView extends ConsumerStatefulWidget {
  const LoginView({super.key});

  @override
  ConsumerState<LoginView> createState() => _LoginViewState();
}

class _LoginViewState extends ConsumerState<LoginView> {
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isPasswordVisible = false;
  bool _isLoading = false;
  bool _checkingSetup = true;

  @override
  void initState() {
    super.initState();
    _checkInitialSetup();
  }

  Future<void> _checkInitialSetup() async {
    try {
      final repository = await ref.read(repositoryFutureProvider.future);
      final needed = await repository.setupRequired();
      if (needed && mounted) {
        context.go('/setup');
        return;
      }
    } catch (_) {
      // Ignored: repository will handle if DB error
    } finally {
      if (mounted) {
        setState(() => _checkingSetup = false);
      }
    }
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;

    if (username.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Username dan password wajib diisi.'),
          backgroundColor: Color(0xFFB42318),
        ),
      );
      return;
    }

    setState(() => _isLoading = true);

    try {
      final repository = await ref.read(repositoryFutureProvider.future);
      final result = await repository.login(username, password);

      final role = result.read<String>('role_name');
      final fullName = result.read<String>('full_name');
      final userId = result.read<int>('id');

      ref
          .read(authNotifierProvider.notifier)
          .setAuthenticated(
            userId: userId,
            username: username,
            fullName: fullName,
            role: role,
          );

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Selamat datang, $fullName!'),
            backgroundColor: const Color(0xFF18794E),
          ),
        );

        if (role == 'CASHIER') {
          context.go('/cashier');
        } else {
          context.go('/');
        }
      }
    } catch (e) {
      if (mounted) {
        final message = e.toString().replaceFirst('StateError: ', '');
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(message),
            backgroundColor: const Color(0xFFB42318),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isLoading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_checkingSetup) {
      return Scaffold(
        backgroundColor: Color(0xFFF4F6F8),
        appBar: AppBar(title: const Text('Memuat akun')),
        body: const Center(
          child: CircularProgressIndicator(color: Color(0xFF006EAE)),
        ),
      );
    }

    final theme = Theme.of(context);

    return OwnerFormTheme(
      child: Scaffold(
        backgroundColor: const Color(0xFFF4F6F8),
        appBar: AppBar(title: const Text('Masuk Kasirin')),
        bottomNavigationBar: const SafeArea(top: false, child: TrialBanner()),
        body: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Card(
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: const BorderSide(color: Color(0xFFD7DEE5)),
                  ),
                  color: Colors.white,
                  child: Padding(
                    padding: const EdgeInsets.all(28),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Center(
                          child: Column(
                            children: [
                              Container(
                                width: 64,
                                height: 64,
                                decoration: BoxDecoration(
                                  color: const Color(0xFF006EAE),
                                  borderRadius: BorderRadius.circular(16),
                                ),
                                child: const Icon(
                                  Icons.point_of_sale_rounded,
                                  size: 36,
                                  color: Colors.white,
                                ),
                              ),
                              const SizedBox(height: 16),
                              Text(
                                'Kasirin POS',
                                style: theme.textTheme.headlineSmall?.copyWith(
                                  fontWeight: FontWeight.bold,
                                  color: const Color(0xFF17212B),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                'Masuk ke sistem kasir toko',
                                style: theme.textTheme.bodyMedium?.copyWith(
                                  color: const Color(0xFF586575),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 32),
                        const Text(
                          'Username',
                          style: TextStyle(
                            color: ownerInk,
                            fontSize: 14,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 6),
                        Semantics(
                          label: 'Username',
                          child: TextField(
                            controller: _usernameController,
                            style: const TextStyle(
                              color: ownerInk,
                              fontSize: 15,
                            ),
                            decoration: const InputDecoration(
                              hintText: 'Masukkan username Anda',
                              prefixIcon: Icon(Icons.person_outline),
                            ),
                            textInputAction: TextInputAction.next,
                          ),
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
                        Semantics(
                          label: 'Password',
                          child: TextField(
                            controller: _passwordController,
                            obscureText: !_isPasswordVisible,
                            style: const TextStyle(
                              color: ownerInk,
                              fontSize: 15,
                            ),
                            decoration: InputDecoration(
                              hintText: 'Masukkan password Anda',
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
                            textInputAction: TextInputAction.done,
                            onSubmitted: (_) => _login(),
                          ),
                        ),
                        const SizedBox(height: 24),
                        SizedBox(
                          height: 52,
                          child: ElevatedButton(
                            onPressed: _isLoading ? null : _login,
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
                                    'Masuk',
                                    style: TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                          ),
                        ),
                        const SizedBox(height: 20),
                        Center(
                          child: TextButton.icon(
                            onPressed: () => context.go('/setup'),
                            icon: const Icon(
                              Icons.settings_backup_restore,
                              size: 16,
                            ),
                            label: const Text(
                              'Setup Toko Baru',
                              style: TextStyle(fontSize: 13),
                            ),
                          ),
                        ),
                        Center(
                          child: TextButton.icon(
                            onPressed: () => context.go('/connection'),
                            icon: const Icon(Icons.lan_outlined, size: 16),
                            label: const Text(
                              'Koneksi Server LAN',
                              style: TextStyle(fontSize: 13),
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
    );
  }
}
