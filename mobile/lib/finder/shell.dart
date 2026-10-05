import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../screens/cart.dart';
import '../screens/shell.dart' show tabGo;
import '../state/app_state.dart';
import '../widgets/contact.dart';
import '../widgets/growth.dart';
import 'home.dart';
import 'requests.dart';
import 'state.dart';

/// پوستهٔ اپ فرش‌یاب: پیدا کن، عکس فرش، سبد، من
class FinderShell extends StatefulWidget {
  const FinderShell({super.key});
  @override
  State<FinderShell> createState() => _FinderShellState();
}

class _FinderShellState extends State<FinderShell> with WidgetsBindingObserver {
  int _i = 0;
  final _pages = const [FinderHome(), PhotoTab(), CartScreen(), FinderAccount()];

  void go(int i) {
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    setState(() => _i = i);
  }

  @override
  void initState() {
    super.initState();
    tabGo = go;
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => context.read<FinderData>().refreshUnread());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) context.read<FinderData>().refreshUnread();
  }

  @override
  Widget build(BuildContext context) {
    final count = context.watch<Cart>().count;
    final unread = context.watch<FinderData>().unread;
    Widget badge(int n, Widget icon, [Color bg = C.pink]) =>
        Badge(isLabelVisible: n > 0, label: Text(faDigits(n)), backgroundColor: bg, child: icon);
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
              const NavigationDestination(
                  icon: Icon(Icons.manage_search_rounded), selectedIcon: Icon(Icons.manage_search_rounded, color: C.pink), label: 'پیدا کن'),
              const NavigationDestination(
                  icon: Icon(Icons.photo_camera_outlined), selectedIcon: Icon(Icons.photo_camera_rounded, color: C.pink), label: 'با عکس'),
              NavigationDestination(
                icon: badge(count, const Icon(Icons.shopping_bag_outlined)),
                selectedIcon: badge(count, const Icon(Icons.shopping_bag_rounded, color: C.pink), C.ink),
                label: 'سبد',
              ),
              NavigationDestination(
                icon: badge(unread, const Icon(Icons.person_outline)),
                selectedIcon: badge(unread, const Icon(Icons.person, color: C.pink), C.ink),
                label: 'من',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// زبانهٔ «من» در فرش‌یاب
class FinderAccount extends StatelessWidget {
  const FinderAccount({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<Auth>();
    final unread = context.watch<FinderData>().unread;
    final cfg = context.watch<AppConfig>().data;
    Widget tile(IconData i, String t, VoidCallback onTap, {String? sub, Widget? trailing, Color color = C.ink}) => ListTile(
          leading: Icon(i, color: color),
          title: Text(t, style: TextStyle(fontWeight: FontWeight.w700, color: color)),
          subtitle: sub == null ? null : Text(sub),
          trailing: trailing ?? const Icon(Icons.chevron_left_rounded, color: C.muted),
          onTap: onTap,
        );
    return Scaffold(
      appBar: AppBar(title: const Text('من')),
      body: ListView(children: [
        Container(
          margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(color: C.ink, borderRadius: BorderRadius.circular(22)),
          child: auth.loggedIn
              ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(auth.displayName, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
                  Text(faDigits(auth.user?['mobile'] ?? ''), style: TextStyle(color: Colors.white.withValues(alpha: .7))),
                ])
              : Row(children: [
                  const Expanded(
                    child: Text('وارد شو تا پاسخ کارشناس و سفارش‌هایت اینجا بیاید.',
                        style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700, height: 1.7)),
                  ),
                  FilledButton(onPressed: () => Navigator.pushNamed(context, '/login'), child: const Text('ورود')),
                ]),
        ),
        tile(Icons.inbox_outlined, 'درخواست‌های من', () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RequestsScreen())),
            sub: 'عکس‌ها و پاسخ کارشناس',
            trailing: unread > 0
                ? Badge(label: Text(faDigits(unread)), backgroundColor: C.pink, child: const Icon(Icons.chevron_left_rounded, color: C.muted))
                : null),
        if (auth.loggedIn) tile(Icons.receipt_long_outlined, 'سفارش‌های من', () => Navigator.pushNamed(context, '/orders')),
        tile(Icons.card_giftcard_rounded, 'دعوت از دوستان', () => showReferralSheet(context), sub: 'کد معرفی و کدهای هدیه'),
        tile(Icons.local_shipping_outlined, 'پیگیری سفارش با شماره', () => Navigator.pushNamed(context, '/track')),
        if (context.watch<AppConfig>().installmentPlans.isNotEmpty)
          tile(Icons.calendar_month_rounded, 'خرید اقساطی', () => Navigator.pushNamed(context, '/installment'),
              sub: 'چک صیادی و ویژهٔ بازنشستگان'),
        tile(Icons.receipt_long_rounded, 'لیست قیمت فرش', () => Navigator.pushNamed(context, '/pricelist')),
        const Divider(),
        if (socials(context, messengersOnly: true).isNotEmpty)
          tile(Icons.chat_outlined, 'گفتگو با کارشناس', () => showContactSheet(context),
              sub: socials(context, messengersOnly: true).map((s) => s['name']).join('، ')),
        if ((cfg['mobile'] as String? ?? '').isNotEmpty)
          tile(Icons.smartphone_rounded, 'موبایل پاسخگو', () => launchUrl(Uri.parse('tel:${cfg['mobile']}')), sub: faDigits(cfg['mobile'])),
        tile(Icons.verified_user_outlined, 'مجوزها و نماد اعتماد',
            () => launchUrl(Uri.parse(cfg['license_url'] as String? ?? '$kSite/license/'), mode: LaunchMode.externalApplication),
            sub: 'فرش‌یاب بخشی از فروشگاه ایران کارپت است'),
        tile(Icons.public, 'سایت ایران کارپت', () => launchUrl(Uri.parse(kSite), mode: LaunchMode.externalApplication)),
        if (auth.loggedIn) tile(Icons.logout_rounded, 'خروج از حساب', () => auth.logout(), color: C.pinkDark),
        const SizedBox(height: 16),
        Center(child: Text('فرش‌یاب، نسخهٔ ${faDigits(kAppVersion)}', style: const TextStyle(color: C.muted, fontSize: 12))),
        const SizedBox(height: 24),
      ]),
    );
  }
}
