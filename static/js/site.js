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
// پررنگ کردن ردیف سایز انتخاب‌شده
(function () {
  var f = document.getElementById("buyForm");
  if (!f) return;
  var mark = function () {
    f.querySelectorAll("tbody tr").forEach(function (tr) {
      var r = tr.querySelector("input[type=radio]");
      tr.classList.toggle("is-picked", !!(r && r.checked));
    });
  };
  f.addEventListener("change", mark);
  f.addEventListener("click", function (e) {
    var tr = e.target.closest("tbody tr");
    if (!tr || e.target.matches("input")) return;
    var r = tr.querySelector("input[type=radio]:not(:disabled)");
    if (r) { r.checked = true; mark(); }
  });
  mark();
  var picked = f.querySelector("tr.is-picked");
  if (picked && location.search.indexOf("size=") > -1) picked.scrollIntoView({ block: "center" });
})();
