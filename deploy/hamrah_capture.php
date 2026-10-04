<?php
/**
 * ضبط پاسخ‌های API اپلیکیشن قدیمی (افزونهٔ wp_hamrah) از خود وردپرس، برای ساختن نسخهٔ سازگار در جنگو.
 * فقط می‌خواند؛ چیزی در وردپرس تغییر نمی‌کند. مسیرهای سبد خرید/پرداخت/کاربر اجرا نمی‌شوند (اطلاعات شخصی).
 *
 *   php deploy/hamrah_capture.php [مسیر وردپرس] > /root/hamrah.json
 */
// نام متغیر نباید $wp باشد (متغیر سراسری خود وردپرس است)
$hc_root = $argv[1] ?? '/var/www/irancarpet/public_html';
define('WP_USE_THEMES', false);
$_SERVER['HTTP_HOST'] = $_SERVER['SERVER_NAME'] = 'irancarpet.net';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['HTTPS'] = 'on';
require $hc_root . '/wp-load.php';

function shrink($v)
{
    if (is_object($v)) {
        $v = (array) $v;
    }
    if (is_array($v)) {
        $list = array_keys($v) === range(0, count($v) - 1);
        $out = [];
        $i = 0;
        foreach ($v as $k => $x) {
            if ($list && $i >= 3) {
                $out[] = '… +' . (count($v) - 3);
                break;
            }
            $out[$k] = shrink($x);
            $i++;
        }
        return $out;
    }
    if (is_string($v) && mb_strlen($v) > 300) {
        return mb_substr($v, 0, 300) . '…';
    }
    return $v;
}

$server = rest_get_server();
$routes = [];
foreach ($server->get_routes() as $route => $handlers) {
    if (strpos($route, '/wp_hamrah_app') === 0) {
        $methods = [];
        foreach ($handlers as $h) {
            $methods = array_merge($methods, array_keys($h['methods'] ?? []));
        }
        $routes[$route] = array_values(array_unique($methods));
    }
}

// نمونهٔ درخواست‌های واقعی برنامه از لاگ nginx
$seen = [];
$samples = [];
foreach (glob('/var/log/nginx/access.log*') as $f) {
    $h = gzopen($f, 'r');
    if (!$h) {
        continue;
    }
    while (($l = gzgets($h)) !== false) {
        if (!preg_match('#"(GET|POST) (/wp-json/wp_hamrah_app/[^ ]+) [^"]*" \d+ \d+ "[^"]*" "([^"]*)"#', $l, $m)) {
            continue;
        }
        $path = parse_url($m[2], PHP_URL_PATH);
        if (preg_match('#cart|checkout|user|login|register|order|otp|profile|address|wishlist#i', $path)) {
            $samples['_skipped'][$path] = true;
            continue;
        }
        $seen[$path] = ($seen[$path] ?? 0) + 1;
        if ($seen[$path] <= 2) {
            $samples[] = ['method' => $m[1], 'url' => $m[2], 'agent' => $m[3]];
        }
    }
    gzclose($h);
}

$out = ['routes' => $routes, 'skipped' => array_keys($samples['_skipped'] ?? []), 'calls' => []];
unset($samples['_skipped']);
foreach ($samples as $s) {
    $u = parse_url($s['url']);
    parse_str($u['query'] ?? '', $q);
    $route = substr($u['path'], strlen('/wp-json'));
    $req = new WP_REST_Request($s['method'], $route);
    $req->set_query_params($q);
    if ($s['method'] === 'POST') {
        $req->set_body_params($q);
    }
    $res = rest_do_request($req);
    $out['calls'][] = [
        'request' => $s,
        'status'  => $res->get_status(),
        'data'    => shrink($server->response_to_data($res, false)),
    ];
}
echo wp_json_encode($out, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT), "\n";
