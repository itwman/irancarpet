// گالری محصول: کشیدن انگشت روی تصویر، دکمه‌های کوچک و کلیدهای جهت
(function () {
  var main = document.getElementById("gMain");
  if (!main) return;
  var slides = main.querySelectorAll(".gallery__slide");
  if (slides.length < 2) return;
  var thumbs = document.querySelectorAll(".gallery__thumbs button");
  var dots = document.querySelectorAll(".gallery__dots i");
  var idx = document.getElementById("gIdx");
  var fa = function (n) { return String(n).replace(/\d/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; }); };
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var cur = 0;
  var mark = function (i) {
    cur = i;
    thumbs.forEach(function (b, j) { b.classList.toggle("on", j === i); });
    dots.forEach(function (d, j) { d.classList.toggle("on", j === i); });
    if (idx) idx.textContent = fa(i + 1);
  };
  var go = function (i) {
    i = Math.max(0, Math.min(slides.length - 1, i));
    var s = slides[i];
    main.scrollTo({ left: s.offsetLeft - (main.clientWidth - s.clientWidth) / 2, behavior: reduce ? "auto" : "smooth" });
    mark(i);
  };
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) mark([].indexOf.call(slides, e.target)); });
    }, { root: main, threshold: 0.6 });
    slides.forEach(function (s) { io.observe(s); });
  }
  thumbs.forEach(function (b, i) { b.addEventListener("click", function () { go(i); }); });
  main.addEventListener("keydown", function (e) {
    // راست‌به‌چپ: فلش چپ = تصویر بعدی
    if (e.key === "ArrowLeft") { e.preventDefault(); go(cur + 1); }
    if (e.key === "ArrowRight") { e.preventDefault(); go(cur - 1); }
  });
})();
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
// ورود و ثبت‌نام
(function () {
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  var en = function (s) { return String(s).replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); }).replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); }); };
  // جابه‌جایی بین ورود پیامکی و رمز، بدون بارگذاری دوباره
  document.querySelectorAll("[data-pane]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      document.querySelectorAll(".auth2__pane").forEach(function (p) { p.hidden = p.id !== a.dataset.pane; });
      var f = document.querySelector("#" + a.dataset.pane + " input:not([type=hidden])");
      if (f) f.focus();
      history.replaceState(null, "", a.href);
    });
  });
  document.querySelectorAll("[data-toggle-pw]").forEach(function (b) {
    b.addEventListener("click", function () {
      var i = b.parentNode.querySelector("input");
      var show = i.type === "password";
      i.type = show ? "text" : "password";
      b.textContent = show ? "پنهان" : "نمایش";
    });
  });
  // کد یک‌بارمصرف در ۵ خانه
  var form = document.getElementById("otpForm");
  if (form) {
    var boxes = Array.prototype.slice.call(form.querySelectorAll(".otp__d"));
    var hidden = document.getElementById("otpCode");
    var sync = function (submitIfFull) {
      var code = boxes.map(function (b) { return b.value; }).join("");
      hidden.value = code;
      boxes.forEach(function (b) { b.classList.toggle("filled", !!b.value); });
      if (submitIfFull && code.length === boxes.length && !form.querySelector("#name")) form.submit();
    };
    var fill = function (start, text) {
      var digits = en(text).replace(/\D/g, "").split("");
      for (var i = start; i < boxes.length && digits.length; i++) boxes[i].value = digits.shift();
      var next = boxes.find(function (b) { return !b.value; });
      (next || boxes[boxes.length - 1]).focus();
      sync(true);
    };
    boxes.forEach(function (b, i) {
      b.addEventListener("input", function () {
        var v = en(b.value).replace(/\D/g, "");
        if (v.length > 1) { b.value = ""; fill(i, v); return; }
        b.value = v;
        if (v && i < boxes.length - 1) boxes[i + 1].focus();
        sync(true);
      });
      b.addEventListener("keydown", function (e) {
        if (e.key === "Backspace" && !b.value && i > 0) { boxes[i - 1].value = ""; boxes[i - 1].focus(); sync(false); e.preventDefault(); }
        if (e.key === "ArrowLeft" && i < boxes.length - 1) boxes[i + 1].focus();
        if (e.key === "ArrowRight" && i > 0) boxes[i - 1].focus();
      });
      b.addEventListener("paste", function (e) { e.preventDefault(); fill(0, (e.clipboardData || window.clipboardData).getData("text")); });
      b.addEventListener("focus", function () { b.select(); });
    });
    form.addEventListener("submit", function (e) {
      sync(false);
      if (hidden.value.length !== boxes.length) {
        e.preventDefault();
        var g = form.querySelector(".otp");
        g.classList.remove("shake"); void g.offsetWidth; g.classList.add("shake");
        (boxes.find(function (b) { return !b.value; }) || boxes[0]).focus();
      }
    });
    if (document.querySelector(".alert-ic")) { var g = form.querySelector(".otp"); g.classList.add("shake"); }
  }
  // شمارش معکوس ارسال دوباره
  var cd = document.querySelector("[data-countdown]");
  if (cd) {
    var left = +cd.dataset.countdown, btn = cd.parentNode.querySelector("button");
    var tick = function () {
      if (left <= 0) { cd.hidden = true; btn.hidden = false; return; }
      cd.querySelector("b").textContent = ("0:" + (left < 10 ? "0" : "") + left).replace(/\d/g, function (d) { return FA[d]; });
      left--; setTimeout(tick, 1000);
    };
    tick();
  }
})();
