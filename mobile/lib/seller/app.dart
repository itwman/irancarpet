import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../screens/login.dart';
import '../state/app_state.dart';
import '../widgets/brand.dart';
import '../widgets/common.dart';
import 'albums.dart';
import 'home.dart';
import 'more.dart';
import 'orders.dart';
import 'products.dart';
import 'ui.dart';

/// اپ «ایران کارپت فروشندگان»: همان حساب سایت؛ فقط برای کسی که فروشگاه فعال در بازارچه دارد.
Future<void> runSellerApp() async {
  final auth = Auth(), wish = Wishlist();
  await auth.load();
  runApp(MultiProvider(
    providers: [ChangeNotifierProvider.value(value: auth), ChangeNotifierProvider.value(value: wish)],
    child: const SellerApp(),
  ));
}

class SellerApp extends StatelessWidget {
  const SellerApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: kAppName,
        debugShowCheckedModeBanner: false,
        theme: buildTheme(),
        locale: const Locale('fa', 'IR'),
        supportedLocales: const [Locale('fa', 'IR')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
        home: const SellerGate(),
      );
}

/// ورود ← بررسی فروشگاه ← پنل
class SellerGate extends StatefulWidget {
  const SellerGate({super.key});
  @override
  State<SellerGate> createState() => _SellerGateState();
}

class _SellerGateState extends State<SellerGate> {
  Future<Json>? _summary;

  @override
  void initState() {
    super.initState();
    if (Api.i.token != null) _summary = _load();
  }

  Future<Json> _load() async {
    await Guides.load();
    final d = await Api.i.get('/seller/summary/') as Json;
    Guides.data = (d['guides'] as Map?)?.cast<String, dynamic>() ?? {};
    return d;
  }

  Future<void> _login() async {
    final ok = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const LoginScreen(
        reason: 'با همان شمارهٔ موبایلی که فروشگاهتان را در ایران کارپت ساخته‌اید وارد شوید.')));
    if (ok == true && mounted) setState(() => _summary = _load());
  }

  @override
  Widget build(BuildContext context) {
    if (Api.i.token == null || _summary == null) return _Welcome(onLogin: _login);
    return FutureBuilder<Json>(
      future: _summary,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) return const Scaffold(body: Loading());
        final err = snap.error;
        if (err is ApiError) {
          if (err.unauthorized) {
            // توکن باطل شده: پس از ساخت صفحه بیرون برو
            WidgetsBinding.instance.addPostFrameCallback((_) async {
              await this.context.read<Auth>().logout(remote: false);
              if (mounted) setState(() => _summary = null);
            });
            return _Welcome(onLogin: _login);
          }
          return Scaffold(
            body: StatusView(
              message: err.message,
              icon: err.status == 403 ? Icons.storefront_outlined : Icons.wifi_off_rounded,
              onRetry: () => setState(() => _summary = _load()),
              action: err.status == 403
                  ? Column(children: [
                      FilledButton(
                          onPressed: () => launchUrl(Uri.parse('$kSite/sell/'), mode: LaunchMode.externalApplication),
                          child: const Text('ساختن فروشگاه در سایت')),
                      TextButton(
                          onPressed: () async {
                            await context.read<Auth>().logout();
                            if (mounted) setState(() => _summary = null);
                          },
                          child: const Text('ورود با حساب دیگر')),
                    ])
                  : null,
            ),
          );
        }
        if (err != null) return Scaffold(body: StatusView(message: '$err', onRetry: () => setState(() => _summary = _load())));
        return SellerShell(first: snap.data!, onLogout: () => setState(() => _summary = null));
      },
    );
  }
}

class _Welcome extends StatelessWidget {
  const _Welcome({required this.onLogin});
  final VoidCallback onLogin;
  @override
  Widget build(BuildContext context) => Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(28),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              const Center(child: BrandLogo(size: 84)),
              const SizedBox(height: 18),
              const Text('ایران کارپت فروشندگان', textAlign: TextAlign.center, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900)),
              const SizedBox(height: 8),
              const Text('سفارش‌ها، قیمت و موجودی، آلبوم‌ها و آمار فروشگاهتان در بازارچهٔ ایران کارپت، همه در جیب شما.',
                  textAlign: TextAlign.center, style: TextStyle(color: C.muted)),
              const SizedBox(height: 32),
              FilledButton(onPressed: onLogin, child: const Text('ورود فروشنده')),
              TextButton(
                  onPressed: () => launchUrl(Uri.parse('$kSite/sell/'), mode: LaunchMode.externalApplication),
                  child: const Text('هنوز فروشگاه ندارید؟ در ایران کارپت بفروشید')),
            ]),
          ),
        ),
      );
}

class SellerShell extends StatefulWidget {
  const SellerShell({super.key, required this.first, required this.onLogout});
  final Json first;
  final VoidCallback onLogout;
  @override
  State<SellerShell> createState() => _SellerShellState();
}

class _SellerShellState extends State<SellerShell> {
  int _tab = 0;
  late Json _summary = widget.first;
  late final List<Widget> _pages = [
    SellerHome(first: widget.first, go: (i) => setState(() => _tab = i), onSummary: (d) => setState(() => _summary = d)),
    const SellerOrders(),
    const SellerProducts(),
    const SellerAlbums(),
    SellerMore(seller: (widget.first['seller'] as Map).cast<String, dynamic>(), onLogout: widget.onLogout),
  ];

  @override
  Widget build(BuildContext context) {
    final todo = (_summary['todo'] as Map?) ?? {};
    final newOrders = (todo['new_orders'] as num?)?.toInt() ?? 0;
    return Scaffold(
      body: IndexedStack(index: _tab, children: _pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _tab,
        onDestinationSelected: (i) => setState(() => _tab = i),
        indicatorColor: C.pinkTint,
        destinations: [
          const NavigationDestination(icon: Icon(Icons.home_outlined), selectedIcon: Icon(Icons.home_rounded), label: 'خانه'),
          NavigationDestination(
              icon: Badge(isLabelVisible: newOrders > 0, label: Text('$newOrders'), child: const Icon(Icons.shopping_bag_outlined)),
              selectedIcon: const Icon(Icons.shopping_bag_rounded),
              label: 'سفارش‌ها'),
          const NavigationDestination(icon: Icon(Icons.inventory_2_outlined), selectedIcon: Icon(Icons.inventory_2_rounded), label: 'کالاها'),
          const NavigationDestination(icon: Icon(Icons.price_change_outlined), selectedIcon: Icon(Icons.price_change_rounded), label: 'آلبوم‌ها'),
          const NavigationDestination(icon: Icon(Icons.more_horiz_rounded), label: 'بیشتر'),
        ],
      ),
    );
  }
}
