import 'dart:ui' show Color;

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
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
    settings: const InitializationSettings(android: AndroidInitializationSettings('@drawable/ic_stat_notify')),
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
  if (kIsFinder) await _checkFinder(p, show);
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
            color: Color(0xFF740601)),
      ),
    );
  }
  return list;
}


/// فرش‌یاب: خبر دادن پاسخ تازهٔ کارشناس به درخواست مشتری.
Future<void> _checkFinder(SharedPreferences p, bool show) async {
  try {
    Api.i.token ??= await const FlutterSecureStorage().read(key: 'token');
    if (Api.i.token == null) return;
    final r = await Api.i.get('/finder/requests/') as Map<String, dynamic>;
    final told = (p.getStringList('finder_told') ?? []).toSet();
    final fresh = (r['results'] as List).cast<Map<String, dynamic>>().where((x) => x['unread'] == true && !told.contains('${x['id']}'));
    for (final x in fresh.take(3)) {
      told.add('${x['id']}');
      if (!show || kIsWeb) continue;
      await _plugin.show(
        id: 900000 + (x['id'] as int),
        title: 'پاسخ کارشناس آماده است',
        body: 'فرش‌های پیشنهادی برای درخواستت را ببین.',
        payload: 'request:${x['id']}',
        notificationDetails: const NotificationDetails(
          android: AndroidNotificationDetails('finder', 'پاسخ کارشناس',
              channelDescription: 'پاسخ کارشناس ایران کارپت به درخواست‌های فرش‌یاب', importance: Importance.high, priority: Priority.high,
              color: Color(0xFF22265A)),
        ),
      );
    }
    await p.setStringList('finder_told', told.toList());
  } catch (_) {}
}
