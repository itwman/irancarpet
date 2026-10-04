#!/usr/bin/env bash
# به‌روزرسانی سایت جنگو روی سرور بعد از هر تغییر در گیت‌هاب
# اجرا (با کاربر root):   bash deploy/update.sh
set -euo pipefail
cd /var/www/irancarpet-django
echo "== دریافت آخرین نسخه"
git pull --ff-only
echo "== کتابخانه‌ها"
venv/bin/pip install -q --no-index --find-links /tmp/ic-wheels -r requirements.txt 2>/dev/null || venv/bin/pip install -q --timeout 60 -r requirements.txt || true
echo "== جدول‌ها"
venv/bin/python manage.py migrate --noinput
echo "== فایل‌های استاتیک"
venv/bin/python manage.py collectstatic --noinput -v0
chown -R root:www-data . && chmod -R g+rX .
echo "== راه‌اندازی دوباره"
systemctl restart irancarpet
sleep 2
systemctl is-active irancarpet
echo "تمام شد."
