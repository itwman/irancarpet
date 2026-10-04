/// قالب‌بندی عدد و مبلغ. ارقام با فونت «Vazirmatn FD» فارسی نمایش داده می‌شوند.
String sep(num n) {
  final s = n.round().abs().toString();
  final b = StringBuffer();
  for (var i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 == 0) b.write('٬');
    b.write(s[i]);
  }
  return (n < 0 ? '-' : '') + b.toString();
}

String toman(num? n) => n == null || n == 0 ? 'استعلام قیمت' : '${sep(n)} تومان';

const _fa = '۰۱۲۳۴۵۶۷۸۹';
const _ar = '٠١٢٣٤٥٦٧٨٩';

/// ارقام فارسی/عربی ورودی کاربر → لاتین
String latin(String s) {
  final b = StringBuffer();
  for (final ch in s.split('')) {
    final i = _fa.indexOf(ch);
    final j = _ar.indexOf(ch);
    b.write(i >= 0 ? '$i' : (j >= 0 ? '$j' : ch));
  }
  return b.toString();
}

String faDigits(Object s) => s.toString().split('').map((c) {
      final d = int.tryParse(c);
      return d == null ? c : _fa[d];
    }).join();

String metres(double v) {
  if (v == v.roundToDouble()) return v.toInt().toString();
  return v.toStringAsFixed(2).replaceAll(RegExp(r'0+$'), '').replaceAll('.', '٫');
}
