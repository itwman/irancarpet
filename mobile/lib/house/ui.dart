import 'dart:math';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/theme.dart';

/// اجزای مشترک ظاهر «فروشگاه تخصصی فرش» اپ فرشستان:
/// نشان ستارهٔ هشت‌پر، سرتیتر بخش‌ها، نشان‌ها (badge)، عکس فرش با برش کادر و «صحنهٔ عکس استودیویی».

/// «فرش طرح زرین سیلور 700 شانه برجسته تمام آکریلیک» ← «زرین سیلور» (همان rug_name سایت)
String rugName(String title) {
  var t = title.replaceAll(RegExp(r'\s+'), ' ').trim();
  final m = RegExp(r'(?:نقشه|طرح)\s+(.+)$').firstMatch(t);
  var rest = m != null ? m.group(1)! : t.replaceFirst(RegExp(r'^(?:تابلو\s*فرش|فرش)\s+'), '');
  rest = rest.split(RegExp(r'\s*[\d۰-۹]{3,4}\s*شانه|\s+(?:سایز|کد|تمام|بافت)\s|\s*[-–(]')).first.trim();
  rest = rest.replaceAll(RegExp(r'\s+زمینه\s+'), ' ');
  final w = rest.split(' ').where((x) => x.isNotEmpty).toList();
  return w.isEmpty ? t : w.take(4).join(' ');
}

/// نشان فرشستان: دو مربع لاجوردی چرخیده (ستارهٔ هشت‌پر)، ستارهٔ خطی سفید و مرکز طلایی (از SVG پروتوتایپ)
class FarshestanMark extends StatelessWidget {
  const FarshestanMark({super.key, this.size = 40});
  final double size;
  @override
  Widget build(BuildContext context) =>
      Semantics(excludeSemantics: true, child: CustomPaint(size: Size.square(size), painter: const _MarkPainter()));
}

class _MarkPainter extends CustomPainter {
  const _MarkPainter();
  static const _pts = [
    [24.0, 12.5], [27.0, 18.7], [33.6, 16.8], [31.7, 23.4], [37.9, 26.4], [31.7, 29.4], [33.6, 36.0], [27.0, 34.1],
    [24.0, 40.3], [21.0, 34.1], [14.4, 36.0], [16.3, 29.4], [10.1, 26.0], [16.3, 23.0], [14.4, 16.4], [21.0, 18.3],
  ];
  @override
  void paint(Canvas c, Size s) {
    c.save();
    c.scale(s.width / 48);
    final sq = RRect.fromRectAndRadius(const Rect.fromLTWH(9, 9, 30, 30), const Radius.circular(3));
    final blue = Paint()..color = C.brand;
    c.drawRRect(sq, blue);
    c.save();
    c.translate(24, 24);
    c.rotate(pi / 4);
    c.translate(-24, -24);
    c.drawRRect(sq, blue);
    c.restore();
    final star = Path()..moveTo(_pts[0][0], _pts[0][1] - 2);
    for (final p in _pts.skip(1)) {
      star.lineTo(p[0], p[1] - 2);
    }
    c.drawPath(
        star..close(),
        Paint()
          ..color = Colors.white
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6
          ..strokeJoin = StrokeJoin.round);
    c.drawCircle(const Offset(24, 24), 4.2, Paint()..color = C.gold);
    c.restore();
  }

  @override
  bool shouldRepaint(_MarkPainter o) => false;
}

/// نشان + نام «فرشستان» + شعار کوتاه
class FarshestanLogo extends StatelessWidget {
  const FarshestanLogo({super.key, this.mark = 34, this.tagline = true, this.light = false});
  final double mark;
  final bool tagline, light;
  @override
  Widget build(BuildContext context) => Semantics(
        label: kAppName,
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          FarshestanMark(size: mark),
          SizedBox(width: mark * .25),
          Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(kAppName,
                style: TextStyle(fontSize: mark * .6, fontWeight: FontWeight.w900, color: light ? Colors.white : C.brand, height: 1.2)),
            if (tagline)
              Text('فرش ماشینی، مستقیم از کارخانه',
                  style: TextStyle(fontSize: max(10.5, mark * .31), color: light ? const Color(0xFFC9D4EE) : C.muted, height: 1.3)),
          ]),
        ]),
      );
}

