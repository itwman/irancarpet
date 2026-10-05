import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';

/// انتخاب کاربر در ماشین‌حساب اقساط
class InstallmentChoice {
  InstallmentChoice(this.plan, this.down, this.step, this.months);
  final Json plan;
  final int down, step, months;
  int get planId => plan['id'] as int;
  bool get payAtCheckout => plan['pay_at'] != 'approval';
}

String _pct(num v) => '${faDigits(v % 1 == 0 ? v.toInt() : v)}٪';

String million(num n) {
  final m = n / 1e6;
  final s = m >= 10 ? m.toStringAsFixed(1) : m.toStringAsFixed(2);
  return '${faDigits(s.replaceAll(RegExp(r'\.?0+$'), '').replaceAll('.', '٫'))} میلیون';
}

/// ماشین‌حساب اقساط: روش، پیش‌پرداخت، فاصله و مدت؛ محاسبهٔ اصلی روی سرور (راس‌گیری).
class InstallmentCalc extends StatefulWidget {
  const InstallmentCalc({super.key, required this.plans, required this.total, this.onChanged, this.initialPlan});
  final List<Json> plans;
  final int total;
  final int? initialPlan;
  final void Function(InstallmentChoice? choice, Json? quote)? onChanged;

  @override
  State<InstallmentCalc> createState() => _InstallmentCalcState();
}

class _InstallmentCalcState extends State<InstallmentCalc> {
  late Json _plan;
  late int _down, _step, _months;
  Json? _q;
  String? _err;
  bool _loading = false;
  Timer? _t;
  int _seq = 0;

  List<int> get _downs => (_plan['down'] as List).cast<int>();
  List<int> get _steps => (_plan['steps'] as List).cast<int>();
  List<int> get _monthsList => (((_plan['months'] as Map)['$_step'] as List?) ?? []).cast<int>();

  @override
  void initState() {
    super.initState();
    _plan = widget.plans.firstWhere((p) => p['id'] == widget.initialPlan, orElse: () => widget.plans.first);
    _step = 1;
    _resetFor(_plan, quiet: true);
  }

  /// روش تازه: پیش‌پرداخت و فاصلهٔ قبلی اگر مجاز باشد می‌ماند؛ مدت = بیشترین
  void _resetFor(Json p, {int? keepDown, bool quiet = false}) {
    _plan = p;
    final downs = _downs;
    _down = keepDown != null && downs.contains(keepDown) ? keepDown : downs.first;
    if (!_steps.contains(_step)) _step = _steps.first;
    final ms = _monthsList;
    _months = ms.isEmpty ? 0 : ms.last;
    _fetch(quiet: quiet);
  }

