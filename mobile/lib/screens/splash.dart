import 'package:flutter/material.dart';

import '../core/theme.dart';
import '../widgets/knots.dart';
import 'shell.dart';

/// شروع اپ: نشان ایران کارپت گره‌به‌گره بافته می‌شود.
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
      body: Center(
        child: AnimatedBuilder(
          animation: _c,
          builder: (_, _) => Column(mainAxisSize: MainAxisSize.min, children: [
            KnotLogo(size: 104, progress: Curves.easeOut.transform(_c.value)),
            const SizedBox(height: 22),
            Opacity(
              opacity: ((_c.value - .55) * 2.2).clamp(0.0, 1.0),
              child: const Column(children: [
                Text('ایران کارپت', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: C.ink)),
                SizedBox(height: 2),
                Text('فرش خانه‌ات را گره‌به‌گره انتخاب کن', style: TextStyle(color: C.muted, fontSize: 14)),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}
