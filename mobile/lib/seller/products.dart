import 'dart:async';

import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'quick.dart';
import 'ui.dart';

const _filters = [('', 'همه'), ('out', 'ناموجود'), ('pending', 'در بررسی'), ('rejected', 'ردشده')];

/// کالاها: جست‌وجو، موجود/ناموجود با یک لمس، قیمت و موجودی هر سایز
class SellerProducts extends StatefulWidget {
  const SellerProducts({super.key});
  @override
  State<SellerProducts> createState() => _SellerProductsState();
}

class _SellerProductsState extends State<SellerProducts> {
  String _f = '', _q = '';
  final _items = <Json>[];
  int _page = 0, _pages = 1, _count = 0;
  bool _loading = false;
  String? _error;
  Timer? _debounce;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _reload();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 400) _more();
    });
  }

  @override
  void dispose() {
    _debounce?.cancel();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    _items.clear();
    _page = 0;
    _pages = 1;
    await _more();
  }

  Future<void> _more() async {
    if (_loading || _page >= _pages) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final d = await Api.i.get('/seller/products/', {'f': _f, 'q': _q, 'page': _page + 1}) as Json;
      _items.addAll(((d['items'] as List?) ?? []).cast<Map>().map((e) => e.cast<String, dynamic>()));
      _page = asInt(d['page']);
      _pages = asInt(d['pages']);
      _count = asInt(d['count']);
    } on ApiError catch (e) {
      _error = e.message;
    }
    if (mounted) setState(() => _loading = false);
  }

  void _replace(Json p) {
    final i = _items.indexWhere((x) => x['id'] == p['id']);
    if (i >= 0) setState(() => _items[i] = p);
  }

  Future<void> _toggle(Json p, bool on) async {
    final old = p['in_stock'];
    setState(() => p['in_stock'] = on);
    final r = await run(context, () async => await Api.i.post('/seller/products/${p['id']}/stock/', {'on': on}) as Json);
    if (r != null) {
      _replace(r);
    } else if (mounted) {
      setState(() => p['in_stock'] = old);
    }
  }

  Future<void> _edit(Json p) async {
    final r = await showModalBottomSheet<Json>(
        context: context, isScrollControlled: true, showDragHandle: true, useSafeArea: true, builder: (_) => PriceSheet(product: p));
    if (r != null) _replace(r);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(
          title: Text(_count > 0 ? 'کالاها (${faDigits(_count)})' : 'کالاها'),
          actions: [GuideButton('products', onChanged: () => setState(() {}))],
          bottom: PreferredSize(
            preferredSize: const Size.fromHeight(108),
            child: Column(children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 4),
                child: TextField(
                  textInputAction: TextInputAction.search,
                  decoration: const InputDecoration(prefixIcon: Icon(Icons.search_rounded), hintText: 'نام کالا یا کد', isDense: true),
                  onChanged: (v) {
                    _debounce?.cancel();
                    _debounce = Timer(const Duration(milliseconds: 450), () {
                      _q = v.trim();
                      _reload();
                    });
                  },
                ),
              ),
              SizedBox(
                height: 52,
                child: ListView(scrollDirection: Axis.horizontal, padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8), children: [
                  for (final (k, label) in _filters)
                    Padding(
                      padding: const EdgeInsetsDirectional.only(end: 8),
                      child: ChoiceChip(
                          label: Text(label),
                          selected: _f == k,
                          onSelected: (_) {
                            _f = k;
                            _reload();
                          }),
                    ),
                ]),
              ),
            ]),
          ),
        ),
        floatingActionButton: FloatingActionButton.extended(
          onPressed: () async {
            final done = await Navigator.push<bool>(context, MaterialPageRoute(builder: (_) => const SellerQuick()));
            if (done == true) _reload();
          },
          icon: const Icon(Icons.add_a_photo_outlined),
          label: const Text('افزودن با عکس'),
        ),
        body: RefreshIndicator(
          onRefresh: _reload,
          child: _items.isEmpty && !_loading
              ? (_error != null
                  ? Empty(_error!, icon: Icons.wifi_off_rounded)
                  : Empty(_q.isEmpty && _f.isEmpty ? 'هنوز کالایی ندارید. با «افزودن با عکس» چند فرش را یکجا اضافه کنید.' : 'کالایی پیدا نشد.',
                      icon: Icons.inventory_2_outlined))
              : ListView.separated(
                  controller: _scroll,
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 96),
                  itemCount: _items.length + 1 + (_loading ? 1 : 0),
                  separatorBuilder: (_, i) => SizedBox(height: i == 0 ? 0 : 10),
                  itemBuilder: (_, j) {
                    if (j == 0) return const GuideCard('products');
                    final i = j - 1;
                    if (i >= _items.length) return const Padding(padding: EdgeInsets.all(16), child: Center(child: CircularProgressIndicator()));
                    return _ProductTile(p: _items[i], onToggle: (on) => _toggle(_items[i], on), onTap: () => _edit(_items[i]));
                  },
                ),
        ),
      );
}

