import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const kSite = String.fromEnvironment('SITE', defaultValue: 'https://irancarpet.net');
const kApi = '$kSite/api/app/v1';
const kAppVersion = '1.0.3';

typedef Json = Map<String, dynamic>;

class ApiError implements Exception {
  ApiError(this.message, {this.status = 0, this.errors = const {}});
  final String message;
  final int status;
  final Map<String, dynamic> errors;
  bool get unauthorized => status == 401;
  @override
  String toString() => message;
}

/// ارتباط با سایت ایران کارپت.
class Api {
  Api._();
  static final Api i = Api._();

  String? token;
  String installId = '';
  final _client = http.Client();

  Future<void> init() async {
    final p = await SharedPreferences.getInstance();
    installId = p.getString('install_id') ?? '';
    if (installId.isEmpty) {
      final r = Random.secure();
      installId = List.generate(16, (_) => r.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
      await p.setString('install_id', installId);
    }
  }

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Install-Id': installId,
        'X-App-Version': kAppVersion,
        'X-Device-Model': kIsWeb ? 'web' : defaultTargetPlatform.name,
        if (token != null) 'Authorization': 'Token $token',
      };

  Future<dynamic> get(String path, [Map<String, dynamic>? query]) async {
    final q = <String, String>{};
    query?.forEach((k, v) {
      if (v != null && '$v'.isNotEmpty) q[k] = '$v';
    });
    final uri = Uri.parse('$kApi$path').replace(queryParameters: q.isEmpty ? null : q);
    return _send(() => _client.get(uri, headers: _headers));
  }

  Future<dynamic> post(String path, [Object? body]) async {
    final uri = Uri.parse('$kApi$path');
    return _send(() => _client.post(uri, headers: _headers, body: jsonEncode(body ?? {})));
  }

  /// فرم چندبخشی (برای فرستادن فایل مثل تصویر چک). files: نام فیلد ← (بایت‌ها، نام فایل)
  Future<dynamic> postMultipart(String path, Map<String, String> fields, Map<String, (List<int>, String)> files) async {
    final uri = Uri.parse('$kApi$path');
    return _send(() async {
      final req = http.MultipartRequest('POST', uri)
        ..headers.addAll({..._headers}..remove('Content-Type'))
        ..fields.addAll(fields);
      for (final e in files.entries) {
        req.files.add(http.MultipartFile.fromBytes(e.key, e.value.$1, filename: e.value.$2));
      }
      return http.Response.fromStream(await _client.send(req).timeout(const Duration(seconds: 60)));
    });
  }

  Future<dynamic> _send(Future<http.Response> Function() fn) async {
    http.Response r;
    try {
      r = await fn().timeout(const Duration(seconds: 25));
    } on TimeoutException {
      throw ApiError('اتصال کند است؛ دوباره امتحان کنید.');
    } catch (_) {
      throw ApiError('اتصال به اینترنت برقرار نیست.');
    }
    dynamic data;
    try {
      data = jsonDecode(utf8.decode(r.bodyBytes));
    } catch (_) {
      throw ApiError('پاسخ نامعتبر از سرور (${r.statusCode}).', status: r.statusCode);
    }
    if (r.statusCode >= 400) {
      final m = data is Map ? data : {};
      throw ApiError((m['error'] ?? 'خطای ناشناخته') as String,
          status: r.statusCode, errors: (m['errors'] as Map?)?.cast<String, dynamic>() ?? {});
    }
    return data;
  }
}
