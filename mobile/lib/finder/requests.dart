import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../core/api.dart';
import '../core/format.dart';
import '../core/theme.dart';
import '../state/app_state.dart';
import '../widgets/common.dart';
import 'home.dart' show hexColor;
import 'state.dart';

/// زبانهٔ «عکس فرش»: مشتری عکس فرشی که دوست دارد را می‌فرستد.
class PhotoTab extends StatefulWidget {
  const PhotoTab({super.key});
  @override
  State<PhotoTab> createState() => _PhotoTabState();
}

class _PhotoTabState extends State<PhotoTab> {
  Uint8List? _img;
  final _text = TextEditingController();
  int? _size, _max;
  bool _busy = false;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource src) async {
    try {
      final x = await ImagePicker().pickImage(source: src, maxWidth: 2000, maxHeight: 2000, imageQuality: 85);
      if (x == null) return;
      final b = await x.readAsBytes();
      setState(() => _img = b);
    } catch (_) {
      if (mounted) toast(context, 'دسترسی به دوربین یا گالری داده نشد.');
    }
  }

  Future<void> _send() async {
    if (_img == null) return;
    if (!context.read<Auth>().loggedIn) {
      final ok = await Navigator.pushNamed(context, '/login', arguments: 'برای گرفتن پاسخ کارشناس وارد شوید') == true;
      if (!ok || !mounted) return;
    }
    setState(() => _busy = true);
    try {
      final r = await Api.i.postMultipart('/finder/requests/', {
        'text': _text.text.trim(),
        'wanted': jsonWanted(Wish(size: _size, max: _max)),
      }, {
        'photo': (_img!.toList(), 'rug.jpg'),
      }) as Json;
      if (!mounted) return;
      setState(() {
        _img = null;
        _text.clear();
        _size = _max = null;
      });
      context.read<FinderData>().refreshUnread();
      Navigator.push(context, MaterialPageRoute(builder: (_) => RequestScreen(data: r)));
    } on ApiError catch (e) {
      if (mounted) toast(context, e.message);
    }
    if (mounted) setState(() => _busy = false);
  }

  @override
  Widget build(BuildContext context) {
    final f = context.watch<FinderData>();
    return Scaffold(
      appBar: AppBar(
        title: const Text('پیدا کردن با عکس'),
        actions: [
          TextButton.icon(
            onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const RequestsScreen())),
            icon: const Icon(Icons.inbox_outlined, size: 20),
            label: const Text('درخواست‌های من'),
          ),
        ],
      ),
      body: ListView(padding: const EdgeInsets.fromLTRB(16, 4, 16, 28), children: [
        if (_img == null) ...[
          const Text('عکس فرشی را که دوستش داری بفرست', style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900, height: 1.5)),
          const SizedBox(height: 4),
          const Text('فرش خانهٔ خودت، فرشی که جایی دیده‌ای یا عکسی از اینترنت. رنگ‌هایش را همین حالا تشخیص می‌دهیم '
              'و کارشناس ایران کارپت شبیه‌ترین فرش‌ها را برایت می‌فرستد.',
              style: TextStyle(color: C.ink2, height: 1.9, fontSize: 13.5)),
          const SizedBox(height: 18),
          const _Steps(),
          const SizedBox(height: 18),
          Row(children: [
            Expanded(
              child: FilledButton.icon(
                style: FilledButton.styleFrom(minimumSize: const Size(10, 56)),
                onPressed: () => _pick(ImageSource.camera),
                icon: const Icon(Icons.photo_camera_rounded),
                label: const Text('عکس بگیر'),
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(minimumSize: const Size(10, 56)),
                onPressed: () => _pick(ImageSource.gallery),
                icon: const Icon(Icons.photo_library_outlined),
                label: const Text('از گالری'),
              ),
            ),
          ]),
          const SizedBox(height: 10),
          const Text('بهتر است کل فرش در عکس باشد و نور کافی داشته باشد.', textAlign: TextAlign.center, style: TextStyle(color: C.muted, fontSize: 12)),
        ] else ...[
          ClipRRect(
            borderRadius: BorderRadius.circular(22),
            child: Stack(children: [
              Image.memory(_img!, height: 300, width: double.infinity, fit: BoxFit.cover),
              Positioned(
                top: 8,
                left: 8,
                child: IconButton.filledTonal(
                  tooltip: 'عکس دیگر',
                  onPressed: () => setState(() => _img = null),
                  icon: const Icon(Icons.close_rounded),
                ),
              ),
            ]),
          ),
          const FieldLabel('توضیح (اختیاری)'),
          TextField(
            controller: _text,
            minLines: 2,
            maxLines: 4,
            decoration: const InputDecoration(hintText: 'مثلاً: همین طرح را با زمینهٔ روشن‌تر می‌خواهم، برای پذیرایی'),
          ),
          if (f.sizes.isNotEmpty) ...[
            const FieldLabel('چه سایزی می‌خواهی؟'),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final s in f.sizes.where((s) => s['type'] == 'rect'))
                ChoiceChip(
                  label: Text(faDigits(s['label'])),
                  selected: _size == s['id'],
                  showCheckmark: false,
                  onSelected: (on) => setState(() => _size = on ? s['id'] as int : null),
                ),
            ]),
          ],
          if (f.budgets.isNotEmpty) ...[
            const FieldLabel('بودجه'),
            Wrap(spacing: 6, runSpacing: 6, children: [
              for (final b in f.budgets)
                ChoiceChip(
                  label: Text('تا ${millionLabel(b)}'),
                  selected: _max == b,
                  showCheckmark: false,
                  onSelected: (on) => setState(() => _max = on ? b : null),
                ),
            ]),
          ],
          const SizedBox(height: 20),
          FilledButton(
            style: FilledButton.styleFrom(minimumSize: const Size(10, 56)),
            onPressed: _busy ? null : _send,
            child: _busy
                ? const SizedBox.square(dimension: 22, child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white))
                : const Text('بفرست برای کارشناس'),
          ),
        ],
      ]),
    );
  }
}

