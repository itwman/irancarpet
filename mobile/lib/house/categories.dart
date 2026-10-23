import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'home.dart';
import 'ui.dart';

/// زبانهٔ «دسته‌بندی» فرشستان: جستجو، میان‌برهای همهٔ فرش‌ها و لیست قیمت، دسته‌ها با تصویر دایره‌ای و زیردسته‌ها
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
      final r = asList(await Api.i.get('/categories/'));
      if (mounted) setState(() => (_cats = r, _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  void _open(Json c) => Navigator.pushNamed(context, '/products', arguments: {'title': faDigits(c['name'] ?? ''), 'query': {'category': c['id']}});

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final cats = _cats;
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        scrolledUnderElevation: 0,
        title: const Text('دسته‌بندی'),
        bottom: const PreferredSize(preferredSize: Size.fromHeight(64), child: HouseSearchBar(hint: 'جستجو در همهٔ فرش‌ها')),
      ),
      body: cats == null
          ? (_err != null
              ? StatusView(message: _err!, onRetry: () {
                  setState(() => _err = null);
                  _load();
                })
              : const Loading())
          : RefreshIndicator(
              color: C.brand,
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.only(bottom: 28), children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
                  child: Row(children: [
                    Expanded(
                      child: _quick(Icons.grid_view_rounded, 'همهٔ فرش‌ها', 'همهٔ طرح‌ها و سایزها', true,
                          () => Navigator.pushNamed(context, '/products', arguments: {'title': 'همهٔ فرش‌ها', 'query': <String, dynamic>{}})),
                    ),
                    const SizedBox(width: 10),
                    Expanded(
                      child: _quick(Icons.receipt_long_rounded, 'لیست قیمت امروز', 'قیمت روز همهٔ سایزها', false,
                          () => Navigator.pushNamed(context, '/pricelist')),
                    ),
                  ]),
                ),
                const SecHead('دسته‌های اصلی'),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 8),
                  child: LayoutBuilder(builder: (_, bc) {
                    final cols = bc.maxWidth >= 600 ? 5 : 3;
                    final cw = bc.maxWidth / cols;
                    return Wrap(runSpacing: 6, children: [
                      for (final c in cats)
                        SizedBox(
                          width: cw,
                          child: Center(child: CatCircle(c, count: asInt(c['count']), size: 78, onTap: () => _open(c))),
                        ),
                    ]);
                  }),
                ),
                for (final c in cats.where((c) => asList(c['children']).isNotEmpty)) _kids(c),
              ]),
            ),
    );
  }

  Widget _quick(IconData ic, String t, String sub, bool primary, VoidCallback on) => Material(
        color: primary ? C.brand : C.surface2,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: BorderSide(color: primary ? C.brand : C.line)),
        child: InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: on,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(color: primary ? const Color(0x24FFFFFF) : C.brand50, borderRadius: BorderRadius.circular(10)),
                child: Icon(ic, color: primary ? Colors.white : C.brand, size: 20),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t, maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.w800, color: primary ? Colors.white : C.ink, fontSize: 13.5)),
                  Text(sub, maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: primary ? const Color(0xFFC9D4EE) : C.muted, fontSize: 11.5)),
                ]),
              ),
            ]),
          ),
        ),
      );

  Widget _kids(Json c) {
    final kids = asList(c['children']);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SecHead(faDigits(c['name'] ?? ''), action: 'همه', onAction: () => _open(c)),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Wrap(spacing: 8, runSpacing: 8, children: [
          for (final k in kids)
            ActionChip(
              backgroundColor: Colors.white,
              side: const BorderSide(color: C.line),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
              label: Text.rich(TextSpan(children: [
                TextSpan(text: faDigits(k['name'] ?? ''), style: const TextStyle(fontWeight: FontWeight.w700, color: C.ink2)),
                TextSpan(text: '  ${sep(asInt(k['count']))}', style: const TextStyle(color: C.muted, fontSize: 12)),
              ])),
              onPressed: () => _open(k),
            ),
        ]),
      ),
    ]);
  }
}
