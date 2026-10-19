import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

/// دسته‌ها: هر دسته یک طاق در دیوار آجری؛ زیردسته‌ها روی کتیبهٔ گچی
class HouseCategories extends StatefulWidget {
  const HouseCategories({super.key});
  @override
  State<HouseCategories> createState() => _HouseCategoriesState();
}

class _HouseCategoriesState extends State<HouseCategories> with AutomaticKeepAliveClientMixin {
  List<Json>? _cats;
  String? _err;
  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = (await Api.i.get('/categories/') as List).cast<Json>();
      if (mounted) setState(() => _cats = r);
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  void _open(Json c) => Navigator.pushNamed(context, '/products', arguments: {'title': c['name'], 'query': {'category': c['id']}});

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final cats = _cats;
    return Scaffold(
      appBar: AppBar(
        title: Text('تالارها', style: nast(24, height: 1.5)),
        actions: [IconButton(tooltip: 'جستجو', onPressed: () => Navigator.pushNamed(context, '/search'), icon: const Icon(Icons.search_rounded))],
        bottom: const PreferredSize(preferredSize: Size.fromHeight(6), child: GirihBand(height: 6)),
      ),
      body: cats == null
          ? (_err != null
              ? StatusView(message: _err!, onRetry: () {
                  setState(() => _err = null);
                  _load();
                })
              : const Loading())
          : ListView(padding: const EdgeInsets.only(bottom: 24), children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 4),
                child: Row(children: [
                  Expanded(
                    child: _wide(Icons.grid_view_rounded, 'همهٔ فرش‌ها', 'از ۷۰۰ تا ۱۵۰۰ شانه', C.lapis, C.cream,
                        () => Navigator.pushNamed(context, '/products', arguments: {'title': 'همهٔ فرش‌ها', 'query': <String, dynamic>{}})),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: _wide(Icons.receipt_long_rounded, 'لیست قیمت امروز', 'همهٔ سایزها', C.soft, C.ink,
                        () => Navigator.pushNamed(context, '/pricelist')),
                  ),
                ]),
              ),
              Container(
                margin: const EdgeInsets.only(top: 14),
                decoration: const BoxDecoration(color: Color(0xFFA35E3A)),
                child: Column(children: [
                  const GirihBand(height: 8),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(12, 16, 12, 16),
                    child: LayoutBuilder(builder: (_, bc) {
                      final cw = (bc.maxWidth - 2 * 10) / 3;
                      return Wrap(spacing: 10, runSpacing: 14, children: [
                        for (final c in cats) SizedBox(width: cw, child: _arch(c)),
                      ]);
                    }),
                  ),
                ]),
              ),
              for (final c in cats.where((c) => (c['children'] as List).isNotEmpty)) _kids(c),
            ]),
    );
  }

  Widget _wide(IconData ic, String t, String sub, Color bg, Color fg, VoidCallback on) => Material(
        color: bg,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4), side: const BorderSide(color: C.rim)),
        child: InkWell(
          onTap: on,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              Icon(ic, color: fg),
              const SizedBox(width: 8),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t, style: TextStyle(fontWeight: FontWeight.w800, color: fg, fontSize: 13.5)),
                  Text(sub, style: TextStyle(color: fg.withValues(alpha: .75), fontSize: 11.5)),
                ]),
              ),
            ]),
          ),
        ),
      );

  Widget _arch(Json c) => GestureDetector(
        onTap: () => _open(c),
        child: Column(children: [
          Niche(ar: RugCrop.of(c['crop']).ar, child: RugImage(c['image'] as String? ?? '', crop: RugCrop.of(c['crop']), seed: asInt(c['id']))),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 5, horizontal: 4),
            color: C.soft,
            child: Column(children: [
              Text(faDigits(c['name']), textAlign: TextAlign.center, maxLines: 2, overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12, height: 1.5)),
              Text('${sep(asInt(c['count']))} طرح', style: const TextStyle(color: C.muted, fontSize: 11)),
            ]),
          ),
        ]),
      );

  Widget _kids(Json c) {
    final kids = (c['children'] as List).cast<Json>();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(faDigits(c['name']), style: nast(26, color: C.brickDark, height: 1.7)),
        const SizedBox(height: 6),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final k in kids)
            ActionChip(
              backgroundColor: C.soft,
              side: const BorderSide(color: C.rim),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              label: Text('${faDigits(k['name'])}  ${sep(asInt(k['count']))}'),
              onPressed: () => _open(k),
            ),
        ]),
      ]),
    );
  }
}
