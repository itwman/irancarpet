import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../screens/shell.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'cards.dart';
import 'sizes.dart';
import 'ui.dart';

/// صفحهٔ اول فرشستان («فروشگاه تخصصی فرش»): جستجوی بزرگ، بنرها، میان‌بر دسته‌ها، پیشنهاد ویژه، پرطرفدارها،
/// سایزیاب، تازه‌ها، خرید بر اساس سایز و رنگ، خرید اقساطی و راهنمای خرید.
/// همهٔ عددها از API می‌آیند؛ هر بخشی که داده‌اش نیست، نشان داده نمی‌شود.
class HouseHome extends StatefulWidget {
  const HouseHome({super.key});
  @override
  State<HouseHome> createState() => _HouseHomeState();
}

class _HouseHomeState extends State<HouseHome> with AutomaticKeepAliveClientMixin {
  Json? _d;
  String? _err;
  List<RugSize> _sizes = RugSize.defaults();
  bool _sizesLive = false;
  List<Json> _colors = [];
  final Map<int, int> _catCount = {};
  final _offersKey = GlobalKey();

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    _extras();
    try {
      final d = await Api.i.get('/home/') as Json;
      if (mounted) setState(() => (_d = d, _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  /// داده‌های کمکی (هر کدام نبود، بخشش پنهان می‌ماند): سایزها و کمترین قیمت از لیست قیمت، رنگ‌های زمینه، تعداد هر دسته
  void _extras() {
    Api.i.get('/pricelist/').then((r) {
      final s = RugSize.fromPriceList(r as Json);
      if (mounted && s.isNotEmpty) setState(() => (_sizes = s, _sizesLive = true));
    }).catchError((_) {});
    Api.i.get('/products/filters/').then((r) {
      final f = r as Json;
      var raw = asList(f['colors']);
      if (raw.isEmpty) {
        // نام ویژگی رنگ زمینه در هر سایت کمی فرق دارد
        final g = asList(f['groups']).where((g) => (g['label'] as String? ?? '').contains('رنگ')).toList();
        if (g.isNotEmpty) raw = asList(g.first['terms']);
      }
      final cs = raw..sort((a, b) => asInt(b['count']).compareTo(asInt(a['count'])));
      if (mounted) setState(() => _colors = cs.where((c) => asInt(c['count']) > 0).toList());
    }).catchError((_) {});
    Api.i.get('/categories/').then((r) {
      void walk(List l) {
        for (final c in l.whereType<Map>()) {
          _catCount[asInt(c['id'])] = asInt(c['count']);
          walk((c['children'] as List?) ?? const []);
        }
      }

      walk(r as List);
      if (mounted) setState(() {});
    }).catchError((_) {});
  }

  List<Json> _list(String k) => asList(_d?[k]);

  void _products(String title, Map<String, dynamic> q) => Navigator.pushNamed(context, '/products', arguments: {'title': title, 'query': q});

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final d = _d;
    return Scaffold(
      backgroundColor: Colors.white,
      body: RefreshIndicator(
        color: C.brand,
        onRefresh: _load,
        child: CustomScrollView(slivers: [
          _appBar(context),
          if (d == null)
            SliverFillRemaining(
              hasScrollBody: false,
              child: _err != null
                  ? StatusView(message: _err!, onRetry: () {
                      setState(() => _err = null);
                      _load();
                    })
                  : const Loading(),
            )
          else ...[
            if ((d['notice'] as String? ?? '').isNotEmpty) SliverToBoxAdapter(child: _notice(d['notice'] as String)),
            SliverToBoxAdapter(child: _Hero(slides: _slides(d))),
            if (_list('trust_points').isNotEmpty) SliverToBoxAdapter(child: _trust(_list('trust_points'))),
            if (_list('categories').isNotEmpty) ...[
              SliverToBoxAdapter(
                  child: SecHead('دسته‌بندی‌های فرشستان', action: 'همه', onAction: () => Shell.goTab(context, 1))),
              SliverToBoxAdapter(child: _cats(_list('categories'))),
            ],
            if (_list('offers').isNotEmpty) SliverToBoxAdapter(key: _offersKey, child: _offers(_list('offers'))),
            if (_list('popular').isNotEmpty) ...[
              SliverToBoxAdapter(
                child: SecHead('پرطرفدارترین‌ها',
                    subtitle: 'پربازدیدترین فرش‌های فرشستان در این روزها',
                    action: 'مشاهدهٔ همه',
                    onAction: () => _products('پرطرفدارترین فرش‌ها', {'sort': 'popular'})),
              ),
              SliverToBoxAdapter(
                child: CardRail(count: _list('popular').length, builder: (_, i, w) => ShopCard(_list('popular')[i], width: w)),
              ),
            ],
            const SliverToBoxAdapter(child: SizedBox(height: 28)),
            SliverToBoxAdapter(child: SizeFinder(sizes: _sizes)),
            if (asList(d['reeds']).isNotEmpty) ...[
              const SliverToBoxAdapter(child: SecHead('خرید بر اساس شانه', subtitle: 'هرچه شانه بیشتر، گره‌ها ریزتر و نقش‌ها ظریف‌تر.')),
              SliverToBoxAdapter(child: _reeds(asList(d['reeds']))),
            ],
            if (_list('newest').isNotEmpty) ...[
              SliverToBoxAdapter(
                child: SecHead('تازه‌های کارخانه',
                    subtitle: 'تازه‌ترین طرح‌هایی که به فرشستان اضافه شده‌اند.',
                    action: 'مشاهدهٔ همه',
                    onAction: () => _products('تازه‌ترین فرش‌ها', {'sort': 'new'})),
              ),
              SliverToBoxAdapter(
                child: CardRail(
                    count: _list('newest').length, builder: (_, i, w) => ShopCard(_list('newest')[i], width: w, badge: 'جدید')),
              ),
            ],
            if (_sizesLive) ...[
              const SliverToBoxAdapter(child: SecHead('خرید بر اساس سایز', subtitle: 'شکل‌ها به نسبت واقعی ابعاد کشیده شده‌اند.')),
              SliverToBoxAdapter(child: _bySize()),
            ],
            if (_colors.isNotEmpty) ...[
              const SliverToBoxAdapter(child: SecHead('خرید بر اساس رنگ زمینه')),
              SliverToBoxAdapter(child: _byColor()),
            ],
            if (context.watch<AppConfig>().installmentPlans.isNotEmpty) SliverToBoxAdapter(child: _installment()),
            const SliverToBoxAdapter(child: SecHead('راهنمای خرید فرش', subtitle: 'پیش از خرید، این سه نکته را بدانید.')),
            SliverToBoxAdapter(child: _guide()),
            SliverToBoxAdapter(child: _footer(d)),
          ],
        ]),
      ),
    );
  }

  // ------------------------------------------------------------------ سربرگ با جستجوی بزرگ
  Widget _appBar(BuildContext context) => SliverAppBar(
        pinned: true,
        backgroundColor: Colors.white,
        surfaceTintColor: Colors.white,
        scrolledUnderElevation: 0,
        toolbarHeight: 60,
        titleSpacing: 16,
        title: const FarshestanLogo(mark: 34),
        actions: [
          IconButton(
              tooltip: 'اعلان‌ها',
              onPressed: () => Navigator.pushNamed(context, '/notifications'),
              icon: const Icon(Icons.notifications_none_rounded, color: C.ink2)),
          const SizedBox(width: 8),
        ],
        bottom: const PreferredSize(preferredSize: Size.fromHeight(64), child: HouseSearchBar()),
      );

  Widget _notice(String t) => Container(
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(color: C.gold50, border: Border.all(color: C.gold100), borderRadius: BorderRadius.circular(12)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Padding(padding: EdgeInsets.only(top: 3), child: Icon(Icons.info_outline_rounded, size: 18, color: C.goldInk)),
          const SizedBox(width: 8),
          Expanded(child: Text(t, style: const TextStyle(fontWeight: FontWeight.w600, color: C.ink2, fontSize: 13, height: 1.8))),
        ]),
      );

  // ------------------------------------------------------------------ بنرها (از دادهٔ واقعی)
  List<_Slide> _slides(Json d) {
    final offers = _list('offers'), pop = _list('popular'), news = _list('newest');
    final out = <_Slide>[];
    if (offers.isNotEmpty) {
      final best = offers.map((o) => asInt(o['percent'])).fold(0, max);
      final o = offers.first;
      out.add(_Slide(
        style: _SlideStyle.blue,
        eyebrow: 'تخفیف‌های کارخانه',
        title: best > 0 ? 'تا ${faDigits(best)}٪ ارزان‌تر؛ فرصت‌های ویژهٔ خرید' : 'فرصت‌های ویژهٔ خرید',
        text: '${faDigits(offers.length)} پیشنهاد فعال، مستقیم از انبار کارخانه.',
        cta: 'مشاهدهٔ پیشنهادها',
        image: o['image'] as String? ?? '',
        seed: asInt(o['product_id']),
        disc: best > 0 ? best : null,
        onTap: () {
          final c = _offersKey.currentContext;
          if (c != null) Scrollable.ensureVisible(c, duration: const Duration(milliseconds: 450), curve: Curves.easeInOutCubic);
        },
      ));
    }
    final hero = pop.isNotEmpty ? pop.first : (news.isNotEmpty ? news.first : null);
    out.add(_Slide(
      style: out.isEmpty ? _SlideStyle.blue : _SlideStyle.light,
      eyebrow: 'خرید مستقیم از کارخانه',
      title: 'فرش ماشینی، بی‌واسطه از کارخانه به خانهٔ شما',
      text: 'طرح، رنگ و سایز را مقایسه کنید و با خیال راحت بخرید.',
      cta: 'دیدن همهٔ فرش‌ها',
      image: hero?['image'] as String? ?? '',
      crop: RugCrop.of(hero?['crop']),
      seed: asInt(hero?['id']),
      onTap: () => _products('همهٔ فرش‌ها', {}),
    ));
    final lensP = pop.length > 1 ? pop[1] : hero;
    if (lensP != null) {
      out.add(_Slide(
        style: _SlideStyle.gold,
        eyebrow: 'نمای نزدیک بافت',
        title: 'گره‌ها را پیش از خرید از نزدیک ببینید',
        text: 'در صفحهٔ هر فرش، بافت ۷۰۰ تا ۱۵۰۰ شانه را کنار هم مقایسه کنید.',
        cta: 'امتحان کنید',
        image: lensP['image'] as String? ?? '',
        crop: RugCrop.of(lensP['crop']),
        seed: asInt(lensP['id']),
        lens: true,
        onTap: () => Navigator.pushNamed(context, '/product', arguments: asInt(lensP['id'])),
      ));
    }
    return out;
  }

  Widget _trust(List<Json> pts) {
    const icons = [Icons.local_shipping_outlined, Icons.verified_outlined, Icons.undo_rounded, Icons.credit_card_rounded, Icons.support_agent_rounded];
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: SizedBox(
        height: 64,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: pts.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (_, i) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            decoration: BoxDecoration(color: C.surface2, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(14)),
            child: Row(children: [
              Container(
                width: 36,
                height: 36,
                decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: C.brand100)),
                child: Icon(icons[i % icons.length], size: 19, color: C.brand),
              ),
              const SizedBox(width: 10),
              Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(pts[i]['title'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13, height: 1.4)),
                if ((pts[i]['subtitle'] as String? ?? '').isNotEmpty)
                  Text(pts[i]['subtitle'] as String, style: const TextStyle(color: C.muted, fontSize: 11.5, height: 1.4)),
              ]),
            ]),
          ),
        ),
      ),
    );
  }

  // ------------------------------------------------------------------ دسته‌ها (دایره‌ای)
  Widget _cats(List<Json> cats) => SizedBox(
        height: 150,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          itemCount: cats.length,
          separatorBuilder: (_, _) => const SizedBox(width: 4),
          itemBuilder: (_, i) {
            final c = cats[i], n = _catCount[asInt(c['id'])];
            return CatCircle(c, count: n, onTap: () => _products(faDigits(c['name']), {'category': c['id']}));
          },
        ),
      );

  // ------------------------------------------------------------------ پیشنهاد ویژه
  Widget _offers(List<Json> offers) {
    final ends = offers.map((o) => DateTime.tryParse(o['ends_at'] as String? ?? '')).whereType<DateTime>().where((t) => t.isAfter(DateTime.now()));
    final soon = ends.isEmpty ? null : ends.reduce((a, b) => a.isBefore(b) ? a : b);
    return Container(
      margin: const EdgeInsets.only(top: 28),
      padding: const EdgeInsets.fromLTRB(0, 20, 0, 18),
      decoration: const BoxDecoration(
        gradient: RadialGradient(center: Alignment(1, -1), radius: 1.4, colors: [Color(0xFF22489C), C.brand800]),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 0, 16, 14),
          child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                if (soon != null) const Text('تا پایان این فرصت', style: TextStyle(color: C.gold300, fontWeight: FontWeight.w700, fontSize: 13)),
                const Text('پیشنهاد ویژهٔ امروز', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 20, height: 1.5)),
                const Text('قیمت مستقیم کارخانه؛ موجودی محدود.', style: TextStyle(color: Color(0xFFC9D4EE), fontSize: 12.5)),
              ]),
            ),
            if (soon != null) Countdown(soon),
          ]),
        ),
        CardRail(count: offers.length, body: kOfferBody, builder: (_, i, w) => OfferCard(offers[i], width: w)),
      ]),
    );
  }

  // ------------------------------------------------------------------ شانه‌ها
  Widget _reeds(List<Json> groups) {
    const density = {'700': '۲۵۵۰', '1000': '۳۰۰۰', '1200': '۳۶۰۰', '1500': '۴۵۰۰'};
    return SizedBox(
      height: 76,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: groups.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final g = groups[i], name = '${g['name']}', dn = density[latin(name)];
          return Material(
            color: Colors.white,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14), side: const BorderSide(color: C.line)),
            child: InkWell(
              borderRadius: BorderRadius.circular(14),
              onTap: () => _products('فرش ${faDigits(name)} شانه', {'reeds': g['term_id']}),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(children: [
                  Container(
                    width: 40,
                    height: 40,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: C.brand50, borderRadius: BorderRadius.circular(10)),
                    child: const Icon(Icons.grid_on_rounded, color: C.brand, size: 20),
                  ),
                  const SizedBox(width: 10),
                  Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('${faDigits(name)} شانه', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14.5)),
                    if (dn != null) Text('تراکم $dn', style: const TextStyle(color: C.muted, fontSize: 12)),
                  ]),
                ]),
              ),
            ),
          );
        },
      ),
    );
  }

  // ------------------------------------------------------------------ سایز
  Widget _bySize() {
    // ترتیب آشنا: فرش‌ها از کوچک به بزرگ، بعد قالیچه، کناره و پادری
    int rank(RugSize s) => switch (s.kind) { SizeKind.rug => 0, SizeKind.small => 1, SizeKind.runner => 2, SizeKind.mat => 3, SizeKind.other => 4 };
    final list = _sizes.where((s) => !s.name.contains('مربع') && s.kind != SizeKind.other).toList()
      ..sort((a, b) => rank(a) != rank(b) ? rank(a) - rank(b) : (rank(a) == 0 ? a.area.compareTo(b.area) : b.area.compareTo(a.area)));
    final maxL = list.map((s) => s.l).fold(0.0, max);
    return SizedBox(
      height: 174,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        itemCount: list.length,
        separatorBuilder: (_, _) => const SizedBox(width: 10),
        itemBuilder: (_, i) {
          final s = list[i];
          return SizedBox(
            width: 116,
            child: Material(
              color: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: C.line)),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: () => s.open(context),
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(8, 12, 8, 10),
                  child: Column(children: [
                    Container(
                      height: 72,
                      width: double.infinity,
                      decoration: BoxDecoration(color: C.surface2, borderRadius: BorderRadius.circular(10)),
                      child: Center(child: SizeShape(s, box: 64, maxL: min(maxL, 6))),
                    ),
                    const SizedBox(height: 8),
                    Text(faDigits(s.name), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5)),
                    Text('${s.dims} متر', style: const TextStyle(color: C.muted, fontSize: 11.5)),
                    if (s.minPrice > 0)
                      Text('از ${sep(s.minPrice)} تومان',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: C.brand, fontSize: 11.5, fontWeight: FontWeight.w700)),
                  ]),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  // ------------------------------------------------------------------ رنگ زمینه
  Widget _byColor() => SizedBox(
        height: 122,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          itemCount: _colors.length,
          separatorBuilder: (_, _) => const SizedBox(width: 2),
          itemBuilder: (_, i) {
            final c = _colors[i], name = faDigits(c['name'] ?? '');
            return InkWell(
              borderRadius: BorderRadius.circular(12),
              onTap: () => _products('فرش زمینه $name', {'color': c['id']}),
              child: SizedBox(
                width: 84,
                child: Column(children: [
                  const SizedBox(height: 4),
                  ColorRing(swatchOf(name) ?? const Color(0xFFB9BEC6)),
                  const SizedBox(height: 6),
                  Text(name, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
                  Text('${faDigits(asInt(c['count']))} طرح', style: const TextStyle(color: C.muted, fontSize: 11.5)),
                ]),
              ),
            );
          },
        ),
      );

  // ------------------------------------------------------------------ اقساط
  Widget _installment() => Container(
        margin: const EdgeInsets.fromLTRB(16, 28, 16, 0),
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(color: C.gold50, border: Border.all(color: C.gold100), borderRadius: BorderRadius.circular(20)),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
                decoration: BoxDecoration(color: C.gold100, borderRadius: BorderRadius.circular(20)),
                child: const Text('خرید اقساطی فرش', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: C.goldInk)),
              ),
              const SizedBox(height: 8),
              const Text('فرش را امروز ببرید، در چند قسط پرداخت کنید',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, height: 1.6)),
              const SizedBox(height: 4),
              const Text('شرایط و مراحل را ببینید و قسط هر فرش را حساب کنید.', style: TextStyle(fontSize: 12.5, color: C.ink2, height: 1.7)),
              const SizedBox(height: 12),
              FilledButton(
                style: FilledButton.styleFrom(minimumSize: const Size(10, 44), padding: const EdgeInsets.symmetric(horizontal: 18)),
                onPressed: () => Navigator.pushNamed(context, '/installment'),
                child: const Text('شرایط خرید اقساطی', style: TextStyle(fontSize: 14)),
              ),
            ]),
          ),
          const SizedBox(width: 12),
          Column(children: [
            for (final (i, t) in const ['انتخاب فرش', 'پیش‌پرداخت', 'اقساط ماهانه'].indexed)
              Container(
                margin: const EdgeInsets.only(bottom: 6),
                padding: const EdgeInsets.fromLTRB(10, 6, 10, 6),
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(10), boxShadow: kShadow1),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  CircleAvatar(
                      radius: 11,
                      backgroundColor: C.brand50,
                      child: Text(faDigits(i + 1), style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: C.brand))),
                  const SizedBox(width: 6),
                  Text(t, style: const TextStyle(fontSize: 11.5)),
                ]),
              ),
          ]),
        ]),
      );

  // ------------------------------------------------------------------ راهنمای خرید
  Widget _guide() => SizedBox(
        height: 172,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: kGuides.length,
          separatorBuilder: (_, _) => const SizedBox(width: 12),
          itemBuilder: (_, i) => GuideCard(kGuides[i], sizes: _sizes),
        ),
      );

  Widget _footer(Json d) {
    final rating = asMap(d['rating']);
    return Container(
      margin: const EdgeInsets.only(top: 32),
      padding: const EdgeInsets.fromLTRB(16, 22, 16, 24),
      color: C.surface2,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Align(alignment: AlignmentDirectional.centerStart, child: FarshestanLogo(mark: 36)),
        const SizedBox(height: 10),
        const Text('فرشستان، فروشگاه آنلاین فرش ماشینی؛ خرید مستقیم از کارخانه با ارسال به سراسر کشور.',
            style: TextStyle(color: C.muted, fontSize: 12.5, height: 1.9)),
        if (asInt(rating['count']) > 0) ...[
          const SizedBox(height: 10),
          Row(children: [
            const Text('رضایت خریداران: ', style: TextStyle(fontSize: 13, color: C.ink2)),
            RatingLine(rating['avg'], asInt(rating['count']), size: 13),
          ]),
        ],
        const SizedBox(height: 14),
        Row(children: [
          Expanded(
            child: FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size(10, 46)),
              onPressed: () => _products('همهٔ فرش‌ها', {}),
              child: const Text('همهٔ فرش‌ها', style: TextStyle(fontSize: 14.5)),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: OutlinedButton(
              style: OutlinedButton.styleFrom(minimumSize: const Size(10, 46)),
              onPressed: () => Navigator.pushNamed(context, '/pricelist'),
              child: const Text('لیست قیمت امروز', style: TextStyle(fontSize: 14)),
            ),
          ),
        ]),
      ]),
    );
  }
}

