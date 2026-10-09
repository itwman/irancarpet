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
venv/bin/python manage.py createcachetable
echo "== اجازهٔ نوشتن در پوشهٔ تصاویر (برای آپلود از پنل)"
UP=$(grep '^MEDIA_ROOT=' .env | cut -d= -f2-)
if [ -n "$UP" ] && [ -d "$UP" ]; then
  M="$UP/$(date +%Y)/$(date +%m)"
  mkdir -p "$M"
  mkdir -p "$UP/app-thumbs" "$UP/reviews/$(date +%Y)/$(date +%m)"
  for D in "$UP" "$UP/$(date +%Y)" "$M" "$UP/app-thumbs" "$UP/reviews" "$UP/reviews/$(date +%Y)" "$UP/reviews/$(date +%Y)/$(date +%m)"; do chgrp www-data "$D"; chmod g+ws "$D"; done
fi
echo "== پوشهٔ خصوصی مدارک مشتری (تصویر چک)؛ فقط برای برنامه، نه عموم"
mkdir -p private
chgrp www-data private && chmod 2770 private
echo "== فایل‌های استاتیک"
venv/bin/python manage.py collectstatic --noinput -v0
chown -R root:www-data . && chmod -R g+rX .
chmod -R g+w private && chmod -R o-rwx private
echo "== کارهای دوره‌ای (هر ۱۰ دقیقه)"
for U in irancarpet-jobs.service irancarpet-jobs.timer; do
  cmp -s "deploy/$U" "/etc/systemd/system/$U" || cp "deploy/$U" "/etc/systemd/system/$U"
done
systemctl daemon-reload
systemctl enable --now irancarpet-jobs.timer >/dev/null
echo "== متن‌های بازنویسی‌شدهٔ مقاله‌ها (content/rewrites)"
runuser -u www-data -- venv/bin/python manage.py rewrites || true
echo "== صفحه‌های فرود"
runuser -u www-data -- venv/bin/python manage.py run_jobs --landing || true
echo "== راه‌اندازی دوباره"
systemctl restart irancarpet
sleep 2
systemctl is-active irancarpet
echo "تمام شد."
