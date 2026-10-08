from django.conf import settings
from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path, re_path
from django.views.static import serve

from blog import views as blog_views
from blog.feeds import LatestPostsFeed
from catalog import views as catalog_views
from core import views as core_views
from seo import sitemaps
from seo import views as seo_views
from api import views as api_views
from finder import api as finder_api
from finder import views as finder_views
from growth import views as growth_views
from installments import views as installments_views
from landing import views as landing_views
from pricing import views as pricing_views
from torob import emalls as torob_emalls
from torob import views as torob_views

P = r"(?:page/(?P<page>\d+)/)?"

urlpatterns = [
    path("", core_views.home, name="home"),
    # فید ترب (همان آدرس افزونهٔ وردپرس)
    re_path(r"^wp-json/torob/products/?$", torob_views.products),
    re_path(r"^wp-json/emalls_ext/v1/products/?$", torob_emalls.products),
    # اپلیکیشن موبایل
    path("api/app/v1/", include("api.urls")),
    path("app-img/<int:w>/<path:path>", api_views.thumb),
    path("app/return/<int:number>/", api_views.app_return),
    # آدرس‌های مخصوص وردپرس → 410 (حذف دائمی)
    re_path(r"^(?:wp-login\.php|xmlrpc\.php|wp-admin|wp-json|wp-includes|wp-cron\.php)(?:/.*)?$", core_views.gone),
    # پنل قدیمی جنگو فقط برای مدیر کل و موارد اضطراری
    path("panel/system/", admin.site.urls),
    path("panel/installment-file/<int:pk>/<str:key>/", installments_views.private_file),
    path("panel/finder-photo/<int:pk>/", finder_api.panel_photo),
    path("panel/", include("dashboard.urls")),
    path("installments/quote/", installments_views.quote_api),
    path("robots.txt", core_views.robots_txt),
    path("o/<str:token>/", growth_views.quickpay),
    path("review/<str:token>/", growth_views.review_invite),
    path("alerts/", growth_views.alert),
    path("farsh-yab/", finder_views.page),
    path("product/<str:slug>/review/", growth_views.product_review),
    path("llms.txt", seo_views.llms_txt),
    re_path(r"^(?P<key>[0-9a-f]{32})\.txt$", seo_views.indexnow_key),
    path("sitemap_index.xml", sitemaps.index),
    re_path(r"^(?P<name>[a-z_\-]+?)-sitemap(?P<num>\d*)\.xml$", sitemaps.section),
    path("feed/", LatestPostsFeed()),
    # نشانی‌های قدیمی خبرخوان (وردپرس و افزونه‌ها) ← /feed/
    re_path(r"^(?:rss2?|atom|rdf|feed/(?:rss2?|atom|rdf))/?$", RedirectView.as_view(url="/feed/", permanent=True)),
    path("search/", catalog_views.search, name="search"),
    path("", include("affiliate.urls")),
    path("", include("market.urls")),
    path("", include("shop.urls")),
    path("blog/", blog_views.blog_index, name="blog"),
    re_path(rf"^blog/{P}$", blog_views.blog_index),
    path("product/<str:slug>/", catalog_views.product_detail, name="product"),
    path("p/<int:pk>/", catalog_views.short_link),
    re_path(rf"^product-category/(?P<path>.+?)/{P}$", catalog_views.category_detail),
    re_path(rf"^product-tag/(?P<slug>[^/]+)/{P}$", catalog_views.tag_detail),
    re_path(rf"^brand/(?P<slug>[^/]+)/{P}$", catalog_views.brand_detail),
    re_path(rf"^category/(?P<path>.+?)/{P}$", blog_views.category_detail),
    re_path(rf"^tag/(?P<slug>[^/]+)/{P}$", blog_views.tag_detail),
    # صفحهٔ هر لیست قیمت (خود /carpets-price-list/ یک برگه با قالب price_list است)
    re_path(rf"^carpets/(?P<slug>[^/]+)/{P}$", landing_views.detail),
    re_path(rf"^carpets-price-list/(?P<slug>(?!page/)[^/]+)/{P}$", pricing_views.album_detail),
]

if settings.DEBUG:
    from core.views import dev_media

    urlpatterns += [re_path(r"^wp-content/uploads/(?P<path>.*)$", dev_media)]

# باید آخرین الگو باشد: مقاله‌ها، برگه‌ها و آرشیو ویژگی‌ها
urlpatterns += [re_path(r"^(?P<path>.+)/$", core_views.resolve)]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