/// جستجوی بزرگ زیر سربرگ (صفحهٔ جستجو را باز می‌کند)
class HouseSearchBar extends StatelessWidget {
  const HouseSearchBar({super.key, this.hint = 'جستجو در طرح‌ها، رنگ‌ها و کد فرش'});
  final String hint;
  @override
  Widget build(BuildContext context) => Container(
        color: Colors.white,
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
        child: Material(
          color: C.soft,
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: () => Navigator.pushNamed(context, '/search'),
            child: SizedBox(
              height: 48,
              child: Row(children: [
                const SizedBox(width: 14),
                const Icon(Icons.search_rounded, color: C.muted),
                const SizedBox(width: 10),
                Expanded(child: Text(hint, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: C.faint, fontSize: 14))),
              ]),
            ),
          ),
        ),
      );
}

/// دایرهٔ دسته: تکه‌ای از وسط فرش + نام و تعداد طرح
class CatCircle extends StatelessWidget {
  const CatCircle(this.c, {super.key, this.count, required this.onTap, this.size = 76});
  final Json c;
  final int? count;
  final VoidCallback onTap;
  final double size;
  @override
  Widget build(BuildContext context) => InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: SizedBox(
          width: size + 18,
          child: Column(children: [
            const SizedBox(height: 4),
            RugDisc(url: c['image'] as String? ?? '', crop: RugCrop.of(c['crop']), seed: asInt(c['id']), size: size),
            const SizedBox(height: 6),
            Text(faDigits(c['name'] ?? ''),
                maxLines: 2,
                textAlign: TextAlign.center,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5, height: 1.45)),
            if (count != null && count! > 0) Text('${faDigits(count!)} طرح', style: const TextStyle(color: C.muted, fontSize: 11)),
          ]),
        ),
      );
}

