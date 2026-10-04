import 'dart:ui' show Color;

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import 'api.dart';

/// اعلان‌ها بدون سرویس خارجی: اپ هر چند ساعت یک‌بار اعلان‌های تازهٔ سایت را می‌گیرد
/// و روی گوشی نشان می‌دهد (در ایران روی همهٔ گوشی‌ها کار می‌کند).
const _task = 'irancarpet-notifications';
final _plugin = FlutterLocalNotificationsPlugin();
void Function(String payload)? onNotificationTap;

@pragma('vm:entry-point')
void notificationDispatcher() {
  Workmanager().executeTask((task, input) async {
    try {
      await _initPlugin();
      await checkNotifications();
    } catch (_) {}
    return true;
  });
}

Future<void> _initPlugin() async {
  await _plugin.initialize(
    settings: const InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher')),
    onDidReceiveNotificationResponse: (r) {
      if (r.payload != null) onNotificationTap?.call(r.payload!);
    },
  );
}

Future<void> setupNotifications() async {
  if (kIsWeb) return;
  await _initPlugin();
  final launch = await _plugin.getNotificationAppLaunchDetails();
  if (launch?.didNotificationLaunchApp == true && launch!.notificationResponse?.payload != null) {
    Future.delayed(const Duration(milliseconds: 900), () => onNotificationTap?.call(launch.notificationResponse!.payload!));
  }
  await _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission();
  await Workmanager().initialize(notificationDispatcher);
  await Workmanager().registerPeriodicTask(_task, _task,
      frequency: const Duration(hours: 4),
      constraints: Constraints(networkType: NetworkType.connected),
      existingWorkPolicy: ExistingPeriodicWorkPolicy.keep);
}

/// اعلان‌های تازه را می‌گیرد و نشان می‌دهد. بار اول فقط نقطهٔ شروع را ثبت می‌کند.
Future<List<Map<String, dynamic>>> checkNotifications({bool show = true}) async {
  final p = await SharedPreferences.getInstance();
  await Api.i.init();
  final since = p.getString('notif_since');
  final list = ((await Api.i.get('/notifications/', {'since': since})) as List).cast<Map<String, dynamic>>();
  if (list.isNotEmpty) await p.setString('notif_since', list.first['created_at'] as String);
  if (since == null || !show || kIsWeb) return list;
  for (final n in list.take(3)) {
    final payload = n['product_id'] != null
        ? 'product:${n['product_id']}'
        : n['category_id'] != null
            ? 'category:${n['category_id']}'
            : 'notifications';
    await _plugin.show(
      id: n['id'] as int,
      title: n['title'] as String,
      body: n['body'] as String,
      payload: payload,
      notificationDetails: const NotificationDetails(
        android: AndroidNotificationDetails('deals', 'تخفیف‌ها و فرش‌های تازه',
            channelDescription: 'اعلان تخفیف و فرش‌های تازهٔ ایران کارپت', importance: Importance.high, priority: Priority.high,
            color: Color(0xFFE5395B)),
      ),
    );
  }
  return list;
}
