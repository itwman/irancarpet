#!/usr/bin/env bash
# جایگزینی وردپرس با سایت جنگو روی irancarpet.net
#
#   bash deploy/cutover.sh check   ← فقط بررسی و گزارش؛ هیچ چیزی تغییر نمی‌کند
#   bash deploy/cutover.sh go      ← اجرای جایگزینی (با پشتیبان کامل)
#   bash deploy/rollback.sh <پوشهٔ پشتیبان>  ← بازگشت به وردپرس در کمتر از یک دقیقه
set -euo pipefail

MODE="${1:-check}"
APP=/var/www/irancarpet-django
WPROOT=/var/www/irancarpet/public_html
LEGACY=/var/www/irancarpet/legacy-root
DOMAIN=irancarpet.net
NEWCONF=/etc/nginx/sites-available/irancarpet.net-django
STAMP=$(date +%Y%m%d-%H%M%S)
BK=/root/irancarpet-cutover-$STAMP

cd "$APP"
say()  { echo; echo "== $*"; }
ok()   { echo "   ✔ $*"; }
warn() { echo "   ⚠ $*"; }
die()  { echo; echo "!! $*"; exit 1; }

# ------------------------------------------------------------------ بررسی
say "۱. پیکربندی فعلی nginx برای $DOMAIN"
NAME_RX="server_name[^;]*[[:space:]](www\.)?irancarpet\.net([[:space:]]|;)"
mapfile -t FOUND < <(grep -lE "$NAME_RX" /etc/nginx/sites-enabled/* /etc/nginx/conf.d/*.conf 2>/dev/null | grep -v "irancarpet.net-django" || true)
[ ${#FOUND[@]} -gt 0 ] || die "هیچ فایل nginx با server_name irancarpet.net پیدا نشد."
for f in "${FOUND[@]}"; do ok "فایل فعال: $f → $(readlink -f "$f")"; done
REAL=$(readlink -f "${FOUND[0]}")

OTHER=$(grep -hoE "server_name[^;]*;" "${FOUND[@]}" | sed 's/server_name//; s/;//' | tr ' ' '\n' | grep -v '^$' | sort -u | grep -vE '^(www\.)?irancarpet\.net$' || true)
if [ -n "$OTHER" ]; then
  warn "این فایل‌ها دامنه‌های دیگری هم دارند: $OTHER"
  die "برای امنیت، اسکریپت متوقف شد. خروجی بالا را برای پشتیبانی بفرستید."
fi

CERT=$(grep -hE "^\s*ssl_certificate\s" "${FOUND[@]}" | head -1 | sed 's/^\s*//')
CKEY=$(grep -hE "^\s*ssl_certificate_key\s" "${FOUND[@]}" | head -1 | sed 's/^\s*//')
SSLINC=$(grep -hE "^\s*(include\s+/etc/letsencrypt/options-ssl-nginx.conf|ssl_dhparam)\s" "${FOUND[@]}" | sort -u | sed 's/^\s*//' || true)
[ -n "$CERT" ] && [ -n "$CKEY" ] || die "گواهی SSL در پیکربندی فعلی پیدا نشد."
ok "$CERT"
ok "$CKEY"
V6=""
grep -qE "listen\s+\[::\]" "${FOUND[@]}" && V6=1 && ok "IPv6 فعال است"

say "۲. فایل‌های ریشهٔ سایت قدیم که باید بمانند (تأیید گوگل، اینماد، favicon و…)"
mapfile -t KEEP < <(find "$WPROOT" -maxdepth 1 -type f \( -name '*.html' -o -name '*.htm' -o -name '*.txt' -o -name '*.ico' -o -name '*.xml' -o -name '*.kml' -o -name '*.png' -o -name '*.jpg' -o -name '*.svg' -o -name '*.webmanifest' \) \
  ! -name 'robots.txt' ! -name 'license.txt' ! -name 'readme.html' ! -name 'wp-*' ! -name '*sitemap*' 2>/dev/null | sort)
if [ ${#KEEP[@]} -gt 0 ]; then for f in "${KEEP[@]}"; do ok "$(basename "$f")"; done; else ok "فایلی نیست"; fi

say "۳. سرویس‌ها و تنظیمات سایت جنگو"
systemctl is-active --quiet irancarpet && ok "سرویس جنگو فعال است" || die "سرویس irancarpet فعال نیست."
[ -f .env ] || die "فایل .env پیدا نشد."
grep -q '^STAGING=True' .env && ok "حالت فعلی: آزمایشی (STAGING=True)" || ok "حالت فعلی: اصلی"
venv/bin/python manage.py shell -c "
from catalog.models import Product; from shop.models import Order, ShopSettings; from django.contrib.auth import get_user_model
from farshplus.models import FarshPlusSettings; from shop import config; from accounts import sms
s=ShopSettings.load(); fp=FarshPlusSettings.load()
print('   ✔ محصولات:', Product.objects.count(), '| سفارش‌ها:', Order.objects.count(), '| کاربران:', get_user_model().objects.count())
print('   ✔ مدیران پنل:', get_user_model().objects.filter(is_staff=True).count())
print('  ', '✔' if config.get('SEP_TERMINAL_ID') else '⚠', 'درگاه سامان', 'تنظیم شده' if config.get('SEP_TERMINAL_ID') else 'تنظیم نشده')
print('  ', '✔' if config.get('ZARINPAL_MERCHANT_ID') else '⚠', 'زرین‌پال', 'تنظیم شده' if config.get('ZARINPAL_MERCHANT_ID') else 'تنظیم نشده')
print('  ', '✔' if sms.configured() else '⚠', 'پیامک', 'تنظیم شده' if sms.configured() else 'تنظیم نشده (ورود فقط با رمز ممکن است)')
print('  ', '✔' if fp.api_key else '⚠', 'کلید فرش پلاس', 'موجود' if fp.api_key else 'پیدا نشد (بعد از انتقال نهایی دوباره بررسی می‌شود)')
" 2>/dev/null || warn "خواندن آمار ممکن نشد"

say "۴. کرون وردپرس"
CRON=$(crontab -l 2>/dev/null | grep -nE "irancarpet" | grep -E "wp-cron|wp cron|action-scheduler" || true)
[ -n "$CRON" ] && warn "این خط‌ها در crontab غیرفعال می‌شوند:" && echo "$CRON" || ok "کرون وردپرسی برای ایران کارپت پیدا نشد"

if [ "$MODE" != "go" ]; then
  echo
  echo "========== بررسی تمام شد؛ چیزی تغییر نکرد =========="
  echo "اگر همه‌چیز ✔ است، برای اجرای جایگزینی بزنید:  bash deploy/cutover.sh go"
  exit 0
fi

# ------------------------------------------------------------------ اجرا
echo
read -r -p "سایت اصلی irancarpet.net به نسخهٔ جنگو منتقل شود؟ بنویسید yes: " ANS
[ "$ANS" = "yes" ] || die "لغو شد."

say "۵. پشتیبان‌گیری در $BK"
mkdir -p "$BK/nginx"
: > "$BK/moved.txt"
for f in "${FOUND[@]}"; do cp -a "$(readlink -f "$f")" "$BK/nginx/"; done
cp -a .env "$BK/env.backup"
mysqldump --single-transaction ic_django | gzip > "$BK/ic_django.sql.gz" && ok "پشتیبان دیتابیس جنگو"
crontab -l > "$BK/crontab.txt" 2>/dev/null || true

say "۶. انتقال نهایی داده‌ها از وردپرس (چند دقیقه)"
venv/bin/python manage.py import_wp
ok "انتقال نهایی انجام شد"

say "۷. فایل‌های ریشهٔ سایت قدیم"
mkdir -p "$LEGACY"
for f in "${KEEP[@]}"; do cp -a "$f" "$LEGACY/"; done
chown -R root:www-data "$LEGACY"; chmod -R g+rX "$LEGACY"
ok "${#KEEP[@]} فایل در $LEGACY"

say "۸. پیکربندی nginx تازه"
L443="listen 443 ssl http2;"; L80="listen 80;"
[ -n "$V6" ] && L443="$L443
    listen [::]:443 ssl http2;" && L80="$L80
    listen [::]:80;"
cat > "$NEWCONF" <<NGINX
# irancarpet.net — سایت جنگو (ساخته‌شده با deploy/cutover.sh در $STAMP)
upstream irancarpet_django { server unix:/run/irancarpet/gunicorn.sock fail_timeout=0; }

server {
    $L443
    server_name irancarpet.net;
    $CERT
    $CKEY
$(echo "$SSLINC" | sed 's/^/    /')

    client_max_body_size 20m;
    gzip on;
    gzip_types text/css application/javascript application/json image/svg+xml text/xml application/xml;

    location /static/ {
        alias $APP/staticfiles/;
        expires 30d;
        access_log off;
    }
    location /wp-content/uploads/ {
        alias $WPROOT/wp-content/uploads/;
        expires 30d;
        access_log off;
        location ~ \.(php|phtml|phar)\$ { deny all; }
    }
    # فایل‌های قدیمی ریشه (تأیید گوگل، اینماد و…)؛ اگر نبود، جنگو جواب می‌دهد
    location ~ ^/[^/]+\.(html?|txt|ico|xml|kml|png|jpg|svg|webmanifest)\$ {
        root $LEGACY;
        try_files \$uri @django;
    }
    location / { try_files /nonexistent @django; }
    location @django {
        proxy_pass http://irancarpet_django;
        proxy_set_header Host \$host;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 90s;
    }
}
server {
    $L443
    server_name www.irancarpet.net;
    $CERT
    $CKEY
$(echo "$SSLINC" | sed 's/^/    /')
    return 301 https://irancarpet.net\$request_uri;
}
server {
    $L80
    server_name irancarpet.net www.irancarpet.net;
    location /.well-known/acme-challenge/ { root $WPROOT; }
    location / { return 301 https://irancarpet.net\$request_uri; }
}
NGINX
for f in "${FOUND[@]}"; do
  mv "$f" "$BK/nginx/enabled-$(basename "$f")"
  echo "$f" >> "$BK/moved.txt"
done
ln -sf "$NEWCONF" /etc/nginx/sites-enabled/irancarpet.net-django
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/irancarpet.net-django
  while read -r f; do mv "$BK/nginx/enabled-$(basename "$f")" "$f"; done < "$BK/moved.txt"
  die "آزمون nginx خطا داد؛ همه‌چیز به حالت قبل برگشت. خروجی بالا را بفرستید."
fi

say "۹. حالت اصلی سایت جنگو"
sed -i 's/^STAGING=.*/STAGING=False/' .env
grep -q '^STAGING=' .env || echo "STAGING=False" >> .env
grep -q '^ALLOWED_HOSTS=.*www.irancarpet.net' .env || sed -i 's/^ALLOWED_HOSTS=/ALLOWED_HOSTS=www.irancarpet.net,/' .env
grep -q '^CSRF_TRUSTED_ORIGINS=.*https://www.irancarpet.net' .env || sed -i 's#^CSRF_TRUSTED_ORIGINS=#CSRF_TRUSTED_ORIGINS=https://www.irancarpet.net,#' .env
sed -i 's/^PAYMENT_FAKE=.*/PAYMENT_FAKE=False/' .env
systemctl restart irancarpet
sleep 2
systemctl reload nginx
ok "nginx و سرویس جنگو دوباره راه‌اندازی شدند"

say "۱۰. تایمرهای فرش پلاس و نگهداری"
cp deploy/irancarpet-farshplus.service deploy/irancarpet-farshplus.timer deploy/irancarpet-daily.service deploy/irancarpet-daily.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now irancarpet-farshplus.timer irancarpet-daily.timer >/dev/null
ok "همگام‌سازی فرش پلاس هر ۵ دقیقه"
if [ -n "$CRON" ]; then
  crontab -l | sed -E '/irancarpet/{/wp-cron|wp cron|action-scheduler/s/^/# disabled by cutover: /}' | crontab -
  ok "کرون وردپرس غیرفعال شد"
fi

say "۱۱. آزمون نهایی"
code() { curl -s -o /dev/null -w "%{http_code}" --resolve "$1:443:127.0.0.1" "https://$1$2"; }
P=$(venv/bin/python manage.py shell -c "from catalog.models import Product; print(Product.objects.published().first().get_absolute_url())" 2>/dev/null | tail -1)
for t in "irancarpet.net /" "irancarpet.net $P" "irancarpet.net /sitemap_index.xml" "irancarpet.net /store/" "irancarpet.net /wp-admin/" "www.irancarpet.net /"; do
  set -- $t; echo "   $(code "$1" "$2")  https://$1$2"
done
curl -s -I --resolve irancarpet.net:443:127.0.0.1 https://irancarpet.net/ | grep -qi "x-robots-tag" && warn "هدر noindex هنوز هست!" || ok "سایت قابل ایندکس است"

echo "$BK" > /root/irancarpet-last-cutover
echo
echo "========== تمام شد =========="
echo "سایت اصلی اکنون جنگو است. پشتیبان: $BK"
echo "بازگشت فوری به وردپرس (در صورت مشکل):  bash deploy/rollback.sh $BK"
