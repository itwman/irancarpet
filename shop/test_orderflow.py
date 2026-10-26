from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone

from shop.models import Order, ShopSettings
from shop import orderflow as F


def mk(status="pending", days=0, paid=0, **kw):
    o = Order.objects.create(first_name="علی", last_name="رضایی", mobile="09120000000", province="تهران", city="تهران",
                             address="خیابان", items_total=10_000_000, paid_amount=paid, status=status, **kw)
    at = timezone.now() - timedelta(days=days)
    Order.objects.filter(pk=o.pk).update(created_at=at, status_at=at, paid_at=at if paid else None)
    o.refresh_from_db()
    return o


class OrderFlowTests(TestCase):
    def setUp(self):
        cache.clear()
        from dashboard import resources

        resources._SS.update(at=0)
        self.u = get_user_model().objects.create_user("staff", password="x", is_staff=True, is_superuser=True)
        self.client.force_login(self.u)

    def test_due_late_and_auto_cancel(self):
        old = mk("pending", 8)
        fresh = mk("pending", 2)
        inst = mk("pending", 9, payment_mode="installment")
        prep_late = mk("paid", 15, paid=10_000_000)
        prep_soon = mk("paid", 13, paid=10_000_000)
        self.assertEqual(F.state(prep_late), "late")
        self.assertEqual(F.state(prep_soon), "soon")
        late = set(Order.objects.filter(F.late_q()).values_list("pk", flat=True))
        self.assertIn(prep_late.pk, late)
        self.assertNotIn(prep_soon.pk, late)
        self.assertEqual(set(Order.objects.filter(F.late_q("soon")).values_list("pk", flat=True)) & {prep_soon.pk}, {prep_soon.pk})
        self.assertEqual(F.auto_cancel(), 1)
        old.refresh_from_db()
        self.assertEqual(old.status, "cancelled")
        self.assertIn("لغو خودکار", old.admin_note)
        self.assertEqual(Order.objects.get(pk=fresh.pk).status, "pending")
        self.assertEqual(Order.objects.get(pk=inst.pk).status, "pending")  # اقساطی لغو خودکار نمی‌شود
        ShopSettings.objects.update(pending_cancel_days=0)
        self.assertEqual(F.auto_cancel(), 0)

    def test_status_at_and_bulk_actions(self):
        paid = mk("paid", 3, paid=10_000_000)
        unpaid = mk("pending", 1)
        paid.status = "processing"
        paid.save()
        self.assertLess(timezone.now() - paid.status_at, timedelta(minutes=1))
        r = self.client.post("/panel/orders/", {"action": "cancel", "ids": [paid.pk, unpaid.pk]}, follow=True)
        self.assertContains(r, "پرداخت دارد و لغو نشد")
        self.assertEqual(Order.objects.get(pk=unpaid.pk).status, "cancelled")
        self.assertEqual(Order.objects.get(pk=paid.pk).status, "processing")
        # ارسال گروهی با کد رهگیری
        r = self.client.get(f"/panel/orders/ship/?ids={paid.pk}&ids={unpaid.pk}")
        self.assertContains(r, f'name="t_{paid.pk}"')
        self.client.post("/panel/orders/ship/", {"ids": [paid.pk], f"t_{paid.pk}": "ABC123"})
        paid.refresh_from_db()
        self.assertEqual((paid.status, paid.tracking_code), ("shipped", "ABC123"))
        self.client.post("/panel/orders/", {"action": "complete", "ids": [paid.pk]})
        self.assertEqual(Order.objects.get(pk=paid.pk).status, "completed")

    def test_list_tabs_print_and_notify(self):
        a = mk("paid", 20, paid=10_000_000)
        r = self.client.get("/panel/orders/?late=late")
        self.assertContains(r, "عقب‌افتاده")
        self.assertContains(r, "due--late")
        self.assertContains(r, "tabs-p")
        r = self.client.get(f"/panel/orders/print/?ids={a.pk}&mode=label")
        self.assertContains(r, "گیرنده")
        d = self.client.get("/panel/orders/notify/?since=0").json()
        self.assertEqual(d["latest"], a.pk)
        self.assertEqual(d["items"][0]["n"], 1)
        b = mk("pending", 0)
        d = self.client.get(f"/panel/orders/notify/?since={a.pk}").json()
        self.assertEqual([x["id"] for x in d["new"]], [b.pk])