/// دایرهٔ رنگ زمینه با حلقهٔ نازک
class ColorRing extends StatelessWidget {
  const ColorRing(this.color, {super.key, this.size = 64});
  final Color color;
  final double size;
  @override
  Widget build(BuildContext context) => Container(
        width: size,
        height: size,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: C.line, width: 1.5)),
        child: CustomPaint(painter: _SwatchPainter(color)),
      );
}

class _SwatchPainter extends CustomPainter {
  _SwatchPainter(this.c);
  final Color c;
  @override
  void paint(Canvas canvas, Size s) {
    final r = s.width / 2, o = s.center(Offset.zero);
    canvas.drawCircle(o, r, Paint()..color = c);
    final lum = c.computeLuminance();
    final mot = (lum > .5 ? Colors.black : Colors.white).withValues(alpha: .16);
    // ترنج کم‌رنگ برای حس فرش
    final p = Path()..moveTo(o.dx, o.dy - r * .55)..lineTo(o.dx + r * .4, o.dy)..lineTo(o.dx, o.dy + r * .55)..lineTo(o.dx - r * .4, o.dy)..close();
    canvas.drawPath(p, Paint()..color = mot);
    canvas.drawCircle(o, r * .8, Paint()..color = mot..style = PaintingStyle.stroke..strokeWidth = 1.2);
    canvas.drawCircle(o, r, Paint()..color = const Color(0x1A000000)..style = PaintingStyle.stroke..strokeWidth = 1);
  }

