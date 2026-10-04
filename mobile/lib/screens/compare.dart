import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class CompareScreen extends StatefulWidget {
  const CompareScreen({super.key});
  @override
  State<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends State<CompareScreen> {
  final Map<int, Json> _data = {};

  Future<void> _ensure(List<int> ids) async {
    for (final id in ids.where((i) => !_data.containsKey(i))) {
      try {
        _data[id] = await Api.i.get('/products/$id/') as Json;
        if (mounted) setState(() {});
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    final cmp = context.watch<Compare>();
    _ensure(cmp.ids);
    final ps = cmp.ids.map((i) => _data[i]).whereType<Json>().toList();
    final specNames = <String>{for (final p in ps) for (final s in (p['specs'] as List).cast<Json>()) s['name'] as String};
    String spec(Json p, String n) => (p['specs'] as List).cast<Json>().where((s) => s['name'] == n).map((s) => s['value'] as String).firstOrNull ?? '—';
    Json? size12(Json p) => (p['sizes'] as List).cast<Json>().where((s) => (s['label'] as String).contains('۱۲')).firstOrNull;
    const colW = 150.0;
    Widget row(String label, Widget Function(Json) cell, {bool shade = false}) => Container(
          color: shade ? C.soft : Colors.white,
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            SizedBox(width: 92, child: Padding(padding: const EdgeInsets.all(10), child: Text(label, style: const TextStyle(color: C.muted, fontSize: 12.5)))),
            for (final p in ps) SizedBox(width: colW, child: Padding(padding: const EdgeInsets.all(10), child: cell(p))),
          ]),
        );
    return Scaffold(
      appBar: AppBar(title: const Text('مقایسهٔ فرش‌ها')),
      body: cmp.ids.isEmpty
          ? const StatusView(message: 'از صفحهٔ هر فرش، دکمهٔ مقایسه را بزنید (تا ۳ فرش).', icon: Icons.compare_outlined)
          : ps.length < cmp.ids.length
              ? const Loading()
              : SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: SingleChildScrollView(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      row('', (p) => Column(children: [
                            AspectRatio(aspectRatio: 3 / 4, child: NetImage(p['image'] as String, radius: 12)),
                            TextButton(onPressed: () => cmp.toggle(p['id'] as int), child: const Text('حذف')),
                          ])),
                      row('نام', (p) => InkWell(
                          onTap: () => Navigator.pushNamed(context, '/product', arguments: p['id']),
                          child: Text(p['title'] as String, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)))),
                      row('شانه', (p) => Align(alignment: AlignmentDirectional.centerStart, child: ReedsBadge(p['reeds'] as String)), shade: true),
                      row('۱۲ متری', (p) {
                        final s = size12(p);
                        return s == null ? const Text('—') : Price(s['price'] as int, size: 13.5);
                      }),
                      row('سایزها', (p) => Text('${(p['sizes'] as List).length} سایز'), shade: true),
                      for (final (i, n) in specNames.indexed) row(n, (p) => Text(spec(p, n), style: const TextStyle(fontSize: 13)), shade: i.isOdd),
                    ]),
                  ),
                ),
    );
  }
}
