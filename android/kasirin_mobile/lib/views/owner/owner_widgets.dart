import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers.dart';

const ownerInk = Color(0xFF17212B);
const ownerMuted = Color(0xFF64748B);
const ownerBlue = Color(0xFF0877B9);
const ownerCanvas = Color(0xFFF5F7FA);
const ownerBorder = Color(0xFFE4E9EF);
const ownerFieldFill = Color(0xFFF8FAFC);
const ownerFieldHint = Color(0xFF94A3B8);
const ownerDanger = Color(0xFFB42318);

/// Tema input untuk permukaan terang (kartu putih pada layar login, setup,
/// owner, lisensi, dan koneksi).
///
/// Tema aplikasi bersifat gelap, sehingga `InputDecorationTheme` global
/// mewarnai kotak input dengan fill gelap dan label terang. Di atas kartu putih
/// itu membuat label mengapung tanpa latar sehingga tampak menumpuk di kotak
/// input. Tema ini mengembalikan field ke gaya terang yang sesuai.
InputDecorationTheme buildOwnerInputDecorationTheme() {
  OutlineInputBorder border(Color color, {double width = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(10),
      borderSide: BorderSide(color: color, width: width),
    );
  }

  return InputDecorationTheme(
    filled: true,
    fillColor: ownerFieldFill,
    isDense: false,
    contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 16),
    labelStyle: const TextStyle(color: ownerMuted, fontSize: 14),
    floatingLabelStyle: const TextStyle(
      color: ownerBlue,
      fontSize: 13,
      fontWeight: FontWeight.w600,
    ),
    hintStyle: const TextStyle(color: ownerFieldHint, fontSize: 14),
    helperStyle: const TextStyle(color: ownerMuted, fontSize: 12),
    helperMaxLines: 2,
    errorStyle: const TextStyle(color: ownerDanger, fontSize: 12),
    errorMaxLines: 2,
    prefixIconColor: ownerMuted,
    suffixIconColor: ownerMuted,
    border: border(ownerBorder),
    enabledBorder: border(ownerBorder),
    disabledBorder: border(ownerBorder),
    focusedBorder: border(ownerBlue, width: 2),
    errorBorder: border(ownerDanger),
    focusedErrorBorder: border(ownerDanger, width: 2),
  );
}

/// Membungkus permukaan terang dengan tema input yang sesuai.
class OwnerFormTheme extends StatelessWidget {
  const OwnerFormTheme({required this.child, super.key});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Theme(
      data: Theme.of(context)
          .copyWith(inputDecorationTheme: buildOwnerInputDecorationTheme()),
      child: child,
    );
  }
}

class TrialBanner extends ConsumerStatefulWidget {
  const TrialBanner({super.key});

  @override
  ConsumerState<TrialBanner> createState() => _TrialBannerState();
}

