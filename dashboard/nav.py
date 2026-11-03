"""چیدمان منوی پنل مدیریت: پرکاربردها بالا، ابزارهای کم‌کاربرد زیر یک عنوان کوچک.

هر گروه: (عنوان، آیکن، ردیف‌ها). ردیف‌ها:
  "کلید"                 ← بخشی از REGISTRY (عنوان و آیکن از خودش)
  ("عنوان", "/نشانی/")    ← صفحهٔ ثابت پنل
  ("عنوان", "کلید")       ← بخشی از REGISTRY با عنوان کوتاه‌تر در منو
  ("#", "زیرعنوان")       ← عنوان کوچک برای جدا کردن ابزارهای کم‌کاربرد
بخشی که این‌جا نیامده باشد (مثلاً بخش تازه) خودکار در گروه «سایر» دیده می‌شود تا هیچ‌چیز گم نشود.
"""

LAYOUT = [
    ("سفارش و فروش", "receipt", [
        "orders", "payments", "installment-plans", ("اقساط بتا (بازنشستگان)", "/panel/beta/"),
        "contact-messages", "abandoned-carts", "product-alerts",
        ("#", "گزارش"),
        ("گزارش فروش و مشتریان", "/panel/crm/report/"), ("گزارش بازدید و ورودی‌ها", "/panel/stats/"),
    ]),
    ("فرش‌ها", "carpet", [
        "products", ("افزودن سریع فرش‌های آلبوم", "/panel/products/quick/"), ("ساخت گروهی یک نقشه", "/panel/products/bulk/"),
        "special-offers", "reviews", "faqs",
        ("#", "دسته‌بندی"),
        "categories", "attributes", "brands", "tags",
        ("#", "ابزارهای متن"),
        "content-templates", "info-blocks", ("جایگزینی متن و لینک‌ها", "/panel/content-tools/"), "keyword-rules", "name-hints",
    ]),
    ("قیمت", "layers", ["albums", "sizes", "pricelog"]),
    ("مشتریان و بازاریابی", "users", [
        ("مشتریان", "customers"), ("کارمندان", "/panel/customers/?is_staff=1"),
        ("پروفایل و گروه‌های مشتریان", "/panel/crm/segments/"), "coupons", "sms",
        ("#", "باشگاه مشتریان"),
        "crm-campaigns", "crm-calendar", "crm-points", "crm-sms", "spam-users",
        ("#", "همکاری در فروش"),
        "affiliates", "affiliate-commissions", "affiliate-payouts", "commission-tiers",
    ]),
    ("مارکت‌پلیس", "box", [
        "sellers", "seller-products", ("صف بررسی کالاها", "/panel/seller-products/?queue=1"), "seller-orders", "seller-payouts",
        "category-commissions",
    ]),
    ("محتوا و سئو", "pen", [
        "posts", "rewrites", "pages", "comments", "blog-categories", "blog-tags",
        ("#", "سئو"),
        "landing-pages", "redirects", "notfound", "search-log",
        ("#", "رسانه"),
        "media", ("رسانه‌های بی‌استفاده", "/panel/media/unused/"),
    ]),
    ("کانال‌ها و اپ", "phone", [
        "farshplus", "rajyar-posts", ("وضعیت در ترب", "/panel/torob/"),
        ("#", "اپلیکیشن"),
        "app-notifications", "app-devices",
        ("#", "فرش‌یاب"),
        "finder-needs", "finder-requests",
    ]),
    ("تنظیمات", "settings", [
        ("تنظیمات سایت، درگاه و پیامک", "/panel/settings/"), ("تنظیمات اپلیکیشن", "/panel/settings/?tab=app"),
        ("تنظیمات پیامک سفارش و باشگاه", "/panel/settings/?tab=crm"), ("تنظیمات همکاری در فروش", "/panel/settings/?tab=affiliate"),
        ("تنظیمات مارکت‌پلیس", "/panel/settings/?tab=market"), "activity",
    ]),
]
OTHER = ("سایر", "box")
