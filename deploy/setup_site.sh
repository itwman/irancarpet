#!/usr/bin/env bash
# نصب یک سایت دیگر روی همین کد (مثلاً فرشستان) کنار ایران کارپت، روی همان سرور
# اجرا (با کاربر root):   bash /var/www/irancarpet-django/deploy/setup_site.sh farshestan
# تنظیمات هر سایت در deploy/sites/<نام>.conf است. اجرای دوباره بی‌خطر است؛ رمزها و ایمپورت تکرار نمی‌شوند.
# هیچ تنظیم سراسری سرور عوض نمی‌شود: فقط پوشه، دیتابیس، سرویس و بلاک nginx خود همین سایت.
set -euo pipefail
NAME_ARG="${1:?نام سایت را بدهید؛ مثلاً: bash setup_site.sh farshestan}"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$SRC_DIR/deploy/sites/$NAME_ARG.conf"
[ -f "$CONF" ] || { echo "!! فایل $CONF نیست"; exit 1; }
# shellcheck disable=SC1090
source "$CONF"
APP=/var/www/$NAME-django
MEDIA=/var/www/$NAME-media/uploads
SERVER_IP=$(hostname -I | awk '{print $1}')
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a NEEDRESTART_SUSPEND=1
step() { echo; echo "========== $1 =========="; }

step "۱/۹ دریافت کد"
if [ ! -d "$APP/.git" ]; then
  git clone -q "$(git -C "$SRC_DIR" remote get-url origin)" "$APP"
else
  git -C "$APP" pull -q --ff-only
fi
cd "$APP"
for p in python3-venv apache2-utils openssl; do dpkg -s "$p" >/dev/null 2>&1 || { apt-get update -qq; apt-get install -y -qq "$p"; }; done

step "۲/۹ محیط پایتون و کتابخانه‌ها"
[ -d venv ] || python3 -m venv venv
installed=0
rm -rf /tmp/ic-wheels
if git clone -q --depth 1 -b wheels "$(git remote get-url origin)" /tmp/ic-wheels 2>/dev/null; then
  venv/bin/pip install -q --no-index --find-links /tmp/ic-wheels -r requirements.txt && installed=1 || true
fi
for IDX in https://pypi.org/simple https://mirror-pypi.runflare.com/simple https://package-mirror.liara.ir/repository/pypi/simple; do
  [ $installed = 1 ] && break
  venv/bin/pip install -q --timeout 60 --retries 2 -i "$IDX" -r requirements.txt && installed=1 || true
done
[ $installed = 1 ] || { echo "!! نصب کتابخانه‌ها ناموفق بود"; exit 1; }

