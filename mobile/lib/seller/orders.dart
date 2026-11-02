import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

const _filters = [
  ('open', 'باز'),
  ('new', 'تازه'),
  ('accepted', 'پذیرفته'),
  ('shipped', 'ارسال‌شده'),
  ('delivered', 'تحویل‌شده'),
  ('cancelled', 'لغوشده'),
];

const _carriers = ['پست پیشتاز', 'تیپاکس', 'باربری', 'پیک', 'چاپار', 'ماهکس'];

/// مهلت پذیرش: «۵ ساعت مانده» یا «مهلت گذشته»
String? _deadline(Json o) {
  if (o['status'] != 'new' || o['accept_until'] == null) return null;
  final until = DateTime.tryParse(o['accept_until'] as String);
  if (until == null) return null;
  final left = until.difference(DateTime.now());
  if (left.isNegative) return 'مهلت پذیرش گذشته؛ همین حالا بپذیرید یا لغو کنید';
  if (left.inHours >= 1) return '${faDigits(left.inHours)} ساعت تا پایان مهلت پذیرش';
  return '${faDigits(left.inMinutes.clamp(1, 59))} دقیقه تا پایان مهلت پذیرش';
}

class SellerOrders extends StatefulWidget {
  const SellerOrders({super.key});
  @override
  State<SellerOrders> createState() => _SellerOrdersState();
}

class _SellerOrdersState extends State<SellerOrders> {
  String _f = 'open';
  Future<Json>? _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = Api.i.get('/seller/orders/', {'f': _f}).then((v) => v as Json));

  Future<void> _open(Json o) async {
    final changed = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => OrderDetail(id: asInt(o['id']))));
    if (changed == true) _load();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: const Text('سفارش‌ها'),
          bottom: PreferredSize(
            preferredSize: const Size.fromHeight(52),
            child: SizedBox(
              height: 52,
              child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), children: [
                for (final (k, label) in _filters)
                  Padding(
                    padding: const EdgeInsetsDirectional.only(end: 8),
                    child: ChoiceChip(
                        label: Text(label),
                        selected: _f == k,
                        onSelected: (_) {
                          _f = k;
                          _load();
                        }),
                  ),
              ]),
            ),
          ),
        ),
        body: RefreshIndicator(
          onRefresh: () async {
            _load();
            await _future;
          },
          child: Loader<Json>(
            future: _future,
            onRetry: _load,
            builder: (d) {
              final items = ((d['items'] as List?) ?? []).cast<Map>().map((e) => e.cast<String, dynamic>()).toList();
              if (items.isEmpty) {
                return Empty(_f == 'open' ? 'سفارش بازی ندارید. سفارش تازه که برسد، پیامک هم می‌گیرید.' : 'سفارشی در این بخش نیست.',
                    icon: Icons.shopping_bag_outlined);
              }
              return ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: items.length,
                separatorBuilder: (_, _) => const SizedBox(height: 10),
                itemBuilder: (_, i) {
                  final o = items[i];
                  final dl = _deadline(o);
                  return Panel(
                    onTap: () => _open(o),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        Text('سفارش ${faDigits(o['number'] ?? '')}', style: const TextStyle(fontWeight: FontWeight.w900)),
                        const Spacer(),
                        Pill('${o['status_label']}', color: orderColor('${o['status']}')),
                      ]),
                      const SizedBox(height: 6),
                      Row(children: [
                        Expanded(child: Text(jdate(o['paid_at'] as String?, time: true), style: const TextStyle(color: C.muted, fontSize: 13))),
                        Text('سهم شما: ${amount(asInt(o['share']))}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
                      ]),
                      if (dl != null) ...[
                        const SizedBox(height: 8),
                        Row(children: [
                          const Icon(Icons.timer_outlined, size: 16, color: Color(0xFFB45309)),
                          const SizedBox(width: 6),
                          Expanded(child: Text(dl, style: const TextStyle(color: Color(0xFFB45309), fontSize: 13, fontWeight: FontWeight.w700))),
                        ]),
                      ],
                    ]),
                  );
                },
              );
            },
          ),
        ),
      );
}

class OrderDetail extends StatefulWidget {
  const OrderDetail({super.key, required this.id});
  final int id;
  @override
  State<OrderDetail> createState() => _OrderDetailState();
}

