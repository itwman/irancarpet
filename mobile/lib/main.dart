import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:provider/provider.dart';

import 'core/api.dart';
import 'core/notify.dart';
import 'core/theme.dart';
import 'screens/account.dart';
import 'screens/cart.dart';
import 'screens/catalog.dart';
import 'screens/checkout.dart';
import 'screens/compare.dart';
import 'screens/login.dart';
import 'screens/orders.dart';
import 'screens/product.dart';
import 'screens/room.dart';
import 'screens/shell.dart';
import 'screens/splash.dart';
import 'state/app_state.dart';

final navKey = GlobalKey<NavigatorState>();
final messengerKey = GlobalKey<ScaffoldMessengerState>();

/// پیام‌های پایین صفحه با رفتن به صفحهٔ دیگر بسته می‌شوند تا روی دکمه‌ها نمانند.
class _SnackCleaner extends NavigatorObserver {
  void _clear() => messengerKey.currentState?.hideCurrentSnackBar();
  @override
  void didPush(Route route, Route? previousRoute) => _clear();
  @override
  void didPop(Route route, Route? previousRoute) => _clear();
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent, statusBarIconBrightness: Brightness.dark, systemNavigationBarColor: Colors.white));
  await Api.i.init();
  final auth = Auth(), cart = Cart(), wish = Wishlist(), config = AppConfig();
  await Future.wait([auth.load(), cart.load(), wish.load()]);
  runApp(MultiProvider(
    providers: [
      ChangeNotifierProvider.value(value: auth),
      ChangeNotifierProvider.value(value: cart),
      ChangeNotifierProvider.value(value: wish),
      ChangeNotifierProvider.value(value: config),
      ChangeNotifierProvider(create: (_) => Compare()),
    ],
    child: const IranCarpetApp(),
  ));
  config.load();
  onNotificationTap = _openPayload;
  setupNotifications().catchError((_) {});
}

void _openPayload(String payload) {
  final nav = navKey.currentState;
  if (nav == null) return;
  final parts = payload.split(':');
  switch (parts.first) {
    case 'product':
      nav.pushNamed('/product', arguments: int.tryParse(parts.last));
    case 'category':
      nav.pushNamed('/products', arguments: {'title': 'فرش‌ها', 'query': {'category': parts.last}});
    default:
      nav.pushNamed('/notifications');
  }
}

class IranCarpetApp extends StatefulWidget {
  const IranCarpetApp({super.key});
  @override
  State<IranCarpetApp> createState() => _IranCarpetAppState();
}

class _IranCarpetAppState extends State<IranCarpetApp> {
  StreamSubscription<Uri>? _links;

  @override
  void initState() {
    super.initState();
    // بازگشت از درگاه بانک: irancarpet://order/123?paid=1
    _links = AppLinks().uriLinkStream.listen(_onLink, onError: (_) {});
  }

  void _onLink(Uri uri) {
    if (uri.scheme != 'irancarpet') return;
    if (uri.host == 'order' && uri.pathSegments.isNotEmpty) {
      final n = int.tryParse(uri.pathSegments.first);
      if (n == null) return;
      final paid = uri.queryParameters['paid'] == '1';
      final ctx = navKey.currentContext;
      if (paid && ctx != null) ctx.read<Cart>().clear();
      navKey.currentState?.pushNamedAndRemoveUntil('/order', (r) => r.isFirst, arguments: {'number': n, 'just_paid': paid});
    } else if (uri.host == 'product' && uri.pathSegments.isNotEmpty) {
      navKey.currentState?.pushNamed('/product', arguments: int.tryParse(uri.pathSegments.first));
    }
  }

  @override
  void dispose() {
    _links?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      navigatorKey: navKey,
      scaffoldMessengerKey: messengerKey,
      navigatorObservers: [_SnackCleaner()],
      title: 'ایران کارپت',
      debugShowCheckedModeBanner: false,
      theme: buildTheme(),
      locale: const Locale('fa', 'IR'),
      supportedLocales: const [Locale('fa', 'IR')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      home: const Splash(),
      onGenerateRoute: (s) {
        final a = s.arguments;
        Widget page = switch (s.name) {
          '/home' => const Shell(),
          '/product' => ProductScreen(id: a as int),
          '/products' => ProductListScreen(
              title: (a as Map)['title'] as String, query: ((a['query'] as Map?) ?? {}).cast<String, dynamic>()),
          '/search' => const SearchScreen(),
          '/room' => RoomScreen(args: a as Map<String, dynamic>),
          '/cart' => const CartScreen(standalone: true),
          '/checkout' => const CheckoutScreen(),
          '/login' => LoginScreen(reason: a as String?),
          '/orders' => const OrdersScreen(),
          '/order' => OrderScreen(number: (a as Map)['number'] as int, justPaid: a['just_paid'] as bool? ?? false),
          '/compare' => const CompareScreen(),
          '/notifications' => const NotificationsScreen(),
          '/profile' => const ProfileScreen(),
          '/track' => const TrackScreen(),
          _ => const Shell(),
        };
        return MaterialPageRoute(builder: (_) => page, settings: s);
      },
    );
  }
}
