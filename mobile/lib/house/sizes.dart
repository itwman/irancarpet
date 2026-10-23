import 'dart:math';

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import 'ui.dart';

enum SizeKind { rug, small, runner, mat, other }

/// یک سایز استاندارد فرش (متر). [id] شناسهٔ سایز در سایت برای فیلتر (`size`)؛ اگر از لیست قیمت نیامده باشد null.
class RugSize {
  RugSize({required this.name, required this.w, required this.l, this.id, this.minPrice = 0});
  final String name;
  final double w, l;
  final int? id;
  int minPrice;

  double get area => w * l;
  SizeKind get kind => name.contains('کناره')
      ? SizeKind.runner
      : name.contains('پادری')
          ? SizeKind.mat
          : name.contains('قالیچه')
              ? SizeKind.small
              : RegExp(r'متری|^فرش').hasMatch(name)
                  ? SizeKind.rug
                  : SizeKind.other; // رویه‌پشتی، تابلو و…
  String get dims => '${faDigits(metres(w))}×${faDigits(metres(l))}';

  /// پیوند فهرست فرش‌های این سایز (با فیلتر سایت، یا جستجوی نام سایز)
  void open(BuildContext context) => Navigator.pushNamed(context, '/products', arguments: {
        'title': kind == SizeKind.rug && !name.startsWith('فرش') ? 'فرش ${faDigits(name)}' : faDigits(name),
        'query': id != null ? {'size': id} : {'q': name},
      });

  /// «۹ متری مستطیل (۳.۵ × ۲.۵)» ← نام «۹ متری» و ابعاد ۲٫۵×۳٫۵
  static RugSize? parse(String label, {int? id}) {
    final lat = latin(label).replaceAll('٫', '.').replaceAll('/', '.');
    final m = RegExp(r'(\d+(?:\.\d+)?)\s*[×xX*]\s*(\d+(?:\.\d+)?)').firstMatch(lat);
    if (m == null) return null;
    final a = double.parse(m.group(1)!), b = double.parse(m.group(2)!);
    if (a <= 0 || b <= 0) return null;
    var name = label.replaceAll(RegExp(r'\s*\([^()]*\)\s*'), ' ').replaceAll(RegExp(r'[\d۰-۹.٫]+\s*[×xX*]\s*[\d۰-۹.٫]+'), '').trim();
    name = name.replaceAll(RegExp(r'\s+مستطیل$'), '').replaceAll(RegExp(r'\s+'), ' ').trim();
    if (name.isEmpty || name == 'قالیچه' || name == 'کناره' || name == 'پادری') {
      final base = name.isEmpty ? 'فرش' : name;
      name = base == 'کناره' ? 'کناره ${faDigits(metres(max(a, b)))} متری' : base == 'قالیچه' ? 'قالیچه ${faDigits(metres((a * b * 2).floor() / 2))} متری' : base;
    }
    return RugSize(name: name, w: min(a, b), l: max(a, b), id: id);
  }

  /// سایزهای رایج (اگر لیست قیمت در دسترس نبود)
  static List<RugSize> defaults() => [
        RugSize(name: '۱۲ متری', w: 3, l: 4),
        RugSize(name: '۹ متری', w: 2.5, l: 3.5),
        RugSize(name: '۶ متری', w: 2, l: 3),
        RugSize(name: 'قالیچه ۳ متری', w: 1.5, l: 2.25),
        RugSize(name: 'قالیچه ۱٫۵ متری', w: 1, l: 1.5),
        RugSize(name: 'کناره ۴ متری', w: 1, l: 4),
        RugSize(name: 'کناره ۳ متری', w: 1, l: 3),
        RugSize(name: 'کناره ۲ متری', w: 1, l: 2),
        RugSize(name: 'پادری', w: .5, l: .85),
      ];

  /// سایزها و کمترین قیمت هر کدام از /pricelist/ (فقط گروه‌های شانه‌دار، نه تابلوفرش و…)
  static List<RugSize> fromPriceList(Json d) {
    final out = <int, RugSize>{};
    for (final g in asList(d['groups'])) {
      final reeds = '${g['reeds'] ?? ''}'.trim();
      for (final s in asList(g['sizes'])) {
        final id = asInt(s['id']);
        if (out.containsKey(id)) continue;
        final r = RugSize.parse(s['label'] as String? ?? '', id: id);
        if (r != null) out[id] = r;
      }
      if (reeds.isEmpty) continue;
      for (final a in asList(g['albums'])) {
        for (final pr in asList(a['prices'])) {
          final r = out[asInt(pr['size_id'])], v = asInt(pr['price']);
          if (r != null && v > 0 && (r.minPrice == 0 || v < r.minPrice)) r.minPrice = v;
        }
      }
    }
    final list = out.values.toList()..sort((a, b) => b.area.compareTo(a.area));
    return list;
  }
}

