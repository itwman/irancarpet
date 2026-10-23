import 'dart:async';
import 'dart:math';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';

import '../core/theme.dart';
import 'ui.dart';

/// پیکسل‌های عکس فرش (یک بار از روی عکس رمزگشایی و نگه داشته می‌شود)
class RugPixels {
  RugPixels._(this.w, this.h, this.rgba, this.image);
  final int w, h;
  final Uint8List rgba;
  final ui.Image image;

  static final _cache = <String, Future<RugPixels?>>{};

  static Future<RugPixels?> load(String url) {
    if (url.isEmpty) return Future.value(null);
    return _cache.putIfAbsent(url, () async {
      try {
        final c = Completer<ui.Image>();
        final stream = CachedNetworkImageProvider(url).resolve(ImageConfiguration.empty);
        late final ImageStreamListener l;
        l = ImageStreamListener((info, _) {
          if (!c.isCompleted) c.complete(info.image.clone());
          stream.removeListener(l);
        }, onError: (e, _) {
          if (!c.isCompleted) c.completeError(e);
          stream.removeListener(l);
        });
        stream.addListener(l);
        final img = await c.future.timeout(const Duration(seconds: 25));
        final bd = await img.toByteData(format: ui.ImageByteFormat.rawRgba);
        if (bd == null) return null;
        return RugPixels._(img.width, img.height, bd.buffer.asUint8List(), img);
      } catch (_) {
        _cache.remove(url);
        return null;
      }
    });
  }

  /// میانگین رنگ چند نقطه در مستطیل (کسرهای ۰ تا ۱ از کل عکس)
  Color avg(double x0, double y0, double x1, double y1) {
    var r = 0, g = 0, b = 0, n = 0;
    for (var j = 0; j < 3; j++) {
      for (var i = 0; i < 3; i++) {
        final fx = x0 + (x1 - x0) * (i + .5) / 3, fy = y0 + (y1 - y0) * (j + .5) / 3;
        final px = (fx * w).floor().clamp(0, w - 1), py = (fy * h).floor().clamp(0, h - 1);
        final k = (py * w + px) * 4;
        r += rgba[k];
        g += rgba[k + 1];
        b += rgba[k + 2];
        n++;
      }
    }
    return Color.fromARGB(255, r ~/ n, g ~/ n, b ~/ n);
  }

  /// رنگ‌های لوله (حاشیه، زمینه، ترنج) از روی خود فرش
  List<Color> rollColors(RugCrop c) {
    Color at(double u) => avg((c.x + u * c.w) / 100, (c.y + c.h * .45) / 100, (c.x + (u + .03) * c.w) / 100, (c.y + c.h * .55) / 100);
    return [at(.02), at(.1), at(.25), at(.48), at(.25), at(.1), at(.02)];
  }
}

/// گره‌ها: تکه‌ای از عکس فرش با تعداد گره متناسب با شانه
/// [cx], [cy] مرکز نسبت به کادر فرش (۰ تا ۱)، [patch] پهنای تکه نسبت به پهنای فرش
class KnotPainter extends CustomPainter {
  KnotPainter({required this.px, required this.crop, required this.cx, required this.cy, required this.knots, required this.patch});
  final RugPixels? px;
  final RugCrop crop;
  final double cx, cy, patch;
  final int knots;