  @override
  bool shouldRepaint(_SwatchPainter o) => o.c != c;
}

// ------------------------------------------------------------------ اسلایدر بنر
enum _SlideStyle { blue, light, gold }

class _Slide {
  _Slide({required this.style, required this.eyebrow, required this.title, required this.text, required this.cta, required this.image,
      this.crop = RugCrop.full, this.seed = 7, this.disc, this.lens = false, required this.onTap});
  final _SlideStyle style;
  final String eyebrow, title, text, cta, image;
  final RugCrop crop;
  final int seed;
  final int? disc;
  final bool lens;
  final VoidCallback onTap;
}

class _Hero extends StatefulWidget {
  const _Hero({required this.slides});
  final List<_Slide> slides;
  @override
  State<_Hero> createState() => _HeroState();
}

class _HeroState extends State<_Hero> {
  final _pc = PageController();
  int _i = 0;
  Timer? _t;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _t?.cancel();
    final reduce = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    if (!reduce && widget.slides.length > 1) {
      _t = Timer.periodic(const Duration(milliseconds: 6500), (_) {
        if (!mounted || !_pc.hasClients) return;
        _pc.animateToPage((_i + 1) % widget.slides.length, duration: const Duration(milliseconds: 600), curve: Curves.easeInOutCubic);
      });
    }
  }

  @override
  void dispose() {
    _t?.cancel();
    _pc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final n = widget.slides.length;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(20),
        child: SizedBox(
          height: 208,
          child: Stack(children: [
            PageView.builder(
              controller: _pc,
              itemCount: n,
              onPageChanged: (i) => setState(() => _i = i),
              itemBuilder: (_, i) => _slide(widget.slides[i]),
            ),
            if (n > 1)
              PositionedDirectional(
                bottom: 12,
                start: 18,
                child: Row(children: [
                  for (var k = 0; k < n; k++)
                    AnimatedContainer(
                      duration: const Duration(milliseconds: 250),
                      margin: const EdgeInsetsDirectional.only(end: 6),
                      width: k == _i ? 22 : 8,
                      height: 8,
                      decoration: BoxDecoration(color: k == _i ? C.gold : const Color(0x8C7882A0), borderRadius: BorderRadius.circular(4)),
                    ),
                ]),
              ),
          ]),
        ),
      ),
    );
  }

  Widget _slide(_Slide s) {
    final (bg, fg, sub, eyeBg, eyeFg) = switch (s.style) {
      _SlideStyle.blue => (
          const BoxDecoration(gradient: RadialGradient(center: Alignment(.8, -.4), radius: 1.3, colors: [Color(0xFF2A56B5), C.brand, C.brand800], stops: [0, .4, 1])),
          Colors.white,
          const Color(0xEBFFFFFF),
          const Color(0x1FFFFFFF),
          C.gold300
        ),
      _SlideStyle.light => (
          const BoxDecoration(gradient: LinearGradient(colors: [Color(0xFFF3F6FB), Color(0xFFE6ECF7)])),
          C.ink,
          C.ink2,
          C.brand100,
          C.brand700
        ),
      _SlideStyle.gold => (
          const BoxDecoration(gradient: LinearGradient(colors: [C.gold50, Color(0xFFF3E3BC)])),
          C.ink,
          C.ink2,
          Colors.white,
          C.goldInk
        ),
    };
    return GestureDetector(
      onTap: s.onTap,
      child: DecoratedBox(
        decoration: bg,
        child: Row(children: [
          Expanded(
            child: Padding(
              padding: const EdgeInsetsDirectional.fromSTEB(18, 16, 4, 30),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.center, children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 1),
                  decoration: BoxDecoration(color: eyeBg, borderRadius: BorderRadius.circular(20)),
                  child: Text(s.eyebrow, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: eyeFg)),
                ),
                const SizedBox(height: 8),
                Text(s.title, maxLines: 3, style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: fg, height: 1.55)),
                const SizedBox(height: 4),
                Text(s.text, maxLines: 2, overflow: TextOverflow.ellipsis, style: TextStyle(fontSize: 12, color: sub, height: 1.7)),
                const SizedBox(height: 10),
                Container(
                  height: 36,
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  decoration: BoxDecoration(
                      color: s.style == _SlideStyle.blue ? C.gold : C.brand, borderRadius: BorderRadius.circular(8)),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    Text(s.cta,
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800, color: s.style == _SlideStyle.blue ? C.goldInk : Colors.white)),
                    Icon(Icons.chevron_left_rounded, size: 18, color: s.style == _SlideStyle.blue ? C.goldInk : Colors.white),
                  ]),
                ),
              ]),
            ),
          ),
          SizedBox(
            width: 124,
            child: Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
              Transform.rotate(
                angle: s.lens ? 0 : -.08,
                child: Container(
                  width: 92,
                  height: 92 / s.crop.ar,
                  decoration: const BoxDecoration(boxShadow: [BoxShadow(color: Color(0x590B1C42), blurRadius: 18, offset: Offset(0, 12))]),
                  child: RugImage(s.image, crop: s.crop, seed: s.seed),
                ),
              ),
              if (s.disc != null)
                Positioned(
                  top: 12,
                  left: 4,
                  child: Container(
                    width: 58,
                    height: 58,
                    alignment: Alignment.center,
                    decoration: const BoxDecoration(
                        color: C.gold, shape: BoxShape.circle, boxShadow: [BoxShadow(color: Color(0x40000000), blurRadius: 12, offset: Offset(0, 6))]),
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      const Text('تا', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w700, color: C.goldInk, height: 1.1)),
                      Text('${faDigits(s.disc!)}٪', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: C.goldInk, height: 1.2)),
                    ]),
                  ),
                ),
              if (s.lens)
                Positioned(
                  bottom: 26,
                  left: 2,
                  child: Container(
                    decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(color: Colors.white, width: 4),
                        boxShadow: const [BoxShadow(color: Color(0x40141D33), blurRadius: 14, offset: Offset(0, 8))]),
                    child: RugDisc(url: s.image, crop: s.crop, seed: s.seed, size: 58, zoom: 3.2),
                  ),
                ),
            ]),
          ),
        ]),
      ),
    );
  }
}

