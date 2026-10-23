import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/contact.dart';
import '../widgets/growth.dart';
import '../widgets/installment.dart';
import '../widgets/offers.dart';
import 'cards.dart';
import 'lens.dart';
import 'ui.dart';

/// صفحهٔ فرش فرشستان («فروشگاه تخصصی فرش»): گالری با «نمای نزدیک بافت»، رنگ‌های دیگر همین نقشه،
/// انتخاب سایز که قیمت را عوض می‌کند، «اندازه در اتاق شما»، جعبهٔ خرید، مشخصات، دیدگاه‌ها و نوار پایینی چسبان.
class HouseProductScreen extends StatefulWidget {
  const HouseProductScreen({super.key, required this.id});
  final int id;
  @override
  State<HouseProductScreen> createState() => _HouseProductScreenState();
}

class _HouseProductScreenState extends State<HouseProductScreen> {
  Json? _p;
  String? _err;
  int _img = 0, _sel = -1, _qty = 1, _sh = 700;
  bool _more = false, _lensOn = false, _lensHold = false;
  Offset _lens = const Offset(.5, .5); // نسبت به کادر فرش
  RugPixels? _px;
  final _pc = PageController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _pc.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final p = await Api.i.get('/products/${widget.id}/') as Json;
      final sizes = asList(p['sizes']);
      var sel = sizes.indexWhere((s) => (s['label'] as String? ?? '').contains('۱۲') && s['available'] == true);
      if (sel < 0) sel = sizes.indexWhere((s) => s['available'] == true);
      final reeds = int.tryParse(p['reeds'] as String? ?? '') ?? 700;
      if (!mounted) return;
      setState(() {
        _p = p;
        _sel = sel;
        _qty = sel >= 0 && sizes[sel]['pair_only'] == true ? 2 : 1;
        _sh = const [700, 1000, 1200, 1500].contains(reeds) ? reeds : 700;
      });
      _loadPixels();
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  List<Json> get _images {
    final l = asList(_p?['images']);
    if (l.isNotEmpty) return l;
    final p = _p;
    return p == null ? [] : [{'thumb': p['image'] ?? '', 'crop': p['crop']}];
  }

  Json? get _image => _images.isEmpty ? null : _images[_img.clamp(0, _images.length - 1)];
  RugCrop get _crop => RugCrop.of(_image?['crop'] ?? _p?['crop']);
  String get _url => (_image?['thumb'] as String?) ?? (_p?['image'] as String? ?? '');

  Future<void> _loadPixels() async {
    final url = _url;
    final px = await RugPixels.load(url);
    if (!mounted || url != _url) return;
    setState(() => _px = px);
  }

  List<Json> get _sizes => asList(_p?['sizes']);
  Json? get _size => _sel >= 0 && _sel < _sizes.length ? _sizes[_sel] : null;

  double get _rugWidthM {
    final s = _size;
    if (s == null) return 2.5;
    final w = (s['width'] as num? ?? 0).toDouble(), l = (s['length'] as num? ?? 0).toDouble();
    return w > 0 && l > 0 ? min(w, l) : 2.5;
  }

  KnotPainter _knots(Offset at) => KnotPainter(
      px: _px, crop: _crop, cx: at.dx, cy: at.dy, knots: max(8, (_sh * .04).round()), patch: (.04 / _rugWidthM).clamp(.004, .2));

  String _sizeName(Json s) => faDigits((s['label'] as String? ?? '').replaceAll(RegExp(r'\s*\([^()]*\)\s*$'), ''));
  bool _onSale(Json s) => s['on_sale'] == true && asInt(s['regular_price']) > asInt(s['price']);

