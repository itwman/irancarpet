from django.test import TestCase

# Create your tests here.


class TopicRecommendTests(__import__("django.test", fromlist=["TestCase"]).TestCase):
    """مقالهٔ «فرش موکا»: پیشنهادها از دستهٔ موکا (هر نقشه یک بار)، نه از شانه‌ای که در متن آمده."""

    def setUp(self):
        from django.core.cache import cache

        from catalog import mocha
        from catalog.models import Attribute, AttributeTerm, Category, Product
        from core.models import Media

        cache.clear()
        self.mocha = Category.objects.get(slug=mocha.SLUG)
        reeds = Attribute.objects.get_or_create(slug="reeds-per-meter", defaults={"label": "شانه", "is_public": True})[0]
        t1000 = AttributeTerm.objects.create(attribute=reeds, name="1000", slug="1000")
        img = Media.objects.create(title="x", file="x.jpg")

        def mk(title, slug, design, views, mocha_cat=False):
            p = Product.objects.create(title=title, slug=slug, status="publish", design_name=design, image=img, views=views,
                                       min_price=10_000_000)
            p.specs.add(t1000)
            if mocha_cat:
                p.categories.add(self.mocha)
            return p

        for i in range(8):  # فرش‌های ۱۰۰۰ شانهٔ پربازدید، غیر موکا
            mk(f"فرش 1000 شانه نقشه کرمان {i} زمینه سرمه ای", f"k{i}", f"کرمان {i}", 1000 + i)
        self.m = [mk("فرش 1000 شانه موکا نقشه آوین زمینه صدفی", "m1", "آوین", 50, True),
                  mk("فرش 1000 شانه موکا نقشه آوین زمینه بژ", "m2", "آوین", 40, True),
                  mk("فرش 1200 شانه موکا نقشه سروش زمینه صدفی", "m3", "سروش", 30, True),
                  mk("فرش 1200 شانه موکا نقشه هما زمینه نسکافه ای", "m4", "هما", 20, True)]
        from blog.models import Post

        self.post = Post.objects.create(title="فرش موکا", slug="فرش-موکا", status="publish",
                                        content="<p>" + "فرش 1000 شانه موکا. " * 20 + "</p>")

    def test_topic_from_title(self):
        from blog import recommend as R

        self.assertEqual(R.topic_of(self.post), ("cat", self.mocha))
        ids = R._pick(self.post, 4)
        names = [x for x in ids[:3]]
        self.assertEqual(set(names), {self.m[0].pk, self.m[2].pk, self.m[3].pk})   # آوین فقط یک بار، بعد بقیهٔ موکاها
        self.assertNotIn(self.m[1].pk, ids)
        t = R.topic_link(self.post)
        self.assertEqual((t["heading"], t["url"], t["count"]), ("فرش‌های پالت موکا", self.mocha.get_absolute_url(), 4))
        r = self.client.get(self.post.get_absolute_url())
        self.assertContains(r, "فرش‌های پالت موکا")
        self.assertContains(r, "همهٔ ۴ فرش پالت موکا")

    def test_manual_tag_and_reeds_link(self):
        from blog import recommend as R
        from catalog.models import Category, ProductTag

        tag = ProductTag.objects.create(name="فرش طرح افشان", slug="afshan")
        self.post.rec_tag = tag
        self.post.save()
        self.assertEqual(R.topic_of(self.post), ("tag", tag))
        c = Category.objects.create(name="فرش 1000 شانه", slug="c1000")
        self.assertEqual(R.reeds_url("1000"), c.get_absolute_url())