// ------------------------------------------------------------------ راهنمای خرید (متن آموزشی ثابت)
class Guide {
  const Guide(this.tag, this.title, this.text, this.icon, this.body);
  final String tag, title, text;
  final IconData icon;
  final List<String> body;
}

const kGuides = [
  Guide('شانه چیست؟', 'فرق ۷۰۰ تا ۱۵۰۰ شانه', 'شانه یعنی تعداد گره در عرض یک متر فرش.', Icons.grid_on_rounded, [
    'شانه تعداد گره‌ها در عرض یک متر فرش ماشینی است. هرچه شانه بیشتر باشد، گره‌ها ریزتر و نقش‌ها ظریف‌تر و تیزتر بافته می‌شوند.',
    '۷۰۰ شانه اقتصادی‌ترین انتخاب برای استفادهٔ روزمره است؛ ۱۰۰۰ و ۱۲۰۰ شانه تعادل خوبی میان ظرافت نقش و قیمت دارند و ۱۵۰۰ شانه ظریف‌ترین بافت فرش ماشینی است.',
    'در صفحهٔ هر فرش، با «نمای نزدیک بافت» می‌توانید گره‌های همان نقش را در شانه‌های مختلف کنار هم ببینید.',
  ]),
  Guide('تراکم چیست؟', 'تراکم و دوام فرش', 'تراکم، تعداد گره در طول یک متر است.', Icons.layers_outlined, [
    'تراکم تعداد گره‌ها در طول یک متر فرش است. شانه و تراکم با هم تعداد کل گره در هر متر مربع را می‌سازند.',
    'معمولاً ۷۰۰ شانه با تراکم ۲۵۵۰، ۱۰۰۰ شانه با ۳۰۰۰، ۱۲۰۰ شانه با ۳۶۰۰ و ۱۵۰۰ شانه با تراکم ۴۵۰۰ بافته می‌شود.',
    'تراکم بیشتر یعنی بافت فشرده‌تر، پرز ایستاده‌تر و نقشی که دیرتر کدر می‌شود. تراکم هر فرش در جدول مشخصات همان فرش آمده است.',
  ]),
  Guide('چه سایزی بخرم؟', 'انتخاب سایز برای هر اتاق', 'از هر دیوار ۳۰ تا ۶۰ سانت فاصله بگذارید.', Icons.straighten_rounded, [
    'قاعدهٔ ساده: فرش پذیرایی از هر دیوار حدود ۳۰ تا ۶۰ سانتی‌متر فاصله داشته باشد تا اتاق باز و مرتب دیده شود.',
    'برای اتاق خواب، فرش ۶ متری یا قالیچه‌ای که دو طرف تخت را بپوشاند مناسب است؛ برای راهرو کناره را طوری بخرید که از هر طرف کمی کف پیدا باشد.',
    'سایزیاب صفحهٔ اول این حساب را برایتان انجام می‌دهد و در صفحهٔ هر فرش، «اندازه در اتاق شما» فرش را به مقیاس روی نقشهٔ اتاق نشان می‌دهد.',
  ]),
];

