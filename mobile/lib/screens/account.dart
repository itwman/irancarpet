import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/brand.dart';
import '../widgets/common.dart';
import '../widgets/contact.dart';
import '../widgets/growth.dart';
import 'checkout.dart' show SectionHead;
import 'shell.dart';

class AccountTab extends StatelessWidget {
  const AccountTab({super.key});

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<Auth>();
    final cfg = context.watch<AppConfig>().data;
    final cmp = context.watch<Compare>();
    Widget tile(IconData i, String t, VoidCallback onTap, {String? sub, Color color = C.ink}) => ListTile(
          leading: Icon(i, color: color),
          title: Text(t, style: TextStyle(fontWeight: FontWeight.w700, color: color)),
          subtitle: sub == null ? null : Text(sub),
          trailing: const Icon(Icons.chevron_right, color: C.muted),
          onTap: onTap,
        );
    return Scaffold(
      appBar: AppBar(title: const Text('حساب من')),
      body: ListView(children: [
        Container(
          margin: const EdgeInsets.fromLTRB(16, 4, 16, 8),
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(color: C.ink, borderRadius: BorderRadius.circular(22)),
          child: Row(children: [
            const BrandLogo(size: 56, tile: true),
            const SizedBox(width: 14),
            Expanded(
              child: auth.loggedIn
                  ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(auth.displayName, style: const TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w900)),
                      Text(faDigits(auth.user?['mobile'] ?? ''), style: TextStyle(color: Colors.white.withValues(alpha: .7))),
                    ])
                  : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('به ایران کارپت خوش آمدید', style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.w900)),
                      const SizedBox(height: 8),
                      FilledButton(
                        style: FilledButton.styleFrom(minimumSize: const Size(10, 42)),
                        onPressed: () => Navigator.pushNamed(context, '/login'),
                        child: const Text('ورود یا ثبت‌نام'),
                      ),
                    ]),
            ),
          ]),
        ),
        if (auth.loggedIn) ...[
          tile(Icons.receipt_long_outlined, 'سفارش‌های من', () => Navigator.pushNamed(context, '/orders')),
          tile(Icons.location_on_outlined, 'مشخصات و نشانی', () => Navigator.pushNamed(context, '/profile')),
        ],
        tile(Icons.local_shipping_outlined, 'پیگیری سفارش با شماره', () => Navigator.pushNamed(context, '/track')),
        tile(Icons.receipt_long_rounded, 'لیست قیمت فرش', () => Navigator.pushNamed(context, '/pricelist')),
        if (context.watch<AppConfig>().installmentPlans.isNotEmpty)
          tile(Icons.calendar_month_rounded, 'خرید اقساطی', () => Navigator.pushNamed(context, '/installment'),
              sub: 'چک صیادی و ویژهٔ بازنشستگان'),
        tile(Icons.card_giftcard_rounded, 'دعوت از دوستان', () => showReferralSheet(context), sub: 'کد معرفی و کدهای هدیه'),
        tile(Icons.favorite_border, 'علاقه‌مندی‌ها', () => Shell.goTab(context, 3)),
        tile(Icons.compare_outlined, 'مقایسهٔ فرش‌ها', () => Navigator.pushNamed(context, '/compare'),
            sub: cmp.ids.isEmpty ? 'از صفحهٔ هر فرش اضافه کنید' : '${faDigits(cmp.ids.length)} فرش'),
        tile(Icons.notifications_none_rounded, 'اعلان‌ها و تخفیف‌ها', () => Navigator.pushNamed(context, '/notifications')),
        const Divider(),
        if (socials(context, messengersOnly: true).isNotEmpty)
          tile(Icons.chat_outlined, 'گفتگو با کارشناس', () => showContactSheet(context),
              sub: socials(context, messengersOnly: true).map((s) => s['name']).join('، ')),
        if ((cfg['mobile'] as String? ?? '').isNotEmpty)
          tile(Icons.smartphone_rounded, 'موبایل پاسخگو', () => launchUrl(Uri.parse('tel:${cfg['mobile']}')), sub: faDigits(cfg['mobile'])),
        if ((cfg['phone'] as String? ?? '').isNotEmpty)
          tile(Icons.call_outlined, 'تماس با فروشگاه', () => launchUrl(Uri.parse('tel:${(cfg['phone'] as String).replaceAll(RegExp(r'[^\d+]'), '')}')),
              sub: faDigits(cfg['phone'])),
        tile(Icons.public, 'سایت ایران کارپت', () => launchUrl(Uri.parse(kSite), mode: LaunchMode.externalApplication)),
        tile(Icons.verified_user_outlined, 'مجوزها و نماد اعتماد',
            () => launchUrl(Uri.parse(cfg['license_url'] as String? ?? '$kSite/license/'), mode: LaunchMode.externalApplication),
            sub: 'نماد اعتماد الکترونیکی (اینماد)'),
        for (final s in socials(context, followsOnly: true))
          tile(socialIcon(s['key'] as String), s['name'] as String, () => openUrl(s['url'] as String), sub: 'ایران کارپت'),
        if (auth.loggedIn) tile(Icons.logout_rounded, 'خروج از حساب', () => auth.logout(), color: C.pinkDark),
        const SizedBox(height: 16),
        Center(child: Text('نسخهٔ ${faDigits(kAppVersion)}', style: const TextStyle(color: C.muted, fontSize: 12))),
        const SizedBox(height: 24),
      ]),
    );
  }
}

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});
  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _c = <String, TextEditingController>{
    for (final k in ['first_name', 'last_name', 'email', 'city', 'address', 'postal_code']) k: TextEditingController(),
  };
  String? _province;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final u = context.read<Auth>().user ?? {};
    for (final e in _c.entries) {
      e.value.text = (u[e.key] ?? '') as String;
    }
    final p = (u['province'] ?? '') as String;
    _province = p.isEmpty ? null : p;
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    try {
      await Api.i.post('/me/', {for (final e in _c.entries) e.key: latin(e.value.text.trim()), 'province': _province ?? ''});
      if (!mounted) return;
      await context.read<Auth>().refresh();
      if (mounted) {
        toast(context, 'ذخیره شد.');
        Navigator.pop(context);
      }
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final provinces = context.watch<AppConfig>().provinces;
    Widget f(String k, String label, {int lines = 1, TextInputType? type}) =>
        Column(crossAxisAlignment: CrossAxisAlignment.start, children: [FieldLabel(label), TextField(controller: _c[k], maxLines: lines, keyboardType: type, textDirection: type == null ? null : TextDirection.ltr)]);
    return Scaffold(
      appBar: AppBar(title: const Text('مشخصات و نشانی')),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 0, 16, 24), children: [
        Row(children: [Expanded(child: f('first_name', 'نام')), const SizedBox(width: 10), Expanded(child: f('last_name', 'نام خانوادگی'))]),
        f('email', 'ایمیل (اختیاری)', type: TextInputType.emailAddress),
        const SectionHead('نشانی پیش‌فرض'),
        const FieldLabel('استان'),
        DropdownButtonFormField<String>(
          initialValue: provinces.contains(_province) ? _province : null,
          isExpanded: true,
          items: [for (final p in provinces) DropdownMenuItem(value: p, child: Text(p))],
          onChanged: (v) => setState(() => _province = v),
        ),
        f('city', 'شهر'),
        f('address', 'نشانی', lines: 3),
        f('postal_code', 'کد پستی', type: TextInputType.number),
      ]),
      bottomNavigationBar: SafeArea(
        child: Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 10), child: FilledButton(onPressed: _busy ? null : _save, child: const Text('ذخیره'))),
      ),
    );
  }
}