/// ستارهٔ هشت‌پر طلایی کوچک کنار سرتیتر بخش‌ها
class Star8 extends StatelessWidget {
  const Star8({super.key, this.size = 16, this.color = C.gold});
  final double size;
  final Color color;
  @override
  Widget build(BuildContext context) => SizedBox.square(
        dimension: size,
        child: Stack(alignment: Alignment.center, children: [
          for (final a in [0.0, pi / 4])
            Transform.rotate(angle: a, child: Container(width: size * .7, height: size * .7, color: color)),
        ]),
      );
}

/// سرتیتر بخش: ستارهٔ طلایی + تیتر + توضیح کوتاه + پیوند «مشاهدهٔ همه»
class SecHead extends StatelessWidget {
  const SecHead(this.title, {super.key, this.subtitle, this.action, this.onAction, this.light = false, this.padding});
  final String title;
  final String? subtitle, action;
  final VoidCallback? onAction;
  final bool light;
  final EdgeInsets? padding;
  @override
  Widget build(BuildContext context) => Padding(
        padding: padding ?? const EdgeInsets.fromLTRB(16, 28, 8, 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                const Star8(size: 15),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(title,
                      style: TextStyle(fontSize: 17.5, fontWeight: FontWeight.w800, height: 1.4, color: light ? Colors.white : C.ink)),
                ),
              ]),
              if (subtitle != null && subtitle!.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(subtitle!, style: TextStyle(fontSize: 12.5, color: light ? const Color(0xFFC9D4EE) : C.muted, height: 1.6)),
                ),
            ]),
          ),
          if (action != null)
            TextButton(
              style: TextButton.styleFrom(
                  foregroundColor: light ? Colors.white : C.brand, minimumSize: const Size(44, 40), padding: const EdgeInsets.symmetric(horizontal: 8)),
              onPressed: onAction,
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(action!, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
                const Icon(Icons.chevron_left_rounded, size: 20),
              ]),
            ),
        ]),
      );
}

enum BdgKind { brand, gold, white, muted }

/// نشان کوچک روی کارت‌ها (جدید، تخفیف، ناموجود…)
class Bdg extends StatelessWidget {
  const Bdg(this.text, {super.key, this.kind = BdgKind.white, this.icon});
  final String text;
  final BdgKind kind;
  final IconData? icon;
  @override
  Widget build(BuildContext context) {
    final (bg, fg) = switch (kind) {
      BdgKind.brand => (C.brand, Colors.white),
      BdgKind.gold => (C.gold100, C.goldInk),
      BdgKind.white => (Colors.white, C.brand700),
      BdgKind.muted => (const Color(0xF2FFFFFF), C.muted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 1),
      decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(6), boxShadow: kind == BdgKind.white ? kShadow1 : null),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        if (icon != null) ...[Icon(icon, size: 13, color: fg), const SizedBox(width: 3)],
        Text(text, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: fg, height: 1.7)),
      ]),
    );
  }
}

/// درصد تخفیف روی زمینهٔ طلایی (متن تیره)
class OffPill extends StatelessWidget {
  const OffPill(this.percent, {super.key, this.size = 12});
  final int percent;
  final double size;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 7),
        decoration: BoxDecoration(color: C.gold, borderRadius: BorderRadius.circular(12)),
        child: Text('${_fa(percent)}٪', style: TextStyle(color: C.goldInk, fontSize: size, fontWeight: FontWeight.w900, height: 1.65)),
      );
}

