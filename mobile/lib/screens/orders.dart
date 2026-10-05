import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/installment.dart';

Color statusColor(String s) => switch (s) {
      'pending' => C.saffron,
      'cancelled' || 'refunded' => C.muted,
      'shipped' || 'completed' => C.pistachio,
      _ => C.teal,
    };

class OrdersScreen extends StatefulWidget {
  const OrdersScreen({super.key});
  @override
  State<OrdersScreen> createState() => _OrdersScreenState();
}

class _OrdersScreenState extends State<OrdersScreen> {
  List<Json>? _list;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = (await Api.i.get('/orders/') as List).cast<Json>();
      if (mounted) setState(() => _list = r);
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('سفارش‌های من')),
      body: _list == null
          ? (_err != null ? StatusView(message: _err!, onRetry: _load) : const Loading())
          : _list!.isEmpty
              ? const StatusView(message: 'هنوز سفارشی ثبت نکرده‌اید.', icon: Icons.receipt_long_outlined)
              : RefreshIndicator(
                  color: C.pink,
                  onRefresh: _load,
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: _list!.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (_, i) {
                      final o = _list![i];
                      return Material(
                        color: C.soft,
                        borderRadius: BorderRadius.circular(18),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(18),
                          onTap: () => Navigator.pushNamed(context, '/order', arguments: {'number': o['number']}).then((_) => _load()),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Row(children: [
                              Expanded(
                                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                  Text('سفارش ${faDigits(o['number'])}', style: const TextStyle(fontWeight: FontWeight.w900)),
                                  Text('${faDigits(o['items_count'])} قلم · ${toman(o['items_total'] as int)}', style: const TextStyle(color: C.muted, fontSize: 13)),
                                ]),
                              ),
                              _StatusPill(o['status'] as String, o['status_label'] as String),
                            ]),
                          ),
                        ),
                      );
                    },
                  ),
                ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill(this.status, this.label);
  final String status, label;
  @override
  Widget build(BuildContext context) {
    final c = statusColor(status);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: c.withValues(alpha: .16), borderRadius: BorderRadius.circular(10)),
      child: Text(label, style: TextStyle(color: c == C.saffron ? const Color(0xFF9A6400) : (c == C.pistachio ? const Color(0xFF3D7A2F) : c),
          fontWeight: FontWeight.w800, fontSize: 12.5)),
    );
  }
}

class OrderScreen extends StatefulWidget {
  const OrderScreen({super.key, required this.number, this.justPaid = false});
  final int number;
  final bool justPaid;
  @override
  State<OrderScreen> createState() => _OrderScreenState();
}

