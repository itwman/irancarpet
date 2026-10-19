import 'dart:math';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../widgets/knots.dart';

/// اجزای «خانهٔ ایرانی» اپ فرشستان: نستعلیق، کتیبه، گره‌چینی، طاق جناغی، عکس بریدهٔ فرش.

/// متن نستعلیق (ایران‌نستعلیق؛ اگر بار نشد وزیرمتن)
TextStyle nast(double size, {Color color = C.lapis, double height = 1.9, List<Shadow>? shadows}) => TextStyle(
    fontFamily: kNast, fontFamilyFallback: const [kFont], fontSize: size, height: height, color: color, fontWeight: FontWeight.w400,
    shadows: shadows);

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

/// طاق جناغی (مثل archPoly سایت): دو کمان با شعاع ۰٫۶۲ پهنا که در وسط به هم می‌رسند
class ArchClipper extends CustomClipper<Path> {
  const ArchClipper({this.k = .62});
  final double k;
  @override
  Path getClip(Size s) => archPath(s, k: k);
  @override
  bool shouldReclip(ArchClipper old) => old.k != k;
}

Path archPath(Size s, {double k = .62}) {
  final w = s.width, h = s.height, r = k * w;
  var ha = sqrt(r * r - (r - w / 2) * (r - w / 2));
  if (ha > h) ha = h;
  final p = Path()..moveTo(0, h)..lineTo(0, ha);
  // کمان چپ: مرکز (r, ha)
  final a1 = atan2(-ha, w / 2 - r) + 2 * pi;
  for (var i = 1; i <= 16; i++) {
    final a = pi + (a1 - pi) * i / 16;
    p.lineTo(r + r * cos(a), ha + r * sin(a));
  }
  final a2 = atan2(-ha, r - w / 2);
  for (var i = 1; i <= 16; i++) {
    final a = a2 + (0 - a2) * i / 16;
    p.lineTo(w - r + r * cos(a), ha + r * sin(a));
  }
  return p
    ..lineTo(w, h)
    ..close();
}

/// نوار گره‌چینی (ستاره‌های هشت‌پر کاشی) برای لبهٔ سربرگ‌ها و کتیبه‌ها
class GirihBand extends StatelessWidget {
  const GirihBand({super.key, this.height = 8, this.bg = C.lapis, this.fg = C.firoozeLight, this.star = C.cream});
  final double height;
  final Color bg, fg, star;
  @override
  Widget build(BuildContext context) =>
      SizedBox(height: height, width: double.infinity, child: CustomPaint(painter: _GirihPainter(bg, fg, star)));
}

class _GirihPainter extends CustomPainter {
  _GirihPainter(this.bg, this.fg, this.star);
  final Color bg, fg, star;
  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = bg);
    final u = s.height, pf = Paint()..color = fg, ps = Paint()..color = star;
    for (var x = u / 2; x < s.width + u; x += u * 1.5) {
      final cx = x, cy = u / 2;
      // ستارهٔ هشت‌پر: دو مربع چرخیده
      for (final rot in [0.0, pi / 4]) {
        final path = Path();
        for (var i = 0; i < 4; i++) {
          final a = rot + i * pi / 2;
          final px = cx + cos(a) * u * .42, py = cy + sin(a) * u * .42;
          i == 0 ? path.moveTo(px, py) : path.lineTo(px, py);
        }
        c.drawPath(path..close(), pf);
      }
      c.drawCircle(Offset(cx, cy), u * .14, ps);
      c.drawRect(Rect.fromCenter(center: Offset(cx + u * .75, cy), width: u * .16, height: u * .16), ps);
    }
  }

  @override
  bool shouldRepaint(_GirihPainter o) => o.bg != bg || o.fg != fg;
}

enum KotibehKind { lapis, wood, gach }

/// کتیبه: تیتر نستعلیق روی کاشی لاجوردی، چوب یا گچ با نوار گره‌چینی بالا و پایین
class Kotibeh extends StatelessWidget {
  const Kotibeh(this.text, {super.key, this.size = 30, this.kind = KotibehKind.lapis});
  final String text;
  final double size;
  final KotibehKind kind;

