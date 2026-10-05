import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'home.dart' show hexColor;
import 'requests.dart';
import 'state.dart';

/// نتیجهٔ فرش‌یاب: آنچه فهمیدیم (قابل حذف) + فرش‌های مناسب.
class FinderResults extends StatefulWidget {
  const FinderResults({super.key, required this.wish});
  final Wish wish;
  @override
  State<FinderResults> createState() => _FinderResultsState();
}

class _FinderResultsState extends State<FinderResults> {
  late Wish _wish = widget.wish;
  final _items = <Json>[];
  List<Json> _chips = [];
  String _relaxed = '', _unknown = '', _sort = 'best';
  int _page = 0, _pages = 1, _count = 0;
  bool _loading = false;
  String? _err;
  final _scroll = ScrollController();

  @override
  void initState() {
    super.initState();
    _scroll.addListener(() {
      if (_scroll.position.pixels > _scroll.position.maxScrollExtent - 600) _more();
    });
    _reload();
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
    _more();
  }

  Future<void> _more() async {
    if (_loading || _page >= _pages) return;
    setState(() {
      _loading = true;
      _err = null;
    });
    try {
      final r = await Api.i.get('/finder/search/', {..._wish.query(), 'sort': _sort, 'page': _page + 1}) as Json;
      _page = r['page'] as int;
      _pages = r['pages'] as int;
      _count = r['count'] as int;
      _items.addAll((r['results'] as List).cast<Json>());
      if (_page == 1) {
        _chips = (r['understood'] as List).cast<Json>();
        _relaxed = r['relaxed'] as String? ?? '';
        _unknown = r['unknown'] as String? ?? '';
        // جمله به انتخاب‌های صریح تبدیل می‌شود تا هر برچسب جدا قابل حذف باشد
        if (_wish.q.isNotEmpty) _wish.absorb((r['applied'] as Json?) ?? {}, _chips.isEmpty ? _wish.q : '');
      }
    } on ApiError catch (e) {
      _err = e.message;
    }
    if (mounted) setState(() => _loading = false);
  }

  void _remove(Json c) {
    final w = _wish.copy();
    switch (c['type']) {
      case 'need':
        w.needs.remove(c['id']);
      case 'reeds':
        w.reeds.remove(c['id']);
      case 'size':
        w.size = null;
      case 'price':
        w
          ..min = null
          ..max = null;
    }
    setState(() => _wish = w);
    _reload();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('فرش‌های مناسب تو'),
        actions: [
          PopupMenuButton<String>(
            tooltip: 'مرتب‌سازی',
            icon: const Icon(Icons.sort_rounded),
            initialValue: _sort,
            onSelected: (v) {
              setState(() => _sort = v);
              _reload();
            },
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'best', child: Text('پیشنهاد فرش‌یاب')),
              PopupMenuItem(value: 'cheap', child: Text('ارزان‌ترین')),
              PopupMenuItem(value: 'expensive', child: Text('گران‌ترین')),
              PopupMenuItem(value: 'new', child: Text('جدیدترین')),
            ],
          ),
        ],
      ),
      body: _items.isEmpty && _loading
          ? const Loading()
          : _items.isEmpty && _err != null
              ? StatusView(message: _err!, onRetry: _reload)
              : CustomScrollView(controller: _scroll, slivers: [
                  SliverToBoxAdapter(child: _head()),
                  if (_items.isEmpty)
                    SliverFillRemaining(
                      hasScrollBody: false,
                      child: StatusView(
                        icon: Icons.search_off_rounded,
                        message: 'فعلاً فرشی با این ویژگی‌ها نداریم.\nکارشناس ما می‌تواند از بین موجودی کارخانه‌ها برایت پیدا کند.',
                        action: FilledButton(onPressed: _askExpert, child: const Text('از کارشناس بپرس')),
                      ),
                    )
                  else ...[
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
                      sliver: SliverGrid(
                        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2, mainAxisSpacing: 14, crossAxisSpacing: 12, childAspectRatio: .5),
                        delegate: SliverChildBuilderDelegate(
                          (_, i) => ProductCard(_items[i], match: ((_items[i]['why'] as List?) ?? []).join('، ')),
                          childCount: _items.length,
                        ),
                      ),
                    ),
                    SliverToBoxAdapter(
                      child: _page < _pages ? const Padding(padding: EdgeInsets.all(20), child: Loading()) : _expertCard(),
                    ),
                  ],
                ]),
    );
  }

  Widget _head() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (_chips.isNotEmpty) ...[
          const Text('فهمیدم که می‌خواهی:', style: TextStyle(color: C.muted, fontSize: 12.5)),
          const SizedBox(height: 6),
          Wrap(spacing: 6, runSpacing: 6, children: [
            for (final c in _chips)
              InputChip(
                label: Text(faDigits(c['label'])),
                labelStyle: const TextStyle(fontWeight: FontWeight.w800, fontSize: 12.5, color: C.ink),
                avatar: c['swatch'] != null && (c['swatch'] as String).isNotEmpty
                    ? CircleAvatar(backgroundColor: hexColor(c['swatch'] as String))
                    : null,
                backgroundColor: C.soft,
                side: BorderSide.none,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                deleteIcon: const Icon(Icons.close_rounded, size: 16),
                deleteButtonTooltipMessage: 'حذف',
                onDeleted: () => _remove(c),
              ),
          ]),
        ] else if (_unknown.isNotEmpty || _wish.q.isNotEmpty)
          Text('جستجو برای «${_wish.q}»', style: const TextStyle(color: C.muted, fontSize: 13)),
        if (_relaxed.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 10),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(14)),
            child: Row(children: [
              const Icon(Icons.lightbulb_outline_rounded, color: Color(0xFF9A6A00)),
              const SizedBox(width: 8),
              Expanded(child: Text(_relaxed, style: const TextStyle(fontSize: 13, height: 1.7))),
            ]),
          ),
        if (_items.isNotEmpty && _relaxed.isEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Text('${faDigits(sep(_count))} فرش پیدا شد', style: const TextStyle(fontWeight: FontWeight.w900, fontSize: 16)),
          ),
      ]),
    );
  }

  Widget _expertCard() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(color: C.tealTint, borderRadius: BorderRadius.circular(20)),
          child: Row(children: [
            const Icon(Icons.support_agent_rounded, color: C.tealDark, size: 32),
            const SizedBox(width: 12),
            const Expanded(
              child: Text('دقیقاً چیزی که می‌خواهی را پیدا نکردی؟ به کارشناس بگو، از بین موجودی کارخانه‌ها برایت پیدا می‌کند.',
                  style: TextStyle(fontSize: 13, height: 1.7)),
            ),
            TextButton(onPressed: _askExpert, child: const Text('بپرس')),
          ]),
        ),
      );

  Future<void> _askExpert() async {
    final summary = _chips.map((c) => c['label']).join('، ');
    await askExpert(context, wish: _wish, prefill: summary.isEmpty ? _wish.q : 'دنبال فرش $summary هستم. ');
  }
}

