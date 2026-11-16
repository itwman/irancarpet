"""چیدمان منوی پنل مدیریت (مثل پرشین پی‌دی‌اف): همهٔ گزارش‌ها در گروه اول، هر گروه با زیرعنوان‌های کوچک.

هر گروه: (عنوان، آیکن، ردیف‌ها). ردیف‌ها:
  "کلید"                 ← بخشی از REGISTRY (عنوان و آیکن از خودش)
  ("عنوان", "/نشانی/")    ← صفحهٔ ثابت پنل
  ("عنوان", "کلید")       ← بخشی از REGISTRY با عنوان کوتاه‌تر در منو
  ("#", "زیرعنوان")       ← عنوان کوچک برای جدا کردن ابزارهای کم‌کاربرد
بخشی که این‌جا نیامده باشد (مثلاً بخش تازه) خودکار در گروه «سایر» دیده می‌شود تا هیچ‌چیز گم نشود.
"""

LAYOUT = [
    ("گزارش‌ها", "list", [
        ("سلامت سایت", "/panel/reports/health/"),
        ("فروش و مشتریان", "/panel/crm/report/"),
        ("مقایسهٔ دو بازه", "/panel/reports/compare/"),
        ("بازدید و ورودی‌ها", "/panel/stats/"),
        ("فرصت‌ها و هشدارهای بازدید", "/panel/reports/insights/"),
        ("جستجوهای مشتری‌ها", "search-log"),
        ("فعالیت کارمندان", "activity"),
    ]),
    ("سفارش و فروش", "receipt", [
        "orders", "payments", "abandoned-carts",
        ("#", "اقساط"),
        "installment-plans", ("اقساط بتا (بازنشستگان)", "/panel/beta/"),
    ]),
    ("فرش‌ها", "carpet", [
        "products", ("افزودن سریع فرش‌های آلبوم", "/panel/products/quick/"), ("ساخت گروهی یک نقشه", "/panel/products/bulk/"),
        "special-offers",
        ("#", "قیمت"),
        "albums", "sizes", "pricelog",
        ("#", "دسته‌بندی"),
        "categories", "attributes", "brands", "tags",
        ("#", "ابزارهای متن"),
        "content-templates", "info-blocks", ("جایگزینی متن و لینک‌ها", "/panel/content-tools/"), "keyword-rules", "name-hints",
    ]),
    ("نظرات و پیام‌ها", "chat", [
        "reviews", "faqs", "comments", "contact-messages", "product-alerts",
    ]),
    ("مشتریان و بازاریابی", "users", [
        ("مشتریان", "customers"), ("پروفایل و گروه‌های مشتریان", "/panel/crm/segments/"), "coupons", "sms",
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
        "posts", "rewrites", "pages", "blog-categories", "blog-tags", "authors",
        ("#", "سئو"),
        "landing-pages", "redirects", "notfound",
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
        ("سایت، درگاه و پیامک", "/panel/settings/"), ("پیامک سفارش و باشگاه", "/panel/settings/?tab=crm"),
        ("اپلیکیشن", "/panel/settings/?tab=app"), ("همکاری در فروش", "/panel/settings/?tab=affiliate"),
        ("مارکت‌پلیس", "/panel/settings/?tab=market"), ("کارمندان پنل", "/panel/customers/?is_staff=1"),
    ]),
]
OTHER = ("سایر", "box")