  @override
  Widget build(BuildContext context) {
    final (bg, fg, band) = switch (kind) {
      KotibehKind.lapis => (C.lapis, C.cream, const GirihBand(height: 7)),
      KotibehKind.wood => (C.walnut, const Color(0xFFF0D9A8), const GirihBand(height: 6, bg: Color(0xFF3E230F), fg: Color(0xFFA7733E), star: Color(0xFF7A4B26))),
      KotibehKind.gach => (C.soft, const Color(0xFF5B3F25), const GirihBand(height: 7, bg: C.rim, fg: C.gach2, star: Colors.white)),
    };
    return IntrinsicWidth(
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        band,
        Container(
          padding: EdgeInsets.fromLTRB(size * .8, size * .05, size * .8, size * .22),
          decoration: BoxDecoration(
            color: bg,
            border: Border.all(color: kind == KotibehKind.lapis ? const Color(0xFFCDB98E) : C.rim, width: 1.2),
            boxShadow: const [BoxShadow(color: Color(0x40000000), blurRadius: 14, offset: Offset(0, 8), spreadRadius: -6)],
          ),
          child: Text(text, textAlign: TextAlign.center, style: nast(size, color: fg, height: 1.75)),
        ),
        band,
      ]),
    );
  }
}

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

/// جای خالی عکس: فرش ساده با ترنج (بی‌شبکه، فوری)
class RugPlaceholder extends StatelessWidget {
  const RugPlaceholder({super.key, this.seed = 7});
  final int seed;
  static const _pals = [
    [Color(0xFFC9C6C0), Color(0xFF5A5753), Color(0xFF6E6A66)],
    [Color(0xFFE9DCC2), Color(0xFF7A2E2A), Color(0xFF2E3A5C)],
    [Color(0xFF1E2A4A), Color(0xFF8E1F22), Color(0xFFE7D7B2)],
    [Color(0xFF8E1F22), Color(0xFF1F2A4A), Color(0xFFE9D9B6)],
  ];
  @override
  Widget build(BuildContext context) {
    final p = _pals[seed.abs() % _pals.length];
    return CustomPaint(painter: _PhPainter(p), child: const SizedBox.expand());
  }
}

class _PhPainter extends CustomPainter {
  _PhPainter(this.p);
  final List<Color> p;
  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = p[1]);
    final b = s.shortestSide * .09;
    c.drawRect(Rect.fromLTRB(b, b, s.width - b, s.height - b), Paint()..color = p[0]);
    final cx = s.width / 2, cy = s.height / 2, rw = s.width * .26, rh = s.height * .2;
    c.drawPath(Path()..moveTo(cx, cy - rh)..lineTo(cx + rw, cy)..lineTo(cx, cy + rh)..lineTo(cx - rw, cy)..close(), Paint()..color = p[2]);
    c.drawPath(
        Path()..moveTo(cx, cy - rh * .45)..lineTo(cx + rw * .45, cy)..lineTo(cx, cy + rh * .45)..lineTo(cx - rw * .45, cy)..close(),
        Paint()..color = p[1]);
  }

  @override
  bool shouldRepaint(_PhPainter o) => false;
}

/// طاقچه: فرشی که از چوب‌پرده در طاقی جناغی آویزان است (کارت‌ها، دسته‌ها، صفحهٔ اول)
class Niche extends StatelessWidget {
  const Niche({super.key, required this.child, this.ar = .6667, this.tile = true, this.inset = .14});

  /// معمولاً RugImage
  final Widget child;
  final double ar;

  /// قاب کاشی فیروزه‌ای دور طاق
  final bool tile;
  final double inset;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: .62,
      child: LayoutBuilder(builder: (_, bc) {
        final w = bc.maxWidth, h = bc.maxHeight;
        final rugW = w * (1 - inset * 2), rugH = min(rugW / ar, h * .68);
        final rw = rugH * ar;
        return ClipPath(
          clipper: const ArchClipper(),
          child: Stack(children: [
            // قاب کاشی
            if (tile) Positioned.fill(child: Container(color: C.teal)),
            Positioned.fill(
              left: tile ? 3 : 0,
              right: tile ? 3 : 0,
              top: tile ? 3 : 0,
              child: ClipPath(
                clipper: const ArchClipper(),
                child: const DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [
                      Color(0xFFD9C7A2), Color(0xFFB99A6E), Color(0xFF9A7650), Color(0xFF7E5C3A),
                    ], stops: [0, .3, .62, 1]),
                  ),
                  child: _Muqarnas(),
                ),
              ),
            ),
            // چوب‌پرده و فرش
            Positioned(
              left: (w - rw) / 2 - 6,
              width: rw + 12,
              top: h * .3 - 3,
              height: 5,
              child: DecoratedBox(
                  decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      gradient: const LinearGradient(
                          begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFC08A4E), Color(0xFF6B4320)]))),
            ),
            Positioned(
              left: (w - rw) / 2,
              width: rw,
              top: h * .3,
              height: rugH,
              child: DecoratedBox(
                decoration: const BoxDecoration(boxShadow: [BoxShadow(color: Color(0x66000000), blurRadius: 10, offset: Offset(0, 6))]),
                child: child,
              ),
            ),
          ]),
        );
      }),
    );
  }
}

