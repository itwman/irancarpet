import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';

class CheckoutScreen extends StatefulWidget {
  const CheckoutScreen({super.key});
  @override
  State<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends State<CheckoutScreen> {
  final _f = <String, TextEditingController>{
    for (final k in ['first_name', 'last_name', 'mobile', 'city', 'address', 'postal_code', 'note']) k: TextEditingController(),
  };
  String? _province, _gateway;
  String _mode = 'full';
  Json? _quote;
  Map<String, dynamic> _errors = {};
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    final u = context.read<Auth>().user ?? {};
    for (final k in ['first_name', 'last_name', 'mobile', 'city', 'address', 'postal_code']) {
      _f[k]!.text = (u[k] ?? '') as String;
    }
    final prov = (u['province'] ?? '') as String;
    _province = prov.isEmpty ? null : prov;
    Api.i.post('/cart/quote/', {'items': context.read<Cart>().payload}).then((q) {
      if (mounted) setState(() => _quote = q as Json);
    }).catchError((_) {});
  }

  @override
  void dispose() {
    for (final c in _f.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _submit() async {
    final cfg = context.read<AppConfig>();
    final cart = context.read<Cart>();
    _gateway ??= cfg.gateways.isNotEmpty ? cfg.gateways.first['key'] as String : null;
    setState(() => (_busy = true, _errors = {}));
    try {
      final r = await Api.i.post('/orders/create/', {
        'items': cart.payload,
        for (final e in _f.entries) e.key: latin(e.value.text.trim()),
        'province': _province ?? '',
        'payment_mode': _mode,
        'gateway': _gateway ?? '',
      }) as Json;
      final order = r['order'] as Json;
      await launchUrl(Uri.parse(r['pay_url'] as String), mode: LaunchMode.externalApplication);
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
            decoration: InputDecoration(hintText: hint, errorText: _errors[key] as String?),
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
    final pay = _mode == 'deposit' ? deposit : total;
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
        const SectionHead('نحوهٔ پرداخت'),
        if (shop['allow_full'] != false)
          _choice('full', 'پرداخت کامل آنلاین', q?['free_shipping'] == true ? 'ارسال رایگان' : 'هزینهٔ ارسال موقع تحویل', total),
        if (shop['allow_deposit'] != false)
          _choice('deposit', 'بیعانهٔ ${faDigits(shop['deposit_percent'] ?? 10)}٪', 'بقیهٔ مبلغ و هزینهٔ ارسال موقع تحویل', deposit),
        if (_errors['payment_mode'] != null) Text(_errors['payment_mode'] as String, style: const TextStyle(color: C.pinkDark)),
        if (gws.length > 1) ...[
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
            onPressed: _busy || gws.isEmpty ? null : _submit,
            child: _busy
                ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white))
                : Text(gws.isEmpty ? 'درگاه پرداخت فعال نیست' : 'پرداخت ${toman(pay)}'),
          ),
        ),
      ),
    );
  }

  Widget _choice(String key, String title, String sub, int amount) {
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
              Price(amount, size: 14),
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
