import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';

/// تکه‌های مشترک صفحه‌های اپ فروشندگان.

int asInt(Object? v) => v is num ? v.round() : int.tryParse('${v ?? ''}') ?? 0;

/// تاریخ میلادی ← شمسی (روز و نام ماه)
const _months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];

(int, int, int) toJalali(DateTime d) {
  var gy = d.year, gm = d.month, gd = d.day;
  const gdm = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334];
  final gy2 = gm > 2 ? gy + 1 : gy;
  var days = 355666 + 365 * gy + ((gy2 + 3) ~/ 4) - ((gy2 + 99) ~/ 100) + ((gy2 + 399) ~/ 400) + gd + gdm[gm - 1];
  var jy = -1595 + 33 * (days ~/ 12053);
  days %= 12053;
  jy += 4 * (days ~/ 1461);
  days %= 1461;
  if (days > 365) {
    jy += (days - 1) ~/ 365;
    days = (days - 1) % 365;
  }
  final jm = days < 186 ? 1 + days ~/ 31 : 7 + (days - 186) ~/ 30;
  final jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return (jy, jm, jd);
}

String jdate(String? iso, {bool time = false}) {
  if (iso == null || iso.isEmpty) return '';
  final d = DateTime.tryParse(iso)?.toLocal();
  if (d == null) return '';
  final (y, m, day) = toJalali(d);
  final t = time ? ' ساعت ${faDigits('${d.hour}'.padLeft(2, '0'))}:${faDigits('${d.minute}'.padLeft(2, '0'))}' : '';
  return '${faDigits(day)} ${_months[m - 1]} ${faDigits(y)}$t';
}

/// مبلغ کوتاه برای کاشی‌ها و نمودار: ۱٫۲ م / ۸۵۰ ه
String shortMoney(num n) {
  if (n >= 1e9) return '${faDigits((n / 1e9).toStringAsFixed(1).replaceAll('.0', '').replaceAll('.', '٫'))} میلیارد';
  if (n >= 1e6) return '${faDigits((n / 1e6).toStringAsFixed(1).replaceAll('.0', '').replaceAll('.', '٫'))} میلیون';
  if (n >= 1e3) return '${faDigits((n / 1e3).round())} هزار';
  return faDigits(n.round());
}

/// قاب سفید گوشه‌گرد
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(14), this.onTap});
  final Widget child;
  final EdgeInsets padding;
  final VoidCallback? onTap;
  @override
  Widget build(BuildContext context) => Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(kR), side: const BorderSide(color: C.line)),
        clipBehavior: Clip.antiAlias,
        child: InkWell(onTap: onTap, child: Padding(padding: padding, child: child)),
      );
}

/// ↑۱۲٪ / ↓۸٪ نسبت به دورهٔ قبل
class ChangeTag extends StatelessWidget {
  const ChangeTag(this.change, {super.key});
  final Object? change;
  @override
  Widget build(BuildContext context) {
    if (change == null) return const SizedBox.shrink();
    final c = asInt(change);
    final up = c >= 0;
    return Text('${up ? '↑' : '↓'}${faDigits(c.abs())}٪',
        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: up ? const Color(0xFF178A4C) : const Color(0xFFC0392B)));
  }
}

/// کاشی عدد کلیدی
class Kpi extends StatelessWidget {
  const Kpi({super.key, required this.label, required this.value, this.change, this.icon});
  final String label, value;
  final Object? change;
  final IconData? icon;
  @override
  Widget build(BuildContext context) => Panel(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            if (icon != null) ...[Icon(icon, size: 16, color: C.muted), const SizedBox(width: 6)],
            Expanded(child: Text(label, style: const TextStyle(color: C.muted, fontSize: 12.5))),
            ChangeTag(change),
          ]),
          const SizedBox(height: 6),
          FittedBox(
              fit: BoxFit.scaleDown,
              alignment: AlignmentDirectional.centerStart,
              child: Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900))),
        ]),
      );
}

/// نمودار ستونی ساده؛ با لمس هر ستون مقدارش زیر نمودار نوشته می‌شود.
class Bars extends StatefulWidget {
  const Bars({super.key, required this.rows, required this.field, this.money = false, this.height = 120, this.color = C.pink});
  final List rows;
  final String field;
  final bool money;
  final double height;
  final Color color;
  @override
  State<Bars> createState() => _BarsState();
}

class _BarsState extends State<Bars> {
  int? _sel;

  String _fmt(num v) => widget.money ? (v == 0 ? '۰' : '${shortMoney(v)} تومان') : faDigits(sep(v));