  @override
  void didUpdateWidget(InstallmentCalc old) {
    super.didUpdateWidget(old);
    if (old.total != widget.total) _fetch();
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  void _fetch({bool quiet = false}) {
    _t?.cancel();
    final my = ++_seq;
    if (quiet) {
      _loading = true;
    } else {
      setState(() => _loading = true);
    }
    _t = Timer(const Duration(milliseconds: 220), () async {
      try {
        final q = await Api.i.get('/installments/quote/', {
          'plan': _plan['id'], 'total': widget.total, 'down': _down, 'months': _months, 'step': _step,
        }) as Json;
        if (!mounted || my != _seq) return;
        setState(() => (_q = q, _err = null, _loading = false));
        widget.onChanged?.call(InstallmentChoice(_plan, _down, _step, _months), q);
      } on ApiError catch (e) {
        if (!mounted || my != _seq) return;
        setState(() => (_err = e.message, _loading = false));
        widget.onChanged?.call(null, null);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final downs = _downs, ms = _monthsList;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      for (final p in widget.plans) _planCard(p),
      const SizedBox(height: 6),
      _label('پیش‌پرداخت', _down == 0 ? 'بدون پیش‌پرداخت' : '${_pct(_down)} — ${million((widget.total * _down / 100 / 1000).ceil() * 1000)}'),
      if (downs.length > 1)
        Slider(
          value: downs.indexOf(_down).toDouble().clamp(0, downs.length - 1),
          max: (downs.length - 1).toDouble(),
          divisions: downs.length - 1,
          activeColor: C.pink,
          onChanged: (v) => setState(() => _down = downs[v.round()]),
          onChangeEnd: (_) => _fetch(),
        ),
      if (_steps.length > 1) ...[
        _label('فاصلهٔ قسط‌ها', null),
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: SegmentedButton<int>(
            segments: const [ButtonSegment(value: 1, label: Text('ماهانه')), ButtonSegment(value: 2, label: Text('دوماه‌یک‌بار'))],
            selected: {_step},
            showSelectedIcon: false,
            onSelectionChanged: (s) {
              setState(() {
                _step = s.first;
                final list = _monthsList;
                if (!list.contains(_months)) _months = list.isEmpty ? 0 : list.last;
              });
              _fetch();
            },
          ),
        ),
      ],
      _label('مدت', ms.isEmpty ? '—' : '${faDigits(_months)} ماه — ${faDigits(_months ~/ _step)} قسط'),
      if (ms.length > 1)
        Slider(
          value: ms.indexOf(_months).toDouble().clamp(0, ms.length - 1),
          max: (ms.length - 1).toDouble(),
          divisions: ms.length - 1,
          activeColor: C.pink,
          onChanged: (v) => setState(() => _months = ms[v.round()]),
          onChangeEnd: (_) => _fetch(),
        ),
      const SizedBox(height: 6),
      _result(),
    ]);
  }

  Widget _label(String t, String? v) => Padding(
        padding: const EdgeInsets.only(top: 6, bottom: 2),
        child: Row(children: [
          Text(t, style: const TextStyle(fontWeight: FontWeight.w800)),
          const Spacer(),
          if (v != null) Text(v, style: const TextStyle(color: C.ink2, fontWeight: FontWeight.w700)),
        ]),
      );

  Widget _planCard(Json p) {
    final on = p['id'] == _plan['id'];
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Material(
        color: on ? const Color(0xFFF7F7FD) : Colors.white,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16), side: BorderSide(color: on ? C.ink : C.line, width: on ? 1.8 : 1.4)),
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: on
              ? null
              : () => _resetFor(p, keepDown: _down),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Icon(on ? Icons.radio_button_checked : Icons.radio_button_off, color: on ? C.pink : C.muted, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(p['title'] as String, style: const TextStyle(fontWeight: FontWeight.w900)),
                  Text(faDigits(p['describe'] ?? p['summary'] ?? ''), style: const TextStyle(color: C.muted, fontSize: 12.5, height: 1.7)),
                ]),
              ),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _result() {
    final q = _q;
    const sub = TextStyle(color: Color(0xFFC9CBE6), fontSize: 12);
    const val = TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 14);
    Widget stat(String a, String b) => Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(a, style: sub), Text(b, style: val)]),
        );
    return AnimatedOpacity(
      opacity: _loading ? .7 : 1,
      duration: const Duration(milliseconds: 150),
      child: Container(
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
        decoration: BoxDecoration(color: C.ink, borderRadius: BorderRadius.circular(20)),
        child: _err != null
            ? Padding(padding: const EdgeInsets.only(bottom: 8), child: Text(_err!, style: const TextStyle(color: Colors.white)))
            : q == null
                ? const SizedBox(height: 80, child: Center(child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2)))
                : Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Text('مبلغ هر قسط', style: sub),
                    Text.rich(TextSpan(children: [
                      TextSpan(text: sep(q['installment'] as int), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900, color: Colors.white)),
                      const TextSpan(text: '  تومان', style: sub),
                    ])),
                    Text('${faDigits(q['count'])} قسط ${q['step'] == 2 ? 'دوماهه' : 'ماهانه'}',
                        style: const TextStyle(color: C.saffron, fontWeight: FontWeight.w800)),
                    const Divider(color: Color(0x24FFFFFF), height: 22),
                    Row(children: [
                      stat('پیش‌پرداخت', (q['down'] as int) == 0 ? 'ندارد' : toman(q['down'] as int)),
                      stat('مانده برای قسط', toman(q['principal'] as int)),
                    ]),
                    const SizedBox(height: 10),
                    Row(children: [
                      stat('سود (راس ${faDigits((q['ras_days'] as num).round())} روز)', _pct(q['interest_percent'] as num)),
                      stat('جمع کل پرداختی', toman(q['payable_total'] as int)),
                    ]),
                    Theme(
                      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
                      child: ExpansionTile(
                        tilePadding: EdgeInsets.zero,
                        iconColor: Colors.white,
                        collapsedIconColor: Colors.white,
                        title: Text('تاریخ قسط‌ها (اولین: ${faDigits((q['schedule'] as List).first['jdate'])})',
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700, fontSize: 13.5)),
                        children: [
                          for (final r in (q['schedule'] as List).cast<Json>())
                            Padding(
                              padding: const EdgeInsets.symmetric(vertical: 5),
                              child: Row(children: [
                                SizedBox(width: 28, child: Text(faDigits(r['n']), style: sub)),
                                Expanded(child: Text(faDigits(r['jdate']), style: val, textDirection: TextDirection.ltr, textAlign: TextAlign.right)),
                                const SizedBox(width: 16),
                                Text(sep(r['amount'] as int), style: val),
                              ]),
                            ),
                          const SizedBox(height: 6),
                        ],
                      ),
                    ),
                  ]),
      ),
    );
  }
}

/// جدول اقساط یک سفارش (صفحهٔ سفارش)
class InstallmentSummary extends StatelessWidget {
  const InstallmentSummary(this.inst, {super.key});
  final Json inst;