/// شکل سایز به نسبت واقعی ابعاد (برای کاشی‌های «خرید بر اساس سایز»)
class SizeShape extends StatelessWidget {
  const SizeShape(this.s, {super.key, this.box = 64, this.maxL = 4});
  final RugSize s;
  final double box, maxL;
  @override
  Widget build(BuildContext context) => CustomPaint(size: Size.square(box), painter: _ShapePainter(s, maxL));
}

class _ShapePainter extends CustomPainter {
  _ShapePainter(this.s, this.maxL);
  final RugSize s;
  final double maxL;
  @override
  void paint(Canvas c, Size z) {
    final k = z.height * .92 / max(maxL, s.l);
    final h = max(14.0, s.l * k), w = max(9.0, s.w * k);
    final r = Rect.fromCenter(center: z.center(Offset.zero), width: w, height: h);
    c.drawRRect(RRect.fromRectAndRadius(r, const Radius.circular(2)), Paint()..color = C.brand50);
    c.drawRRect(
        RRect.fromRectAndRadius(r, const Radius.circular(2)),
        Paint()
          ..color = C.brand
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6);
    final inner = r.deflate(min(w, h) * .14);
    c.drawRect(
        inner,
        Paint()
          ..color = C.brand200
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1);
    c.drawCircle(r.center, min(w, h) * .16, Paint()..color = C.gold);
  }

  @override
  bool shouldRepaint(_ShapePainter o) => o.s != s;
}

/// «سایزیاب»: نوع اتاق + طول و عرض ← سایز پیشنهادی با پوشش کف و فاصله از دیوار
class SizeFinder extends StatefulWidget {
  const SizeFinder({super.key, required this.sizes});
  final List<RugSize> sizes;
  @override
  State<SizeFinder> createState() => _SizeFinderState();
}

class _SizeFinderState extends State<SizeFinder> {
  String _type = 'liv';
  double _l = 5, _w = 4;
  static const _types = {'liv': 'پذیرایی', 'bed': 'اتاق خواب', 'din': 'ناهارخوری', 'hall': 'راهرو'};

  ({RugSize? best, List<RugSize> alts}) _calc() {
    final big = max(_l, _w), small = min(_l, _w);
    final all = widget.sizes;
    final cand = switch (_type) {
      'hall' => all.where((s) => s.kind == SizeKind.runner),
      'bed' => all.where((s) => (s.kind == SizeKind.rug && s.area <= 6.01) || s.kind == SizeKind.small),
      _ => all.where((s) => s.kind == SizeKind.rug || s.kind == SizeKind.small),
    }
        .toList()
      ..sort((a, b) => b.area.compareTo(a.area));
    final m = _type == 'hall' ? .15 : (_type == 'bed' ? .45 : .3);
    final fits = cand.where((s) => s.w <= small - 2 * m + 1e-9 && s.l <= big - 2 * m + 1e-9).toList();
    return (best: fits.isEmpty ? null : fits.first, alts: fits.skip(1).take(2).toList());
  }

