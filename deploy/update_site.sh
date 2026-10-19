#!/usr/bin/env bash
# به‌روزرسانی سایت دوم (مثلاً فرشستان) با آخرین کد گیت‌هاب — update.sh ایران کارپت خودش این را صدا می‌زند
# اجرا (با کاربر root):   bash /var/www/irancarpet-django/deploy/update_site.sh farshestan
set -euo pipefail
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1090
source "$SRC_DIR/deploy/sites/${1:?نام سایت}.conf"
APP=/var/www/$NAME-django
[ -d "$APP/.git" ] || { echo "$NAME نصب نشده است؛ اول setup_site.sh"; exit 0; }
cd "$APP"
echo "== $NAME: دریافت آخرین نسخه"
git pull -q --ff-only
venv/bin/pip install -q --no-index --find-links /tmp/ic-wheels -r requirements.txt 2>/dev/null || venv/bin/pip install -q --timeout 60 -r requirements.txt || true
mkdir -p private/cache && chgrp -R www-data private && chmod 2770 private private/cache
venv/bin/python manage.py migrate --noinput
venv/bin/python manage.py collectstatic --noinput -v0
chown -R root:www-data . && chmod -R g+rX . && chmod -R g+rw private && chmod -R o-rwx private
venv/bin/python manage.py check_theme || true
systemctl restart "$NAME"
sleep 2; systemctl is-active "$NAME"
