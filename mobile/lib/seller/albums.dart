import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

/// آلبوم قیمت: یک قیمت پایه برای چند کالای هم‌جنس؛ با عوض شدن آن قیمت همهٔ کالاهای آلبوم یکجا عوض می‌شود.
class SellerAlbums extends StatefulWidget {
  const SellerAlbums({super.key});
  @override
  State<SellerAlbums> createState() => _SellerAlbumsState();
}

class _SellerAlbumsState extends State<SellerAlbums> {
  Future<Json>? _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = Api.i.get('/seller/albums/').then((v) => v as Json));

  Future<void> _open(int id) async {
    await Navigator.push(context, MaterialPageRoute(builder: (_) => AlbumEditor(id: id)));
    _load();
  }

  Future<void> _create(List sizes) async {
    final id = await showModalBottomSheet<int>(
        context: context, isScrollControlled: true, showDragHandle: true, builder: (_) => _NewAlbum(sizes: sizes));
    if (id != null) _open(id);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('آلبوم‌های قیمت'), actions: [GuideButton('albums', onChanged: () => setState(() {}))]),
        body: RefreshIndicator(
          onRefresh: () async {
            _load();
            await _future;
          },
          child: Loader<Json>(
            future: _future,
            onRetry: _load,
            builder: (d) {
              final items = ((d['items'] as List?) ?? []).cast<Map>();
              final sizes = (d['sizes'] as List?) ?? [];
              return Stack(children: [
                if (items.isEmpty)
                  const Empty('آلبوم قیمت ندارید.\nیک آلبوم بسازید (مثل «۷۰۰ شانه پلی‌استر»)، قیمت سایز پایه را بدهید و همهٔ فرش‌های آن جنس را در آن بگذارید.',
                      icon: Icons.price_change_outlined)
                else
                  ListView.separated(
                    padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                    itemCount: items.length + 1,
                    separatorBuilder: (_, i) => SizedBox(height: i == 0 ? 0 : 10),
                    itemBuilder: (_, i) {
                      if (i == 0) return const GuideCard('albums');
                      final a = items[i - 1];
                      return Panel(
                        onTap: () => _open(asInt(a['id'])),
                        child: Row(children: [
                          Expanded(
                            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Text('${a['name']}', style: const TextStyle(fontWeight: FontWeight.w900)),
                              const SizedBox(height: 4),
                              Text('${faDigits(a['base_size'] ?? '')}: ${amount(asInt(a['base_price']))}',
                                  style: const TextStyle(color: C.ink2, fontSize: 13)),
                              Text('${faDigits(asInt(a['products']))} کالا · به‌روزرسانی ${jdate(a['updated'] as String?)}',
                                  style: const TextStyle(color: C.muted, fontSize: 12.5)),
                            ]),
                          ),
                          const Icon(Icons.chevron_left_rounded, color: C.muted),
                        ]),
                      );
                    },
                  ),
                PositionedDirectional(
                  start: 16,
                  bottom: 16,
                  child: FloatingActionButton.extended(
                    heroTag: 'album-new',
                    onPressed: () => _create(sizes),
                    icon: const Icon(Icons.add_rounded),
                    label: const Text('آلبوم تازه'),
                  ),
                ),
              ]);
            },
          ),
        ),
      );
}

class _NewAlbum extends StatefulWidget {
  const _NewAlbum({required this.sizes});
  final List sizes;
  @override
  State<_NewAlbum> createState() => _NewAlbumState();
}

class _NewAlbumState extends State<_NewAlbum> {
  final _name = TextEditingController(), _price = TextEditingController();
  int? _base;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    // پیش‌فرض: ۱۲ متری، رایج‌ترین سایز پایه
    final twelve = widget.sizes.cast<Map>().where((z) => '${z['label']}'.contains('12') || '${z['label']}'.contains('۱۲'));
    if (twelve.isNotEmpty) _base = asInt(twelve.first['id']);
  }

  Future<void> _save() async {
    setState(() => _busy = true);
    final r = await run(
        context,
        () async => await Api.i.post('/seller/albums/', {'name': _name.text.trim(), 'base_size': _base, 'base_price': moneyValue(_price)})
            as Json);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) Navigator.pop(context, asInt(r['id']));
  }

  @override
  Widget build(BuildContext context) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(context).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Text('آلبوم تازه', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          const SizedBox(height: 14),
          TextField(controller: _name, decoration: const InputDecoration(labelText: 'نام آلبوم', hintText: 'مثل «۷۰۰ شانه پلی‌استر»')),
          const SizedBox(height: 12),
          DropdownButtonFormField<int>(
            initialValue: _base,
            decoration: const InputDecoration(labelText: 'سایز پایه'),
            items: [
              for (final z in widget.sizes.cast<Map>()) DropdownMenuItem(value: asInt(z['id']), child: Text(faDigits(z['label'] ?? ''))),
            ],
            onChanged: (v) => setState(() => _base = v),
          ),
          const SizedBox(height: 12),
          MoneyField(controller: _price, label: 'قیمت سایز پایه'),
          const SizedBox(height: 6),
          const Text('قیمت سایزهای دیگر خودکار از متراژ حساب می‌شود؛ بعداً می‌توانید برای هر سایز قیمت دلخواه بگذارید.',
              style: TextStyle(color: C.muted, fontSize: 12.5)),
          const SizedBox(height: 16),
          FilledButton(onPressed: _busy ? null : _save, child: const Text('ساختن آلبوم')),
        ]),
      );
}

