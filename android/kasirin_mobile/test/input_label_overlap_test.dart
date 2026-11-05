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

Future<ProviderContainer> _pump(
  WidgetTester tester,
  Widget view, {
  Size viewport = const Size(360, 800),
}) async {
  tester.view.physicalSize = viewport * 3;
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
      child: MaterialApp(theme: container.read(themeProvider), home: view),
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

    _expectLoginLabelsAboveFields(tester);
  });

  testWidgets('login labels stay clear of inputs at desktop width', (
    tester,
  ) async {
    await _pump(tester, const LoginView(), viewport: const Size(1280, 900));

    _expectLoginLabelsAboveFields(tester);
  });

  testWidgets('setup owner inputs use light surface styling', (tester) async {
    await _pump(tester, const SetupOwnerView());
    _expectLightInputs(tester, 'SetupOwnerView');

    _expectSetupLabelsAboveFields(tester);

    await tester.tap(find.byType(TextFormField).first);
    await tester.pump(const Duration(milliseconds: 300));
    _drain(tester);
    _expectSetupLabelsAboveFields(tester);
  });

  testWidgets('setup labels stay clear of inputs at desktop width', (
    tester,
  ) async {
    await _pump(
      tester,
      const SetupOwnerView(),
      viewport: const Size(1280, 900),
    );
    _expectSetupLabelsAboveFields(tester);
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

void _expectLoginLabelsAboveFields(WidgetTester tester) {
  final fields = find.byType(InputDecorator);
  expect(fields, findsNWidgets(2));

  for (final (label, index) in [('Username', 0), ('Password', 1)]) {
    final labelRect = tester.getRect(find.text(label));
    final fieldRect = tester.getRect(fields.at(index));
    expect(
      labelRect.bottom,
      lessThan(fieldRect.top),
      reason: '$label label must sit above, not overlap, its input',
    );
  }
}

void _expectSetupLabelsAboveFields(WidgetTester tester) {
  const labels = [
    'Nama Toko',
    'Nama Lengkap Pemilik',
    'Username',
    'Password',
    'Konfirmasi Password',
  ];
  final fields = find.byType(InputDecorator);
  expect(fields, findsNWidgets(labels.length));

  for (var i = 0; i < labels.length; i++) {
    final labelRect = tester.getRect(find.text(labels[i]));
    final fieldRect = tester.getRect(fields.at(i));
    expect(
      labelRect.bottom,
      lessThan(fieldRect.top),
      reason: '${labels[i]} label must sit above, not overlap, its input',
    );
    if (i + 1 < labels.length) {
      final nextLabelRect = tester.getRect(find.text(labels[i + 1]));
      expect(
        nextLabelRect.top,
        greaterThanOrEqualTo(fieldRect.bottom),
        reason: '${labels[i + 1]} label must not overlap ${labels[i]} input',
      );
    }
  }
}
