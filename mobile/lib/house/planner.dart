import 'dart:math';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'lens.dart';
import 'ui.dart';

/// «اندازه در اتاق شما»: نقشهٔ اتاق از بالا با اندازهٔ واقعی؛ فرش را می‌کشید، می‌چرخانید و فاصله تا دیوارها را می‌بینید.
class HousePlannerScreen extends StatefulWidget {
  const HousePlannerScreen({super.key, required this.args});
  final Map<String, dynamic> args;
  @override
  State<HousePlannerScreen> createState() => _HousePlannerScreenState();
}

class _PlSize {
  _PlSize(this.l, this.w, this.name, this.index);
  final int l, w, index; // سانتی‌متر
  final String name;
}

class _HousePlannerScreenState extends State<HousePlannerScreen> {
  Json? _p;
  final _sizes = <_PlSize>[];
  int _k = 0;
  int _len = 500, _wid = 400;
  bool _rot = false;
  double _cx = 250, _cy = 200;
  ui.Image? _img;
  RugCrop _crop = RugCrop.full;
  Offset? _drag;
  double _dcx = 0, _dcy = 0;
  final _l = TextEditingController(text: '۵'), _w = TextEditingController(text: '۴');

  @override
  void initState() {
    super.initState();
    _init();
  }

  Future<void> _init() async {
    var p = widget.args['product'] as Json?;
    if (p == null) {
      try {
        p = await Api.i.get('/products/${widget.args['id']}/') as Json;
      } on ApiError catch (e) {
        if (mounted) toast(context, e.message);
        return;
      }
    }
    final all = (p['sizes'] as List).cast<Json>();
    final seen = <String>{};
    for (var i = 0; i < all.length; i++) {
      final s = all[i];
      final l = ((s['length'] as num) * 100).round(), w = ((s['width'] as num) * 100).round();
      if (l <= 0 || w <= 0 || s['round'] == true || !seen.add('${l}x$w')) continue;
      _sizes.add(_PlSize(max(l, w), min(l, w), (s['label'] as String).replaceAll(RegExp(r'\s*\([^()]*\)\s*$'), ''), i));
    }
    final want = widget.args['size'] as int? ?? -1;
    var k = _sizes.indexWhere((s) => s.index == want);
    if (k < 0) k = _sizes.indexWhere((s) => s.name.contains('۱۲'));
    final images = ((p['images'] as List?) ?? []).cast<Json>();
    final url = images.isNotEmpty ? images.first['thumb'] as String? ?? '' : p['image'] as String? ?? '';
    setState(() {
      _p = p;
      _k = max(0, k);
      _crop = RugCrop.of(images.isNotEmpty ? images.first['crop'] : p!['crop']);
    });
    _fit(true);
    final px = await RugPixels.load(url);
    if (mounted && px != null) setState(() => _img = px.image);
  }

  ({double w, double h, bool horiz}) get _rug {
    final s = _sizes[_k];
    final horiz = (_len >= _wid) != _rot;
    return (w: (horiz ? s.l : s.w).toDouble(), h: (horiz ? s.w : s.l).toDouble(), horiz: horiz);
  }

  void _fit(bool reclamp) {
    if (_sizes.isEmpty) return;
    final r = _rug;
    if (reclamp) {
      _cx = r.w > _len ? _len / 2 : _cx.clamp(r.w / 2, _len - r.w / 2);
      _cy = r.h > _wid ? _wid / 2 : _cy.clamp(r.h / 2, _wid - r.h / 2);
    }
  }

  void _setDims() {
    double v(TextEditingController c) => (double.tryParse(latin(c.text).replaceAll('٫', '.').replaceAll('/', '.')) ?? 4).clamp(1, 20);
    setState(() {
      _len = (v(_l) * 100).round();
      _wid = (v(_w) * 100).round();
      _cx = _len / 2;
      _cy = _wid / 2;
      _fit(true);
    });
  }

  void _step(TextEditingController c, double d) {
    final v = ((double.tryParse(latin(c.text).replaceAll('٫', '.')) ?? 4) + d).clamp(1.0, 20.0);
    c.text = faDigits(v == v.roundToDouble() ? v.toInt() : v).replaceAll('.', '٫');
    _setDims();
  }

  String m(num cm) => metres(cm / 100);