class _TrialBannerState extends ConsumerState<TrialBanner>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ticker = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 14),
  );

  /// The marquee only needs to run while a trial banner is actually on screen.
  /// Starting it eagerly kept an endless animation alive on screens that render
  /// no banner at all, which never lets the widget tree reach a settled state.
  void _syncTicker(bool shouldRun) {
    if (shouldRun) {
      if (!_ticker.isAnimating) _ticker.repeat();
    } else if (_ticker.isAnimating) {
      _ticker.stop();
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // Never run the marquee when the platform asks for reduced motion; an
    // endless animation also prevents the tree from ever settling.
    final reduceMotion = MediaQuery.maybeDisableAnimationsOf(context) ?? false;

    if (ref.watch(billingLicenseActiveProvider).asData?.value == true) {
      _syncTicker(false);
      return const SizedBox.shrink();
    }
    return ref
        .watch(trialStatusProvider)
        .when(
          data: (trial) {
            _syncTicker(!reduceMotion);
            final expired = !trial.active;
            final message = expired
                ? 'MODE TRIAL BERAKHIR - Aktivasi diperlukan untuk transaksi.'
                : 'MODE TRIAL 7 HARI - Sisa ${trial.remaining.inDays} hari - Ketuk untuk aktivasi.';
            return _buildTickerBanner(
              context,
              message,
              expired ? const Color(0xFF8A2C20) : const Color(0xFF8A4B08),
              expired ? Icons.warning_amber_rounded : Icons.timelapse,
            );
          },
          loading: () {
            _syncTicker(!reduceMotion);
            return _buildTickerBanner(
              context,
              'MEMERIKSA STATUS TRIAL - Mohon tunggu sebentar.',
              const Color(0xFF8A4B08),
              Icons.timelapse,
            );
          },
          error: (_, _) {
            _syncTicker(!reduceMotion);
            return _buildTickerBanner(
              context,
              'STATUS TRIAL TIDAK TERSEDIA - Ketuk untuk aktivasi.',
              const Color(0xFF8A2C20),
              Icons.warning_amber_rounded,
            );
          },
        );
  }

  Widget _buildTickerBanner(
    BuildContext context,
    String message,
    Color color,
    IconData icon,
  ) {
    return Material(
      color: color,
      child: InkWell(
        onTap: () => context.go('/license'),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(icon, color: Colors.white),
              const SizedBox(width: 10),
              Expanded(
                child: _TrialTicker(text: message, controller: _ticker),
              ),
              const Icon(Icons.chevron_right, color: Colors.white),
            ],
          ),
        ),
      ),
    );
  }
}

class _TrialTicker extends StatelessWidget {
  const _TrialTicker({required this.text, required this.controller});

  final String text;
  final AnimationController controller;