  Widget _stepper(String label, double v, ValueChanged<double> on) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Container(
          height: 44,
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.line, width: 1.5), borderRadius: BorderRadius.circular(8)),
          child: Row(children: [
            _sb(Icons.add_rounded, 'نیم متر بیشتر', v < 15 ? () => on(v + .5) : null),
            Expanded(child: Text(faDigits(metres(v)), textAlign: TextAlign.center, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 16))),
            _sb(Icons.remove_rounded, 'نیم متر کمتر', v > 1 ? () => on(v - .5) : null),
          ]),
        ),
      ]);

  Widget _sb(IconData ic, String tip, VoidCallback? on) => IconButton(
        tooltip: tip,
        onPressed: on,
        style: IconButton.styleFrom(minimumSize: const Size(40, 42), padding: EdgeInsets.zero, foregroundColor: C.brand),
        icon: Icon(ic, size: 20),
      );

  @override
  Widget build(BuildContext context) {
    final r = _calc();
    final best = r.best;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 0),
      padding: const EdgeInsets.all(16),
      decoration: boxDeco(r: 20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Container(
            width: 42,
            height: 42,
            decoration: BoxDecoration(color: C.brand50, borderRadius: BorderRadius.circular(12)),
            child: const Icon(Icons.straighten_rounded, color: C.brand),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('سایزیاب فرش', style: TextStyle(fontSize: 16.5, fontWeight: FontWeight.w800, height: 1.4)),
              Text('ابعاد اتاق را بدهید؛ سایز درست را پیشنهاد می‌دهیم.', style: TextStyle(fontSize: 12, color: C.muted)),
            ]),
          ),
        ]),
        const SizedBox(height: 14),
        Container(
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(8)),
          child: Row(children: [
            for (final e in _types.entries)
              Expanded(
                child: Semantics(
                  selected: _type == e.key,
                  button: true,
                  child: GestureDetector(
                    onTap: () => setState(() => _type = e.key),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 160),
                      height: 38,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                          color: _type == e.key ? Colors.white : Colors.transparent,
                          borderRadius: BorderRadius.circular(6),
                          boxShadow: _type == e.key ? kShadow1 : null),
                      child: Text(e.value,
                          style: TextStyle(
                              fontSize: 12.5,
                              fontWeight: _type == e.key ? FontWeight.w800 : FontWeight.w600,
                              color: _type == e.key ? C.brand : C.muted)),
                    ),
                  ),
                ),
              ),
          ]),
        ),
        const SizedBox(height: 12),
        Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Expanded(child: _stepper('طول اتاق (متر)', _l, (v) => setState(() => _l = v))),
          const Padding(padding: EdgeInsets.fromLTRB(8, 0, 8, 12), child: Text('×', style: TextStyle(color: C.faint, fontWeight: FontWeight.w700))),
          Expanded(child: _stepper('عرض اتاق (متر)', _w, (v) => setState(() => _w = v))),
        ]),
        const SizedBox(height: 14),
        const _Dash(),
        const SizedBox(height: 14),
        if (best == null)
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: C.warnTint, borderRadius: BorderRadius.circular(10)),
            child: const Text('این اتاق برای فرش‌های این دسته کوچک است؛ قالیچه یا پادری را ببینید.',
                style: TextStyle(color: C.warn, fontSize: 13, fontWeight: FontWeight.w600)),
          )
        else ...[
          Row(children: [
            SizedBox(width: 104, height: 80, child: CustomPaint(painter: _RoomPainter(_l, _w, best))),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Text('سایز پیشنهادی', style: TextStyle(fontSize: 12, color: C.muted)),
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6),
                    decoration: BoxDecoration(color: C.gold100, borderRadius: BorderRadius.circular(4)),
                    child: const Text('بهترین', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: C.goldInk)),
                  ),
                ]),
                Text('${best.kind == SizeKind.rug ? 'فرش ' : ''}${faDigits(best.name)} · ${best.dims}',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: C.brand800, height: 1.5)),
                Text(_meta(best), style: const TextStyle(fontSize: 12, color: C.ink2, height: 1.6)),
              ]),
            ),
          ]),
          if (r.alts.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(spacing: 6, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: [
              const Text('جایگزین:', style: TextStyle(fontSize: 12.5, color: C.muted)),
              for (final a in r.alts)
                ActionChip(
                  visualDensity: VisualDensity.compact,
                  backgroundColor: Colors.white,
                  side: const BorderSide(color: C.line),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  labelStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: C.ink2),
                  label: Text('${faDigits(a.name)} · ${a.dims}'),
                  onPressed: () => a.open(context),
                ),
            ]),
          ],
          const SizedBox(height: 12),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(10, 48)),
            onPressed: () => best.open(context),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Flexible(child: Text('مشاهدهٔ فرش‌های ${faDigits(best.name)}', overflow: TextOverflow.ellipsis)),
              const Icon(Icons.chevron_left_rounded),
            ]),
          ),
        ],
      ]),
    );
  }

  String _meta(RugSize s) {
    final cov = (s.area / (_l * _w) * 100).round();
    final small = min(_l, _w), big = max(_l, _w);
    final mx = ((small - s.w) / 2 * 100).round(), my = ((big - s.l) / 2 * 100).round();
    final dist = mx == my ? faDigits(mx) : '${faDigits(min(mx, my))} تا ${faDigits(max(mx, my))}';
    return 'پوشش کف ${faDigits(cov)}٪ · فاصله از دیوار $dist سانتی‌متر';
  }
}

class _Dash extends StatelessWidget {
  const _Dash();
  @override
  Widget build(BuildContext context) => CustomPaint(size: const Size(double.infinity, 1), painter: _DashPainter());
}

class _DashPainter extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final p = Paint()..color = C.line;
    for (var x = 0.0; x < s.width; x += 7) {
      c.drawLine(Offset(x, 0), Offset(min(x + 4, s.width), 0), p);
    }
  }

  @override
  bool shouldRepaint(_DashPainter o) => false;
}

/// اتاق از بالا با فرش پیشنهادی به مقیاس
class _RoomPainter extends CustomPainter {
  _RoomPainter(this.l, this.w, this.s);
  final double l, w;
  final RugSize s;
  @override
  void paint(Canvas c, Size z) {
    final big = max(l, w), small = min(l, w);
    final sc = min((z.width - 6) / big, (z.height - 6) / small);
    final room = Rect.fromCenter(center: z.center(Offset.zero), width: big * sc, height: small * sc);
    c.drawRect(room, Paint()..color = Colors.white);
    c.drawRect(
        room,
        Paint()
          ..color = C.ink2
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5);
    final rug = Rect.fromCenter(center: room.center, width: s.l * sc, height: s.w * sc);
    c.drawRect(rug, Paint()..color = C.brand100);
    c.drawRect(
        rug,
        Paint()
          ..color = C.brand
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
    c.drawRRect(
        RRect.fromRectAndRadius(Rect.fromCenter(center: rug.center, width: rug.width * .4, height: rug.height * .5), Radius.circular(rug.height * .2)),
        Paint()..color = C.gold.withValues(alpha: .55));
  }

  @override
  bool shouldRepaint(_RoomPainter o) => o.l != l || o.w != w || o.s != s;
}
