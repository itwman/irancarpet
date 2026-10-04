import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import '../widgets/knots.dart';

// ------------------------------------------------------------------ دسته‌ها
class CategoriesTab extends StatefulWidget {
  const CategoriesTab({super.key});
  @override
  State<CategoriesTab> createState() => _CategoriesTabState();
}

class _CategoriesTabState extends State<CategoriesTab> with AutomaticKeepAliveClientMixin {
  List<Json>? _cats;
  String? _err;
  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final r = (await Api.i.get('/categories/') as List).cast<Json>();
      if (mounted) setState(() => _cats = r);
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  void _open(Json c) => Navigator.pushNamed(context, '/products', arguments: {'title': c['name'], 'query': {'category': c['id']}});

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return Scaffold(
      appBar: AppBar(title: const Text('دسته‌ها'), actions: [
        IconButton(tooltip: 'جستجو', onPressed: () => Navigator.pushNamed(context, '/search'), icon: const Icon(Icons.search_rounded)),
      ]),
      body: _cats == null
          ? (_err != null ? StatusView(message: _err!, onRetry: () {
                setState(() => _err = null);
                _load();
              }) : const Loading())
          : ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 24), children: [
              _allTile(),
              for (final (i, c) in _cats!.indexed) _CatTile(c, index: i, onOpen: _open),
            ]),
    );
  }

  Widget _allTile() => Card(
        elevation: 0,
        color: C.ink,
        margin: const EdgeInsets.only(bottom: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
        child: ListTile(
          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          leading: const KnotLogo(size: 36),
          title: const Text('همهٔ فرش‌ها', style: TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
          trailing: const Icon(Icons.chevron_left, color: Colors.white),
          onTap: () => Navigator.pushNamed(context, '/products', arguments: {'title': 'همهٔ فرش‌ها', 'query': <String, dynamic>{}}),
        ),
      );
}

class _CatTile extends StatelessWidget {
  const _CatTile(this.c, {required this.index, required this.onOpen});
  final Json c;
  final int index;
  final void Function(Json) onOpen;

  @override
  Widget build(BuildContext context) {
    final kids = (c['children'] as List).cast<Json>();
    final tint = [C.pinkTint, C.tealTint, C.saffronTint, const Color(0xFFEFF8EC)][index % 4];
    final leading = Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(color: tint, borderRadius: BorderRadius.circular(14)),
      clipBehavior: Clip.antiAlias,
      child: (c['image'] as String).isEmpty
          ? Center(child: KnotIcon(c1: [C.pink, C.teal, C.saffron, C.pistachio][index % 4], c2: C.ink.withValues(alpha: .15), size: 22))
          : NetImage(c['image'] as String),
    );
    final subtitle = Text('${sep(c['count'] as int)} فرش', style: const TextStyle(color: C.muted, fontSize: 12.5));
    final shape = RoundedRectangleBorder(borderRadius: BorderRadius.circular(18));
    if (kids.isEmpty) {
      return Card(
        elevation: 0,
        color: C.soft,
        margin: const EdgeInsets.only(bottom: 10),
        shape: shape,
        child: ListTile(
            leading: leading,
            title: Text(c['name'] as String, style: const TextStyle(fontWeight: FontWeight.w700)),
            subtitle: subtitle,
            trailing: const Icon(Icons.chevron_left),
            onTap: () => onOpen(c)),
      );
    }
    return Card(
      elevation: 0,
      color: C.soft,
      margin: const EdgeInsets.only(bottom: 10),
      shape: shape,
      clipBehavior: Clip.antiAlias,
      child: ExpansionTile(
        shape: shape,
        leading: leading,
        title: Text(c['name'] as String, style: const TextStyle(fontWeight: FontWeight.w700)),
        subtitle: subtitle,
        children: [
          ListTile(title: Text('همهٔ ${c['name']}', style: const TextStyle(color: C.pinkDark, fontWeight: FontWeight.w700)), onTap: () => onOpen(c)),
          for (final k in kids)
            ListTile(
                title: Text(k['name'] as String),
                trailing: Text(sep(k['count'] as int), style: const TextStyle(color: C.muted)),
                onTap: () => onOpen(k)),
        ],
      ),
    );
  }
}

// ------------------------------------------------------------------ فهرست محصولات
class ProductListScreen extends StatefulWidget {
  const ProductListScreen({super.key, required this.title, this.query = const {}, this.embedded = false});
  final String title;
  final Map<String, dynamic> query;
  final bool embedded;
  @override
  State<ProductListScreen> createState() => _ProductListScreenState();
}