  @override
  Widget build(BuildContext context) {
    final p = _p;
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(backgroundColor: Colors.white, surfaceTintColor: Colors.white, title: const Text('اندازه در اتاق شما')),
      body: p == null
          ? const Loading()
          : _sizes.isEmpty
              ? const StatusView(message: 'برای این فرش سایز مستطیل ثبت نشده است.', icon: Icons.straighten_rounded)
              : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 32), children: [
                  Text('طول و عرض اتاق را بدهید؛ فرش با اندازهٔ واقعی روی نقشه می‌نشیند. فرش را با انگشت جابه‌جا کنید.',
                      style: const TextStyle(color: C.ink2, height: 1.9)),
                  const SizedBox(height: 10),
                  Row(children: [
                    Expanded(child: _dim('طول اتاق (متر)', _l)),
                    const SizedBox(width: 10),
                    Expanded(child: _dim('عرض اتاق (متر)', _w)),
                  ]),
                  const SizedBox(height: 14),
                  _plan(),
                  const SizedBox(height: 10),
                  _readout(),
                  const SizedBox(height: 12),
                  Wrap(spacing: 8, runSpacing: 8, children: [
                    for (var i = 0; i < _sizes.length; i++)
                      ChoiceChip(
                        showCheckmark: false,
                        selected: i == _k,
                        selectedColor: C.brand50,
                        backgroundColor: Colors.white,
                        side: BorderSide(color: i == _k ? C.brand : C.line, width: 1.5),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                        label: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(faDigits(_sizes[i].name), style: TextStyle(fontWeight: FontWeight.w800, color: i == _k ? C.brand : C.ink)),
                          Text('${faDigits(m(_sizes[i].l))} × ${faDigits(m(_sizes[i].w))}',
                              style: const TextStyle(fontSize: 11.5, color: C.muted)),
                        ]),
                        onSelected: (_) => setState(() {
                          _k = i;
                          _fit(true);
                        }),
                      ),
                  ]),
                  const SizedBox(height: 12),
                  Row(children: [
                    Expanded(
                        child: OutlinedButton.icon(
                            onPressed: () => setState(() {
                              _rot = !_rot;
                              _fit(true);
                            }),
                            icon: const Icon(Icons.rotate_90_degrees_ccw_rounded),
                            label: const Text('چرخاندن ۹۰ درجه'))),
                    const SizedBox(width: 10),
                    Expanded(
                        child: OutlinedButton(
                            onPressed: () => setState(() => (_cx = _len / 2, _cy = _wid / 2)), child: const Text('وسط اتاق'))),
                  ]),
                  const SizedBox(height: 14),
                  FilledButton(
                    onPressed: () => Navigator.pop(context, _sizes[_k].index),
                    child: const Text('بازگشت و انتخاب همین سایز'),
                  ),
                ]),
    );
  }

  Widget _dim(String label, TextEditingController c) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12.5, color: C.muted)),
        const SizedBox(height: 4),
        Container(
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: C.line, width: 1.5), borderRadius: BorderRadius.circular(10)),
          child: Row(children: [
            IconButton(tooltip: 'نیم متر بیشتر', color: C.brand, onPressed: () => _step(c, .5), icon: const Icon(Icons.add_rounded)),
            Expanded(
              child: TextField(
                controller: c,
                textAlign: TextAlign.center,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
                decoration: const InputDecoration(filled: false, border: InputBorder.none, isDense: true),
                onSubmitted: (_) => _setDims(),
                onTapOutside: (_) {
                  FocusScope.of(context).unfocus();
                  _setDims();
                },
              ),
            ),
            IconButton(tooltip: 'نیم متر کمتر', color: C.brand, onPressed: () => _step(c, -.5), icon: const Icon(Icons.remove_rounded)),
          ]),
        ),
      ]);

  static const _margin = 60.0;

  Widget _plan() {
    return LayoutBuilder(builder: (_, bc) {
      final w = bc.maxWidth;
      final scale = w / (_len + 2 * _margin);
      final h = (_wid + 2 * _margin) * scale;
      Offset toRoom(Offset o) => Offset(o.dx / scale - _margin, o.dy / scale - _margin);
      return Container(
        decoration: BoxDecoration(color: C.surface2, border: Border.all(color: C.line), borderRadius: BorderRadius.circular(14)),
        clipBehavior: Clip.antiAlias,
        child: GestureDetector(
          onPanStart: (d) {
            final q = toRoom(d.localPosition), r = _rug;
            if ((q.dx - _cx).abs() <= r.w / 2 + 30 && (q.dy - _cy).abs() <= r.h / 2 + 30) {
              _drag = q;
              _dcx = _cx;
              _dcy = _cy;
            }
          },
          onPanUpdate: (d) {
            if (_drag == null) return;
            final q = toRoom(d.localPosition);
            setState(() {
              _cx = _dcx + q.dx - _drag!.dx;
              _cy = _dcy + q.dy - _drag!.dy;
              _fit(true);
            });
          },
          onPanEnd: (_) => _drag = null,
          child: Semantics(
            label: 'نقشهٔ اتاق ${m(_len)} در ${m(_wid)} متر با فرش ${_sizes[_k].name}',
            child: CustomPaint(
              size: Size(w, h),
              painter: _PlanPainter(L: _len.toDouble(), W: _wid.toDouble(), cx: _cx, cy: _cy, rug: _rug, img: _img, crop: _crop, scale: scale, margin: _margin),
            ),
          ),
        ),
      );
    });
  }

  Widget _readout() {
    final r = _rug;
    final x0 = _cx - r.w / 2, y0 = _cy - r.h / 2;
    final top = y0, bottom = _wid - (y0 + r.h), left = x0, right = _len - (x0 + r.w);
    final big = r.w > _len || r.h > _wid;
    final s = _sizes[_k];
    String warn = '';
    if (big) {
      warn = 'این فرش از اتاق بزرگ‌تر است.${r.h <= _len && r.w <= _wid ? ' با چرخاندن ۹۰ درجه جا می‌شود.' : ' سایز کوچک‌تری انتخاب کنید.'}';
    } else if ([top, bottom, left, right].reduce(min) < 20) {
      warn = 'فرش به دیوار خیلی نزدیک است؛ معمولاً ۲۰ تا ۶۰ سانت فاصله خوش‌نشین‌تر است.';
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(color: C.brand50, border: Border.all(color: C.brand100), borderRadius: BorderRadius.circular(12)),
        child: Text(
          big
              ? 'فرش ${faDigits(s.name)} (${faDigits(m(s.l))} × ${faDigits(m(s.w))}) روی اتاق ${faDigits(m(_len))} × ${faDigits(m(_wid))} متر.'
              : 'فاصلهٔ فرش ${faDigits(s.name)} تا دیوارها: تا پنجره ${faDigits(m(top))}، تا دیوار مبل ${faDigits(m(bottom))}، '
                  'تا دیوار در ${faDigits(m(left))} و تا دیوار روبه‌رو ${faDigits(m(right))} متر.',
          style: const TextStyle(fontSize: 13.5, height: 1.9),
        ),
      ),
      if (warn.isNotEmpty)
        Container(
          margin: const EdgeInsets.only(top: 8),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: C.warnTint, borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFF2DDB0))),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Padding(padding: EdgeInsets.only(top: 2), child: Icon(Icons.warning_amber_rounded, size: 18, color: C.warn)),
            const SizedBox(width: 8),
            Expanded(child: Text(warn, style: const TextStyle(color: C.warn, fontWeight: FontWeight.w700, fontSize: 13.5, height: 1.8))),
          ]),
        ),
    ]);
  }
}

