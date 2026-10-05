import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// لیست قیمت فرش ماشینی (همان صفحهٔ سایت): گروه‌ها بر اساس شانه، قیمت سایزهای هر لیست
class PriceListScreen extends StatefulWidget {
  const PriceListScreen({super.key});
  @override
  State<PriceListScreen> createState() => _PriceListScreenState();
}

class _PriceListScreenState extends State<PriceListScreen> {
  Json? _d;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d = await Api.i.get('/pricelist/') as Json;
      if (mounted) setState(() => (_d = d, _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final groups = ((d?['groups'] as List?) ?? []).cast<Json>();
    return Scaffold(
      appBar: AppBar(title: const Text('لیست قیمت فرش ماشینی')),
      body: d == null
          ? (_err != null
              ? StatusView(message: _err!, onRetry: () {
                  setState(() => _err = null);
                  _load();
                })
              : const Loading())
          : RefreshIndicator(
              color: C.pink,
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 28), children: [
                if ((d['updated_label'] as String? ?? '').isNotEmpty)
                  Text('آخرین تغییر قیمت: ${d['updated_label']} · ${faDigits(d['albums'])} لیست · ${faDigits(d['products'])} فرش',
                      style: const TextStyle(color: C.muted, fontSize: 12.5)),
                const SizedBox(height: 4),
                const Text('روی هر لیست بزنید تا فرش‌های همان لیست را ببینید.', style: TextStyle(color: C.ink2, fontSize: 13)),
                for (final g in groups) ..._group(g),
                if (groups.isEmpty)
                  const Padding(padding: EdgeInsets.only(top: 40), child: Center(child: Text('لیست قیمت در حال به‌روزرسانی است.'))),
              ]),
            ),
    );
  }

  Color _accent(String reeds) => switch (reeds) {
        '700' => C.teal,
        '1000' => C.saffron,
        '1200' => C.pink,
        '1500' => C.ink,
        _ => C.ink2,
      };

  List<Widget> _group(Json g) {
    final acc = _accent(g['reeds'] as String? ?? '');
    final lo = g['min_base'] as int?, hi = g['max_base'] as int?;
    return [
      Padding(
        padding: const EdgeInsets.only(top: 22, bottom: 8),
        child: Row(children: [
          Container(width: 10, height: 24, decoration: BoxDecoration(color: acc, borderRadius: BorderRadius.circular(4))),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('قیمت ${faDigits(g['title'])}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
              if (lo != null)
                Text(lo == hi ? '۱۲ متری ${toman(lo)}' : '۱۲ متری از ${sep(lo)} تا ${toman(hi)}',
                    style: const TextStyle(color: C.muted, fontSize: 12.5)),
            ]),
          ),
        ]),
      ),
      for (final a in (g['albums'] as List).cast<Json>()) _album(a, acc),
    ];
  }

  Widget _album(Json a, Color acc) {
    final prices = (a['prices'] as List).cast<Json>();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18), side: const BorderSide(color: C.line, width: 1.4)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => Navigator.pushNamed(context, '/products',
              arguments: {'title': 'لیست قیمت ${a['title']}', 'query': {'album': a['id']}}),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(faDigits(a['title']), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15)),
                    Text(
                        '${faDigits(a['count'])} فرش${(a['company'] as String? ?? '').isNotEmpty ? ' · ${a['company']}' : ''}',
                        style: const TextStyle(color: C.muted, fontSize: 12)),
                  ]),
                ),
                if (a['base_price'] != null)
                  Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                    Text(faDigits(a['base_label'] ?? '۱۲ متری'), style: const TextStyle(color: C.muted, fontSize: 11)),
                    Text(sep(a['base_price'] as int), style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16, color: acc == C.saffron ? C.ink : acc)),
                  ]),
              ]),
              const SizedBox(height: 10),
              Wrap(spacing: 6, runSpacing: 6, children: [
                for (final p in prices)
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(10)),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(faDigits(p['label']), style: const TextStyle(fontSize: 10.5, color: C.ink2)),
                      Text(sep(p['price'] as int), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w800)),
                    ]),
                  ),
              ]),
              const SizedBox(height: 8),
              Row(children: [
                Text('دیدن ${faDigits(a['count'])} فرش این لیست', style: const TextStyle(color: C.pinkDark, fontWeight: FontWeight.w800, fontSize: 13)),
                const Icon(Icons.chevron_right, color: C.pinkDark, size: 20),
              ]),
            ]),
          ),
        ),
      ),
    );
  }
}
