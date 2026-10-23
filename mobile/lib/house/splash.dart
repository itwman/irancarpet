import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../screens/shell.dart';
import 'ui.dart';

/// شروع اپ فرشستان: نشان ستارهٔ هشت‌پر درست همان‌جای صفحهٔ شروع اندروید، بعد نام و شعار
class HouseSplash extends StatefulWidget {
  const HouseSplash({super.key});
  @override
  State<HouseSplash> createState() => _HouseSplashState();
}

class _HouseSplashState extends State<HouseSplash> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1300));

  @override
  void initState() {
    super.initState();
    _c.forward().whenComplete(() {
      if (!mounted) return;
      Navigator.of(context).pushReplacement(PageRouteBuilder(
        pageBuilder: (_, _, _) => const Shell(),
        transitionsBuilder: (_, a, _, child) => FadeTransition(opacity: a, child: child),
        transitionDuration: const Duration(milliseconds: 380),
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
      backgroundColor: Colors.white,
      body: AnimatedBuilder(
        animation: _c,
        builder: (_, _) {
          final t = Curves.easeOutCubic.transform(((_c.value - .1) / .55).clamp(0.0, 1.0));
          return Center(
            child: Stack(clipBehavior: Clip.none, alignment: Alignment.center, children: [
              const FarshestanMark(size: 120),
              Transform.translate(
                offset: Offset(0, 104 + 14 * (1 - t)),
                child: Opacity(
                  opacity: t,
                  child: const Column(mainAxisSize: MainAxisSize.min, children: [
                    Text('فرشستان', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: C.brand, height: 1.4)),
                    Text('فرش ماشینی، مستقیم از کارخانه', style: TextStyle(color: C.muted, fontSize: 14)),
                  ]),
                ),
              ),
            ]),
          );
        },
      ),
    );
  }
}
