import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'common.dart';

/// دکمه‌های «ویدیوی فرش» و «خبرم کن» در صفحهٔ فرش
class ProductExtras extends StatelessWidget {
  const ProductExtras(this.p, {super.key});
  final Json p;

  @override
  Widget build(BuildContext context) {
    final video = p['video'] as Json?;
    final stock = p['purchasable'] != true;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
      child: Wrap(spacing: 8, runSpacing: 8, children: [
        if (video != null)
          ActionChip(
            avatar: const Icon(Icons.play_circle_fill_rounded, color: C.pink),
            label: const Text('ویدیوی فرش'),
            onPressed: () => launchUrl(Uri.parse(video['url'] as String), mode: LaunchMode.externalApplication),
          ),
        ActionChip(
          avatar: Icon(stock ? Icons.notifications_active_outlined : Icons.trending_down_rounded, color: C.tealDark),
          label: Text(stock ? 'موجود شد خبرم کن' : 'ارزان شد خبرم کن'),
          onPressed: () => _alert(context, stock ? 'stock' : 'price'),
        ),
      ]),
    );
  }

  Future<void> _alert(BuildContext context, String kind) async {
    final auth = context.read<Auth>();
    String? mobile;
    if (!auth.loggedIn) {
      final c = TextEditingController();
      mobile = await showDialog<String>(
        context: context,
        builder: (d) => AlertDialog(
          title: Text(kind == 'stock' ? 'وقتی موجود شد خبرت می‌کنیم' : 'وقتی ارزان شد خبرت می‌کنیم'),
          content: TextField(
            controller: c,
            keyboardType: TextInputType.phone,
            textDirection: TextDirection.ltr,
            autofocus: true,
            decoration: const InputDecoration(hintText: '۰۹۱۲۱۲۳۴۵۶۷'),
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(d), child: const Text('انصراف')),
            FilledButton(onPressed: () => Navigator.pop(d, latin(c.text)), child: const Text('ثبت')),
          ],
        ),
      );
      if (mobile == null || mobile.trim().isEmpty) return;
    }
    try {
      final r = await Api.i.post('/alerts/', {'product': p['id'], 'kind': kind, 'mobile': ?mobile}) as Json;
      if (context.mounted) toast(context, r['message'] as String);
    } on ApiError catch (e) {
      if (context.mounted) toast(context, e.message);
    }
  }
}

/// برگهٔ ثبت نظر با عکس
Future<void> showReviewSheet(BuildContext context, int productId) async {
  if (!context.read<Auth>().loggedIn) {
    final ok = await Navigator.pushNamed(context, '/login', arguments: 'برای ثبت نظر وارد شوید') == true;
    if (!ok || !context.mounted) return;
  }
  await showModalBottomSheet(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: Colors.white,
    builder: (_) => _ReviewSheet(productId: productId),
  );
}

class _ReviewSheet extends StatefulWidget {
  const _ReviewSheet({required this.productId});
  final int productId;
  @override
  State<_ReviewSheet> createState() => _ReviewSheetState();
}

