/* فرشستان «فروشگاه تخصصی»: رفتارهای مشترک همهٔ صفحه‌ها — سربرگ، مگامنو، جستجوی زنده، کشو و برگه‌های پایین،
   ریل‌ها، اسلایدر و سایزیاب صفحهٔ اول، فیلتر قیمت، سینی و جدول مقایسه، پیام کوتاه.
   همهٔ پیوندها و فرم‌ها بدون این فایل هم کار می‌کنند؛ این‌جا فقط بهترشان می‌کند. */
(function () {
  "use strict";
  var d = document;
  function $(s, r) { return (r || d).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || d).querySelectorAll(s)); }
  var RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var FAD = "۰۱۲۳۴۵۶۷۸۹";
  function fa(s) { return String(s).replace(/\d/g, function (c) { return FAD[c]; }).replace(/\./g, "٫"); }
  function money(n) { return fa(Math.round(+n || 0).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",")).replace(/,/g, "٬"); }
  function toEn(s) { return String(s || "").replace(/[۰-۹]/g, function (c) { return FAD.indexOf(c); }).replace(/[٠-٩]/g, function (c) { return "٠١٢٣٤٥٦٧٨٩".indexOf(c); }); }
  function num(s) { return +toEn(s).replace(/[٫,\/]/g, ".").replace(/[^\d.]/g, "") || 0; }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function ic(n, c) { return '<svg class="ic ' + (c || "") + '" aria-hidden="true"><use href="#i-' + n + '"/></svg>'; }
  function isMobile() { return window.matchMedia("(max-width:860px)").matches; }
  var store = {
    get: function (k, def) { try { var v = window.localStorage.getItem(k); return v ? JSON.parse(v) : def; } catch (e) { return def; } },
    set: function (k, v) { try { window.localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* حالت خصوصی: بی‌صدا */ } }
  };
  var FS = window.FS = { $: $, $$: $$, RM: RM, fa: fa, money: money, toEn: toEn, num: num, clamp: clamp, esc: esc, ic: ic, isMobile: isMobile, store: store };

  /* ---------- پیام کوتاه */
  var toastT;
  FS.toast = function (html) {
    var t = $("#toast"); if (!t) return;
    t.innerHTML = ic("check") + "<span>" + html + "</span>";
    t.classList.add("show");
    clearTimeout(toastT); toastT = setTimeout(function () { t.classList.remove("show"); }, 3200);
  };

  /* ---------- rug.js تنبل برای فرش‌های بی‌عکس: <canvas data-rug="seed,palette,knotsX"> */
  var rugP = null, me = d.currentScript;
  var rugSrc = me ? me.src.replace(/theme\.js(\?.*)?$/, "rug.js$1") : "/static/js/rug.js";
  FS.rug = function () {
    if (window.FarshRug) return Promise.resolve(window.FarshRug);
    if (rugP) return rugP;
    rugP = new Promise(function (ok, no) { var s = d.createElement("script"); s.src = rugSrc; s.async = true; s.onload = function () { ok(window.FarshRug); }; s.onerror = no; d.head.appendChild(s); });
    return rugP;
  };
  var PALS = ["silver", "cream", "navy", "lacquer", "beige", "metallic", "charcoal", "turquoise"];
  function drawRug(c) {
    var a = c.getAttribute("data-rug").split(","), seed = +a[0] || 7, w = c.clientWidth, h = c.clientHeight;
    if (!w || !h || !window.FarshRug) return;
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
    try { FarshRug.render(c, { design: FarshRug.design(seed, PALS[seed % PALS.length]), knotsX: +a[2] || 70, fringe: true }); } catch (e) { /* بی‌صدا */ }
  }
  FS.hydrate = function (root) {
    var list = $$("canvas[data-rug]:not([data-done])", root);
    if (!list.length) return;
    list.forEach(function (c) { c.setAttribute("data-done", "1"); });
    if (!("IntersectionObserver" in window)) { FS.rug().then(function () { list.forEach(drawRug); }); return; }
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (!e.isIntersecting) return; io.unobserve(e.target); FS.rug().then(function () { drawRug(e.target); }); });
    }, { rootMargin: "300px 300px" });
    list.forEach(function (c) { io.observe(c); });
  };
  FS.hydrate(d);

  /* ---------- لایه‌ها: کشو، برگهٔ پایین، پنجره */
  var openEl = null, lastFocus = null, bd = $("#backdrop");
  FS.open = function (el, opener) {
    if (!el) return;
    FS.close(true);
    lastFocus = opener || d.activeElement; openEl = el;
    if (el.classList.contains("filters2")) el.classList.add("open"); else el.hidden = false;
    if (bd) bd.hidden = false;
    d.documentElement.style.overflow = "hidden";
    $$('[aria-controls="' + el.id + '"]').forEach(function (b) { b.setAttribute("aria-expanded", "true"); });
    setTimeout(function () { var f = $("[data-close-sheet],[data-close-modal],button,a,input", el); if (f) f.focus(); }, 40);
  };
  FS.close = function (silent) {
    if (!openEl) return;
    var el = openEl; openEl = null;
    if (el.classList.contains("filters2")) el.classList.remove("open"); else el.hidden = true;
    if (bd) bd.hidden = true;
    d.documentElement.style.overflow = "";
    $$('[aria-controls="' + el.id + '"]').forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
    if (!silent && lastFocus && lastFocus.focus) lastFocus.focus();
    el.dispatchEvent(new CustomEvent("fs:close"));
  };
  FS.isOpen = function (el) { return openEl === el; };
  if (bd) bd.addEventListener("click", function () { FS.close(); });
  d.addEventListener("keydown", function (e) { if (e.key === "Escape" && openEl) FS.close(); });
  d.addEventListener("click", function (e) {
    var t = e.target;
    if (t.closest("[data-close-sheet],[data-close-modal]")) { e.preventDefault(); FS.close(); return; }
    var dr = t.closest("[data-drawer]"); if (dr) { e.preventDefault(); FS.open($("#drawer"), dr); return; }
    var sh = t.closest("[data-sheet]"); if (sh) { e.preventDefault(); FS.open(d.getElementById(sh.getAttribute("data-sheet")), sh); return; }
    var fm = t.closest(".fmodal"); if (fm && t === fm) { FS.close(); }
  });
  var drawer = $("#drawer");
  if (drawer) drawer.addEventListener("click", function (e) { var a = e.target.closest("a[href]"); if (a && a.getAttribute("href").indexOf("#") === -1) FS.close(true); else if (a && /#sizeyab$/.test(a.getAttribute("href"))) FS.close(true); });

  /* ---------- سربرگ: ارتفاع برای چسبیدن‌ها و پنهان شدن جستجوی موبایل با اسکرول */
  var hdr = $("#hdr");
  if (hdr) {
    var setH = function () { d.documentElement.style.setProperty("--hdr-h", hdr.offsetHeight + "px"); };
    if ("ResizeObserver" in window) new ResizeObserver(setH).observe(hdr); setH();
    var lastY = 0;
    addEventListener("scroll", function () { var y = window.scrollY; if (isMobile()) hdr.classList.toggle("hide-search", y > 140 && y > lastY); lastY = y; }, { passive: true });
  }

  /* ---------- مگامنو */
  var mw = $("#megaWrap"), mb = $("#megaBtn"), mega = $("#mega");
  if (mw && mb && mega) {
    var mt;
    var setMega = function (v) { mb.setAttribute("aria-expanded", String(v)); mega.hidden = !v; };
    mw.addEventListener("mouseenter", function () { clearTimeout(mt); mt = setTimeout(function () { setMega(true); }, 120); });
    mw.addEventListener("mouseleave", function () { clearTimeout(mt); mt = setTimeout(function () { setMega(false); }, 180); });
    mb.addEventListener("click", function (e) { e.preventDefault(); setMega(mega.hidden); if (!mega.hidden) { var f = $("a", mega); if (f) f.focus(); } });
    mw.addEventListener("keydown", function (e) { if (e.key === "Escape" && !mega.hidden) { setMega(false); mb.focus(); } });
    mw.addEventListener("focusout", function (e) { if (!mw.contains(e.relatedTarget)) setMega(false); });
  }

  /* ---------- جستجوی زنده: دسته‌ها از دادهٔ همین صفحه، فرش‌ها از نتیجهٔ واقعی /search/ (بدون ثبت در آمار جستجو) */
  var q = $("#q"), box = $("#sugg"), qs = $("#qsearch");
  if (q && box && qs) {
    var CATS = [];
    try { CATS = JSON.parse($("#suggData").textContent).filter(function (x) { return x && x.t; }); } catch (e) { CATS = []; }
    var norm = function (s) { return toEn(s).replace(/ي/g, "ی").replace(/ك/g, "ک").replace(/[‌\s]+/g, " ").trim().toLowerCase(); };
    var match = function (text, s) { var t = norm(text), toks = norm(s).split(" ").filter(Boolean); return toks.length && toks.every(function (x) { return t.indexOf(x) > -1; }); };
    var hl = function (text, s) {
      var out = esc(text);
      norm(s).split(" ").filter(Boolean).forEach(function (tok) { var f = fa(tok), i = out.indexOf(f); if (i < 0) { f = tok; i = out.indexOf(f); } if (i >= 0) out = out.slice(0, i) + "<mark>" + f + "</mark>" + out.slice(i + f.length); });
      return out;
    };
    var catIcon = function (c) {
      if (c.c) return '<span class="sg-ic"><span class="sw" style="background:' + esc(c.c) + '"></span></span>';
      var i = c.i || "i-grid", cls = i.indexOf("d-") === 0 ? "dens" : i.indexOf("p-") === 0 ? "pat" : "ic";
      return '<span class="sg-ic"><svg class="' + cls + '" aria-hidden="true"><use href="#' + esc(i) + '"/></svg></span>';
    };
    var items = [], cur = -1, ctl = null, timer = 0, lastQ = null, cache = {};
    var closeBox = function () { box.hidden = true; q.setAttribute("aria-expanded", "false"); cur = -1; };
    var setItems = function () {
      items = $$(".sg", box);
      items.forEach(function (it, i) { it.id = "sg" + i; it.setAttribute("role", "option"); it.setAttribute("aria-selected", "false"); });
      box.hidden = false; q.setAttribute("aria-expanded", "true"); cur = -1;
    };
    var popular = CATS.slice(0, 6);
    var renderEmpty = function () {
      box.innerHTML = (popular.length ? "<h4>دسته‌های پرطرفدار</h4>" + popular.map(function (c) { return '<a class="sg" href="' + esc(c.h) + '">' + catIcon(c) + '<span class="sg-t">' + esc(c.t) + "<small>" + esc(c.s || "") + "</small></span></a>"; }).join("") : "") +
        '<h4>میان‌بر</h4><a class="sg" href="/#sizeyab"><span class="sg-ic">' + ic("ruler", "ic-sm") + '</span><span class="sg-t">سایزیاب<small>سایز مناسب اتاقتان را پیدا کنید</small></span></a>' +
        '<a class="sg" href="/carpets-price-list/"><span class="sg-ic">' + ic("list", "ic-sm") + '</span><span class="sg-t">لیست قیمت امروز<small>قیمت همهٔ سایزها</small></span></a>';
      setItems();
    };
    var renderQ = function (s, prods, loading) {
      var cats = CATS.filter(function (c) { return match(c.t, s); }).slice(0, 4), h = "";
      if (cats.length) h += "<h4>دسته‌ها</h4>" + cats.map(function (c) { return '<a class="sg" href="' + esc(c.h) + '">' + catIcon(c) + '<span class="sg-t">' + hl(c.t, s) + "<small>" + esc(c.s || "") + "</small></span></a>"; }).join("");
      if (prods && prods.length) h += "<h4>فرش‌ها</h4>" + prods.map(function (p) {
        return '<a class="sg" href="' + esc(p.u) + '">' + (p.img ? '<img src="' + esc(p.img) + '" alt="" loading="lazy">' : '<span class="sg-ic">' + ic("image", "ic-sm") + "</span>") +
          '<span class="sg-t">' + hl(p.t, s) + "<small>" + (p.r ? fa(p.r) + " شانه" : "") + (p.tex ? " · " + esc(p.tex) : "") + '</small></span><span class="sg-p">' + (p.out ? "ناموجود" : p.p ? "از " + money(p.p) + " تومان" : "") + "</span></a>";
      }).join("");
      if (loading) h += '<p class="sugg-load">در حال جستجو در فرش‌ها…</p>';
      else if (!h) h = "<h4>نتیجه‌ای برای «" + esc(s) + "» پیدا نشد</h4>" + (popular.length ? '<div class="sugg-chips">' + popular.slice(0, 4).map(function (c) { return '<a href="' + esc(c.h) + '">' + esc(c.t) + "</a>"; }).join("") + "</div>" : "");
      h += '<div class="sugg-all"><a class="link" href="/search/?q=' + encodeURIComponent(s) + '">همهٔ نتیجه‌ها برای «' + esc(s) + "»" + ic("chl", "ic-sm") + "</a></div>";
      box.innerHTML = h; setItems();
    };
    var parse = function (html) {
      var doc = new DOMParser().parseFromString(html, "text/html");
      return $$("article.pc[data-id]", doc).slice(0, 5).map(function (a) { var ds = a.dataset; return { t: ds.t, u: ds.u, img: ds.img, r: ds.r, tex: ds.tex, p: ds.p, out: ds.out }; });
    };
    var run = function () {
      var s = q.value.trim();
      if (s === lastQ && !box.hidden) return;
      lastQ = s;
      if (!s) { renderEmpty(); return; }
      if (cache[s]) { renderQ(s, cache[s]); return; }
      renderQ(s, null, s.length >= 2);
      if (s.length < 2) return;
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (ctl && ctl.abort) ctl.abort();
        ctl = "AbortController" in window ? new AbortController() : null;
        fetch("/search/?q=" + encodeURIComponent(s) + "&p=1", { credentials: "same-origin", signal: ctl ? ctl.signal : undefined })
          .then(function (r) { return r.ok ? r.text() : ""; })
          .then(function (html) { var list = html ? parse(html) : []; cache[s] = list; if (q.value.trim() === s) renderQ(s, list); })
          .catch(function () { /* قطع شد یا لغو شد */ });
      }, 280);
    };
    q.addEventListener("input", function () { lastQ = null; run(); });
    q.addEventListener("focus", function () { lastQ = null; run(); });
    q.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault(); if (!items.length) return;
        cur = (cur + (e.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
        items.forEach(function (it, i) { it.setAttribute("aria-selected", String(i === cur)); });
        q.setAttribute("aria-activedescendant", items[cur].id); items[cur].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Enter" && cur >= 0) { e.preventDefault(); items[cur].click(); }
      else if (e.key === "Escape") { closeBox(); if (d.body.classList.contains("search-open")) closeSearch(); }
    });
    d.addEventListener("click", function (e) { if (!qs.contains(e.target) && !e.target.closest("#btnMSearch")) closeBox(); });
    var closeSearch = function () { d.body.classList.remove("search-open"); closeBox(); q.blur(); };
    var ms = $("#btnMSearch");
    if (ms) ms.addEventListener("click", function () { d.body.classList.add("search-open"); q.focus(); });
    var sc = $("#searchClose"); if (sc) sc.addEventListener("click", closeSearch);
    if (isMobile() && q.dataset.short) q.placeholder = q.dataset.short;
  }

  /* ---------- ریل‌های افقی */
  $$("[data-rail]").forEach(function (r) {
    var tr = $(".rail-track", r); if (!tr) return;
    r.insertAdjacentHTML("beforeend", '<button class="rail-nav prev" type="button" aria-label="قبلی">' + ic("chr") + '</button><button class="rail-nav next" type="button" aria-label="بعدی">' + ic("chl") + "</button>");
    var pv = $(".rail-nav.prev", r), nx = $(".rail-nav.next", r);
    var upd = function () { var max = tr.scrollWidth - tr.clientWidth, x = Math.abs(tr.scrollLeft); pv.disabled = x < 4; nx.disabled = x > max - 4; };
    pv.addEventListener("click", function () { tr.scrollBy({ left: tr.clientWidth * .8, behavior: RM ? "auto" : "smooth" }); });
    nx.addEventListener("click", function () { tr.scrollBy({ left: -tr.clientWidth * .8, behavior: RM ? "auto" : "smooth" }); });
    tr.addEventListener("scroll", upd, { passive: true });
    setTimeout(upd, 120); addEventListener("resize", upd);
  });

  /* ---------- اسلایدر صفحهٔ اول */
  var sl = $("#slider");
  if (sl) {
    var slides = $$(".slide", sl), dots = $(".sl-dots", sl), si = 0, st;
    if (slides.length < 2) { $$(".sl-arrow", sl).forEach(function (b) { b.hidden = true; }); }
    else {
      dots.innerHTML = slides.map(function (_, k) { return '<button type="button" role="tab" aria-selected="' + (k === 0) + '" aria-label="اسلاید ' + fa(k + 1) + '"></button>'; }).join("");
      var show = function (n) {
        si = (n + slides.length) % slides.length;
        slides.forEach(function (s, k) { s.classList.toggle("is-active", k === si); s.setAttribute("aria-hidden", String(k !== si)); if (k !== si) s.setAttribute("inert", ""); else s.removeAttribute("inert"); });
        $$("button", dots).forEach(function (b, k) { b.setAttribute("aria-selected", String(k === si)); });
      };
      var play = function () { if (RM) return; clearInterval(st); st = setInterval(function () { show(si + 1); }, 6500); };
      var stop = function () { clearInterval(st); };
      $(".sl-arrow.prev", sl).addEventListener("click", function () { show(si - 1); play(); });
      $(".sl-arrow.next", sl).addEventListener("click", function () { show(si + 1); play(); });
      dots.addEventListener("click", function (e) { var b = e.target.closest("button"); if (b) { show($$("button", dots).indexOf(b)); play(); } });
      sl.addEventListener("mouseenter", stop); sl.addEventListener("mouseleave", play);
      sl.addEventListener("focusin", stop); sl.addEventListener("focusout", play);
      var x0 = null;
      sl.addEventListener("pointerdown", function (e) { x0 = e.clientX; });
      sl.addEventListener("pointerup", function (e) { if (x0 === null) return; var dx = e.clientX - x0; x0 = null; if (Math.abs(dx) > 40) { show(si + (dx > 0 ? 1 : -1)); play(); } });
      show(0); play();
    }
  }

  /* ---------- دکمه‌های + و − (سایزیاب و نقشهٔ اتاق) */
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-stp]"); if (!b) return;
    var a = b.getAttribute("data-stp").split(":"), inp = d.getElementById(a[0]); if (!inp) return;
    inp.value = fa(clamp(Math.round((num(inp.value) + (+a[1])) * 10) / 10, +inp.dataset.min || 1, +inp.dataset.max || 20));
    inp.dispatchEvent(new Event("input", { bubbles: true }));
  });
  d.addEventListener("focusout", function (e) { var i = e.target; if (i.matches && i.matches("input[data-min]") && i.value) i.value = fa(clamp(num(i.value), +i.dataset.min, +i.dataset.max)); });

  /* ---------- سایزیاب صفحهٔ اول (سایزهای واقعی فعال، لینک به /shop/?size=) */
  var sy = $("#sizeyab"), syData = $("#sizesData");
  if (sy && syData) {
    var SZ = []; try { SZ = JSON.parse(syData.textContent) || []; } catch (e) { SZ = []; }
    var type = "liv", L = $("#syL"), W = $("#syW"), out = $("#syRes");
    var dim = function (s) { return fa(s.l) + "×" + fa(s.w); };
    var calc = function () {
      var l = clamp(num(L.value), 0, 30), w = clamp(num(W.value), 0, 30), big = Math.max(l, w), small = Math.min(l, w);
      if (!big || !small || !SZ.length) { out.innerHTML = '<p class="pr-note">طول و عرض اتاق را وارد کنید.</p>'; return; }
      var kinds = type === "hall" ? ["runner"] : type === "bed" ? ["rect", "rug"] : ["rect", "rug"];
      var m = type === "hall" ? .15 : type === "bed" ? .45 : .3;
      var fits = SZ.filter(function (s) { return kinds.indexOf(s.type) > -1 && s.w <= small - 2 * m + 1e-9 && s.l <= big - 2 * m + 1e-9; })
        .sort(function (a, b) { return type === "hall" ? b.l - a.l : b.area - a.area; });
      if (!fits.length) {
        var small1 = SZ.filter(function (s) { return s.type === "rug" || s.type === "doormat"; }).sort(function (a, b) { return b.area - a.area; })[0];
        out.innerHTML = '<div class="rwarn">' + ic("info") + "<span>این اتاق برای فرش‌های بزرگ کوچک است." + (small1 ? ' <a href="/shop/?size=' + encodeURIComponent(small1.slug) + '">' + esc(small1.name) + "</a> را ببینید." : "") + "</span></div>";
        return;
      }
      var best = fits[0], alts = fits.slice(1, 3);
      var cov = Math.round(best.w * best.l / (l * w) * 100);
      var mx = Math.round((small - best.w) / 2 * 100), my = Math.round((big - best.l) / 2 * 100);
      var sc = Math.min(100 / big, 76 / small), rw = big * sc, rh = small * sc, gw = best.l * sc, gh = best.w * sc;
      out.innerHTML = '<div class="sy-best"><svg viewBox="0 0 110 84" aria-hidden="true"><rect x="' + (110 - rw) / 2 + '" y="' + (84 - rh) / 2 + '" width="' + rw + '" height="' + rh + '" fill="#fff" stroke="#323C52" stroke-width="2.5" rx="1"/><rect x="' + (110 - gw) / 2 + '" y="' + (84 - gh) / 2 + '" width="' + gw + '" height="' + gh + '" fill="#DDE5F5" stroke="#1D3F8F" stroke-width="1.5" rx="1"/><rect x="' + ((110 - gw) / 2 + gw * .3) + '" y="' + ((84 - gh) / 2 + gh * .25) + '" width="' + gw * .4 + '" height="' + gh * .5 + '" fill="#C99A2E" opacity=".55" rx="' + gh * .2 + '"/></svg>' +
        '<div><small>سایز پیشنهادی<span class="sy-tag">بهترین</span></small><b>' + esc(fa(best.name)) + " · " + dim(best) + "</b>" +
        '<div class="meta">پوشش کف ' + fa(cov) + "٪ · فاصله از دیوار " + (mx === my ? fa(mx) : fa(Math.min(mx, my)) + " تا " + fa(Math.max(mx, my))) + " سانتی‌متر" + (best.count ? " · " + fa(best.count) + " طرح" : "") + "</div></div></div>" +
        (alts.length ? '<div class="sy-alt">جایگزین: ' + alts.map(function (s) { return '<a href="/shop/?size=' + encodeURIComponent(s.slug) + '">' + esc(fa(s.name)) + " · " + dim(s) + "</a>"; }).join("") + "</div>" : "") +
        '<a class="fbtn fbtn--primary fbtn--block" href="/shop/?size=' + encodeURIComponent(best.slug) + '">مشاهدهٔ فرش‌های ' + esc(fa(best.name)) + (best.min_price ? " · از " + money(best.min_price) + " تومان" : "") + ic("chl", "ic-sm") + "</a>";
    };
    $("#syType").addEventListener("click", function (e) { var b = e.target.closest("button"); if (!b) return; type = b.dataset.t; $$("#syType button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); }); calc(); });
    [L, W].forEach(function (i) { i.addEventListener("input", calc); });
    calc();
  }

  /* ---------- بازهٔ قیمت (دو لغزنده؛ ارسال با min و max) */
  var pf = $("#priceForm");
  if (pf) {
    var lo = +pf.dataset.lo, hi = +pf.dataset.hi, rs = $$('input[type=range]', pf), fill = $(".fill", pf), tmin = $('input[name=min]', pf), tmax = $('input[name=max]', pf);
    var paint = function () {
      var a = Math.min(+rs[0].value, +rs[1].value), b = Math.max(+rs[0].value, +rs[1].value);
      fill.style.right = ((a - lo) / (hi - lo) * 100) + "%"; fill.style.left = (100 - (b - lo) / (hi - lo) * 100) + "%";
    };
    rs.forEach(function (r) {
      r.addEventListener("input", function () {
        var a = Math.min(+rs[0].value, +rs[1].value), b = Math.max(+rs[0].value, +rs[1].value);
        tmin.value = a > lo ? money(a) : ""; tmax.value = b < hi ? money(b) : ""; paint();
      });
    });
    [tmin, tmax].forEach(function (t, k) { if (t.value) t.value = money(num(t.value)); t.addEventListener("change", function () { var v = num(t.value); t.value = v ? money(v) : ""; if (v) rs[k].value = v; paint(); }); });
    pf.addEventListener("submit", function () {
      [tmin, tmax].forEach(function (t) { var v = num(t.value); t.value = v ? String(Math.round(v)) : ""; if (!t.value) t.disabled = true; });
    });
    paint();
  }

  /* ---------- مقایسه: سینی پایین صفحه (localStorage) و جدول مقایسه */
  var KEY = "fs_cmp", MAX = 3;
  var cmp = store.get(KEY, []); if (!Array.isArray(cmp)) cmp = [];
  var tray = $("#cmpTray");
  function dataOf(el) { var ds = el.dataset; return { id: +ds.id, t: ds.t, u: ds.u, img: ds.img, r: ds.r, tex: ds.tex, p: +ds.p || 0, rt: ds.rt || "", rc: +ds.rc || 0, out: !!ds.out }; }
  function has(id) { return cmp.some(function (x) { return x.id === id; }); }
  function save() { store.set(KEY, cmp); }
  FS.cmp = { list: function () { return cmp.slice(); }, has: has };
  FS.cmpToggle = function (item, on) {
    var i = -1; cmp.forEach(function (x, k) { if (x.id === item.id) i = k; });
    if (on && i < 0) {
      if (cmp.length >= MAX) { FS.toast("حداکثر " + fa(MAX) + " فرش را می‌توانید کنار هم مقایسه کنید."); syncChecks(); return false; }
      cmp.push(item);
    } else if (!on && i >= 0) cmp.splice(i, 1);
    save(); syncChecks(); updateTray(); d.dispatchEvent(new CustomEvent("fs:cmp"));
    return true;
  };
  function syncChecks() {
    $$("[data-cmp]").forEach(function (c) { c.checked = has(+c.getAttribute("data-cmp")); });
    $$("[data-cmp-btn]").forEach(function (b) { b.setAttribute("aria-pressed", String(has(+b.getAttribute("data-cmp-btn")))); });
  }
  function updateTray() {
    if (!tray) return;
    var show = cmp.length > 0;
    tray.hidden = !show; d.body.classList.toggle("has-tray", show);
    if (!show) return;
    var h = "";
    for (var i = 0; i < MAX; i++) {
      var p = cmp[i];
      h += p ? '<div class="cmp-slot">' + (p.img ? '<img src="' + esc(p.img) + '" alt="">' : "") + "<span>" + esc(p.t) + '</span><button type="button" data-uncmp="' + p.id + '" aria-label="حذف ' + esc(p.t) + ' از مقایسه">' + ic("close", "ic-sm") + "</button></div>"
        : '<div class="cmp-slot empty">' + (i === 1 ? "فرش دوم را انتخاب کنید" : "فرش سوم (اختیاری)") + "</div>";
    }
    $("#cmpSlots").innerHTML = h;
    var g = $("#cmpGo"), self = $("#pdSelf");
    var need = self ? 1 : 2;
    g.disabled = cmp.length < need; g.textContent = "مقایسه (" + fa(cmp.length + (self && !has(+self.dataset.id) ? 1 : 0)) + ")";
  }
  d.addEventListener("change", function (e) {
    var c = e.target.closest("[data-cmp]"); if (!c) return;
    var card = c.closest("[data-id]"); if (!card) return;
    if (!FS.cmpToggle(dataOf(card), c.checked)) c.checked = false;
  });
  if (tray) {
    $("#cmpSlots").addEventListener("click", function (e) { var b = e.target.closest("[data-uncmp]"); if (b) FS.cmpToggle({ id: +b.getAttribute("data-uncmp") }, false); });
    $("#cmpClear").addEventListener("click", function () { cmp = []; save(); syncChecks(); updateTray(); d.dispatchEvent(new CustomEvent("fs:cmp")); });
    $("#cmpGo").addEventListener("click", function () {
      var pc = $("#p-compare");
      if (pc) { pc.scrollIntoView({ behavior: RM ? "auto" : "smooth", block: "start" }); return; }
      $("#cmpModalB").innerHTML = FS.cmpTable(cmp, null);
      FS.open($("#cmpModal"), this);
    });
  }
  /* جدول مقایسه با دادهٔ واقعی کارت‌ها: قیمت «از»، شانه، بافت، امتیاز (اگر هست)، وضعیت */
  FS.cmpTable = function (list, curId) {
    if (!list.length) return '<p class="muted">فرشی برای مقایسه انتخاب نشده است.</p>';
    var prices = list.map(function (x) { return x.out || !x.p ? Infinity : x.p; }), minP = Math.min.apply(null, prices);
    var reeds = list.map(function (x) { return +x.r || 0; }), maxR = Math.max.apply(null, reeds);
    var rate = list.map(function (x) { return x.rc ? +toEn(x.rt).replace("٫", ".") : 0; }), maxRate = Math.max.apply(null, rate);
    var rows = [
      ["قیمت (از)", list.map(function (x, i) { return x.out ? '<span class="out">ناموجود</span>' : x.p ? '<span class="pp">' + money(x.p) + "</span> تومان" + (prices[i] === minP && list.length > 1 && prices.filter(function (v) { return v === minP; }).length === 1 ? '<span class="best">ارزان‌ترین</span>' : "") : "استعلام"; })],
      ["شانه", list.map(function (x, i) { return x.r ? fa(x.r) + (reeds[i] === maxR && reeds.some(function (v) { return v !== maxR; }) ? '<span class="best">ظریف‌ترین بافت</span>' : "") : "—"; })],
      ["نوع بافت", list.map(function (x) { return x.tex || "—"; })],
      ["امتیاز خریداران", list.map(function (x, i) { return x.rc ? fa(x.rt) + " از ۵ (" + fa(x.rc) + ")" + (rate[i] === maxRate && rate.some(function (v) { return v !== maxRate; }) ? '<span class="best">بیشترین</span>' : "") : "بدون دیدگاه"; })],
      ["وضعیت", list.map(function (x) { return x.out ? "ناموجود" : "موجود"; })]
    ];
    var head = list.map(function (x) {
      return '<td class="' + (x.id === curId ? "cur" : "") + '"><div class="ch">' + (x.id !== curId ? '<button type="button" class="rm" data-uncmp-t="' + x.id + '" aria-label="حذف ' + esc(x.t) + ' از مقایسه">' + ic("close", "ic-sm") + "</button>" : "") +
        (x.img ? '<img src="' + esc(x.img) + '" alt="" loading="lazy">' : "") + (x.id === curId ? '<span class="cur-tag">همین فرش</span>' : "") + '<a href="' + esc(x.u) + '">' + esc(x.t) + "</a></div></td>";
    }).join("");
    return '<div class="tbl-wrap"><table class="ctbl"><caption class="sr-only">جدول مقایسهٔ فرش‌ها</caption><thead><tr><th scope="row" style="background:#fff;border-top:0"><span class="sr-only">فرش</span></th>' + head + "</tr></thead><tbody>" +
      rows.map(function (r) { return '<tr><th scope="row">' + r[0] + "</th>" + r[1].map(function (c, i) { return '<td class="' + (list[i].id === curId ? "cur" : "") + '">' + c + "</td>"; }).join("") + "</tr>"; }).join("") + "</tbody></table></div>";
  };
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-uncmp-t]"); if (!b) return;
    FS.cmpToggle({ id: +b.getAttribute("data-uncmp-t") }, false);
    var mb2 = $("#cmpModalB"); if (mb2 && FS.isOpen($("#cmpModal"))) { if (cmp.length) mb2.innerHTML = FS.cmpTable(cmp, null); else FS.close(); }
  });
  syncChecks(); updateTray();

  /* ---------- ارقام فارسی در ورودی‌های عددی پیش از ارسال */
  d.addEventListener("submit", function (e) {
    $$('input[inputmode="decimal"],input[inputmode="numeric"],input[type=number]', e.target).forEach(function (i) { i.value = toEn(i.value); });
  }, true);
})();
