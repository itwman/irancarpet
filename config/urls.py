from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

from blog import views as blog_views
from blog.feeds import LatestPostsFeed
from catalog import views as catalog_views
from core import views as core_views
from seo import sitemaps

P = r"(?:page/(?P<page>\d+)/)?"

urlpatterns = [
    path("", core_views.home, name="home"),
    # آدرس‌های مخصوص وردپرس → 410 (حذف دائمی)
    re_path(r"^(?:wp-login\.php|xmlrpc\.php|wp-admin|wp-json|wp-includes|wp-cron\.php)(?:/.*)?$", core_views.gone),
    # پنل قدیمی جنگو فقط برای مدیر کل و موارد اضطراری
    path("panel/system/", admin.site.urls),
    path("panel/", include("dashboard.urls")),
    path("robots.txt", core_views.robots_txt),
    path("sitemap_index.xml", sitemaps.index),
    re_path(r"^(?P<name>[a-z_\-]+?)-sitemap(?P<num>\d*)\.xml$", sitemaps.section),
    path("feed/", LatestPostsFeed()),
    path("search/", catalog_views.search, name="search"),
    path("", include("shop.urls")),
    path("blog/", blog_views.blog_index, name="blog"),
    re_path(rf"^blog/{P}$", blog_views.blog_index),
    path("product/<str:slug>/", catalog_views.product_detail, name="product"),
    re_path(rf"^product-category/(?P<path>.+?)/{P}$", catalog_views.category_detail),
    re_path(rf"^product-tag/(?P<slug>[^/]+)/{P}$", catalog_views.tag_detail),
    re_path(rf"^brand/(?P<slug>[^/]+)/{P}$", catalog_views.brand_detail),
    re_path(rf"^category/(?P<path>.+?)/{P}$", blog_views.category_detail),
    re_path(rf"^tag/(?P<slug>[^/]+)/{P}$", blog_views.tag_detail),
]

if settings.DEBUG:
    from core.views import dev_media

    urlpatterns += [re_path(r"^wp-content/uploads/(?P<path>.*)$", dev_media)]

# باید آخرین الگو باشد: مقاله‌ها، برگه‌ها و آرشیو ویژگی‌ها
urlpatterns += [re_path(r"^(?P<path>.+)/$", core_views.resolve)]

handler404 = "core.views.not_found"
handler500 = "core.views.server_error"