class _ProductTile extends StatelessWidget {
  const _ProductTile({required this.p, required this.onToggle, required this.onTap});
  final Json p;
  final ValueChanged<bool> onToggle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final review = '${p['review'] ?? ''}';
    final album = p['album'] as Map?;
    final on = p['in_stock'] == true;
    return Panel(
      padding: const EdgeInsets.all(10),
      onTap: onTap,
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        SizedBox(width: 74, height: 96, child: NetImage('${p['image'] ?? ''}', radius: 10)),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('${p['title']}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14)),
            const SizedBox(height: 4),
            Text(asInt(p['min_price']) > 0 ? 'از ${toman(asInt(p['min_price']))}' : 'بدون قیمت',
                style: const TextStyle(color: C.ink2, fontSize: 13)),
            const SizedBox(height: 6),
            Wrap(spacing: 6, runSpacing: 4, children: [
              if (review == 'pending') const Pill('در انتظار بررسی', color: Color(0xFFB45309)),
              if (review == 'rejected') const Pill('رد شد', color: Color(0xFFC0392B)),
              if (p['status'] == 'draft') const Pill('پیش‌نویس'),
              if (album != null) Pill('آلبوم ${album['name']}', color: C.tealDark),
            ]),
            if (review == 'rejected' && '${p['review_note'] ?? ''}'.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Text('${p['review_note']}', style: const TextStyle(color: Color(0xFFC0392B), fontSize: 12.5)),
              ),
          ]),
        ),
        Column(children: [
          Switch(value: on, onChanged: onToggle),
          Text(on ? 'موجود' : 'ناموجود', style: TextStyle(fontSize: 11.5, color: on ? C.ink2 : C.muted)),
        ]),
      ]),
    );
  }
}

/// برگهٔ قیمت و موجودی سایزها. کالای آلبوم‌دار قیمتش را از آلبوم می‌گیرد؛ این‌جا فقط موجودی‌اش عوض می‌شود.
class PriceSheet extends StatefulWidget {
  const PriceSheet({super.key, required this.product});
  final Json product;
  @override
  State<PriceSheet> createState() => _PriceSheetState();
}

class _PriceSheetState extends State<PriceSheet> {
  late final List<Json> _rows;
  final _price = <int, TextEditingController>{}, _sale = <int, TextEditingController>{}, _qty = <int, TextEditingController>{};
  final _avail = <int, bool>{};
  bool _busy = false;

  bool get _album => widget.product['album'] != null;

  @override
  void initState() {
    super.initState();
    _rows = ((widget.product['variations'] as List?) ?? []).cast<Map>().map((e) => e.cast<String, dynamic>()).toList();
    for (final v in _rows) {
      final id = asInt(v['id']);
      _price[id] = TextEditingController(text: moneyText(v['price']));
      _sale[id] = TextEditingController(text: moneyText(v['sale']));
      _qty[id] = TextEditingController(text: v['qty'] == null ? '' : faDigits(asInt(v['qty'])));
      _avail[id] = v['available'] == true;
    }
  }

  @override
  void dispose() {
    for (final c in [..._price.values, ..._sale.values, ..._qty.values]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _save() async {
    final rows = [
      for (final v in _rows)
        {
          'id': v['id'],
          'available': _avail[asInt(v['id'])],
          'qty': latin(_qty[asInt(v['id'])]!.text).trim(),
          if (!_album) 'price': moneyValue(_price[asInt(v['id'])]!),
          if (!_album) 'sale': moneyValue(_sale[asInt(v['id'])]!),
        }
    ];
    setState(() => _busy = true);
    final r = await run(context, () async => await Api.i.post('/seller/products/${widget.product['id']}/prices/', {'variations': rows}) as Json);
    if (!mounted) return;
    setState(() => _busy = false);
    if (r != null) {
      toast(context, 'ذخیره شد.');
      Navigator.pop(context, r);
    }
  }

  @override
  Widget build(BuildContext context) {
    final p = widget.product;
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: DraggableScrollableSheet(
        expand: false,
        initialChildSize: .85,
        maxChildSize: .95,
        builder: (context, sc) => Column(children: [
          Expanded(
            child: ListView(controller: sc, padding: const EdgeInsets.fromLTRB(16, 0, 16, 16), children: [
              Text('${p['title']}', style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
              const SizedBox(height: 4),
              Text(
                  _album
                      ? 'قیمت این کالا از آلبوم «${(p['album'] as Map)['name']}» می‌آید؛ برای تغییر قیمت به بخش آلبوم‌ها بروید. این‌جا موجودی هر سایز را تنظیم کنید.'
                      : 'قیمت و تخفیف به تومان. تعداد را خالی بگذارید یعنی همیشه موجود.',
                  style: const TextStyle(color: C.muted, fontSize: 13)),
              const SizedBox(height: 12),
              if (_rows.isEmpty) const Text('این کالا سایزی ندارد.'),
              for (final v in _rows) _row(v),
            ]),
          ),
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                    onPressed: _busy || _rows.isEmpty ? null : _save,
                    child: _busy ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2)) : const Text('ذخیره')),
              ),
            ),
          ),
        ]),
      ),
    );
  }

  Widget _row(Json v) {
    final id = asInt(v['id']);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Panel(
        padding: const EdgeInsets.fromLTRB(12, 6, 12, 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [
            Expanded(child: Text(faDigits(v['size'] ?? ''), style: const TextStyle(fontWeight: FontWeight.w900))),
            if (_album) Text(toman(asInt(v['final'])), style: const TextStyle(color: C.ink2, fontSize: 13)),
            Switch(value: _avail[id] ?? true, onChanged: (x) => setState(() => _avail[id] = x)),
          ]),
          Row(children: [
            if (!_album) ...[
              Expanded(flex: 3, child: MoneyField(controller: _price[id]!, label: 'قیمت', dense: true)),
              const SizedBox(width: 8),
              Expanded(flex: 3, child: MoneyField(controller: _sale[id]!, label: 'با تخفیف', dense: true)),
              const SizedBox(width: 8),
            ],
            Expanded(
              flex: 2,
              child: TextField(
                controller: _qty[id],
                keyboardType: TextInputType.number,
                textDirection: TextDirection.ltr,
                decoration: const InputDecoration(labelText: 'تعداد', hintText: '∞', isDense: true),
              ),
            ),
          ]),
        ]),
      ),
    );
  }
}
