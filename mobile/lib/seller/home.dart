import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'questions.dart';
import 'quick.dart';
import 'stats.dart';
import 'ui.dart';

/// خانه: کارهای امروز، عددهای هفته، نمودار و موجودی حساب
class SellerHome extends StatefulWidget {
  const SellerHome({super.key, required this.first, required this.go, required this.onSummary});
  final Json first;
  final ValueChanged<int> go;
  final ValueChanged<Json> onSummary;
  @override
  State<SellerHome> createState() => _SellerHomeState();
}

class _SellerHomeState extends State<SellerHome> {
  late Json _d = widget.first;
  String _field = 'sales';

  Future<void> _refresh() async {
    final d = await run(context, () async => await Api.i.get('/seller/summary/') as Json);
    if (d != null && mounted) {
      Guides.data = (d['guides'] as Map?)?.cast<String, dynamic>() ?? Guides.data;
      setState(() => _d = d);
      widget.onSummary(d);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = (_d['seller'] as Map).cast<String, dynamic>();
    final w = (_d['week'] as Map).cast<String, dynamic>();
    final todo = (_d['todo'] as Map).cast<String, dynamic>();
    final bal = (_d['balance'] as Map).cast<String, dynamic>();
    final series = (_d['series'] as List?) ?? [];
    Map v(String k) => (w[k] as Map?) ?? {};
    final conv = w['conversion'];
    final paused = s['status'] == 'paused';
    final setup = (_d['setup'] as Map?)?.cast<String, dynamic>();

    final tasks = <(IconData, String, int, VoidCallback)>[
      (Icons.notifications_active_outlined, 'سفارش تازه؛ منتظر پذیرش شما', asInt(todo['new_orders']), () => widget.go(1)),
      (Icons.local_shipping_outlined, 'سفارش پذیرفته؛ منتظر ارسال', asInt(todo['to_ship']), () => widget.go(1)),
      (Icons.help_outline_rounded, 'پرسش بی‌پاسخ مشتری', asInt(todo['questions']),
          () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SellerQuestions()))),
      (Icons.remove_shopping_cart_outlined, 'کالای ناموجود', asInt(todo['out']), () => widget.go(2)),
      (Icons.report_gmailerrorred_rounded, 'کالای ردشده در بررسی', asInt(todo['rejected']), () => widget.go(2)),
    ].where((t) => t.$3 > 0).toList();

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 12,
        title: Row(children: [
          if ((s['logo'] ?? '').toString().isNotEmpty) ...[
            SizedBox(width: 34, height: 34, child: NetImage(s['logo'] as String, radius: 10, fit: BoxFit.contain)),
            const SizedBox(width: 10),
          ],
          Expanded(child: Text('${s['name']}', overflow: TextOverflow.ellipsis)),
        ]),
        actions: [
          GuideButton('home', onChanged: () => setState(() {})),
          IconButton(
              tooltip: 'دیدن ویترین',
              icon: const Icon(Icons.storefront_outlined),
              onPressed: () => launchUrl(Uri.parse('$kSite${s['url']}'), mode: LaunchMode.externalApplication)),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
          const GuideCard('home'),
          if (paused)
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Panel(
                  child: Row(children: const [
                Icon(Icons.pause_circle_outline_rounded, color: Color(0xFFB45309)),
                SizedBox(width: 8),
                Expanded(child: Text('فروشگاه شما موقتاً بسته است و کالاهایتان در سایت فروخته نمی‌شوند.')),
              ])),
            ),
          if (tasks.isEmpty)
            const Panel(
                child: Row(children: [
              Icon(Icons.check_circle_outline_rounded, color: Color(0xFF178A4C)),
              SizedBox(width: 8),
              Expanded(child: Text('کار عقب‌افتاده‌ای ندارید.')),
            ]))
          else
            Panel(
              padding: EdgeInsets.zero,
              child: Column(children: [
                for (final t in tasks)
                  ListTile(
                    leading: Icon(t.$1, color: C.pinkDark),
                    title: Text(t.$2),
                    trailing: Row(mainAxisSize: MainAxisSize.min, children: [
                      Pill(faDigits(t.$3), color: C.pinkDark),
                      const Icon(Icons.chevron_left_rounded, color: C.muted),
                    ]),
                    onTap: t.$4,
                  ),
              ]),
            ),
          if (setup != null && setup['all'] != true) ...[
            const SizedBox(height: 12),
            _Setup(setup),
          ],
          const SizedBox(height: 18),
          const Text('هفت روز گذشته', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
          const Text('در مقایسه با هفت روز پیش از آن', style: TextStyle(color: C.muted, fontSize: 12.5)),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.9,
            children: [
              Kpi(label: 'فروش', value: amount(asInt(v('sales')['value'])), change: v('sales')['change'], icon: Icons.payments_outlined),
              Kpi(label: 'سفارش', value: faDigits(asInt(v('orders')['value'])), change: v('orders')['change'], icon: Icons.shopping_bag_outlined),
              Kpi(label: 'بازدید', value: faDigits(sep(asInt(v('views')['value']))), change: v('views')['change'], icon: Icons.visibility_outlined),
              Kpi(
                  label: 'نرخ تبدیل',
                  value: conv == null ? '—' : '${faDigits('$conv'.replaceAll('.', '٫'))}٪',
                  icon: Icons.trending_up_rounded),
            ],
          ),
          const SizedBox(height: 12),
          Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              SegmentedButton<String>(
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(value: 'sales', label: Text('فروش')),
                  ButtonSegment(value: 'orders', label: Text('سفارش')),
                  ButtonSegment(value: 'views', label: Text('بازدید')),
                ],
                selected: {_field},
                onSelectionChanged: (x) => setState(() => _field = x.first),
              ),
              const SizedBox(height: 14),
              Bars(key: ValueKey(_field), rows: series, field: _field, money: _field == 'sales', color: _field == 'views' ? C.teal : C.pink),
            ]),
          ),
          const SizedBox(height: 10),
          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                  onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const SellerStats())),
                  icon: const Icon(Icons.insights_rounded),
                  label: const Text('آمار کامل')),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: FilledButton.icon(
                  onPressed: () async {
                    final done = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const SellerQuick()));
                    if (done == true) _refresh();
                  },
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: const Text('افزودن با عکس')),
            ),
          ]),
          const SizedBox(height: 18),
          const Text('حساب شما', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
          const SizedBox(height: 10),
          Panel(
            padding: EdgeInsets.zero,
            child: Column(children: [
              for (final (k, label, hint) in const [
                ('waiting', 'در جریان ارسال', 'سفارش‌هایی که هنوز به مشتری نرسیده'),
                ('hold', 'در مهلت مرجوعی', 'تحویل شده؛ پس از مهلت مرجوعی قابل تسویه می‌شود'),
                ('payable', 'قابل تسویه', 'در نوبت واریز به حساب شما'),
                ('paid', 'واریزشده', 'جمع واریزهای گذشته'),
              ])
                ListTile(
                  dense: true,
                  title: Text(label, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                  subtitle: Text(hint, style: const TextStyle(fontSize: 12)),
                  trailing: Text(amount(asInt((bal[k] as Map?)?['amount'])),
                      style: TextStyle(fontWeight: FontWeight.w900, color: k == 'payable' ? const Color(0xFF178A4C) : C.ink)),
                ),
            ]),
          ),
          const SizedBox(height: 10),
          Text('${faDigits(asInt(_d['followers']))} نفر فروشگاه شما را دنبال می‌کنند.',
              textAlign: TextAlign.center, style: const TextStyle(color: C.muted, fontSize: 13)),
        ]),
      ),
    );
  }
}

