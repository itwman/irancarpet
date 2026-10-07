import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api.dart';

/// ورود و حساب کاربری
class Auth extends ChangeNotifier {
  static const _storage = FlutterSecureStorage();
  Json? user;
  bool get loggedIn => Api.i.token != null;

  Future<void> load() async {
    try {
      Api.i.token = await _storage.read(key: 'token');
      final u = await _storage.read(key: 'user');
      if (u != null) user = jsonDecode(u) as Json;
    } catch (_) {}
    if (loggedIn) refresh();
  }

  Future<void> refresh() async {
    try {
      user = await Api.i.get('/me/') as Json;
      await _storage.write(key: 'user', value: jsonEncode(user));
      notifyListeners();
    } on ApiError catch (e) {
      if (e.unauthorized) await logout(remote: false);
    }
  }

  Future<void> signIn(Json data) async {
    Api.i.token = data['token'] as String;
    user = data['user'] as Json;
    await _storage.write(key: 'token', value: Api.i.token);
    await _storage.write(key: 'user', value: jsonEncode(user));
    notifyListeners();
  }

  Future<void> logout({bool remote = true}) async {
    if (remote) {
      try {
        await Api.i.post('/auth/logout/');
      } catch (_) {}
    }
    Api.i.token = null;
    user = null;
    await _storage.deleteAll();
    notifyListeners();
  }

  String get displayName {
    final u = user;
    if (u == null) return '';
    final n = '${u['first_name'] ?? ''} ${u['last_name'] ?? ''}'.trim();
    return n.isEmpty ? (u['mobile'] ?? '') as String : n;
  }
}

/// یک قلم سبد: شناسهٔ سایز + اطلاعات نمایشی (قیمت قطعی را سرور حساب می‌کند)
class CartItem {
  CartItem({required this.variation, required this.qty, required this.productId, required this.title,
      required this.size, required this.image, required this.price, required this.pairOnly});
  final int variation, productId;
  int qty;
  final String title, size, image;
  final int price;
  final bool pairOnly;

  Json toJson() => {'variation': variation, 'qty': qty, 'product_id': productId, 'title': title, 'size': size,
        'image': image, 'price': price, 'pair_only': pairOnly};
  factory CartItem.fromJson(Json j) => CartItem(variation: j['variation'] as int, qty: j['qty'] as int,
      productId: j['product_id'] as int, title: j['title'] as String, size: j['size'] as String,
      image: j['image'] as String, price: j['price'] as int, pairOnly: j['pair_only'] as bool? ?? false);
}

class Cart extends ChangeNotifier {
  final List<CartItem> items = [];
  int get count => items.fold(0, (a, b) => a + b.qty);
  int get roughTotal => items.fold(0, (a, b) => a + b.qty * b.price);

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    final raw = p.getString('cart');
    if (raw != null) {
      try {
        items.addAll((jsonDecode(raw) as List).map((e) => CartItem.fromJson(e as Json)));
      } catch (_) {}
    }
    notifyListeners();
  }

  Future<void> _save() async {
    final p = await SharedPreferences.getInstance();
    await p.setString('cart', jsonEncode(items.map((e) => e.toJson()).toList()));
    notifyListeners();
  }

  static int fix(int q, bool pair) {
    q = q.clamp(1, 20);
    return pair && q.isOdd ? q + 1 : q;
  }

  Future<void> add(CartItem it) async {
    final ex = items.where((e) => e.variation == it.variation).firstOrNull;
    if (ex != null) {
      ex.qty = fix(ex.qty + it.qty, ex.pairOnly);
    } else {
      it.qty = fix(it.qty, it.pairOnly);
      items.add(it);
    }
    await _save();
  }

  /// فرصت ویژه: دقیقاً همین تعداد از این سایز (حتی اگر سایز «فقط جفت» باشد)
  Future<void> putExact(CartItem it, int qty) async {
    items.removeWhere((e) => e.variation == it.variation);
    it.qty = qty.clamp(1, 20);
    items.add(it);
    await _save();
  }

  Future<void> setQty(int variation, int q) async {
    final it = items.where((e) => e.variation == variation).firstOrNull;
    if (it == null) return;
    if (q <= 0) {
      items.remove(it);
    } else {
      it.qty = fix(q, it.pairOnly);
    }
    await _save();
  }

  Future<void> clear() async {
    items.clear();
    await _save();
  }

  List<Json> get payload => items.map((e) => {'variation': e.variation, 'qty': e.qty}).toList();
}

/// علاقه‌مندی‌ها (روی گوشی؛ بعد از ورود با حساب هم‌گام می‌شود)
class Wishlist extends ChangeNotifier {
  final Set<int> ids = {};

  Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    ids.addAll((p.getStringList('wish') ?? []).map(int.parse));
    notifyListeners();
  }

  Future<void> _save() async {
    final p = await SharedPreferences.getInstance();
    await p.setStringList('wish', ids.map((e) => '$e').toList());
    notifyListeners();
  }

  bool has(int id) => ids.contains(id);

  Future<void> toggle(int id) async {
    final add = !ids.contains(id);
    add ? ids.add(id) : ids.remove(id);
    await _save();
    if (Api.i.token != null) {
      try {
        await Api.i.post('/wishlist/', add ? {'add': [id]} : {'remove': [id]});
      } catch (_) {}
    }
  }

  /// بعد از ورود: علاقه‌مندی‌های گوشی و حساب یکی می‌شوند
  Future<void> sync() async {
    if (Api.i.token == null) return;
    try {
      final r = await Api.i.post('/wishlist/', {'add': ids.toList()}) as Json;
      ids
        ..clear()
        ..addAll((r['ids'] as List).cast<int>());
      await _save();
    } catch (_) {}
  }
}

/// مقایسه (حداکثر ۳ فرش)
class Compare extends ChangeNotifier {
  final List<int> ids = [];
  bool has(int id) => ids.contains(id);

  /// false یعنی جا پر است
  bool toggle(int id) {
    if (ids.contains(id)) {
      ids.remove(id);
    } else {
      if (ids.length >= 3) return false;
      ids.add(id);
    }
    notifyListeners();
    return true;
  }
}

/// تنظیمات سایت (درگاه‌ها، بیعانه، استان‌ها…)
class AppConfig extends ChangeNotifier {
  Json data = {};
  Future<void> load() async {
    try {
      data = await Api.i.get('/config/') as Json;
      notifyListeners();
    } catch (e) {
      debugPrint('config: $e');
    }
  }

  List<Json> get gateways => ((data['gateways'] as List?) ?? []).cast<Json>();
  List<String> get provinces => ((data['provinces'] as List?) ?? []).cast<String>();
  Json get shop => (data['shop'] as Json?) ?? {};
  List<Json> get sorts => ((data['sorts'] as List?) ?? []).cast<Json>();
  List<Json> get installmentPlans => (((data['installment'] as Json?)?['plans'] as List?) ?? []).cast<Json>();
}
