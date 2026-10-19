#!/usr/bin/env bash
# پل موقت اپلیکیشن قدیمی: مسیرهای /wp-json/wp_hamrah_app/ دوباره به وردپرس می‌روند تا اپ کار کند
# و درخواست‌ها برای ساختن نسخهٔ سازگار در جنگو ثبت می‌شوند.
#   bash deploy/hamrah_bridge.sh on | off | status | dump
set -euo pipefail
WPROOT=/var/www/irancarpet/public_html
CONF=/etc/nginx/sites-available/irancarpet.net-django
SNIP=/etc/nginx/snippets/hamrah-bridge.conf
MU=$WPROOT/wp-content/mu-plugins/hamrah-capture.php
HERE="$(cd "$(dirname "$0")" && pwd)"

ensure_include() {
  grep -q "snippets/hamrah-bridge.conf" "$CONF" && return
  cp "$CONF" "$CONF.bak-hamrah"
  # فقط در اولین server (سایت اصلی ۴۴۳)
  sed -i '0,/client_max_body_size 20m;/s//client_max_body_size 20m;\n    include snippets\/hamrah-bridge.conf;/' "$CONF"
}

case "${1:-status}" in
  on)
    SOCK=$(ls /run/php/php*-fpm.sock 2>/dev/null | head -1 || true)
    [ -n "$SOCK" ] || { echo "!! سرویس PHP-FPM پیدا نشد (ls /run/php)."; exit 1; }
    mkdir -p /etc/nginx/snippets /var/log/hamrah "$WPROOT/wp-content/mu-plugins"
    chown www-data:www-data /var/log/hamrah
    cat > "$SNIP" <<NG
# پل موقت اپ قدیمی → وردپرس (deploy/hamrah_bridge.sh)
location ^~ /wp-json/wp_hamrah_app/ {
    root $WPROOT;
    include fastcgi_params;
    fastcgi_param SCRIPT_FILENAME \$document_root/index.php;
    fastcgi_param SCRIPT_NAME /index.php;
    fastcgi_param HTTPS on;
    fastcgi_read_timeout 60s;
    fastcgi_pass unix:$SOCK;
}
NG
    cp "$HERE/hamrah/hamrah-capture.php" "$MU"
    chown www-data:www-data "$MU"
    ensure_include
    nginx -t && systemctl reload nginx
    sleep 1
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST https://irancarpet.net/wp-json/wp_hamrah_app/splash || true)
    echo "✔ پل روشن شد (PHP: $SOCK) — پاسخ splash: $CODE"
    ;;
  off)
    echo "# پل خاموش است" > "$SNIP"
    rm -f "$MU"
    nginx -t && systemctl reload nginx
    echo "✔ پل خاموش شد؛ ثبت درخواست‌ها هم متوقف شد."
    ;;
  dump)
    [ -f /var/log/hamrah/capture.jsonl ] || { echo "هنوز درخواستی ثبت نشده."; exit 0; }
    cp /var/log/hamrah/capture.jsonl /root/hamrah-capture.jsonl
    echo "تعداد درخواست‌های ثبت‌شده به تفکیک مسیر:"
    grep -o '"path":"[^"]*"' /root/hamrah-capture.jsonl | sort | uniq -c | sort -rn
    echo "فایل: /root/hamrah-capture.jsonl"
    ;;
  *)
    grep -q "location" "$SNIP" 2>/dev/null && echo "پل: روشن" || echo "پل: خاموش"
    [ -f /var/log/hamrah/capture.jsonl ] && wc -l /var/log/hamrah/capture.jsonl || true
    ;;
esac
