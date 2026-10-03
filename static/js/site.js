// گالری محصول
document.addEventListener("click", function (e) {
  var b = e.target.closest(".gallery__thumbs button");
  if (!b) return;
  var main = document.getElementById("mainImg");
  if (main) { main.src = b.dataset.src; }
  document.querySelectorAll(".gallery__thumbs button").forEach(function (x) { x.classList.toggle("on", x === b); });
});
// تبدیل ارقام فارسی ورودی‌های عددی به لاتین قبل از ارسال
document.addEventListener("submit", function (e) {
  e.target.querySelectorAll('input[inputmode="numeric"]').forEach(function (i) {
    i.value = i.value.replace(/[۰-۹]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹".indexOf(d); });
  });
});
