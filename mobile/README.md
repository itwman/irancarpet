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

## دو اپ از یک کد

| اپ | بسته | ساخت |
|---|---|---|
| ایران کارپت (فروشگاه) | `net.irancarpet.app` | `flutter build apk --release --flavor store --split-per-abi --target-platform android-arm,android-arm64` |
| فرش‌یاب (پیدا کردن فرش بر اساس نیاز و عکس) | `net.irancarpet.finder` | `flutter build apk --release --flavor finder --split-per-abi --target-platform android-arm,android-arm64 --build-name 1.0.1 --build-number 2` |

کدهای فرش‌یاب در `lib/finder/` است؛ آیکون و صفحهٔ شروعش در `android/app/src/finder/res`.
برای آزمایش روی وب: `--dart-define=APP=finder`.