  @override
  Widget build(BuildContext context) {
    final rows = widget.rows;
    if (rows.isEmpty) return const SizedBox.shrink();
    final vals = [for (final r in rows) (r[widget.field] as num?) ?? 0];
    final top = vals.fold<num>(0, (a, b) => b > a ? b : a);
    final total = vals.fold<num>(0, (a, b) => a + b);
    final sel = _sel;
    final caption = sel == null
        ? 'جمع: ${_fmt(total)}'
        : '${faDigits(rows[sel]['label'] ?? '')}: ${_fmt(vals[sel])}';
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      SizedBox(
        height: widget.height,
        // ترتیب زمانی از چپ به راست مثل همهٔ نمودارها، حتی در صفحهٔ راست‌به‌چپ
        child: Directionality(
          textDirection: TextDirection.ltr,
          child: LayoutBuilder(builder: (context, c) {
            final gap = rows.length > 40 ? 1.0 : 3.0;
            return GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapDown: (d) => setState(() {
                final i = (d.localPosition.dx / c.maxWidth * rows.length).floor().clamp(0, rows.length - 1);
                _sel = _sel == i ? null : i;
              }),
              child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                for (var i = 0; i < rows.length; i++)
                  Expanded(
                    child: Padding(
                      padding: EdgeInsets.symmetric(horizontal: gap / 2),
                      child: Container(
                        height: top == 0 ? 2 : (2 + (widget.height - 2) * vals[i] / top).toDouble(),
                        decoration: BoxDecoration(
                          color: sel == null || sel == i ? widget.color : widget.color.withValues(alpha: .3),
                          borderRadius: const BorderRadius.vertical(top: Radius.circular(3)),
                        ),
                      ),
                    ),
                  ),
              ]),
            );
          }),
        ),
      ),
      const SizedBox(height: 6),
      Directionality(
        textDirection: TextDirection.ltr,
        child: Row(children: [
          Text(faDigits(rows.first['label'] ?? ''), style: const TextStyle(fontSize: 11, color: C.muted)),
          const Spacer(),
          Text(faDigits(rows.last['label'] ?? ''), style: const TextStyle(fontSize: 11, color: C.muted)),
        ]),
      ),
      const SizedBox(height: 4),
      Text(caption, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: C.ink2)),
    ]);
  }
}

/// ورودی مبلغ به تومان با جداکنندهٔ هزارگان (ارقام فارسی هم پذیرفته می‌شود)
class MoneyField extends StatelessWidget {
  const MoneyField({super.key, required this.controller, this.label, this.hint, this.onChanged, this.dense = false});
  final TextEditingController controller;
  final String? label, hint;
  final ValueChanged<String>? onChanged;
  final bool dense;
  @override
  Widget build(BuildContext context) => TextField(
        controller: controller,
        keyboardType: TextInputType.number,
        textDirection: TextDirection.ltr,
        inputFormatters: [_Thousands()],
        onChanged: onChanged,
        decoration: InputDecoration(labelText: label, hintText: hint, suffixText: 'تومان', isDense: dense),
      );
}

int moneyValue(TextEditingController c) => int.tryParse(latin(c.text).replaceAll(RegExp(r'[^0-9]'), '')) ?? 0;

String moneyText(Object? v) {
  final n = asInt(v);
  return n == 0 ? '' : sep(n);
}

class _Thousands extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) {
    final digits = latin(newValue.text).replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.isEmpty) return const TextEditingValue();
    final t = sep(int.parse(digits));
    return TextEditingValue(text: t, selection: TextSelection.collapsed(offset: t.length));
  }
}

/// وضعیت سفارش ← رنگ
Color orderColor(String s) => switch (s) {
      'new' => const Color(0xFFB45309),
      'accepted' => const Color(0xFF1D4ED8),
      'shipped' => const Color(0xFF6D28D9),
      'delivered' => const Color(0xFF178A4C),
      'cancelled' => const Color(0xFFC0392B),
      _ => C.muted,
    };

class Pill extends StatelessWidget {
  const Pill(this.text, {super.key, this.color = C.muted});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
        decoration: BoxDecoration(color: color.withValues(alpha: .1), borderRadius: BorderRadius.circular(99)),
        child: Text(text, style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w800)),
      );
}

/// اجرای یک درخواست با پیام خطا؛ نتیجه یا null
Future<T?> run<T>(BuildContext context, Future<T> Function() fn) async {
  try {
    return await fn();
  } on ApiError catch (e) {
    if (context.mounted) toastErr(context, e.message);
  } catch (e) {
    if (context.mounted) toastErr(context, '$e');
  }
  return null;
}