class _ReviewSheetState extends State<_ReviewSheet> {
  int _rating = 0;
  final _text = TextEditingController();
  final _photos = <Uint8List>[];
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    try {
      final xs = await ImagePicker().pickMultiImage(maxWidth: 1600, imageQuality: 84, limit: 4);
      for (final x in xs.take(4 - _photos.length)) {
        _photos.add(await x.readAsBytes());
      }
      if (mounted) setState(() {});
    } catch (_) {}
  }

  Future<void> _send() async {
    if (_rating == 0 && _text.text.trim().length < 5) {
      toast(context, 'امتیاز بدهید یا چند کلمه بنویسید.');
      return;
    }
    setState(() => _busy = true);
    try {
      final r = await Api.i.postMultipart('/products/${widget.productId}/reviews/', {
        'rating': '$_rating',
        'text': _text.text.trim(),
      }, {
        for (var i = 0; i < _photos.length; i++) 'photo_$i': (_photos[i].toList(), 'photo$i.jpg'),
      }) as Json;
      if (!mounted) return;
      Navigator.pop(context);
      toast(context, r['message'] as String);
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('نظر شما دربارهٔ این فرش', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          for (var i = 1; i <= 5; i++)
            IconButton(
              iconSize: 36,
              tooltip: '${faDigits(i)} ستاره',
              onPressed: () => setState(() => _rating = i),
              icon: Icon(i <= _rating ? Icons.star_rounded : Icons.star_outline_rounded, color: C.saffron),
            ),
        ]),
        TextField(controller: _text, minLines: 3, maxLines: 6, decoration: const InputDecoration(hintText: 'کیفیت، رنگ، ارسال…')),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (var i = 0; i < _photos.length; i++)
            Stack(children: [
              ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.memory(_photos[i], width: 72, height: 72, fit: BoxFit.cover)),
              Positioned(
                top: -6,
                left: -6,
                child: IconButton(
                  iconSize: 18,
                  onPressed: () => setState(() => _photos.removeAt(i)),
                  icon: const Icon(Icons.cancel_rounded, color: Colors.white, shadows: [Shadow(blurRadius: 6)]),
                ),
              ),
            ]),
          if (_photos.length < 4)
            InkWell(
              onTap: _pick,
              borderRadius: BorderRadius.circular(12),
              child: Container(
                width: 72,
                height: 72,
                decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(12)),
                child: const Icon(Icons.add_a_photo_outlined, color: C.ink2),
              ),
            ),
        ]),
        const Padding(
          padding: EdgeInsets.only(top: 6),
          child: Text('عکس فرش در خانه‌تان به خریداران دیگر خیلی کمک می‌کند.', style: TextStyle(color: C.muted, fontSize: 12)),
        ),
        const SizedBox(height: 14),
        FilledButton(
          onPressed: _busy ? null : _send,
          child: _busy
              ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
              : const Text('ثبت نظر'),
        ),
      ]),
    );
  }
}

/// برگهٔ «دعوت از دوستان» (کد معرفی و کدهای هدیه)
Future<void> showReferralSheet(BuildContext context) async {
  if (!context.read<Auth>().loggedIn) {
    final ok = await Navigator.pushNamed(context, '/login', arguments: 'برای گرفتن کد معرفی وارد شوید') == true;
    if (!ok || !context.mounted) return;
  }
  Json d;
  try {
    d = await Api.i.get('/referral/') as Json;
  } on ApiError catch (e) {
    if (context.mounted) toast(context, e.message);
    return;
  }
  if (!context.mounted) return;
  final gifts = ((d['gifts'] as List?) ?? []).cast<Json>();
  await showModalBottomSheet(
    context: context,
    showDragHandle: true,
    backgroundColor: Colors.white,
    builder: (c) => SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          if (d['enabled'] == true) ...[
            const Text('دوستانت را دعوت کن', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
            const SizedBox(height: 6),
            Text(
              'دوستت با کد تو در اولین خرید ${faDigits(d['percent'])}٪ تخفیف می‌گیرد (تا ${toman(d['max'] as int)}) '
              'و بعد از خریدش، یک کد هدیهٔ ${toman(d['reward'] as int)} برای تو فرستاده می‌شود.',
              style: const TextStyle(color: C.ink2, height: 1.8),
            ),
            const SizedBox(height: 14),
            Container(
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(16)),
              alignment: Alignment.center,
              child: SelectableText(d['code'] as String,
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, letterSpacing: 2, fontFamily: 'monospace')),
            ),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {
                    Clipboard.setData(ClipboardData(text: d['code'] as String));
                    toast(c, 'کد کپی شد');
                  },
                  icon: const Icon(Icons.copy_rounded),
                  label: const Text('کپی کد'),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: FilledButton.icon(
                  onPressed: () => SharePlus.instance.share(ShareParams(text: d['share'] as String)),
                  icon: const Icon(Icons.share_rounded),
                  label: const Text('فرستادن برای دوست'),
                ),
              ),
            ]),
          ] else
            const Text('کد معرفی فعلاً فعال نیست.', style: TextStyle(color: C.muted)),
          if (gifts.isNotEmpty) ...[
            const SizedBox(height: 18),
            const Text('کدهای هدیهٔ تو', style: TextStyle(fontWeight: FontWeight.w900)),
            for (final g in gifts)
              ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.card_giftcard_rounded, color: C.pink),
                title: Text(g['code'] as String, textDirection: TextDirection.ltr, textAlign: TextAlign.right),
                subtitle: Text(faDigits(g['label'])),
                onTap: () {
                  Clipboard.setData(ClipboardData(text: g['code'] as String));
                  toast(c, 'کد کپی شد؛ در مرحلهٔ پرداخت بزنید.');
                },
              ),
          ],
        ]),
      ),
    ),
  );
}
