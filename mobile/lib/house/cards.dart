import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'ui.dart';

/// بلندی بخش متنی کارت (زیر عکس مربعی)؛ شبکه‌ها و ردیف‌ها از همین حساب می‌کنند
const double kCardBody = 142;
const double kOfferBody = 176;

/// «۷۰۰ شانه · برجسته» از روی داده‌های کارت (بافت فقط وقتی در عنوان آمده)
String cardMeta(Json p) {
  final reeds = p['reeds'] as String? ?? '';
  final title = p['title'] as String? ?? '';
  return [
    if (reeds.isNotEmpty) '${faDigits(reeds)} شانه',
    if (title.contains('برجسته')) 'برجسته',
  ].join(' · ');
}

/// کارت محصول فرشستان: عکس مربعی استودیویی، تیتر دوخطی، شانه/بافت، امتیاز (فقط اگر دیدگاه واقعی هست) و قیمت
class ShopCard extends StatelessWidget {
  const ShopCard(this.p, {super.key, this.width, this.match, this.badge});
  final Json p;
  final double? width;

  /// برچسب «چرا این فرش؟» (فرش‌یاب)
  final String? match;

  /// نشان اختیاری بالای عکس، مثل «جدید»
  final String? badge;

  @override
  Widget build(BuildContext context) {
    final id = asInt(p['id']);
    final inStock = p['in_stock'] as bool? ?? true;
    final title = p['title'] as String? ?? '';
    final price = asInt(p['price']);
    final rc = asInt(p['rating_count']);
    final meta = cardMeta(p);
    return SizedBox(
      width: width,
      child: Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: const BorderSide(color: C.line)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => Navigator.pushNamed(context, '/product', arguments: id),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            AspectRatio(
              aspectRatio: 1,
              child: Stack(fit: StackFit.expand, children: [
                RugStage(
                    url: p['image'] as String? ?? '', crop: RugCrop.of(p['crop']), seed: id, dim: !inStock, heroTag: 'p$id-${p['image']}'),
                PositionedDirectional(
                  top: 8,
                  start: 8,
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    if (badge != null) Bdg(badge!, kind: BdgKind.gold),
                    if (!inStock) const Bdg('ناموجود', kind: BdgKind.muted),
                  ]),
                ),
                PositionedDirectional(top: 4, end: 4, child: WishButton(id)),
                if (match != null && match!.isNotEmpty)
                  PositionedDirectional(
                    bottom: 8,
                    start: 8,
                    end: 8,
                    child: Align(alignment: AlignmentDirectional.centerStart, child: Bdg(match!, icon: Icons.check_circle_rounded)),
                  ),
              ]),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  SizedBox(
                    height: 18,
                    child: Text(meta, maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: C.muted, height: 1.5)),
                  ),
                  const SizedBox(height: 4),
                  Text(faDigits(title),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, height: 1.65, color: C.ink)),
                  if (rc > 0) ...[const SizedBox(height: 2), RatingLine(p['rating'], rc)],
                  const Spacer(),
                  Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: CardPrice(price: price, from: p['price_is_from'] == true, inStock: inStock),
                  ),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

/// ★ ۴٫۶ (۲۱۴)
class RatingLine extends StatelessWidget {
  const RatingLine(this.avg, this.count, {super.key, this.size = 12.5});
  final Object? avg;
  final int count;
  final double size;
  @override
  Widget build(BuildContext context) {
    final a = avg is num ? (avg as num).toDouble() : double.tryParse('$avg') ?? 0;
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(Icons.star_rounded, size: size + 3, color: C.gold),
      const SizedBox(width: 2),
      Text(faDigits(a.toStringAsFixed(1)).replaceAll('.', '٫'), style: TextStyle(fontSize: size, fontWeight: FontWeight.w700, color: C.ink2)),
      Text(' (${faDigits(count)})', style: TextStyle(fontSize: size - .5, color: C.muted)),
    ]);
  }
}

/// قیمت پایین کارت: «از ۱۸٬۷۶۰٬۰۰۰ تومان»؛ با تخفیف واقعی، قیمت خط‌خورده و درصد
class CardPrice extends StatelessWidget {
  const CardPrice({super.key, required this.price, this.from = false, this.strike, this.percent, this.inStock = true, this.size = 15.5});
  final int price;
  final bool from, inStock;
  final int? strike, percent;
  final double size;
  @override
  Widget build(BuildContext context) {
    if (!inStock && price == 0) return const Text('ناموجود', style: TextStyle(color: C.faint, fontWeight: FontWeight.w800, fontSize: 14));
    if (price == 0) return const Text('استعلام قیمت', style: TextStyle(color: C.muted, fontWeight: FontWeight.w700, fontSize: 13));
    final off = (percent ?? 0) > 0 ? percent! : (strike != null && strike! > price ? ((strike! - price) * 100 / strike!).round() : 0);
    return Column(crossAxisAlignment: CrossAxisAlignment.end, mainAxisSize: MainAxisSize.min, children: [
      if (strike != null && strike! > price)
        Row(mainAxisSize: MainAxisSize.min, children: [
          Text(sep(strike!), style: const TextStyle(color: C.faint, fontSize: 12, decoration: TextDecoration.lineThrough, decorationColor: C.faint)),
          if (off > 0) ...[const SizedBox(width: 6), OffPill(off)],
        ]),
      Text.rich(
        TextSpan(children: [
          if (from) const TextSpan(text: 'از ', style: TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w500)),
          TextSpan(text: sep(price), style: TextStyle(fontSize: size, fontWeight: FontWeight.w800, color: inStock ? C.ink : C.faint)),
          const TextSpan(text: ' تومان', style: TextStyle(fontSize: 11.5, color: C.muted, fontWeight: FontWeight.w500)),
        ]),
        maxLines: 1,
      ),
    ]);
  }
}

