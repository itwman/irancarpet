import 'dart:math';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';

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
import 'unroll.dart';

/// صفحهٔ فرش فرشستان: فرش روی آجرفرش باز می‌شود، ذره‌بین گره‌ها را از روی عکس خود فرش نشان می‌دهد،
/// و «در اتاق من» سایز را با اندازهٔ واقعی روی نقشهٔ اتاق می‌نشاند.
class HouseProductScreen extends StatefulWidget {
  const HouseProductScreen({super.key, required this.id});
  final int id;
  @override
  State<HouseProductScreen> createState() => _HouseProductScreenState();
}

class _HouseProductScreenState extends State<HouseProductScreen> with SingleTickerProviderStateMixin {
  Json? _p;
  String? _err;
  int _img = 0, _sel = -1, _qty = 1, _sh = 700;
  bool _more = false, _lensOn = false, _lensHold = false;
  Offset _lens = const Offset(.5, .5); // نسبت به کادر فرش
  RugPixels? _px;
  late final AnimationController _ur = AnimationController(vsync: this, duration: const Duration(milliseconds: 1800));
  late final Animation<double> _urA = CurvedAnimation(parent: _ur, curve: Curves.easeInOutCubic);
  final _rugKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _ur.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final p = await Api.i.get('/products/${widget.id}/') as Json;
      final sizes = (p['sizes'] as List).cast<Json>();
      var sel = sizes.indexWhere((s) => (s['label'] as String).contains('۱۲') && s['available'] == true);
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

  List<Json> get _images => ((_p?['images'] as List?) ?? []).cast<Json>();
  Json? get _image => _images.isEmpty ? null : _images[_img.clamp(0, _images.length - 1)];
  RugCrop get _crop => RugCrop.of(_image?['crop'] ?? _p?['crop']);
  String get _url => (_image?['thumb'] as String?) ?? (_p?['image'] as String? ?? '');

  Future<void> _loadPixels() async {
    final url = _url;
    final reduce = MediaQuery.maybeDisableAnimationsOf(context) ?? false;
    // فرش تا رسیدن عکس لوله می‌ماند؛ بعد باز می‌شود
    final px = await RugPixels.load(url);
    if (!mounted || url != _url) return;
    setState(() => _px = px);
    if (reduce) {
      _ur.value = 1;
    } else {
      _ur.forward(from: 0);
    }
  }

  List<Json> get _sizes => ((_p?['sizes'] as List?) ?? []).cast<Json>();
  Json? get _size => _sel >= 0 && _sel < _sizes.length ? _sizes[_sel] : null;

  double get _rugWidthM {
    final s = _size;
    if (s == null) return 2.5;
    final w = (s['width'] as num).toDouble(), l = (s['length'] as num).toDouble();
    return w > 0 && l > 0 ? min(w, l) : 2.5;
  }

  KnotPainter _knots(Offset at) => KnotPainter(
      px: _px, crop: _crop, cx: at.dx, cy: at.dy, knots: max(8, (_sh * .04).round()), patch: (.04 / _rugWidthM).clamp(.004, .2));

