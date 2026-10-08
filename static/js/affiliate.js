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

  // جستجوی فرش و پیوند هر فرش
  var q = document.getElementById("affQ"), box = document.getElementById("affResults");
  if (q && box) {
    var timer, last = null;
    var esc = function (s) { var d = document.createElement("div"); d.textContent = s; return d.innerHTML; };
    var load = function () {
      var v = q.value.trim(); if (v === last) return; last = v;
      fetch("/my-account/affiliate/products/?q=" + encodeURIComponent(v), { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d.items || !d.items.length) { box.innerHTML = '<li class="muted">فرشی پیدا نشد؛ کلمهٔ دیگری بنویسید.</li>'; return; }
          box.innerHTML = d.items.map(function (it) {
            return '<li><img src="' + esc(it.image) + '" alt="" loading="lazy" width="64" height="64"><div><b>' + esc(it.title) + "</b>" +
              (it.price ? "<small>از " + esc(it.price) + " تومان</small>" : "") + '<span dir="ltr">' + esc(it.link) + "</span></div>" +
              '<div class="aff-acts"><button class="pill" type="button" data-copy="' + esc(it.link) + '">کپی پیوند</button>' +
              '<button class="pill" type="button" data-copy="' + esc(it.text) + '">کپی متن آماده</button>' +
              '<a class="pill" target="_blank" rel="noopener" href="https://wa.me/?text=' + encodeURIComponent(it.text) + '">واتس‌اپ</a></div></li>';
          }).join("");
        }).catch(function () {});
    };
    q.addEventListener("input", function () { clearTimeout(timer); timer = setTimeout(load, 300); });
    load();
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