class WishlistTab extends StatefulWidget {
  const WishlistTab({super.key});
  @override
  State<WishlistTab> createState() => _WishlistTabState();
}

class _WishlistTabState extends State<WishlistTab> {
  List<Json> _items = [];
  String _sig = '';
  bool _loading = false;

  Future<void> _load(Set<int> ids) async {
    final sig = (ids.toList()..sort()).join(',');
    if (sig == _sig) return;
    _sig = sig;
    if (ids.isEmpty) return setState(() => _items = []);
    setState(() => _loading = true);
    try {
      final r = await Api.i.get('/products/', {'ids': sig}) as Json;
      _items = (r['results'] as List).cast<Json>();
    } catch (_) {
      _sig = '';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final wish = context.watch<Wishlist>();
    WidgetsBinding.instance.addPostFrameCallback((_) => _load(wish.ids));
    final items = _items.where((p) => wish.has(p['id'] as int)).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('علاقه‌مندی‌ها')),
      body: wish.ids.isEmpty
          ? const StatusView(message: 'با زدن ♡ روی هر فرش، اینجا نگهش دارید.', icon: Icons.favorite_border)
          : (_loading && items.isEmpty)
              ? const Loading()
              : GridView.builder(
                  padding: const EdgeInsets.all(16),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2, mainAxisSpacing: 14, crossAxisSpacing: 12, childAspectRatio: .54),
                  itemCount: items.length,
                  itemBuilder: (_, i) => ProductCard(items[i]),
                ),
    );
  }
}

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});
  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  List<Json>? _list;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = (await Api.i.get('/notifications/') as List).cast<Json>();
      if (mounted) setState(() => _list = r);
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('اعلان‌ها')),
        body: _list == null
            ? (_err != null ? StatusView(message: _err!, onRetry: _load) : const Loading())
            : _list!.isEmpty
                ? const StatusView(message: 'فعلاً اعلان تازه‌ای نیست. تخفیف‌ها و فرش‌های تازه همین‌جا می‌آیند.', icon: Icons.notifications_none_rounded)
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _list!.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (_, i) {
                      final n = _list![i];
                      final kind = n['kind'] as String;
                      final color = kind == 'deal' ? C.pink : (kind == 'new' ? C.teal : C.saffron);
                      return Material(
                        color: C.soft,
                        borderRadius: BorderRadius.circular(18),
                        clipBehavior: Clip.antiAlias,
                        child: InkWell(
                          onTap: () {
                            if (n['product_id'] != null) {
                              Navigator.pushNamed(context, '/product', arguments: n['product_id']);
                            } else if (n['category_id'] != null) {
                              Navigator.pushNamed(context, '/products', arguments: {'title': n['title'], 'query': {'category': n['category_id']}});
                            } else if ((n['url'] as String).isNotEmpty) {
                              launchUrl(Uri.parse(n['url'] as String), mode: LaunchMode.externalApplication);
                            }
                          },
                          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Container(width: 6, height: 92, color: color),
                            if ((n['image'] as String).isNotEmpty) SizedBox(width: 80, height: 92, child: NetImage(n['image'] as String)),
                            Expanded(
                              child: Padding(
                                padding: const EdgeInsets.all(12),
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text(n['title'] as String, style: const TextStyle(fontWeight: FontWeight.w900)),
                                  Text(n['body'] as String, style: const TextStyle(color: C.ink2, fontSize: 13)),
                                ]),
                              ),
                            ),
                          ]),
                        ),
                      );
                    },
                  ),
      );
}