  Future<void> _addToCart() async {
    final p = _p!, s = _size;
    if (s == null) return toast(context, 'اول یک سایز انتخاب کنید.');
    await context.read<Cart>().add(CartItem(
        variation: s['variation_id'] as int, qty: _qty, productId: p['id'] as int, title: p['title'] as String,
        size: s['label'] as String, image: p['image'] as String? ?? '', price: s['price'] as int, pairOnly: s['pair_only'] == true));
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        duration: const Duration(milliseconds: 2600),
        persist: false,
        content: Text('«${_sizeName(s)}» به سبد اضافه شد.'),
        action: SnackBarAction(label: 'دیدن سبد', textColor: C.gold300, onPressed: () => Navigator.pushNamed(context, '/cart')),
      ));
  }

  Future<void> _planner() async {
    final i = await Navigator.pushNamed(context, '/plan', arguments: {'product': _p, 'size': _sel});
    if (i is int && mounted && i < _sizes.length && _sizes[i]['available'] == true) {
      setState(() => (_sel = i, _qty = _sizes[i]['pair_only'] == true ? 2 : 1));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    if (p == null) {
      return Scaffold(
          backgroundColor: Colors.white,
          appBar: AppBar(backgroundColor: Colors.white),
          body: _err != null
              ? StatusView(message: _err!, onRetry: () {
                  setState(() => _err = null);
                  _load();
                })
              : const Loading());
    }
    final title = p['title'] as String? ?? '';
    final related = asList(p['related']);
    final count = context.watch<Cart>().count;
    return Scaffold(
      backgroundColor: Colors.white,
      body: CustomScrollView(slivers: [
        SliverAppBar(
          pinned: true,
          backgroundColor: Colors.white,
          surfaceTintColor: Colors.white,
          scrolledUnderElevation: .5,
          shadowColor: C.line,
          title: Text(faDigits(rugName(title)), style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          actions: [
            IconButton(
              tooltip: 'سبد خرید',
              onPressed: () => Navigator.pushNamed(context, '/cart'),
              icon: Badge(
                isLabelVisible: count > 0,
                label: Text(faDigits(count)),
                backgroundColor: C.gold,
                textColor: C.goldInk,
                child: const Icon(Icons.shopping_cart_outlined, color: C.ink2),
              ),
            ),
            const SizedBox(width: 6),
          ],
        ),
        SliverToBoxAdapter(child: _gallery(p)),
        SliverToBoxAdapter(child: _thumbs(p)),
        SliverToBoxAdapter(child: _texture(p)),
        SliverToBoxAdapter(child: _info(p)),
        if (asList(p['colors']).length > 1) SliverToBoxAdapter(child: _colors(p)),
        SliverToBoxAdapter(child: _sizesBlock()),
        for (final o in asList(p['special_offers'])) SliverToBoxAdapter(child: OfferBox(offer: o, product: p)),
        SliverToBoxAdapter(child: _keyFeatures(p)),
        SliverToBoxAdapter(child: _buyBox(p)),
        SliverToBoxAdapter(child: _description(p)),
        SliverToBoxAdapter(child: _specs(p)),
        SliverToBoxAdapter(child: _sizeTable()),
        SliverToBoxAdapter(child: _faqs(p)),
        SliverToBoxAdapter(child: _reviews(p)),
        if (related.isNotEmpty) ...[
          const SliverToBoxAdapter(child: SecHead('کالاهای مشابه')),
          SliverToBoxAdapter(child: CardRail(count: related.length, builder: (_, i, w) => ShopCard(related[i], width: w))),
        ],
        const SliverToBoxAdapter(child: SizedBox(height: 28)),
      ]),
      bottomNavigationBar: _buyBar(p),
    );
  }

  // ------------------------------------------------------------------ گالری و ذره‌بین
  Widget _gallery(Json p) {
    final imgs = _images;
    final id = p['id'] as int;
    final wish = context.watch<Wishlist>();
    return LayoutBuilder(builder: (_, bc) {
      final side = min(bc.maxWidth, 520.0);
      final crop = _crop;
      var rh = side * .86, rw = rh * crop.ar;
      if (rw > side * .9) {
        rw = side * .9;
        rh = rw / crop.ar;
      }
      final rug = Rect.fromCenter(center: Offset(bc.maxWidth / 2, side / 2), width: rw, height: rh);
      Offset rel(Offset local) =>
          Offset(((local.dx - rug.left) / rug.width).clamp(.05, .95), ((local.dy - rug.top) / rug.height).clamp(.04, .96));
      final showLens = (_lensOn || _lensHold) && _px != null;
      return SizedBox(
        height: side,
        child: Stack(children: [
          Positioned.fill(
            child: GestureDetector(
              onTapUp: _lensOn ? (d) => setState(() => _lens = rel(d.localPosition)) : null,
              onLongPressStart: (d) => setState(() => (_lensHold = true, _lens = rel(d.localPosition))),
              onLongPressMoveUpdate: (d) => setState(() => _lens = rel(d.localPosition)),
              onLongPressEnd: (_) => setState(() => _lensHold = false),
              onPanUpdate: _lensOn ? (d) => setState(() => _lens = rel(d.localPosition)) : null,
              child: PageView.builder(
                controller: _pc,
                physics: _lensOn ? const NeverScrollableScrollPhysics() : null,
                itemCount: imgs.length,
                onPageChanged: (i) {
                  setState(() => (_img = i, _px = null, _lens = const Offset(.5, .5)));
                  _loadPixels();
                },
                itemBuilder: (_, i) => Semantics(
                  label: 'عکس ${faDigits(i + 1)} از فرش ${p['title']}',
                  image: true,
                  child: RugStage(
                    url: imgs[i]['thumb'] as String? ?? '',
                    crop: RugCrop.of(imgs[i]['crop']),
                    seed: id,
                    fill: .86,
                    heroTag: i == 0 ? 'p$id-${p['image']}' : null,
                  ),
                ),
              ),
            ),
          ),
          if (showLens)
            Positioned(
              left: rug.left + _lens.dx * rug.width - 70,
              top: rug.top + _lens.dy * rug.height - 70 - (_lensHold ? 64 : 0),
              child: IgnorePointer(child: Loupe(painter: _knots(_lens), size: 140)),
            ),
          PositionedDirectional(
            top: 12,
            end: 12,
            child: Column(children: [
              _roundBtn(wish.has(id) ? Icons.favorite_rounded : Icons.favorite_border_rounded,
                  wish.has(id) ? 'برداشتن از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها', () => wish.toggle(id),
                  color: wish.has(id) ? C.heart : C.ink2),
              const SizedBox(height: 8),
              _roundBtn(Icons.share_outlined, 'اشتراک‌گذاری',
                  () => SharePlus.instance.share(ShareParams(text: '${p['title']}\n${p['url']}'))),
            ]),
          ),
          if (_lensOn || imgs.length > 1)
            Positioned(
              bottom: 12,
              left: 0,
              right: 0,
              child: Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
                  decoration: BoxDecoration(color: const Color(0xEBFFFFFF), borderRadius: BorderRadius.circular(20), boxShadow: kShadow1),
                  child: Text(
                    _lensOn
                        ? (_px == null ? 'در حال آماده کردن بافت…' : 'انگشت را روی فرش بکشید')
                        : '${faDigits(_img + 1)} از ${faDigits(imgs.length)}',
                    style: const TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ),
        ]),
      );
    });
  }

  Widget _roundBtn(IconData ic, String tip, VoidCallback on, {Color color = C.ink2}) => Material(
        color: Colors.white,
        shape: const CircleBorder(),
        elevation: 0,
        shadowColor: Colors.transparent,
        child: Container(
          decoration: const BoxDecoration(shape: BoxShape.circle, boxShadow: kShadow1),
          child: IconButton(tooltip: tip, onPressed: on, icon: Icon(ic, color: color, size: 21)),
        ),
      );

  Widget _thumbs(Json p) {
    final imgs = _images;
    Widget tool(IconData ic, String t, VoidCallback on, {bool active = false}) => Padding(
          padding: const EdgeInsetsDirectional.only(end: 8),
          child: Material(
            color: active ? C.brand : C.brand50,
            borderRadius: BorderRadius.circular(10),
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: on,
              child: SizedBox(
                width: 72,
                height: 68,
                child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Icon(ic, size: 20, color: active ? Colors.white : C.brand),
                  const SizedBox(height: 3),
                  Text(t,
                      textAlign: TextAlign.center,
                      style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, height: 1.3, color: active ? Colors.white : C.brand)),
                ]),
              ),
            ),
          ),
        );
    return SizedBox(
      height: 84,
      child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.fromLTRB(16, 8, 16, 8), children: [
        if (imgs.length > 1)
          for (var i = 0; i < imgs.length; i++)
            Padding(
              padding: const EdgeInsetsDirectional.only(end: 8),
              child: GestureDetector(
                onTap: () => _pc.animateToPage(i, duration: const Duration(milliseconds: 300), curve: Curves.easeOut),
                child: Container(
                  width: 68,
                  height: 68,
                  clipBehavior: Clip.antiAlias,
                  decoration: BoxDecoration(
                    color: C.soft,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: i == _img ? C.brand : C.line, width: i == _img ? 2 : 1.5),
                  ),
                  child: RugStage(url: imgs[i]['thumb'] as String? ?? '', crop: RugCrop.of(imgs[i]['crop']), seed: p['id'] as int),
                ),
              ),
            ),
        tool(Icons.zoom_in_rounded, 'نمای نزدیک\nبافت', () => setState(() => _lensOn = !_lensOn), active: _lensOn),
        tool(Icons.crop_square_rounded, 'در اتاق\nشما', _planner),
        tool(Icons.photo_camera_outlined, 'با دوربین', () => Navigator.pushNamed(context, '/room', arguments: {'product': p, 'size': _sel})),
      ]),
    );
  }

  /// «نمای نزدیک بافت»: همین نقش با شانه‌های مختلف زیر ذره‌بین
  Widget _texture(Json p) {
    final own = p['reeds'] as String? ?? '';
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(color: C.brand50, border: Border.all(color: C.brand100), borderRadius: BorderRadius.circular(14)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.all(6),
          child: _px == null
              ? Container(width: 76, height: 76, decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.white))
              : Loupe(painter: _knots(_lens), size: 76, handle: false),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              const Expanded(child: Text('نمای نزدیک بافت', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5, color: C.brand800))),
              GestureDetector(
                onTap: () => setState(() => _lensOn = !_lensOn),
                child: Text(_lensOn ? 'بستن ذره‌بین' : 'ذره‌بین روی عکس',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: C.brand)),
              ),
            ]),
            const SizedBox(height: 8),
            Container(
              padding: const EdgeInsets.all(3),
              decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8), border: Border.all(color: C.brand100)),
              child: Row(children: [
                for (final s in const [700, 1000, 1200, 1500])
                  Expanded(
                    child: Semantics(
                      selected: _sh == s,
                      button: true,
                      label: '${faDigits(s)} شانه',
                      child: GestureDetector(
                        onTap: () => setState(() => _sh = s),
                        child: Container(
                          height: 40,
                          alignment: Alignment.center,
                          decoration: BoxDecoration(color: _sh == s ? C.brand : Colors.transparent, borderRadius: BorderRadius.circular(6)),
                          child: Column(mainAxisSize: MainAxisSize.min, children: [
                            Text(faDigits(s),
                                style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5, height: 1.2, color: _sh == s ? Colors.white : C.ink)),
                            Text('$s' == own ? 'این فرش' : 'شانه',
                                style: TextStyle(
                                    fontSize: 9.5,
                                    height: 1.3,
                                    fontWeight: '$s' == own ? FontWeight.w800 : FontWeight.w500,
                                    color: _sh == s ? const Color(0xFFC9D4EE) : ('$s' == own ? C.gold : C.muted))),
                          ]),
                        ),
                      ),
                    ),
                  ),
              ]),
            ),
            const SizedBox(height: 6),
            Text(knotSentence(_sh, own), style: const TextStyle(fontSize: 12, color: C.ink2, height: 1.8)),
          ]),
        ),
      ]),
    );
  }

  // ------------------------------------------------------------------ تیتر
  Widget _info(Json p) {
    final title = p['title'] as String? ?? '';
    final cats = asList(p['categories']);
    final rc = asInt(p['rating_count']);
    final sku = p['sku'] as String? ?? '';
    final reeds = p['reeds'] as String? ?? '';
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (cats.isNotEmpty)
          Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 6, children: [
            const Star8(size: 14, color: C.brand),
            for (final (i, c) in cats.take(2).indexed) ...[
              if (i > 0) const Text('/', style: TextStyle(color: C.faint)),
              GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/products', arguments: {'title': faDigits(c['name'] ?? ''), 'query': {'category': c['id']}}),
                child: Text(faDigits(c['name'] ?? ''), style: const TextStyle(color: C.brand, fontWeight: FontWeight.w700, fontSize: 13)),
              ),
            ],
          ]),
        const SizedBox(height: 6),
        Text(faDigits(title), style: const TextStyle(fontSize: 18.5, fontWeight: FontWeight.w800, height: 1.75)),
        const SizedBox(height: 8),
        Wrap(spacing: 12, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          if (rc > 0) RatingLine(p['rating'], rc, size: 13),
          if (reeds.isNotEmpty) Bdg('${faDigits(reeds)} شانه', kind: BdgKind.brand),
          if (title.contains('برجسته')) const Bdg('بافت برجسته', kind: BdgKind.gold),
          if (sku.isNotEmpty) Text('کد کالا: ${faDigits(sku)}', style: const TextStyle(fontSize: 12.5, color: C.muted)),
        ]),
        const SizedBox(height: 14),
        const Divider(color: C.line2),
      ]),
    );
  }

  Widget _blkHead(String t, {String? trailing}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          Expanded(child: Text(t, style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800))),
          if (trailing != null) Text(trailing, style: const TextStyle(fontSize: 13, color: C.muted)),
        ]),
      );

  Widget _colors(Json p) {
    final cs = asList(p['colors']);
    final cur = cs.firstWhere((c) => c['current'] == true, orElse: () => cs.first);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _blkHead('رنگ‌های دیگر همین نقشه', trailing: faDigits(cur['color'] ?? '')),
        SizedBox(
          height: 100,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: cs.length,
            separatorBuilder: (_, _) => const SizedBox(width: 10),
            itemBuilder: (_, i) {
              final c = cs[i], on = c['current'] == true;
              return Semantics(
                selected: on,
                button: true,
                child: GestureDetector(
                  onTap: on ? null : () => Navigator.pushReplacementNamed(context, '/product', arguments: c['id']),
                  child: Container(
                    width: 78,
                    padding: const EdgeInsets.fromLTRB(4, 6, 4, 4),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: on ? C.brand : C.line, width: on ? 2 : 1.5),
                    ),
                    child: Column(children: [
                      Expanded(child: RugStage(url: c['image'] as String? ?? '', seed: asInt(c['id']), fill: .9)),
                      const SizedBox(height: 4),
                      Text(faDigits(c['color'] ?? ''),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: on ? C.brand : C.ink2)),
                    ]),
                  ),
                ),
              );
            },
          ),
        ),
      ]),
    );
  }

  // ------------------------------------------------------------------ سایز
  Widget _sizesBlock() {
    final sizes = _sizes;
    if (sizes.isEmpty) return const SizedBox.shrink();
    final s = _size;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _blkHead('انتخاب سایز', trailing: s == null ? null : '${_sizeName(s)}${(s['dimensions'] as String? ?? '').isNotEmpty ? ' · ${faDigits(s['dimensions'])}' : ''}'),
        LayoutBuilder(builder: (_, bc) {
          final cw = (bc.maxWidth - 8) / 2;
          return Wrap(spacing: 8, runSpacing: 8, children: [
            for (var i = 0; i < sizes.length; i++) SizedBox(width: cw, child: _sizeTile(sizes[i], i)),
          ]);
        }),
        const SizedBox(height: 10),
        Material(
          color: C.surface2,
          borderRadius: BorderRadius.circular(12),
          child: InkWell(
            borderRadius: BorderRadius.circular(12),
            onTap: _planner,
            child: CustomPaint(
              painter: _DashedBorder(),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                child: Row(children: [
                  Container(
                    width: 36,
                    height: 36,
                    decoration: BoxDecoration(color: C.brand, borderRadius: BorderRadius.circular(10)),
                    child: const Icon(Icons.crop_free_rounded, color: Colors.white, size: 20),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      const Text('اندازه در اتاق شما', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: C.brand800)),
                      Text(
                          s == null
                              ? 'فرش را به مقیاس روی نقشهٔ اتاقتان ببینید'
                              : 'فرش ${_sizeName(s)} را به مقیاس روی نقشهٔ اتاقتان ببینید',
                          style: const TextStyle(fontSize: 12, color: C.muted)),
                    ]),
                  ),
                  const Icon(Icons.chevron_left_rounded, color: C.brand),
                ]),
              ),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _sizeTile(Json s, int i) {
    final on = i == _sel, ok = s['available'] == true;
    final dims = s['dimensions'] as String? ?? '';
    return Semantics(
      selected: on,
      button: true,
      enabled: ok,
      child: Material(
        color: on ? C.brand50 : (ok ? Colors.white : C.soft),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10), side: BorderSide(color: on ? C.brand : C.line, width: 1.5)),
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: ok ? () => setState(() => (_sel = i, _qty = s['pair_only'] == true ? 2 : 1)) : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(
                  child: Text(_sizeName(s),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5, color: on ? C.brand : (ok ? C.ink : C.faint))),
                ),
                if (s['pair_only'] == true) const Bdg('جفت', kind: BdgKind.gold),
              ]),
              Text(dims.isNotEmpty ? '${faDigits(dims)} متر' : ' ', style: TextStyle(fontSize: 11.5, color: ok ? C.muted : C.faint)),
              ok
                  ? Text.rich(TextSpan(children: [
                      if (_onSale(s))
                        TextSpan(
                            text: '${sep(asInt(s['regular_price']))} ',
                            style: const TextStyle(fontSize: 11, decoration: TextDecoration.lineThrough, color: C.faint)),
                      TextSpan(text: sep(asInt(s['price'])), style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5, color: on ? C.brand800 : C.ink2)),
                      const TextSpan(text: ' تومان', style: TextStyle(fontSize: 10.5, color: C.muted)),
                    ]))
                  : const Text('ناموجود', style: TextStyle(color: C.faint, fontSize: 12, fontWeight: FontWeight.w700)),
            ]),
          ),
        ),
      ),
    );
  }

  /// چهار ویژگی اصلی (شانه، تراکم، جنس نخ، بافت) از مشخصات واقعی همین فرش
  Widget _keyFeatures(Json p) {
    final specs = asList(p['specs']);
    if (specs.isEmpty) return const SizedBox.shrink();
    final picked = <Json>[];
    for (final k in const ['شانه', 'تراکم', 'جنس', 'بافت', 'رنگ']) {
      final f = specs.where((s) => (s['name'] as String? ?? '').contains(k) && !picked.contains(s));
      if (f.isNotEmpty) picked.add(f.first);
      if (picked.length == 4) break;
    }
    for (final s in specs) {
      if (picked.length >= 4) break;
      if (!picked.contains(s)) picked.add(s);
    }
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        _blkHead('ویژگی‌های اصلی'),
        LayoutBuilder(builder: (_, bc) {
          final cw = (bc.maxWidth - 8) / 2;
          return Wrap(spacing: 8, runSpacing: 8, children: [
            for (final s in picked)
              Container(
                width: cw,
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(8)),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(s['name'] as String? ?? '', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: C.muted)),
                  Text(faDigits(s['value'] ?? ''),
                      maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800)),
                ]),
              ),
          ]);
        }),
      ]),
    );
  }

  // ------------------------------------------------------------------ جعبهٔ خرید
  Widget _buyBox(Json p) {
    final s = _size;
    final seller = asMap(p['seller']);
    final inStock = p['in_stock'] as bool? ?? true;
    final purchasable = p['purchasable'] as bool? ?? true;
    final wish = context.watch<Wishlist>(), cmp = context.watch<Compare>();
    final id = p['id'] as int;
    final price = s == null ? asInt(p['price']) : asInt(s['price']);
    final ship = [
      if ((seller['shipping'] as String? ?? '').isNotEmpty) seller['shipping'] as String,
      if (asInt(seller['prep_days']) > 0) 'آماده‌سازی ${faDigits(asInt(seller['prep_days']))} روز کاری',
    ].join(' · ');
    Widget line(IconData ic, String t, {Color? color}) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(children: [
            Icon(ic, size: 19, color: color ?? C.brand),
            const SizedBox(width: 8),
            Expanded(child: Text(t, style: TextStyle(fontSize: 13, color: color ?? C.ink2, fontWeight: color != null ? FontWeight.w700 : FontWeight.w500))),
          ]),
        );
    Widget sec(IconData ic, String t, VoidCallback on, {bool active = false}) => Expanded(
          child: OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(10, 44),
              padding: const EdgeInsets.symmetric(horizontal: 6),
              foregroundColor: active ? C.brand : C.ink2,
              backgroundColor: active ? C.brand50 : Colors.white,
              side: BorderSide(color: active ? C.brand : C.line),
              textStyle: const TextStyle(fontFamily: kFont, fontSize: 12.5, fontWeight: FontWeight.w700),
            ),
            onPressed: on,
            icon: Icon(ic, size: 18),
            label: FittedBox(child: Text(t)),
          ),
        );
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 20, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: C.surface2, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(16)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (seller.isNotEmpty) ...[
          Row(children: [
            Container(
              width: 40,
              height: 40,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: Colors.white, shape: BoxShape.circle, border: Border.all(color: C.brand100)),
              child: const FarshestanMark(size: 26),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('فروشنده: ${seller['name'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
                if ((seller['city'] as String? ?? '').isNotEmpty) Text(seller['city'] as String, style: const TextStyle(color: C.muted, fontSize: 12)),
              ]),
            ),
          ]),
          const Padding(padding: EdgeInsets.symmetric(vertical: 12), child: Divider(color: C.line)),
        ],
        inStock && purchasable
            ? line(Icons.inventory_2_outlined, 'موجود و آمادهٔ سفارش', color: C.ok)
            : line(Icons.inventory_2_outlined, 'در حال حاضر ناموجود', color: C.warn),
        if (ship.isNotEmpty) line(Icons.local_shipping_outlined, ship),
        if (s != null && s['pair_only'] == true) line(Icons.info_outline_rounded, 'این سایز فقط به‌صورت جفت فروخته می‌شود.'),
        const Divider(color: C.line),
        const SizedBox(height: 10),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          if (s != null && purchasable)
            Container(
              height: 46,
              decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.line, width: 1.5), borderRadius: BorderRadius.circular(10)),
              child: Row(children: [
                IconButton(
                    tooltip: 'یکی بیشتر',
                    color: C.brand,
                    onPressed: _qty + _step <= 20 ? () => setState(() => _qty += _step) : null,
                    icon: const Icon(Icons.add_rounded)),
                Text(faDigits(_qty), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                IconButton(
                    tooltip: 'یکی کمتر',
                    color: C.brand,
                    onPressed: _qty - _step >= _step ? () => setState(() => _qty -= _step) : null,
                    icon: const Icon(Icons.remove_rounded)),
              ]),
            ),
          const Spacer(),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            CardPrice(
              price: price * (s == null ? 1 : _qty),
              strike: s != null && _onSale(s) ? asInt(s['regular_price']) * _qty : null,
              from: s == null && p['price_is_from'] == true,
              size: 22,
            ),
            if (s != null) Text('قیمت ${_qty > 1 ? '${faDigits(_qty)} تخته ' : ''}${_sizeName(s)}', style: const TextStyle(fontSize: 11.5, color: C.muted)),
          ]),
        ]),
        if (purchasable && price > 0)
          InstallmentTeaser(
              plans: context.watch<AppConfig>().installmentPlans, amount: price * (s == null ? 1 : _qty), margin: const EdgeInsets.only(top: 12)),
        const SizedBox(height: 12),
        Row(children: [
          sec(wish.has(id) ? Icons.favorite_rounded : Icons.favorite_border_rounded, 'علاقه‌مندی', () => wish.toggle(id), active: wish.has(id)),
          const SizedBox(width: 6),
          sec(Icons.compare_arrows_rounded, 'مقایسه', () {
            if (!cmp.toggle(id)) return toast(context, 'حداکثر سه فرش را می‌شود با هم مقایسه کرد.');
            if (cmp.has(id) && cmp.ids.length > 1) {
              ScaffoldMessenger.of(context)
                ..hideCurrentSnackBar()
                ..showSnackBar(SnackBar(
                    content: Text('${faDigits(cmp.ids.length)} فرش برای مقایسه'),
                    action: SnackBarAction(label: 'مقایسه', textColor: C.gold300, onPressed: () => Navigator.pushNamed(context, '/compare'))));
            }
          }, active: cmp.has(id)),
          const SizedBox(width: 6),
          sec(purchasable ? Icons.trending_down_rounded : Icons.notifications_active_outlined, 'خبرم کن',
              () => ProductExtras.ask(context, p, purchasable ? 'price' : 'stock')),
        ]),
        if (p['video'] != null) ...[
          const SizedBox(height: 8),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(minimumSize: const Size(10, 44)),
            onPressed: () => launchUrl(Uri.parse((p['video'] as Json)['url'] as String), mode: LaunchMode.externalApplication),
            icon: const Icon(Icons.play_circle_outline_rounded),
            label: const Text('ویدیوی فرش'),
          ),
        ],
      ]),
    );
  }

  int get _step => _size?['pair_only'] == true ? 2 : 1;

  // ------------------------------------------------------------------ بخش‌های پایین
  Widget _secHead(String t, {Widget? trailing}) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 30, 16, 12),
        child: Row(children: [
          Container(width: 4, height: 20, decoration: BoxDecoration(color: C.gold, borderRadius: BorderRadius.circular(2))),
          const SizedBox(width: 8),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800))),
          ?trailing,
        ]),
      );

  Widget _description(Json p) {
    final short = p['short_description'] as String? ?? '', long = p['content_text'] as String? ?? '';
    if (short.isEmpty && long.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _secHead('معرفی'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (short.isNotEmpty) Text(faDigits(short), style: const TextStyle(height: 2, color: C.ink2, fontSize: 14)),
          if (long.isNotEmpty) ...[
            const SizedBox(height: 6),
            AnimatedCrossFade(
              duration: const Duration(milliseconds: 250),
              crossFadeState: _more ? CrossFadeState.showSecond : CrossFadeState.showFirst,
              firstChild: Text(faDigits(long), maxLines: 5, overflow: TextOverflow.ellipsis, style: const TextStyle(color: C.ink2, height: 2, fontSize: 14)),
              secondChild: Text(faDigits(long), style: const TextStyle(color: C.ink2, height: 2, fontSize: 14)),
            ),
            TextButton(
              style: TextButton.styleFrom(foregroundColor: C.brand, padding: EdgeInsets.zero),
              onPressed: () => setState(() => _more = !_more),
              child: Text(_more ? 'بستن' : 'بیشتر بخوانید', style: const TextStyle(fontWeight: FontWeight.w700)),
            ),
          ],
        ]),
      ),
    ]);
  }

  Widget _specs(Json p) {
    final specs = asList(p['specs']);
    if (specs.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _secHead('مشخصات فنی'),
      Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
        clipBehavior: Clip.antiAlias,
        child: Column(children: [
          for (final (i, s) in specs.indexed)
            Container(
              color: i.isEven ? C.surface2 : Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 118, child: Text(s['name'] as String? ?? '', style: const TextStyle(color: C.muted, fontSize: 13))),
                Expanded(child: Text(faDigits(s['value'] ?? ''), style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5))),
              ]),
            ),
        ]),
      ),
    ]);
  }

  /// جدول سایز و قیمت (همهٔ سایزهای همین فرش)
  Widget _sizeTable() {
    final sizes = _sizes;
    if (sizes.length < 2) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _secHead('جدول سایز و قیمت'),
      Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
        clipBehavior: Clip.antiAlias,
        child: Column(children: [
          Container(
            color: C.brand50,
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: const Row(children: [
              Expanded(flex: 5, child: Text('سایز', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5, color: C.brand800))),
              Expanded(flex: 4, child: Text('ابعاد (متر)', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5, color: C.brand800))),
              Expanded(flex: 5, child: Text('قیمت (تومان)', textAlign: TextAlign.end, style: TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5, color: C.brand800))),
            ]),
          ),
          for (final (i, s) in sizes.indexed)
            InkWell(
              onTap: s['available'] == true ? () => setState(() => (_sel = i, _qty = s['pair_only'] == true ? 2 : 1)) : null,
              child: Container(
                color: i == _sel ? const Color(0x80EEF2FA) : null,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 9),
                decoration: i == 0 ? null : null,
                child: Row(children: [
                  Expanded(flex: 5, child: Text(_sizeName(s), style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700))),
                  Expanded(flex: 4, child: Text(faDigits(s['dimensions'] ?? ''), style: const TextStyle(fontSize: 12.5, color: C.muted))),
                  Expanded(
                    flex: 5,
                    child: Text(s['available'] == true ? sep(asInt(s['price'])) : 'ناموجود',
                        textAlign: TextAlign.end,
                        style: TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w800, color: s['available'] == true ? C.ink : C.faint)),
                  ),
                ]),
              ),
            ),
        ]),
      ),
    ]);
  }

  Widget _faqs(Json p) {
    final fs = asList(p['faqs']);
    if (fs.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _secHead('پرسش‌های متداول'),
      for (final f in fs)
        Container(
          margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
          decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
          clipBehavior: Clip.antiAlias,
          child: ExpansionTile(
            shape: const Border(),
            collapsedShape: const Border(),
            iconColor: C.brand,
            title: Text(f['q'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            expandedAlignment: AlignmentDirectional.centerStart,
            children: [Text(f['a'] as String? ?? '', style: const TextStyle(color: C.ink2, height: 1.9))],
          ),
        ),
    ]);
  }

  /// «محمد رضایی» ← «محمد ر.» (نام کامل خریدار نمایش داده نمی‌شود)
  String _who(String a) {
    final w = a.trim().split(RegExp(r'\s+')).where((x) => x.isNotEmpty).toList();
    if (w.isEmpty) return 'کاربر فرشستان';
    return w.length == 1 ? w.first : '${w.first} ${w[1].characters.first}.';
  }

  Widget _reviews(Json p) {
    final rs = asList(p['reviews']);
    final rated = rs.where((r) => asInt(r['rating']) > 0).toList();
    final count = max(asInt(p['rating_count']), rated.length);
    final avg = asInt(p['rating_count']) > 0
        ? (p['rating'] as num? ?? 0).toDouble()
        : (rated.isEmpty ? 0.0 : rated.map((r) => asInt(r['rating'])).reduce((a, b) => a + b) / rated.length);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      _secHead('دیدگاه خریداران',
          trailing: TextButton(
            style: TextButton.styleFrom(foregroundColor: C.brand),
            onPressed: () => showReviewSheet(context, p['id'] as int),
            child: const Text('ثبت دیدگاه', style: TextStyle(fontWeight: FontWeight.w700)),
          )),
      if (rs.isEmpty)
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 16),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: C.surface2, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
          child: const Row(children: [
            Icon(Icons.rate_review_outlined, color: C.brand),
            SizedBox(width: 10),
            Expanded(child: Text('هنوز دیدگاهی برای این فرش ثبت نشده؛ اگر آن را خریده‌اید، اولین نفر باشید.', style: TextStyle(color: C.ink2, fontSize: 13, height: 1.8))),
          ]),
        )
      else ...[
        if (rated.isNotEmpty)
          Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: C.surface2, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
            child: Row(children: [
              Column(children: [
                Text(faDigits(avg.toStringAsFixed(1)).replaceAll('.', '٫'), style: const TextStyle(fontSize: 34, fontWeight: FontWeight.w900, height: 1.2)),
                Row(mainAxisSize: MainAxisSize.min, children: [
                  for (var k = 1; k <= 5; k++)
                    Icon(k <= avg.round() ? Icons.star_rounded : Icons.star_outline_rounded, size: 15, color: C.gold),
                ]),
                Text('از ${faDigits(count)} دیدگاه', style: const TextStyle(fontSize: 11.5, color: C.muted)),
              ]),
              const SizedBox(width: 18),
              Expanded(
                child: Column(children: [
                  for (var k = 5; k >= 1; k--)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Row(children: [
                        SizedBox(width: 14, child: Text(faDigits(k), style: const TextStyle(fontSize: 11.5, color: C.muted))),
                        const SizedBox(width: 4),
                        Expanded(
                          child: ClipRRect(
                            borderRadius: BorderRadius.circular(3),
                            child: LinearProgressIndicator(
                              value: rated.where((r) => asInt(r['rating']) == k).length / rated.length,
                              minHeight: 6,
                              backgroundColor: C.line2,
                              color: C.gold,
                            ),
                          ),
                        ),
                      ]),
                    ),
                ]),
              ),
            ]),
          ),
        for (final r in rs.take(6))
          Container(
            margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(12)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                CircleAvatar(
                  radius: 15,
                  backgroundColor: C.brand50,
                  child: Text(_who(r['author'] as String? ?? '').characters.first,
                      style: const TextStyle(color: C.brand, fontWeight: FontWeight.w800, fontSize: 13)),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(_who(r['author'] as String? ?? ''), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13)),
                    if (r['verified'] == true)
                      const Text('خریدار این فرش', style: TextStyle(fontSize: 11, color: C.ok, fontWeight: FontWeight.w700)),
                  ]),
                ),
                if (asInt(r['rating']) > 0)
                  Row(mainAxisSize: MainAxisSize.min, children: [
                    for (var k = 0; k < asInt(r['rating']); k++) const Icon(Icons.star_rounded, size: 15, color: C.gold),
                  ]),
              ]),
              const SizedBox(height: 8),
              Text(r['text'] as String? ?? '', style: const TextStyle(fontSize: 13.5, height: 1.9, color: C.ink2)),
            ]),
          ),
      ],
    ]);
  }

  // ------------------------------------------------------------------ نوار پایینی
  Widget _buyBar(Json p) {
    final s = _size;
    final purchasable = p['purchasable'] as bool? ?? true;
    return Container(
      decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: C.line)),
          boxShadow: [BoxShadow(color: Color(0x0F141D33), blurRadius: 12, offset: Offset(0, -4))]),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
          child: !purchasable || s == null
              ? Row(children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      style: OutlinedButton.styleFrom(minimumSize: const Size(10, 50)),
                      onPressed: () => ProductExtras.ask(context, p, 'stock'),
                      icon: const Icon(Icons.notifications_active_outlined, size: 20),
                      label: const FittedBox(child: Text('موجود شد خبرم کن')),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      style: FilledButton.styleFrom(minimumSize: const Size(10, 50)),
                      onPressed: () => showContactSheet(context, text: p['url'] as String?),
                      icon: const Icon(Icons.support_agent_rounded, size: 20),
                      label: const FittedBox(child: Text('پرسیدن از کارشناس')),
                    ),
                  ),
                ])
              : Row(children: [
                  Expanded(
                    flex: 11,
                    child: FilledButton(
                      style: FilledButton.styleFrom(minimumSize: const Size(10, 52)),
                      onPressed: _addToCart,
                      child: const Text('افزودن به سبد'),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    flex: 10,
                    child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.end, children: [
                      FittedBox(
                        child: CardPrice(
                          price: asInt(s['price']) * _qty,
                          strike: _onSale(s) ? asInt(s['regular_price']) * _qty : null,
                          size: 17,
                        ),
                      ),
                      Text('${_qty > 1 ? '${faDigits(_qty)} تخته · ' : ''}${_sizeName(s)}',
                          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: C.muted)),
                    ]),
                  ),
                ]),
        ),
      ),
    );
  }
}

class _DashedBorder extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final r = RRect.fromRectAndRadius(Offset.zero & s, const Radius.circular(12)).deflate(.75);
    final path = Path()..addRRect(r);
    final paint = Paint()
      ..color = C.brand200
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5;
    for (final m in path.computeMetrics()) {
      for (var d = 0.0; d < m.length; d += 9) {
        c.drawPath(m.extractPath(d, min(d + 5, m.length)), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_DashedBorder o) => false;
}
