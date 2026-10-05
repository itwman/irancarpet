import 'package:flutter/services.dart' show appFlavor;

/// دو اپ از یک کد: «ایران کارپت» (store) و «فرش‌یاب» (finder).
/// اندروید: --flavor finder ؛ وب و آزمایش: --dart-define=APP=finder
const _app = String.fromEnvironment('APP');
final bool kIsFinder = _app == 'finder' || appFlavor == 'finder';
final String kAppName = kIsFinder ? 'فرش‌یاب' : 'ایران کارپت';
final String kScheme = kIsFinder ? 'farshyab' : 'irancarpet';
final String kAppVersion = kIsFinder ? '1.0.1' : '1.0.6';