class _OrderDetailState extends State<OrderDetail> {
  Future<Json>? _future;
  bool _changed = false, _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = Api.i.get('/seller/orders/${widget.id}/').then((v) => v as Json));

  Future<void> _act(Json body, String done) async {
    setState(() => _busy = true);
    final r = await run(context, () async => await Api.i.post('/seller/orders/${widget.id}/', body) as Json);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      _changed = true;
      setState(() => _future = Future.value(r));
      toast(context, done);
    }
  }

  Future<void> _accept() async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        title: const Text('پذیرش سفارش'),
        content: const Text('با پذیرش، نشانی و شمارهٔ مشتری را می‌بینید و باید کالا را در مهلت تعیین‌شده ارسال کنید.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('انصراف')),
          FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('می‌پذیرم')),
        ],
      ),
    );
    if (ok == true) _act({'act': 'accept'}, 'سفارش پذیرفته شد.');
  }

  Future<void> _ship(Json o) async {
    final code = TextEditingController(text: '${o['tracking_code'] ?? ''}');
    final carrier = TextEditingController(text: '${o['carrier'] ?? ''}');
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(c).viewInsets.bottom),
        child: StatefulBuilder(
          builder: (c, set) => Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Text('ثبت ارسال', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
            const SizedBox(height: 4),
            const Text('کد رهگیری برای مشتری پیامک می‌شود.', style: TextStyle(color: C.muted)),
            const SizedBox(height: 14),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final x in _carriers)
                ChoiceChip(label: Text(x), selected: carrier.text == x, onSelected: (_) => set(() => carrier.text = x)),
            ]),
            const SizedBox(height: 12),
            TextField(controller: carrier, decoration: const InputDecoration(labelText: 'شرکت حمل'), onChanged: (_) => set(() {})),
            const SizedBox(height: 12),
            TextField(
              controller: code,
              textDirection: TextDirection.ltr,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'کد رهگیری یا شمارهٔ بارنامه'),
            ),
            const SizedBox(height: 16),
            FilledButton(onPressed: () => Navigator.pop(c, true), child: const Text('ثبت ارسال')),
          ]),
        ),
      ),
    );
    if (ok == true) {
      _act({'act': 'ship', 'tracking_code': latin(code.text.trim()), 'carrier': carrier.text.trim()}, 'ارسال ثبت شد و مشتری باخبر شد.');
    }
  }

  Future<void> _cancel() async {
    final reason = TextEditingController();
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (c) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(c).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('لغو سفارش', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          const SizedBox(height: 4),
          const Text('لغو پیاپی در کارنامهٔ فروشگاه اثر می‌گذارد. مبلغ به مشتری برگردانده می‌شود.', style: TextStyle(color: C.muted)),
          const SizedBox(height: 12),
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final x in const ['کالا تمام شده', 'سایز موجود نیست', 'رنگ موجود نیست'])
              ActionChip(label: Text(x), onPressed: () => reason.text = x),
          ]),
          const SizedBox(height: 12),
          TextField(controller: reason, maxLines: 2, decoration: const InputDecoration(labelText: 'دلیل لغو')),
          const SizedBox(height: 16),
          FilledButton(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFFB42318)),
              onPressed: () => Navigator.pop(c, true),
              child: const Text('لغو سفارش')),
        ]),
      ),
    );
    if (ok == true) _act({'act': 'cancel', 'reason': reason.text.trim()}, 'سفارش لغو شد.');
  }

  @override
  Widget build(BuildContext context) => PopScope(
        canPop: false,
        onPopInvokedWithResult: (did, _) {
          if (!did) Navigator.pop(context, _changed);
        },
        child: Scaffold(
          appBar: AppBar(title: const Text('جزئیات سفارش')),
          body: Loader<Json>(
            future: _future,
            onRetry: _load,
            builder: (o) {
              final st = '${o['status']}';
              final cu = ((o['customer'] as Map?) ?? {}).cast<String, dynamic>();
              final items = ((o['items'] as List?) ?? []).cast<Map>();
              final dl = _deadline(o);
              final mobile = '${cu['mobile'] ?? ''}';
              return ListView(padding: const EdgeInsets.all(16), children: [
                Row(children: [
                  Expanded(
                      child: Text('سفارش ${faDigits(o['number'] ?? '')}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900))),
                  Pill('${o['status_label']}', color: orderColor(st)),
                ]),
                const SizedBox(height: 4),
                Text('پرداخت: ${jdate(o['paid_at'] as String?, time: true)}', style: const TextStyle(color: C.muted)),
                if (dl != null) ...[
                  const SizedBox(height: 8),
                  Text(dl, style: const TextStyle(color: Color(0xFFB45309), fontWeight: FontWeight.w700)),
                ],
                const SizedBox(height: 14),
                Panel(
                  padding: EdgeInsets.zero,
                  child: Column(children: [
                    for (final it in items)
                      ListTile(
                        title: Text('${it['title']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
                        subtitle: Text('${faDigits(it['size'] ?? '')} · ${faDigits(asInt(it['qty']))} عدد'),
                        trailing: Text(amount(asInt(it['price']) * asInt(it['qty']))),
                      ),
                    const Divider(height: 1),
                    ListTile(
                      dense: true,
                      title: const Text('جمع کالاها'),
                      trailing: Text(amount(asInt(o['total'])), style: const TextStyle(fontWeight: FontWeight.w700)),
                    ),
                    ListTile(
                      dense: true,
                      title: const Text('سهم شما (پس از کارمزد)'),
                      trailing: Text(amount(asInt(o['share'])), style: const TextStyle(fontWeight: FontWeight.w900, color: Color(0xFF178A4C))),
                    ),
                  ]),
                ),
                const SizedBox(height: 14),
                Panel(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('گیرنده', style: TextStyle(fontWeight: FontWeight.w900)),
                    const SizedBox(height: 8),
                    Text('${cu['name'] ?? ''}'),
                    const SizedBox(height: 4),
                    Text(faDigits(cu['address'] ?? ''), style: const TextStyle(color: C.ink2)),
                    if ('${cu['postal_code'] ?? ''}'.isNotEmpty) Text('کد پستی: ${faDigits(cu['postal_code'])}', style: const TextStyle(color: C.ink2)),
                    if (mobile.isNotEmpty)
                      Row(children: [
                        Expanded(child: Text(faDigits(mobile), textDirection: TextDirection.ltr, textAlign: TextAlign.right)),
                        IconButton(
                            tooltip: 'کپی شماره',
                            icon: const Icon(Icons.copy_rounded, size: 20),
                            onPressed: () {
                              Clipboard.setData(ClipboardData(text: mobile));
                              toast(context, 'شماره کپی شد.');
                            }),
                      ]),
                    if (st == 'new')
                      const Padding(
                        padding: EdgeInsets.only(top: 8),
                        child: Text('نشانی کامل و شمارهٔ مشتری پس از پذیرش سفارش نمایش داده می‌شود.',
                            style: TextStyle(color: C.muted, fontSize: 12.5)),
                      ),
                  ]),
                ),
                if ('${o['tracking_code'] ?? ''}'.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Panel(
                    child: Text('ارسال با ${o['carrier'] ?? '—'} · کد رهگیری ${faDigits(o['tracking_code'])}'),
                  ),
                ],
                if (st == 'cancelled' && '${o['cancel_reason'] ?? ''}'.isNotEmpty) ...[
                  const SizedBox(height: 14),
                  Panel(child: Text('دلیل لغو: ${o['cancel_reason']}')),
                ],
                const SizedBox(height: 20),
                if (_busy) const Center(child: CircularProgressIndicator()),
                if (!_busy && st == 'new') ...[
                  FilledButton.icon(onPressed: _accept, icon: const Icon(Icons.check_rounded), label: const Text('پذیرش سفارش')),
                  const SizedBox(height: 8),
                  OutlinedButton(onPressed: () => _ship(o), child: const Text('همین حالا ارسال کرده‌ام')),
                ],
                if (!_busy && st == 'accepted')
                  FilledButton.icon(onPressed: () => _ship(o), icon: const Icon(Icons.local_shipping_outlined), label: const Text('ثبت ارسال')),
                if (!_busy && st == 'shipped')
                  OutlinedButton(onPressed: () => _ship(o), child: const Text('اصلاح کد رهگیری')),
                if (!_busy && (st == 'new' || st == 'accepted'))
                  TextButton(
                      onPressed: _cancel,
                      child: const Text('لغو سفارش', style: TextStyle(color: Color(0xFFB42318)))),
              ]);
            },
          ),
        ),
      );
}
