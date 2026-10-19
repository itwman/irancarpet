import 'package:flutter/services.dart' show appFlavor;

/// سه اپ از یک کد: «ایران کارپت» (store)، «فرش‌یاب» (finder) و «فرشستان» (farshestan).
/// اندروید: --flavor finder ؛ وب و آزمایش: --dart-define=APP=finder
/// فرشستان حتماً با هر دو ساخته می‌شود: --flavor farshestan --dart-define=APP=farshestan
/// (رنگ‌ها ثابت‌های زمان کامپایل‌اند، پس انتخاب ظاهر باید از dart-define بیاید.)
const _app = String.fromEnvironment('APP');

/// اپ فرشستان با ظاهر «خانهٔ ایرانی»
const bool kHouse = _app == 'farshestan';
final bool kIsFinder = !kHouse && (_app == 'finder' || appFlavor == 'finder');
final String kAppName = kHouse ? 'فرشستان' : (kIsFinder ? 'فرش‌یاب' : 'ایران کارپت');
final String kScheme = kHouse ? 'farshestan' : (kIsFinder ? 'farshyab' : 'irancarpet');
final String kAppVersion = kHouse ? '1.0.0' : (kIsFinder ? '1.0.3' : '1.0.8');
