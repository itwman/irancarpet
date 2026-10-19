import 'dart:math';

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../screens/shell.dart';
import '../widgets/common.dart';
import '../widgets/offers.dart';
import 'cards.dart';
import 'ui.dart';
import 'unroll.dart';

/// صفحهٔ اول فرشستان: سردر، تالارهای شانه، حیاط طاق‌ها، پنج‌دری با فرشی که باز می‌شود، شاه‌نشین
class HouseHome extends StatefulWidget {
  const HouseHome({super.key});
  @override
  State<HouseHome> createState() => _HouseHomeState();
}

class _HouseHomeState extends State<HouseHome> with AutomaticKeepAliveClientMixin, SingleTickerProviderStateMixin {
  Json? _d;
  String? _err;
  int _reeds = 0;
  final _scroll = ScrollController();
  final _roomKey = GlobalKey();
  late final AnimationController _room = AnimationController(vsync: this, duration: const Duration(milliseconds: 2200));
  late final Animation<double> _roomA = CurvedAnimation(parent: _room, curve: Curves.easeInOutCubic);

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
    _scroll.addListener(_checkRoom);
  }

  @override
  void dispose() {
    _scroll.dispose();
    _room.dispose();
    super.dispose();
  }

  /// فرش پنج‌دری وقتی به دید رسید باز می‌شود
  void _checkRoom() {
    if (_room.isAnimating || _room.value > 0) return;
    final box = _roomKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null || !box.attached) return;
    final y = box.localToGlobal(Offset.zero).dy;
    if (y < MediaQuery.sizeOf(context).height * .75) {
      (MediaQuery.maybeDisableAnimationsOf(context) ?? false) ? _room.value = 1 : _room.forward();
    }
  }

  Future<void> _load() async {
    try {
      final d = await Api.i.get('/home/') as Json;
      if (mounted) setState(() => (_d = d, _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  List<Json> _list(String k) => ((_d?[k] as List?) ?? []).cast<Json>();

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final d = _d;
    return Scaffold(
      body: d == null
          ? SafeArea(
              child: _err != null
                  ? StatusView(message: _err!, onRetry: () {
                      setState(() => _err = null);
                      _load();
                    })
                  : const Loading())
          : RefreshIndicator(
              color: C.pink,
              onRefresh: _load,
              child: CustomScrollView(controller: _scroll, slivers: [
                SliverToBoxAdapter(child: _header(context)),
                SliverToBoxAdapter(child: _sardar(context)),
                if ((d['notice'] as String? ?? '').isNotEmpty) SliverToBoxAdapter(child: _notice(d['notice'] as String)),
                if ((d['reeds'] as List? ?? []).isNotEmpty) SliverToBoxAdapter(child: _talar(context)),
                if (_list('categories').isNotEmpty) SliverToBoxAdapter(child: _hayat(context)),
                if (_list('newest').isNotEmpty) SliverToBoxAdapter(child: _panjdari(context, _list('newest').first)),
                if (_list('offers').isNotEmpty) SliverToBoxAdapter(child: Padding(
                  padding: const EdgeInsets.only(top: 18),
                  child: OffersStrip(_list('offers')),
                )),
                SliverToBoxAdapter(child: _title('شاه‌نشین', 'پرطرفدارترین فرش‌های این روزها، در بهترین جای خانه.', KotibehKind.gach)),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                  sliver: SliverGrid(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2, mainAxisSpacing: 18, crossAxisSpacing: 14, childAspectRatio: .45),
                    delegate: SliverChildBuilderDelegate((_, i) => NicheCard(_list('popular')[i]), childCount: _list('popular').length),
                  ),
                ),
                SliverToBoxAdapter(
                  child: Center(
                    child: TextButton(
                      onPressed: () => Navigator.pushNamed(context, '/products', arguments: {'title': 'همهٔ فرش‌ها', 'query': <String, dynamic>{}}),
                      child: const Text('دیدن همهٔ فرش‌ها'),
                    ),
                  ),
                ),
                SliverToBoxAdapter(child: _hashti(d)),
              ]),
            ),
    );
  }

  Widget _header(BuildContext context) => Container(
        color: C.bg,
        child: SafeArea(
          bottom: false,
          child: Column(children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 4, 6, 0),
              child: Row(children: [
                Image.asset('assets/house/farshestan_tile.png', width: 38, height: 38, errorBuilder: (_, _, _) => const SizedBox(width: 38)),
                const SizedBox(width: 8),
                Text(kAppName, style: nast(30, height: 1.7)),
                const Spacer(),
                IconButton(tooltip: 'جستجو', onPressed: () => Navigator.pushNamed(context, '/search'), icon: const Icon(Icons.search_rounded)),
                IconButton(
                    tooltip: 'اعلان‌ها', onPressed: () => Navigator.pushNamed(context, '/notifications'), icon: const Icon(Icons.notifications_none_rounded)),
              ]),
            ),
            const GirihBand(height: 6),
          ]),
        ),
      );

  /// سردر: دیوار آجری، طاق کاشی‌کاری‌شده با فرش پربازدید و کتیبهٔ نستعلیق
  Widget _sardar(BuildContext context) {
    final pop = _list('popular');
    final hero = pop.isNotEmpty ? pop.first : null;
    final rating = asMap(_d?['rating']);
    return CustomPaint(
      painter: _BrickWall(),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 22),
        child: Column(children: [
          const Kotibeh('از کارخانه، تا خانه', size: 30),
          const SizedBox(height: 16),
          if (hero != null)
            SizedBox(
              width: min(MediaQuery.sizeOf(context).width * .62, 300),
              child: GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/product', arguments: asInt(hero['id'])),
                child: Niche(
                  ar: RugCrop.of(hero['crop']).ar,
                  inset: .12,
                  child: RugImage(hero['image'] as String? ?? '', crop: RugCrop.of(hero['crop']), seed: asInt(hero['id'])),
                ),
              ),
            ),
          const SizedBox(height: 14),
          Material(
            color: C.soft,
            borderRadius: BorderRadius.circular(4),
            child: InkWell(
              borderRadius: BorderRadius.circular(4),
              onTap: () => Navigator.pushNamed(context, '/search'),
              child: const Padding(
                padding: EdgeInsets.symmetric(horizontal: 14, vertical: 14),
                child: Row(children: [
                  Icon(Icons.search_rounded, color: C.ink2),
                  SizedBox(width: 10),
                  Expanded(child: Text('نام نقشه، رنگ یا کد فرش', style: TextStyle(color: C.muted))),
                ]),
              ),
            ),
          ),
          if (asInt(rating['count']) > 0) ...[
            const SizedBox(height: 10),
            Text('★ ${faDigits(rating['avg'])} از ۵ در ${sep(asInt(rating['count']))} نظر خریدار',
                style: const TextStyle(color: C.cream, fontWeight: FontWeight.w700, shadows: [Shadow(blurRadius: 6, color: Colors.black54)])),
          ],
        ]),
      ),
    );
  }

  Widget _notice(String t) => Container(
        margin: const EdgeInsets.fromLTRB(16, 14, 16, 0),
        padding: const EdgeInsets.all(12),
        decoration: const BoxDecoration(color: C.saffronTint, border: BorderDirectional(start: BorderSide(color: C.saffron, width: 3))),
        child: Text(t, style: const TextStyle(fontWeight: FontWeight.w700, color: C.ink)),
      );

  Widget _title(String t, String sub, KotibehKind k) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 30, 16, 12),
        child: Column(children: [
          Kotibeh(t, size: 28, kind: k),
          const SizedBox(height: 10),
          Text(sub, textAlign: TextAlign.center, style: const TextStyle(color: C.ink2, fontSize: 13.5)),
        ]),
      );

  /// تالارهای شانه: ۷۰۰ تا ۱۵۰۰ با طاقچه‌ها
  Widget _talar(BuildContext context) {
    final groups = (_d!['reeds'] as List).cast<Json>();
    final g = groups[_reeds.clamp(0, groups.length - 1)];
    final items = (g['products'] as List).cast<Json>();
    return Column(children: [
      _title('تالارهای شانه', 'هرچه شانه بیشتر، گره‌ها ریزتر و نقش‌ها ظریف‌تر.', KotibehKind.lapis),
      SizedBox(
        height: 46,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: groups.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (_, i) => ChoiceChip(
            showCheckmark: false,
            selected: i == _reeds,
            selectedColor: C.lapis,
            backgroundColor: C.soft,
            side: const BorderSide(color: C.rim),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
            labelStyle: TextStyle(fontWeight: FontWeight.w800, color: i == _reeds ? C.cream : C.ink),
            label: Text('${faDigits(groups[i]['name'])} شانه'),
            onSelected: (_) => setState(() => _reeds = i),
          ),
        ),
      ),
      const SizedBox(height: 12),
      SizedBox(
        height: 372,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: items.length + 1,
          separatorBuilder: (_, _) => const SizedBox(width: 14),
          itemBuilder: (_, i) => i < items.length
              ? NicheCard(items[i], width: 158)
              : Center(
                  child: OutlinedButton(
                    onPressed: () => Navigator.pushNamed(context, '/products',
                        arguments: {'title': 'فرش ${faDigits(g['name'])} شانه', 'query': {'reeds': g['term_id']}}),
                    child: Text('همهٔ ${faDigits(g['name'])} شانه'),
                  ),
                ),
        ),
      ),
    ]);
  }

  /// حیاط: هر طاق یک دسته، با انعکاس در حوض
  Widget _hayat(BuildContext context) {
    final cats = _list('categories');
    return Column(children: [
      _title('هر طاق، یک دسته', 'دسته‌ها را از زیر طاق‌های حیاط انتخاب کنید.', KotibehKind.lapis),
      Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFB0643E), Color(0xFF9A5333)]),
        ),
        child: Column(children: [
          const GirihBand(height: 9),
          SizedBox(
            height: 240,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
              itemCount: cats.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (_, i) {
                final c = cats[i];
                return GestureDetector(
                  onTap: () => Navigator.pushNamed(context, '/products', arguments: {'title': c['name'], 'query': {'category': c['id']}}),
                  child: SizedBox(
                    width: 112,
                    child: Column(children: [
                      SizedBox(
                        height: 160,
                        child: Niche(ar: RugCrop.of(c['crop']).ar, child: RugImage(c['image'] as String? ?? '', crop: RugCrop.of(c['crop']), seed: asInt(c['id']))),
                      ),
                      Container(
                        width: 112,
                        padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 4),
                        color: C.soft,
                        child: Text(faDigits(c['name']), textAlign: TextAlign.center, maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5)),
                      ),
                    ]),
                  ),
                );
              },
            ),
          ),
          // حوض
          Container(
            height: 40,
            decoration: const BoxDecoration(
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1F6F70), Color(0xFF0E4A4C)]),
              border: Border(top: BorderSide(color: Color(0xFFE2D3B4), width: 6)),
            ),
            alignment: Alignment.center,
            child: const Text('دسته را بزنید و وارد تالارش شوید', style: TextStyle(color: Color(0xCCF3E9D3), fontSize: 12)),
          ),
        ]),
      ),
      Padding(
        padding: const EdgeInsets.only(top: 6),
        child: TextButton(onPressed: () => Shell.goTab(context, 1), child: const Text('همهٔ دسته‌ها')),
      ),
    ]);
  }

  /// پنج‌دری: ارسی رنگی روی دیوار؛ فرش تازه روی آجرفرش باز می‌شود
  Widget _panjdari(BuildContext context, Json p) {
    final crop = RugCrop.of(p['crop']);
    final w = MediaQuery.sizeOf(context).width;
    return Container(
      key: _roomKey,
      margin: const EdgeInsets.only(top: 26),
      child: Column(children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.fromLTRB(0, 18, 0, 18),
          color: const Color(0xFFC9AC84),
          child: Column(children: [
            const Kotibeh('فرش را باید روی زمین دید', size: 24, kind: KotibehKind.wood),
            const SizedBox(height: 14),
            SizedBox(width: min(w * .82, 420), height: 120, child: CustomPaint(painter: _Orosi())),
          ]),
        ),
        BrickFloor(
          padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
          child: Column(children: [
            // فرش افقی روی زمین؛ از راست به چپ باز می‌شود
            SizedBox(
              width: min(w - 40, 520),
              child: RotatedBox(
                quarterTurns: 1,
                child: UnrollRug(
                  progress: _roomA,
                  ar: crop.ar,
                  child: RugImage(p['image'] as String? ?? '', crop: crop, seed: asInt(p['id'])),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: C.soft.withValues(alpha: .95), border: Border.all(color: C.rim)),
              child: Row(children: [
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(faDigits(rugName(p['title'] as String? ?? '')), style: nast(28, height: 1.7)),
                    Text('تازه به پنج‌دری آمده؛ ${p['reeds'] != null && (p['reeds'] as String).isNotEmpty ? '${faDigits(p['reeds'])} شانه، ' : ''}'
                        'از ${sep(asInt(p['price']))} تومان', style: const TextStyle(color: C.ink2, fontSize: 13)),
                  ]),
                ),
                FilledButton(
                  style: FilledButton.styleFrom(minimumSize: const Size(10, 46)),
                  onPressed: () => Navigator.pushNamed(context, '/product', arguments: asInt(p['id'])),
                  child: const Text('دیدن فرش'),
                ),
              ]),
            ),
          ]),
        ),
      ]),
    );
  }

  /// هشتی: پاخور با «خانه‌تان آباد»
  Widget _hashti(Json d) {
    final pts = ((d['trust_points'] as List?) ?? []).cast<Json>();
    return Container(
      margin: const EdgeInsets.only(top: 20),
      color: C.lapisDark,
      child: Column(children: [
        const GirihBand(height: 8),
        const SizedBox(height: 18),
        Text('خانه‌تان آباد', style: nast(40, color: const Color(0xFFF2D9A4))),
        for (final t in pts.take(4))
          Padding(
            padding: const EdgeInsets.fromLTRB(24, 4, 24, 4),
            child: Text('${t['title']}${(t['subtitle'] as String? ?? '').isNotEmpty ? ' — ${t['subtitle']}' : ''}',
                textAlign: TextAlign.center, style: const TextStyle(color: Color(0xCCF3E9D3), fontSize: 13)),
          ),
        const SizedBox(height: 24),
      ]),
    );
  }
}

