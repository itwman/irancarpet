import 'package:flutter/material.dart';

/// رنگ‌های «گره به گره» — همان رنگ‌های سایت ایران کارپت.
class C {
  static const pink = Color(0xFFE5395B);
  static const pinkDark = Color(0xFFC42645);
  static const pinkTint = Color(0xFFFFEFF2);
  static const teal = Color(0xFF12A9B8);
  static const tealDark = Color(0xFF0B7C88);
  static const tealTint = Color(0xFFE5F7F8);
  static const saffron = Color(0xFFFFB21E);
  static const saffronTint = Color(0xFFFFF6E2);
  static const pistachio = Color(0xFF7CC46B);
  static const ink = Color(0xFF22265A);
  static const ink2 = Color(0xFF4B4F7E);
  static const muted = Color(0xFF6C6F98);
  static const soft = Color(0xFFF3F4FB);
  static const line = Color(0xFFECEDF6);
  static const bg = Colors.white;

  /// رنگ نشان شانه (مثل سایت)
  static Color reeds(String r) => switch (r) {
        '700' => pistachio,
        '1000' => teal,
        '1200' => pink,
        '1500' => saffron,
        _ => ink2,
      };
}

const kFont = 'Vazirmatn';

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    fontFamily: kFont,
    scaffoldBackgroundColor: C.bg,
    colorScheme: ColorScheme.fromSeed(seedColor: C.pink, primary: C.pink, secondary: C.teal, surface: Colors.white)
        .copyWith(onSurface: C.ink),
  );
  final t = base.textTheme.apply(bodyColor: C.ink, displayColor: C.ink, fontFamily: kFont);
  return base.copyWith(
    textTheme: t.copyWith(
      headlineMedium: t.headlineMedium?.copyWith(fontWeight: FontWeight.w900, height: 1.35),
      headlineSmall: t.headlineSmall?.copyWith(fontWeight: FontWeight.w900, height: 1.35),
      titleLarge: t.titleLarge?.copyWith(fontWeight: FontWeight.w900),
      titleMedium: t.titleMedium?.copyWith(fontWeight: FontWeight.w800),
      bodyMedium: t.bodyMedium?.copyWith(height: 1.8),
      bodySmall: t.bodySmall?.copyWith(color: C.muted, height: 1.7),
    ),
    appBarTheme: const AppBarTheme(
      backgroundColor: Colors.white,
      foregroundColor: C.ink,
      elevation: 0,
      scrolledUnderElevation: .5,
      centerTitle: false,
      titleTextStyle: TextStyle(fontFamily: kFont, fontSize: 18, fontWeight: FontWeight.w900, color: C.ink),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: C.pink,
        foregroundColor: Colors.white,
        minimumSize: const Size(64, 54),
        textStyle: const TextStyle(fontFamily: kFont, fontWeight: FontWeight.w800, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: C.ink,
        minimumSize: const Size(64, 50),
        side: const BorderSide(color: C.line, width: 1.5),
        textStyle: const TextStyle(fontFamily: kFont, fontWeight: FontWeight.w700, fontSize: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: C.soft,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.teal, width: 2)),
      errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: C.pink, width: 1.5)),
      labelStyle: const TextStyle(color: C.muted),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: C.soft,
      selectedColor: C.ink,
      labelStyle: const TextStyle(fontFamily: kFont, color: C.ink, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(fontFamily: kFont, color: Colors.white, fontWeight: FontWeight.w700),
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: C.ink,
      contentTextStyle: TextStyle(fontFamily: kFont, color: Colors.white),
    ),
    dividerTheme: const DividerThemeData(color: C.line, thickness: 1, space: 1),
  );
}
