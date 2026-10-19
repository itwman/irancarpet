from django.conf import settings
from django.contrib.syndication.views import Feed

from core import brand
from core.seo import plain

from .models import Post


class LatestPostsFeed(Feed):
    link = "/blog/"

    def title(self):
        return brand.name()

    def description(self):
        return f"آخرین مطالب {brand.name()}"

    def items(self):
        return Post.objects.published()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return plain(item.excerpt or item.content, 300)

    def item_pubdate(self, item):
        return item.published_at
