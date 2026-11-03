// App-level smoke test.
//
// The previous content was the untouched Flutter counter template, which never
// matched this app and failed on `find.text('0')`. This replaces it with a real
// check of the app shell: the splash renders, then the login screen appears.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kasirin_mobile/main.dart';
import 'package:kasirin_mobile/providers.dart';
import 'package:kasirin_mobile/services/trial_service.dart';
import 'package:kasirin_mobile/views/auth/login_view.dart';

void main() {
  testWidgets('splash lalu layar login tampil', (tester) async {
    final now = DateTime.utc(2026, 11, 1);
    final container = ProviderContainer(
      overrides: [
        // No real database or secure storage in a widget test.
        repositoryFutureProvider.overrideWith(
          (ref) async => throw StateError('setup probe'),
        ),
        trialStatusProvider.overrideWith(
          (ref) async => TrialStatus(
            active: true,
            startedAt: now,
            endsAt: now.add(const Duration(days: 7)),
            remaining: const Duration(days: 4),
          ),
        ),
        billingLicenseActiveProvider.overrideWith((ref) async => true),
      ],
    );
    addTearDown(container.dispose);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const KasirinApp(),
      ),
    );

    // The startup splash is shown first.
    expect(find.text('Kasirin · Memulai Aplikasi'), findsOneWidget);

    // After the splash delay the login screen takes over.
    await tester.pump(const Duration(milliseconds: 1900));
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.byType(LoginView), findsOneWidget);
    expect(find.text('Masuk Kasirin'), findsOneWidget);
    expect(find.text('Username'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);

    // No layout overflow or other render exception on the login screen.
    expect(tester.takeException(), isNull);
  });
}