/// دکمهٔ گرد علاقه‌مندی روی عکس
class WishButton extends StatelessWidget {
  const WishButton(this.id, {super.key, this.size = 36});
  final int id;
  final double size;
  @override
  Widget build(BuildContext context) {
    final wish = context.watch<Wishlist>();
    final on = wish.has(id);
    return IconButton(
      tooltip: on ? 'برداشتن از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها',
      onPressed: () => wish.toggle(id),
      style: IconButton.styleFrom(
        backgroundColor: const Color(0xEBFFFFFF),
        fixedSize: Size.square(size),
        minimumSize: Size.square(size),
        padding: EdgeInsets.zero,
      ),
      icon: Icon(on ? Icons.favorite_rounded : Icons.favorite_border_rounded, size: size * .55, color: on ? C.heart : C.muted),
    );
  }
}

/// کارت «پیشنهاد ویژه»: قیمت فرصت، قیمت خط‌خورده و درصد واقعی، و زمان باقی‌مانده فقط اگر API پایان را داده
class OfferCard extends StatelessWidget {
  const OfferCard(this.o, {super.key, this.width = 168});
  final Json o;
  final double width;
  @override
  Widget build(BuildContext context) {
    final pid = asInt(o['product_id']);
    final remaining = asInt(o['remaining']);
    return SizedBox(
      width: width,
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => Navigator.pushNamed(context, '/product', arguments: pid),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            AspectRatio(
              aspectRatio: 1,
              child: Stack(fit: StackFit.expand, children: [
                RugStage(url: o['image'] as String? ?? '', seed: pid),
                PositionedDirectional(top: 4, end: 4, child: WishButton(pid)),
              ]),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(faDigits(o['size'] ?? ''), maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, color: C.muted)),
                  const SizedBox(height: 4),
                  Text(faDigits(o['title'] ?? ''),
                      maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w600, height: 1.65)),
                  const Spacer(),
                  Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: CardPrice(price: asInt(o['price']), strike: asInt(o['regular_price']), percent: asInt(o['percent'])),
                  ),
                  const SizedBox(height: 6),
                  Row(children: [
                    const Icon(Icons.schedule_rounded, size: 14, color: C.brand),
                    const SizedBox(width: 4),
                    Expanded(
                      child: o['ends_at'] != null
                          ? Countdown(DateTime.tryParse(o['ends_at'] as String), compact: true)
                          : Text(remaining <= 1 ? 'آخرین تخته' : '${faDigits(remaining)} تخته باقی مانده',
                              style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: C.brand700)),
                    ),
                  ]),
                ]),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}

/// شمارش معکوس واقعی تا پایان یک فرصت (متنی یا خانه‌های سفید)
class Countdown extends StatefulWidget {
  const Countdown(this.end, {super.key, this.compact = false});
  final DateTime? end;
  final bool compact;
  @override
  State<Countdown> createState() => _CountdownState();
}

class _CountdownState extends State<Countdown> {
  Timer? _t;
  @override
  void initState() {
    super.initState();
    if (widget.end != null) _t = Timer.periodic(const Duration(seconds: 1), (_) => mounted ? setState(() {}) : null);
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  String _two(int n) => faDigits(n.toString().padLeft(2, '0'));

  @override
  Widget build(BuildContext context) {
    final end = widget.end;
    if (end == null) return const SizedBox.shrink();
    final left = end.difference(DateTime.now());
    if (left.isNegative) {
      return const Text('این فرصت تمام شد', style: TextStyle(fontSize: 11.5, color: C.muted, fontWeight: FontWeight.w700));
    }
    final d = left.inDays, h = left.inHours % 24, m = left.inMinutes % 60, s = left.inSeconds % 60;
    if (widget.compact) {
      return Text('${d > 0 ? '${faDigits(d)} روز و ' : ''}${_two(h)}:${_two(m)}:${_two(s)} مانده',
          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: C.brand700));
    }
    Widget cell(String t) => Container(
          width: 40,
          height: 40,
          alignment: Alignment.center,
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8)),
          child: Text(t, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 17, color: C.brand800)),
        );
    const sepr = Padding(
      padding: EdgeInsets.symmetric(horizontal: 4),
      child: Text(':', style: TextStyle(color: C.gold300, fontWeight: FontWeight.w900, fontSize: 17)),
    );
    return Semantics(
      label: 'زمان باقی‌مانده',
      child: Directionality(
        textDirection: TextDirection.ltr,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          if (d > 0) ...[cell(faDigits(d)), const Padding(padding: EdgeInsets.symmetric(horizontal: 4), child: Text('روز', style: TextStyle(color: Colors.white, fontSize: 12)))],
          cell(_two(h)), sepr, cell(_two(m)), sepr, cell(_two(s)),
        ]),
      ),
    );
  }
}

