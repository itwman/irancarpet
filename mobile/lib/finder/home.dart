import 'dart:async';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../screens/shell.dart' show Shell;
import '../widgets/brand.dart';
import '../widgets/common.dart';
import 'results.dart';
import 'state.dart';

/// صفحهٔ اول فرش‌یاب: مشتری می‌نویسد یا انتخاب می‌کند چه فرشی می‌خواهد.
class FinderHome extends StatefulWidget {
  const FinderHome({super.key});
  @override
  State<FinderHome> createState() => _FinderHomeState();
}

class _FinderHomeState extends State<FinderHome> {
  final _q = TextEditingController();
  final _wish = Wish();
  Timer? _debounce;
  int? _count;
  bool _counting = false;

  @override
  void dispose() {
    _q.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  void _changed() {
    setState(() {});
    _debounce?.cancel();
    if (_wish.isEmpty) {
      setState(() => _count = null);
      return;
    }
    _debounce = Timer(const Duration(milliseconds: 450), () async {
      setState(() => _counting = true);
      try {
        final r = await Api.i.get('/finder/search/', _wish.query()) as Json;
        if (mounted) setState(() => _count = (r['relaxed'] as String? ?? '').isEmpty ? r['count'] as int : 0);
      } catch (_) {}
      if (mounted) setState(() => _counting = false);
    });
  }

  void _toggleNeed(int id) {
    _wish.needs.contains(id) ? _wish.needs.remove(id) : _wish.needs.add(id);
    _changed();
  }

  void _ask([String? text]) {
    final t = (text ?? _q.text).trim();
    if (t.isEmpty) return;
    FocusScope.of(context).unfocus();
    Navigator.push(context, MaterialPageRoute(builder: (_) => FinderResults(wish: Wish(q: t))));
  }

  void _show() => Navigator.push(context, MaterialPageRoute(builder: (_) => FinderResults(wish: _wish.copy())));

  @override
  Widget build(BuildContext context) {
    final f = context.watch<FinderData>();
    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(children: [
        RefreshIndicator(
          color: C.pink,
          onRefresh: f.load,
          child: CustomScrollView(slivers: [
            SliverToBoxAdapter(child: _hero(f)),
            if (!f.ready)
              SliverFillRemaining(
                hasScrollBody: false,
                child: f.error != null ? StatusView(message: f.error!, onRetry: f.load) : const Padding(padding: EdgeInsets.all(40), child: Loading()),
              )
            else ...[
              for (final g in f.groups) SliverToBoxAdapter(child: _group(g)),
              SliverToBoxAdapter(child: _sizes(f)),
              SliverToBoxAdapter(child: _budgets(f)),
              SliverToBoxAdapter(child: _photoCta()),
              const SliverToBoxAdapter(child: SizedBox(height: 120)),
            ],
          ]),
        ),
        if (!_wish.isEmpty) Positioned(left: 16, right: 16, bottom: 14, child: SafeArea(top: false, child: _bar())),
      ]),
    );
  }

