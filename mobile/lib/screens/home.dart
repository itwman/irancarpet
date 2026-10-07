import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/brand.dart';
import '../widgets/common.dart';
import '../widgets/knots.dart';
import '../widgets/offers.dart';
import 'shell.dart';

class HomeTab extends StatefulWidget {
  const HomeTab({super.key});
  @override
  State<HomeTab> createState() => _HomeTabState();
}

class _HomeTabState extends State<HomeTab> with AutomaticKeepAliveClientMixin {
  Json? _d;
  String? _err;
  int _reeds = 0;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d = await Api.i.get('/home/') as Json;
      if (mounted) setState(() => (_d = d, _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final d = _d;
    return Scaffold(
      body: SafeArea(
        child: d == null
            ? (_err != null ? StatusView(message: _err!, onRetry: () {
                setState(() => _err = null);
                _load();
              }) : const Loading())
            : RefreshIndicator(
                color: C.pink,
                onRefresh: _load,
                child: CustomScrollView(slivers: [
                  SliverToBoxAdapter(child: _top(context)),
                  SliverToBoxAdapter(child: _hero(context, d)),
                  SliverToBoxAdapter(child: _quick(context)),
                  if ((d['notice'] as String? ?? '').isNotEmpty) SliverToBoxAdapter(child: _notice(d['notice'] as String)),
                  if (((d['offers'] as List?) ?? []).isNotEmpty)
                    SliverToBoxAdapter(child: OffersStrip((d['offers'] as List).cast<Json>())),
                  SliverToBoxAdapter(child: _categories(context, d)),
                  if ((d['reeds'] as List).isNotEmpty) ..._reedsSection(context, d),
                  SliverToBoxAdapter(
                      child: SectionTitle('تازه‌ترین نقشه‌ها', action: 'همه',
                          onAction: () => Navigator.pushNamed(context, '/products',
                              arguments: {'title': 'تازه‌ترین فرش‌ها', 'query': {'sort': 'new'}}))),
                  SliverToBoxAdapter(child: _row((d['newest'] as List).cast<Json>())),
                  SliverToBoxAdapter(child: _roomCard(context, d)),
                  SliverToBoxAdapter(
                      child: SectionTitle('پربازدیدها', action: 'همه',
                          onAction: () => Navigator.pushNamed(context, '/products',
                              arguments: {'title': 'پربازدیدترین فرش‌ها', 'query': {'sort': 'popular'}}))),
                  _grid((d['popular'] as List).cast<Json>()),
                  SliverToBoxAdapter(child: _trust(d)),
                  const SliverToBoxAdapter(child: SizedBox(height: 24)),
                ]),
              ),
      ),
    );
  }

  Widget _top(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 8, 4),
        child: Row(children: [
          const BrandLogo(size: 40),
          const SizedBox(width: 10),
          const Expanded(child: Align(alignment: AlignmentDirectional.centerStart, child: Wordmark(height: 25))),
          IconButton(
              tooltip: 'اعلان‌ها', onPressed: () => Navigator.pushNamed(context, '/notifications'), icon: const Icon(Icons.notifications_none_rounded)),
        ]),
      );

