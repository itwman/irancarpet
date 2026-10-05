import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/installment.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key, this.initialMode});
  final String? initialMode;
  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _f = <String, TextEditingController>{
    for (final k in ['first_name', 'last_name', 'mobile', 'city', 'address', 'postal_code', 'note']) k: TextEditingController(),
  };
  String? _province, _gateway;
  late String _mode = widget.initialMode ?? 'full';
  Json? _quote;
  final _couponC = TextEditingController();
  String _coupon = '';
  bool _couponBusy = false;
  Map<String, dynamic> _errors = {};
  bool _busy = false;
  // خرید اقساطی
  InstallmentChoice? _inst;
  Json? _instQuote;
  final _docs = <String, TextEditingController>{};
  String? _pensioner;
  Uint8List? _image;
  String _imageName = 'cheque.jpg';

  TextEditingController _doc(String key) => _docs.putIfAbsent(key, () {
        final c = TextEditingController();
        if (key == 'holder_name') {
          c.text = '${_f['first_name']!.text} ${_f['last_name']!.text}'.trim();
        }
        return c;
      });

  bool get _payNowInstallment =>
      _inst != null && _instQuote != null && _inst!.payAtCheckout && (_instQuote!['down'] as int) > 0;

  @override
  void initState() {
    super.initState();
    final u = context.read<Auth>().user ?? {};
    for (final k in ['first_name', 'last_name', 'mobile', 'city', 'address', 'postal_code']) {
      _f[k]!.text = (u[k] ?? '') as String;
    }
    final prov = (u['province'] ?? '') as String;
    _province = prov.isEmpty ? null : prov;
    _requote();
  }

  Future<void> _requote([String? code]) async {
    final c = (code ?? _coupon).trim().toUpperCase();
    setState(() => _couponBusy = true);
    try {
      final q = await Api.i.post('/cart/quote/', {'items': context.read<Cart>().payload, if (c.isNotEmpty) 'coupon': c}) as Json;
      if (!mounted) return;
      final err = q['coupon_error'] as String? ?? '';
      setState(() {
        _quote = q;
        _coupon = err.isEmpty ? c : '';
        _inst = null;
        _instQuote = null;
      });
      if (err.isNotEmpty) toast(context, err);
      if (err.isEmpty && c.isNotEmpty) toast(context, 'کد تخفیف اعمال شد.');
    } catch (_) {}
    if (mounted) setState(() => _couponBusy = false);
  }

  @override
  void dispose() {
    _couponC.dispose();
    for (final c in [..._f.values, ..._docs.values]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _pickImage() async {
    final src = await showModalBottomSheet<ImageSource>(
      context: context,
      showDragHandle: true,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(leading: const Icon(Icons.photo_camera_outlined), title: const Text('عکس گرفتن با دوربین'),
              onTap: () => Navigator.pop(c, ImageSource.camera)),
          ListTile(leading: const Icon(Icons.photo_library_outlined), title: const Text('انتخاب از گالری'),
              onTap: () => Navigator.pop(c, ImageSource.gallery)),
        ]),
      ),
    );
    if (src == null) return;
    final x = await ImagePicker().pickImage(source: src, maxWidth: 2200, imageQuality: 88);
    if (x == null) return;
    final bytes = await x.readAsBytes();
    if (mounted) setState(() => (_image = bytes, _imageName = x.name.isEmpty ? 'cheque.jpg' : x.name, _errors.remove('inst_cheque_image')));
  }

  Future<void> _submit() async {
    final cfg = context.read<AppConfig>();
    final cart = context.read<Cart>();
    _gateway ??= cfg.gateways.isNotEmpty ? cfg.gateways.first['key'] as String : null;
    setState(() => (_busy = true, _errors = {}));
    try {
      final fields = <String, String>{
        for (final e in _f.entries) e.key: latin(e.value.text.trim()),
        'province': _province ?? '',
        'payment_mode': _mode,
        'gateway': _gateway ?? '',
        if (_coupon.isNotEmpty) 'coupon': _coupon,
      };
      dynamic r;
      if (_mode == 'installment') {
        final c = _inst;
        if (c == null) throw ApiError('اول اقساط را حساب کنید.');
        fields.addAll({'inst_plan': '${c.planId}', 'inst_down': '${c.down}', 'inst_months': '${c.months}', 'inst_step': '${c.step}'});
        for (final f in (c.plan['fields'] as List).cast<Json>()) {
          final key = f['key'] as String;
          if (f['type'] == 'image') continue;
          fields['inst_$key'] = f['type'] == 'pensioner' ? (_pensioner ?? '') : latin(_doc(key).text.trim());
        }
        final img = _image;
        r = await Api.i.postMultipart('/orders/create/', {...fields, 'items': jsonEncode(cart.payload)},
            img == null ? {} : {'inst_cheque_image': (img, _imageName)});
      } else {
        r = await Api.i.post('/orders/create/', {...fields, 'items': cart.payload});
      }
      final order = (r as Json)['order'] as Json;
      final payUrl = r['pay_url'] as String?;
      if (payUrl == null) {
        await cart.clear();
        if (!mounted) return;
        toast(context, 'درخواست خرید اقساطی ثبت شد؛ نتیجه را با پیامک خبر می‌دهیم.');
        Navigator.pushNamedAndRemoveUntil(context, '/order', (route) => route.isFirst, arguments: {'number': order['number']});
        return;
      }
      await launchUrl(Uri.parse(payUrl), mode: LaunchMode.externalApplication);
      if (!mounted) return;
      Navigator.pushNamedAndRemoveUntil(context, '/order', (route) => route.isFirst, arguments: {'number': order['number']});
    } on ApiError catch (e) {
      setState(() => _errors = e.errors);
      if (mounted) toast(context, e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _field(String key, String label, {TextInputType? type, int lines = 1, String? hint}) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          FieldLabel(label),
          TextField(
            controller: _f[key],
            keyboardType: type,
            maxLines: lines,
            textDirection: type == null ? null : TextDirection.ltr,
            textAlign: type == null ? TextAlign.start : TextAlign.right,
            decoration: InputDecoration(
                hintText: hint, hintTextDirection: type == null ? null : TextDirection.ltr, errorText: _errors[key] as String?),
          ),
        ],
      );

  @override
  Widget build(BuildContext context) {
    final cfg = context.watch<AppConfig>();
    final shop = cfg.shop;
    final q = _quote;
    final total = (q?['total'] as int?) ?? context.read<Cart>().roughTotal;
    final deposit = (q?['deposit'] as int?) ?? 0;
    final gws = cfg.gateways;
    _gateway ??= gws.isNotEmpty ? gws.first['key'] as String : null;
    final plans = cfg.installmentPlans;
    final inst = _mode == 'installment';
    final pay = inst ? (_payNowInstallment ? _instQuote!['down'] as int : 0) : (_mode == 'deposit' ? deposit : total);
    final needGateway = !inst || pay > 0;
    final canSubmit = !_busy && (!needGateway || gws.isNotEmpty) && (!inst || _instQuote != null);
    final label = inst
        ? (pay > 0 ? 'پرداخت پیش‌پرداخت ${toman(pay)}' : 'ثبت درخواست خرید اقساطی')
        : (gws.isEmpty ? 'درگاه پرداخت فعال نیست' : 'پرداخت ${toman(pay)}');
    return Scaffold(
      appBar: AppBar(title: const Text('ثبت سفارش')),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 24), children: [
        const SectionHead('نشانی تحویل'),
        Row(children: [
          Expanded(child: _field('first_name', 'نام')),
          const SizedBox(width: 10),
          Expanded(child: _field('last_name', 'نام خانوادگی')),
        ]),
        _field('mobile', 'موبایل', type: TextInputType.phone, hint: '۰۹۱۲۱۲۳۴۵۶۷'),
        const FieldLabel('استان'),
        DropdownButtonFormField<String>(
          initialValue: cfg.provinces.contains(_province) ? _province : null,
          isExpanded: true,
          items: [for (final p in cfg.provinces) DropdownMenuItem(value: p, child: Text(p))],
          onChanged: (v) => setState(() => _province = v),
          decoration: InputDecoration(errorText: _errors['province'] as String?, hintText: 'انتخاب استان'),
        ),
        _field('city', 'شهر'),
        _field('address', 'نشانی کامل', lines: 3),
        _field('postal_code', 'کد پستی (اختیاری)', type: TextInputType.number),
        _field('note', 'توضیح برای فروشگاه (اختیاری)', lines: 2),
        const SectionHead('کد تخفیف'),
        Row(children: [
          Expanded(
            child: TextField(
              controller: _couponC,
              enabled: _coupon.isEmpty,
              textDirection: TextDirection.ltr,
              textCapitalization: TextCapitalization.characters,
              decoration: InputDecoration(hintText: 'کد تخفیف یا کد معرفی دوست', errorText: _errors['coupon'] as String?),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.tonal(
            style: FilledButton.styleFrom(minimumSize: const Size(84, 52)),
            onPressed: _couponBusy
                ? null
                : () {
                    if (_coupon.isNotEmpty) {
                      _couponC.clear();
                      _coupon = '';
                      _requote('');
                    } else if (_couponC.text.trim().isNotEmpty) {
                      _requote(latin(_couponC.text));
                    }
                  },
            child: Text(_coupon.isNotEmpty ? 'حذف' : 'اعمال'),
          ),
        ]),
        if (((q?['discount'] as int?) ?? 0) > 0)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text('تخفیف ${q!['coupon']?['code'] ?? ''}: ${toman(q['discount'] as int)} — مبلغ نهایی ${toman(total)}',
                style: const TextStyle(color: C.tealDark, fontWeight: FontWeight.w800)),
          ),
        const SectionHead('نحوهٔ پرداخت'),
        if (shop['allow_full'] != false)
          _choice('full', 'پرداخت کامل آنلاین', q?['free_shipping'] == true ? 'ارسال رایگان' : 'هزینهٔ ارسال موقع تحویل', total),
        if (shop['allow_deposit'] != false)
          _choice('deposit', 'بیعانهٔ ${faDigits(shop['deposit_percent'] ?? 10)}٪', 'بقیهٔ مبلغ و هزینهٔ ارسال موقع تحویل', deposit),
        if (plans.isNotEmpty) _choice('installment', 'خرید اقساطی', plans.map((p) => p['title']).join('، '), null),
        if (inst && plans.isNotEmpty) ...[
          const SizedBox(height: 6),
          InstallmentCalc(
            plans: plans,
            total: total,
            onChanged: (c, q) => setState(() => (_inst = c, _instQuote = q)),
          ),
          if (_inst != null) ..._docsSection(_inst!.plan),
        ],
        if (_errors['payment_mode'] != null) Text(_errors['payment_mode'] as String, style: const TextStyle(color: C.pinkDark)),
        if (gws.length > 1 && needGateway) ...[
          const SectionHead('درگاه پرداخت'),
          Wrap(spacing: 8, children: [
            for (final g in gws)
              ChoiceChip(
                selected: _gateway == g['key'],
                showCheckmark: false,
                label: Text(g['name'] as String),
                onSelected: (_) => setState(() => _gateway = g['key'] as String),
              ),
          ]),
        ],
        if (_errors['cart'] != null)
          Padding(padding: const EdgeInsets.only(top: 12), child: Text(_errors['cart'] as String, style: const TextStyle(color: C.pinkDark))),
        if ((shop['note'] as String? ?? '').isNotEmpty)
          Padding(padding: const EdgeInsets.only(top: 14), child: Text(shop['note'] as String, style: const TextStyle(color: C.muted, fontSize: 12.5))),
      ]),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
          child: FilledButton(
            onPressed: canSubmit ? _submit : null,
            child: _busy
                ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
                : Text(label),
          ),
        ),
      ),
    );
  }

  List<Widget> _docsSection(Json plan) {
    final fields = (plan['fields'] as List).cast<Json>();
    if (fields.isEmpty) return const [];
    return [
      const SectionHead('مشخصات و مدارک'),
      if ((plan['submit_note'] as String? ?? '').isNotEmpty)
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(14)),
          child: Text(plan['submit_note'] as String, style: const TextStyle(height: 1.8, fontSize: 13)),
        ),
      for (final f in fields) _docField(f, plan),
      if (plan['pay_at'] == 'approval')
        const Padding(
          padding: EdgeInsets.only(top: 10),
          child: Text('پیش‌پرداخت بعد از تأیید مدارک از صفحهٔ سفارش پرداخت می‌شود.', style: TextStyle(color: C.muted, fontSize: 12.5)),
        ),
    ];
  }

  Widget _docField(Json f, Json plan) {
    final key = f['key'] as String, type = f['type'] as String, label = f['label'] as String;
    final err = _errors['inst_$key'] as String?;
    if (type == 'image') {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FieldLabel(label),
        InkWell(
          onTap: _pickImage,
          borderRadius: BorderRadius.circular(16),
          child: Container(
            height: _image == null ? 96 : 170,
            width: double.infinity,
            decoration: BoxDecoration(
              color: C.soft,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: err != null ? C.pink : C.line, width: 1.6),
            ),
            clipBehavior: Clip.antiAlias,
            child: _image == null
                ? const Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                    Icon(Icons.add_a_photo_outlined, color: C.ink2, size: 28),
                    SizedBox(height: 4),
                    Text('عکس یک برگ چک', style: TextStyle(color: C.ink2, fontWeight: FontWeight.w700)),
                  ])
                : Stack(fit: StackFit.expand, children: [
                    Image.memory(_image!, fit: BoxFit.cover),
                    const Align(
                      alignment: AlignmentDirectional.bottomStart,
                      child: Padding(
                        padding: EdgeInsets.all(8),
                        child: Chip(label: Text('تغییر عکس'), avatar: Icon(Icons.edit, size: 16)),
                      ),
                    ),
                  ]),
          ),
        ),
        const Padding(
          padding: EdgeInsets.only(top: 4),
          child: Text('فقط مدیران فروشگاه این تصویر را می‌بینند.', style: TextStyle(color: C.muted, fontSize: 11.5)),
        ),
        if (err != null) Text(err, style: const TextStyle(color: C.pinkDark, fontSize: 12)),
      ]);
    }
    if (type == 'pensioner') {
      final choices = ((plan['pensioner_choices'] as List?) ?? const ['بازنشسته', 'مستمری‌بگیر']).cast<String>();
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        FieldLabel(label),
        Wrap(spacing: 8, children: [
          for (final c in choices)
            ChoiceChip(
              label: Text(c),
              selected: _pensioner == c,
              showCheckmark: false,
              onSelected: (_) => setState(() => _pensioner = c),
            ),
        ]),
        if (err != null) Text(err, style: const TextStyle(color: C.pinkDark, fontSize: 12)),
      ]);
    }
    final numeric = type != 'text';
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      FieldLabel(label),
      TextField(
        controller: _doc(key),
        keyboardType: numeric ? TextInputType.number : TextInputType.text,
        textDirection: numeric ? TextDirection.ltr : null,
        textAlign: numeric ? TextAlign.right : TextAlign.start,
        maxLength: switch (type) { 'national_code' => 10, 'sayad' => 16, 'mobile' => 11, _ => null },
        decoration: InputDecoration(
          counterText: '',
          errorText: err,
          hintText: type == 'mobile' ? '۰۹۱۲۱۲۳۴۵۶۷' : null,
          hintTextDirection: numeric ? TextDirection.ltr : null,
        ),
      ),
    ]);
  }

  Widget _choice(String key, String title, String sub, int? amount) {
    final on = _mode == key;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: on ? C.pinkTint : C.soft,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: on ? C.pink : Colors.transparent, width: 1.6)),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => setState(() => _mode = key),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(children: [
              Icon(on ? Icons.radio_button_checked : Icons.radio_button_off, color: on ? C.pink : C.muted),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(title, style: const TextStyle(fontWeight: FontWeight.w800)),
                  Text(sub, style: const TextStyle(color: C.muted, fontSize: 12.5)),
                ]),
              ),
              if (amount != null) Price(amount, size: 14) else const Icon(Icons.calendar_month_rounded, color: C.ink2),
            ]),
          ),
        ),
      ),
    );
  }
}

class SectionHead extends StatelessWidget {
  const SectionHead(this.t, {super.key});
  final String t;
  @override
  Widget build(BuildContext context) =>
      Padding(padding: const EdgeInsets.only(top: 22, bottom: 4), child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)));
}