  Widget _hero(FinderData f) {
    return Container(
      decoration: const BoxDecoration(
        color: C.ink,
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(34)),
      ),
      padding: EdgeInsets.fromLTRB(20, MediaQuery.paddingOf(context).top + 14, 20, 22),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.all(3),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(14)),
            child: Image.asset('assets/brand/finder.png', width: 36, height: 36),
          ),
          const SizedBox(width: 10),
          const Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('فرش‌یاب', style: TextStyle(color: Colors.white, fontSize: 19, fontWeight: FontWeight.w900, height: 1.3)),
              Row(children: [
                Text('از ', style: TextStyle(color: Colors.white70, fontSize: 11.5)),
                Wordmark(height: 14, light: true),
              ]),
            ]),
          ),
        ]),
        const SizedBox(height: 22),
        const Text('چه فرشی دلت می‌خواد؟',
            style: TextStyle(color: Colors.white, fontSize: 27, fontWeight: FontWeight.w900, height: 1.35)),
        const SizedBox(height: 4),
        const Text('بنویس یا پایین‌تر انتخاب کن؛ از بین فرش‌های ایران کارپت برایت پیدا می‌کنیم.',
            style: TextStyle(color: Color(0xFFC9CBE6), fontSize: 13.5, height: 1.8)),
        const SizedBox(height: 16),
        Container(
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(22)),
          padding: const EdgeInsetsDirectional.fromSTEB(16, 4, 6, 4),
          child: Row(children: [
            Expanded(
              child: TextField(
                controller: _q,
                minLines: 1,
                maxLines: 3,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _ask(),
                style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w600),
                decoration: const InputDecoration(
                  hintText: 'مثلاً: فرش ضخیم قرمز ۶ متری زیر ۴۰ میلیون',
                  hintStyle: TextStyle(color: C.muted, fontSize: 13.5, fontWeight: FontWeight.w500),
                  border: InputBorder.none,
                  enabledBorder: InputBorder.none,
                  focusedBorder: InputBorder.none,
                  filled: false,
                  contentPadding: EdgeInsets.symmetric(vertical: 14),
                ),
              ),
            ),
            IconButton.filled(
              style: IconButton.styleFrom(backgroundColor: C.pink, fixedSize: const Size(48, 48)),
              tooltip: 'پیدا کن',
              onPressed: _ask,
              icon: const Icon(Icons.arrow_forward_rounded, color: Colors.white),
            ),
          ]),
        ),
        if (f.examples.isNotEmpty) ...[
          const SizedBox(height: 12),
          SizedBox(
            height: 36,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: f.examples.length,
              separatorBuilder: (_, _) => const SizedBox(width: 8),
              itemBuilder: (_, i) => InkWell(
                borderRadius: BorderRadius.circular(18),
                onTap: () => _ask(f.examples[i]),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14),
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: Colors.white.withValues(alpha: .28)),
                  ),
                  child: Text(faDigits(f.examples[i]), style: const TextStyle(color: Colors.white, fontSize: 12.5, fontWeight: FontWeight.w600)),
                ),
              ),
            ),
          ),
        ],
      ]),
    );
  }

  Widget _title(String t, [String? sub]) => Padding(
        padding: const EdgeInsets.fromLTRB(20, 26, 20, 12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(t, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
          if (sub != null) Text(sub, style: const TextStyle(color: C.muted, fontSize: 12.5)),
        ]),
      );

  Widget _group(Json g) {
    final needs = (g['needs'] as List).cast<Json>();
    if (g['key'] == 'color') {
      return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _title(g['title'] as String, 'رنگ زمینهٔ فرش؛ چندتا را می‌شود با هم انتخاب کرد'),
        SizedBox(
          height: 96,
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            scrollDirection: Axis.horizontal,
            itemCount: needs.length,
            separatorBuilder: (_, _) => const SizedBox(width: 6),
            itemBuilder: (_, i) => _Swatch(needs[i], on: _wish.needs.contains(needs[i]['id']), onTap: () => _toggleNeed(needs[i]['id'] as int)),
          ),
        ),
      ]);
    }
    final sub = switch (g['key']) {
      'feel' => 'فرش زیر پایت چه حسی داشته باشد؟',
      'style' => 'حال‌وهوای طرح و نقشه',
      'use' => 'برای کجا می‌خواهی؟',
      _ => null,
    };
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _title(g['title'] as String, sub),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: LayoutBuilder(builder: (_, c) {
          final w = (c.maxWidth - 10) / 2;
          return Wrap(spacing: 10, runSpacing: 10, children: [
            for (final n in needs)
              SizedBox(width: w, child: _NeedTile(n, on: _wish.needs.contains(n['id']), onTap: () => _toggleNeed(n['id'] as int))),
          ]);
        }),
      ),
    ]);
  }

  Widget _chips<T>(List<T> items, bool Function(T) on, String Function(T) label, void Function(T) tap) => SizedBox(
        height: 42,
        child: ListView.separated(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          scrollDirection: Axis.horizontal,
          itemCount: items.length,
          separatorBuilder: (_, _) => const SizedBox(width: 8),
          itemBuilder: (_, i) {
            final sel = on(items[i]);
            return ChoiceChip(
              selected: sel,
              showCheckmark: false,
              label: Text(label(items[i])),
              labelStyle: TextStyle(color: sel ? Colors.white : C.ink, fontWeight: FontWeight.w700, fontSize: 13),
              selectedColor: C.ink,
              backgroundColor: C.soft,
              side: BorderSide.none,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
              onSelected: (_) => tap(items[i]),
            );
          },
        ),
      );

  Widget _sizes(FinderData f) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _title('اندازه', 'قیمت‌ها برای همین سایز نشان داده می‌شود'),
        _chips<Json>(f.sizes, (s) => _wish.size == s['id'], (s) => faDigits(s['label']), (s) {
          _wish.size = _wish.size == s['id'] ? null : s['id'] as int;
          _changed();
        }),
      ]);

  Widget _budgets(FinderData f) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _title('بودجه', 'حداکثر قیمتی که در نظر داری'),
        _chips<int>(f.budgets, (b) => _wish.max == b, (b) => 'تا ${millionLabel(b)}', (b) {
          _wish.max = _wish.max == b ? null : b;
          _changed();
        }),
      ]);

  Widget _photoCta() => Padding(
        padding: const EdgeInsets.fromLTRB(16, 28, 16, 0),
        child: Material(
          color: C.saffronTint,
          borderRadius: BorderRadius.circular(24),
          child: InkWell(
            borderRadius: BorderRadius.circular(24),
            onTap: () => Shell.goTab(context, 1),
            child: Padding(
              padding: const EdgeInsets.all(18),
              child: Row(children: [
                Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(color: C.saffron, borderRadius: BorderRadius.circular(18)),
                  child: const Icon(Icons.photo_camera_rounded, color: C.ink, size: 28),
                ),
                const SizedBox(width: 14),
                const Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text('عکس فرشی را داری که دوستش داری؟', style: TextStyle(fontWeight: FontWeight.w900, fontSize: 15)),
                    SizedBox(height: 2),
                    Text('بفرست تا کارشناس ایران کارپت شبیه‌ترین‌ها را برایت پیدا کند.',
                        style: TextStyle(color: C.ink2, fontSize: 12.5, height: 1.7)),
                  ]),
                ),
                const Icon(Icons.chevron_left_rounded, color: C.ink2),
              ]),
            ),
          ),
        ),
      );

  Widget _bar() {
    final label = _counting && _count == null
        ? 'در حال جستجو…'
        : _count == null
            ? 'نمایش فرش‌ها'
            : _count == 0
                ? 'نزدیک‌ترین فرش‌ها را ببین'
                : 'نمایش ${faDigits(sep(_count!))} فرش';
    return Material(
      elevation: 10,
      shadowColor: C.ink.withValues(alpha: .35),
      borderRadius: BorderRadius.circular(22),
      color: Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(8),
        child: Row(children: [
          TextButton(
            onPressed: () {
              _wish
                ..needs.clear()
                ..size = null
                ..max = null;
              _changed();
            },
            child: const Text('پاک کردن', style: TextStyle(color: C.muted)),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: FilledButton(
              style: FilledButton.styleFrom(minimumSize: const Size(10, 52)),
              onPressed: _show,
              child: AnimatedSwitcher(duration: const Duration(milliseconds: 200), child: Text(label, key: ValueKey(label))),
            ),
          ),
        ]),
      ),
    );
  }
}

