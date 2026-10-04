import 'dart:math';
import 'dart:ui' as ui;

import 'package:camera/camera.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:image_picker/image_picker.dart';
import 'package:share_plus/share_plus.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

/// فرش در اتاق: تصویر فرش روی دوربین یا عکس اتاق قرار می‌گیرد؛
/// با یک انگشت جابه‌جا، با دو انگشت بزرگ/کوچک و چرخانده می‌شود و شیب آن با زاویهٔ کف تنظیم می‌شود.
/// به ARCore نیاز ندارد، پس روی همهٔ گوشی‌ها کار می‌کند.
class RoomScreen extends StatefulWidget {
  const RoomScreen({super.key, required this.args});
  final Map<String, dynamic> args;
  @override
  State<RoomScreen> createState() => _RoomScreenState();
}

class _RoomScreenState extends State<RoomScreen> with WidgetsBindingObserver {
  Json? _p;
  int _size = 0;
  CameraController? _cam;
  String? _camErr;
  Uint8List? _photo; // عکس اتاق به‌جای دوربین
  final _shot = GlobalKey();

  // وضعیت فرش روی صفحه
  Offset _pos = Offset.zero;
  double _scale = 1, _rot = 0, _tilt = .9; // tilt: زاویهٔ کف (رادیان)
  double _s0 = 1, _r0 = 0;
  bool _hint = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
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
    final sizes = _rectSizes(p);
    var sel = (widget.args['size'] as int?) ?? -1;
    final all = (p['sizes'] as List).cast<Json>();
    if (sel >= 0 && sel < all.length) sel = sizes.indexOf(all[sel]);
    if (sel < 0) sel = sizes.indexWhere((s) => (s['label'] as String).contains('۱۲'));
    setState(() => (_p = p, _size = max(0, sel)));
    _startCamera();
  }

  List<Json> _rectSizes(Json p) => (p['sizes'] as List).cast<Json>().where((s) => (s['width'] as num) > 0 || (s['diameter'] as num) > 0).toList();

  Future<void> _startCamera() async {
    try {
      final cams = await availableCameras();
      final back = cams.firstWhere((c) => c.lensDirection == CameraLensDirection.back, orElse: () => cams.first);
      final c = CameraController(back, ResolutionPreset.high, enableAudio: false);
      await c.initialize();
      if (!mounted) {
        await c.dispose();
        return;
      }
      setState(() => _cam = c);
    } catch (e) {
      if (mounted) setState(() => _camErr = 'دوربین در دسترس نیست. یک عکس از اتاقتان انتخاب کنید.');
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState s) {
    if (s == AppLifecycleState.inactive) {
      _cam?.dispose();
      _cam = null;
    } else if (s == AppLifecycleState.resumed && _photo == null && _cam == null) {
      _startCamera();
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _cam?.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto(ImageSource src) async {
    final x = await ImagePicker().pickImage(source: src, maxWidth: 2000, imageQuality: 88);
    if (x == null) return;
    final bytes = await x.readAsBytes();
    await _cam?.dispose();
    setState(() => (_cam = null, _photo = bytes));
  }

  Future<void> _share() async {
    try {
      final b = _shot.currentContext!.findRenderObject() as RenderRepaintBoundary;
      final img = await b.toImage(pixelRatio: 2);
      final data = await img.toByteData(format: ui.ImageByteFormat.png);
      await SharePlus.instance.share(ShareParams(
        text: '${_p!['title']}\n${_p!['url']}',
        files: [XFile.fromData(data!.buffer.asUint8List(), mimeType: 'image/png', name: 'irancarpet-room.png')],
      ));
    } catch (_) {
      if (mounted) toast(context, 'ذخیرهٔ تصویر ممکن نشد.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = _p;
    return Scaffold(
      backgroundColor: Colors.black,
      body: p == null
          ? const Loading()
          : LayoutBuilder(builder: (context, box) {
              final sizes = _rectSizes(p);
              final s = sizes.isEmpty ? null : sizes[_size.clamp(0, sizes.length - 1)];
              // اندازهٔ پایهٔ فرش روی صفحه: ۱۲ متری (۳×۴) حدود ۴۵٪ عرض صفحه
              final unit = box.maxWidth * .45 / 3;
              final w = s == null ? 3.0 : ((s['diameter'] as num) > 0 ? (s['diameter'] as num).toDouble() : (s['width'] as num).toDouble());
              final l = s == null ? 4.0 : ((s['diameter'] as num) > 0 ? (s['diameter'] as num).toDouble() : (s['length'] as num).toDouble());
              final round = s?['round'] == true;
              return Stack(fit: StackFit.expand, children: [
                RepaintBoundary(
                  key: _shot,
                  child: Stack(fit: StackFit.expand, children: [
                    _background(),
                    GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onScaleStart: (_) {
                        _s0 = _scale;
                        _r0 = _rot;
                        setState(() => _hint = false);
                      },
                      onScaleUpdate: (d) => setState(() {
                        _pos += d.focalPointDelta;
                        if (d.pointerCount > 1) {
                          _scale = (_s0 * d.scale).clamp(.3, 4);
                          _rot = _r0 + d.rotation;
                        }
                      }),
                      child: Center(
                        child: Transform.translate(
                          offset: _pos + Offset(0, box.maxHeight * .12),
                          child: Transform(
                            alignment: Alignment.center,
                            transform: Matrix4.identity()
                              ..setEntry(3, 2, 0.0012)
                              ..rotateX(_tilt)
                              ..rotateZ(_rot)
                              ..scaleByDouble(_scale, _scale, 1, 1),
                            child: Container(
                              width: w * unit,
                              height: l * unit,
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(round ? 999 : 4),
                                boxShadow: const [BoxShadow(color: Color(0x88000000), blurRadius: 18, offset: Offset(0, 10))],
                              ),
                              clipBehavior: Clip.antiAlias,
                              child: NetImage(p['image'] as String, fit: BoxFit.fill),
                            ),
                          ),
                        ),
                      ),
                    ),
                  ]),
                ),
                // بالا
                Positioned(
                  top: 0,
                  left: 0,
                  right: 0,
                  child: SafeArea(
                    child: Row(children: [
                      _roundBtn(Icons.close_rounded, 'بستن', () => Navigator.pop(context)),
                      Expanded(
                        child: Text(p['title'] as String,
                            maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, shadows: [Shadow(blurRadius: 6)])),
                      ),
                      _roundBtn(Icons.ios_share_rounded, 'اشتراک تصویر', _share),
                    ]),
                  ),
                ),
                if (_hint)
                  const Positioned(
                    top: 110,
                    left: 24,
                    right: 24,
                    child: _Hint('فرش را با یک انگشت جابه‌جا کن، با دو انگشت بزرگ و کوچک کن و بچرخان.'),
                  ),
                if (_camErr != null && _photo == null)
                  Center(child: Padding(padding: const EdgeInsets.all(32), child: _Hint(_camErr!))),
                // پایین: سایزها، شیب کف، منبع تصویر
                Positioned(
                  left: 0,
                  right: 0,
                  bottom: 0,
                  child: Container(
                    decoration: const BoxDecoration(
                        gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Colors.transparent, Color(0xCC000000)])),
                    child: SafeArea(
                      top: false,
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(12, 24, 12, 10),
                        child: Column(mainAxisSize: MainAxisSize.min, children: [
                          Row(children: [
                            const Icon(Icons.straighten_rounded, color: Colors.white70, size: 18),
                            const SizedBox(width: 6),
                            const Text('زاویهٔ کف', style: TextStyle(color: Colors.white70, fontSize: 12.5)),
                            Expanded(
                              child: Slider(
                                value: _tilt,
                                min: 0,
                                max: 1.3,
                                activeColor: C.saffron,
                                inactiveColor: Colors.white24,
                                onChanged: (v) => setState(() => _tilt = v),
                              ),
                            ),
                          ]),
                          SizedBox(
                            height: 40,
                            child: ListView.separated(
                              scrollDirection: Axis.horizontal,
                              itemCount: sizes.length,
                              separatorBuilder: (_, _) => const SizedBox(width: 8),
                              itemBuilder: (_, i) {
                                final on = i == _size;
                                return ChoiceChip(
                                  selected: on,
                                  showCheckmark: false,
                                  selectedColor: C.pink,
                                  backgroundColor: Colors.white.withValues(alpha: .16),
                                  labelStyle: TextStyle(fontFamily: kFont, color: Colors.white, fontWeight: on ? FontWeight.w800 : FontWeight.w500),
                                  label: Text(_sizeLabel(sizes[i])),
                                  onSelected: (_) => setState(() => _size = i),
                                );
                              },
                            ),
                          ),
                          const SizedBox(height: 10),
                          Row(children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Colors.white38)),
                                onPressed: () => _pickPhoto(ImageSource.gallery),
                                icon: const Icon(Icons.photo_library_outlined, size: 19),
                                label: const Text('عکس اتاقم'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: OutlinedButton.icon(
                                style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Colors.white38)),
                                onPressed: () {
                                  if (_photo != null) {
                                    setState(() => _photo = null);
                                    _startCamera();
                                  } else {
                                    setState(() => (_pos = Offset.zero, _scale = 1, _rot = 0, _tilt = .9));
                                  }
                                },
                                icon: Icon(_photo != null ? Icons.videocam_outlined : Icons.restart_alt_rounded, size: 19),
                                label: Text(_photo != null ? 'دوربین زنده' : 'از نو'),
                              ),
                            ),
                          ]),
                        ]),
                      ),
                    ),
                  ),
                ),
              ]);
            }),
    );
  }

  String _sizeLabel(Json s) {
    final d = (s['diameter'] as num).toDouble();
    if (d > 0) return 'گرد ${metres(d)}';
    return '${metres((s['length'] as num).toDouble())}×${metres((s['width'] as num).toDouble())}';
  }

  Widget _background() {
    if (_photo != null) return Image.memory(_photo!, fit: BoxFit.cover);
    final c = _cam;
    if (c != null && c.value.isInitialized) {
      return FittedBox(
        fit: BoxFit.cover,
        child: SizedBox(width: c.value.previewSize?.height ?? 1080, height: c.value.previewSize?.width ?? 1920, child: CameraPreview(c)),
      );
    }
    return Container(color: const Color(0xFF1B1E44));
  }

  Widget _roundBtn(IconData i, String tip, VoidCallback onTap) => Padding(
        padding: const EdgeInsets.all(8),
        child: IconButton.filled(
          tooltip: tip,
          style: IconButton.styleFrom(backgroundColor: Colors.black38, foregroundColor: Colors.white),
          onPressed: onTap,
          icon: Icon(i),
        ),
      );
}

class _Hint extends StatelessWidget {
  const _Hint(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(16)),
        child: Text(text, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, height: 1.7)),
      );
}
