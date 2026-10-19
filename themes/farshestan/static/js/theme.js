/* فرشستان «خانهٔ ایرانی»: رفتارهای مشترک همهٔ صفحه‌ها (سربرگ، منوها، جستجو، طاق‌ها، کشوها).
   همه‌چیز بدون این فایل هم کار می‌کند (پیوند واقعی و ‎:target)؛ این‌جا فقط بهترش می‌کند. */
(function () {
  "use strict";
  var d = document;
  function $(s, r) { return (r || d).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || d).querySelectorAll(s)); }
  var RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var FH = window.FarshHouse = { $: $, $$: $$, RM: RM };
  FH.fa = function (x) { return String(x).replace(/[0-9]/g, function (c) { return "۰۱۲۳۴۵۶۷۸۹"[c]; }).replace(/\./g, "٫"); };
  FH.en = function (s) { return String(s).replace(/[۰-۹]/g, function (c) { return "۰۱۲۳۴۵۶۷۸۹".indexOf(c); }).replace(/[٠-٩]/g, function (c) { return "٠١٢٣٤٥٦٧٨٩".indexOf(c); }).replace(/[٫,\/]/g, "."); };
  FH.clamp = function (v, a, b) { return Math.max(a === undefined ? 0 : a, Math.min(b === undefined ? 1 : b, v)); };

  /* ---------- طاق جناغی دقیق برای هر اندازه (پیش‌فرض CSS برای ۱ به ۱٫۸ است) */
  function archPoly(w, h) {
    var r = .62 * w, ha = Math.sqrt(r * r - (r - w / 2) * (r - w / 2)); if (ha > h) ha = h;
    var pts = [[0, h], [0, ha]], n = 12, a1 = Math.atan2(-ha, w / 2 - r) + 2 * Math.PI, a2 = Math.atan2(-ha, r - w / 2), i, a;
    for (i = 1; i <= n; i++) { a = Math.PI + (a1 - Math.PI) * i / n; pts.push([r + r * Math.cos(a), ha + r * Math.sin(a)]); }
    for (i = 1; i <= n; i++) { a = a2 + (0 - a2) * i / n; pts.push([w - r + r * Math.cos(a), ha + r * Math.sin(a)]); }
    pts.push([w, h]);
    return "polygon(" + pts.map(function (p) { return (p[0] / w * 100).toFixed(2) + "% " + (p[1] / h * 100).toFixed(2) + "%"; }).join(",") + ")";
  }
  if ("ResizeObserver" in window) {
    var aro = new ResizeObserver(function (es) {
      es.forEach(function (e) { var el = e.target, w = el.clientWidth, h = el.clientHeight; if (w && h) el.style.clipPath = archPoly(w, h); });
    });
    FH.archify = function (root) { $$(".arch-o,.arch-i,.niche-o,.niche-i,.by-arch,.by-arch>span", root).forEach(function (el) { if (!el._a) { el._a = 1; aro.observe(el); } }); };
    FH.archify(d);
  } else FH.archify = function () {};

  /* ---------- بارگذاری تنبل rug.js (فقط برای مقایسهٔ تراکم و فرش‌های بی‌عکس) */
  var rugP = null;
  FH.rug = function () {
    if (window.FarshRug) return Promise.resolve(window.FarshRug);
    if (rugP) return rugP;
    rugP = new Promise(function (ok, no) {
      var s = d.createElement("script");
      s.src = FH.rugSrc; s.async = true;
      s.onload = function () { ok(window.FarshRug); }; s.onerror = no;
      d.head.appendChild(s);
    });
    return rugP;
  };
  var me = d.currentScript;
  FH.rugSrc = me ? me.src.replace(/theme\.js(\?.*)?$/, "rug.js$1") : "/static/js/rug.js";
  FH.drawRug = function (c, o) {
    var dpr = Math.min(2, window.devicePixelRatio || 1), w = c.clientWidth, h = c.clientHeight;
    if (!w || !h || !window.FarshRug) return false;
    c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
    FarshRug.render(c, { design: o.design || FarshRug.design(o.seed, o.pal), knotsX: o.knotsX || 80, fringe: o.fringe !== false, crop: o.crop });
    return true;
  };
  // فرش‌های بی‌عکس: <canvas data-rug="seed,palette,knotsX">
  var lazyRugs = $$("canvas[data-rug]");
  if (lazyRugs.length && "IntersectionObserver" in window) {
    var PALS = ["silver", "cream", "navy", "lacquer", "beige", "metallic", "charcoal", "turquoise"];
    var rio = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting) return;
        rio.unobserve(e.target);
        var a = e.target.getAttribute("data-rug").split(","), seed = +a[0] || 7;
        FH.rug().then(function () { FH.drawRug(e.target, { seed: seed, pal: PALS[seed % PALS.length], knotsX: +a[2] || 70 }); });
      });
    }, { rootMargin: "300px 0px" });
    lazyRugs.forEach(function (c) { rio.observe(c); });
  }

  /* ---------- فرش لوله‌شده‌ای که باز می‌شود. dir: "x" (از راست به چپ روی زمین) یا "y" (از بالا به پایین) */
  FH.ease = function (t) { return 1 - Math.pow(1 - t, 3); };
  FH.easeIO = function (t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
  FH.Unroll = function (el, dir) {
    var sheet = $(".ur-sheet", el), roll = $(".ur-roll", el), self = { p: -1 };
    self.set = function (p) {
      p = FH.clamp(p); if (Math.abs(p - self.p) < .0005) return; self.p = p;
      var W = el.clientWidth, H = el.clientHeight, d0 = dir === "x" ? Math.max(26, H * .17) : Math.max(26, W * .15), dd = d0 * Math.sqrt(1 - p * .82);
      if (dir === "x") {
        sheet.style.clipPath = "inset(0 0 0 " + ((1 - p) * 100).toFixed(3) + "%)"; roll.style.width = dd + "px";
        roll.style.transform = "translateX(" + ((1 - p) * W - dd / 2).toFixed(1) + "px)";
      } else {
        sheet.style.clipPath = "inset(0 0 " + ((1 - p) * 100).toFixed(3) + "% 0)"; roll.style.height = dd + "px";
        roll.style.transform = "translateY(" + (p * H - dd / 2).toFixed(1) + "px)";
      }
      roll.style.opacity = p > .985 ? 0 : 1;
    };
    self.play = function (ms, from) {
      if (RM) { self.set(1); return; }
      var t0 = performance.now(), f0 = from || 0; self.p = -1; self.set(f0);
      (function f(t) { var k = FH.clamp((t - t0) / (ms || 1800)); self.set(f0 + (1 - f0) * FH.easeIO(k)); if (k < 1) requestAnimationFrame(f); })(t0);
    };
    // رنگ لوله از خود عکس: حاشیه، زمینه و ترنج
    self.tex = function () {
      var img = $("img", sheet); if (!img) return;
      function go() {
        try {
          var box = img.parentNode, cs = getComputedStyle(box), cx = +cs.getPropertyValue("--cx") || 0, cy = +cs.getPropertyValue("--cy") || 0,
            cw = +cs.getPropertyValue("--cw") || 100, ch = +cs.getPropertyValue("--ch") || 100, c = d.createElement("canvas"), N = 24;
          c.width = N; c.height = N; var x = c.getContext("2d");
          var iw = img.naturalWidth, ih = img.naturalHeight;
          x.drawImage(img, iw * cx / 100, ih * cy / 100, iw * cw / 100, ih * ch / 100, 0, 0, N, N);
          var px = x.getImageData(0, 0, N, N).data;
          function col(i, j) { var k = (j * N + i) * 4; return "rgb(" + px[k] + "," + px[k + 1] + "," + px[k + 2] + ")"; }
          var g = dir === "x" ? "180deg" : "90deg", mid = Math.floor(N / 2);
          var b = col(1, mid), gd = col(3, mid), f = col(6, mid), m = col(mid, mid), f2 = col(9, mid);
          el.style.setProperty("--rtex", "linear-gradient(" + g + "," + b + " 0 8%," + gd + " 8% 12%," + f + " 12% 32%," + f2 + " 32% 42%," + m + " 42% 58%," + f2 + " 58% 68%," + f + " 68% 88%," + gd + " 88% 92%," + b + " 92%)");
        } catch (e) { /* تصویر از دامنهٔ دیگر: رنگ پیش‌فرض */ }
      }
      if (img.complete && img.naturalWidth) go(); else img.addEventListener("load", go, { once: true });
    };
    self.tex();
    return self;
  };

  /* ---------- دسته‌ها (منوی بزرگ) */
  var cb = $("#cats-btn"), mega = $("#h-mega");
  function closeMega() { if (mega && !mega.hidden) { mega.hidden = true; cb.setAttribute("aria-expanded", "false"); } }
  if (cb && mega) {
    cb.setAttribute("role", "button");
    cb.addEventListener("click", function (e) {
      e.preventDefault();
      var open = mega.hidden; mega.hidden = !open; cb.setAttribute("aria-expanded", String(open));
      if (open) { var f = $("a", mega); if (f) f.focus(); }
    });
  }
  /* ---------- پیام‌رسان‌ها (details) با کلیک بیرون بسته شود */
  d.addEventListener("click", function (e) {
    if (mega && !e.target.closest("#h-mega,#cats-btn")) closeMega();
    $$("details.h-msg[open]").forEach(function (m) { if (!m.contains(e.target)) m.open = false; });
  });

  /* ---------- کشوها: منوی موبایل و پالایش‌ها (بدون اسکریپت با ‎:target) */
  var openDr = null, lastFocus = null;
  function openDrawer(el, btn) {
    if (!el) return;
    if (openDr) closeDrawer();
    lastFocus = btn || d.activeElement; openDr = el;
    el.classList.add("on"); if (btn) btn.setAttribute("aria-expanded", "true");
    var sc = el.parentNode.querySelector(".h-scrim") || $(".h-scrim"); if (sc) { sc.style.opacity = 1; sc.style.pointerEvents = "auto"; FH._sc = sc; }
    d.documentElement.style.overflow = "hidden";
    setTimeout(function () { var f = $("[data-close]", el) || $("a,button,input", el); if (f) f.focus(); }, 60);
  }
  function closeDrawer() {
    if (!openDr) return;
    openDr.classList.remove("on");
    $$('[aria-controls="' + openDr.id + '"]').forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    if (FH._sc) { FH._sc.style.opacity = ""; FH._sc.style.pointerEvents = ""; }
    d.documentElement.style.overflow = "";
    openDr = null; if (location.hash.length > 1 && $(location.hash.replace(/[^#\w-]/g, ""))) history.replaceState(null, "", location.pathname + location.search);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }
  FH.openDrawer = openDrawer; FH.closeDrawer = closeDrawer;
  $$('a[href^="#"][aria-controls]').forEach(function (a) {
    var el = d.getElementById(a.getAttribute("aria-controls"));
    if (!el || !el.matches(".h-drawer,.h-filters")) return;
    a.addEventListener("click", function (e) { e.preventDefault(); openDrawer(el, a); });
  });
  d.addEventListener("click", function (e) {
    var c = e.target.closest("[data-close]"); if (!c) return;
    var dl = c.closest("dialog"); e.preventDefault();
    if (dl) dl.close(); else closeDrawer();
  });
  d.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    closeMega(); if (openDr) closeDrawer();
    $$("details.h-msg[open]").forEach(function (m) { m.open = false; });
  });

  /* ---------- جستجو در کادر گفت‌وگو (بدون اسکریپت: صفحهٔ /search/) */
  var sb = $("#search-btn"), sd = $("#h-search");
  if (sb && sd && sd.showModal) {
    sb.addEventListener("click", function (e) {
      e.preventDefault(); closeMega(); sd.showModal(); var i = $("input[name=q]", sd); if (i) i.focus();
    });
    sd.addEventListener("click", function (e) { if (e.target === sd) sd.close(); });
  }

  /* ---------- ارقام فارسی در ورودی‌های عددی پیش از ارسال */
  d.addEventListener("submit", function (e) {
    $$('input[inputmode="decimal"],input[inputmode="numeric"],input[type=number]', e.target).forEach(function (i) { i.value = FH.en(i.value); });
  }, true);
})();