  Future<void> _addToCart() async {
    final p = _p!, s = _size;
    if (s == null) return toast(context, 'اول یک سایز انتخاب کنید.');
    await context.read<Cart>().add(CartItem(
        variation: s['variation_id'] as int, qty: _qty, productId: p['id'] as int, title: p['title'] as String,
        size: s['label'] as String, image: p['image'] as String, price: s['price'] as int, pairOnly: s['pair_only'] as bool));
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(
        duration: const Duration(milliseconds: 2600),
        persist: false,
        content: Text('«${faDigits(s['label'])}» به سبد اضافه شد.'),
        action: SnackBarAction(label: 'دیدن سبد', textColor: C.saffron, onPressed: () => Navigator.pushNamed(context, '/cart')),
      ));
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    if (p == null) {
      return Scaffold(
          appBar: AppBar(),
          body: _err != null
              ? StatusView(message: _err!, onRetry: () {
                  setState(() => _err = null);
                  _load();
                })
              : const Loading());
    }
    final wish = context.watch<Wishlist>();
    final id = p['id'] as int;
    final title = p['title'] as String;
    return Scaffold(
      body: CustomScrollView(slivers: [
        SliverAppBar(
          pinned: true,
          title: Text(faDigits(rugName(title)), style: nast(24, height: 1.6)),
          actions: [
            IconButton(
                tooltip: 'اشتراک‌گذاری',
                onPressed: () => SharePlus.instance.share(ShareParams(text: '$title\n${p['url']}')),
                icon: const Icon(Icons.share_outlined)),
            IconButton(
                tooltip: wish.has(id) ? 'برداشتن از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها',
                onPressed: () => wish.toggle(id),
                icon: Icon(wish.has(id) ? Icons.favorite : Icons.favorite_border, color: wish.has(id) ? C.pink : null)),
          ],
          bottom: const PreferredSize(preferredSize: Size.fromHeight(6), child: GirihBand(height: 6)),
        ),
        SliverToBoxAdapter(child: _floor(p)),
        if (_images.length > 1) SliverToBoxAdapter(child: _thumbs()),
        SliverToBoxAdapter(child: _tools(p)),
        SliverToBoxAdapter(child: _knotBox(p)),
        SliverToBoxAdapter(child: _info(p)),
        if (((p['colors'] as List?) ?? []).length > 1) SliverToBoxAdapter(child: _colors(p)),
        for (final o in ((p['special_offers'] as List?) ?? []).cast<Json>()) SliverToBoxAdapter(child: OfferBox(offer: o, product: p)),
        SliverToBoxAdapter(child: _sizesGrid()),
        if (p['purchasable'] == true && ((_size?['price'] as int?) ?? (p['price'] as int? ?? 0)) > 0)
          SliverToBoxAdapter(
            child: InstallmentTeaser(
                plans: context.watch<AppConfig>().installmentPlans, amount: (_size?['price'] as int?) ?? (p['price'] as int)),
          ),
        SliverToBoxAdapter(child: ProductExtras(p)),
        SliverToBoxAdapter(child: _specs(p)),
        SliverToBoxAdapter(child: _description(p)),
        SliverToBoxAdapter(child: _reviews(p)),
        SliverToBoxAdapter(child: _faqs(p)),
        if ((p['related'] as List).isNotEmpty) ...[
          SliverToBoxAdapter(child: _head('هم‌خانواده‌ها')),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 372,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: (p['related'] as List).length,
                separatorBuilder: (_, _) => const SizedBox(width: 14),
                itemBuilder: (_, i) => NicheCard((p['related'] as List)[i] as Json, width: 158),
              ),
            ),
          ),
        ],
        const SliverToBoxAdapter(child: SizedBox(height: 110)),
      ]),
      bottomNavigationBar: _buyBar(p),
    );
  }

  /// فرش روی آجرفرش، زیر نور ارسی؛ با لمس طولانی یا ذره‌بین روشن، گره‌ها دیده می‌شوند
  Widget _floor(Json p) {
    final w = MediaQuery.sizeOf(context).width;
    final crop = _crop;
    final rugW = min(w * .7, 380.0), rugH = rugW / crop.ar;
    final maxH = MediaQuery.sizeOf(context).height * .58;
    final fitW = rugH > maxH ? maxH * crop.ar : rugW;
    final showLens = _lensOn || _lensHold;
    return BrickFloor(
      padding: const EdgeInsets.fromLTRB(16, 26, 16, 30),
      child: Center(
        child: SizedBox(
          width: fitW,
          child: GestureDetector(
            key: _rugKey,
            onTapUp: (d) => _moveLens(d.localPosition, show: true),
            onLongPressStart: (d) => setState(() {
              _lensHold = true;
              _lens = _rel(d.localPosition);
            }),
            onLongPressMoveUpdate: (d) => setState(() => _lens = _rel(d.localPosition)),
            onLongPressEnd: (_) => setState(() => _lensHold = false),
            onPanUpdate: _lensOn ? (d) => _moveLens(d.localPosition) : null,
            child: Stack(clipBehavior: Clip.none, children: [
              DecoratedBox(
                decoration: const BoxDecoration(boxShadow: [BoxShadow(color: Color(0x80281405), blurRadius: 22, offset: Offset(0, 16))]),
                child: UnrollRug(
                  progress: _urA,
                  ar: crop.ar,
                  roll: _px?.rollColors(crop),
                  child: Semantics(
                    label: 'عکس فرش ${p['title']}',
                    image: true,
                    child: RugImage(_url, crop: crop, seed: p['id'] as int),
                  ),
                ),
              ),
              // ذره‌بین؛ هنگام نگه داشتن انگشت کمی بالاتر تا زیر انگشت پنهان نشود
              if (showLens)
                Positioned(
                  left: _lens.dx * fitW - 75,
                  top: _lens.dy * fitW / crop.ar - 75 - (_lensHold ? 70 : 0),
                  child: IgnorePointer(child: Loupe(painter: _knots(_lens), size: 150)),
                ),
            ]),
          ),
        ),
      ),
    );
  }

  Offset _rel(Offset local) {
    final box = _rugKey.currentContext?.findRenderObject() as RenderBox?;
    if (box == null) return _lens;
    return Offset((local.dx / box.size.width).clamp(.05, .95), (local.dy / box.size.height).clamp(.04, .96));
  }

  void _moveLens(Offset local, {bool show = false}) => setState(() {
        if (show) _lensOn = true;
        _lens = _rel(local);
      });

  Widget _thumbs() => SizedBox(
        height: 76,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
          itemCount: _images.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (_, i) {
            final on = i == _img;
            return GestureDetector(
              onTap: () {
                if (on) return;
                setState(() => (_img = i, _px = null, _lens = const Offset(.5, .5)));
                _ur.value = .35;
                _loadPixels();
              },
              child: Container(
                width: 64,
                decoration: BoxDecoration(border: Border.all(color: on ? C.lapis : C.rim, width: on ? 2.5 : 1), borderRadius: BorderRadius.circular(3)),
                child: NetImage(_images[i]['thumb'] as String? ?? ''),
              ),
            );
          },
        ),
      );

  Widget _tools(Json p) {
    Widget b(IconData ic, String t, VoidCallback on, {bool active = false}) => Padding(
          padding: const EdgeInsetsDirectional.only(end: 8, bottom: 8),
          child: OutlinedButton.icon(
            style: OutlinedButton.styleFrom(
              minimumSize: const Size(10, 44),
              backgroundColor: active ? C.lapis : C.soft,
              foregroundColor: active ? C.cream : C.ink,
              side: BorderSide(color: active ? C.lapis : C.rim),
              padding: const EdgeInsets.symmetric(horizontal: 12),
            ),
            onPressed: on,
            icon: Icon(ic, size: 20),
            label: Text(t),
          ),
        );
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: Wrap(children: [
        b(Icons.search_rounded, 'ذره‌بین', () => setState(() => _lensOn = !_lensOn), active: _lensOn),
        b(Icons.straighten_rounded, 'در اتاق من', () async {
          final i = await Navigator.pushNamed(context, '/plan', arguments: {'product': p, 'size': _sel});
          if (i is int && mounted && i < _sizes.length && _sizes[i]['available'] == true) {
            setState(() => (_sel = i, _qty = _sizes[i]['pair_only'] == true ? 2 : 1));
          }
        }),
        b(Icons.photo_camera_outlined, 'با دوربین', () => Navigator.pushNamed(context, '/room', arguments: {'product': p, 'size': _sel})),
        b(Icons.replay_rounded, 'باز کردن دوباره', () => _ur.forward(from: 0)),
      ]),
    );
  }

  /// مقایسهٔ تراکم: دایرهٔ گره‌ها از وسط فرش (یا جای ذره‌بین) با شانهٔ انتخاب‌شده
  Widget _knotBox(Json p) {
    final own = p['reeds'] as String? ?? '';
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 0),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: C.soft, border: Border.all(color: C.rim), borderRadius: BorderRadius.circular(3)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: Loupe(painter: _knots(_lens), size: 96, handle: false),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('گره‌ها زیر ذره‌بین', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5)),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final s in const [700, 1000, 1200, 1500])
                ChoiceChip(
                  label: Text(faDigits(s)),
                  selected: _sh == s,
                  showCheckmark: false,
                  selectedColor: C.lapis,
                  backgroundColor: Colors.white,
                  labelStyle: TextStyle(color: _sh == s ? C.cream : C.ink, fontWeight: FontWeight.w700),
                  side: const BorderSide(color: C.rim),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(3)),
                  onSelected: (_) => setState(() => _sh = s),
                ),
            ]),
            const SizedBox(height: 8),
            Text(knotSentence(_sh, own), style: const TextStyle(fontSize: 13, color: C.ink2, height: 1.9)),
            const Text('روی عکس فرش انگشت را نگه دارید و بکشید.', style: TextStyle(fontSize: 12, color: C.muted)),
          ]),
        ),
      ]),
    );
  }

  Widget _info(Json p) {
    final reeds = p['reeds'] as String? ?? '';
    final title = p['title'] as String;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(faDigits(rugName(title)), style: nast(42, height: 1.9)),
        Text(faDigits(title), style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: C.ink2, height: 1.7)),
        const SizedBox(height: 8),
        Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
          if (reeds.isNotEmpty) HouseChip('${faDigits(reeds)} شانه'),
          if (title.contains('برجسته')) const HouseChip('برجسته', color: C.ink2),
          if (asInt(p['rating_count']) > 0) HouseChip('★ ${faDigits(p['rating'])} · ${sep(asInt(p['rating_count']))} نظر', color: C.brickDark),
          if ((p['sku'] as String? ?? '').isNotEmpty) HouseChip('کد ${faDigits(p['sku'])}', color: C.muted),
        ]),
      ]),
    );
  }

  Widget _head(String t) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 26, 16, 8),
        child: Text(t, style: nast(30, color: C.brickDark, height: 1.8)),
      );

  Widget _colors(Json p) {
    final cs = (p['colors'] as List).cast<Json>();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Text('رنگ‌های دیگر همین نقشه', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14)),
      ),
      SizedBox(
        height: 92,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: cs.length,
          separatorBuilder: (_, _) => const SizedBox(width: 10),
          itemBuilder: (_, i) {
            final c = cs[i], on = c['current'] == true;
            return GestureDetector(
              onTap: on ? null : () => Navigator.pushReplacementNamed(context, '/product', arguments: c['id']),
              child: SizedBox(
                width: 64,
                child: Column(children: [
                  Container(
                    width: 60,
                    height: 60,
                    padding: const EdgeInsets.all(2),
                    decoration: BoxDecoration(
                        color: Colors.white, borderRadius: BorderRadius.circular(3), border: Border.all(color: on ? C.lapis : C.rim, width: on ? 2.5 : 1)),
                    child: NetImage(c['image'] as String? ?? ''),
                  ),
                  const SizedBox(height: 4),
                  Text(c['color'] as String? ?? '', maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(fontSize: 11.5, fontWeight: on ? FontWeight.w900 : FontWeight.w500, color: on ? C.lapis : C.ink)),
                ]),
              ),
            );
          },
        ),
      ),
    ]);
  }

  Widget _sizesGrid() {
    final sizes = _sizes;
    if (sizes.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 18, 16, 0),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text.rich(TextSpan(children: [
          TextSpan(text: 'سایز ', style: TextStyle(fontWeight: FontWeight.w800, fontSize: 15)),
          TextSpan(text: 'ابعاد به متر', style: TextStyle(color: C.muted, fontSize: 12.5)),
        ])),
        const SizedBox(height: 8),
        LayoutBuilder(builder: (_, bc) {
          final cw = (bc.maxWidth - 8) / 2;
          return Wrap(spacing: 8, runSpacing: 8, children: [
            for (var i = 0; i < sizes.length; i++) SizedBox(width: cw, child: _sizeTile(sizes[i], i)),
          ]);
        }),
      ]),
    );
  }

  Widget _sizeTile(Json s, int i) {
    final on = i == _sel, ok = s['available'] == true;
    final label = (s['label'] as String).replaceAll(RegExp(r'\s*\([^()]*\)\s*$'), '');
    final dims = s['dimensions'] as String? ?? '';
    return Material(
      color: on ? C.lapis : (ok ? C.soft : Colors.transparent),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4), side: BorderSide(color: on ? C.lapis : C.rim)),
      child: InkWell(
        borderRadius: BorderRadius.circular(4),
        onTap: ok ? () => setState(() => (_sel = i, _qty = s['pair_only'] == true ? 2 : 1)) : null,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(
                child: Text(faDigits(label), maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontWeight: FontWeight.w800, fontSize: 14, color: on ? C.cream : (ok ? C.ink : C.muted))),
              ),
              if (s['pair_only'] == true)
                Text('جفت', style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: on ? C.saffron : C.brickDark)),
            ]),
            if (dims.isNotEmpty)
              Text('${faDigits(dims)} متر', style: TextStyle(fontSize: 12, color: on ? const Color(0xFFCFD8E8) : C.ink2)),
            const SizedBox(height: 2),
            ok
                ? Text.rich(TextSpan(children: [
                    if (s['on_sale'] == true && asInt(s['regular_price']) > asInt(s['price']))
                      TextSpan(
                          text: '${sep(asInt(s['regular_price']))} ',
                          style: TextStyle(fontSize: 11, decoration: TextDecoration.lineThrough, color: on ? const Color(0xFFCFD8E8) : C.muted)),
                    TextSpan(text: sep(asInt(s['price'])), style: TextStyle(fontWeight: FontWeight.w900, fontSize: 13.5, color: on ? Colors.white : C.ink)),
                  ]))
                : const Text('ناموجود', style: TextStyle(color: C.muted, fontSize: 12.5)),
          ]),
        ),
      ),
    );
  }

  Widget _specs(Json p) {
    final specs = (p['specs'] as List).cast<Json>();
    if (specs.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _head('شناسنامهٔ فرش'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(children: [
          for (final s in specs)
            Container(
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: const BoxDecoration(border: Border(bottom: BorderSide(color: C.line))),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 120, child: Text(s['name'] as String, style: const TextStyle(color: C.ink2))),
                Expanded(child: Text(faDigits(s['value']), style: const TextStyle(fontWeight: FontWeight.w700))),
              ]),
            ),
        ]),
      ),
    ]);
  }

  Widget _description(Json p) {
    final short = p['short_description'] as String? ?? '', long = p['content_text'] as String? ?? '';
    if (short.isEmpty && long.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _head('دربارهٔ این فرش'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (short.isNotEmpty) Text(short, style: const TextStyle(height: 2)),
          if (long.isNotEmpty) ...[
            const SizedBox(height: 6),
            AnimatedCrossFade(
              duration: const Duration(milliseconds: 250),
              crossFadeState: _more ? CrossFadeState.showSecond : CrossFadeState.showFirst,
              firstChild: Text(long, maxLines: 5, overflow: TextOverflow.ellipsis, style: const TextStyle(color: C.ink2, height: 2)),
              secondChild: Text(long, style: const TextStyle(color: C.ink2, height: 2)),
            ),
            TextButton(onPressed: () => setState(() => _more = !_more), child: Text(_more ? 'بستن' : 'بیشتر بخوانید')),
          ],
        ]),
      ),
    ]);
  }

  Widget _reviews(Json p) {
    final rs = (p['reviews'] as List).cast<Json>();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: _head('نظر خریداران')),
        Padding(
          padding: const EdgeInsets.only(left: 12, top: 18),
          child: TextButton(onPressed: () => showReviewSheet(context, p['id'] as int), child: const Text('نظر بدهید')),
        ),
      ]),
      if (rs.isEmpty)
        const Padding(padding: EdgeInsets.symmetric(horizontal: 16), child: Text('هنوز نظری ثبت نشده؛ اولین نفر باشید.', style: TextStyle(color: C.muted)))
      else
        SizedBox(
          height: 160,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            itemCount: rs.length,
            separatorBuilder: (_, _) => const SizedBox(width: 10),
            itemBuilder: (_, i) => Container(
              width: 264,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(color: C.soft, border: Border.all(color: C.rim), borderRadius: BorderRadius.circular(3)),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Expanded(child: Text(rs[i]['author'] as String, style: const TextStyle(fontWeight: FontWeight.w800))),
                  for (var k = 0; k < (rs[i]['rating'] as int); k++) const Icon(Icons.star_rounded, size: 16, color: C.saffron),
                ]),
                if (rs[i]['verified'] == true)
                  const Text('خریدار این فرش', style: TextStyle(fontSize: 11, color: C.tealDark, fontWeight: FontWeight.w800)),
                const SizedBox(height: 4),
                Expanded(child: Text(rs[i]['text'] as String, maxLines: 4, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13))),
              ]),
            ),
          ),
        ),
    ]);
  }

  Widget _faqs(Json p) {
    final fs = (p['faqs'] as List).cast<Json>();
    if (fs.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _head('پرسش‌های پرتکرار'),
      for (final f in fs)
        ExpansionTile(
          title: Text(f['q'] as String, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedAlignment: AlignmentDirectional.centerStart,
          children: [Text(f['a'] as String, style: const TextStyle(color: C.ink2, height: 1.9))],
        ),
    ]);
  }

  Widget _buyBar(Json p) {
    final s = _size;
    final purchasable = p['purchasable'] as bool? ?? true;
    return Container(
      decoration: const BoxDecoration(color: C.soft, border: Border(top: BorderSide(color: C.rim))),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
          child: !purchasable || s == null
              ? Row(children: [
                  const Expanded(child: Text('این فرش الان قابل خرید آنلاین نیست.', style: TextStyle(color: C.muted))),
                  FilledButton.icon(
                    style: FilledButton.styleFrom(backgroundColor: C.lapis, minimumSize: const Size(10, 48)),
                    onPressed: () => showContactSheet(context, text: p['url'] as String),
                    icon: const Icon(Icons.chat_rounded, size: 20),
                    label: const Text('پرسیدن از کارشناس'),
                  ),
                ])
              : Row(children: [
                  _stepper(s),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton(
                      onPressed: () => _addToCart(),
                      child: FittedBox(
                        child: Column(children: [
                          const Text('افزودن به سبد'),
                          Text('${sep((s['price'] as int) * _qty)} تومان', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500)),
                        ]),
                      ),
                    ),
                  ),
                ]),
        ),
      ),
    );
  }

  Widget _stepper(Json s) {
    final step = s['pair_only'] == true ? 2 : 1;
    return Container(
      height: 54,
      decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.rim), borderRadius: BorderRadius.circular(4)),
      child: Row(children: [
        IconButton(tooltip: 'یکی بیشتر', onPressed: _qty + step <= 20 ? () => setState(() => _qty += step) : null, icon: const Icon(Icons.add_rounded)),
        Text(faDigits(_qty), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
        IconButton(tooltip: 'یکی کمتر', onPressed: _qty - step >= step ? () => setState(() => _qty -= step) : null, icon: const Icon(Icons.remove_rounded)),
      ]),
    );
  }
}
