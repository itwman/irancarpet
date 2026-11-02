import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

/// آمار فروشگاه: بازدید، سفارش و فروش در ۷/۳۰/۹۰ روز با مقایسه با دورهٔ پیش از آن
class SellerStats extends StatefulWidget {
  const SellerStats({super.key});
  @override
  State<SellerStats> createState() => _SellerStatsState();
}

class _SellerStatsState extends State<SellerStats> {
  int _d = 30;
  Future<Json>? _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = Api.i.get('/seller/stats/', {'d': _d}).then((v) => v as Json));

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('آمار فروشگاه')),
        body: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: SizedBox(
              width: double.infinity,
              child: SegmentedButton<int>(
                showSelectedIcon: false,
                segments: const [
                  ButtonSegment(value: 7, label: Text('۷ روز')),
                  ButtonSegment(value: 30, label: Text('۳۰ روز')),
                  ButtonSegment(value: 90, label: Text('۹۰ روز')),
                ],
                selected: {_d},
                onSelectionChanged: (x) {
                  _d = x.first;
                  _load();
                },
              ),
            ),
          ),
          Expanded(
            child: Loader<Json>(future: _future, onRetry: _load, builder: _body),
          ),
        ]),
      );

  Widget _body(Json d) {
    final t = (d['totals'] as Map).cast<String, dynamic>();
    final rows = (d['series'] as List?) ?? [];
    Map v(String k) => (t[k] as Map?) ?? {};
    final conv = t['conversion'];
    final topV = ((d['top_viewed'] as List?) ?? []).cast<Map>();
    final topS = ((d['top_sold'] as List?) ?? []).cast<Map>();
    Widget chart(String title, String field, {bool money = false, Color color = C.pink}) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Panel(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
              const SizedBox(height: 12),
              Bars(rows: rows, field: field, money: money, color: color, height: 110),
            ]),
          ),
        );

    return RefreshIndicator(
      onRefresh: () async {
        _load();
        await _future;
      },
      child: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
        Text('در مقایسه با ${faDigits(_d)} روز پیش از آن', style: const TextStyle(color: C.muted, fontSize: 12.5)),
        const SizedBox(height: 8),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 10,
          crossAxisSpacing: 10,
          childAspectRatio: 1.9,
          children: [
            Kpi(label: 'فروش', value: amount(asInt(v('sales')['value'])), change: v('sales')['change']),
            Kpi(label: 'سهم شما', value: amount(asInt(v('net')['value'])), change: v('net')['change']),
            Kpi(label: 'سفارش', value: faDigits(asInt(v('orders')['value'])), change: v('orders')['change']),
            Kpi(label: 'بازدید کل', value: faDigits(sep(asInt(v('views')['value']))), change: v('views')['change']),
            Kpi(label: 'بازدید ویترین', value: faDigits(sep(asInt(v('store')['value']))), change: v('store')['change']),
            Kpi(label: 'نرخ تبدیل', value: conv == null ? '—' : '${faDigits('$conv'.replaceAll('.', '٫'))}٪'),
          ],
        ),
        const SizedBox(height: 12),
        chart('فروش روزانه', 'sales', money: true),
        chart('سفارش روزانه', 'orders'),
        chart('بازدید کالاها', 'products', color: C.teal),
        chart('بازدید ویترین', 'store', color: C.tealDark),
        const Text('بیشترین بازدید', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
        const SizedBox(height: 8),
        _top(topV, (x) => '${faDigits(sep(asInt(x['views'])))} بازدید', 'هنوز بازدیدی ثبت نشده.'),
        const SizedBox(height: 16),
        const Text('پرفروش‌ترین‌ها', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
        const SizedBox(height: 8),
        _top(topS, (x) => '${faDigits(asInt(x['qty']))} فروش', 'در این بازه فروشی نبوده.'),
        const SizedBox(height: 12),
        const Text('بازدیدها بدون ربات‌ها شمرده می‌شوند.', textAlign: TextAlign.center, style: TextStyle(color: C.muted, fontSize: 12)),
      ]),
    );
  }

  Widget _top(List<Map> rows, String Function(Map) metric, String empty) {
    if (rows.isEmpty) return Panel(child: Text(empty, style: const TextStyle(color: C.muted)));
    return Panel(
      padding: EdgeInsets.zero,
      child: Column(children: [
        for (final x in rows)
          ListTile(
            leading: SizedBox(width: 40, height: 52, child: NetImage('${x['image'] ?? ''}', radius: 6)),
            title: Text('${x['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5)),
            trailing: Text(metric(x), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13)),
          ),
      ]),
    );
  }
}
