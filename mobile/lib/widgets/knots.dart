import 'dart:math';

import 'package:flutter/material.dart';

import '../core/theme.dart';

/// نشان ایران کارپت: ۴×۴ گره روی زمینهٔ سرمه‌ای.
/// [progress] از ۰ تا ۱ گره‌ها را یکی‌یکی «می‌بافد».
class KnotLogo extends StatelessWidget {
  const KnotLogo({super.key, this.size = 48, this.progress = 1});
  final double size, progress;

  @override
  Widget build(BuildContext context) => CustomPaint(size: Size.square(size), painter: _LogoPainter(progress));
}

const _logoGrid = [
  [C.pink, C.saffron, C.saffron, C.pink],
  [C.saffron, C.teal, C.teal, C.saffron],
  [C.saffron, C.teal, C.teal, C.saffron],
  [C.pink, C.saffron, C.saffron, C.pink],
];

class _LogoPainter extends CustomPainter {
  _LogoPainter(this.progress);
  final double progress;

  @override
  void paint(Canvas canvas, Size s) {
    final u = s.width / 48;
    canvas.drawRRect(RRect.fromRectAndRadius(Offset.zero & s, Radius.circular(13 * u)), Paint()..color = C.ink);
    // ترتیب بافت: از گوشهٔ بالا-راست، ردیف‌به‌ردیف مثل دار قالی
    for (var r = 0; r < 4; r++) {
      for (var c = 0; c < 4; c++) {
        final idx = r * 4 + (3 - c);
        final t = ((progress * 16) - idx).clamp(0.0, 1.0);
        if (t <= 0) continue;
        final cx = (5 + c * 9.8 + 4.25) * u, cy = (5 + r * 9.8 + 4.25) * u;
        final half = 4.25 * u * Curves.easeOutBack.transform(t);
        canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromCenter(center: Offset(cx, cy), width: half * 2, height: half * 2), Radius.circular(2 * u)),
          Paint()..color = _logoGrid[r][c],
        );
      }
    }
  }

  @override
  bool shouldRepaint(_LogoPainter o) => o.progress != progress;
}

/// میدان گره‌های رنگی که آرام موج می‌خورند (بالای صفحهٔ اول)
class KnotField extends StatefulWidget {
  const KnotField({super.key, this.height = 150});
  final double height;
  @override
  State<KnotField> createState() => _KnotFieldState();
}

class _KnotFieldState extends State<KnotField> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(seconds: 6));

  @override
  void initState() {
    super.initState();
    if (!WidgetsBinding.instance.platformDispatcher.accessibilityFeatures.disableAnimations) _c.repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => SizedBox(
        height: widget.height,
        width: double.infinity,
        child: AnimatedBuilder(animation: _c, builder: (_, _) => CustomPaint(painter: _FieldPainter(_c.value))),
      );
}

class _FieldPainter extends CustomPainter {
  _FieldPainter(this.t);
  final double t;
  static const colors = [C.pink, C.saffron, C.teal, C.pistachio];

  @override
  void paint(Canvas canvas, Size s) {
    const cell = 13.0, gap = 3.0;
    final cols = (s.width / (cell + gap)).ceil(), rows = (s.height / (cell + gap)).ceil();
    final p = Paint();
    for (var r = 0; r < rows; r++) {
      for (var c = 0; c < cols; c++) {
        // نقش ترنج ساده: فاصله از مرکز رنگ را تعیین می‌کند
        final dx = (c - cols / 2).abs() / (cols / 2), dy = (r - rows / 2).abs() / (rows / 2);
        final d = sqrt(dx * dx + dy * dy);
        final band = ((d * 5 - t * 4) % 4).floor().abs() % 4;
        final wave = 0.55 + 0.45 * sin((d * 9 - t * 2 * pi));
        p.color = colors[band].withValues(alpha: 0.18 + 0.62 * wave * (1 - d * .45).clamp(0.2, 1));
        canvas.drawRRect(
          RRect.fromRectAndRadius(Rect.fromLTWH(c * (cell + gap), r * (cell + gap), cell, cell), const Radius.circular(3.5)),
          p,
        );
      }
    }
  }

  @override
  bool shouldRepaint(_FieldPainter o) => o.t != t;
}

/// آیکن کوچک گره (۲×۲) برای نکته‌ها و نشان‌ها
class KnotIcon extends StatelessWidget {
  const KnotIcon({super.key, this.c1 = C.pink, this.c2 = C.saffron, this.size = 26});
  final Color c1, c2;
  final double size;
  @override
  Widget build(BuildContext context) {
    final cell = (size - 3) / 2;
    Widget b(Color c) => Container(width: cell, height: cell, decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(3)));
    return SizedBox(
      width: size,
      height: size,
      child: Wrap(spacing: 3, runSpacing: 3, children: [b(c1), b(c2), b(c2), b(c1)]),
    );
  }
}