class _Steps extends StatelessWidget {
  const _Steps();
  @override
  Widget build(BuildContext context) {
    Widget step(int n, String t, String s, Color c) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Container(
              width: 34,
              height: 34,
              alignment: Alignment.center,
              decoration: BoxDecoration(color: c, borderRadius: BorderRadius.circular(11)),
              child: Text(faDigits(n), style: const TextStyle(fontWeight: FontWeight.w900, color: C.ink)),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(t, style: const TextStyle(fontWeight: FontWeight.w800)),
                Text(s, style: const TextStyle(color: C.muted, fontSize: 12.5, height: 1.7)),
              ]),
            ),
          ]),
        );
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 2),
      decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(20)),
      child: Column(children: [
        step(1, 'عکس را بفرست', 'رنگ‌های فرش همان لحظه تشخیص داده می‌شود و چند پیشنهاد اولیه می‌بینی.', C.saffron),
        step(2, 'کارشناس بررسی می‌کند', 'طرح، رنگ و جنس را با فرش‌های ایران کارپت مقایسه می‌کند.', const Color(0xFF9ADBE2)),
        step(3, 'پیشنهادها را می‌گیری', 'پاسخ در «درخواست‌های من» می‌آید و با پیامک هم خبرت می‌کنیم.', const Color(0xFFF7B5C3)),
      ]),
    );
  }
}

Map<String, String> get _authHeaders => {if (Api.i.token != null) 'Authorization': 'Token ${Api.i.token}'};

class _Photo extends StatelessWidget {
  const _Photo(this.url, {this.height = 220, this.radius = 20});
  final String url;
  final double height, radius;
  @override
  Widget build(BuildContext context) {
    if (url.isEmpty) {
      return Container(
        height: height,
        decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(radius)),
        child: const Icon(Icons.notes_rounded, color: C.muted, size: 34),
      );
    }
    return ClipRRect(
      borderRadius: BorderRadius.circular(radius),
      child: CachedNetworkImage(
        imageUrl: url,
        httpHeaders: _authHeaders,
        height: height,
        width: double.infinity,
        fit: BoxFit.cover,
        placeholder: (_, _) => Container(color: C.soft),
        errorWidget: (_, _, _) => Container(color: C.soft, child: const Icon(Icons.image_not_supported_outlined, color: C.muted)),
      ),
    );
  }
}

