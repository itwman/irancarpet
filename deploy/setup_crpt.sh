#!/usr/bin/env bash
# راه‌اندازی دامنهٔ پیوند کوتاه همکاران (یک بار، بعد از تنظیم DNS)
# اجرا (با کاربر root):   bash deploy/setup_crpt.sh
set -euo pipefail
cd /var/www/irancarpet-django
DOM=${1:-crpt.ir}
echo "== IP دامنهٔ $DOM در DNS: $(getent ahostsv4 "$DOM" | awk '{print $1; exit}' || echo 'پیدا نشد')"
echo "== IPهای این سرور: $(hostname -I)"

echo "== تنظیم nginx"
sed "s/crpt\.ir/$DOM/g" deploy/nginx-crpt.conf > /etc/nginx/sites-available/crpt
ln -sf /etc/nginx/sites-available/crpt /etc/nginx/sites-enabled/crpt
mkdir -p /var/www/html/.well-known/acme-challenge
nginx -t
systemctl reload nginx

echo "== آزمایش اینکه دامنه واقعاً به همین سرور می‌رسد"
TOKEN=$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')
echo "$TOKEN" > "/var/www/html/.well-known/acme-challenge/ic-$TOKEN"
GOT=$(curl -s --max-time 15 "http://$DOM/.well-known/acme-challenge/ic-$TOKEN" || true)
rm -f "/var/www/html/.well-known/acme-challenge/ic-$TOKEN"
if [ "$GOT" != "$TOKEN" ]; then
  echo "!! http://$DOM به nginx همین سرور نمی‌رسد. رکورد A دامنه را بررسی کنید و چند دقیقه بعد دوباره اجرا کنید."
  exit 1
fi
echo "   درست است."

echo "== گواهی SSL (Let's Encrypt)"
command -v certbot >/dev/null || { apt-get update -qq; apt-get install -y -qq certbot python3-certbot-nginx; }
WWW=""
A1=$(getent ahostsv4 "$DOM" | awk '{print $1; exit}' || true)
A2=$(getent ahostsv4 "www.$DOM" | awk '{print $1; exit}' || true)
if [ -n "$A2" ] && [ "$A1" = "$A2" ]; then WWW="-d www.$DOM"; fi
certbot --nginx -d "$DOM" $WWW --redirect --non-interactive --agree-tos --register-unsafely-without-email --keep-until-expiring
nginx -t
systemctl reload nginx

echo "== آزمایش نهایی"
curl -sI "https://$DOM/" | head -3 || true
echo "تمام شد. پیوند نمونه: https://$DOM/<کد همکار>"