step "۳/۹ عکس‌ها (همان مسیر /wp-content/uploads/ قبلی)"
mkdir -p "$MEDIA"
if [ -d "$MEDIA_SRC" ] && [ -z "$(ls -A "$MEDIA" 2>/dev/null)" ]; then
  echo "انتقال عکس‌ها از $MEDIA_SRC ..."
  mv "$MEDIA_SRC"/* "$MEDIA"/
fi
find "$MEDIA" -type f \( -iname '*.php' -o -iname '*.phtml' -o -iname '*.phar' \) -delete
chgrp -R www-data "/var/www/$NAME-media" && chmod -R g+rwX "/var/www/$NAME-media"
find "/var/www/$NAME-media" -type d -exec chmod g+s {} +
echo "$(find "$MEDIA" -type f | wc -l) فایل عکس"

step "۴/۹ دیتابیس وردپرس قبلی (فقط خواندنی، برای ایمپورت)"
if ! mysql -e "USE \`$WP_DB\`" 2>/dev/null; then
  [ -f "$WP_SQL" ] || { echo "!! فایل $WP_SQL نیست؛ دیتابیس وردپرس را آنجا بگذارید"; exit 1; }
  mysql -e "CREATE DATABASE \`$WP_DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  mysql "$WP_DB" < "$WP_SQL"
  echo "دیتابیس $WP_DB ساخته شد."
else
  echo "دیتابیس $WP_DB از قبل هست."
fi

step "۵/۹ دیتابیس سایت و فایل تنظیمات (خودکار)"
DB=${NAME}_django
if [ ! -f .env ]; then
  DBPASS=$(openssl rand -hex 16); RDPASS=$(openssl rand -hex 16); SECRET=$(openssl rand -hex 32)
  mysql -e "CREATE DATABASE IF NOT EXISTS \`$DB\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  for H in localhost 127.0.0.1; do
    mysql -e "CREATE USER IF NOT EXISTS '$DB'@'$H' IDENTIFIED BY '$DBPASS'; ALTER USER '$DB'@'$H' IDENTIFIED BY '$DBPASS'; GRANT ALL PRIVILEGES ON \`$DB\`.* TO '$DB'@'$H';"
    mysql -e "CREATE USER IF NOT EXISTS '${NAME}_reader'@'$H' IDENTIFIED BY '$RDPASS'; ALTER USER '${NAME}_reader'@'$H' IDENTIFIED BY '$RDPASS'; GRANT SELECT ON \`$WP_DB\`.* TO '${NAME}_reader'@'$H';"
  done
  mysql -e "FLUSH PRIVILEGES;"
  cat > .env <<EOF
# این فایل را اسکریپت نصب ساخته؛ دستی ویرایش نکنید. همهٔ کلیدها و اتصال‌ها در پنل سایت تنظیم می‌شوند.
SECRET_KEY=$SECRET
DEBUG=False
STAGING=True
SITE_URL=https://$DOMAIN
SITE_NAME=$BRAND
SITE_THEME=$THEME
ALLOWED_HOSTS=$DOMAIN,www.$DOMAIN,$STAGING_DOMAIN,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN,https://$STAGING_DOMAIN
DATABASE_URL=mysql://$DB:$DBPASS@127.0.0.1:3306/$DB
WP_DATABASE_URL=mysql://${NAME}_reader:$RDPASS@127.0.0.1:3306/$WP_DB
MEDIA_ROOT=$MEDIA
STATIC_ROOT=$APP/staticfiles
PRIVATE_ROOT=$APP/private
EOF
  echo "فایل .env با رمزهای تصادفی ساخته شد."
fi
chown root:www-data .env && chmod 640 .env
mkdir -p private/cache && chgrp -R www-data private && chmod -R 2770 private

step "۶/۹ جدول‌ها، ایمپورت و تنظیمات برند"
venv/bin/python manage.py migrate --noinput
if [ ! -f .imported ]; then
  venv/bin/python manage.py import_wp --prefix "$WP_PREFIX"
  touch .imported
else
  echo "قبلاً ایمپورت شده؛ برای تکرار: rm $APP/.imported"
fi
if [ ! -f .profiled ]; then  # فقط بار اول؛ بعد از آن تنظیمات از پنل عوض می‌شود
  # shellcheck disable=SC2086
  venv/bin/python manage.py site_profile --brand "$BRAND" --off $FEATURES_OFF
  touch .profiled
fi
if [ ! -f .admin ]; then
  PANELPASS=$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-14)
  venv/bin/python manage.py shell -c "
from django.contrib.auth.models import User
u, _ = User.objects.get_or_create(username='nazeri', defaults={'email': ''})
u.is_staff = u.is_superuser = True
u.set_password('$PANELPASS'); u.save()"
  echo "nazeri  $PANELPASS" > .admin && chmod 600 .admin
fi

step "۷/۹ فایل‌های استاتیک"
venv/bin/python manage.py collectstatic --noinput -v0
chown -R root:www-data "$APP" && chmod -R g+rX "$APP"
chmod -R g+rw private && chmod -R o-rwx private

step "۸/۹ سرویس‌ها"
for U in irancarpet.service irancarpet-jobs.service irancarpet-jobs.timer irancarpet-daily.service irancarpet-daily.timer; do
  T=${U/irancarpet/$NAME}
  sed -e "s#/var/www/irancarpet-django#$APP#g" -e "s#/run/irancarpet/#/run/$NAME/#g" -e "s#RuntimeDirectory=irancarpet#RuntimeDirectory=$NAME#" \
      -e "s#--workers 3#--workers ${WORKERS:-2}#" -e "s#IranCarpet#$NAME#g" "deploy/$U" > "/etc/systemd/system/$T"
done
systemctl daemon-reload
systemctl enable -q "$NAME" "$NAME-jobs.timer" "$NAME-daily.timer"
systemctl restart "$NAME"
systemctl start "$NAME-jobs.timer" "$NAME-daily.timer"
sleep 2; systemctl is-active "$NAME"

step "۹/۹ nginx و SSL نسخهٔ آزمایشی ($STAGING_DOMAIN)"
STAGEPASS_FILE=/etc/nginx/.htpasswd-$NAME
if [ ! -f "$STAGEPASS_FILE" ]; then
  STAGEPASS=$(openssl rand -base64 9 | tr -d '/+=' | cut -c1-10)
  htpasswd -bc "$STAGEPASS_FILE" admin "$STAGEPASS" >/dev/null
  echo "admin  $STAGEPASS" > "$APP/.staging" && chmod 600 "$APP/.staging"
fi
sed -e "s#__DOMAIN__#$STAGING_DOMAIN#g" -e "s#__APP__#$APP#g" -e "s#__MEDIA__#$MEDIA#g" -e "s#__NAME__#$NAME#g" \
    deploy/nginx-site-staging.conf > "/etc/nginx/sites-available/$STAGING_DOMAIN"
ln -sf "/etc/nginx/sites-available/$STAGING_DOMAIN" "/etc/nginx/sites-enabled/$STAGING_DOMAIN"
nginx -t && systemctl reload nginx
RESOLVED=$(getent hosts "$STAGING_DOMAIN" | awk '{print $1}' | head -1 || true)
if [ "$RESOLVED" = "$SERVER_IP" ] || [ "$RESOLVED" = "195.88.208.168" ]; then
  certbot --nginx -d "$STAGING_DOMAIN" --non-interactive --agree-tos --redirect --register-unsafely-without-email || \
    echo "!! گرفتن SSL ناموفق بود؛ نسخهٔ آزمایشی فعلاً روی http است."
else
  echo "!! DNS دامنهٔ $STAGING_DOMAIN هنوز به این سرور ($SERVER_IP) اشاره نمی‌کند (الان: ${RESOLVED:-هیچ})."
  echo "   رکورد A را بسازید و همین اسکریپت را دوباره اجرا کنید تا SSL گرفته شود."
fi

echo
echo "========== تمام شد =========="
echo "نسخهٔ آزمایشی: http(s)://$STAGING_DOMAIN"
echo "رمز ورود به نسخهٔ آزمایشی (پنجرهٔ مرورگر):  $(cat "$APP/.staging" 2>/dev/null)"
echo "ورود به پنل: https://$STAGING_DOMAIN/panel/  ←  $(cat "$APP/.admin" 2>/dev/null)"
echo "بعد از ورود، رمز پنل را از «حساب کاربری» عوض کنید."
