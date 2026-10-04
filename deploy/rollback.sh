#!/usr/bin/env bash
# بازگشت irancarpet.net به وردپرس (اگر بعد از جایگزینی مشکلی پیش آمد)
#   bash deploy/rollback.sh [پوشهٔ پشتیبان]
set -euo pipefail
APP=/var/www/irancarpet-django
BK="${1:-$(cat /root/irancarpet-last-cutover 2>/dev/null || true)}"
[ -n "$BK" ] && [ -f "$BK/moved.txt" ] || { echo "پوشهٔ پشتیبان پیدا نشد. نمونه: bash deploy/rollback.sh /root/irancarpet-cutover-..."; exit 1; }

echo "== بازگرداندن پیکربندی nginx وردپرس از $BK"
rm -f /etc/nginx/sites-enabled/irancarpet.net-django
while read -r f; do
  [ -n "$f" ] && mv "$BK/nginx/enabled-$(basename "$f")" "$f" && echo "   ✔ $f"
done < "$BK/moved.txt"
nginx -t
systemctl reload nginx

echo "== خاموش کردن همگام‌سازی فرش پلاس جنگو (افزونهٔ وردپرس دوباره کار می‌کند)"
systemctl disable --now irancarpet-farshplus.timer >/dev/null 2>&1 || true
[ -f "$BK/crontab.txt" ] && crontab "$BK/crontab.txt" && echo "   ✔ کرون قبلی برگشت"

echo "== حالت آزمایشی برای نسخهٔ جنگو"
cd "$APP"
sed -i 's/^STAGING=.*/STAGING=True/' .env
systemctl restart irancarpet

echo
echo "========== irancarpet.net دوباره وردپرس است =========="
echo "سفارش‌هایی که در این فاصله در جنگو ثبت شده‌اند در پنل جنگو (new.irancarpet.net/panel/) می‌مانند."
