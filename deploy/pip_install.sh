#!/usr/bin/env bash
# نصب کتابخانه‌های پایتون فقط وقتی requirements.txt عوض شده باشد، اول از میرورهای داخلی (سرور ایران به PyPI کند است)
# استفاده:  bash deploy/pip_install.sh /var/www/irancarpet-django
set -uo pipefail
APP="${1:-$(pwd)}"
cd "$APP"
HASH=$(sha256sum requirements.txt | cut -d' ' -f1)
if [ "$(cat venv/.req-hash 2>/dev/null)" = "$HASH" ] && venv/bin/pip check >/dev/null 2>&1; then
  echo "کتابخانه‌ها تغییری نکرده‌اند؛ نصب لازم نیست."
  exit 0
fi
try() { echo "تلاش: $1"; venv/bin/pip install -q --disable-pip-version-check --timeout 15 --retries 1 "${@:2}" -r requirements.txt; }
ok=0
# ۱) بسته‌های آماده در شاخهٔ wheels گیت‌هاب (اگر هست)
if [ ! -d /tmp/ic-wheels ]; then git clone -q --depth 1 -b wheels "$(git remote get-url origin)" /tmp/ic-wheels 2>/dev/null || true; fi
[ -d /tmp/ic-wheels ] && try "بسته‌های آماده" --no-index --find-links /tmp/ic-wheels && ok=1
# ۲) میرورهای داخلی، ۳) خود PyPI
for IDX in https://package-mirror.liara.ir/repository/pypi/simple https://pypi.org/simple; do  # رانفلر پولی شده (402)
  [ $ok = 1 ] && break
  try "$IDX" -i "$IDX" && ok=1
done
if [ $ok = 1 ]; then
  echo "$HASH" > venv/.req-hash
  echo "کتابخانه‌ها نصب شدند."
else
  echo "!! نصب کتابخانه‌ها ناموفق بود؛ سایت با کتابخانه‌های قبلی ادامه می‌دهد. بعداً دوباره اجرا کنید."
fi
exit 0