/// فهرست درخواست‌های مشتری
class RequestsScreen extends StatefulWidget {
  const RequestsScreen({super.key});
  @override
  State<RequestsScreen> createState() => _RequestsScreenState();
}

class _RequestsScreenState extends State<RequestsScreen> {
  List<Json>? _items;
  String? _err;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!context.read<Auth>().loggedIn) {
      setState(() => _items = []);
      return;
    }
    try {
      final r = await Api.i.get('/finder/requests/') as Json;
      if (mounted) setState(() => (_items = (r['results'] as List).cast<Json>(), _err = null));
    } on ApiError catch (e) {
      if (mounted) setState(() => _err = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final items = _items;
    return Scaffold(
      appBar: AppBar(title: const Text('درخواست‌های من')),
      body: items == null
          ? (_err != null ? StatusView(message: _err!, onRetry: _load) : const Loading())
          : items.isEmpty
              ? StatusView(
                  icon: Icons.inbox_outlined,
                  message: context.read<Auth>().loggedIn
                      ? 'هنوز درخواستی نفرستاده‌ای.\nعکس فرشی که دوست داری را بفرست تا کارشناس شبیه‌اش را پیدا کند.'
                      : 'برای دیدن درخواست‌ها وارد شو.',
                  action: context.read<Auth>().loggedIn
                      ? null
                      : FilledButton(
                          onPressed: () async {
                            if (await Navigator.pushNamed(context, '/login') == true) _load();
                          },
                          child: const Text('ورود')),
                )
              : RefreshIndicator(
                  color: C.pink,
                  onRefresh: _load,
                  child: ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 10),
                    itemBuilder: (_, i) => _row(items[i]),
                  ),
                ),
    );
  }

  Widget _row(Json r) {
    final unread = r['unread'] as bool? ?? false;
    final answered = r['status'] == 'answered';
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(18), side: BorderSide(color: unread ? C.pink : C.line, width: unread ? 2 : 1.4)),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () async {
          await Navigator.push(context, MaterialPageRoute(builder: (_) => RequestScreen(data: r)));
          _load();
        },
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Row(children: [
            SizedBox(width: 74, child: _Photo(r['photo'] as String? ?? '', height: 74, radius: 14)),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  (r['text'] as String? ?? '').isNotEmpty ? r['text'] as String : (r['kind'] == 'photo' ? 'عکس فرش' : 'درخواست'),
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(fontWeight: FontWeight.w800, height: 1.6),
                ),
                const SizedBox(height: 4),
                Row(children: [
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                    decoration: BoxDecoration(color: answered ? C.tealTint : C.soft, borderRadius: BorderRadius.circular(8)),
                    child: Text(r['status_label'] as String,
                        style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: answered ? C.tealDark : C.ink2)),
                  ),
                  if (unread) ...[
                    const SizedBox(width: 6),
                    const Text('پاسخ تازه', style: TextStyle(color: C.pinkDark, fontSize: 11.5, fontWeight: FontWeight.w900)),
                  ],
                ]),
              ]),
            ),
            const Icon(Icons.chevron_left_rounded, color: C.muted),
          ]),
        ),
      ),
    );
  }
}

/// جزئیات یک درخواست: عکس، رنگ‌ها، پاسخ کارشناس و فرش‌های پیشنهادی
class RequestScreen extends StatefulWidget {
  const RequestScreen({super.key, required this.data});
  final Json data;
  @override
  State<RequestScreen> createState() => _RequestScreenState();
}

class _RequestScreenState extends State<RequestScreen> {
  late Json r = widget.data;

  @override
  void initState() {
    super.initState();
    if (r['unread'] == true) {
      Api.i.post('/finder/requests/${r['id']}/seen/').then((_) {
        if (mounted) context.read<FinderData>().refreshUnread();
      }).catchError((_) {});
    }
  }

