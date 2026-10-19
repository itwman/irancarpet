import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../screens/shell.dart';
import 'ui.dart';

/// شروع اپ فرشستان: نشان درست همان‌جای صفحهٔ شروع اندروید، بعد نام نستعلیق و نوار گره‌چینی
class HouseSplash extends StatefulWidget {
  const HouseSplash({super.key});
  @override
  State<HouseSplash> createState() => _HouseSplashState();
}

class _HouseSplashState extends State<HouseSplash> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1500));

  @override
  void initState() {
    super.initState();
    _c.forward().whenComplete(() {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(PageRouteBuilder(
        pageBuilder: (_, _, _) => const Shell(),
        transitionsBuilder: (_, a, _, child) => FadeTransition(opacity: a, child: child),
        transitionDuration: const Duration(milliseconds: 420),
      ));
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: C.bg,
      body: AnimatedBuilder(
        animation: _c,
        builder: (_, _) {
          final t = Curves.easeOutCubic.transform(((_c.value - .12) / .55).clamp(0.0, 1.0));
          final b = Curves.easeOut.transform(((_c.value - .35) / .5).clamp(0.0, 1.0));
          return Stack(children: [
            Positioned(top: 0, left: 0, right: 0, child: Opacity(opacity: b, child: const SafeArea(child: GirihBand(height: 10)))),
            Positioned(bottom: 0, left: 0, right: 0, child: Opacity(opacity: b, child: const SafeArea(child: GirihBand(height: 10)))),
            Center(
              child: Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
                Image.asset('assets/house/farshestan_logo.png', width: 120, height: 120,
                    errorBuilder: (_, _, _) => const SizedBox.square(dimension: 120)),
                Transform.translate(
                  offset: Offset(0, 118 + 16 * (1 - t)),
                  child: Opacity(
                    opacity: t,
                    child: Column(mainAxisSize: MainAxisSize.min, children: [
                      Text('فرشستان', style: nast(52, height: 1.6)),
                      const Text('از کارخانه، تا خانه', style: TextStyle(color: C.ink2, fontSize: 14)),
                    ]),
                  ),
                ),
              ]),
            ),
          ]);
        },
      ),
    );
  }
}