class _PlanPainter extends CustomPainter {
  _PlanPainter({required this.L, required this.W, required this.cx, required this.cy, required this.rug, required this.img,
      required this.crop, required this.scale, required this.margin});
  final double L, W;
  final double cx, cy, scale, margin;
  final ({double w, double h, bool horiz}) rug;
  final ui.Image? img;
  final RugCrop crop;

  @override
  void paint(Canvas c, Size size) {
    c.save();
    c.scale(scale);
    c.translate(margin, margin);
    final room = Rect.fromLTWH(0, 0, L.toDouble(), W.toDouble());
    const t = 18.0;
    // دیوارها
    c.drawRect(room.inflate(t), Paint()..color = const Color(0xFF323C52));
    c.drawRect(room, Paint()..color = Colors.white);
    final grid = Paint()
      ..color = const Color(0xFFE6EAF1)
      ..strokeWidth = 1.2;
    for (var x = 50.0; x < L; x += 50) {
      c.drawLine(Offset(x, 0), Offset(x, W.toDouble()), grid);
    }
    for (var y = 50.0; y < W; y += 50) {
      c.drawLine(Offset(0, y), Offset(L.toDouble(), y), grid);
    }
    // پنجره (ارسی) در دیوار بالا
    final ow = min(L * .6, 360.0), ox = (L - ow) / 2;
    c.drawRect(Rect.fromLTWH(ox, -t, ow, t), Paint()..color = Colors.white);
    c.drawRect(Rect.fromLTWH(ox + 3, -t / 2 - 2, ow - 6, 4), Paint()..color = const Color(0xFFC3D0EC));
    // در در دیوار چپ
    final dl = min(90.0, W * .3), dy = W - min(110.0, W * .4);
    c.drawRect(Rect.fromLTWH(-t - 1, dy, t + 2, dl), Paint()..color = Colors.white);
    c.drawArc(Rect.fromCircle(center: Offset(0, dy), radius: dl), 0, pi / 2, false,
        Paint()
          ..color = const Color(0xFF8A92A3)
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5);
    c.drawLine(Offset(0, dy), Offset(dl, dy), Paint()..color = const Color(0xFF323C52)..strokeWidth = 2.5);

    // فرش
    final big = rug.w > L || rug.h > W;
    c.save();
    c.translate(cx, cy);
    final double sw = min(rug.w, rug.h), sl = max(rug.w, rug.h);
    if (rug.horiz) c.rotate(pi / 2);
    final dst = Rect.fromCenter(center: Offset.zero, width: sw, height: sl);
    c.drawRect(dst.shift(const Offset(0, 6)), Paint()..color = const Color(0x33000000)..maskFilter = const MaskFilter.blur(BlurStyle.normal, 6));
    final im = img;
    if (im != null) {
      final src = Rect.fromLTWH(im.width * crop.x / 100, im.height * crop.y / 100, im.width * crop.w / 100, im.height * crop.h / 100);
      c.drawImageRect(im, src, dst, Paint()..filterQuality = FilterQuality.medium);
    } else {
      c.drawRect(dst, Paint()..color = const Color(0xFFDDE5F5));
    }
    c.restore();
    c.drawRect(Rect.fromCenter(center: Offset(cx, cy), width: rug.w, height: rug.h),
        Paint()
          ..color = big ? const Color(0xFFB4352F) : const Color(0x40000000)
          ..style = PaintingStyle.stroke
          ..strokeWidth = big ? 5 : 1.5);

    // مبلمان
    final fur = Paint()..color = const Color(0xD9F4F6F9), edge = Paint()..color = const Color(0xFF8A92A3)..style = PaintingStyle.stroke..strokeWidth = 2;
    final sofaW = min(220.0, L * .5), sx = L / 2 - sofaW / 2, sy = W - 90.0 - 12;
    final sofa = RRect.fromRectAndRadius(Rect.fromLTWH(sx, sy, sofaW, 90), const Radius.circular(10));
    c.drawRRect(sofa, fur);
    c.drawRRect(sofa, edge);
    if (L >= 300) {
      for (final ax in [max(10.0, sx - 95), min(L - 95.0, sx + sofaW + 10)]) {
        final a = RRect.fromRectAndRadius(Rect.fromLTWH(ax, W / 2 - 42, 85, 85), const Radius.circular(10));
        c.drawRRect(a, fur);
        c.drawRRect(a, edge);
      }
    }
    final table = RRect.fromRectAndRadius(Rect.fromLTWH(L / 2 - 55, W / 2 - 10, 110, 55), const Radius.circular(4));
    c.drawRRect(table, Paint()..color = const Color(0x8CC3D0EC));
    c.drawRRect(table, edge);
    c.drawCircle(Offset(L - 34.0, 34), 22, Paint()..color = const Color(0x8C0D7146));
    c.drawCircle(Offset(L - 34.0, 34), 22, edge);

    // اندازه‌ها
    final fs = max(L, W) / 26;
    void label(String s, Offset at, {Color bg = const Color(0xFF1D3F8F), Color fg = Colors.white, bool box = true}) {
      final tp = TextPainter(
        text: TextSpan(text: s, style: TextStyle(fontFamily: kFont, fontSize: fs, fontWeight: FontWeight.w800, color: box ? fg : const Color(0xFF5A6377))),
        textDirection: TextDirection.rtl,
      )..layout();
      final r = Rect.fromCenter(center: at, width: tp.width + fs * .8, height: tp.height + fs * .2);
      if (box) c.drawRRect(RRect.fromRectAndRadius(r, Radius.circular(fs * .3)), Paint()..color = bg);
      tp.paint(c, Offset(r.left + fs * .4, r.top + fs * .1));
    }

    String mm(double v) => faDigits(metres(v / 100));
    if (!big) {
      final x0 = cx - rug.w / 2, y0 = cy - rug.h / 2;
      final ax = cx + rug.w * .22, ay = cy + rug.h * .22;
      final ln = Paint()..color = const Color(0xFF1D3F8F)..strokeWidth = 2;
      void dimLine(Offset a, Offset b, double v) {
        if (v <= 1) return;
        c.drawLine(a, b, ln);
        c.drawCircle(a, 3.5, ln);
        c.drawCircle(b, 3.5, ln);
        label(mm(v), Offset((a.dx + b.dx) / 2, (a.dy + b.dy) / 2));
      }

      dimLine(Offset(ax, 0), Offset(ax, y0), y0);
      dimLine(Offset(ax, y0 + rug.h), Offset(ax, W.toDouble()), W - (y0 + rug.h));
      dimLine(Offset(0, ay), Offset(x0, ay), x0);
      dimLine(Offset(x0 + rug.w, ay), Offset(L.toDouble(), ay), L - (x0 + rug.w));
    }
    label('طول ${mm(L.toDouble())} متر', Offset(L / 2, W + t + fs * 1.1), box: false);
    label('پنجره', Offset(L / 2, -t - fs * .9), box: false);
    c.restore();
  }

  @override
  bool shouldRepaint(_PlanPainter o) =>
      o.L != L || o.W != W || o.cx != cx || o.cy != cy || o.rug != rug || o.img != img || o.scale != scale;
}
