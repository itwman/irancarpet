import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/installment.dart';

/// صفحهٔ «خرید اقساطی»: معرفی روش‌ها و ماشین‌حساب قسط
class InstallmentScreen extends StatefulWidget {
  const InstallmentScreen({super.key, this.amount});
  final int? amount;
  @override
  State<InstallmentScreen> createState() => _InstallmentScreenState();
}

class _InstallmentScreenState extends State<InstallmentScreen> {
  late final TextEditingController _amount = TextEditingController(text: sep(widget.amount ?? 50000000));
  late int _total = widget.amount ?? 50000000;

  @override
  void dispose() {
    _amount.dispose();
    super.dispose();
  }

  void _onAmount(String v) {
    final n = int.tryParse(latin(v).replaceAll(RegExp(r'[^0-9]'), '')) ?? 0;
    final txt = n == 0 ? '' : sep(n);
    if (txt != v) {
      _amount.value = TextEditingValue(text: txt, selection: TextSelection.collapsed(offset: txt.length));
    }
    if (n >= 1000000) setState(() => _total = n);
  }

  @override
  Widget build(BuildContext context) {
    final plans = context.watch<AppConfig>().installmentPlans;
    return Scaffold(
      appBar: AppBar(title: const Text('خرید اقساطی')),
      body: plans.isEmpty
          ? const StatusView(message: 'خرید اقساطی فعلاً فعال نیست.', icon: Icons.event_busy_rounded)
          : ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 28), children: [
              const Text('فرش دلخواهت را الان بخر و هزینه‌اش را قسطی بپرداز. جدول کامل اقساط را همین‌جا می‌بینی.',
                  style: TextStyle(color: C.ink2, height: 1.9)),
              const FieldLabel('مبلغ خرید (تومان)'),
              TextField(
                controller: _amount,
                keyboardType: TextInputType.number,
                inputFormatters: [FilteringTextInputFormatter.allow(RegExp(r'[0-9۰-۹٬,]'))],
                textDirection: TextDirection.ltr,
                textAlign: TextAlign.right,
                style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900),
                onChanged: _onAmount,
              ),
              const SizedBox(height: 14),
              InstallmentCalc(plans: plans, total: _total),
              const SizedBox(height: 18),
              for (final p in plans) _planInfo(p),
              const SizedBox(height: 8),
              Row(children: [
                Expanded(
                    child: FilledButton(
                        onPressed: () => Navigator.pushNamed(context, '/pricelist'), child: const Text('لیست قیمت'))),
                const SizedBox(width: 10),
                Expanded(
                    child: OutlinedButton(
                        onPressed: () => Navigator.pushNamed(context, '/products',
                            arguments: {'title': 'همهٔ فرش‌ها', 'query': <String, dynamic>{}}),
                        child: const Text('همهٔ فرش‌ها'))),
              ]),
              const SizedBox(height: 18),
              const Text('سود اقساط چطور حساب می‌شود؟', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
              const SizedBox(height: 4),
              const Text(
                  'با راس‌گیری: میانگین فاصلهٔ سررسید قسط‌ها (به روز) تقسیم بر ۳۰، ضرب در درصد سود ماهانه. مثلاً دو قسط ماهانه راس ۴۵ روز دارد '
                  'و با سود ماهی ۶٪ سود کل ۹٪ می‌شود. هرچه پیش‌پرداخت بیشتر و مدت کوتاه‌تر باشد، سود کمتری می‌پردازید.',
                  style: TextStyle(color: C.ink2, height: 1.9)),
            ]),
    );
  }

  Widget _planInfo(Json p) {
    final cheque = p['kind'] == 'cheque';
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: C.soft,
        borderRadius: BorderRadius.circular(18),
        border: BorderDirectional(start: BorderSide(color: cheque ? C.teal : C.saffron, width: 5)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(p['title'] as String, style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 15.5)),
        Text(faDigits(p['describe'] ?? ''), style: const TextStyle(color: C.ink2, fontSize: 12.5, fontWeight: FontWeight.w600)),
        if ((p['description'] as String? ?? '').isNotEmpty) ...[
          const SizedBox(height: 6),
          Text(faDigits(p['description']), style: const TextStyle(height: 1.9, fontSize: 13.5)),
        ],
      ]),
    );
  }
}
