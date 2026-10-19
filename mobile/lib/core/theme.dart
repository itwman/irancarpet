import 'package:flutter/material.dart';

import 'flavor.dart';

/// رنگ‌ها: «گره به گره» ایران کارپت، یا «خانهٔ ایرانی» فرشستان (kHouse، ثابت زمان کامپایل).
/// نام‌ها مشترک‌اند تا صفحه‌های کاربردی (سبد، پرداخت، حساب) بی‌تغییر رنگ هر اپ را بگیرند:
/// pink ← لاکی، teal ← فیروزه‌ای، saffron ← زرد کاشی، ink ← قهوه‌ای گردو، soft ← گچ روشن.
class C {
  static const pink = kHouse ? Color(0xFF8C1D25) : Color(0xFFE5395B);
  static const pinkDark = kHouse ? Color(0xFF6E141B) : Color(0xFFC42645);
  static const pinkTint = kHouse ? Color(0xFFF4E0DA) : Color(0xFFFFEFF2);
  static const teal = kHouse ? Color(0xFF167A7E) : Color(0xFF12A9B8);
  static const tealDark = kHouse ? Color(0xFF0E5458) : Color(0xFF0B7C88);
  static const tealTint = kHouse ? Color(0xFFDCEDE9) : Color(0xFFE5F7F8);
  static const saffron = kHouse ? Color(0xFFD29A2E) : Color(0xFFFFB21E);
  static const saffronTint = kHouse ? Color(0xFFF5E9CF) : Color(0xFFFFF6E2);
  static const pistachio = kHouse ? Color(0xFF5E8A5A) : Color(0xFF7CC46B);
  static const ink = kHouse ? Color(0xFF2B1D15) : Color(0xFF22265A);
  static const ink2 = kHouse ? Color(0xFF5A4536) : Color(0xFF4B4F7E);
  static const muted = kHouse ? Color(0xFF66513F) : Color(0xFF6C6F98);
  static const soft = kHouse ? Color(0xFFF2EADA) : Color(0xFFF3F4FB);
  static const line = kHouse ? Color(0xFFD8C9AB) : Color(0xFFECEDF6);
  static const bg = kHouse ? Color(0xFFE8DDC7) : Colors.white;

  // فقط خانهٔ ایرانی
  static const lapis = Color(0xFF1B3768);
  static const lapisDark = Color(0xFF0F2348);
  static const firoozeLight = Color(0xFF3FA7A3);
  static const brick = Color(0xFFA35E3A);
  static const brickDark = Color(0xFF7B4127);
  static const kahgel = Color(0xFFC4A076);
  static const walnut = Color(0xFF4A2B19);
  static const brass = Color(0xFFB8873A);
  static const gach2 = Color(0xFFDACCB1);
  static const rim = Color(0xFFD2C09C);
  static const cream = Color(0xFFF3E9D3);

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

/// نستعلیق (ایران‌نستعلیق) برای تیترهای کوتاه اپ فرشستان؛ در main.dart بار می‌شود
const kNast = 'Nast';

/// گردی گوشه‌ها: خانهٔ ایرانی گوشه‌های تیز دارد
const double kR = kHouse ? 4 : 16;

ThemeData buildTheme() {
  final base = ThemeData(
    useMaterial3: true,
    fontFamily: kFont,
    scaffoldBackgroundColor: C.bg,
    colorScheme: ColorScheme.fromSeed(seedColor: C.pink, primary: kHouse ? C.lapis : C.pink, secondary: C.teal, surface: kHouse ? C.soft : Colors.white)
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
      backgroundColor: kHouse ? C.bg : Colors.white,
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
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kR)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: C.ink,
        minimumSize: const Size(64, 50),
        side: const BorderSide(color: C.line, width: 1.5),
        textStyle: const TextStyle(fontFamily: kFont, fontWeight: FontWeight.w700, fontSize: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kHouse ? 4 : 14)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: kHouse ? Colors.white : C.soft,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(kHouse ? 4 : 14), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(kHouse ? 4 : 14), borderSide: const BorderSide(color: C.teal, width: 2)),
      errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(kHouse ? 4 : 14), borderSide: const BorderSide(color: C.pink, width: 1.5)),
      labelStyle: const TextStyle(color: C.muted),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: C.soft,
      selectedColor: C.ink,
      labelStyle: const TextStyle(fontFamily: kFont, color: C.ink, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(fontFamily: kFont, color: Colors.white, fontWeight: FontWeight.w700),
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kHouse ? 20 : 12)),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: C.ink,
      contentTextStyle: TextStyle(fontFamily: kFont, color: Colors.white),
    ),
    dividerTheme: const DividerThemeData(color: C.line, thickness: 1, space: 1),
  );
}
