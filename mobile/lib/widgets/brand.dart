import 'package:flutter/material.dart';

import '../core/flavor.dart';
import '../core/theme.dart';
import '../house/ui.dart';

/// نشان رسمی ایران کارپت (assets/brand). نسبت پهنا به بلندی نشان ۰٫۸۳۷ است.
class BrandLogo extends StatelessWidget {
  const BrandLogo({super.key, this.size = 48, this.tile = false});

  /// بلندی نشان؛ با [tile] اندازهٔ کاشی سفید دور آن.
  final double size;

  /// روی زمینهٔ تیره نشان روی کاشی سفید گوشه‌گرد می‌نشیند تا رنگ‌ها و فاصله‌های سفیدش دیده شوند.
  final bool tile;

  @override
  Widget build(BuildContext context) {
    if (kHouse) {
      // نشان ستارهٔ هشت‌پر فرشستان؛ روی زمینهٔ تیره روی کاشی سفید
      if (!tile) return FarshestanMark(size: size);
      return Container(
        width: size,
        height: size,
        alignment: Alignment.center,
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(size * .24)),
        child: FarshestanMark(size: size * .82),
      );
    }
    final img = Image.asset('assets/brand/logo.png',
        height: tile ? size * .78 : size, filterQuality: FilterQuality.medium, semanticLabel: tile ? null : 'ایران کارپت');
    if (!tile) return img;
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(size * .24)),
      child: img,
    );
  }
}

/// نوشتار «ایران کارپت» (تایپوگرافی رسمی). نسبت پهنا به بلندی ۴٫۰۱ است.
class Wordmark extends StatelessWidget {
  const Wordmark({super.key, this.height = 28, this.light = false});
  final double height;
  final bool light;

  @override
  Widget build(BuildContext context) => kHouse
      ? Text(kAppName, style: TextStyle(fontSize: height * .85, fontWeight: FontWeight.w900, height: 1.3, color: light ? Colors.white : C.brand))
      : Image.asset(
        light ? 'assets/brand/wordmark_white.png' : 'assets/brand/wordmark.png',
        height: height,
        filterQuality: FilterQuality.medium,
        semanticLabel: 'ایران کارپت',
      );
}