class _ProductListScreenState extends State<ProductListScreen> {
  late Map<String, dynamic> _q = {'sort': 'new', ...widget.query};
  final List<Json> _items = [];
  int _page = 0, _pages = 1, _count = 0;
  bool _loading = false;
  String? _err;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _more();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 800) _more();
    });
  }

  @override
  void didUpdateWidget(covariant ProductListScreen old) {
    super.didUpdateWidget(old);
    if (old.query.toString() != widget.query.toString()) {
      _q = {'sort': _q['sort'], ...widget.query};
      _reload();
    }
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _reload() {
    _items.clear();
    _page = 0;
    _pages = 1;
    _err = null;
    setState(() {});
    _more();
  }

  Future<void> _more() async {
    if (_loading || _page >= _pages) return;
    setState(() => _loading = true);
    try {
      final r = await Api.i.get('/products/', {..._q, 'page': _page + 1}) as Json;
      _page = r['page'] as int;
      _pages = r['pages'] as int;
      _count = r['count'] as int;
      _items.addAll((r['results'] as List).cast<Json>());
    } on ApiError catch (e) {
      _err = e.message;
    }
    if (mounted) setState(() => _loading = false);
  }

  int get _activeFilters => ['reeds', 'color', 'size', 'brand', 'min', 'max', 'instock'].where((k) => _q[k] != null).length;

  Future<void> _filters() async {
    final r = await showModalBottomSheet<Map<String, dynamic>>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: Colors.white,
      builder: (_) => _FilterSheet(query: _q),
    );
    if (r != null) {
      _q = r;
      _reload();
    }
  }

  Future<void> _sort() async {
    final sorts = context.read<AppConfig>().sorts;
    final r = await showModalBottomSheet<String>(
      context: context,
      showDragHandle: true,
      backgroundColor: Colors.white,
      builder: (c) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          for (final s in sorts.isEmpty ? [{'key': 'new', 'label': 'جدیدترین'}] : sorts)
            ListTile(
              title: Text(s['label'] as String),
              trailing: _q['sort'] == s['key'] ? const Icon(Icons.check_rounded, color: C.pink) : null,
              onTap: () => Navigator.pop(c, s['key'] as String),
            ),
        ]),
      ),
    );
    if (r != null) {
      _q['sort'] = r;
      _reload();
    }
  }

  @override
  Widget build(BuildContext context) {
    final body = Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
        child: Row(children: [
          Expanded(child: Text(_page == 0 ? '' : '${sep(_count)} فرش', style: const TextStyle(color: C.muted))),
          OutlinedButton.icon(
            style: OutlinedButton.styleFrom(minimumSize: const Size(10, 40)),
            onPressed: _sort,
            icon: const Icon(Icons.sort_rounded, size: 18),
            label: const Text('مرتب‌سازی'),
          ),
          const SizedBox(width: 8),
          Badge(
            isLabelVisible: _activeFilters > 0,
            label: Text('$_activeFilters'),
            backgroundColor: C.pink,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: C.ink, minimumSize: const Size(10, 40)),
              onPressed: _filters,
              icon: const Icon(Icons.tune_rounded, size: 18),
              label: const Text('فیلتر'),
            ),
          ),
        ]),
      ),
      Expanded(
        child: _items.isEmpty
            ? (_loading
                ? const Loading()
                : _err != null
                    ? StatusView(message: _err!, onRetry: _reload)
                    : const StatusView(message: 'فرشی با این مشخصات پیدا نشد.', icon: Icons.search_off_rounded))
            : RefreshIndicator(
                color: C.pink,
                onRefresh: () async => _reload(),
                child: GridView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                  gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 2, mainAxisSpacing: 14, crossAxisSpacing: 12, childAspectRatio: .54),
                  itemCount: _items.length + (_page < _pages ? 1 : 0),
                  itemBuilder: (_, i) => i < _items.length ? ProductCard(_items[i]) : const Center(child: Loading()),
                ),
              ),
      ),
    ]);
    if (widget.embedded) return body;
    return Scaffold(appBar: AppBar(title: Text(widget.title)), body: body);
  }
}

class _FilterSheet extends StatefulWidget {
  const _FilterSheet({required this.query});
  final Map<String, dynamic> query;
  @override
  State<_FilterSheet> createState() => _FilterSheetState();
}

class _FilterSheetState extends State<_FilterSheet> {
  late final Map<String, dynamic> q = Map.of(widget.query);
  Json? _f;
  final _min = TextEditingController(), _max = TextEditingController();

  @override
  void initState() {
    super.initState();
    _min.text = q['min'] == null ? '' : '${q['min']}';
    _max.text = q['max'] == null ? '' : '${q['max']}';
    final base = Map.of(widget.query)..removeWhere((k, _) => ['reeds', 'color', 'size', 'brand', 'min', 'max', 'instock', 'sort'].contains(k));
    Api.i.get('/products/filters/', base).then((r) {
      if (mounted) setState(() => _f = r as Json);
    }).catchError((_) {});
  }

