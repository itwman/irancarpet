import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'ui.dart';

/// کارت فرش «طاقچه»: فرش در طاق جناغی، نام کوتاه نقشه، شانه و قیمت
class NicheCard extends StatelessWidget {
  const NicheCard(this.p, {super.key, this.width, this.match});
  final Json p;
  final double? width;
  final String? match;

  @override
  Widget build(BuildContext context) {
    final id = asInt(p['id']);
    final inStock = p['in_stock'] as bool? ?? true;
    final wish = context.watch<Wishlist>();
    final crop = RugCrop.of(p['crop']);
    final reeds = p['reeds'] as String? ?? '';
    final price = asInt(p['price']);
    final title = p['title'] as String? ?? '';
    return SizedBox(
      width: width,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => Navigator.pushNamed(context, '/product', arguments: id),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
          Stack(children: [
            Niche(
              ar: crop.ar,
              child: Hero(
                tag: 'p$id-${p['image']}',
                child: ColorFiltered(
                  colorFilter: inStock
                      ? const ColorFilter.mode(Colors.transparent, BlendMode.dst)
                      : const ColorFilter.matrix([.5, .3, .2, 0, 0, .3, .5, .2, 0, 0, .3, .3, .4, 0, 0, 0, 0, 0, .85, 0]),
                  child: RugImage(p['image'] as String? ?? '', crop: crop, seed: id),
                ),
              ),
            ),
            PositionedDirectional(
              bottom: 2,
              end: 0,
              child: IconButton(
                tooltip: wish.has(id) ? 'برداشتن از علاقه‌مندی‌ها' : 'افزودن به علاقه‌مندی‌ها',
                onPressed: () => wish.toggle(id),
                icon: Icon(wish.has(id) ? Icons.favorite : Icons.favorite_border, color: wish.has(id) ? C.pink : C.cream,
                    shadows: const [Shadow(blurRadius: 6, color: Colors.black54)]),
              ),
            ),
            if (!inStock)
              const PositionedDirectional(
                  bottom: 12, start: 10, child: HouseChip('ناموجود', color: C.ink2, bg: Color(0xEEF2EADA))),
            if (match != null && match!.isNotEmpty)
              PositionedDirectional(bottom: 12, start: 10, end: 44, child: Align(
                alignment: AlignmentDirectional.centerStart,
                child: HouseChip(match!, color: C.tealDark, bg: const Color(0xEEF2EADA)),
              )),
          ]),
          const SizedBox(height: 8),
          Text(faDigits(rugName(title)), maxLines: 1, overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 14.5, fontWeight: FontWeight.w800, height: 1.5)),
          const SizedBox(height: 3),
          Wrap(spacing: 4, runSpacing: 4, children: [
            if (reeds.isNotEmpty) HouseChip('${faDigits(reeds)} شانه'),
            if (title.contains('برجسته')) const HouseChip('برجسته', color: C.ink2),
          ]),
          const SizedBox(height: 5),
          price == 0
              ? const Text('استعلام قیمت', style: TextStyle(color: C.muted, fontSize: 12.5))
              : Text.rich(TextSpan(children: [
                  if (p['price_is_from'] == true) const TextSpan(text: 'از ', style: TextStyle(color: C.muted, fontSize: 12)),
                  TextSpan(text: sep(price), style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 14.5)),
                  const TextSpan(text: ' تومان', style: TextStyle(color: C.muted, fontSize: 11.5)),
                ])),
        ]),
      ),
    );
  }
}