class GuideCard extends StatelessWidget {
  const GuideCard(this.g, {super.key, required this.sizes});
  final Guide g;
  final List<RugSize> sizes;
  @override
  Widget build(BuildContext context) => SizedBox(
        width: 236,
        child: Material(
          color: Colors.white,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: C.line)),
          clipBehavior: Clip.antiAlias,
          child: InkWell(
            onTap: () => showGuide(context, g),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Container(
                height: 64,
                color: C.brand50,
                alignment: AlignmentDirectional.centerStart,
                padding: const EdgeInsets.symmetric(horizontal: 14),
                child: Row(children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
                    child: Icon(g.icon, color: C.brand, size: 21),
                  ),
                ]),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    decoration: BoxDecoration(color: C.gold100, borderRadius: BorderRadius.circular(6)),
                    child: Text(g.tag, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: C.goldInk, height: 1.7)),
                  ),
                  const SizedBox(height: 6),
                  Text(g.title, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800)),
                  Text(g.text, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: C.muted)),
                ]),
              ),
            ]),
          ),
        ),
      );
}

void showGuide(BuildContext context, Guide g) => showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      builder: (c) => SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(g.tag, style: const TextStyle(color: C.goldInk, fontWeight: FontWeight.w800, fontSize: 13)),
            Text(g.title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, height: 1.6)),
            const SizedBox(height: 8),
            for (final p in g.body) Padding(padding: const EdgeInsets.only(bottom: 10), child: Text(p, style: const TextStyle(height: 2, color: C.ink2))),
          ]),
        ),
      ),
    );
