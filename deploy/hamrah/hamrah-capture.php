<?php
/**
 * Plugin Name: ثبت موقت درخواست‌های اپلیکیشن قدیمی (ایران کارپت)
 * Description: درخواست و پاسخ مسیرهای /wp-json/wp_hamrah_app/ را برای ساختن نسخهٔ سازگار در جنگو ثبت می‌کند.
 *              مقدارهای متنی بخش‌های سبد خرید، پرداخت و کاربر ثبت نمی‌شوند (فقط ساختار). با «hamrah_bridge.sh off» حذف می‌شود.
 */
if (empty($_SERVER['REQUEST_URI']) || strpos($_SERVER['REQUEST_URI'], '/wp-json/wp_hamrah_app/') === false) {
    return;
}
define('HC_LOG', '/var/log/hamrah/capture.jsonl');
$GLOBALS['hc_body'] = file_get_contents('php://input');
$GLOBALS['hc_out'] = '';

function hc_sensitive($path)
{
    return (bool) preg_match('#cart|checkout|user|login|register|order|otp|profile|address|wishlist|pay|account|sms|token#i', $path);
}

function hc_clean($v, $mask, $depth = 0)
{
    if (is_array($v)) {
        $list = array_keys($v) === range(0, count($v) - 1);
        $out = [];
        $i = 0;
        foreach ($v as $k => $x) {
            if ($list && $i >= 4) {
                $out[] = '… +' . (count($v) - 4);
                break;
            }
            $out[$k] = hc_clean($x, $mask || preg_match('#phone|mobile|mail|name|address|pass|token|card|code|postcode|city|state#i', (string) $k), $depth + 1);
            $i++;
        }
        return $out;
    }
    if (is_string($v)) {
        if ($mask) {
            return 'str(' . mb_strlen($v) . ')';
        }
        return mb_strlen($v) > 400 ? mb_substr($v, 0, 400) . '…' : $v;
    }
    return $v;
}

function hc_parse($raw)
{
    $j = json_decode($raw, true);
    if (is_array($j)) {
        return $j;
    }
    parse_str((string) $raw, $f);
    return $f ?: ($raw === '' ? null : 'raw(' . strlen($raw) . ')');
}

ob_start(function ($buf, $phase) {
    $GLOBALS['hc_out'] .= $buf;
    if ($phase & PHP_OUTPUT_HANDLER_FINAL) {
        if (!is_dir(dirname(HC_LOG)) || (file_exists(HC_LOG) && filesize(HC_LOG) > 30 * 1024 * 1024)) {
            return $buf;
        }
        $path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
        $mask = hc_sensitive($path);
        $headers = [];
        foreach ($_SERVER as $k => $val) {
            if (strpos($k, 'HTTP_') === 0 && !preg_match('#COOKIE|AUTHORIZATION|TOKEN#', $k)) {
                $headers[$k] = mb_substr((string) $val, 0, 200);
            } elseif (strpos($k, 'HTTP_') === 0) {
                $headers[$k] = 'str(' . strlen((string) $val) . ')';
            }
        }
        $q = [];
        parse_str((string) parse_url($_SERVER['REQUEST_URI'], PHP_URL_QUERY), $q);
        $row = [
            't'        => gmdate('c'),
            'method'   => $_SERVER['REQUEST_METHOD'] ?? '',
            'path'     => $path,
            'query'    => hc_clean($q, $mask),
            'headers'  => $headers,
            'body'     => hc_clean(hc_parse($GLOBALS['hc_body']), $mask),
            'status'   => http_response_code(),
            'response' => hc_clean(hc_parse($GLOBALS['hc_out']), $mask),
        ];
        @file_put_contents(HC_LOG, wp_json_encode($row, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . "\n", FILE_APPEND | LOCK_EX);
    }
    return $buf;
}, 0, PHP_OUTPUT_HANDLER_STDFLAGS);