  Widget _group(String title, String key, List items) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      FieldLabel(title),
      Wrap(spacing: 8, runSpacing: 8, children: [
        for (final it in items.cast<Json>())
          FilterChip(
            showCheckmark: false,
            selected: '${q[key]}' == '${it['id']}',
            label: Text('${it['name']}'),
            onSelected: (on) => setState(() => on ? q[key] = it['id'] : q.remove(key)),
          ),
      ]),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final f = _f;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: .8,
      maxChildSize: .94,
      builder: (_, sc) => Column(children: [
        Expanded(
          child: f == null
              ? const Loading()
              : ListView(controller: sc, padding: const EdgeInsets.fromLTRB(20, 0, 20, 20), children: [
                  const Text('فیلتر فرش‌ها', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    activeThumbColor: C.pink,
                    title: const Text('فقط فرش‌های موجود'),
                    value: q['instock'] != null,
                    onChanged: (v) => setState(() => v ? q['instock'] = 1 : q.remove('instock')),
                  ),
                  _group('شانه', 'reeds', f['reeds'] as List),
                  _group('سایز', 'size', f['sizes'] as List),
                  _group('رنگ زمینه', 'color', f['colors'] as List),
                  _group('برند', 'brand', f['brands'] as List),
                  const FieldLabel('قیمت (تومان)'),
                  Row(children: [
                    Expanded(child: TextField(controller: _min, keyboardType: TextInputType.number, decoration: const InputDecoration(hintText: 'از'))),
                    const SizedBox(width: 10),
                    Expanded(child: TextField(controller: _max, keyboardType: TextInputType.number, decoration: const InputDecoration(hintText: 'تا'))),
                  ]),
                ]),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 12),
            child: Row(children: [
              Expanded(
                child: OutlinedButton(
                    onPressed: () => Navigator.pop(context, Map<String, dynamic>.of(widget.query)
                      ..removeWhere((k, _) => ['reeds', 'color', 'size', 'brand', 'min', 'max', 'instock'].contains(k))),
                    child: const Text('حذف فیلترها')),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 2,
                child: FilledButton(
                  onPressed: () {
                    final mn = int.tryParse(latin(_min.text).replaceAll(RegExp(r'\D'), ''));
                    final mx = int.tryParse(latin(_max.text).replaceAll(RegExp(r'\D'), ''));
                    mn == null ? q.remove('min') : q['min'] = mn;
                    mx == null ? q.remove('max') : q['max'] = mx;
                    Navigator.pop(context, q);
                  },
                  child: const Text('نمایش فرش‌ها'),
                ),
              ),
            ]),
          ),
        ),
      ]),
    );
  }
}

// ------------------------------------------------------------------ جستجو
class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key});
  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _c = TextEditingController();
  Timer? _t;
  String _q = '';
  List<String> _recent = [];

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((p) => setState(() => _recent = p.getStringList('recent_q') ?? []));
  }

  @override
  void dispose() {
    _t?.cancel();
    _c.dispose();
    super.dispose();
  }

  void _changed(String v) {
    _t?.cancel();
    _t = Timer(const Duration(milliseconds: 450), () => setState(() => _q = v.trim()));
  }

  Future<void> _submit(String v) async {
    v = v.trim();
    if (v.isEmpty) return;
    setState(() => _q = v);
    final p = await SharedPreferences.getInstance();
    _recent = [v, ..._recent.where((x) => x != v)].take(8).toList();
    await p.setStringList('recent_q', _recent);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: TextField(
          controller: _c,
          autofocus: true,
          textInputAction: TextInputAction.search,
          onChanged: _changed,
          onSubmitted: _submit,
          decoration: InputDecoration(
            hintText: 'نقشه، رنگ یا کد فرش…',
            contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            suffixIcon: _c.text.isEmpty
                ? null
                : IconButton(onPressed: () {
                      _c.clear();
                      setState(() => _q = '');
                    }, icon: const Icon(Icons.close_rounded)),
          ),
        ),
        actions: const [SizedBox(width: 12)],
      ),
      body: _q.length < 2
          ? ListView(padding: const EdgeInsets.all(16), children: [
              if (_recent.isNotEmpty) ...[
                const Text('جستجوهای اخیر', style: TextStyle(fontWeight: FontWeight.w800)),
                const SizedBox(height: 10),
                Wrap(spacing: 8, runSpacing: 8, children: [
                  for (final r in _recent)
                    ActionChip(label: Text(r), onPressed: () {
                      _c.text = r;
                      _submit(r);
                    }),
                ]),
              ] else
                const StatusView(message: 'نام نقشه (مثل «افشان»)، رنگ (مثل «سرمه‌ای») یا کد فرش را بنویسید.', icon: Icons.search_rounded),
            ])
          : ProductListScreen(key: ValueKey(_q), title: '', query: {'q': _q}, embedded: true),
    );
  }
}
