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
import '../widgets/knots.dart';

class ProductScreen extends StatefulWidget {
  const ProductScreen({super.key, required this.id});
  final int id;
  @override
  State<ProductScreen> createState() => _ProductScreenState();
}

final _bubble = IconButton.styleFrom(backgroundColor: Colors.white.withValues(alpha: .92), elevation: 2, shadowColor: Colors.black26);

class _ProductScreenState extends State<ProductScreen> {
  Json? _p;
  String? _err;
  int _img = 0, _sel = -1, _qty = 1;
  bool _more = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final p = await Api.i.get('/products/${widget.id}/') as Json;
      final sizes = (p['sizes'] as List).cast<Json>();
      // سایز پیش‌فرض: ۱۲ متری یا اولین سایز موجود
      var sel = sizes.indexWhere((s) => (s['label'] as String).contains('۱۲') && s['available'] == true);
      if (sel < 0) sel = sizes.indexWhere((s) => s['available'] == true);
      if (mounted) {
        setState(() {
          _p = p;
          _sel = sel;
          _qty = sel >= 0 && sizes[sel]['pair_only'] == true ? 2 : 1;
        });
      }
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  List<Json> get _sizes => ((_p?['sizes'] as List?) ?? []).cast<Json>();
  Json? get _size => _sel >= 0 && _sel < _sizes.length ? _sizes[_sel] : null;