/// مقرنس سادهٔ بالای طاق (ردیف‌های نیم‌دایره)
class _Muqarnas extends StatelessWidget {
  const _Muqarnas();
  @override
  Widget build(BuildContext context) => CustomPaint(painter: _MuqPainter(), child: const SizedBox.expand());
}

class _MuqPainter extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final top = s.height * .26, u = s.width / 7;
    final light = Paint()..color = const Color(0x33FFFFFF), dark = Paint()..color = const Color(0x22000000);
    for (var row = 0; row < 4; row++) {
      final y = row * u * .55;
      if (y > top) break;
      for (var i = -1; i < 9; i++) {
        final x = i * u + (row.isOdd ? u / 2 : 0);
        c.drawArc(Rect.fromLTWH(x, y, u, u * .9), pi, pi, true, light);
        c.drawArc(Rect.fromLTWH(x, y + u * .1, u, u * .9), 0, pi, false, dark..style = PaintingStyle.stroke..strokeWidth = 1);
      }
    }
    // سایهٔ عمق طاقچه
    c.drawRect(Rect.fromLTWH(0, top, s.width, s.height - top),
        Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0x00000000), Color(0x40000000)])
            .createShader(Rect.fromLTWH(0, top, s.width, s.height - top)));
  }

  @override
  bool shouldRepaint(_MuqPainter o) => false;
}

/// کاشی کف آجری (برای صفحهٔ فرش و پنج‌دری)
class BrickFloor extends StatelessWidget {
  const BrickFloor({super.key, required this.child, this.padding = const EdgeInsets.all(26)});
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) => CustomPaint(painter: _FloorPainter(), child: Padding(padding: padding, child: child));
}

class _FloorPainter extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0xFFB66D45));
    const u = 34.0;
    final grout = Paint()
      ..color = const Color(0xFFE2C9A2)
      ..strokeWidth = 2;
    final rnd = Random(3);
    for (var y = 0.0; y < s.height; y += u) {
      for (var x = 0.0; x < s.width; x += u) {
        final t = rnd.nextDouble();
        c.drawRect(Rect.fromLTWH(x + 1, y + 1, u - 2, u - 2),
            Paint()..color = Color.lerp(const Color(0xFFA9603A), const Color(0xFFC57E52), t)!);
      }
      c.drawLine(Offset(0, y), Offset(s.width, y), grout);
    }
    for (var x = 0.0; x < s.width; x += u) {
      c.drawLine(Offset(x, 0), Offset(x, s.height), grout);
    }
    // نور ارسی
    c.drawRect(
        Offset.zero & s,
        Paint()
          ..shader = const RadialGradient(center: Alignment(.7, -.8), radius: 1.1, colors: [Color(0x40FFF0C8), Color(0x00000000), Color(0x55281405)])
              .createShader(Offset.zero & s));
  }

  @override
  bool shouldRepaint(_FloorPainter o) => false;
}

/// نشان شانه به رنگ خانه
class HouseChip extends StatelessWidget {
  const HouseChip(this.text, {super.key, this.color = C.lapis, this.bg});
  final String text;
  final Color color;
  final Color? bg;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: bg ?? C.soft, borderRadius: BorderRadius.circular(3), border: Border.all(color: C.rim)),
        child: Text(text, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: color)),
      );
}

/// بارگذاری با گره‌ها (همان KnotLogo با رنگ خانه)
class HouseLoading extends StatelessWidget {
  const HouseLoading({super.key});
  @override
  Widget build(BuildContext context) => const Center(child: KnotIcon(size: 28));
}

/// خواندن عدد از JSON
int asInt(Object? v) => v is num ? v.toInt() : int.tryParse('$v') ?? 0;
Json asMap(Object? v) => v is Map ? v.cast<String, dynamic>() : <String, dynamic>{};