  @override
  Widget build(BuildContext context) {
    final state = inst['state'] as String? ?? 'review';
    final (bg, fg) = switch (state) {
      'approved' || 'done' => (C.tealTint, C.tealDark),
      'rejected' => (C.pinkTint, C.pinkDark),
      _ => (C.saffronTint, const Color(0xFF7A4F00)),
    };
    final note = (inst['note'] as String? ?? '').trim();
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(18)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(inst['plan_title'] as String? ?? 'خرید اقساطی', style: const TextStyle(fontWeight: FontWeight.w900))),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(99)),
            child: Text(inst['state_label'] as String? ?? '', style: TextStyle(color: fg, fontSize: 12, fontWeight: FontWeight.w800)),
          ),
        ]),
        if (note.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 10),
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(12)),
            child: Text(note, style: TextStyle(color: fg, fontWeight: FontWeight.w600, height: 1.8)),
          ),
        const SizedBox(height: 8),
        _row((inst['down'] as int) == 0 ? 'پیش‌پرداخت' : 'پیش‌پرداخت (${faDigits(inst['down_percent'])}٪)',
            (inst['down'] as int) == 0 ? 'ندارد' : toman(inst['down'] as int)),
        _row('سود (راس ${faDigits((inst['ras_days'] as num).round())} روز)', _pct(inst['interest_percent'] as num)),
        _row('${faDigits(inst['count'])} قسط ${inst['step'] == 2 ? 'دوماهه' : 'ماهانه'}', toman(inst['installment'] as int)),
        _row('جمع کل پرداختی', toman(inst['payable_total'] as int), bold: true),
        const Divider(height: 18),
        Text(inst['kind'] == 'cheque' ? 'تاریخ و مبلغ چک‌ها' : 'تاریخ و مبلغ اقساط',
            style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 13.5)),
        for (final r in (inst['schedule'] as List).cast<Json>())
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(children: [
              SizedBox(width: 26, child: Text(faDigits(r['n']), style: const TextStyle(color: C.muted))),
              Expanded(child: Text(faDigits(r['jdate']), textDirection: TextDirection.ltr, textAlign: TextAlign.right)),
              Text(sep(r['amount'] as int), style: const TextStyle(fontWeight: FontWeight.w700)),
            ]),
          ),
      ]),
    );
  }

  Widget _row(String a, String b, {bool bold = false}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Expanded(child: Text(a, style: const TextStyle(color: C.ink2))),
          Text(b, style: TextStyle(fontWeight: bold ? FontWeight.w900 : FontWeight.w700)),
        ]),
      );
}

/// کارت کوچک «خرید اقساطی: قسط از …» برای صفحهٔ فرش و سبد خرید
class InstallmentTeaser extends StatefulWidget {
  const InstallmentTeaser(
      {super.key, required this.plans, required this.amount, this.margin = const EdgeInsets.fromLTRB(16, 10, 16, 0), this.onTap});
  final List<Json> plans;
  final int amount;
  final EdgeInsets margin;
  final VoidCallback? onTap;
  @override
  State<InstallmentTeaser> createState() => _InstallmentTeaserState();
}

class _InstallmentTeaserState extends State<InstallmentTeaser> {
  static final _cache = <int, Json?>{};
  Json? _best;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(InstallmentTeaser old) {
    super.didUpdateWidget(old);
    if (old.amount != widget.amount) _load();
  }

  /// کمترین قسط ماهانه بین روش‌ها (کمترین پیش‌پرداخت و بیشترین مدت ماهانه)
  Future<void> _load() async {
    final amount = widget.amount;
    if (amount <= 0 || widget.plans.isEmpty) return;
    if (_cache.containsKey(amount)) {
      setState(() => _best = _cache[amount]);
      return;
    }
    Json? best;
    for (final p in widget.plans) {
      final steps = (p['steps'] as List).cast<int>();
      final step = steps.contains(1) ? 1 : steps.first;
      final months = (((p['months'] as Map)['$step'] as List?) ?? []).cast<int>();
      if (months.isEmpty) continue;
      try {
        final q = await Api.i.get('/installments/quote/', {
          'plan': p['id'], 'total': amount, 'down': (p['down'] as List).first, 'months': months.last, 'step': step,
        }) as Json;
        final per = (q['installment'] as int) / step;
        if (best == null || per < (best['_per'] as num)) best = {...q, '_per': per};
      } catch (_) {}
    }
    _cache[amount] = best;
    if (mounted && widget.amount == amount) setState(() => _best = best);
  }

  @override
  Widget build(BuildContext context) {
    final b = _best;
    if (b == null) return const SizedBox.shrink();
    final down = b['down_percent'] as int;
    return Padding(
      padding: widget.margin,
      child: Material(
        color: C.saffronTint,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: widget.onTap ?? () => Navigator.pushNamed(context, '/installment', arguments: widget.amount),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(children: [
              const Icon(Icons.calendar_month_rounded, color: Color(0xFF9A6400), size: 28),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Text('خرید اقساطی', style: TextStyle(fontWeight: FontWeight.w900)),
                  Text('${down == 0 ? 'بدون پیش‌پرداخت' : '${faDigits(down)}٪ پیش‌پرداخت'}، قسط از ${toman(b['installment'] as int)}',
                      style: const TextStyle(fontSize: 12.5, color: C.ink2)),
                ]),
              ),
              const Text('محاسبه', style: TextStyle(color: C.pinkDark, fontWeight: FontWeight.w900)),
              const Icon(Icons.chevron_right, color: C.pinkDark),
            ]),
          ),
        ),
      ),
    );
  }
}