  Future<void> _addToCart({bool go = false}) async {
    final p = _p!, s = _size;
    if (s == null) return toast(context, 'اول یک سایز انتخاب کنید.');
    await context.read<Cart>().add(CartItem(
        variation: s['variation_id'] as int, qty: _qty, productId: p['id'] as int, title: p['title'] as String,
        size: s['label'] as String, image: p['image'] as String, price: s['price'] as int, pairOnly: s['pair_only'] as bool));
    if (!mounted) return;
    if (go) {
      Navigator.pushNamed(context, '/cart');
    } else {
      ScaffoldMessenger.of(context)
        ..hideCurrentSnackBar()
        ..showSnackBar(SnackBar(
          duration: const Duration(milliseconds: 2500),
          persist: false,
          content: Text('«${s['label']}» به سبد اضافه شد.'),
          action: SnackBarAction(label: 'دیدن سبد', textColor: C.saffron, onPressed: () => Navigator.pushNamed(context, '/cart')),
        ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    if (p == null) {
      return Scaffold(
          appBar: AppBar(),
          body: _err != null ? StatusView(message: _err!, onRetry: () {
                setState(() => _err = null);
                _load();
              }) : const Loading());
    }
    final images = (p['images'] as List).cast<Json>();
    final w = MediaQuery.sizeOf(context).width;
    final wish = context.watch<Wishlist>();
    final cmp = context.watch<Compare>();
    final id = p['id'] as int;
    return Scaffold(
      body: CustomScrollView(slivers: [
        SliverAppBar(
          pinned: true,
          leading: Padding(
            padding: const EdgeInsets.all(6),
            child: IconButton.filled(
              tooltip: 'بازگشت',
              style: IconButton.styleFrom(
                  backgroundColor: Colors.white.withValues(alpha: .92), foregroundColor: C.ink, elevation: 2, shadowColor: Colors.black26),
              onPressed: () => Navigator.maybePop(context),
              icon: const Icon(Icons.arrow_back_rounded),
            ),
          ),
          expandedHeight: (w * 1.12).clamp(280, 520),
          backgroundColor: Colors.white,
          actionsPadding: const EdgeInsetsDirectional.only(end: 6),
          actionsIconTheme: const IconThemeData(color: C.ink),
          actions: [
            IconButton(
                style: _bubble,
                tooltip: 'اشتراک‌گذاری',
                onPressed: () => SharePlus.instance.share(ShareParams(text: '${p['title']}\n${p['url']}')),
                icon: const Icon(Icons.share_outlined)),
            IconButton(
                style: _bubble,
                tooltip: 'مقایسه',
                onPressed: () {
                  if (!cmp.toggle(id)) return toast(context, 'حداکثر ۳ فرش را می‌شود مقایسه کرد.');
                  if (cmp.has(id)) {
                    ScaffoldMessenger.of(context)
                      ..hideCurrentSnackBar()
                      ..showSnackBar(SnackBar(
                        persist: false,
                        duration: const Duration(milliseconds: 2500),
                        content: Text('به مقایسه اضافه شد (${faDigits(cmp.ids.length)} از ۳).'),
                        action: SnackBarAction(label: 'مقایسه', textColor: C.saffron, onPressed: () => Navigator.pushNamed(context, '/compare'))));
                  }
                },
                icon: Icon(cmp.has(id) ? Icons.compare_rounded : Icons.compare_outlined, color: cmp.has(id) ? C.teal : null)),
            IconButton(
                style: _bubble,
                tooltip: 'علاقه‌مندی',
                onPressed: () => wish.toggle(id),
                icon: Icon(wish.has(id) ? Icons.favorite : Icons.favorite_border, color: wish.has(id) ? C.pink : null)),
          ],
          flexibleSpace: FlexibleSpaceBar(
            background: Stack(fit: StackFit.expand, children: [
              PageView.builder(
                itemCount: images.isEmpty ? 1 : images.length,
                onPageChanged: (i) => setState(() => _img = i),
                itemBuilder: (_, i) => images.isEmpty
                    ? const NetImage('')
                    : GestureDetector(
                        onTap: () => _fullscreen(images, i),
                        child: i == 0
                            ? Hero(tag: 'p$id-${p['image']}', child: NetImage(images[i]['thumb'] as String, fit: BoxFit.contain))
                            : NetImage(images[i]['thumb'] as String, fit: BoxFit.contain),
                      ),
              ),
              if (images.length > 1)
                Positioned(
                  bottom: 14,
                  left: 0,
                  right: 0,
                  child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                    for (var i = 0; i < images.length; i++)
                      AnimatedContainer(
                        duration: const Duration(milliseconds: 220),
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        width: i == _img ? 20 : 7,
                        height: 7,
                        decoration: BoxDecoration(color: i == _img ? C.pink : C.ink.withValues(alpha: .25), borderRadius: BorderRadius.circular(4)),
                      ),
                  ]),
                ),
            ]),
          ),
        ),
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                ReedsBadge(p['reeds'] as String? ?? ''),
                const SizedBox(width: 8),
                if ((p['rating_count'] as int) > 0) ...[
                  const Icon(Icons.star_rounded, color: C.saffron, size: 20),
                  Text(' ${faDigits(p['rating'])}  (${sep(p['rating_count'] as int)} نظر)', style: const TextStyle(color: C.muted, fontSize: 13)),
                ],
              ]),
              const SizedBox(height: 8),
              Text(p['title'] as String, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, height: 1.55)),
              if ((p['sku'] as String? ?? '').isNotEmpty)
                Text('کد کالا: ${faDigits(p['sku'])}', style: const TextStyle(color: C.muted, fontSize: 12.5)),
            ]),
          ),
        ),
        SliverToBoxAdapter(child: _sizesSection(p)),
        if (p['purchasable'] == true && ((_size?['price'] as int?) ?? (p['price'] as int? ?? 0)) > 0)
          SliverToBoxAdapter(
            child: InstallmentTeaser(
                plans: context.watch<AppConfig>().installmentPlans, amount: (_size?['price'] as int?) ?? (p['price'] as int)),
          ),
        SliverToBoxAdapter(child: _roomBanner(p)),
        SliverToBoxAdapter(child: ProductExtras(p)),
        SliverToBoxAdapter(child: _specs(p)),
        SliverToBoxAdapter(child: _description(p)),
        SliverToBoxAdapter(child: _reviews(p)),
        SliverToBoxAdapter(child: _faqs(p)),
        if ((p['related'] as List).isNotEmpty) ...[
          const SliverToBoxAdapter(child: SectionTitle('فرش‌های مشابه')),
          SliverToBoxAdapter(
            child: SizedBox(
              height: 300,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: (p['related'] as List).length,
                separatorBuilder: (_, _) => const SizedBox(width: 12),
                itemBuilder: (_, i) => ProductCard((p['related'] as List)[i] as Json, width: 160),
              ),
            ),
          ),
        ],
        const SliverToBoxAdapter(child: SizedBox(height: 110)),
      ]),
      bottomNavigationBar: _buyBar(p),
    );
  }

  void _fullscreen(List<Json> images, int start) {
    Navigator.push(context, MaterialPageRoute(
      fullscreenDialog: true,
      builder: (_) => Scaffold(
        backgroundColor: Colors.black,
        appBar: AppBar(backgroundColor: Colors.black, foregroundColor: Colors.white),
        body: PageView.builder(
          controller: PageController(initialPage: start),
          itemCount: images.length,
          itemBuilder: (_, i) => InteractiveViewer(maxScale: 5, child: Center(child: NetImage(images[i]['full'] as String, fit: BoxFit.contain))),
        ),
      ),
    ));
  }

  Widget _sizesSection(Json p) {
    final sizes = _sizes;
    if (sizes.isEmpty) return const SizedBox.shrink();
    final maxDim = sizes.fold<double>(1, (a, s) {
      final d = [(s['width'] as num).toDouble(), (s['length'] as num).toDouble(), (s['diameter'] as num).toDouble()].reduce((x, y) => x > y ? x : y);
      return d > a ? d : a;
    });
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionTitle('سایز و قیمت'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(children: [
          for (var i = 0; i < sizes.length; i++) _sizeRow(sizes[i], i, maxDim),
        ]),
      ),
    ]);
  }

  Widget _sizeRow(Json s, int i, double maxDim) {
    final on = i == _sel, ok = s['available'] == true;
    final wd = (s['width'] as num).toDouble(), ln = (s['length'] as num).toDouble(), dia = (s['diameter'] as num).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: on ? C.pinkTint : C.soft,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: on ? C.pink : Colors.transparent, width: 1.6)),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: ok ? () => setState(() => (_sel = i, _qty = s['pair_only'] == true ? 2 : 1)) : null,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            child: Row(children: [
              // طرح کوچک سایز به نسبت واقعی
              SizedBox(
                width: 40,
                height: 40,
                child: Center(
                  child: Container(
                    width: dia > 0 ? 38 * dia / maxDim : (38 * (wd > 0 ? wd : 1) / maxDim).clamp(6, 38),
                    height: dia > 0 ? 38 * dia / maxDim : (38 * (ln > 0 ? ln : 1) / maxDim).clamp(6, 38),
                    decoration: BoxDecoration(
                      color: on ? C.pink : (ok ? C.ink2 : C.line),
                      borderRadius: BorderRadius.circular(s['round'] == true ? 40 : 3),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(s['label'] as String, style: TextStyle(fontWeight: FontWeight.w800, color: ok ? C.ink : C.muted)),
                  Wrap(spacing: 6, children: [
                    if ((s['dimensions'] as String).isNotEmpty) Text('${s['dimensions']} متر', style: const TextStyle(color: C.muted, fontSize: 12)),
                    if (s['pair_only'] == true) const Text('· فقط جفت', style: TextStyle(color: C.tealDark, fontSize: 12, fontWeight: FontWeight.w700)),
                  ]),
                ]),
              ),
              ok
                  ? Price(s['price'] as int, size: 15, strike: s['on_sale'] == true ? s['regular_price'] as int : null)
                  : const Text('ناموجود', style: TextStyle(color: C.muted, fontWeight: FontWeight.w700)),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _roomBanner(Json p) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
        child: Material(
          color: C.tealTint,
          borderRadius: BorderRadius.circular(18),
          child: InkWell(
            borderRadius: BorderRadius.circular(18),
            onTap: () => Navigator.pushNamed(context, '/room', arguments: {'product': p, 'size': _sel}),
            child: const Padding(
              padding: EdgeInsets.all(14),
              child: Row(children: [
                Icon(Icons.view_in_ar_rounded, color: C.tealDark, size: 30),
                SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('این فرش را در اتاقت ببین', style: TextStyle(fontWeight: FontWeight.w900, color: C.tealDark)),
                    Text('با دوربین گوشی یا عکس اتاقت', style: TextStyle(fontSize: 12.5, color: C.ink2)),
                  ]),
                ),
                Icon(Icons.chevron_right, color: C.tealDark),
              ]),
            ),
          ),
        ),
      );

  Widget _specs(Json p) {
    final specs = (p['specs'] as List).cast<Json>();
    if (specs.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionTitle('مشخصات'),
      Container(
        margin: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(16)),
        child: Column(children: [
          for (var i = 0; i < specs.length; i++)
            Container(
              color: i.isEven ? C.soft : Colors.white,
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                SizedBox(width: 120, child: Text(specs[i]['name'] as String, style: const TextStyle(color: C.muted))),
                Expanded(child: Text(specs[i]['value'] as String, style: const TextStyle(fontWeight: FontWeight.w700))),
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
      const SectionTitle('دربارهٔ این فرش'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          if (short.isNotEmpty) Text(short),
          if (long.isNotEmpty) ...[
            const SizedBox(height: 6),
            AnimatedCrossFade(
              duration: const Duration(milliseconds: 250),
              crossFadeState: _more ? CrossFadeState.showSecond : CrossFadeState.showFirst,
              firstChild: Text(long, maxLines: 4, overflow: TextOverflow.ellipsis, style: const TextStyle(color: C.ink2)),
              secondChild: Text(long, style: const TextStyle(color: C.ink2)),
            ),
            TextButton(onPressed: () => setState(() => _more = !_more), child: Text(_more ? 'بستن' : 'بیشتر بخوانید')),
          ],
        ]),
      ),
    ]);
  }

  Widget _reviews(Json p) {
    final rs = (p['reviews'] as List).cast<Json>();
    final hasPhotos = rs.any((r) => ((r['photos'] as List?) ?? []).isNotEmpty);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle('نظر خریدارها',
          subtitle: rs.isEmpty ? 'اولین نظر را شما بنویسید' : '${sep(p['rating_count'] as int)} نظر',
          action: 'نظر بدهید',
          onAction: () => showReviewSheet(context, p['id'] as int)),
      if (rs.isNotEmpty)
      SizedBox(
        height: hasPhotos ? 230 : 150,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: rs.length,
          separatorBuilder: (_, _) => const SizedBox(width: 10),
          itemBuilder: (_, i) => Container(
            width: 260,
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(16)),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Expanded(child: Text(rs[i]['author'] as String, style: const TextStyle(fontWeight: FontWeight.w800))),
                for (var k = 0; k < (rs[i]['rating'] as int); k++) const Icon(Icons.star_rounded, size: 16, color: C.saffron),
              ]),
              if (rs[i]['verified'] == true)
                const Text('خریدار این فرش', style: TextStyle(fontSize: 11, color: C.tealDark, fontWeight: FontWeight.w800)),
              const SizedBox(height: 4),
              Expanded(child: Text(rs[i]['text'] as String, maxLines: 4, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13))),
              if (((rs[i]['photos'] as List?) ?? []).isNotEmpty)
                SizedBox(
                  height: 70,
                  child: ListView(scrollDirection: Axis.horizontal, children: [
                    for (final ph in (rs[i]['photos'] as List).cast<String>())
                      Padding(
                        padding: const EdgeInsetsDirectional.only(end: 6),
                        child: GestureDetector(
                          onTap: () => _fullscreen([{'full': ph}], 0),
                          child: SizedBox(width: 70, child: NetImage(ph, radius: 10)),
                        ),
                      ),
                  ]),
                ),
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
      const SectionTitle('پرسش‌های متداول'),
      for (final f in fs)
        ExpansionTile(
          title: Text(f['q'] as String, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14.5)),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          expandedAlignment: AlignmentDirectional.centerStart,
          children: [Text(f['a'] as String, style: const TextStyle(color: C.ink2))],
        ),
    ]);
  }

  Widget _buyBar(Json p) {
    final s = _size;
    final purchasable = p['purchasable'] as bool? ?? true;
    return Container(
      decoration: const BoxDecoration(color: Colors.white, boxShadow: [BoxShadow(color: Color(0x1A22265A), blurRadius: 20, offset: Offset(0, -6))]),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
          child: !purchasable || s == null
              ? Row(children: [
                  const Expanded(child: Text('این فرش الان قابل خرید آنلاین نیست.', style: TextStyle(color: C.muted))),
                  FilledButton.icon(
                    style: FilledButton.styleFrom(backgroundColor: C.pistachio, foregroundColor: C.ink, minimumSize: const Size(10, 48)),
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
      decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(16)),
      child: Row(children: [
        IconButton(
            tooltip: 'بیشتر',
            onPressed: _qty + step <= 20 ? () => setState(() => _qty += step) : null,
            icon: const Icon(Icons.add_rounded)),
        Text(faDigits(_qty), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
        IconButton(
            tooltip: 'کمتر', onPressed: _qty - step >= step ? () => setState(() => _qty -= step) : null, icon: const Icon(Icons.remove_rounded)),
      ]),
    );
  }
}

/// برای استفادهٔ دیگر صفحه‌ها
class KnotDivider extends StatelessWidget {
  const KnotDivider({super.key});
  @override
  Widget build(BuildContext context) => const Padding(padding: EdgeInsets.symmetric(vertical: 8), child: Center(child: KnotIcon(size: 18)));
}