/// شبکهٔ دوستونی کارت‌ها: بلندی هر خانه = پهنای عکس مربعی + بخش متنی (با بزرگ‌نمایی متن کاربر)
class HouseGrid extends SliverGridDelegate {
  const HouseGrid({this.textScale = 1, this.body = kCardBody, this.spacing = 12});
  final double textScale, body, spacing;

  @override
  SliverGridLayout getLayout(SliverConstraints constraints) {
    final cols = constraints.crossAxisExtent >= 640 ? 3 : 2;
    final w = (constraints.crossAxisExtent - spacing * (cols - 1)) / cols;
    final h = w + body * textScale.clamp(1.0, 1.6);
    return SliverGridRegularTileLayout(
      crossAxisCount: cols,
      mainAxisStride: h + spacing,
      crossAxisStride: w + spacing,
      childMainAxisExtent: h,
      childCrossAxisExtent: w,
      reverseCrossAxis: axisDirectionIsReversed(constraints.crossAxisDirection),
    );
  }

  @override
  bool shouldRelayout(HouseGrid old) => old.textScale != textScale || old.body != body || old.spacing != spacing;
}

/// ضریب بزرگ‌نمایی متن کاربر برای حساب بلندی کارت‌ها
double textScaleOf(BuildContext context) => MediaQuery.textScalerOf(context).scale(14) / 14;

/// ردیف افقی کارت‌ها با بلندی درست
class CardRail extends StatelessWidget {
  const CardRail({super.key, required this.count, required this.builder, this.width = 164, this.body = kCardBody});
  final int count;
  final Widget Function(BuildContext, int, double width) builder;
  final double width, body;
  @override
  Widget build(BuildContext context) {
    final h = width + body * textScaleOf(context).clamp(1.0, 1.6);
    return SizedBox(
      height: h + 4,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
        itemCount: count,
        separatorBuilder: (_, _) => const SizedBox(width: 12),
        itemBuilder: (c, i) => builder(c, i, width),
      ),
    );
  }
}

/// رنگ نمونهٔ «رنگ زمینه» از روی نام (برای نقطه‌ها و دایره‌های رنگ)
Color? swatchOf(String name) {
  final n = name.replaceAll(RegExp(r'[\s‌]'), '').replaceAll('ي', 'ی');
  const map = {
    'نقره‌ای': Color(0xFFC9C6C0), 'نقرهای': Color(0xFFC9C6C0), 'سرمه‌ای': Color(0xFF1E2A4A), 'سرمهای': Color(0xFF1E2A4A),
    'کرم': Color(0xFFE9DCC2), 'دودی': Color(0xFF5E5B57), 'سیلور': Color(0xFFBCC0C3), 'بژ': Color(0xFFD8C3A0),
    'متالیک': Color(0xFF9AA0A3), 'لاکی': Color(0xFF8E1F22), 'روناسی': Color(0xFFA8452F), 'زغالی': Color(0xFF3B3936),
    'فیلی': Color(0xFF9B948B), 'طوسی': Color(0xFF8E9296), 'آبی': Color(0xFF3C67B0), 'سبز': Color(0xFF3F7D57),
    'مشکی': Color(0xFF1E1E1E), 'سفید': Color(0xFFF6F4EF), 'قرمز': Color(0xFFA92A2A), 'صورتی': Color(0xFFD99AA6),
    'قهوه‌ای': Color(0xFF6B4A33), 'قهوهای': Color(0xFF6B4A33), 'قهوه ای': Color(0xFF6B4A33), 'گردویی': Color(0xFF5C3B26),
    'فیروزه‌ای': Color(0xFF2E9A9A), 'فیروزهای': Color(0xFF2E9A9A), 'یشمی': Color(0xFF2F6B5A), 'زرشکی': Color(0xFF6D1A2A),
    'طلایی': Color(0xFFC99A2E), 'خردلی': Color(0xFFC49A2C), 'استخوانی': Color(0xFFE9E2D0), 'گلبهی': Color(0xFFE8A893),
  };
  for (final e in map.entries) {
    final k = e.key.replaceAll(RegExp(r'[\s‌]'), '');
    if (n.contains(k)) return e.value;
  }
  return null;
}
