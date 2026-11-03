// Regression test for the trial banner layout bugs.
//
// Two real defects lived here:
// 1. The marquee Row was forced to the banner width and overflowed by the full
//    text width, throwing a RenderFlex overflow on every screen showing it.
// 2. The static (reduced-motion) fallback used an Align without heightFactor,
//    which expanded the banner to the entire screen height and squeezed the
//    page body down to nothing.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kasirin_mobile/providers.dart';
import 'package:kasirin_mobile/services/trial_service.dart';
import 'package:kasirin_mobile/views/owner/owner_widgets.dart';

void main() {
  final now = DateTime.utc(2026, 11, 1);

  ProviderContainer buildContainer({required bool active}) {
    return ProviderContainer(
      overrides: [
        billingLicenseActiveProvider.overrideWith((ref) async => false),
        trialStatusProvider.overrideWith(
          (ref) async => TrialStatus(
            active: active,
            startedAt: now,
            endsAt: now.add(const Duration(days: 7)),
            remaining: const Duration(days: 4),
          ),
        ),
      ],
    );
  }

  Future<void> pumpBanner(
    WidgetTester tester,
    ProviderContainer container, {
    required bool disableAnimations,
  }) async {
    tester.view.physicalSize = const Size(400, 850);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MediaQuery(
          data: MediaQueryData.fromView(tester.view)
              .copyWith(disableAnimations: disableAnimations),
          child: const MaterialApp(
            home: Scaffold(
              body: SizedBox.expand(),
              bottomNavigationBar: SafeArea(top: false, child: TrialBanner()),
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 200));
  }

  testWidgets('banner does not overflow and stays banner-sized', (
    tester,
  ) async {
    final container = buildContainer(active: true);
    addTearDown(container.dispose);

    await pumpBanner(tester, container, disableAnimations: true);

    // No RenderFlex overflow.
    expect(tester.takeException(), isNull);

    final bannerRect = tester.getRect(find.byType(TrialBanner));
    expect(bannerRect.height, lessThan(120));
    expect(bannerRect.width, 400);

    // The body must keep the rest of the screen.
    final bodyRect = tester.getRect(find.byType(SizedBox).first);
    expect(bodyRect.height, greaterThan(600));
  });

  testWidgets('animated marquee also does not overflow', (tester) async {
    final container = buildContainer(active: true);
    addTearDown(container.dispose);

    await pumpBanner(tester, container, disableAnimations: false);

    expect(tester.takeException(), isNull);
    final bannerRect = tester.getRect(find.byType(TrialBanner));
    expect(bannerRect.height, lessThan(120));
  });

  testWidgets('no banner is laid out when the license is active', (
    tester,
  ) async {
    final container = ProviderContainer(
      overrides: [
        billingLicenseActiveProvider.overrideWith((ref) async => true),
        trialStatusProvider.overrideWith(
          (ref) async => TrialStatus(
            active: true,
            startedAt: now,
            endsAt: now.add(const Duration(days: 7)),
            remaining: const Duration(days: 4),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);

    await pumpBanner(tester, container, disableAnimations: false);

    expect(tester.takeException(), isNull);
    expect(tester.getSize(find.byType(TrialBanner)).height, 0);
  });
}
