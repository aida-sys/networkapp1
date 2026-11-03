// Regression test for the login/setup input label overlap.
//
// The app theme is dark, so the global InputDecorationTheme fills inputs with
// #131B2E and colors labels #DAE2FD. Login and setup draw those inputs on a
// white card, which made the floating label sit on the border with no backing
// and read as overlapping the field. These tests pin the light-surface
// decoration so the bug cannot come back.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:kasirin_mobile/providers.dart';
import 'package:kasirin_mobile/services/trial_service.dart';
import 'package:kasirin_mobile/views/auth/login_view.dart';
import 'package:kasirin_mobile/views/auth/setup_owner_view.dart';
import 'package:kasirin_mobile/views/owner/owner_widgets.dart';

double _luminance(Color c) => c.computeLuminance();

double _contrast(Color a, Color b) {
  final la = _luminance(a);
  final lb = _luminance(b);
  final hi = la > lb ? la : lb;
  final lo = la > lb ? lb : la;
  return (hi + 0.05) / (lo + 0.05);
}

void _drain(WidgetTester tester) {
  while (tester.takeException() != null) {}
}

Future<ProviderContainer> _pump(WidgetTester tester, Widget view) async {
  tester.view.physicalSize = const Size(1080, 2400);
  tester.view.devicePixelRatio = 3.0;
  addTearDown(tester.view.reset);

  final now = DateTime(2026, 11, 4);
  final container = ProviderContainer(
    overrides: [
      repositoryFutureProvider.overrideWith(
        (ref) async => throw StateError('probe'),
      ),
      trialStatusProvider.overrideWith(
        (ref) async => TrialStatus(
          active: true,
          startedAt: now,
          endsAt: now.add(const Duration(days: 7)),
          remaining: const Duration(days: 7),
        ),
      ),
      billingLicenseActiveProvider.overrideWith((ref) async => true),
    ],
  );
  addTearDown(container.dispose);

  await tester.pumpWidget(
    UncontrolledProviderScope(
      container: container,
      child: MaterialApp(
        theme: container.read(themeProvider),
        home: view,
      ),
    ),
  );
  _drain(tester);
  await tester.pump(const Duration(milliseconds: 200));
  _drain(tester);
  return container;
}

/// Asserts every visible input on screen uses a light fill and a readable
/// label, i.e. the light-surface decoration actually reached the field.
void _expectLightInputs(WidgetTester tester, String screen) {
  final fields = find.byType(TextField);
  expect(fields, findsWidgets, reason: '$screen should show input fields');

  final theme = Theme.of(tester.element(fields.first));
  final deco = theme.inputDecorationTheme;

  expect(
    deco.fillColor,
    ownerFieldFill,
    reason: '$screen inputs must use the light fill, not the dark app fill',
  );
  expect(
    _luminance(deco.fillColor!),
    greaterThan(0.8),
    reason: '$screen input fill must be light',
  );

  // The floating label must be readable against the field fill.
  final floating = deco.floatingLabelStyle?.color;
  expect(floating, isNotNull, reason: '$screen needs a floating label style');
  expect(
    _contrast(floating!, deco.fillColor!),
    greaterThan(4.5),
    reason: '$screen floating label must hit 4.5:1 against the fill',
  );

  // The resting label must also be readable against the fill.
  final resting = deco.labelStyle?.color;
  expect(resting, isNotNull, reason: '$screen needs a resting label style');
  expect(
    _contrast(resting!, deco.fillColor!),
    greaterThan(4.5),
    reason: '$screen resting label must hit 4.5:1 against the fill',
  );
}

void main() {
  testWidgets('login inputs use light surface styling', (tester) async {
    await _pump(tester, const LoginView());
    _expectLightInputs(tester, 'LoginView');

    // Label geometry: the floating label straddles the top border by design,
    // so it must have an opaque backing. With a light fill on a white card the
    // label reads as part of the field instead of colliding with it.
    await tester.enterText(find.byType(TextField).first, 'owner');
    _drain(tester);
    // The text cursor blinks forever, so pumpAndSettle would never settle.
    await tester.pump(const Duration(milliseconds: 300));
    _drain(tester);

    final labelRect = tester.getRect(find.text('Username'));
    final fillRect = tester.getRect(find.byType(InputDecorator).first);
    // ignore: avoid_print
    print('LOGIN label=$labelRect fill=$fillRect');
    expect(
      labelRect.top < fillRect.top,
      isTrue,
      reason: 'floating label should sit on the top border',
    );
    expect(
      labelRect.center.dy,
      lessThan(fillRect.top + 4),
      reason: 'floating label should not sink into the field body',
    );
  });

  testWidgets('setup owner inputs use light surface styling', (tester) async {
    await _pump(tester, const SetupOwnerView());
    _expectLightInputs(tester, 'SetupOwnerView');

    // All five fields must be present and non-overlapping vertically.
    final fields = find.byType(TextField);
    expect(fields, findsNWidgets(5));

    final rects = <Rect>[];
    for (var i = 0; i < 5; i++) {
      rects.add(tester.getRect(fields.at(i)));
    }
    for (var i = 1; i < rects.length; i++) {
      expect(
        rects[i].top,
        greaterThanOrEqualTo(rects[i - 1].bottom),
        reason: 'field $i must not overlap field ${i - 1}',
      );
    }
  });

  testWidgets('dark app inputs keep the dark theme untouched', (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final theme = container.read(themeProvider);

    // Guard: the fix must be scoped to light surfaces only.
    expect(theme.inputDecorationTheme.fillColor, const Color(0xFF131B2E));
    expect(theme.brightness, Brightness.dark);
  });
}
