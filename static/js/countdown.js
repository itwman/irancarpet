/* شمارندهٔ معکوس فرصت‌های ویژه: [data-countdown="ISO"] */
(function () {
  "use strict";
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  function fa(n) { return String(n).replace(/\d/g, function (d) { return FA[d]; }); }
  function pad(n) { return n < 10 ? "0" + n : String(n); }
  var els = Array.prototype.slice.call(document.querySelectorAll("[data-offer-end]"));
  if (!els.length) return;
  els.forEach(function (el) { el.dataset.end = String(Date.parse(el.dataset.offerEnd)); });
  function tick() {
    var now = Date.now();
    els.forEach(function (el) {
      var left = Math.max(0, Math.floor((+el.dataset.end - now) / 1000));
      if (!left) { el.textContent = "این فرصت تمام شد"; el.classList.add("is-over"); return; }
      var d = Math.floor(left / 86400), h = Math.floor(left % 86400 / 3600), m = Math.floor(left % 3600 / 60), s = left % 60;
      el.textContent = (d ? fa(d) + " روز و " : "") + fa(pad(h) + ":" + pad(m) + ":" + pad(s)) + " مانده";
    });
  }
  tick();
  setInterval(tick, 1000);
})();