  @override
  Widget build(BuildContext context) {
    const style = TextStyle(
      color: Colors.white,
      fontWeight: FontWeight.w700,
      fontSize: 13,
    );
    final painter = TextPainter(
      text: TextSpan(text: text, style: style),
      textDirection: TextDirection.ltr,
      maxLines: 1,
    )..layout();
    final gap = painter.width * 0.2 + 24;
    final cycleWidth = painter.width + gap;

    // Respect the platform "reduce motion" accessibility setting: show the
    // message once, statically, instead of scrolling it forever.
    final reduceMotion = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (reduceMotion) {
      // Static fallback: a single, ellipsized line. Align is avoided here
      // because an Align without heightFactor expands to the full available
      // height and would stretch the banner over the whole screen.
      return ClipRect(
        child: Text(
          text,
          style: style,
          maxLines: 1,
          softWrap: false,
          overflow: TextOverflow.ellipsis,
        ),
      );
    }

    return ClipRect(
      child: AnimatedBuilder(
        animation: controller,
        builder: (context, child) => Transform.translate(
          offset: Offset(-cycleWidth * controller.value, 0),
          child: child,
        ),
        // The marquee is intentionally wider than the banner. Without
        // OverflowBox the Row is forced to the incoming width and overflows by
        // the full text width, which threw a RenderFlex overflow on every
        // screen that shows the trial banner. OverflowBox sizes itself to the
        // biggest incoming constraint, so the height is pinned with a SizedBox
        // first; otherwise the banner stretches over the whole screen.
        child: SizedBox(
          height: painter.height,
          child: OverflowBox(
            alignment: Alignment.centerLeft,
            minWidth: 0,
            maxWidth: double.infinity,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(text, style: style, maxLines: 1, softWrap: false),
                SizedBox(width: gap),
                Text(text, style: style, maxLines: 1, softWrap: false),
                SizedBox(width: gap),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class OwnerScaffold extends StatelessWidget {
  const OwnerScaffold({
    required this.title,
    required this.body,
    this.onBack,
    this.onAdd,
    this.addLabel = 'Tambah',
    this.actions = const [],
    this.maxWidth = 1080,
    super.key,
  });

  final String title;
  final Widget body;
  final VoidCallback? onBack;
  final VoidCallback? onAdd;
  final String addLabel;
  final List<Widget> actions;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    final tableTheme = Theme.of(context).dataTableTheme.copyWith(
      headingRowColor: const WidgetStatePropertyAll(Color(0xFFEAF1F6)),
      dataRowColor: const WidgetStatePropertyAll(Colors.white),
      headingTextStyle: const TextStyle(
        color: ownerInk,
        fontSize: 13,
        fontWeight: FontWeight.w700,
      ),
      dataTextStyle: const TextStyle(color: ownerInk, fontSize: 14),
      dividerThickness: 1,
      headingRowHeight: 52,
      dataRowMinHeight: 54,
      dataRowMaxHeight: 72,
      horizontalMargin: 16,
      columnSpacing: 24,
    );

    return Scaffold(
      backgroundColor: ownerCanvas,
      bottomNavigationBar: const SafeArea(top: false, child: TrialBanner()),
      drawer: Drawer(
        child: SafeArea(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              const DrawerHeader(
                decoration: BoxDecoration(color: ownerBlue),
                child: Align(
                  alignment: Alignment.bottomLeft,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        Icons.storefront_rounded,
                        color: Colors.white,
                        size: 34,
                      ),
                      SizedBox(height: 10),
                      Text(
                        'Kasirin POS',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Text(
                        'Navigasi toko',
                        style: TextStyle(color: Color(0xFFDCEEFF)),
                      ),
                    ],
                  ),
                ),
              ),
              _navigationItem(
                context,
                Icons.dashboard_outlined,
                'Dashboard',
                '/',
              ),
              _navigationItem(
                context,
                Icons.point_of_sale_rounded,
                'Kasir POS',
                '/cashier',
              ),
              const Divider(),
              _navigationItem(
                context,
                Icons.group_outlined,
                'Tim & Akses',
                '/user-management',
              ),
              _navigationItem(
                context,
                Icons.inventory_2_outlined,
                'Produk & Stok',
                '/master-data',
              ),
              _navigationItem(
                context,
                Icons.sell_outlined,
                'Harga Spesial',
                '/special-prices',
              ),
              _navigationItem(
                context,
                Icons.shopping_bag_outlined,
                'Pembelian & Supplier',
                '/purchase',
              ),
              _navigationItem(
                context,
                Icons.assessment_outlined,
                'Laporan',
                '/report-center',
              ),
              _navigationItem(
                context,
                Icons.store_outlined,
                'Profil Toko',
                '/store-settings',
              ),
            ],
          ),
        ),
      ),
      appBar: AppBar(
        backgroundColor: ownerCanvas,
        foregroundColor: ownerInk,
        elevation: 0,
        scrolledUnderElevation: 0,
        titleSpacing: 0,
        leading: Builder(
          builder: (context) => IconButton(
            tooltip: 'Buka menu',
            onPressed: () => Scaffold.of(context).openDrawer(),
            icon: const Icon(Icons.menu_rounded),
          ),
        ),
        title: Text(
          title,
          style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w700),
        ),
        actions: [...actions, const SizedBox(width: 12)],
      ),
      body: Column(
        children: [
          Expanded(
            child: Theme(
              data: Theme.of(context).copyWith(
                dataTableTheme: tableTheme,
                inputDecorationTheme: buildOwnerInputDecorationTheme(),
              ),
              child: Stack(
                children: [
                  SafeArea(
                    top: false,
                    child: Align(
                      alignment: Alignment.topCenter,
                      child: ConstrainedBox(
                        constraints: BoxConstraints(maxWidth: maxWidth),
                        child: SizedBox(width: double.infinity, child: body),
                      ),
                    ),
                  ),
                  if (onAdd != null)
                    _MovableAddAction(label: addLabel, onPressed: onAdd!),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _navigationItem(
    BuildContext context,
    IconData icon,
    String label,
    String route,
  ) => ListTile(
    leading: Icon(icon),
    title: Text(label),
    onTap: () {
      Navigator.of(context).pop();
      if (route == '/' && onBack != null) {
        onBack!();
      } else {
        context.go(route);
      }
    },
  );
}

class OwnerTabBar<T> extends StatelessWidget {
  const OwnerTabBar({
    required this.tabs,
    required this.selected,
    required this.onSelected,
    super.key,
  });

  final List<(T, String)> tabs;
  final T selected;
  final ValueChanged<T> onSelected;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: ownerBorder),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          for (final tab in tabs)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 2),
                child: Material(
                  color: tab.$1 == selected ? ownerBlue : Colors.transparent,
                  borderRadius: BorderRadius.circular(10),
                  child: InkWell(
                    onTap: () => onSelected(tab.$1),
                    borderRadius: BorderRadius.circular(10),
                    child: SizedBox(
                      height: 42,
                      child: Center(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 4),
                          child: FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              tab.$2,
                              maxLines: 1,
                              softWrap: false,
                              style: TextStyle(
                                color: tab.$1 == selected
                                    ? Colors.white
                                    : ownerInk,
                                fontSize: 13,
                                fontWeight: tab.$1 == selected
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _MovableAddAction extends StatefulWidget {
  const _MovableAddAction({required this.label, required this.onPressed});

  final String label;
  final VoidCallback onPressed;

  @override
  State<_MovableAddAction> createState() => _MovableAddActionState();
}

class _MovableAddActionState extends State<_MovableAddAction> {
  Offset? _position;

  @override
  Widget build(BuildContext context) {
    return Positioned.fill(
      child: SafeArea(
        top: false,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final width = constraints.maxWidth;
            final height = constraints.maxHeight;
            final buttonWidth = (88 + widget.label.length * 7.0)
                .clamp(120.0, width - 16)
                .toDouble();
            final buttonHeight = 56.0;
            final position =
                _position ??
                Offset(
                  (width - buttonWidth - 14).clamp(0.0, width - buttonWidth),
                  (height - buttonHeight - 16).clamp(
                    0.0,
                    height - buttonHeight,
                  ),
                );

            return Stack(
              children: [
                Positioned(
                  left: position.dx,
                  top: position.dy,
                  child: GestureDetector(
                    onPanUpdate: (details) {
                      setState(() {
                        _position = Offset(
                          (position.dx + details.delta.dx)
                              .clamp(0.0, width - buttonWidth)
                              .toDouble(),
                          (position.dy + details.delta.dy)
                              .clamp(0.0, height - buttonHeight)
                              .toDouble(),
                        );
                      });
                    },
                    child: FloatingActionButton.extended(
                      heroTag: null,
                      tooltip: 'Geser tombol ini bila menutupi tabel',
                      onPressed: widget.onPressed,
                      icon: const Icon(Icons.add_rounded),
                      label: Text(widget.label),
                    ),
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class OwnerSectionHeading extends StatelessWidget {
  const OwnerSectionHeading({
    required this.title,
    this.subtitle,
    this.trailing,
    super.key,
  });

  final String title;
  final String? subtitle;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(
                  color: ownerInk,
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (subtitle != null) ...[
                const SizedBox(height: 4),
                Text(
                  subtitle!,
                  style: const TextStyle(color: ownerMuted, fontSize: 13),
                ),
              ],
            ],
          ),
        ),
        ?trailing,
      ],
    );
  }
}

class OwnerSurface extends StatelessWidget {
  const OwnerSurface({
    required this.child,
    this.padding = const EdgeInsets.all(18),
    super.key,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: ownerBorder),
        boxShadow: const [
          BoxShadow(
            color: Color(0x080F172A),
            blurRadius: 18,
            offset: Offset(0, 5),
          ),
        ],
      ),
      child: child,
    );
  }
}

class OwnerEmptyState extends StatelessWidget {
  const OwnerEmptyState({
    required this.icon,
    required this.title,
    this.message,
    this.action,
    super.key,
  });

  final IconData icon;
  final String title;
  final String? message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 64,
              height: 64,
              decoration: BoxDecoration(
                color: ownerBlue.withValues(alpha: .08),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, color: ownerBlue, size: 30),
            ),
            const SizedBox(height: 18),
            Text(
              title,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: ownerInk,
                fontSize: 17,
                fontWeight: FontWeight.w700,
              ),
            ),
            if (message != null) ...[
              const SizedBox(height: 6),
              Text(
                message!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: ownerMuted, fontSize: 13),
              ),
            ],
            if (action != null) ...[const SizedBox(height: 18), action!],
          ],
        ),
      ),
    );
  }
}
