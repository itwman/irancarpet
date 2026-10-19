# irancarpet_app

A new Flutter project.

## Getting Started

This project is a starting point for a Flutter application.

A few resources to get you started if this is your first Flutter project:

- [Learn Flutter](https://docs.flutter.dev/get-started/learn-flutter)
- [Write your first Flutter app](https://docs.flutter.dev/get-started/codelab)
- [Flutter learning resources](https://docs.flutter.dev/reference/learning-resources)

For help getting started with Flutter development, view the
[online documentation](https://docs.flutter.dev/), which offers tutorials,
samples, guidance on mobile development, and a full API reference.

## سه اپ از یک کد

| اپ | بسته | ساخت |
|---|---|---|
| ایران کارپت (فروشگاه) | `net.irancarpet.app` | `flutter build apk --release --flavor store --split-per-abi --target-platform android-arm,android-arm64` |
| فرشستان (ظاهر «خانهٔ ایرانی»، وصل به farshestan.ir) | `ir.farshestan.app` | `flutter build apk --release --flavor farshestan --dart-define=APP=farshestan --split-per-abi --target-platform android-arm,android-arm64 --build-name 1.0.0 --build-number 1` |
| فرش‌یاب (پیدا کردن فرش بر اساس نیاز و عکس) | `net.irancarpet.finder` | `flutter build apk --release --flavor finder --split-per-abi --target-platform android-arm,android-arm64 --build-name 1.0.1 --build-number 2` |

کدهای فرش‌یاب در `lib/finder/` است؛ آیکون و صفحهٔ شروعش در `android/app/src/finder/res`.
برای آزمایش روی وب: `--dart-define=APP=finder`.

## فرشستان

- ظاهر جدا در `lib/house/` (صفحهٔ اول، تالارها، صفحهٔ فرش با فرش لوله‌شده و ذره‌بین گره، «در اتاق من»)؛ بقیهٔ صفحه‌ها (سبد، پرداخت، حساب، سفارش‌ها) همان کد مشترک با رنگ‌های خانه.
- رنگ‌ها ثابت زمان کامپایل‌اند (`kHouse`)، پس `--dart-define=APP=farshestan` همیشه کنار `--flavor farshestan` لازم است.
- نشان و فونت ایران‌نستعلیق فقط در این flavor بسته‌بندی می‌شود (`assets/house/`)؛ فونت در `main.dart` با `FontLoader` بار می‌شود.
- کلید امضای جدا: `android/key-farshestan.properties` (بیرون از مخزن؛ مثل `key.properties`).
- سرور: کادر خود فرش در عکس‌ها (`crop`) و عکس دسته‌ها را API فقط روی سایت‌های قالب‌دار می‌دهد (`SITE_THEME`).
