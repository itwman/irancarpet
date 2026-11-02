import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'questions.dart';
import 'quick.dart';
import 'stats.dart';
import 'ui.dart';

/// بیشتر: آمار، پرسش‌ها و بخش‌هایی که فعلاً در پنل سایت است (ظاهر ویترین، قفسه، فرصت ویژه، کد تخفیف، تسویه)
class SellerMore extends StatelessWidget {
  const SellerMore({super.key, required this.seller, required this.onLogout});
  final Json seller;
  final VoidCallback onLogout;

  void _web(String path) => launchUrl(Uri.parse('$kSite$path'), mode: LaunchMode.externalApplication);

  @override
  Widget build(BuildContext context) {
    final inApp = <(IconData, String, String, Widget)>[
      (Icons.insights_rounded, 'آمار فروشگاه', 'بازدید، سفارش و فروش با نمودار', const SellerStats()),
      (Icons.help_outline_rounded, 'پرسش‌های مشتریان', 'پاسخ به پرسش‌ها زیر هر کالا', const SellerQuestions()),
      (Icons.add_a_photo_outlined, 'افزودن با عکس', 'چند فرش را یکجا با عکس اضافه کنید', const SellerQuick()),
    ];
    const onWeb = [
      (Icons.palette_outlined, 'ظاهر ویترین', 'لوگو، کاور، اسلایدها و رنگ فروشگاه', '/seller/look/'),
      (Icons.view_agenda_outlined, 'قفسه‌ها', 'دسته‌بندی کالاها در ویترین', '/seller/shelves/'),
      (Icons.local_fire_department_outlined, 'فرصت ویژه', 'تخفیف زمان‌دار روی کالاها', '/seller/offers/'),
      (Icons.sell_outlined, 'کد تخفیف', 'کد تخفیف ویژهٔ مشتریان شما', '/seller/coupons/'),
      (Icons.account_balance_wallet_outlined, 'حساب و تسویه', 'واریزها و شبای حساب', '/seller/finance/'),
      (Icons.settings_outlined, 'تنظیمات فروشگاه', 'ارسال، مرجوعی و اطلاعات تماس', '/seller/settings/'),
    ];
    return Scaffold(
      appBar: AppBar(title: const Text('بیشتر')),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
        Panel(
          child: Row(children: [
            SizedBox(width: 52, height: 52, child: NetImage('${seller['logo'] ?? ''}', radius: 12, fit: BoxFit.contain)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('${seller['name']}', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
                Text(seller['status'] == 'paused' ? 'تعطیل موقت' : 'فروشگاه باز است',
                    style: TextStyle(color: seller['status'] == 'paused' ? const Color(0xFFB45309) : const Color(0xFF178A4C), fontSize: 13)),
              ]),
            ),
            TextButton(onPressed: () => _web('${seller['url']}'), child: const Text('ویترین')),
          ]),
        ),
        const SizedBox(height: 14),
        Panel(
          padding: EdgeInsets.zero,
          child: Column(children: [
            for (final (icon, title, sub, page) in inApp)
              ListTile(
                leading: Icon(icon, color: C.pinkDark),
                title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(sub, style: const TextStyle(fontSize: 12.5)),
                trailing: const Icon(Icons.chevron_left_rounded, color: C.muted),
                onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => page)),
              ),
          ]),
        ),
        const SizedBox(height: 18),
        const Text('در پنل سایت', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900)),
        const Text('این بخش‌ها در مرورگر باز می‌شوند (همان شمارهٔ موبایل برای ورود).', style: TextStyle(color: C.muted, fontSize: 12.5)),
        const SizedBox(height: 8),
        Panel(
          padding: EdgeInsets.zero,
          child: Column(children: [
            for (final (icon, title, sub, path) in onWeb)
              ListTile(
                leading: Icon(icon, color: C.tealDark),
                title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
                subtitle: Text(sub, style: const TextStyle(fontSize: 12.5)),
                trailing: const Icon(Icons.open_in_new_rounded, size: 18, color: C.muted),
                onTap: () => _web(path),
              ),
          ]),
        ),
        const SizedBox(height: 18),
        OutlinedButton.icon(
          onPressed: () async {
            final ok = await showDialog<bool>(
              context: context,
              builder: (c) => AlertDialog(
                content: const Text('از حساب فروشندگی خارج می‌شوید؟'),
                actions: [
                  TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('انصراف')),
                  TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('خروج')),
                ],
              ),
            );
            if (ok != true || !context.mounted) return;
            await context.read<Auth>().logout();
            onLogout();
          },
          icon: const Icon(Icons.logout_rounded),
          label: const Text('خروج از حساب'),
        ),
        const SizedBox(height: 10),
        Text('نسخهٔ ${kAppVersion.replaceAll('.', '٫')}', textAlign: TextAlign.center, style: const TextStyle(color: C.muted, fontSize: 12)),
      ]),
    );
  }
}
