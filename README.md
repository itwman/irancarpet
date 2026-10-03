# ایران کارپت — نسخهٔ جنگو

این پروژه سایت فروشگاهی [irancarpet.net](https://irancarpet.net) را از وردپرس/ووکامرس به جنگو منتقل می‌کند. **همهٔ آدرس‌ها، عنوان‌ها و متای سئو دقیقاً حفظ می‌شوند.**

## ساختار

| اپ | کار |
|---|---|
| `pricing` | قیمت‌گذاری آلبومی، نسخهٔ جنگوی افزونهٔ **ICSD Price Manager v2** (آلبوم، سایز، پرتی، markup، حمل و گرد کردن) |
| `catalog` | محصول، تنوع (سایز)، دسته، برچسب، برند، ویژگی‌ها، نظرات |
| `blog` | مقاله، برگه، دسته و برچسب مقاله، دیدگاه، پرسش‌های متداول |
| `seo` | ریدایرکت‌ها، گزارش ۴۰۴، سایت‌مپ با نام‌های Rank Math، بررسی‌کنندهٔ آدرس‌ها |
| `core` | رسانه (مسیر `/wp-content/uploads/` حفظ می‌شود)، تنظیمات سایت، ایمپورت وردپرس، ورود با رمز قدیمی وردپرس |

### فرمول قیمت (عیناً مطابق افزونه)
```
نرخ هر متر مربع = قیمت پایهٔ آلبوم ÷ مساحت سایز پایه
قیمت خرید سایز  = نرخ × مساحت (+ پرتی، فقط ۹ متری مستطیل)
قیمت نهایی      = ROUND_UP_100K( قیمت خرید × ۱٫۱۵ + ۵۰۰٬۰۰۰ )
```
با تغییر قیمت پایهٔ یک آلبوم در پنل، قیمت همهٔ محصولات آن آلبوم خودکار بازمحاسبه می‌شود. تست‌ها در `pricing/tests.py` همان مثال‌های README افزونه را بررسی می‌کنند.

### آدرس‌ها
| نوع | آدرس |
|---|---|
| محصول | `/product/<نامک>/` |
| دسته | `/product-category/<والد>/<فرزند>/` و `/page/N/` |
| برچسب / برند | `/product-tag/<نامک>/` ، `/brand/<نامک>/` |
| آرشیو ویژگی | `/reeds-per-meter/1200/` ، `/picks-per-meter/3600/` |
| مقاله / برگه | `/<نامک>/` |
| دسته / برچسب مقاله | `/category/<نامک>/` ، `/tag/<نامک>/` |
| فروشگاه | `/store/` |
| سایت‌مپ | `/sitemap_index.xml` ، `/product-sitemap1.xml` و... |
| پنل مدیریت | `/panel/` |

آدرس‌های قدیمی (`?p=123`، `/1396/09/21/slug/`، نامک‌های قدیمی، ریدایرکت‌های Rank Math، برندهای تکراری) با ۳۰۱ به آدرس درست می‌روند. `wp-login.php`، `wp-admin` و `xmlrpc.php` پاسخ ۴۱۰ می‌دهند.

## راه‌اندازی روی سرور (استیجینگ)

پیش‌نیاز: Python 3.10+، MySQL/MariaDB، nginx.

```bash
cd /var/www
git clone https://github.com/itwman/irancarpet.git irancarpet-django
cd irancarpet-django
python3 -m venv venv
venv/bin/pip install -r requirements.txt
```

دیتابیس جدید و یک کاربر **فقط‌خواندنی** برای دیتابیس وردپرس:
```bash
mysql -e "CREATE DATABASE ic_django CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER 'ic_django'@'127.0.0.1' IDENTIFIED BY 'رمز-قوی-۱';"
mysql -e "GRANT ALL ON ic_django.* TO 'ic_django'@'127.0.0.1';"
mysql -e "CREATE USER 'ic_reader'@'127.0.0.1' IDENTIFIED BY 'رمز-قوی-۲';"
mysql -e "GRANT SELECT ON irancarpet_shop.* TO 'ic_reader'@'127.0.0.1';"
```

تنظیمات:
```bash
cp .env.example .env
nano .env        # رمزها، SECRET_KEY و STAGING=True
```

ساخت جدول‌ها، ایمپورت، فایل‌های استاتیک:
```bash
venv/bin/python manage.py migrate
venv/bin/python manage.py import_wp
venv/bin/python manage.py collectstatic --noinput
venv/bin/python manage.py createsuperuser
venv/bin/python manage.py check_urls --file docs/legacy-urls.txt
```

سرویس و nginx:
```bash
cp deploy/irancarpet.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now irancarpet
cp deploy/nginx-staging.conf /etc/nginx/sites-available/new.irancarpet.net
ln -s /etc/nginx/sites-available/new.irancarpet.net /etc/nginx/sites-enabled/
htpasswd -c /etc/nginx/.htpasswd-irancarpet admin
nginx -t
systemctl reload nginx
```

## به‌روزرسانی
```bash
cd /var/www/irancarpet-django
git pull
venv/bin/pip install -r requirements.txt
venv/bin/python manage.py migrate
venv/bin/python manage.py collectstatic --noinput
systemctl restart irancarpet
```

## ایمپورت دوباره
ایمپورت قابل تکرار است (بر اساس `wp_id`). برای یک بخش خاص:
```bash
venv/bin/python manage.py import_wp --only products
```
مراحل: `settings media taxonomies pricing products reviews blog redirects`

> ⚠️ ایمپورت `products` قیمت پایهٔ آلبوم‌ها را از روی قیمت‌های فعلی سایت وردپرس دوباره محاسبه می‌کند. بعد از اینکه قیمت‌ها را در پنل جنگو تنظیم کردید، آن را دوباره اجرا نکنید.