class _BrickWall extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0xFFB0643E));
    const bw = 44.0, bh = 16.0;
    final mortar = Paint()..color = const Color(0xFFD9BC94);
    final rnd = Random(5);
    for (var y = 0.0, row = 0; y < s.height; y += bh, row++) {
      c.drawRect(Rect.fromLTWH(0, y, s.width, 2), mortar);
      for (var x = row.isOdd ? -bw / 2 : 0.0; x < s.width; x += bw) {
        c.drawRect(Rect.fromLTWH(x + 1, y + 2, bw - 2, bh - 2),
            Paint()..color = Color.lerp(const Color(0xFFA35E3A), const Color(0xFFC07A50), rnd.nextDouble())!);
      }
    }
    c.drawRect(
        Offset.zero & s,
        Paint()
          ..shader = const RadialGradient(center: Alignment(0, -.2), radius: .9, colors: [Color(0x00000000), Color(0x55301508)])
              .createShader(Offset.zero & s));
  }

  @override
  bool shouldRepaint(_BrickWall o) => false;
}

/// ارسی: پنجرهٔ مشبک با شیشه‌های رنگی
class _Orosi extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    const glass = [Color(0xFFC6392B), Color(0xFF2E5E9A), Color(0xFFE2B13C), Color(0xFF2F8A57)];
    final frame = Paint()..color = const Color(0xFF3B2414);
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0xFFE6D3B0));
    final n = 5, pw = (s.width - 12) / n;
    for (var k = 0; k < n; k++) {
      final x = 6 + k * pw, r = Rect.fromLTWH(x + 3, 6, pw - 6, s.height - 12);
      c.drawRect(r, frame);
      final inner = r.deflate(3);
      // نیم‌دایرهٔ بادبزنی بالا
      final top = Rect.fromLTWH(inner.left, inner.top, inner.width, inner.width * .55);
      for (var j = 0; j < 6; j++) {
        c.drawArc(Rect.fromCenter(center: top.bottomCenter, width: inner.width, height: inner.width), pi + j * pi / 6, pi / 6, true,
            Paint()..color = glass[(j + k) % 4]);
      }
      // شبکهٔ لوزی
      final gy = top.bottom + 3, cell = inner.width / 4;
      for (var y = gy; y + cell <= inner.bottom; y += cell) {
        for (var x2 = inner.left; x2 + cell <= inner.right + .5; x2 += cell) {
          final cr = Rect.fromLTWH(x2 + 1, y + 1, cell - 2, cell - 2);
          c.drawRect(cr, Paint()..color = const Color(0xFFF3E3B8));
          c.drawPath(
              Path()
                ..moveTo(cr.center.dx, cr.top + 2)
                ..lineTo(cr.right - 2, cr.center.dy)
                ..lineTo(cr.center.dx, cr.bottom - 2)
                ..lineTo(cr.left + 2, cr.center.dy)
                ..close(),
              Paint()..color = glass[((x2 + y) ~/ cell + k) % 4]);
        }
      }
    }
  }

  @override
  bool shouldRepaint(_Orosi o) => false;
}
