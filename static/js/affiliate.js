/* همکاری در فروش: ماشین‌حساب پورسانت، کپی پیوند، جستجوی فرش و ساخت پیوند کوتاه */
(function () {
  "use strict";
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  function fa(s) { return String(s).replace(/\d/g, function (d) { return FA[d]; }); }
  function sep(n) { return fa(Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, "٬")); }
  function label(v) {
    if (v >= 1e9) return fa((v / 1e9).toFixed(2).replace(/\.?0+$/, "").replace(".", "٫")) + " میلیارد";
    return fa(Math.round(v / 1e6)) + " میلیون";
  }

  function copy(text, btn) {
    var done = function () { var t = btn.textContent; btn.textContent = "کپی شد ✓"; setTimeout(function () { btn.textContent = t; }, 1600); };
    if (navigator.clipboard && window.isSecureContext) { navigator.clipboard.writeText(text).then(done, function () { fallback(text); done(); }); }
    else { fallback(text); done(); }
  }
  function fallback(text) {
    var ta = document.createElement("textarea"); ta.value = text; ta.setAttribute("readonly", ""); ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); } catch (e) {} document.body.removeChild(ta);
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-copy]");
    if (b && b.getAttribute("data-copy")) { e.preventDefault(); copy(b.getAttribute("data-copy"), b); }
  });

  // دکمهٔ «شروع همکاری» پایین صفحه: رفتن به فرم موبایل بالای صفحه
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-focus]"), id = b && b.getAttribute("data-focus");
    var el = id && document.getElementById(id);
    if (el) { e.preventDefault(); el.scrollIntoView({ behavior: "smooth", block: "center" }); setTimeout(function () { el.focus({ preventScroll: true }); }, 400); }
  });

  // ماشین‌حساب صفحهٔ معرفی
  var data = document.getElementById("calcData"), inp = document.getElementById("calcIn");
  if (data && inp) {
    var cfg = JSON.parse(data.textContent), tiers = cfg.tiers || [];
    var rateFor = function (v) { var p = tiers.length ? tiers[0][1] : 0; tiers.forEach(function (t) { if (v >= t[0]) p = t[1]; }); return p; };
    var bracket = function (v) {
      var s = 0; tiers.forEach(function (t, i) { var lo = i ? t[0] : 0, hi = i + 1 < tiers.length ? tiers[i + 1][0] : Infinity; if (v > lo) s += (Math.min(v, hi) - lo) * t[1] / 100; });
      return s;
    };
    var upd = function () {
      var v = +inp.value, amt = cfg.mode === "bracket" ? bracket(v) : v * rateFor(v) / 100;
      document.getElementById("calcSales").textContent = label(v);
      document.getElementById("calcOut").textContent = sep(amt);
      document.getElementById("calcRate").textContent = "(" + fa((amt / v * 100).toFixed(2).replace(/\.?0+$/, "").replace(".", "٫")) + "٪)";
    };
    inp.addEventListener("input", upd); upd();
  }

  // پیش‌نمایش نام پیوند در فرم ثبت‌نام
  var code = document.getElementById("acode"), prev = document.getElementById("codePrev");
  if (code && prev) code.addEventListener("input", function () { code.value = code.value.toLowerCase().replace(/[^a-z0-9_]/g, ""); prev.textContent = code.value || "…"; });

  // فرش‌ها برای معرفی: زبانه‌ها، شانه، جستجو و «بیشتر»
  var q = document.getElementById("affQ"), box = document.getElementById("affResults");
  if (q && box) {
    var more = document.getElementById("affMore"), reeds = document.getElementById("affReeds");
    var st = { tab: "best", page: 1, seed: String(Date.now() % 100000) }, timer, busy = false;
    var esc = function (s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; };
    var card = function (it) {
      var o = it.offer;
      return '<article class="affc">' +
        '<a class="affc__img" href="' + esc(it.url) + '" target="_blank" rel="noopener">' +
          (it.image ? '<img src="' + esc(it.image) + '" alt="" loading="lazy" width="480" height="480">' : "") +
          (o ? '<span class="affc__off">٪' + esc(o.percent) + " تخفیف</span>" : "") +
          (it.reeds ? '<span class="affc__reeds">' + esc(it.reeds) + " شانه</span>" : "") + "</a>" +
        '<div class="affc__body"><h3>' + esc(it.title) + "</h3>" +
          '<p class="affc__price">' + (it.price ? (it.from ? "<small>از</small> " : "") + "<b>" + esc(it.price) + "</b> <small>تومان</small>" : "") +
            (o && o.regular ? " <s>" + esc(o.regular) + "</s>" : "") + "</p>" +
          '<p class="affc__meta">' + (o ? esc(o.size) + " · " + esc(o.left) + " تخته مانده" + (o.ends ? " · تا " + esc(o.ends) : "") :
            (it.sizes ? esc(it.sizes) + " سایز موجود" : "")) + "</p>" +
          (it.commission ? '<p class="affc__earn">پورسانت شما از هر فروش حدود <b>' + esc(it.commission) + "</b> تومان</p>" : "") +
          '<div class="affc__acts">' +
            '<button class="pill" type="button" data-copy="' + esc(it.link) + '">کپی پیوند</button>' +
            '<button class="pill" type="button" data-copy="' + esc(it.text) + '">کپی متن</button>' +
            '<a class="pill" target="_blank" rel="noopener" href="https://wa.me/?text=' + encodeURIComponent(it.text) + '">واتس‌اپ</a>' +
            (it.download ? '<a class="pill" href="' + esc(it.download) + '" download>دانلود عکس</a>' : "") +
          "</div></div></article>";
    };
    var load = function (append) {
      if (busy) return; busy = true;
      var params = new URLSearchParams({ q: q.value.trim(), tab: st.tab, page: st.page, reeds: reeds ? reeds.value : "", seed: st.seed });
      if (!append) box.setAttribute("aria-busy", "true");
      fetch("/my-account/affiliate/products/?" + params, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          var html = (d.items || []).map(card).join("");
          if (!append) box.innerHTML = html || '<p class="muted aff-empty">' + (st.tab === "offers" && !q.value.trim() ? "الان فرصت ویژه‌ای نیست." : "فرشی پیدا نشد؛ کلمهٔ دیگری بنویسید یا شانه را عوض کنید.") + "</p>";
          else box.insertAdjacentHTML("beforeend", html);
          more.hidden = !d.more;
        })
        .catch(function () {})
        .finally(function () { busy = false; box.removeAttribute("aria-busy"); });
    };
    var reset = function () { st.page = 1; load(false); };
    document.querySelectorAll(".aff-tabs [data-tab]").forEach(function (b) {
      b.addEventListener("click", function () {
        document.querySelectorAll(".aff-tabs [data-tab]").forEach(function (x) { x.classList.toggle("on", x === b); x.setAttribute("aria-selected", x === b); });
        st.tab = b.getAttribute("data-tab");
        if (st.tab === "random") st.seed = String(Date.now() % 100000);  // هر بار چیدمان تازه
        q.value = ""; reset();
      });
    });
    if (reeds) reeds.addEventListener("change", reset);
    q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(reset, 300); });
    more.addEventListener("click", function () { st.page += 1; load(true); });
    load(false);
  }

  // پیوند کوتاه هر صفحه
  var pf = document.getElementById("affPage");
  if (pf) pf.addEventListener("submit", function (e) {
    e.preventDefault();
    var out = document.getElementById("affPageOut"), err = document.getElementById("affPageErr");
    fetch("/my-account/affiliate/link/", { method: "POST", body: new FormData(pf), credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.error) { err.textContent = d.error; err.hidden = false; out.hidden = true; return; }
        err.hidden = true; out.hidden = false; out.querySelector("input").value = d.link; out.querySelector("button").setAttribute("data-copy", d.link);
      });
  });
})();
