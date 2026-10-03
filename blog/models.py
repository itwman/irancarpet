from django.db import models
from django.utils import timezone

from core.models import Media, SeoFields


class PublishStatus(models.TextChoices):
    PUBLISH = "publish", "منتشرشده"
    DRAFT = "draft", "پیش‌نویس"
    PENDING = "pending", "در انتظار بررسی"
    PRIVATE = "private", "خصوصی"


class BlogCategory(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    name = models.CharField("نام", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    description = models.TextField("توضیحات", blank=True)

    class Meta:
        verbose_name = "دستهٔ مقاله"
        verbose_name_plural = "دسته‌های مقاله"
        unique_together = [("parent", "slug")]
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def path(self):
        chain, node = [self.slug], self.parent
        while node is not None and len(chain) < 10:
            chain.insert(0, node.slug)
            node = node.parent
        return "/".join(chain)

    def get_absolute_url(self):
        return f"/category/{self.path}/"


class BlogTag(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    name = models.CharField("نام", max_length=255)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True, unique=True)
    description = models.TextField("توضیحات", blank=True)

    class Meta:
        verbose_name = "برچسب مقاله"
        verbose_name_plural = "برچسب‌های مقاله"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return f"/tag/{self.slug}/"


class PostQuerySet(models.QuerySet):
    def published(self):
        return self.filter(status=PublishStatus.PUBLISH, published_at__lte=timezone.now())


class Post(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    title = models.CharField("عنوان", max_length=300)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True, unique=True)
    content = models.TextField("متن (HTML)", blank=True)
    excerpt = models.TextField("خلاصه", blank=True)
    image = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="تصویر شاخص")
    categories = models.ManyToManyField(BlogCategory, related_name="posts", blank=True, verbose_name="دسته‌ها")
    primary_category = models.ForeignKey(BlogCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    tags = models.ManyToManyField(BlogTag, related_name="posts", blank=True, verbose_name="برچسب‌ها")
    status = models.CharField("وضعیت", max_length=20, choices=PublishStatus.choices, default=PublishStatus.PUBLISH, db_index=True)
    author_name = models.CharField("نویسنده", max_length=200, blank=True)
    views = models.PositiveIntegerField("بازدید", default=0)
    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now, db_index=True)
    modified_at = models.DateTimeField("آخرین ویرایش", default=timezone.now)

    objects = PostQuerySet.as_manager()

    class Meta:
        verbose_name = "مقاله"
        verbose_name_plural = "مقالات"
        ordering = ["-published_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return f"/{self.slug}/"


class Page(SeoFields):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    title = models.CharField("عنوان", max_length=300)
    slug = models.SlugField("نامک", max_length=255, allow_unicode=True)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="children")
    content = models.TextField("متن (HTML)", blank=True)
    image = models.ForeignKey(Media, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField("وضعیت", max_length=20, choices=PublishStatus.choices, default=PublishStatus.PUBLISH)
    template = models.CharField("قالب ویژه", max_length=50, blank=True, help_text="home, shop, cart, contact و...")
    menu_order = models.IntegerField("ترتیب", default=0)
    published_at = models.DateTimeField("تاریخ انتشار", default=timezone.now)
    modified_at = models.DateTimeField("آخرین ویرایش", default=timezone.now)

    class Meta:
        verbose_name = "برگه"
        verbose_name_plural = "برگه‌ها"
        unique_together = [("parent", "slug")]
        ordering = ["menu_order", "title"]

    def __str__(self):
        return self.title

    @property
    def path(self):
        chain, node = [self.slug], self.parent
        while node is not None and len(chain) < 10:
            chain.insert(0, node.slug)
            node = node.parent
        return "/".join(chain)

    def get_absolute_url(self):
        if self.template == "home":
            return "/"
        return f"/{self.path}/"


class Comment(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies")
    author_name = models.CharField("نام", max_length=200)
    author_email = models.EmailField("ایمیل", blank=True)
    content = models.TextField("متن")
    is_approved = models.BooleanField("تأییدشده", default=False, db_index=True)
    created_at = models.DateTimeField("تاریخ", default=timezone.now)

    class Meta:
        verbose_name = "دیدگاه"
        verbose_name_plural = "دیدگاه‌ها"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.author_name}: {self.content[:40]}"


class Faq(models.Model):
    wp_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True, editable=False)
    question = models.CharField("پرسش", max_length=500)
    answer = models.TextField("پاسخ (HTML)")
    group = models.CharField("گروه", max_length=100, blank=True)
    product = models.ForeignKey("catalog.Product", null=True, blank=True, on_delete=models.CASCADE, related_name="faqs")
    order = models.IntegerField("ترتیب", default=0)
    is_active = models.BooleanField("فعال", default=True)

    class Meta:
        verbose_name = "پرسش متداول"
        verbose_name_plural = "پرسش‌های متداول"
        ordering = ["order", "pk"]

    def __str__(self):
        return self.question