/// برگهٔ «از کارشناس بپرس» (بدون عکس)
Future<void> askExpert(BuildContext context, {Wish? wish, String prefill = ''}) async {
  final auth = context.read<Auth>();
  if (!auth.loggedIn) {
    final ok = await Navigator.pushNamed(context, '/login', arguments: 'برای گرفتن پاسخ کارشناس وارد شوید') == true;
    if (!ok || !context.mounted) return;
  }
  final c = TextEditingController(text: faDigits(prefill));
  final sent = await showModalBottomSheet<Json>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    backgroundColor: Colors.white,
    builder: (ctx) => _AskSheet(controller: c, wish: wish),
  );
  if (sent != null && context.mounted) {
    context.read<FinderData>().refreshUnread();
    Navigator.push(context, MaterialPageRoute(builder: (_) => RequestScreen(data: sent)));
  }
}

class _AskSheet extends StatefulWidget {
  const _AskSheet({required this.controller, this.wish});
  final TextEditingController controller;
  final Wish? wish;
  @override
  State<_AskSheet> createState() => _AskSheetState();
}

class _AskSheetState extends State<_AskSheet> {
  bool _busy = false;

  Future<void> _send() async {
    final t = widget.controller.text.trim();
    if (t.length < 5) {
      toast(context, 'چند کلمه بنویس چه فرشی می‌خواهی.');
      return;
    }
    setState(() => _busy = true);
    try {
      final w = widget.wish;
      final r = await Api.i.postMultipart('/finder/requests/', {
        'text': t,
        'wanted': jsonWanted(w),
      }, {}) as Json;
      if (mounted) Navigator.pop(context, r);
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.fromLTRB(20, 0, 20, MediaQuery.viewInsetsOf(context).bottom + 20),
      child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('از کارشناس بپرس', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900)),
        const Text('بنویس چه فرشی می‌خواهی؛ کارشناس ایران کارپت فرش‌های مناسب را برایت می‌فرستد.',
            style: TextStyle(color: C.muted, fontSize: 13, height: 1.8)),
        const SizedBox(height: 12),
        TextField(
          controller: widget.controller,
          minLines: 3,
          maxLines: 6,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'مثلاً: برای پذیرایی ۲۴ متری، دو تکه ۱۲ متری، رنگ روشن، تا ۱۲۰ میلیون'),
        ),
        const SizedBox(height: 14),
        FilledButton(
          onPressed: _busy ? null : _send,
          child: _busy ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white)) : const Text('بفرست'),
        ),
      ]),
    );
  }
}
