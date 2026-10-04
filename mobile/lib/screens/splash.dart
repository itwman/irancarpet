import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../widgets/brand.dart';
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
          pageBuilder: (_, _, _) => const Shell(),
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
                const SizedBox.square(dimension: 120, child: BrandLogo(size: 120)),
                Transform.translate(
                  offset: Offset(0, 112 + 14 * (1 - t)),
                  child: Opacity(
                    opacity: t,
                    child: const Column(
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
