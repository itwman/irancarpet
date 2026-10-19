#!/usr/bin/env bash
# سوییچ دامنهٔ اصلی سایت دوم (مثلاً farshestan.ir) به نسخهٔ جنگو؛ بعد از اینکه DNS دامنه به این سرور اشاره کرد
# اجرا (با کاربر root):   bash /var/www/irancarpet-django/deploy/switch_site.sh farshestan
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1090
source "$SRC_DIR/deploy/sites/${1:?نام سایت}.conf"
APP=/var/www/$NAME-django
MEDIA=/var/www/$NAME-media/uploads
cd "$APP"
for H in "$DOMAIN" "www.$DOMAIN"; do
  R=$(getent hosts "$H" | awk '{print $1}' | head -1 || true)
  if [ "$R" != "195.88.208.168" ]; then echo "!! DNS دامنهٔ $H هنوز به این سرور نیست (الان: ${R:-هیچ}). اول رکورد A را عوض کنید."; exit 1; fi
done
sed -e "s#__DOMAIN__#$DOMAIN#g" -e "s#__APP__#$APP#g" -e "s#__MEDIA__#$MEDIA#g" -e "s#__NAME__#$NAME#g" \
    deploy/nginx-site-production.conf > "/etc/nginx/sites-available/$DOMAIN"
ln -sf "/etc/nginx/sites-available/$DOMAIN" "/etc/nginx/sites-enabled/$DOMAIN"
nginx -t && systemctl reload nginx
certbot --nginx -d "$DOMAIN" -d "www.$DOMAIN" --non-interactive --agree-tos --redirect --register-unsafely-without-email
sed -i 's/^STAGING=True/STAGING=False/' .env
systemctl restart "$NAME"
sleep 2; systemctl is-active "$NAME"
curl -s -o /dev/null -w "https://$DOMAIN/ → %{http_code}\n" "https://$DOMAIN/"
echo "سوییچ انجام شد. نسخهٔ آزمایشی $STAGING_DOMAIN همچنان رمزدار می‌ماند."