  Widget _hero(BuildContext context, Json d) {
    final rating = d['rating'] as Json;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 0),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(26),
        child: Container(
          color: C.ink,
          child: Stack(children: [
            const Positioned.fill(child: Opacity(opacity: .55, child: KnotField(height: 260))),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('فرش خانه‌ات را\nگره‌به‌گره انتخاب کن',
                    style: TextStyle(color: Colors.white, fontSize: 25, fontWeight: FontWeight.w900, height: 1.45)),
                const SizedBox(height: 8),
                if ((rating['count'] as int) > 0)
                  Text('${rating['avg']} از ۵ در ${sep(rating['count'] as int)} نظر خریدار',
                      style: TextStyle(color: Colors.white.withValues(alpha: .85), fontSize: 13)),
                const SizedBox(height: 16),
                // جستجو
                Material(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(16),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(16),
                    onTap: () => Navigator.pushNamed(context, '/search'),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                      child: Row(children: [
                        Icon(Icons.search_rounded, color: C.muted),
                        SizedBox(width: 8),
                        Text('نقشه، رنگ یا کد فرش…', style: TextStyle(color: C.muted)),
                      ]),
                    ),
                  ),
                ),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  /// دو میان‌بر: لیست قیمت و خرید اقساطی
  Widget _quick(BuildContext context) {
    final hasInst = context.watch<AppConfig>().installmentPlans.isNotEmpty;
    Widget tile(IconData icon, String t, String sub, Color bg, Color fg, String route) => Expanded(
          child: Material(
            color: bg,
            borderRadius: BorderRadius.circular(18),
            child: InkWell(
              borderRadius: BorderRadius.circular(18),
              onTap: () => Navigator.pushNamed(context, route),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Row(children: [
                  Icon(icon, color: fg, size: 26),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(t, style: TextStyle(fontWeight: FontWeight.w900, color: fg)),
                      Text(sub, style: const TextStyle(fontSize: 11.5, color: C.ink2), maxLines: 1, overflow: TextOverflow.ellipsis),
                    ]),
                  ),
                ]),
              ),
            ),
          ),
        );
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Row(children: [
        tile(Icons.receipt_long_rounded, 'لیست قیمت', 'قیمت روز همهٔ سایزها', C.tealTint, C.tealDark, '/pricelist'),
        if (hasInst) ...[
          const SizedBox(width: 10),
          tile(Icons.calendar_month_rounded, 'خرید اقساطی', 'چک صیادی و بازنشستگان', C.saffronTint, const Color(0xFF8A5A00), '/installment'),
        ],
      ]),
    );
  }

  Widget _notice(String t) => Container(
        margin: const EdgeInsets.fromLTRB(16, 14, 16, 0),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(16)),
        child: Row(children: [const KnotIcon(c1: C.saffron, c2: C.pink, size: 22), const SizedBox(width: 10), Expanded(child: Text(t))]),
      );

  Widget _categories(BuildContext context, Json d) {
    final cats = (d['categories'] as List).cast<Json>();
    if (cats.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('دسته‌ها', action: 'همه', onAction: () => Shell.goTab(context, 1)),
      SizedBox(
        height: 104,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: cats.length,
          separatorBuilder: (_, _) => const SizedBox(width: 12),
          itemBuilder: (_, i) {
            final c = cats[i];
            final colors = [C.pinkTint, C.tealTint, C.saffronTint, const Color(0xFFEFF8EC)];
            return InkWell(
              borderRadius: BorderRadius.circular(18),
              onTap: () => Navigator.pushNamed(context, '/products', arguments: {'title': c['name'], 'query': {'category': c['id']}}),
              child: SizedBox(
                width: 78,
                child: Column(children: [
                  Container(
                    width: 64,
                    height: 64,
                    decoration: BoxDecoration(color: colors[i % 4], borderRadius: BorderRadius.circular(20)),
                    clipBehavior: Clip.antiAlias,
                    child: (c['image'] as String).isEmpty
                        ? Center(child: KnotIcon(c1: [C.pink, C.teal, C.saffron, C.pistachio][i % 4], c2: C.ink.withValues(alpha: .15)))
                        : NetImage(c['image'] as String),
                  ),
                  const SizedBox(height: 6),
                  Text(c['name'] as String, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600)),
                ]),
              ),
            );
          },
        ),
      ),
    ]);
  }

  List<Widget> _reedsSection(BuildContext context, Json d) {
    final groups = (d['reeds'] as List).cast<Json>();
    final g = groups[_reeds.clamp(0, groups.length - 1)];
    return [
      const SliverToBoxAdapter(child: SectionTitle('شانه‌ات را انتخاب کن', subtitle: 'هرچه شانه بیشتر، گره‌ها ریزتر و نقش ظریف‌تر')),
      SliverToBoxAdapter(
        child: SizedBox(
          height: 44,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: groups.length,
            separatorBuilder: (_, _) => const SizedBox(width: 8),
            itemBuilder: (_, i) {
              final on = i == _reeds;
              final c = C.reeds(groups[i]['slug'] as String);
              return ChoiceChip(
                selected: on,
                onSelected: (_) => setState(() => _reeds = i),
                showCheckmark: false,
                avatar: Container(width: 10, height: 10, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(3))),
                label: Text('${groups[i]['name']} شانه'),
              );
            },
          ),
        ),
      ),
      SliverToBoxAdapter(
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 280),
          child: KeyedSubtree(key: ValueKey(_reeds), child: _row((g['products'] as List).cast<Json>())),
        ),
      ),
      SliverToBoxAdapter(
        child: Align(
          alignment: AlignmentDirectional.centerStart,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: TextButton(
              onPressed: () => Navigator.pushNamed(context, '/products',
                  arguments: {'title': 'فرش ${g['name']} شانه', 'query': {'reeds': g['term_id']}}),
              child: Text('همهٔ فرش‌های ${g['name']} شانه', style: const TextStyle(color: C.pinkDark, fontWeight: FontWeight.w700)),
            ),
          ),
        ),
      ),
    ];
  }

  Widget _row(List<Json> items) => SizedBox(
        height: 300,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          itemCount: items.length,
          separatorBuilder: (_, _) => const SizedBox(width: 12),
          itemBuilder: (_, i) => ProductCard(items[i], width: 160),
        ),
      );

  Widget _grid(List<Json> items) => SliverPadding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        sliver: SliverGrid(
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2, mainAxisSpacing: 14, crossAxisSpacing: 12, childAspectRatio: .54),
          delegate: SliverChildBuilderDelegate((_, i) => ProductCard(items[i]), childCount: items.length),
        ),
      );

  Widget _roomCard(BuildContext context, Json d) {
    final first = (d['popular'] as List).isNotEmpty ? (d['popular'] as List).first as Json : null;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 22, 16, 0),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: C.tealTint, borderRadius: BorderRadius.circular(24)),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('فرش را در اتاقت ببین', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: C.tealDark)),
            const SizedBox(height: 4),
            const Text('دوربین گوشی را رو به کف اتاق بگیر؛ فرش با اندازهٔ واقعی‌اش روی زمین می‌نشیند.',
                style: TextStyle(fontSize: 13, color: C.ink2)),
            const SizedBox(height: 10),
            FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: C.tealDark, minimumSize: const Size(10, 44)),
              onPressed: first == null ? null : () => Navigator.pushNamed(context, '/room', arguments: {'id': first['id']}),
              icon: const Icon(Icons.view_in_ar_rounded, size: 20),
              label: const Text('امتحان کن'),
            ),
          ]),
        ),
        const SizedBox(width: 12),
        if (first != null)
          Transform.rotate(angle: -.12, child: SizedBox(width: 86, height: 115, child: NetImage(first['image'] as String, radius: 14))),
      ]),
    );
  }

  Widget _trust(Json d) {
    final pts = (d['trust_points'] as List).cast<Json>();
    if (pts.isEmpty) return const SizedBox.shrink();
    const pairs = [(C.pink, C.saffron), (C.teal, C.pistachio), (C.saffron, C.pink), (C.pistachio, C.teal)];
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 26, 16, 0),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(24)),
      child: Column(children: [
        for (var i = 0; i < pts.length; i++)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              KnotIcon(c1: pairs[i % 4].$1, c2: pairs[i % 4].$2),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(pts[i]['title'] as String, style: const TextStyle(fontWeight: FontWeight.w800)),
                  Text(pts[i]['subtitle'] as String, style: const TextStyle(color: C.muted, fontSize: 13)),
                ]),
              ),
            ]),
          ),
      ]),
    );
  }
}
