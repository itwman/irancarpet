import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'common.dart';

/// برچسب زمان یا کمیابی: اگر فرصت «پایان» دارد شمارندهٔ معکوس واقعی، وگرنه «آخرین تخته».
class OfferClock extends StatefulWidget {
  const OfferClock(this.offer, {super.key, this.size = 13});
  final Json offer;
  final double size;
  @override
  State<OfferClock> createState() => _OfferClockState();
}

class _OfferClockState extends State<OfferClock> {
  Timer? _t;
  DateTime? _end;

  @override
  void initState() {
    super.initState();
    final e = widget.offer['ends_at'] as String?;
    if (e != null) {
      _end = DateTime.tryParse(e);
      _t = Timer.periodic(const Duration(seconds: 1), (_) => mounted ? setState(() {}) : null);
    }
  }

  @override
  void dispose() {
    _t?.cancel();
    super.dispose();
  }

  String _two(int n) => n.toString().padLeft(2, '0');

  @override
  Widget build(BuildContext context) {
    String text;
    if (_end != null) {
      final left = _end!.difference(DateTime.now());
      if (left.isNegative) {
        text = 'این فرصت تمام شد';
      } else {
        final d = left.inDays, h = left.inHours % 24, m = left.inMinutes % 60, s = left.inSeconds % 60;
        text = '${d > 0 ? '${faDigits(d)} روز و ' : ''}${faDigits('${_two(h)}:${_two(m)}:${_two(s)}')} مانده';
      }
    } else if ((widget.offer['remaining'] as int? ?? 1) == 1) {
      text = 'آخرین تخته';
    } else {
      text = '${faDigits(widget.offer['remaining'])} تخته باقی مانده';
    }
    return Text(text, style: TextStyle(color: C.pinkDark, fontWeight: FontWeight.w900, fontSize: widget.size));
  }
}

class OfferTag extends StatelessWidget {
  const OfferTag({super.key, this.text = 'فرصت ویژهٔ خرید'});
  final String text;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 3),
        decoration: BoxDecoration(color: C.pink, borderRadius: BorderRadius.circular(99)),
        child: Text(text, style: const TextStyle(color: Colors.white, fontSize: 11.5, fontWeight: FontWeight.w800)),
      );
}

/// کادر فرصت ویژه در صفحهٔ فرش
class OfferBox extends StatelessWidget {
  const OfferBox({super.key, required this.offer, required this.product});
  final Json offer, product;

  Future<void> _buy(BuildContext context, int qty) async {
    await context.read<Cart>().putExact(
        CartItem(
            variation: offer['variation'] as int, qty: qty, productId: product['id'] as int, title: product['title'] as String,
            size: offer['size'] as String, image: product['image'] as String? ?? '', price: offer['price'] as int, pairOnly: false),
        qty);
    if (context.mounted) Navigator.pushNamed(context, '/cart');
  }

  String _label(int q) => q == 1 ? 'خرید یک تخته' : (q == 2 ? 'خرید جفت (۲ تخته)' : 'خرید ${faDigits(q)} تخته');

  @override
  Widget build(BuildContext context) {
    final remaining = offer['remaining'] as int? ?? 1;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 10),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        border: Border.all(color: C.pink, width: 2),
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [C.pinkTint, Colors.white]),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [const OfferTag(), const Spacer(), OfferClock(offer)]),
        const SizedBox(height: 8),
        Text('${faDigits(offer['size'])} · ${remaining == 1 ? 'فقط یک تخته' : '${faDigits(remaining)} تخته'} آمادهٔ ارسال',
            style: const TextStyle(fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 8, children: [
          Text(sep(offer['regular_price'] as int),
              style: const TextStyle(color: C.muted, decoration: TextDecoration.lineThrough, fontSize: 13)),
          Text('${sep(offer['price'] as int)} تومان${remaining > 1 ? ' هر تخته' : ''}',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
          if ((offer['percent'] as int? ?? 0) > 0)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(99)),
              child: Text('٪${faDigits(offer['percent'])} تخفیف',
                  style: const TextStyle(color: Color(0xFF8A5A00), fontWeight: FontWeight.w800, fontSize: 12)),
            ),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          for (final (i, q) in (((offer['allowed'] as List?) ?? [1]).cast<int>()).indexed) ...[
            if (i > 0) const SizedBox(width: 8),
            Expanded(
              child: i == 0
                  ? FilledButton(onPressed: () => _buy(context, q), child: Text(_label(q)))
                  : OutlinedButton(onPressed: () => _buy(context, q), child: Text(_label(q))),
            ),
          ],
        ]),
        const SizedBox(height: 4),
        Text(offer['note'] as String? ?? '', style: const TextStyle(color: C.muted, fontSize: 11.5)),
      ]),
    );
  }
}

/// ردیف افقی فرصت‌ها در صفحهٔ اول
class OffersStrip extends StatelessWidget {
  const OffersStrip(this.offers, {super.key});
  final List<Json> offers;

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const SectionTitle('فرصت‌های ویژهٔ خرید', subtitle: 'تک‌تخته‌های آمادهٔ ارسال با تخفیف'),
      SizedBox(
        height: 318,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 16),
          itemCount: offers.length,
          separatorBuilder: (_, _) => const SizedBox(width: 12),
          itemBuilder: (_, i) {
            final o = offers[i];
            return GestureDetector(
              onTap: () => Navigator.pushNamed(context, '/product', arguments: o['product_id']),
              child: Container(
                width: 184,
                decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18), border: Border.all(color: C.line)),
                clipBehavior: Clip.antiAlias,
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Stack(children: [
                    SizedBox(height: 176, width: double.infinity, child: NetImage(o['image'] as String? ?? '')),
                    if ((o['percent'] as int? ?? 0) > 0)
                      Positioned(
                        top: 8,
                        left: 8,
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(color: C.pink, borderRadius: BorderRadius.circular(10)),
                          child: Text('٪${faDigits(o['percent'])}',
                              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900)),
                        ),
                      ),
                  ]),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(10, 8, 10, 8),
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text(faDigits(o['title']), maxLines: 2, overflow: TextOverflow.ellipsis,
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 12.5, height: 1.6)),
                      Text(faDigits(o['size']), maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: C.muted, fontSize: 11.5)),
                      Text(sep(o['regular_price'] as int),
                          style: const TextStyle(color: C.muted, decoration: TextDecoration.lineThrough, fontSize: 11.5)),
                      Text('${sep(o['price'] as int)} تومان', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 14)),
                      OfferClock(o, size: 11.5),
                    ]),
                  ),
                ]),
              ),
            );
          },
        ),
      ),
    ]);
  }
}
