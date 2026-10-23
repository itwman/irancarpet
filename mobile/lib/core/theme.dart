import 'package:flutter/material.dart';

import 'flavor.dart';

/// رنگ‌ها: «گره به گره» ایران کارپت، یا «فروشگاه تخصصی فرش» فرشستان (kHouse، ثابت زمان کامپایل).
/// نام‌ها مشترک‌اند تا صفحه‌های کاربردی (سبد، پرداخت، حساب) بی‌تغییر رنگ هر اپ را بگیرند:
/// در فرشستان pink ← آبی لاجوردی (دکمه‌های اصلی)، teal ← آبی روشن‌تر، saffron ← طلایی، ink ← جوهری، soft ← خاکستری سرد.
class C {
  static const pink = kHouse ? Color(0xFF1D3F8F) : Color(0xFFE5395B);
  static const pinkDark = kHouse ? Color(0xFF17336F) : Color(0xFFC42645);
  static const pinkTint = kHouse ? Color(0xFFEEF2FA) : Color(0xFFFFEFF2);
  static const teal = kHouse ? Color(0xFF2549A0) : Color(0xFF12A9B8);
  static const tealDark = kHouse ? Color(0xFF10275A) : Color(0xFF0B7C88);
  static const tealTint = kHouse ? Color(0xFFEEF2FA) : Color(0xFFE5F7F8);
  static const saffron = kHouse ? Color(0xFFC99A2E) : Color(0xFFFFB21E);
  static const saffronTint = kHouse ? Color(0xFFFCF6E7) : Color(0xFFFFF6E2);
  static const pistachio = kHouse ? Color(0xFF0D7146) : Color(0xFF7CC46B);
  static const ink = kHouse ? Color(0xFF141D33) : Color(0xFF22265A);
  static const ink2 = kHouse ? Color(0xFF323C52) : Color(0xFF4B4F7E);
  static const muted = kHouse ? Color(0xFF5A6377) : Color(0xFF6C6F98);
  static const soft = kHouse ? Color(0xFFF4F6F9) : Color(0xFFF3F4FB);
  static const line = kHouse ? Color(0xFFE2E6ED) : Color(0xFFECEDF6);
  static const bg = Colors.white;

  // فقط فرشستان («فروشگاه تخصصی فرش»): آبی لاجوردی برای عمل‌ها، طلایی برای نشان‌ها (متن تیره روی طلایی)
  static const brand = Color(0xFF1D3F8F);
  static const brand600 = Color(0xFF2549A0);
  static const brand700 = Color(0xFF17336F);
  static const brand800 = Color(0xFF10275A);
  static const brand900 = Color(0xFF0B1C42);
  static const brand50 = Color(0xFFEEF2FA);
  static const brand100 = Color(0xFFDDE5F5);
  static const brand200 = Color(0xFFC3D0EC);
  static const gold = Color(0xFFC99A2E);
  static const gold300 = Color(0xFFE5BE62);
  static const gold100 = Color(0xFFF6E8C4);
  static const gold50 = Color(0xFFFCF6E7);
  static const goldInk = Color(0xFF3A2A05);
  static const faint = Color(0xFF8A92A3);
  static const line2 = Color(0xFFEDF0F4);
  static const surface2 = Color(0xFFF9FAFC);
  static const ok = Color(0xFF0D7146);
  static const okTint = Color(0xFFE7F5EE);
  static const warn = Color(0xFF8A5300);
  static const warnTint = Color(0xFFFFF4DF);
  static const heart = Color(0xFFB4352F);

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

/// گردی گوشه‌ها (فرشستان: کارت‌ها ۱۲ تا ۱۶، دکمه‌ها ۱۰)
const double kR = kHouse ? 12 : 16;
const double _btnR = kHouse ? 10 : 14;

/// سایه‌های نرم فرشستان
const kShadow1 = [BoxShadow(color: Color(0x0F141D33), blurRadius: 3, offset: Offset(0, 1))];
const kShadow2 = [BoxShadow(color: Color(0x14141D33), blurRadius: 14, offset: Offset(0, 4))];

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
      titleTextStyle: TextStyle(fontFamily: kFont, fontSize: kHouse ? 17 : 18, fontWeight: kHouse ? FontWeight.w800 : FontWeight.w900, color: C.ink),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: C.pink,
        foregroundColor: Colors.white,
        minimumSize: const Size(64, 54),
        textStyle: const TextStyle(fontFamily: kFont, fontWeight: FontWeight.w800, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kHouse ? _btnR : kR)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: kHouse ? C.brand : C.ink,
        minimumSize: const Size(64, 50),
        side: BorderSide(color: kHouse ? C.brand200 : C.line, width: 1.5),
        textStyle: const TextStyle(fontFamily: kFont, fontWeight: FontWeight.w700, fontSize: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(_btnR)),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: C.soft,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(_btnR), borderSide: BorderSide.none),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(_btnR), borderSide: const BorderSide(color: C.teal, width: 2)),
      errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(_btnR), borderSide: const BorderSide(color: kHouse ? C.heart : C.pink, width: 1.5)),
      labelStyle: const TextStyle(color: C.muted),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: C.soft,
      selectedColor: kHouse ? C.brand : C.ink,
      labelStyle: const TextStyle(fontFamily: kFont, color: C.ink, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(fontFamily: kFont, color: Colors.white, fontWeight: FontWeight.w700),
      side: BorderSide.none,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kHouse ? 8 : 12)),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: C.ink,
      contentTextStyle: TextStyle(fontFamily: kFont, color: Colors.white),
    ),
    dividerTheme: const DividerThemeData(color: C.line, thickness: 1, space: 1),
  );
}
