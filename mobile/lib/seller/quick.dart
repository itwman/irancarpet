import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

class _Photo {
  _Photo(this.file, this.bytes);
  final XFile file;
  final Uint8List bytes;
  final design = TextEditingController();
  String color = '';
  bool samePrev = false; // عکس دیگری از همان فرش قبلی
}

/// افزودن چند فرش با عکس: آلبوم و دسته را یک بار انتخاب کنید، برای هر عکس نقشه و رنگ؛ قیمت از آلبوم می‌آید.
class SellerQuick extends StatefulWidget {
  const SellerQuick({super.key});
  @override
  State<SellerQuick> createState() => _SellerQuickState();
}

class _SellerQuickState extends State<SellerQuick> {
  Json? _opt;
  String? _error;
  int? _album, _cat;
  final _prefix = TextEditingController();
  final _photos = <_Photo>[];
  final _specs = <int, int?>{};
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final d = await Api.i.get('/seller/options/') as Json;
      final albums = (d['albums'] as List).cast<Map>();
      setState(() {
        _opt = d;
        _error = null;
        if (albums.length == 1) _pickAlbum(asInt(albums.first['id']), albums.first);
      });
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    }
  }

  void _pickAlbum(int id, Map a) {
    final oldName = _album == null ? '' : '${(_opt!['albums'] as List).cast<Map>().firstWhere((x) => asInt(x['id']) == _album, orElse: () => {})['name'] ?? ''}';
    _album = id;
    if (_prefix.text.isEmpty || _prefix.text == oldName) _prefix.text = '${a['name']}';
  }

  Future<void> _add(ImageSource src) async {
    final picker = ImagePicker();
    final left = 60 - _photos.length;
    final List<XFile> files;
    if (src == ImageSource.camera) {
      final x = await picker.pickImage(source: src, maxWidth: 2000, imageQuality: 85);
      files = x == null ? [] : [x];
    } else {
      files = await picker.pickMultiImage(maxWidth: 2000, imageQuality: 85, limit: left >= 2 ? left : null);
    }
    for (final f in files.take(left)) {
      _photos.add(_Photo(f, await f.readAsBytes()));
    }
    if (mounted) setState(() {});
  }

  String _group(int i) {
    var k = i;
    while (k > 0 && _photos[k].samePrev) {
      k--;
    }
    return 'g$k';
  }

  int get _carpets => _photos.where((p) => !p.samePrev).length;

  Future<void> _submit() async {
    if (_album == null || _cat == null || _photos.isEmpty) {
      toastErr(context, 'آلبوم، دسته و دست‌کم یک عکس لازم است.');
      return;
    }
    setState(() => _busy = true);
    final meta = [
      for (var i = 0; i < _photos.length; i++)
        {
          'design': (_photos[i].samePrev ? _photos[int.parse(_group(i).substring(1))] : _photos[i]).design.text.trim(),
          'color': (_photos[i].samePrev ? _photos[int.parse(_group(i).substring(1))] : _photos[i]).color,
          'group': _group(i),
        }
    ];
    final fields = <String, String>{
      'album': '$_album',
      'category': '$_cat',
      'prefix': _prefix.text.trim(),
      'meta': jsonEncode(meta),
      for (final e in _specs.entries)
        if (e.value != null) 'spec_${e.key}': '${e.value}',
    };
    final files = [
      for (var i = 0; i < _photos.length; i++) ('photos', _photos[i].bytes.toList(), 'photo-${i + 1}.${_ext(_photos[i].file.name)}'),
    ];
    final r = await run(context, () async => await Api.i.postFiles('/seller/quick/', fields, files) as Json);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      final n = (r['created'] as List?)?.length ?? 0;
      await showDialog<void>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text('${faDigits(n)} کالا ساخته شد'),
          content: const Text('کالاها برای بررسی ایران کارپت فرستاده شدند و پس از تأیید در ویترین شما دیده می‌شوند. قیمتشان از آلبوم می‌آید.'),
          actions: [FilledButton(onPressed: () => Navigator.pop(c), child: const Text('خوب'))],
        ),
      );
      if (mounted) Navigator.pop(context, true);
    }
  }

  static String _ext(String name) {
    final i = name.lastIndexOf('.');
    final e = i < 0 ? 'jpg' : name.substring(i + 1).toLowerCase();
    return const ['jpg', 'jpeg', 'png', 'webp'].contains(e) ? e : 'jpg';
  }

  @override
  Widget build(BuildContext context) {
    final o = _opt;
    return Scaffold(
      appBar: AppBar(title: const Text('افزودن با عکس')),
      body: o == null
          ? (_error != null ? StatusView(message: _error!, onRetry: _load) : const Center(child: CircularProgressIndicator()))
          : _form(o),
      bottomNavigationBar: o == null
          ? null
          : SafeArea(
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
                child: FilledButton(
                  onPressed: _busy || _photos.isEmpty ? null : _submit,
                  child: _busy
                      ? const Row(mainAxisSize: MainAxisSize.min, children: [
                          SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)),
                          SizedBox(width: 10),
                          Text('در حال فرستادن عکس‌ها…'),
                        ])
                      : Text(_photos.isEmpty ? 'عکس‌ها را انتخاب کنید' : 'ساختن ${faDigits(_carpets)} کالا'),
                ),
              ),
            ),
    );
  }

  Widget _form(Json o) {
    final albums = (o['albums'] as List).cast<Map>();
    final cats = (o['categories'] as List).cast<Map>();
    final colors = (o['colors'] as List? ?? []).cast<String>();
    final designs = (o['designs'] as List? ?? []).cast<String>();
    final attrs = (o['attributes'] as List? ?? []).cast<Map>();
    if (albums.isEmpty) {
      return const StatusView(
          icon: Icons.price_change_outlined,
          message: 'اول از بخش «آلبوم‌ها» یک آلبوم قیمت بسازید؛ کالاهایی که با عکس اضافه می‌کنید قیمتشان را از آلبوم می‌گیرند.');
    }
    return ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
      DropdownButtonFormField<int>(
        initialValue: _album,
        decoration: const InputDecoration(labelText: 'آلبوم قیمت'),
        items: [for (final a in albums) DropdownMenuItem(value: asInt(a['id']), child: Text('${a['name']}'))],
        onChanged: (v) => setState(() => _pickAlbum(v!, albums.firstWhere((a) => asInt(a['id']) == v))),
      ),
      const SizedBox(height: 12),
      DropdownButtonFormField<int>(
        initialValue: _cat,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'دسته'),
        items: [
          for (final c in cats)
            DropdownMenuItem(value: asInt(c['id']), child: Text(c['child'] == true ? '  ${c['name']}' : '${c['name']}')),
        ],
        onChanged: (v) => setState(() => _cat = v),
      ),
      const SizedBox(height: 12),
      TextField(
          controller: _prefix,
          decoration: const InputDecoration(labelText: 'آغاز نام کالاها', helperText: 'مثل «فرش ۷۰۰ شانه»؛ نقشه و رنگ پس از آن می‌آید.')),
      if (attrs.isNotEmpty)
        ExpansionTile(
          tilePadding: EdgeInsets.zero,
          title: const Text('مشخصات مشترک همهٔ این فرش‌ها', style: TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
          subtitle: const Text('اختیاری', style: TextStyle(fontSize: 12)),
          children: [
            for (final a in attrs)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: DropdownButtonFormField<int?>(
                  initialValue: _specs[asInt(a['id'])],
                  isExpanded: true,
                  decoration: InputDecoration(labelText: '${a['name']}', isDense: true),
                  items: [
                    const DropdownMenuItem<int?>(value: null, child: Text('—')),
                    for (final t in (a['terms'] as List).cast<Map>()) DropdownMenuItem<int?>(value: asInt(t['id']), child: Text('${t['name']}')),
                  ],
                  onChanged: (v) => setState(() => _specs[asInt(a['id'])] = v),
                ),
              ),
          ],
        ),
      const SizedBox(height: 16),
      Row(children: [
        Expanded(
          child: OutlinedButton.icon(
              onPressed: _busy || _photos.length >= 60 ? null : () => _add(ImageSource.gallery),
              icon: const Icon(Icons.photo_library_outlined),
              label: const Text('از گالری')),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: OutlinedButton.icon(
              onPressed: _busy || _photos.length >= 60 ? null : () => _add(ImageSource.camera),
              icon: const Icon(Icons.photo_camera_outlined),
              label: const Text('دوربین')),
        ),
      ]),
      const SizedBox(height: 6),
      const Text('هر عکس یک فرش است؛ اگر چند عکس از یک فرش دارید، روی عکس دوم «همان فرش قبلی» را روشن کنید.',
          style: TextStyle(color: C.muted, fontSize: 12.5)),
      const SizedBox(height: 12),
      for (var i = 0; i < _photos.length; i++) _photoCard(i, colors, designs),
    ]);
  }

  Widget _photoCard(int i, List<String> colors, List<String> designs) {
    final p = _photos[i];
    return Padding(
      key: ObjectKey(p),
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        padding: const EdgeInsets.all(10),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.memory(p.bytes, width: 78, height: 104, fit: BoxFit.cover)),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              if (i > 0)
                SwitchListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: const Text('همان فرش قبلی', style: TextStyle(fontSize: 13)),
                  value: p.samePrev,
                  onChanged: (v) => setState(() => p.samePrev = v),
                ),
              if (!p.samePrev) ...[
                Autocomplete<String>(
                  initialValue: TextEditingValue(text: p.design.text),
                  optionsBuilder: (v) => v.text.trim().isEmpty ? const [] : designs.where((d) => d.contains(v.text.trim())).take(8),
                  onSelected: (v) => p.design.text = v,
                  fieldViewBuilder: (c, ctrl, focus, submit) => TextField(
                    controller: ctrl,
                    focusNode: focus,
                    onChanged: (v) => p.design.text = v,
                    decoration: const InputDecoration(labelText: 'نقشه', hintText: 'مثل افشان', isDense: true),
                  ),
                ),
                const SizedBox(height: 8),
                DropdownButtonFormField<String>(
                  initialValue: p.color.isEmpty ? null : p.color,
                  isExpanded: true,
                  decoration: const InputDecoration(labelText: 'رنگ زمینه', isDense: true),
                  items: [
                    const DropdownMenuItem(value: '', child: Text('—')),
                    for (final c in colors) DropdownMenuItem(value: c, child: Text(c)),
                  ],
                  onChanged: (v) => setState(() => p.color = v ?? ''),
                ),
              ] else
                const Text('به عکس‌های فرش قبلی اضافه می‌شود.', style: TextStyle(color: C.muted, fontSize: 12.5)),
            ]),
          ),
          IconButton(
              tooltip: 'برداشتن',
              icon: const Icon(Icons.close_rounded, color: C.muted),
              onPressed: _busy
                  ? null
                  : () => setState(() {
                        _photos.removeAt(i);
                        if (_photos.isNotEmpty) _photos.first.samePrev = false;
                      })),
        ]),
      ),
    );
  }
}
