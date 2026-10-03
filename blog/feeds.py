from django.conf import settings
from django.contrib.syndication.views import Feed

from core.seo import plain

from .models import Post


class LatestPostsFeed(Feed):
    title = "ایران کارپت"
    link = "/blog/"
    description = "آخرین مطالب ایران کارپت"

    def items(self):
        return Post.objects.published()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return plain(item.excerpt or item.content, 300)

    def item_pubdate(self, item):
        return item.published_at
