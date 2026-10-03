#!/usr/bin/env bash
# نصب خودکار نسخهٔ آزمایشی (استیجینگ) ایران کارپت روی سرور
# اجرا (با کاربر root):   bash deploy/setup_staging.sh
# قابل اجرای دوباره است؛ رمزهای ساخته‌شده در .env می‌مانند.
set -euo pipefail

APP=/var/www/irancarpet-django
WP_DB=irancarpet_shop
UPLOADS=/var/www/irancarpet/public_html/wp-content/uploads
DOMAIN=new.irancarpet.net

cd "$APP"
step() { echo; echo "========== $1 =========="; }

step "۱/۸ نصب پیش‌نیازها"
apt-get update -qq
apt-get install -y -qq python3-venv python3-dev apache2-utils openssl >/dev/null
command -v certbot >/dev/null || apt-get install -y -qq certbot python3-certbot-nginx >/dev/null
mysql --version

step "۲/۸ محیط پایتون و کتابخانه‌ها"
[ -d venv ] || python3 -m venv venv
venv/bin/pip install -q --upgrade pip
venv/bin/pip install -q -r requirements.txt

step "۳/۸ دیتابیس و فایل تنظیمات"
if [ ! -f .env ]; then
  DBPASS=$(openssl rand -hex 16)
  RDPASS=$(openssl rand -hex 16)
  SECRET=$(openssl rand -hex 32)
  mysql -e "CREATE DATABASE IF NOT EXISTS ic_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
  for H in localhost 127.0.0.1; do
    mysql -e "CREATE USER IF NOT EXISTS 'ic_django'@'$H' IDENTIFIED BY '$DBPASS';"
    mysql -e "ALTER USER 'ic_django'@'$H' IDENTIFIED BY '$DBPASS';"
    mysql -e "GRANT ALL PRIVILEGES ON ic_django.* TO 'ic_django'@'$H';"
    mysql -e "CREATE USER IF NOT EXISTS 'ic_reader'@'$H' IDENTIFIED BY '$RDPASS';"
    mysql -e "ALTER USER 'ic_reader'@'$H' IDENTIFIED BY '$RDPASS';"
    mysql -e "GRANT SELECT ON $WP_DB.* TO 'ic_reader'@'$H';"
  done
  mysql -e "FLUSH PRIVILEGES;"
  cat > .env <<EOF
SECRET_KEY=$SECRET
DEBUG=False
STAGING=True
ALLOWED_HOSTS=$DOMAIN,irancarpet.net,www.irancarpet.net,127.0.0.1,localhost
CSRF_TRUSTED_ORIGINS=https://$DOMAIN,http://$DOMAIN,https://irancarpet.net
SITE_URL=https://irancarpet.net
DATABASE_URL=mysql://ic_django:$DBPASS@127.0.0.1:3306/ic_django
WP_DATABASE_URL=mysql://ic_reader:$RDPASS@127.0.0.1:3306/$WP_DB
MEDIA_ROOT=$UPLOADS
STATIC_ROOT=$APP/staticfiles
EOF
  echo "فایل .env ساخته شد (رمزها تصادفی هستند)."
else
  echo "فایل .env از قبل وجود دارد؛ دست نخورد."
fi
chown root:www-data .env
chmod 640 .env

step "۴/۸ ساخت جدول‌ها"
venv/bin/python manage.py migrate --noinput

step "۵/۸ انتقال داده از وردپرس (۱ تا ۳ دقیقه)"
if [ ! -f .imported ]; then
  venv/bin/python manage.py import_wp
  touch .imported
else
  echo "قبلاً ایمپورت شده است. برای تکرار: rm .imported و دوباره اجرا کنید."
fi

step "۶/۸ فایل‌های استاتیک"
venv/bin/python manage.py collectstatic --noinput -v0
chown -R root:www-data "$APP"
chmod -R g+rX "$APP"

step "۷/۸ سرویس gunicorn"
cp deploy/irancarpet.service /etc/systemd/system/irancarpet.service
systemctl daemon-reload
systemctl enable -q irancarpet
systemctl restart irancarpet
sleep 2
systemctl is-active irancarpet

step "۸/۸ nginx و SSL"
cp deploy/nginx-staging.conf /etc/nginx/sites-available/$DOMAIN
ln -sf /etc/nginx/sites-available/$DOMAIN /etc/nginx/sites-enabled/$DOMAIN
if [ ! -f /etc/nginx/.htpasswd-irancarpet ]; then
  echo "یک رمز برای ورود به نسخهٔ آزمایشی انتخاب کنید (نام کاربری: admin):"
  htpasswd -c /etc/nginx/.htpasswd-irancarpet admin
fi
nginx -t
systemctl reload nginx
certbot --nginx -d $DOMAIN --non-interactive --agree-tos --redirect --register-unsafely-without-email || \
  echo "!! گرفتن SSL ناموفق بود؛ سایت فعلاً روی http بالا است."

echo
echo "========== تمام شد =========="
echo "آدرس: https://$DOMAIN  (نام کاربری: admin)"
echo "قدم بعد: ساخت مدیر پنل با دستور:"
echo "  venv/bin/python manage.py createsuperuser"
