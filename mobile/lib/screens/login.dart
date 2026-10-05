import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/brand.dart';
import '../widgets/common.dart';

/// ورود با کد پیامکی (یا رمز). موفقیت: Navigator.pop(context, true)
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, this.reason});
  final String? reason;
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _mobile = TextEditingController(), _code = TextEditingController(), _name = TextEditingController();
  final _ident = TextEditingController(), _pass = TextEditingController();
  int _step = 0; // ۰ موبایل، ۱ کد، ۲ رمز
  bool _busy = false, _isNew = false;
  String? _err, _sentTo;
  int _wait = 0;
  Timer? _timer;

  @override
  void dispose() {
    _timer?.cancel();
    for (final c in [_mobile, _code, _name, _ident, _pass]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _run(Future<void> Function() fn) async {
    setState(() => (_busy = true, _err = null));
    try {
      await fn();
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _send() => _run(() async {
        final r = await Api.i.post('/auth/otp/', {'mobile': latin(_mobile.text)}) as Json;
        _sentTo = r['mobile'] as String;
        _isNew = r['is_new'] as bool? ?? false;
        if (r['dev_code'] != null) _code.text = '${r['dev_code']}';
        _step = 1;
        _wait = 60;
        _timer?.cancel();
        _timer = Timer.periodic(const Duration(seconds: 1), (t) {
          if (!mounted || _wait <= 0) return t.cancel();
          setState(() => _wait--);
        });
      });

  Future<void> _done(Json data) async {
    await context.read<Auth>().signIn(data);
    if (!mounted) return;
    context.read<Wishlist>().sync();
    Navigator.pop(context, true);
  }

  Future<void> _verify() => _run(() async {
        final r = await Api.i.post('/auth/verify/', {'mobile': _sentTo, 'code': latin(_code.text), 'name': _name.text.trim(), 'device': 'android'}) as Json;
        await _done(r);
      });

  Future<void> _password() => _run(() async {
        final r = await Api.i.post('/auth/password/', {'identifier': latin(_ident.text.trim()), 'password': _pass.text, 'device': 'android'}) as Json;
        await _done(r);
      });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(),
      body: ListView(padding: const EdgeInsets.fromLTRB(24, 0, 24, 24), children: [
        Center(child: kIsFinder ? Image.asset('assets/brand/finder.png', height: 84) : const BrandLogo(size: 76)),
        const SizedBox(height: 16),
        Text(
          _step == 1 ? 'کد تأیید را وارد کنید' : (_step == 2 ? 'ورود با رمز' : 'ورود یا ثبت‌نام'),
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900),
        ),
        const SizedBox(height: 6),
        Text(
          _step == 1 ? 'کد ۵ رقمی به ${faDigits(_sentTo ?? '')} پیامک شد.' : (widget.reason ?? 'با شمارهٔ موبایلتان وارد شوید؛ اگر حساب ندارید، همین‌جا ساخته می‌شود.'),
          textAlign: TextAlign.center,
          style: const TextStyle(color: C.muted),
        ),
        const SizedBox(height: 24),
        if (_step == 0) ...[
          TextField(
            controller: _mobile,
            keyboardType: TextInputType.phone,
            autofillHints: const [AutofillHints.telephoneNumber],
            textDirection: TextDirection.ltr,
            textAlign: TextAlign.center,
            style: const TextStyle(fontSize: 20, letterSpacing: 2, fontWeight: FontWeight.w700),
            decoration: const InputDecoration(hintText: '۰۹۱۲ ۱۲۳ ۴۵۶۷', hintTextDirection: TextDirection.ltr),
            onSubmitted: (_) => _send(),
          ),
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _send, child: _busy ? const _Spin() : const Text('دریافت کد ورود')),
          TextButton(onPressed: () => setState(() => (_step = 2, _err = null)), child: const Text('ورود با رمز')),
        ],
        if (_step == 1) ...[
          TextField(
            controller: _code,
            autofocus: true,
            keyboardType: TextInputType.number,
            autofillHints: const [AutofillHints.oneTimeCode],
            textDirection: TextDirection.ltr,
            textAlign: TextAlign.center,
            maxLength: 5,
            inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9۰-۹]'))],
            style: const TextStyle(fontSize: 28, letterSpacing: 14, fontWeight: FontWeight.w900),
            decoration: const InputDecoration(counterText: '', hintText: '-----'),
            onChanged: (v) {
              if (v.length == 5 && !_isNew) _verify();
            },
          ),
          if (_isNew) ...[
            const FieldLabel('نام و نام خانوادگی'),
            TextField(controller: _name, textInputAction: TextInputAction.done, onSubmitted: (_) => _verify()),
          ],
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _verify, child: _busy ? const _Spin() : const Text('ورود')),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            TextButton(onPressed: () => setState(() => (_step = 0, _err = null)), child: const Text('تغییر شماره')),
            TextButton(
              onPressed: _wait > 0 || _busy ? null : _send,
              child: Text(_wait > 0 ? 'ارسال دوباره (${faDigits(_wait)})' : 'ارسال دوباره'),
            ),
          ]),
        ],
        if (_step == 2) ...[
          TextField(controller: _ident, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(hintText: 'موبایل یا ایمیل')),
          const SizedBox(height: 10),
          TextField(controller: _pass, obscureText: true, decoration: const InputDecoration(hintText: 'رمز'), onSubmitted: (_) => _password()),
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _password, child: _busy ? const _Spin() : const Text('ورود')),
          TextButton(onPressed: () => setState(() => (_step = 0, _err = null)), child: const Text('ورود با کد پیامکی')),
        ],
        if (_err != null)
          Container(
            margin: const EdgeInsets.only(top: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: C.pinkTint, borderRadius: BorderRadius.circular(12)),
            child: Text(_err!, style: const TextStyle(color: C.pinkDark)),
          ),
      ]),
    );
  }
}

class _Spin extends StatelessWidget {
  const _Spin();
  @override
  Widget build(BuildContext context) =>
      const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white));
}
