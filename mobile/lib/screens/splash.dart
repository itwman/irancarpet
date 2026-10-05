import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../widgets/brand.dart';
import '../core/flavor.dart';
import '../finder/shell.dart';
import 'shell.dart';

/// شروع اپ: نشان ایران کارپت و نوشتار آن.
class Splash extends StatefulWidget {
  const Splash({super.key});
  @override
  State<Splash> createState() => _SplashState();
}

class _SplashState extends State<Splash> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300));

  @override
  void initState() {
    super.initState();
    _c.forward().whenComplete(() {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        PageRouteBuilder(
          pageBuilder: (_, _, _) => kIsFinder ? const FinderShell() : const Shell(),
          transitionsBuilder: (_, a, _, child) => FadeTransition(opacity: a, child: child),
          transitionDuration: const Duration(milliseconds: 380),
        ),
      );
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    // نشان دقیقاً همان‌جا و همان اندازه‌ای است که صفحهٔ شروع اندروید نشان می‌دهد؛ فقط نوشتار زیرش ظاهر می‌شود.
    return Scaffold(
      backgroundColor: Colors.white,
      body: AnimatedBuilder(
        animation: _c,
        builder: (_, _) {
          final t = Curves.easeOutCubic.transform(((_c.value - .15) / .6).clamp(0.0, 1.0));
          return Center(
            child: Stack(
              clipBehavior: Clip.none,
              alignment: Alignment.center,
              children: [
                SizedBox.square(
                    dimension: 120,
                    child: kIsFinder ? Image.asset('assets/brand/finder.png', width: 120, height: 120) : const BrandLogo(size: 120)),
                Transform.translate(
                  offset: Offset(0, 112 + 14 * (1 - t)),
                  child: Opacity(
                    opacity: t,
                    child: kIsFinder
                        ? const Column(mainAxisSize: MainAxisSize.min, children: [
                            Text('فرش‌یاب', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: C.ink, height: 1.2)),
                            SizedBox(height: 6),
                            Text('بگو چه فرشی می‌خواهی؛ ما پیدایش می‌کنیم', style: TextStyle(color: C.muted, fontSize: 14)),
                            SizedBox(height: 14),
                            Row(mainAxisSize: MainAxisSize.min, children: [
                              Text('از ', style: TextStyle(color: C.muted, fontSize: 12)),
                              Wordmark(height: 18),
                            ]),
                          ])
                        : const Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Wordmark(height: 36),
                              SizedBox(height: 10),
                              Text('فرش خانه‌ات را گره‌به‌گره انتخاب کن', style: TextStyle(color: C.muted, fontSize: 14)),
                            ],
                          ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
