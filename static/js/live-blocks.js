/* بخش‌های زندهٔ مقاله: زبانه‌های سایز در لیست قیمت اقساطی */
(function () {
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-lb-tab]");
    if (!b) return;
    var box = b.closest(".lb-prices"), n = b.getAttribute("data-lb-tab");
    box.querySelectorAll("[data-lb-tab]").forEach(function (x) { x.setAttribute("aria-selected", x === b ? "true" : "false"); });
    box.querySelectorAll("[data-lb-panel]").forEach(function (p) { p.hidden = p.getAttribute("data-lb-panel") !== n; });
  });
})();
