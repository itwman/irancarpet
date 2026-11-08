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


class AuthorTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        from blog.models import Author, BlogCategory, Post

        cache.clear()
        Author.objects.all().delete()
        self.cat = BlogCategory.objects.create(name="نگهداری", slug="care")
        self.a = Author.objects.create(name="محمدعلی ناظری", slug="محمدعلی-ناظری", role="مدیر فروش", is_default=True, bio="معرفی")
        self.b = Author.objects.create(name="نویسندهٔ دوم", slug="b", role="کارشناس")
        self.b.categories.add(self.cat)
        cache.clear()
        self.p1 = Post.objects.create(title="مقالهٔ یک", slug="p1", status="publish", content="<p>x</p>")
        self.p2 = Post.objects.create(title="مقالهٔ دو", slug="p2", status="publish", content="<p>x</p>", primary_category=self.cat)
        self.p2.categories.add(self.cat)
        self.p3 = Post.objects.create(title="مقالهٔ سه", slug="p3", status="publish", content="<p>x</p>", author=self.b)

    def test_byline_rules(self):
        self.assertEqual(self.p1.byline(), self.a)   # پیش‌فرض
        self.assertEqual(self.p2.byline(), self.b)   # از دسته
        self.assertEqual(self.p3.byline(), self.b)   # مستقیم
        self.assertEqual(set(self.b.posts()), {self.p2, self.p3})

    def test_pages(self):
        r = self.client.get("/p1/")
        self.assertContains(r, '"@type": "Person"')
        self.assertContains(r, 'href="/author/محمدعلی-ناظری/" rel="author"')
        self.assertContains(r, "author-box")
        r = self.client.get("/author/b/")
        self.assertContains(r, "نویسندهٔ دوم")
        self.assertContains(r, "ProfilePage")
        self.assertContains(r, "مقالهٔ دو")
        self.assertEqual(self.client.get("/author/nobody/").status_code, 404)

    def test_panel(self):
        from django.contrib.auth import get_user_model

        boss = get_user_model().objects.create_user("boss", password="x" * 10, is_staff=True, is_superuser=True)
        self.client.force_login(boss)
        self.assertContains(self.client.get("/panel/authors/"), "نویسندهٔ دوم")
        self.assertEqual(self.client.get("/panel/authors/add/").status_code, 200)
        self.assertEqual(self.client.get(f"/panel/authors/{self.b.pk}/").status_code, 200)
        self.assertContains(self.client.get(f"/panel/posts/{self.p1.pk}/"), "نویسنده")
        r = self.client.post("/panel/posts/", {"action": "set_author", "action_value": str(self.b.pk), "ids": [self.p1.pk]}, follow=True)
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.author, self.b)
