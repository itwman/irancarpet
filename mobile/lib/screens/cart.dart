import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/installment.dart';
import 'shell.dart';

class CartScreen extends StatefulWidget {
  const CartScreen({super.key, this.standalone = false});
  final bool standalone;
  @override
  State<CartScreen> createState() => _CartScreenState();
}

class _CartScreenState extends State<CartScreen> {
  Json? _quote;
  String _sig = '';
  bool _busy = false;

  Future<void> _refresh(Cart cart) async {
    final sig = cart.payload.toString();
    if (sig == _sig || _busy) return;
    _sig = sig;
    if (cart.items.isEmpty) return setState(() => _quote = null);
    setState(() => _busy = true);
    try {
      _quote = await Api.i.post('/cart/quote/', {'items': cart.payload}) as Json;
    } on ApiError catch (_) {
      _sig = '';
    }
    if (mounted) setState(() => _busy = false);
    if (mounted && cart.payload.toString() != _sig) _refresh(cart);
  }

  @override
  Widget build(BuildContext context) {
    final cart = context.watch<Cart>();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh(cart));
    final q = _quote;
    final lines = {for (final l in ((q?['lines'] as List?) ?? []).cast<Json>()) l['variation'] as int: l};
    return Scaffold(
      appBar: AppBar(title: Text(cart.count > 0 ? 'سبد خرید (${faDigits(cart.count)})' : 'سبد خرید'), automaticallyImplyLeading: widget.standalone),
      body: cart.items.isEmpty
          ? StatusView(
              message: 'سبد خریدتان خالی است.',
              icon: Icons.shopping_bag_outlined,
              action: FilledButton(
                onPressed: () => widget.standalone ? Navigator.popUntil(context, (r) => r.isFirst) : Shell.goTab(context, 0),
                child: const Text('دیدن فرش‌ها'),
              ),
            )
          : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
              for (final it in cart.items) _line(context, cart, it, lines[it.variation]),
              const SizedBox(height: 8),
              if (q != null) _summary(q),
              if (q != null && (q['total'] as int) > 0 && q['has_problem'] != true)
                InstallmentTeaser(
                    plans: context.watch<AppConfig>().installmentPlans,
                    amount: q['total'] as int,
                    margin: const EdgeInsets.only(top: 12),
                    onTap: () => _goCheckout(context, mode: 'installment')),
            ]),
      bottomNavigationBar: cart.items.isEmpty
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 10),
                child: FilledButton(
                  onPressed: q == null || q['has_problem'] == true || _busy
                      ? null
                      : () => _goCheckout(context),
                  child: Text(q != null && q['has_problem'] == true ? 'کالاهای ناموجود را حذف کنید' : 'ادامهٔ خرید'),
                ),
              ),
            ),
    );
  }

  Widget _line(BuildContext context, Cart cart, CartItem it, Json? l) {
    final problem = l?['problem'] as String? ?? '';
    final price = (l?['unit_price'] as int?) ?? it.price;
    final step = it.pairOnly ? 2 : 1;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(18)),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        GestureDetector(
          onTap: () => Navigator.pushNamed(context, '/product', arguments: it.productId),
          child: SizedBox(width: 74, height: 98, child: NetImage(it.image, radius: 12)),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(it.title, maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5)),
            Text(it.size + (it.pairOnly ? ' · فقط جفت' : ''), style: const TextStyle(color: C.muted, fontSize: 12.5)),
            if (problem.isNotEmpty) Text(problem, style: const TextStyle(color: C.pinkDark, fontSize: 12.5, fontWeight: FontWeight.w700)),
            const SizedBox(height: 6),
            Row(children: [
              Expanded(child: Price(price * it.qty, size: 14)),
              Container(
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
                child: Row(children: [
                  IconButton(
                      visualDensity: VisualDensity.compact,
                      tooltip: 'بیشتر',
                      onPressed: it.qty + step <= 20 ? () => cart.setQty(it.variation, it.qty + step) : null,
                      icon: const Icon(Icons.add_rounded, size: 18)),
                  Text(faDigits(it.qty), style: const TextStyle(fontWeight: FontWeight.w900)),
                  IconButton(
                      visualDensity: VisualDensity.compact,
                      tooltip: it.qty - step < step ? 'حذف' : 'کمتر',
                      onPressed: () => cart.setQty(it.variation, it.qty - step),
                      icon: Icon(it.qty - step < step ? Icons.delete_outline_rounded : Icons.remove_rounded, size: 18)),
                ]),
              ),
            ]),
          ]),
        ),
      ]),
    );
  }

  Future<void> _goCheckout(BuildContext context, {String? mode}) async {
    if (!context.read<Auth>().loggedIn) {
      final ok = await Navigator.pushNamed(context, '/login', arguments: 'برای ثبت سفارش وارد شوید') == true;
      if (!ok || !context.mounted) return;
    }
    if (context.mounted) Navigator.pushNamed(context, '/checkout', arguments: mode);
  }

  Widget _summary(Json q) {
    final total = q['total'] as int;
    final free = q['free_shipping'] as bool;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(border: Border.all(color: C.line), borderRadius: BorderRadius.circular(18)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const Expanded(child: Text('جمع سبد', style: TextStyle(fontWeight: FontWeight.w800))), Price(total, size: 17)]),
        const SizedBox(height: 10),
        Text(
          free
              ? 'با پرداخت کامل آنلاین، ارسال رایگان است.'
              : 'برای ارسال رایگان، سفارش باید دست‌کم ${toman(q['free_shipping_min'] as int)} باشد و کامل آنلاین پرداخت شود. در غیر این صورت هزینهٔ ارسال موقع تحویل پرداخت می‌شود.',
          style: const TextStyle(color: C.muted, fontSize: 12.5),
        ),
        const SizedBox(height: 4),
        Text('اگر بخواهید فقط بیعانه بدهید: ${toman(q['deposit'] as int)} الان و بقیه موقع تحویل.',
            style: const TextStyle(color: C.muted, fontSize: 12.5)),
      ]),
    );
  }
}
