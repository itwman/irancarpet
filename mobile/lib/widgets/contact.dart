import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';

IconData socialIcon(String key) => switch (key) {
      'whatsapp' => Icons.chat_rounded,
      'telegram' => Icons.send_rounded,
      'telegram_channel' => Icons.campaign_rounded,
      'eitaa' => Icons.forum_rounded,
      'eitaa_channel' => Icons.campaign_outlined,
      'instagram' => Icons.camera_alt_outlined,
      'farshplus' => Icons.storefront_rounded,
      _ => Icons.call_rounded,
    };

Color socialColor(String key) => switch (key) {
      'whatsapp' => const Color(0xFF1F9D55),
      'telegram' || 'telegram_channel' => const Color(0xFF1D8FD1),
      'eitaa' || 'eitaa_channel' => const Color(0xFFE08A00),
      'instagram' => const Color(0xFFC1356B),
      'farshplus' => C.pinkDark,
      _ => C.tealDark,
    };

const _messengers = ['whatsapp', 'telegram', 'eitaa'];

List<Json> socials(BuildContext context, {bool messengersOnly = false, bool followsOnly = false}) {
  final all = ((context.read<AppConfig>().data['socials'] as List?) ?? []).cast<Json>();
  if (messengersOnly) return all.where((s) => _messengers.contains(s['key'])).toList();
  if (followsOnly) return all.where((s) => !_messengers.contains(s['key'])).toList();
  return all;
}

Future<void> openUrl(String url) => launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

/// انتخاب راه گفتگو با کارشناس (واتساپ، تلگرام، ایتا، تماس). text: پیامی که در واتساپ آماده می‌شود
Future<void> showContactSheet(BuildContext context, {String? text}) {
  final cfg = context.read<AppConfig>().data;
  final ms = socials(context, messengersOnly: true);
  final phones = [
    if ((cfg['mobile'] as String? ?? '').isNotEmpty) cfg['mobile'] as String,
    if ((cfg['phone'] as String? ?? '').isNotEmpty) cfg['phone'] as String,
  ];
  return showModalBottomSheet(
    context: context,
    showDragHandle: true,
    builder: (c) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(8, 0, 8, 12),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Text('گفتگو با کارشناس فروش', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
          const SizedBox(height: 6),
          for (final s in ms)
            ListTile(
              leading: Icon(socialIcon(s['key'] as String), color: socialColor(s['key'] as String)),
              title: Text(s['name'] as String, style: const TextStyle(fontWeight: FontWeight.w800)),
              trailing: const Icon(Icons.chevron_right, color: C.muted),
              onTap: () {
                Navigator.pop(c);
                var url = s['url'] as String;
                if (s['key'] == 'whatsapp' && text != null) url = '$url?text=${Uri.encodeComponent(text)}';
                openUrl(url);
              },
            ),
          for (final p in phones)
            ListTile(
              leading: Icon(Icons.call_rounded, color: socialColor('phone')),
              title: Text('تماس ${faDigits(p)}', style: const TextStyle(fontWeight: FontWeight.w800)),
              onTap: () {
                Navigator.pop(c);
                launchUrl(Uri.parse('tel:${p.replaceAll(RegExp(r'[^\d+]'), '')}'));
              },
            ),
        ]),
      ),
    ),
  );
}