  @override
  void paint(Canvas canvas, Size s) {
    final r = Offset.zero & s;
    canvas.save();
    canvas.clipPath(Path()..addOval(r));
    canvas.drawRect(r, Paint()..color = const Color(0xFF1A120C));
    final p = px;
    if (p == null) {
      canvas.restore();
      return;
    }
    final n = knots, cell = s.width / n;
    final pw = patch, ph = patch * crop.ar; // تکهٔ مربعی واقعی: نسبت به بلندی فرش
    final u0 = (cx - pw / 2).clamp(0.0, 1 - pw), v0 = (cy - ph / 2).clamp(0.0, max(0.0, 1 - ph));
    final groove = Paint(), knot = Paint(), hi = Paint()..color = const Color(0x2BFFFFFF);
    for (var j = 0; j < n; j++) {
      for (var i = 0; i < n; i++) {
        final ua = u0 + pw * i / n, ub = u0 + pw * (i + 1) / n, va = v0 + ph * j / n, vb = v0 + ph * (j + 1) / n;
        final col = p.avg((crop.x + ua * crop.w) / 100, (crop.y + va * crop.h) / 100, (crop.x + ub * crop.w) / 100, (crop.y + vb * crop.h) / 100);
        // جهت فارسی: i از راست
        final x = s.width - (i + 1) * cell, y = j * cell, mx = x + cell / 2, my = y + cell / 2;
        groove.color = Color.lerp(col, Colors.black, .38)!;
        canvas.drawRect(Rect.fromLTWH(x, y, cell + .6, cell + .6), groove);
        knot.color = col;
        // گره دو بازو دارد؛ دو بیضی کج کنار هم
        for (final side in [-1.0, 1.0]) {
          canvas.save();
          canvas.translate(mx + side * cell * .2, my);
          canvas.rotate(-side * .32);
          canvas.drawOval(Rect.fromCenter(center: Offset.zero, width: cell * .52, height: cell * .88), knot);
          if (cell > 5) canvas.drawOval(Rect.fromCenter(center: Offset(-cell * .05, -cell * .16), width: cell * .14, height: cell * .36), hi);
          canvas.restore();
        }
      }
    }
    // برق شیشه
    canvas.drawRect(
        r,
        Paint()
          ..shader = const RadialGradient(center: Alignment(-.35, -.55), radius: .7, colors: [Color(0x55FFFFFF), Color(0x00FFFFFF)])
              .createShader(r));
    canvas.restore();
  }

  @override
  bool shouldRepaint(KnotPainter o) => o.px != px || o.cx != cx || o.cy != cy || o.knots != knots || o.patch != patch || o.crop != crop;
}

/// ذره‌بین «نمای نزدیک بافت»: حلقهٔ سفید با سایهٔ نرم و دستهٔ لاجوردی
class Loupe extends StatelessWidget {
  const Loupe({super.key, required this.painter, this.size = 150, this.handle = true});
  final KnotPainter painter;
  final double size;
  final bool handle;
  @override
  Widget build(BuildContext context) => SizedBox.square(
        dimension: size,
        child: Stack(clipBehavior: Clip.none, children: [
          if (handle)
            Positioned(
              left: size * .78,
              top: size * .8,
              child: Transform.rotate(
                angle: -.75,
                child: Container(
                  width: 14,
                  height: size * .42,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(7),
                    color: C.brand800,
                    boxShadow: const [BoxShadow(color: Color(0x40141D33), blurRadius: 8, offset: Offset(0, 6))],
                  ),
                ),
              ),
            ),
          Container(
            decoration: const BoxDecoration(shape: BoxShape.circle, boxShadow: [
              BoxShadow(color: Colors.white, spreadRadius: 4),
              BoxShadow(color: Color(0x14000000), spreadRadius: 5),
              BoxShadow(color: Color(0x59141D33), spreadRadius: 4, blurRadius: 26, offset: Offset(0, 10)),
            ]),
            child: CustomPaint(size: Size.square(size), painter: painter),
          ),
        ]),
      );
}

/// جملهٔ توضیح شانه
String knotSentence(int sh, String own) {
  const say = {
    700: 'گره‌ها درشت‌ترند؛ نقش‌ها ساده‌تر و پررنگ دیده می‌شوند.',
    1000: 'گره‌ها ریزترند؛ مرز رنگ‌ها نرم‌تر است.',
    1200: 'پیچ‌وتاب گل‌ها و برگ‌ها با جزئیات بیشتری بافته می‌شود.',
    1500: 'ریزترین گره‌ها؛ از فاصلهٔ معمول، نقش تقریباً مثل نقاشی دیده می‌شود.',
  };
  String fa(Object x) => x.toString().split('').map((c) => int.tryParse(c) == null ? c : '۰۱۲۳۴۵۶۷۸۹'[int.parse(c)]).join();
  final head = '$sh' == own ? 'این فرش ${fa(sh)} شانه است' : 'اگر همین نقش ${fa(sh)} شانه بود';
  return '$head؛ در هر ۱۰ سانت از عرض فرش حدود ${fa(sh ~/ 10)} گره کنار هم می‌نشیند. ${say[sh] ?? ''}';
}
