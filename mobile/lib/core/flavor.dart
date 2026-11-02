import 'package:flutter/services.dart' show appFlavor;

/// سه اپ از یک کد: «ایران کارپت» (store)، «فرش‌یاب» (finder) و «فرشستان» (farshestan).
/// اندروید: --flavor finder ؛ وب و آزمایش: --dart-define=APP=finder
/// فرشستان حتماً با هر دو ساخته می‌شود: --flavor farshestan --dart-define=APP=farshestan
/// (رنگ‌ها ثابت‌های زمان کامپایل‌اند، پس انتخاب ظاهر باید از dart-define بیاید.)
const _app = String.fromEnvironment('APP');

/// اپ فرشستان با ظاهر «فروشگاه تخصصی فرش» (lib/house/)
const bool kHouse = _app == 'farshestan';

/// اپ «ایران کارپت فروشندگان» (lib/seller/): پنل فروشندگان بازارچه.
/// ساخت: --flavor seller --dart-define=APP=seller
const bool kSeller = _app == 'seller';
final bool kIsFinder = !kHouse && !kSeller && (_app == 'finder' || appFlavor == 'finder');
final String kAppName = kHouse ? 'فرشستان' : (kSeller ? 'ایران کارپت فروشندگان' : (kIsFinder ? 'فرش‌یاب' : 'ایران کارپت'));
final String kScheme = kHouse ? 'farshestan' : (kSeller ? 'icseller' : (kIsFinder ? 'farshyab' : 'irancarpet'));
final String kAppVersion = kHouse ? '1.1.1' : (kSeller ? '1.0.0' : (kIsFinder ? '1.0.3' : '1.0.8'));