class _NeedTile extends StatelessWidget {
  const _NeedTile(this.n, {required this.on, required this.onTap});
  final Json n;
  final bool on;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 180),
      decoration: BoxDecoration(
        color: on ? C.ink : C.soft,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Material(
        type: MaterialType.transparency,
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(n['title'] as String,
                      style: TextStyle(fontWeight: FontWeight.w900, fontSize: 14.5, color: on ? Colors.white : C.ink, height: 1.4)),
                  if ((n['subtitle'] as String? ?? '').isNotEmpty)
                    Text(n['subtitle'] as String,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 11.5, color: on ? const Color(0xFFC9CBE6) : C.muted, height: 1.6)),
                ]),
              ),
              AnimatedOpacity(
                opacity: on ? 1 : 0,
                duration: const Duration(milliseconds: 180),
                child: const Icon(Icons.check_circle_rounded, color: C.saffron, size: 20),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

Color? hexColor(String? h) {
  final s = (h ?? '').replaceAll('#', '');
  if (s.length != 6) return null;
  return Color(int.parse('FF$s', radix: 16));
}

class _Swatch extends StatelessWidget {
  const _Swatch(this.n, {required this.on, required this.onTap});
  final Json n;
  final bool on;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = hexColor(n['swatch'] as String?) ?? C.soft;
    final dark = c.computeLuminance() < .4;
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: onTap,
      child: SizedBox(
        width: 74,
        child: Column(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            width: 54,
            height: 54,
            padding: EdgeInsets.all(on ? 4 : 0),
            decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: on ? C.pink : C.line, width: on ? 3 : 1.4)),
            child: DecoratedBox(
              decoration: BoxDecoration(color: c, shape: BoxShape.circle),
              child: on ? Icon(Icons.check_rounded, color: dark ? Colors.white : C.ink, size: 22) : null,
            ),
          ),
          const SizedBox(height: 6),
          Text(n['title'] as String,
              textAlign: TextAlign.center,
              maxLines: 2,
              style: TextStyle(fontSize: 11, height: 1.35, fontWeight: on ? FontWeight.w900 : FontWeight.w600)),
        ]),
      ),
    );
  }
}
