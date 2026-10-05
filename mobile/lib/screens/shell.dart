import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'account.dart';
import 'cart.dart';
import 'catalog.dart';
import 'home.dart';

/// رفتن به یک زبانه از هر جای اپ (پوستهٔ ایران کارپت یا فرش‌یاب خودش را ثبت می‌کند).
void Function(int)? tabGo;

class Shell extends StatefulWidget {
  const Shell({super.key});
  static void goTab(BuildContext context, int i) => tabGo?.call(i);
  @override
  State<Shell> createState() => _ShellState();
}

class _ShellState extends State<Shell> {
  int _i = 0;
  bool _checkedUpdate = false;
  final _pages = const [HomeTab(), CategoriesTab(), CartScreen(), WishlistTab(), AccountTab()];

  void go(int i) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    setState(() => _i = i);
  }

  @override
  void initState() {
    super.initState();
    tabGo = go;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final cfg = context.watch<AppConfig>();
    if (!_checkedUpdate && cfg.data.isNotEmpty) {
      _checkedUpdate = true;
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybeUpdate(cfg.data));
    }
  }

  static int _v(String s) => s.split('.').map((x) => int.tryParse(x) ?? 0).fold(0, (a, b) => a * 1000 + b);

  void _maybeUpdate(Json d) {
    final latest = d['latest_version'] as String? ?? kAppVersion, min = d['min_version'] as String? ?? kAppVersion;
    final url = d['update_url'] as String? ?? '';
    if (url.isEmpty || _v(latest) <= _v(kAppVersion)) return;
    final force = _v(min) > _v(kAppVersion);
    showDialog(
      context: context,
      barrierDismissible: !force,
      builder: (c) => PopScope(
        canPop: !force,
        child: AlertDialog(
          title: const Text('نسخهٔ تازهٔ ایران کارپت'),
          content: Text((d['update_note'] as String?)?.isNotEmpty == true ? d['update_note'] as String : 'نسخهٔ $latest آماده است.'),
          actions: [
            if (!force) TextButton(onPressed: () => Navigator.pop(c), child: const Text('بعداً')),
            FilledButton(
                onPressed: () => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication), child: const Text('دریافت نسخهٔ تازه')),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final count = context.watch<Cart>().count;
    return PopScope(
      canPop: _i == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) setState(() => _i = 0);
      },
      child: Scaffold(
        body: IndexedStack(index: _i, children: _pages),
        bottomNavigationBar: NavigationBarTheme(
          data: NavigationBarThemeData(
            indicatorColor: C.pinkTint,
            labelTextStyle: WidgetStateProperty.resolveWith((s) => TextStyle(
                fontFamily: kFont, fontSize: 12, fontWeight: s.contains(WidgetState.selected) ? FontWeight.w800 : FontWeight.w500,
                color: s.contains(WidgetState.selected) ? C.pinkDark : C.muted)),
          ),
          child: NavigationBar(
            height: 66,
            backgroundColor: Colors.white,
            surfaceTintColor: Colors.white,
            selectedIndex: _i,
            onDestinationSelected: go,
            destinations: [
              const NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home_rounded, color: C.pink), label: 'خانه'),
              const NavigationDestination(icon: Icon(Icons.grid_view_outlined), selectedIcon: Icon(Icons.grid_view_rounded, color: C.pink), label: 'دسته‌ها'),
              NavigationDestination(
                icon: Badge(isLabelVisible: count > 0, label: Text('$count'), backgroundColor: C.pink, child: const Icon(Icons.shopping_bag_outlined)),
                selectedIcon: Badge(isLabelVisible: count > 0, label: Text('$count'), backgroundColor: C.ink, child: const Icon(Icons.shopping_bag_rounded, color: C.pink)),
                label: 'سبد',
              ),
              const NavigationDestination(icon: Icon(Icons.favorite_border), selectedIcon: Icon(Icons.favorite, color: C.pink), label: 'علاقه‌مندی'),
              const NavigationDestination(icon: Icon(Icons.person_outline), selectedIcon: Icon(Icons.person, color: C.pink), label: 'حساب من'),
            ],
          ),
        ),
      ),
    );
  }
}