/// راه‌اندازی فروشگاه: کارهای مانده (در پنل سایت باز می‌شوند)
class _Setup extends StatelessWidget {
  const _Setup(this.d);
  final Map<String, dynamic> d;
  @override
  Widget build(BuildContext context) {
    final steps = ((d['steps'] as List?) ?? []).cast<Map>();
    final done = asInt(d['done']), total = asInt(d['total']);
    return Panel(
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          const Expanded(child: Text('راه‌اندازی فروشگاه', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16))),
          Text('${faDigits(done)} از ${faDigits(total)}', style: const TextStyle(color: C.ink2, fontWeight: FontWeight.w700)),
        ]),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(99),
          child: LinearProgressIndicator(value: total == 0 ? 0 : done / total, minHeight: 8, backgroundColor: C.soft, color: C.pinkDark),
        ),
        const SizedBox(height: 6),
        for (final st in steps.where((x) => x['done'] != true))
          ListTile(
            dense: true,
            contentPadding: EdgeInsets.zero,
            leading: const Icon(Icons.radio_button_unchecked_rounded, color: C.muted),
            title: Text(faDigits(st['text'] ?? ''), style: const TextStyle(fontWeight: FontWeight.w700)),
            trailing: const Icon(Icons.chevron_left_rounded, color: C.muted),
            onTap: () => launchUrl(Uri.parse('$kSite${st['url']}'), mode: LaunchMode.externalApplication),
          ),
      ]),
    );
  }
}