/// ویرایش آلبوم: قیمت پایه، روشن/خاموش کردن سایزها و قیمت دستی هر سایز
class AlbumEditor extends StatefulWidget {
  const AlbumEditor({super.key, required this.id});
  final int id;
  @override
  State<AlbumEditor> createState() => _AlbumEditorState();
}

class _AlbumEditorState extends State<AlbumEditor> {
  Json? _a;
  String? _error;
  bool _busy = false, _dirty = false;
  final _name = TextEditingController(), _base = TextEditingController();
  final _manual = <int, TextEditingController>{};
  final _on = <int, bool>{};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      _fill(await Api.i.get('/seller/albums/${widget.id}/') as Json);
    } on ApiError catch (e) {
      setState(() => _error = e.message);
    }
  }

  void _fill(Json a) {
    _name.text = '${a['name']}';
    _base.text = moneyText(a['base_price']);
    for (final z in (a['sizes'] as List).cast<Map>()) {
      final id = asInt(z['id']);
      (_manual[id] ??= TextEditingController()).text = moneyText(z['manual']);
      _on[id] = z['on'] == true;
    }
    setState(() {
      _a = a;
      _error = null;
      _dirty = false;
    });
  }

  Future<void> _save() async {
    final sizes = (_a!['sizes'] as List).cast<Map>();
    final body = {
      'name': _name.text.trim(),
      'base_price': moneyValue(_base),
      'sizes': [for (final z in sizes) if (_on[asInt(z['id'])] == true) asInt(z['id'])],
      'prices': {for (final z in sizes) if (z['base'] != true) '${z['id']}': moneyValue(_manual[asInt(z['id'])]!)},
    };
    setState(() => _busy = true);
    final r = await run(context, () async => await Api.i.post('/seller/albums/${widget.id}/', body) as Json);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      _fill(r);
      toast(context, 'ذخیره شد؛ قیمت ${faDigits(asInt(r['products']))} کالا به‌روز شد.');
    }
  }

  Future<bool> _confirmLeave() async {
    if (!_dirty) return true;
    final r = await showDialog<bool>(
      context: context,
      builder: (c) => AlertDialog(
        content: const Text('تغییرات ذخیره نشده. بیرون بروید؟'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('ماندن')),
          TextButton(onPressed: () => Navigator.pop(c, true), child: const Text('بیرون رفتن بدون ذخیره')),
        ],
      ),
    );
    return r == true;
  }

  void _touch([_]) {
    if (!_dirty) setState(() => _dirty = true);
  }

  @override
  Widget build(BuildContext context) {
    final a = _a;
    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (did, _) async {
        if (did) return;
        if (await _confirmLeave() && context.mounted) {
          setState(() => _dirty = false);
          Navigator.pop(context);
        }
      },
      child: Scaffold(
        appBar: AppBar(title: Text(a == null ? 'آلبوم' : '${a['name']}')),
        body: a == null
            ? (_error != null ? StatusView(message: _error!, onRetry: _load) : const Center(child: CircularProgressIndicator()))
            : ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 24), children: [
                TextField(controller: _name, decoration: const InputDecoration(labelText: 'نام آلبوم'), onChanged: _touch),
                const SizedBox(height: 12),
                MoneyField(controller: _base, label: 'قیمت ${faDigits(a['base_size'] ?? '')} (سایز پایه)', onChanged: _touch),
                const SizedBox(height: 6),
                Text('${faDigits(asInt(a['products']))} کالا در این آلبوم است.', style: const TextStyle(color: C.muted, fontSize: 13)),
                const SizedBox(height: 18),
                const Text('سایزها', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
                const Text('سایزی را که نمی‌فروشید خاموش کنید. قیمت را خالی بگذارید تا خودکار از متراژ حساب شود.',
                    style: TextStyle(color: C.muted, fontSize: 12.5)),
                const SizedBox(height: 10),
                for (final z in (a['sizes'] as List).cast<Map>()) _sizeRow(z),
                const SizedBox(height: 8),
                FilledButton(
                  onPressed: _busy ? null : _save,
                  child: _busy
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Text('ذخیره و به‌روزرسانی قیمت کالاها'),
                ),
              ]),
      ),
    );
  }

  Widget _sizeRow(Map z) {
    final id = asInt(z['id']);
    final base = z['base'] == true;
    final on = base || _on[id] == true;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Panel(
        padding: const EdgeInsets.fromLTRB(12, 4, 8, 4),
        child: Row(children: [
          SizedBox(
              width: 92,
              child: Text(faDigits(z['label'] ?? ''), style: TextStyle(fontWeight: FontWeight.w800, color: on ? C.ink : C.muted))),
          Expanded(
            child: base
                ? const Text('همان قیمت پایه', style: TextStyle(color: C.muted, fontSize: 13))
                : on
                    ? MoneyField(
                        controller: _manual[id]!,
                        dense: true,
                        hint: z['auto'] == null ? 'خودکار' : 'خودکار: ${sep(asInt(z['auto']))}',
                        onChanged: _touch)
                    : const Text('فروخته نمی‌شود', style: TextStyle(color: C.muted, fontSize: 13)),
          ),
          Switch(
              value: on,
              onChanged: base
                  ? null
                  : (x) => setState(() {
                        _on[id] = x;
                        _dirty = true;
                      })),
        ]),
      ),
    );
  }
}