String _fa(Object s) => s.toString().split('').map((c) => int.tryParse(c) == null ? c : '۰۱۲۳۴۵۶۷۸۹'[int.parse(c)]).join();

/// کادر خود فرش در عکس محصول: [x, y, w, h, ar] به درصد (از API)؛ بیرون کادر (حاشیهٔ سفید، لوگو) دیده نمی‌شود
class RugCrop {
  const RugCrop(this.x, this.y, this.w, this.h, this.ar);
  final double x, y, w, h, ar;
  static const full = RugCrop(0, 0, 100, 100, .6667);
  static RugCrop of(Object? v) {
    if (v is List && v.length >= 5) {
      double d(int i) => (v[i] as num).toDouble();
      return RugCrop(d(0), d(1), d(2), d(3), d(4) > 0 ? d(4) : .6667);
    }
    return full;
  }

  bool get cropped => w < 99.5 || h < 99.5;
}

/// عکس فرش با برش کادر فرش؛ اندازهٔ ویجت را والد تعیین می‌کند (معمولاً AspectRatio(crop.ar))
class RugImage extends StatelessWidget {
  const RugImage(this.url, {super.key, this.crop = RugCrop.full, this.seed = 7});
  final String url;
  final RugCrop crop;
  final int seed;

  @override
  Widget build(BuildContext context) {
    if (url.isEmpty) return RugPlaceholder(seed: seed);
    return LayoutBuilder(builder: (_, bc) {
      final w = bc.maxWidth, h = bc.maxHeight;
      final img = CachedNetworkImage(
        imageUrl: url,
        fit: BoxFit.fill,
        fadeInDuration: const Duration(milliseconds: 200),
        placeholder: (_, _) => RugPlaceholder(seed: seed),
        errorWidget: (_, _, _) => RugPlaceholder(seed: seed),
      );
      if (!crop.cropped || !w.isFinite || !h.isFinite) return SizedBox(width: w, height: h, child: img);
      return ClipRect(
        child: OverflowBox(
          alignment: Alignment.topLeft,
          minWidth: 0,
          minHeight: 0,
          maxWidth: double.infinity,
          maxHeight: double.infinity,
          child: Transform.translate(
            offset: Offset(-w * crop.x / crop.w, -h * crop.y / crop.h),
            child: SizedBox(width: w * 100 / crop.w, height: h * 100 / crop.h, child: img),
          ),
        ),
      );
    });
  }
}

/// جای خالی عکس: مستطیل خاکستری روشن با ترنج کم‌رنگ (بی‌شبکه، فوری)
class RugPlaceholder extends StatelessWidget {
  const RugPlaceholder({super.key, this.seed = 7});
  final int seed;
  @override
  Widget build(BuildContext context) => CustomPaint(painter: _PhPainter(), child: const SizedBox.expand());
}

class _PhPainter extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0xFFE6EAF1));
    final b = s.shortestSide * .08;
    c.drawRect(
        Rect.fromLTRB(b, b, s.width - b, s.height - b),
        Paint()
          ..color = const Color(0xFFD5DCE7)
          ..style = PaintingStyle.stroke
          ..strokeWidth = max(1.0, b * .35));
    final cx = s.width / 2, cy = s.height / 2, rw = s.width * .2, rh = s.height * .15;
    c.drawPath(Path()..moveTo(cx, cy - rh)..lineTo(cx + rw, cy)..lineTo(cx, cy + rh)..lineTo(cx - rw, cy)..close(),
        Paint()..color = const Color(0xFFD5DCE7));
  }

  @override
  bool shouldRepaint(_PhPainter o) => false;
}

/// «عکس استودیویی»: فرش وسط زمینهٔ روشن خنثی با سایهٔ نرم (کارت‌ها، دسته‌ها، گالری)
class RugStage extends StatelessWidget {
  const RugStage({super.key, required this.url, this.crop = RugCrop.full, this.seed = 7, this.fill = .84, this.dim = false, this.heroTag});
  final String url;
  final RugCrop crop;
  final int seed;