  @override
  Widget build(BuildContext context) {
    final products = ((r['products'] as List?) ?? []).cast<Json>();
    final auto = ((r['auto'] as List?) ?? []).cast<Json>();
    final colors = ((r['colors'] as List?) ?? []).cast<Json>();
    final names = ((r['color_names'] as List?) ?? []).cast<String>();
    final answered = r['status'] == 'answered';
    return Scaffold(
      appBar: AppBar(title: Text('درخواست ${faDigits(r['id'])}')),
      body: CustomScrollView(slivers: [
        SliverPadding(
          padding: const EdgeInsets.fromLTRB(16, 4, 16, 0),
          sliver: SliverList.list(children: [
            if ((r['photo'] as String? ?? '').isNotEmpty) _Photo(r['photo'] as String, height: 240),
            if (colors.isNotEmpty) ...[
              const SizedBox(height: 14),
              const Text('رنگ‌های فرش تو', style: TextStyle(fontWeight: FontWeight.w900)),
              const SizedBox(height: 8),
              Row(children: [
                for (final c in colors)
                  Expanded(
                    flex: (((c['share'] as num?) ?? .2) * 100).round().clamp(6, 100),
                    child: Container(
                      height: 34,
                      margin: const EdgeInsetsDirectional.only(end: 4),
                      decoration: BoxDecoration(color: hexColor(c['hex'] as String), borderRadius: BorderRadius.circular(9)),
                    ),
                  ),
              ]),
              if (names.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text('نزدیک به: ${names.join('، ')}', style: const TextStyle(color: C.muted, fontSize: 12.5)),
                ),
            ],
            if ((r['text'] as String? ?? '').isNotEmpty) ...[
              const SizedBox(height: 14),
              _bubble('تو', r['text'] as String, mine: true),
            ],
            const SizedBox(height: 14),
            if (answered && (r['reply'] as String? ?? '').isNotEmpty)
              _bubble('کارشناس ایران کارپت', r['reply'] as String)
            else if (!answered)
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(color: C.saffronTint, borderRadius: BorderRadius.circular(16)),
                child: const Row(children: [
                  Icon(Icons.hourglass_top_rounded, color: Color(0xFF9A6A00)),
                  SizedBox(width: 10),
                  Expanded(
                      child: Text('کارشناس در حال بررسی است. پاسخ همین‌جا می‌آید و با پیامک هم خبرت می‌کنیم.',
                          style: TextStyle(height: 1.7, fontSize: 13))),
                ]),
              ),
          ]),
        ),
        if (products.isNotEmpty) ..._grid('پیشنهاد کارشناس', products),
        if (auto.isNotEmpty) ..._grid(answered ? 'پیشنهادهای اولیهٔ فرش‌یاب' : 'تا جواب کارشناس، این‌ها شبیه‌اند', auto),
        const SliverToBoxAdapter(child: SizedBox(height: 28)),
      ]),
    );
  }

  List<Widget> _grid(String title, List<Json> items) => [
        SliverToBoxAdapter(child: SectionTitle(title)),
        SliverPadding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          sliver: SliverGrid(
            gridDelegate:
                const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 2, mainAxisSpacing: 14, crossAxisSpacing: 12, childAspectRatio: .52),
            delegate: SliverChildBuilderDelegate((_, i) => ProductCard(items[i]), childCount: items.length),
          ),
        ),
      ];

  Widget _bubble(String who, String text, {bool mine = false}) => Align(
        alignment: mine ? AlignmentDirectional.centerStart : AlignmentDirectional.centerEnd,
        child: Container(
          constraints: const BoxConstraints(maxWidth: 520),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: mine ? C.soft : C.ink,
            borderRadius: BorderRadiusDirectional.only(
              topStart: const Radius.circular(18),
              topEnd: const Radius.circular(18),
              bottomStart: Radius.circular(mine ? 4 : 18),
              bottomEnd: Radius.circular(mine ? 18 : 4),
            ),
          ),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(who, style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: mine ? C.muted : C.saffron)),
            const SizedBox(height: 4),
            Text(faDigits(text), style: TextStyle(height: 1.9, color: mine ? C.ink : Colors.white)),
          ]),
        ),
      );
}