class _OrderScreenState extends State<OrderScreen> with WidgetsBindingObserver {
  Json? _o;
  String? _err;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // برگشت از مرورگر/بانک
  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.resumed) _load();
  }

  Future<void> _load() async {
    try {
      final o = await Api.i.get('/orders/${widget.number}/') as Json;
      if (!mounted) return;
      if (o['status'] != 'pending') context.read<Cart>().clear();
      setState(() => _o = o);
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  Future<void> _pay(String gw) async {
    setState(() => _busy = true);
    try {
      final r = await Api.i.post('/orders/${widget.number}/', {'gateway': gw}) as Json;
      await launchUrl(Uri.parse(r['pay_url'] as String), mode: LaunchMode.externalApplication);
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final o = _o;
    final gws = context.watch<AppConfig>().gateways;
    return Scaffold(
      appBar: AppBar(title: Text('سفارش ${faDigits(widget.number)}')),
      body: o == null
          ? (_err != null ? StatusView(message: _err!, onRetry: _load) : const Loading())
          : RefreshIndicator(
              color: C.pink,
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                if (o['status'] != 'pending' && (widget.justPaid || o['paid_amount'] as int > 0))
                  _banner(C.tealTint, C.tealDark, Icons.check_circle_rounded,
                      widget.justPaid ? 'پرداخت انجام شد؛ سفارش شما ثبت شد.' : 'پرداخت این سفارش انجام شده است.'),
                if (o['status'] == 'pending')
                  _banner(C.saffronTint, const Color(0xFF9A6400), Icons.schedule_rounded,
                      o['installment'] != null
                          ? 'پیش‌پرداخت این سفارش هنوز پرداخت نشده است.'
                          : 'سفارش منتظر پرداخت است. اگر پرداخت را انجام داده‌اید، صفحه را پایین بکشید تا به‌روز شود.'),
                if (o['status'] == 'on_hold')
                  _banner(C.saffronTint, const Color(0xFF9A6400), Icons.hourglass_top_rounded,
                      'درخواست خرید اقساطی ثبت شد و در حال بررسی است؛ نتیجه را با پیامک خبر می‌دهیم.'),
                const SizedBox(height: 12),
                _row('وضعیت', o['status_label'] as String, bold: true),
                _row('جمع کالاها', toman(o['items_total'] as int)),
                _row('پرداخت‌شده', amount(o['paid_amount'] as int)),
                if ((o['remaining'] as int) > 0 && o['status'] != 'pending')
                  _row(o['installment'] != null ? 'مانده (اقساط)' : 'مانده (موقع تحویل)', toman(o['remaining'] as int)),
                _row('ارسال', o['shipping_mode'] == 'free' ? 'رایگان' : 'پس‌کرایه (موقع تحویل)'),
                if ((o['tracking_code'] as String).isNotEmpty) _row('کد رهگیری مرسوله', faDigits(o['tracking_code'])),
                if (o['installment'] != null) ...[
                  const SizedBox(height: 12),
                  InstallmentSummary((o['installment'] as Json)),
                ],
                const SizedBox(height: 12),
                const Text('اقلام', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                for (final it in (o['items'] as List).cast<Json>())
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: SizedBox(width: 48, height: 64, child: NetImage(it['image'] as String, radius: 8)),
                    title: Text(it['title'] as String, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
                    subtitle: Text('${it['size']} · ${faDigits(it['quantity'])} عدد'),
                    trailing: Text(sep((it['unit_price'] as int) * (it['quantity'] as int))),
                    onTap: it['product_id'] == null ? null : () => Navigator.pushNamed(context, '/product', arguments: it['product_id']),
                  ),
                const SizedBox(height: 8),
                const Text('نشانی', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                Builder(builder: (_) {
                  final a = o['address'] as Json;
                  return Text('${a['first_name']} ${a['last_name']} · ${faDigits(a['mobile'])}\n${a['province']}، ${a['city']}، ${a['address']}',
                      style: const TextStyle(color: C.ink2));
                }),
              ]),
            ),
      bottomNavigationBar: o != null && o['can_pay'] == true && gws.isNotEmpty
          ? SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
                child: FilledButton(
                  onPressed: _busy ? null : () => _pay(gws.first['key'] as String),
                  child: Text('${o['installment'] != null ? 'پرداخت پیش‌پرداخت' : 'پرداخت'} ${toman(o['online_amount'] as int)}'),
                ),
              ),
            )
          : null,
    );
  }

  Widget _banner(Color bg, Color fg, IconData i, String t) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(16)),
        child: Row(children: [Icon(i, color: fg), const SizedBox(width: 10), Expanded(child: Text(t, style: TextStyle(color: fg, fontWeight: FontWeight.w700)))]),
      );

  Widget _row(String k, String v, {bool bold = false}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Expanded(child: Text(k, style: const TextStyle(color: C.muted))),
          Text(v, style: TextStyle(fontWeight: bold ? FontWeight.w900 : FontWeight.w700)),
        ]),
      );
}

class TrackScreen extends StatefulWidget {
  const TrackScreen({super.key});
  @override
  State<TrackScreen> createState() => _TrackScreenState();
}

class _TrackScreenState extends State<TrackScreen> {
  final _n = TextEditingController(), _m = TextEditingController();
  Json? _o;
  String? _err;

  Future<void> _go() async {
    try {
      final o = await Api.i.post('/track/', {'number': latin(_n.text), 'mobile': latin(_m.text)}) as Json;
      setState(() => (_o = o, _err = null));
    } on ApiError catch (e) {
      setState(() => (_err = e.message, _o = null));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('پیگیری سفارش')),
        body: ListView(padding: const EdgeInsets.all(20), children: [
          const Text('شمارهٔ سفارش و موبایلی را که با آن سفارش داده‌اید وارد کنید.', style: TextStyle(color: C.muted)),
          const FieldLabel('شمارهٔ سفارش'),
          TextField(controller: _n, keyboardType: TextInputType.number, textDirection: TextDirection.ltr),
          const FieldLabel('موبایل'),
          TextField(controller: _m, keyboardType: TextInputType.phone, textDirection: TextDirection.ltr),
          const SizedBox(height: 16),
          FilledButton(onPressed: _go, child: const Text('پیگیری')),
          if (_err != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(_err!, style: const TextStyle(color: C.pinkDark))),
          if (_o != null)
            Container(
              margin: const EdgeInsets.only(top: 16),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(16)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('سفارش ${faDigits(_o!['number'])}', style: const TextStyle(fontWeight: FontWeight.w900)),
                const SizedBox(height: 6),
                _StatusPill(_o!['status'] as String, _o!['status_label'] as String),
                if ((_o!['tracking_code'] as String).isNotEmpty) Text('کد رهگیری مرسوله: ${faDigits(_o!['tracking_code'])}'),
              ]),
            ),
        ]),
      );
}
