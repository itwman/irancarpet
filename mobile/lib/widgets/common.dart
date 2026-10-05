import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import 'knots.dart';

class NetImage extends StatelessWidget {
  const NetImage(this.url, {super.key, this.fit = BoxFit.cover, this.radius = 0});
  final String url;
  final BoxFit fit;
  final double radius;

  @override
  Widget build(BuildContext context) {
    final ph = Container(color: C.soft, alignment: Alignment.center, child: const KnotIcon(c1: C.line, c2: Color(0xFFE2E4F2)));
    Widget img = url.isEmpty
        ? ph
        : CachedNetworkImage(imageUrl: url, fit: fit, fadeInDuration: const Duration(milliseconds: 220),
            placeholder: (_, _) => ph, errorWidget: (_, _, _) => ph);
    return radius > 0 ? ClipRRect(borderRadius: BorderRadius.circular(radius), child: img) : img;
  }
}

class ReedsBadge extends StatelessWidget {
  const ReedsBadge(this.reeds, {super.key});
  final String reeds;
  @override
  Widget build(BuildContext context) {
    if (reeds.isEmpty) return const SizedBox.shrink();
    final c = C.reeds(reeds);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(9)),
      child: Text('$reeds شانه',
          style: TextStyle(color: c == C.saffron || c == C.pistachio ? C.ink : Colors.white, fontSize: 11.5, fontWeight: FontWeight.w800)),
    );
  }
}

class Price extends StatelessWidget {
  const Price(this.value, {super.key, this.from = false, this.size = 16, this.color = C.ink, this.strike});
  final int value;
  final bool from;
  final double size;
  final Color color;
  final int? strike;

  @override
  Widget build(BuildContext context) {
    if (value == 0) return Text('استعلام قیمت', style: TextStyle(color: C.muted, fontSize: size * .85, fontWeight: FontWeight.w700));
    return Wrap(crossAxisAlignment: WrapCrossAlignment.end, spacing: 6, children: [
      if (strike != null && strike! > value)
        Text(sep(strike!), style: TextStyle(color: C.muted, fontSize: size * .75, decoration: TextDecoration.lineThrough)),
      if (from) Text('از', style: TextStyle(color: C.muted, fontSize: size * .75)),
      Text(sep(value), style: TextStyle(color: color, fontSize: size, fontWeight: FontWeight.w900)),
      Text('تومان', style: TextStyle(color: C.muted, fontSize: size * .7)),
    ]);
  }
}

class ProductCard extends StatelessWidget {
  const ProductCard(this.p, {super.key, this.width, this.match});
  final Json p;
  final double? width;

  /// برچسب «چرا این فرش؟» روی عکس (فرش‌یاب)
  final String? match;

  @override
  Widget build(BuildContext context) {
    final id = p['id'] as int;
    final inStock = p['in_stock'] as bool? ?? true;
    final wish = context.watch<Wishlist>();
    return SizedBox(
      width: width,
      child: Material(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: () => Navigator.pushNamed(context, '/product', arguments: id),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            AspectRatio(
              aspectRatio: 3 / 4,
              child: Stack(fit: StackFit.expand, children: [
                Hero(
                  tag: 'p$id-${p['image']}',
                  child: ColorFiltered(
                    colorFilter: inStock
                        ? const ColorFilter.mode(Colors.transparent, BlendMode.dst)
                        : const ColorFilter.matrix([.5, .3, .2, 0, 0, .3, .5, .2, 0, 0, .3, .3, .4, 0, 0, 0, 0, 0, .8, 0]),
                    child: NetImage(p['image'] as String? ?? '', radius: 20),
                  ),
                ),
                Positioned(top: 8, right: 8, child: ReedsBadge(p['reeds'] as String? ?? '')),
                Positioned(
                  top: 2,
                  left: 2,
                  child: IconButton(
                    tooltip: wish.has(id) ? 'حذف از علاقه‌مندی' : 'افزودن به علاقه‌مندی',
                    onPressed: () => wish.toggle(id),
                    icon: Icon(wish.has(id) ? Icons.favorite : Icons.favorite_border, color: wish.has(id) ? C.pink : Colors.white,
                        shadows: const [Shadow(blurRadius: 8, color: Colors.black38)]),
                  ),
                ),
                if (match != null && match!.isNotEmpty)
                  Positioned(
                    bottom: 8,
                    right: 8,
                    left: 8,
                    child: Align(
                      alignment: AlignmentDirectional.centerStart,
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(color: Colors.white.withValues(alpha: .94), borderRadius: BorderRadius.circular(9)),
                        child: Row(mainAxisSize: MainAxisSize.min, children: [
                          const Icon(Icons.check_circle_rounded, size: 14, color: C.tealDark),
                          const SizedBox(width: 4),
                          Flexible(
                            child: Text(match!, maxLines: 1, overflow: TextOverflow.ellipsis,
                                style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: C.ink)),
                          ),
                        ]),
                      ),
                    ),
                  ),
                if (!inStock)
                  Positioned(
                    bottom: 8,
                    right: 8,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(color: Colors.white.withValues(alpha: .9), borderRadius: BorderRadius.circular(8)),
                      child: const Text('ناموجود', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: C.muted)),
                    ),
                  ),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 10, 4, 6),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(p['title'] as String, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, height: 1.6)),
                const SizedBox(height: 4),
                Price((p['price'] as int?) ?? 0, from: p['price_is_from'] as bool? ?? false, size: 15),
                if ((p['size_label'] as String? ?? '').isNotEmpty)
                  Text('برای ${faDigits(p['size_label'])}', style: const TextStyle(fontSize: 11.5, color: C.muted)),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.title, {super.key, this.action, this.onAction, this.subtitle});
  final String title;
  final String? action, subtitle;
  final VoidCallback? onAction;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 22, 16, 10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title, style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
              if (subtitle != null) Text(subtitle!, style: const TextStyle(color: C.muted, fontSize: 13)),
            ]),
          ),
          if (action != null) TextButton(onPressed: onAction, child: Text(action!, style: const TextStyle(color: C.pinkDark, fontWeight: FontWeight.w700))),
        ]),
      );
}

class StatusView extends StatelessWidget {
  const StatusView({super.key, required this.message, this.onRetry, this.icon = Icons.wifi_off_rounded, this.action});
  final String message;
  final VoidCallback? onRetry;
  final IconData icon;
  final Widget? action;
  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 44, color: C.muted),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center, style: const TextStyle(color: C.ink2, fontSize: 15)),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              OutlinedButton(onPressed: onRetry, child: const Text('تلاش دوباره')),
            ],
            if (action != null) ...[const SizedBox(height: 16), action!],
          ]),
        ),
      );
}

class Loading extends StatefulWidget {
  const Loading({super.key});
  @override
  State<Loading> createState() => _LoadingState();
}

class _LoadingState extends State<Loading> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat();
  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Center(
        child: AnimatedBuilder(animation: _c, builder: (_, _) => KnotLogo(size: 44, progress: _c.value * 1.15)),
      );
}

void toast(BuildContext context, String msg) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(SnackBar(content: Text(msg)));
}

/// سرآیند فرم‌ها
class FieldLabel extends StatelessWidget {
  const FieldLabel(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) =>
      Padding(padding: const EdgeInsets.only(bottom: 6, top: 14), child: Text(text, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)));
}
