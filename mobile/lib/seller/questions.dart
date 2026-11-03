import 'package:flutter/material.dart';

import '../core/api.dart';
import '../core/theme.dart';
import '../widgets/common.dart';
import 'ui.dart';

/// پرسش‌های مشتریان دربارهٔ کالاهای فروشگاه
class SellerQuestions extends StatefulWidget {
  const SellerQuestions({super.key});
  @override
  State<SellerQuestions> createState() => _SellerQuestionsState();
}

class _SellerQuestionsState extends State<SellerQuestions> {
  Future<Json>? _future;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() => setState(() => _future = Api.i.get('/seller/questions/').then((v) => v as Json));

  Future<void> _answer(Map q) async {
    final c = TextEditingController();
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (s) => Padding(
        padding: EdgeInsets.fromLTRB(20, 0, 20, 20 + MediaQuery.of(s).viewInsets.bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text('${q['text']}', style: const TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 12),
          TextField(controller: c, autofocus: true, maxLines: 4, decoration: const InputDecoration(labelText: 'پاسخ شما')),
          const SizedBox(height: 6),
          const Text('پاسخ زیر کالا برای همه نمایش داده می‌شود. شمارهٔ تماس، پیوند و شناسهٔ شبکه‌های اجتماعی مجاز نیست.',
              style: TextStyle(color: C.muted, fontSize: 12.5)),
          const SizedBox(height: 14),
          FilledButton(onPressed: () => Navigator.pop(s, true), child: const Text('ثبت پاسخ')),
        ]),
      ),
    );
    if (ok != true || !mounted) return;
    final r = await run(context, () async => await Api.i.post('/seller/questions/', {'id': q['id'], 'answer': c.text.trim()}) as Json);
    if (r != null && mounted) {
      toast(context, 'پاسخ ثبت شد.');
      setState(() => _future = Future.value(r));
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: const Text('پرسش‌های مشتریان'), actions: [GuideButton('questions', onChanged: () => setState(() {}))]),
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
              if (items.isEmpty) return const Empty('هنوز پرسشی دربارهٔ کالاهایتان نرسیده.', icon: Icons.help_outline_rounded);
              // بی‌پاسخ‌ها اول
              final sorted = [...items.where((q) => (q['answers'] as List).isEmpty), ...items.where((q) => (q['answers'] as List).isNotEmpty)];
              return ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: sorted.length + 1,
                separatorBuilder: (_, i) => SizedBox(height: i == 0 ? 0 : 10),
                itemBuilder: (_, j) {
                  if (j == 0) return const GuideCard('questions');
                  final q = sorted[j - 1];
                  final p = (q['product'] as Map?) ?? {};
                  final answers = (q['answers'] as List).cast<String>();
                  return Panel(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Row(children: [
                        SizedBox(width: 34, height: 44, child: NetImage('${p['image'] ?? ''}', radius: 6)),
                        const SizedBox(width: 10),
                        Expanded(
                            child: Text('${p['title'] ?? ''}',
                                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(color: C.muted, fontSize: 12.5))),
                        Text(jdate(q['at'] as String?), style: const TextStyle(color: C.muted, fontSize: 12)),
                      ]),
                      const SizedBox(height: 8),
                      Text('${q['text']}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      Text('${q['name'] ?? ''}', style: const TextStyle(color: C.muted, fontSize: 12)),
                      for (final a in answers)
                        Container(
                          width: double.infinity,
                          margin: const EdgeInsets.only(top: 8),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(color: C.soft, borderRadius: BorderRadius.circular(10)),
                          child: Text(a),
                        ),
                      if (answers.isEmpty)
                        Align(
                          alignment: AlignmentDirectional.centerEnd,
                          child: FilledButton.tonal(onPressed: () => _answer(q), child: const Text('پاسخ دادن')),
                        ),
                    ]),
                  );
                },
              );
            },
          ),
        ),
      );
}
