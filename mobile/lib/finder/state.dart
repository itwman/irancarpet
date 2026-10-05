import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../core/api.dart';
import '../core/format.dart';

/// تنظیمات فرش‌یاب از سرور: گروه‌های نیاز، سایزها، بودجه‌ها و جمله‌های نمونه.
class FinderData extends ChangeNotifier {
  Json data = {};
  String? error;
  int unread = 0;

  bool get ready => data.isNotEmpty;
  List<Json> get groups => ((data['groups'] as List?) ?? []).cast<Json>();
  List<Json> get sizes => ((data['sizes'] as List?) ?? []).cast<Json>();
  List<int> get budgets => ((data['budgets'] as List?) ?? []).cast<int>();
  List<String> get examples => ((data['examples'] as List?) ?? []).cast<String>();

  Json? need(int id) {
    for (final g in groups) {
      for (final n in (g['needs'] as List).cast<Json>()) {
        if (n['id'] == id) return n;
      }
    }
    return null;
  }

  Future<void> load() async {
    try {
      data = await Api.i.get('/finder/config/') as Json;
      error = null;
    } on ApiError catch (e) {
      error = e.message;
    }
    notifyListeners();
  }

  /// تعداد پاسخ‌های تازهٔ کارشناس (برای نشان روی زبانهٔ «من»)
  Future<void> refreshUnread() async {
    if (Api.i.token == null) {
      if (unread != 0) {
        unread = 0;
        notifyListeners();
      }
      return;
    }
    try {
      final r = await Api.i.get('/finder/requests/') as Json;
      unread = r['unread'] as int? ?? 0;
      notifyListeners();
    } catch (_) {}
  }
}

/// خواستهٔ مشتری: نیازها، سایز، بودجه و جملهٔ آزاد.
class Wish {
  Wish({Set<int>? needs, this.size, this.min, this.max, Set<int>? reeds, this.q = ''})
      : needs = needs ?? <int>{},
        reeds = reeds ?? <int>{};
  final Set<int> needs, reeds;
  int? size, min, max;
  String q;

  bool get isEmpty => needs.isEmpty && reeds.isEmpty && size == null && min == null && max == null && q.trim().isEmpty;

  Wish copy() => Wish(needs: {...needs}, size: size, min: min, max: max, reeds: {...reeds}, q: q);

  Map<String, dynamic> query() => {
        if (q.trim().isNotEmpty) 'q': q.trim(),
        if (needs.isNotEmpty) 'needs': needs.join(','),
        if (reeds.isNotEmpty) 'reeds': reeds.join(','),
        'size': size,
        'min': min,
        'max': max,
      };

  /// بعد از جستجو، آنچه سرور از جمله فهمید به انتخاب‌های صریح تبدیل می‌شود.
  void absorb(Json applied, String unknown) {
    needs.addAll(((applied['needs'] as List?) ?? []).cast<int>());
    reeds.addAll(((applied['reeds'] as List?) ?? []).cast<int>());
    size = applied['size'] as int? ?? size;
    min = applied['min'] as int? ?? min;
    max = applied['max'] as int? ?? max;
    q = unknown;
  }
}

/// «۴۰ میلیون»
String millionLabel(int n) {
  if (n % 1000000 == 0) return '${faDigits(n ~/ 1000000)} میلیون';
  return '${faDigits((n / 1000000).toStringAsFixed(1))} میلیون';
}


/// خواسته‌ها برای فرستادن همراه درخواست کارشناس
String jsonWanted(Wish? w) => jsonEncode({
      if (w != null && w.needs.isNotEmpty) 'needs': w.needs.toList(),
      if (w?.size != null) 'size': w!.size,
      if (w?.max != null) 'max': w!.max,
      if (w != null && w.q.trim().isNotEmpty) 'q': w.q.trim(),
    });