  /// بلندی فرش نسبت به بلندی کادر
  final double fill;

  /// فرش ناموجود: خاکستری و کم‌رنگ
  final bool dim;
  final Object? heroTag;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: const BoxDecoration(
        gradient: RadialGradient(center: Alignment(0, -.1), radius: .85, colors: [Colors.white, Color(0xFFEEF1F5)]),
      ),
      child: LayoutBuilder(builder: (_, bc) {
        var h = bc.maxHeight * fill, w = h * crop.ar;
        if (w > bc.maxWidth * .9) {
          w = bc.maxWidth * .9;
          h = w / crop.ar;
        }
        Widget rug = SizedBox(width: w, height: h, child: RugImage(url, crop: crop, seed: seed));
        if (dim) {
          rug = Opacity(
              opacity: .55,
              child: ColorFiltered(
                  colorFilter: const ColorFilter.matrix([.33, .59, .11, 0, 0, .33, .59, .11, 0, 0, .33, .59, .11, 0, 0, 0, 0, 0, 1, 0]),
                  child: rug));
        }
        if (heroTag != null) rug = Hero(tag: heroTag!, child: rug);
        return Center(
          child: DecoratedBox(
            decoration: const BoxDecoration(boxShadow: [
              BoxShadow(color: Color(0x2E141D33), blurRadius: 12, offset: Offset(0, 9)),
              BoxShadow(color: Color(0x1F141D33), blurRadius: 2, offset: Offset(0, 1)),
            ]),
            child: rug,
          ),
        );
      }),
    );
  }
}

/// تکهٔ گرد از وسط فرش (دسته‌ها و رنگ‌ها)
class RugDisc extends StatelessWidget {
  const RugDisc({super.key, required this.url, this.crop = RugCrop.full, this.seed = 7, this.size = 76, this.zoom = 1.5, this.label});
  final String url;
  final RugCrop crop;
  final int seed;
  final double size, zoom;
  final String? label;
  @override
  Widget build(BuildContext context) {
    final w = size * zoom, h = w / crop.ar;
    return Container(
      width: size,
      height: size,
      decoration: const BoxDecoration(shape: BoxShape.circle, color: C.soft),
      clipBehavior: Clip.antiAlias,
      foregroundDecoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: const Color(0x0F000000))),
      child: Stack(fit: StackFit.expand, children: [
        OverflowBox(maxWidth: w, maxHeight: h, child: SizedBox(width: w, height: h, child: RugImage(url, crop: crop, seed: seed))),
        if (label != null) ...[
          const DecoratedBox(
            decoration: BoxDecoration(
                gradient: LinearGradient(
                    begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0x00000000), Color(0x00000000), Color(0x8C0B1C42)])),
          ),
          Positioned(
            bottom: size * .1,
            left: 0,
            right: 0,
            child: Text(label!,
                textAlign: TextAlign.center,
                style: TextStyle(
                    color: Colors.white, fontWeight: FontWeight.w900, fontSize: size * .17, shadows: const [Shadow(blurRadius: 3, color: Colors.black45)])),
          ),
        ],
      ]),
    );
  }
}

/// کادر سفید با حاشیهٔ نازک و سایهٔ نرم
BoxDecoration boxDeco({double r = 16, Color color = Colors.white, Color border = C.line}) =>
    BoxDecoration(color: color, borderRadius: BorderRadius.circular(r), border: Border.all(color: border), boxShadow: kShadow1);

/// خواندن عدد از JSON
int asInt(Object? v) => v is num ? v.toInt() : int.tryParse('$v') ?? 0;
Json asMap(Object? v) => v is Map ? v.cast<String, dynamic>() : <String, dynamic>{};
List<Json> asList(Object? v) => v is List ? v.whereType<Map>().map((e) => e.cast<String, dynamic>()).toList() : <Json>[];
