import 'dart:math';

import 'package:flutter/material.dart';

/// فرش لوله‌شده‌ای که از بالا به پایین باز می‌شود. [progress] صفر: لوله، یک: کاملاً باز.
/// [roll] رنگ‌های نوار لوله (از حاشیه تا ترنج خود فرش)؛ اگر نباشد قهوه‌ای خنثی.
class UnrollRug extends StatelessWidget {
  const UnrollRug({super.key, required this.progress, required this.ar, required this.child, this.roll});
  final Animation<double> progress;
  final double ar;
  final Widget child;
  final List<Color>? roll;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: ar,
      child: LayoutBuilder(builder: (_, bc) {
        final w = bc.maxWidth, h = bc.maxHeight;
        final sheet = RepaintBoundary(child: child);
        return AnimatedBuilder(
          animation: progress,
          builder: (_, _) {
            final p = progress.value.clamp(0.0, 1.0);
            final d0 = max(22.0, w * .13), d = d0 * sqrt(1 - p * .82);
            return Stack(clipBehavior: Clip.none, children: [
              Positioned.fill(child: ClipRect(clipper: _TopClip(p), child: sheet)),
              if (p < .985)
                Positioned(
                  left: -w * .03,
                  right: -w * .03,
                  top: p * h - d / 2,
                  height: d,
                  child: _Roll(colors: roll),
                ),
            ]);
          },
        );
      }),
    );
  }
}

class _TopClip extends CustomClipper<Rect> {
  _TopClip(this.p);
  final double p;
  @override
  Rect getClip(Size s) => Rect.fromLTWH(-2, -2, s.width + 4, s.height * p + 2);
  @override
  bool shouldReclip(_TopClip o) => o.p != p;
}

class _Roll extends StatelessWidget {
  const _Roll({this.colors});
  final List<Color>? colors;
  @override
  Widget build(BuildContext context) {
    final cs = colors ?? const [Color(0xFF6E4B33), Color(0xFF8A7A66), Color(0xFFA58E6E), Color(0xFF8A7A66), Color(0xFF6E4B33)];
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        gradient: LinearGradient(colors: cs),
        boxShadow: const [BoxShadow(color: Color(0x73000000), blurRadius: 14, offset: Offset(0, 12), spreadRadius: -4)],
      ),
      foregroundDecoration: BoxDecoration(
        borderRadius: BorderRadius.circular(999),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [
          Color(0x8C000000), Color(0x14000000), Color(0x47FFFFFF), Color(0x1F000000), Color(0x99000000),
        ], stops: [0, .32, .46, .64, 1]),
      ),
      child: Align(
        alignment: AlignmentDirectional.centerEnd,
        // سر لوله: حلقه‌های پیچیدهٔ فرش
        child: AspectRatio(
          aspectRatio: .55,
          child: Container(
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(colors: [Color(0xFF6B5A4A), Color(0xFFD9CDB8), Color(0xFF6B5A4A), Color(0xFFD9CDB8), Color(0xFF6B5A4A)],
                  stops: [0, .25, .5, .75, 1]),
            ),
          ),
        ),
      ),
    );
  }
}
