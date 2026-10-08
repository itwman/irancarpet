#!/usr/bin/env bash
# راه‌اندازی دامنهٔ پیوند کوتاه همکاران (یک بار، بعد از تنظیم DNS)
# اجرا (با کاربر root):   bash deploy/setup_crpt.sh
set -euo pipefail
cd /var/www/irancarpet-django
DOM=${1:-crpt.it}
IP=$(curl -s4 --max-time 10 https://api.ipify.org || hostname -I | awk '{print $1}')
echo "== IP این سرور: $IP"
DNS=$(getent ahostsv4 "$DOM" | awk '{print $1; exit}' || true)
echo "== IP دامنهٔ $DOM در DNS: ${DNS:-پیدا نشد}"
if [ "$DNS" != "$IP" ]; then
  echo "!! رکورد A دامنهٔ $DOM هنوز به این سرور ($IP) اشاره نمی‌کند. چند دقیقه بعد دوباره اجرا کنید."
  exit 1
fi
echo "== تنظیم nginx"
sed "s/crpt\.it/$DOM/g" deploy/nginx-crpt.conf > /etc/nginx/sites-available/crpt
ln -sf /etc/nginx/sites-available/crpt /etc/nginx/sites-enabled/crpt
mkdir -p /var/www/html
nginx -t
systemctl reload nginx
echo "== گواهی SSL (Let's Encrypt)"
command -v certbot >/dev/null || { apt-get update -qq; apt-get install -y -qq certbot python3-certbot-nginx; }
WWW=""
if getent ahostsv4 "www.$DOM" >/dev/null; then WWW="-d www.$DOM"; fi
certbot --nginx -d "$DOM" $WWW --redirect --non-interactive --agree-tos --register-unsafely-without-email --keep-until-expiring
nginx -t
systemctl reload nginx
echo "== آزمایش"
curl -sI "https://$DOM/" | head -3 || true
echo "تمام شد. پیوند نمونه: https://$DOM/<کد همکار>"