void toastErr(BuildContext context, String msg) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(msg), backgroundColor: const Color(0xFFB42318)));
}

/// صفحهٔ فهرست با کشیدن برای تازه‌سازی و حالت‌های بارگذاری/خطا/خالی
class Loader<T> extends StatelessWidget {
  const Loader({super.key, required this.future, required this.builder, required this.onRetry});
  final Future<T>? future;
  final Widget Function(T data) builder;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) => FutureBuilder<T>(
        future: future,
        builder: (context, s) {
          if (s.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (s.hasError) {
            final e = s.error;
            return Center(
                child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.wifi_off_rounded, size: 40, color: C.muted),
                const SizedBox(height: 10),
                Text(e is ApiError ? e.message : '$e', textAlign: TextAlign.center),
                const SizedBox(height: 12),
                OutlinedButton(onPressed: onRetry, child: const Text('تلاش دوباره')),
              ]),
            ));
          }
          return builder(s.data as T);
        },
      );
}

class Empty extends StatelessWidget {
  const Empty(this.text, {super.key, this.icon = Icons.inbox_outlined});
  final String text;
  final IconData icon;
  @override
  Widget build(BuildContext context) => ListView(children: [
        const SizedBox(height: 90),
        Icon(icon, size: 46, color: C.line),
        const SizedBox(height: 10),
        Text(text, textAlign: TextAlign.center, style: const TextStyle(color: C.muted)),
      ]);
}

/// راهنمای هر بخش (از سرور، همان متن پنل سایت). با «متوجه شدم» بسته می‌شود و در گوشی یادش می‌ماند.
class Guides {
  static Map<String, dynamic> data = {};
  static Set<String> off = {};
  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    off = (p.getStringList('seller_guide_off') ?? []).toSet();
  }

  static Future<void> setOff(String key, bool v) async {
    v ? off.add(key) : off.remove(key);
    final p = await SharedPreferences.getInstance();
    await p.setStringList('seller_guide_off', off.toList());
  }
}

class GuideCard extends StatefulWidget {
  const GuideCard(this.tab, {super.key});
  final String tab;
  @override
  State<GuideCard> createState() => _GuideCardState();
}

class _GuideCardState extends State<GuideCard> {
  @override
  Widget build(BuildContext context) {
    final g = Guides.data[widget.tab] as Map?;
    if (g == null || Guides.off.contains(widget.tab)) return const SizedBox.shrink();
    final steps = ((g['steps'] as List?) ?? []).cast<String>();
    final ordered = g['ordered'] == true;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(kR),
        border: const BorderDirectional(start: BorderSide(color: C.teal, width: 4), top: BorderSide(color: C.line),
            end: BorderSide(color: C.line), bottom: BorderSide(color: C.line)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.help_outline_rounded, size: 20, color: C.tealDark),
          const SizedBox(width: 8),
          Expanded(child: Text('${g['title']}', style: const TextStyle(fontWeight: FontWeight.w900))),
        ]),
        const SizedBox(height: 6),
        for (var i = 0; i < steps.length; i++)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(
                width: 24,
                child: ordered
                    ? Text('${faDigits(i + 1)}.', style: const TextStyle(color: C.tealDark, fontWeight: FontWeight.w900))
                    : const Padding(padding: EdgeInsets.only(top: 8), child: CircleAvatar(radius: 3, backgroundColor: C.teal)),
              ),
              Expanded(child: Text(faDigits(steps[i]), style: const TextStyle(color: C.ink2, fontSize: 13.5, height: 1.7))),
            ]),
          ),
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: TextButton(
            onPressed: () async {
              await Guides.setOff(widget.tab, true);
              if (mounted) setState(() {});
            },
            child: const Text('متوجه شدم'),
          ),
        ),
      ]),
    );
  }
}

/// دکمهٔ «راهنما» در نوار بالا: راهنمای بسته‌شده را دوباره باز می‌کند.
class GuideButton extends StatelessWidget {
  const GuideButton(this.tab, {super.key, required this.onChanged});
  final String tab;
  final VoidCallback onChanged;
  @override
  Widget build(BuildContext context) => IconButton(
        tooltip: 'راهنمای این بخش',
        icon: const Icon(Icons.help_outline_rounded),
        onPressed: () async {
          await Guides.setOff(tab, !Guides.off.contains(tab));
          onChanged();
        },
      );
}
