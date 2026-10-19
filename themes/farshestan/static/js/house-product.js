/* فرشستان «خانهٔ ایرانی» — صفحهٔ فرش: باز شدن فرش، عکس‌ها، ذره‌بین گره‌ها از روی عکس خود فرش، نقشهٔ اتاق.
   همهٔ خرید بدون این فایل هم کار می‌کند (فرم buyForm و رادیوهای variation)؛ این‌جا فقط بهترش می‌کند. */
(function () {
  "use strict";
  var FH = window.FarshHouse; if (!FH) return;
  var d = document, $ = FH.$, $$ = FH.$$, RM = FH.RM, clamp = FH.clamp, fa = FH.fa, en = FH.en;
  var form = $("#buyForm"), GLASS = ["#2E5E9A", "#C6392B", "#E2B13C", "#2F8A57"];

  function radios() { return form ? $$('input[name="variation"]', form) : []; }
  function picked() { return form ? $('input[name="variation"]:checked', form) : null; }
  function faMoney(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "٬").replace(/\d/g, function (c) { return "۰۱۲۳۴۵۶۷۸۹"[c]; }); }

  /* ---------- تعداد و قیمت سایز انتخاب‌شده */
  if (form) {
    var qty = $('input[name="qty"]', form), price = $("#pd-price"), price0 = price ? price.innerHTML : "";
    $$("[data-q]", form).forEach(function (b) {
      b.addEventListener("click", function () {
        var r = picked(), st = r && r.dataset.pair ? 2 : 1, v = (+en(qty.value) || 1) + (+b.dataset.q) * st;
        qty.value = String(clamp(v, st, 20));
      });
    });
    var onSize = function () {
      var r = picked(); if (!r) return;
      if (price) {
        if (r.dataset.pt) price.innerHTML = (r.dataset.was ? "<del>" + r.dataset.was + "</del> " : "") + "<b>" + r.dataset.pt + "</b> <small>تومان · " + (r.dataset.label || "") + "</small>";
        else price.innerHTML = price0;
      }
      if (r.dataset.pair) { var q = +en(qty.value) || 1; if (q % 2) qty.value = String(q + 1); }
      var p = +r.dataset.price;
      var tl = $("#torobLine");
      if (tl && p) {
        tl.hidden = p > +tl.dataset.max;
        $("span", tl).textContent = p <= +tl.dataset.eachMax ? "۴ قسط " + faMoney(Math.ceil(p / 4)) + " تومان، بدون چک و ضامن" : "خرید ۴ قسطی بر اساس اعتبار شما در ترب‌پی";
      }
      var it = $("#instTeaser"); if (it && it.dataset.base && p) it.href = it.dataset.base + "?amount=" + p;
      if (PL.ready) { var k = sizeKey(r); if (k && k !== PL.key) { PL.key = k; plSizes(); plRender(true); } }
      if (K.ready) paintKnots();
    };
    form.addEventListener("change", function (e) { if (e.target.name === "variation") onSize(); });
  }

  /* ---------- فرش روی آجرفرش باز می‌شود */
  var rug = $("#pd-rug"), sheet = $("#pd-sheet"), UR = rug ? FH.Unroll(rug, "y") : null;
  function unroll() {
    if (!UR) return;
    var img = $("img", sheet);
    function go() { UR.tex(); UR.play(1700); }
    if (RM) { UR.set(1); return; }
    UR.set(0);
    if (!img || (img.complete && img.naturalWidth)) setTimeout(go, 120);
    else { img.addEventListener("load", go, { once: true }); img.addEventListener("error", function () { UR.set(1); }, { once: true }); }
  }
  unroll();
  var rp = $("#replay"); if (rp && UR) rp.addEventListener("click", function () { UR.play(1500); });

  /* ---------- عکس‌های دیگر */
  var crop = (rug && rug.dataset.crop || "0,0,100,100,0.6667").split(",").map(Number);
  $$(".gal-thumbs button").forEach(function (b) {
    b.addEventListener("click", function () {
      $$(".gal-thumbs button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      var box = $(".rugimg", sheet), img = $("img", sheet); if (!box || !img) return;
      crop = b.dataset.crop.split(",").map(Number);
      var st = "--ar:" + crop[4] + (crop[2] < 100 || crop[3] < 100 ? ";--cx:" + crop[0] + ";--cy:" + crop[1] + ";--cw:" + crop[2] + ";--ch:" + crop[3] : "");
      rug.setAttribute("style", st); box.setAttribute("style", st);
      img.srcset = b.dataset.set; img.src = b.dataset.src; rug.dataset.full = b.dataset.full; full = null;
      if (UR) { UR.set(1); if (!RM) img.addEventListener("load", function () { UR.tex(); UR.play(1100, .35); }, { once: true }); }
      if (K.ready) { K.x = .5; K.y = .5; paintKnots(); }
      if (PL.ready) plRender(false);
    });
  });

  /* ---------- ذره‌بین: گره‌ها از روی عکس خود فرش، با تراکم انتخاب‌شده */
  var lens = $("#pd-lens"), lc = lens && $("canvas", lens), kc = $("#knots canvas"), grp = $("#pd-sh"), say = $("#pd-say");
  var K = { x: .5, y: .5, on: false, ready: false }, full = null, PATCH = .04; // ۴ سانت از فرش زیر ذره‌بین
  var REEDS = +((grp && $("input:checked", grp)) || { value: 700 }).value;
  function shaneh() { var i = grp && $("input:checked", grp); return i ? +i.value : 700; }
  function rugWidthM() { var r = picked(); var w = r && +r.dataset.w, l = r && +r.dataset.l; return w && l ? Math.min(w, l) : 2.5; }
  function source() {
    var img = $("img", sheet);
    if (full && full.complete && full.naturalWidth) return full;
    if (!full && rug.dataset.full) { full = new Image(); full.decoding = "async"; full.onload = function () { if (K.ready) { paintKnots(); if (K.on) paintLens(); } }; full.src = rug.dataset.full; }
    return img && img.complete && img.naturalWidth ? img : null;
  }
  function knotPaint(c, x, y) {
    var img = source(); if (!img || !c) return;
    var dpr = Math.min(2, window.devicePixelRatio || 1), W = c.clientWidth || 160, S = Math.round(W * dpr);
    if (c.width !== S) { c.width = S; c.height = S; }
    var n = Math.max(8, Math.round(shaneh() * PATCH)), iw = img.naturalWidth, ih = img.naturalHeight;
    var f = PATCH / rugWidthM(), cw = iw * crop[2] / 100, ch = ih * crop[3] / 100, sw = Math.max(2, cw * f), sh = sw;
    var sx = clamp(iw * crop[0] / 100 + x * cw - sw / 2, 0, iw - sw), sy = clamp(ih * crop[1] / 100 + y * ch - sh / 2, 0, ih - sh);
    var t = d.createElement("canvas"); t.width = n; t.height = n;
    var tx = t.getContext("2d"); tx.imageSmoothingEnabled = true; tx.imageSmoothingQuality = "high";
    var px;
    try { tx.drawImage(img, sx, sy, sw, sh, 0, 0, n, n); px = tx.getImageData(0, 0, n, n).data; } catch (e) { return; }
    var g = c.getContext("2d"), cell = S / n;
    g.fillStyle = "#1a120c"; g.fillRect(0, 0, S, S);
    for (var j = 0; j < n; j++) for (var i = 0; i < n; i++) {
      var k = (j * n + i) * 4, r = px[k], gg = px[k + 1], b = px[k + 2], cx = (i + .5) * cell, cy = (j + .5) * cell;
      g.fillStyle = "rgb(" + (r * .62 | 0) + "," + (gg * .62 | 0) + "," + (b * .62 | 0) + ")";
      g.fillRect(i * cell, j * cell, cell + .5, cell + .5);
      // هر گره دو بازو دارد (گره فارسی)؛ دو بیضی کج کنار هم
      g.fillStyle = "rgb(" + r + "," + gg + "," + b + ")";
      g.beginPath(); g.ellipse(cx - cell * .2, cy, cell * .26, cell * .44, .32, 0, 6.2832); g.fill();
      g.beginPath(); g.ellipse(cx + cell * .2, cy, cell * .26, cell * .44, -.32, 0, 6.2832); g.fill();
      if (cell > 4) {
        g.fillStyle = "rgba(255,255,255,.16)";
        g.beginPath(); g.ellipse(cx - cell * .24, cy - cell * .14, cell * .08, cell * .2, .32, 0, 6.2832); g.fill();
        g.beginPath(); g.ellipse(cx + cell * .16, cy - cell * .14, cell * .08, cell * .2, -.32, 0, 6.2832); g.fill();
      }
    }
  }
  function paintKnots() { if (kc) knotPaint(kc, K.x, K.y); }
  function paintLens() { if (lc) knotPaint(lc, K.x, K.y); }
  var SAY = { 700: "گره‌ها درشت‌ترند؛ نقش‌ها ساده‌تر و پررنگ دیده می‌شوند.", 1000: "گره‌ها ریزترند؛ مرز رنگ‌ها نرم‌تر است.",
    1200: "پیچ‌وتاب گل‌ها و برگ‌ها با جزئیات بیشتری بافته می‌شود.", 1500: "ریزترین گره‌ها؛ از فاصلهٔ معمول، نقش تقریباً مثل نقاشی دیده می‌شود." };
  function sayText() {
    if (!say) return; var s = shaneh();
    say.innerHTML = (s === REEDS ? "این فرش " + fa(s) + " شانه است" : "اگر همین نقش " + fa(s) + " شانه بود") +
      "؛ در هر ۱۰ سانت از عرض فرش حدود <b>" + fa(Math.round(s / 10)) + " گره</b> کنار هم می‌نشیند. " + (SAY[s] || "") +
      (lens ? " ذره‌بین را روی عکس فرش ببرید." : "");
  }
  if (lens && rug) {
    var pend = false;
    var place = function () {
      lens.style.transform = "translate(" + (K.x * rug.clientWidth).toFixed(1) + "px," + (K.y * rug.clientHeight).toFixed(1) + "px)";
      if (pend) return; pend = true;
      requestAnimationFrame(function () { pend = false; if (K.on) paintLens(); paintKnots(); });
    };
    var at = function (e) { var r = rug.getBoundingClientRect(); K.x = clamp((e.clientX - r.left) / r.width, .05, .95); K.y = clamp((e.clientY - r.top) / r.height, .04, .96); place(); };
    var lk = $("#lens-key");
    var on = function (v) { K.on = v; lens.classList.toggle("on", v); lens.style.pointerEvents = v ? "auto" : "none"; if (lk) lk.setAttribute("aria-pressed", String(v)); if (v) place(); };
    sheet.addEventListener("pointerenter", function (e) { if (e.pointerType === "mouse") { on(true); at(e); } });
    sheet.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse") at(e); });
    rug.addEventListener("pointerleave", function (e) { if (e.pointerType === "mouse" && d.activeElement !== lk) on(false); });
    sheet.addEventListener("click", function (e) { on(true); at(e); });
    var drag = false;
    lens.addEventListener("pointerdown", function (e) { drag = true; lens.setPointerCapture(e.pointerId); e.preventDefault(); });
    lens.addEventListener("pointermove", function (e) { if (drag) at(e); });
    lens.addEventListener("pointerup", function () { drag = false; });
    lens.addEventListener("pointercancel", function () { drag = false; });
    if (lk) {
      lk.addEventListener("click", function () { on(!K.on); });
      lk.addEventListener("keydown", function (e) {
        if (!K.on) return; var st = e.shiftKey ? .1 : .03, k = e.key;
        if (k === "ArrowLeft") K.x -= st; else if (k === "ArrowRight") K.x += st; else if (k === "ArrowUp") K.y -= st; else if (k === "ArrowDown") K.y += st; else if (k === "Escape") { on(false); return; } else return;
        e.preventDefault(); K.x = clamp(K.x, .05, .95); K.y = clamp(K.y, .04, .96); place();
      });
    }
    if (grp) grp.addEventListener("change", function () { sayText(); paintKnots(); if (K.on) paintLens(); });
    sayText();
    // نقش وسط فرش (ترنج) برای شروع
    var start = function () { K.ready = true; paintKnots(); };
    var im0 = $("img", sheet);
    if (im0 && !(im0.complete && im0.naturalWidth)) im0.addEventListener("load", start, { once: true }); else start();
    addEventListener("resize", function () { if (K.on) place(); paintKnots(); });
  }

  /* ---------- نقشهٔ اتاق: سایزها با اندازهٔ واقعی */
  var plan = $("#plan"), PL = { L: 500, W: 400, key: null, rot: false, cx: 250, cy: 200, ready: false, sizes: [] };
  function sizeKey(r) { var l = +r.dataset.l, w = +r.dataset.w; return l > 0 && w > 0 && r.dataset.t !== "round" ? (Math.round(l * 100) + "x" + Math.round(w * 100)) : null; }
  function m(v) { return fa(Math.round(v) / 100); }
  if (plan) {
    var seen = {};
    radios().forEach(function (r) {
      var k = sizeKey(r); if (!k || seen[k]) return; seen[k] = 1;
      PL.sizes.push({ key: k, l: Math.round(+r.dataset.l * 100), w: Math.round(+r.dataset.w * 100), name: (r.dataset.label || "").replace(/\s*\([^()]*\)\s*$/, ""), radio: r });
    });
    if (!PL.sizes.length) { var sec = $("#planner"); if (sec) sec.hidden = true; var tp = $("#to-plan"); if (tp) tp.hidden = true; }
    else {
      var pr = picked(); PL.key = (pr && sizeKey(pr)) || PL.sizes[0].key;
      PL.ready = true; plSizes(); plRender(true);
    }
  }
  function sz() { for (var i = 0; i < PL.sizes.length; i++) if (PL.sizes[i].key === PL.key) return PL.sizes[i]; return PL.sizes[0]; }
  function plSizes() {
    var box = $("#pl-sizes");
    box.innerHTML = PL.sizes.map(function (s) {
      var dims = fa(s.l / 100) + " × " + fa(s.w / 100);
      var name = s.name;
      return '<button type="button" class="pl-size" role="radio" aria-checked="' + (s.key === PL.key) + '" tabindex="' + (s.key === PL.key ? 0 : -1) + '" data-k="' + s.key + '"><b>' + name + '</b><small>' + dims + ' متر</small></button>';
    }).join("");
  }
  function pickPl(k, focus) {
    PL.key = k; plSizes(); plRender(true);
    var nb = $('[data-k="' + k + '"]'); if (focus && nb) nb.focus();
    var s = sz(); if (s.radio && !s.radio.disabled && !s.radio.checked) { s.radio.checked = true; s.radio.dispatchEvent(new Event("change", { bubbles: true })); }
  }
  if (PL.ready) {
    var box = $("#pl-sizes");
    box.addEventListener("click", function (e) { var b = e.target.closest("[data-k]"); if (b) pickPl(b.dataset.k, true); });
    box.addEventListener("keydown", function (e) {
      var k = e.key, i = PL.sizes.indexOf(sz());
      if (k === "ArrowLeft" || k === "ArrowDown") i++; else if (k === "ArrowRight" || k === "ArrowUp") i--; else return;
      e.preventDefault(); i = (i + PL.sizes.length) % PL.sizes.length; pickPl(PL.sizes[i].key, true);
    });
    $("#pl-rot").addEventListener("click", function () { PL.rot = !PL.rot; plRender(true); });
    $("#pl-center").addEventListener("click", function () { PL.cx = PL.L / 2; PL.cy = PL.W / 2; plRender(false); });
    var readDims = function () {
      var l = parseFloat(en($("#room-l").value)), w = parseFloat(en($("#room-w").value));
      if (!(l >= 1)) l = 1; if (!(w >= 1)) w = 1; l = Math.min(l, 20); w = Math.min(w, 20);
      PL.L = Math.round(l * 100); PL.W = Math.round(w * 100); PL.cx = PL.L / 2; PL.cy = PL.W / 2; plRender(true);
    };
    ["#room-l", "#room-w"].forEach(function (s) {
      var i = $(s);
      i.addEventListener("change", function () { var v = parseFloat(en(i.value)); if (v > 0) i.value = fa(Math.round(v * 10) / 10); readDims(); });
      i.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); i.blur(); } });
    });
    $$("[data-step]").forEach(function (b) {
      b.addEventListener("click", function () {
        var a = b.dataset.step.split(","), i = $(a[0] === "l" ? "#room-l" : "#room-w");
        var v = parseFloat(en(i.value)) || 4; v = clamp(Math.round((v + (+a[1]) * .5) * 10) / 10, 1, 20); i.value = fa(v); readDims();
      });
    });
    var tp = $("#to-plan");
    if (tp) tp.addEventListener("click", function (e) { e.preventDefault(); $("#planner").scrollIntoView({ behavior: RM ? "auto" : "smooth" }); });
  }
  function plRug() { var s = sz(), horiz = (PL.L >= PL.W) !== PL.rot; return { w: horiz ? s.l : s.w, h: horiz ? s.w : s.l, s: s, horiz: horiz }; }
  function furn(x, y, w, h, label, sofa, fs) {
    var s = '<g><rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="10" fill="rgba(242,234,218,.82)" stroke="#2B1D15" stroke-width="2"/>';
    if (sofa) { s += '<rect x="' + (x + 6) + '" y="' + (y + h - 26) + '" width="' + (w - 12) + '" height="20" rx="6" fill="rgba(140,29,37,.25)" stroke="#2B1D15" stroke-width="1.2"/>'; for (var i = 1; i < 3; i++) s += '<line x1="' + (x + w * i / 3) + '" y1="' + (y + 8) + '" x2="' + (x + w * i / 3) + '" y2="' + (y + h - 30) + '" stroke="#2B1D15" stroke-width="1.2"/>'; }
    else s += '<rect x="' + (x + 8) + '" y="' + (y + 8) + '" width="' + (w - 16) + '" height="' + (h - 16) + '" rx="8" fill="none" stroke="#2B1D15" stroke-width="1.2"/>';
    if (label) s += '<text x="' + (x + w / 2) + '" y="' + (y + h / 2 - 2) + '" text-anchor="middle" font-size="' + fs * .8 + '" fill="#2B1D15">' + label + '</text>';
    return s + "</g>";
  }
  function plRender(reclamp) {
    if (!PL.ready) return;
    var L = PL.L, W = PL.W, r = plRug(), t = 22, M = 95, img = $("img", sheet), src = img ? (img.currentSrc || img.src) : "";
    if (reclamp) {
      PL.cx = clamp(PL.cx, r.w / 2, Math.max(r.w / 2, L - r.w / 2)); PL.cy = clamp(PL.cy, r.h / 2, Math.max(r.h / 2, W - r.h / 2));
      if (r.w > L) PL.cx = L / 2; if (r.h > W) PL.cy = W / 2;
    }
    var x0 = PL.cx - r.w / 2, y0 = PL.cy - r.h / 2, g = { top: y0, bottom: W - (y0 + r.h), right: L - (x0 + r.w), left: x0 },
      big = r.w > L || r.h > W, fs = Math.max(L, W) / 30, s = [];
    plan.setAttribute("viewBox", (-M) + " " + (-M) + " " + (L + 2 * M) + " " + (W + 2 * M));
    plan.setAttribute("font-family", "Vazirmatn, Tahoma, sans-serif");
    s.push('<defs><pattern id="pl-floor" width="50" height="50" patternUnits="userSpaceOnUse"><rect width="50" height="50" fill="#E9DBC0"/><path d="M50 0H0V50" fill="none" stroke="#CDB894" stroke-width="1.2"/></pattern>' +
      '<pattern id="pl-hatch" width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="10" height="10" fill="#7B4127"/><path d="M0 0V10" stroke="#A35E3A" stroke-width="3"/></pattern>' +
      '<marker id="pl-ar" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="5" markerHeight="5"><circle cx="5" cy="5" r="3.2" fill="' + (big ? "#8C1D25" : "#1B3768") + '"/></marker></defs>');
    s.push('<rect x="0" y="0" width="' + L + '" height="' + W + '" fill="url(#pl-floor)"/>');
    s.push('<path fill-rule="evenodd" fill="url(#pl-hatch)" d="M' + (-t) + " " + (-t) + "H" + (L + t) + "V" + (W + t) + "H" + (-t) + "Z M0 0V" + W + "H" + L + 'V0Z"/>');
    var ow = Math.min(L * .6, 360), ox = (L - ow) / 2;
    s.push('<rect x="' + ox + '" y="' + (-t) + '" width="' + ow + '" height="' + t + '" fill="#F2EADA" stroke="#2B1D15" stroke-width="1.5"/>');
    for (var k = 0; k < 5; k++) s.push('<rect x="' + (ox + k * ow / 5 + 3) + '" y="' + (-t + 5) + '" width="' + (ow / 5 - 6) + '" height="' + (t - 10) + '" fill="' + GLASS[k % 4] + '" opacity=".75"/>');
    s.push('<text x="' + (L / 2) + '" y="' + (-t - 12) + '" text-anchor="middle" font-size="' + fs + '" fill="#5A4536">پنجره</text>');
    var dy = W - Math.min(110, W * .4), dl = Math.min(90, W * .3);
    s.push('<rect x="' + (-t - 1) + '" y="' + dy + '" width="' + (t + 2) + '" height="' + dl + '" fill="#E9DBC0"/><path d="M0 ' + dy + " A" + dl + " " + dl + " 0 0 1 " + dl + " " + (dy + dl) + '" fill="none" stroke="#8C7656" stroke-width="1.5" stroke-dasharray="6 5"/><line x1="0" y1="' + dy + '" x2="' + dl + '" y2="' + dy + '" stroke="#2B1D15" stroke-width="2.5"/>');
    // فرش: کادر خود فرش از عکس (همان برش صفحه)
    var sw = Math.min(r.w, r.h), sl = Math.max(r.w, r.h), vb = crop[2] < 100 || crop[3] < 100 ? crop[0] + " " + crop[1] + " " + crop[2] + " " + crop[3] : "0 0 100 100";
    s.push('<g class="rugG" id="rugG" tabindex="0" role="img" aria-label="فرش ' + sz().name + "، " + m(sl) + " در " + m(sw) + ' متر؛ با کلیدهای جهت جابه‌جا کنید و با R بچرخانید" transform="translate(' + PL.cx + " " + PL.cy + ')">' +
      '<g transform="rotate(' + (r.horiz ? 90 : 0) + ')"><rect x="' + (-sw / 2) + '" y="' + (-sl / 2) + '" width="' + sw + '" height="' + sl + '" fill="#8A7A66"/>' +
      (src ? '<svg x="' + (-sw / 2) + '" y="' + (-sl / 2) + '" width="' + sw + '" height="' + sl + '" viewBox="' + vb + '" preserveAspectRatio="none"><image href="' + src + '" width="100" height="100" preserveAspectRatio="none"/></svg>' : "") +
      '</g><rect class="rug-focus" x="' + (-r.w / 2) + '" y="' + (-r.h / 2) + '" width="' + r.w + '" height="' + r.h + '" fill="none" stroke="' + (big ? "#8C1D25" : "rgba(0,0,0,.25)") + '" stroke-width="' + (big ? 5 : 1.5) + '"/></g>');
    var fur = [], sofaW = Math.min(220, L * .5), sx = L / 2 - sofaW / 2, syy = W - 90 - 12;
    fur.push(furn(sx, syy, sofaW, 90, "مبل", 1, fs));
    if (L >= 300) { fur.push(furn(Math.max(10, sx - 95), W / 2 - 42, 85, 85, "", 0, fs)); fur.push(furn(Math.min(L - 95, sx + sofaW + 10), W / 2 - 42, 85, 85, "", 0, fs)); }
    fur.push('<rect x="' + (L / 2 - 55) + '" y="' + (W / 2 - 10) + '" width="110" height="55" rx="4" fill="rgba(122,78,43,.55)" stroke="#2B1D15" stroke-width="2"/><text x="' + (L / 2) + '" y="' + (W / 2 + 24) + '" text-anchor="middle" font-size="' + (fs * .8) + '" fill="#fff">میز</text>');
    fur.push('<circle cx="' + (L - 34) + '" cy="34" r="22" fill="rgba(46,139,87,.55)" stroke="#2B1D15" stroke-width="2"/><circle cx="' + (L - 34) + '" cy="34" r="9" fill="rgba(46,139,87,.8)"/>');
    s.push('<g pointer-events="none">' + fur.join("") + "</g>");
    var dim = [], col = big ? "#8C1D25" : "#1B3768";
    function dl1(x1, y1, x2, y2, val, tx, ty) {
      if (val <= .5) return;
      dim.push('<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="' + col + '" stroke-width="2" marker-start="url(#pl-ar)" marker-end="url(#pl-ar)"/>' +
        '<rect x="' + (tx - fs * 1.7) + '" y="' + (ty - fs * .75) + '" width="' + (fs * 3.4) + '" height="' + (fs * 1.45) + '" rx="' + (fs * .3) + '" fill="' + col + '"/><text x="' + tx + '" y="' + (ty + fs * .38) + '" text-anchor="middle" font-size="' + fs + '" font-weight="700" fill="#F3E9D3">' + m(val) + "</text>");
    }
    if (!big) {
      var ax = PL.cx + r.w * .22, ay = PL.cy + r.h * .22;
      dl1(ax, 0, ax, y0, g.top, ax, y0 / 2); dl1(ax, y0 + r.h, ax, W, g.bottom, ax, (y0 + r.h + W) / 2);
      dl1(0, ay, x0, ay, g.left, x0 / 2, ay); dl1(x0 + r.w, ay, L, ay, g.right, (x0 + r.w + L) / 2, ay);
    }
    s.push('<g pointer-events="none">' + dim.join("") + "</g>");
    s.push('<text x="' + (L / 2) + '" y="' + (W + t + fs * 1.6) + '" text-anchor="middle" font-size="' + fs + '" fill="#5A4536">طول ' + m(L) + " متر</text>");
    s.push('<text transform="translate(' + (L + t + fs * 1.2) + " " + (W / 2) + ') rotate(90)" text-anchor="middle" font-size="' + fs + '" fill="#5A4536">عرض ' + m(W) + " متر</text>");
    plan.innerHTML = s.join("");
    var nm = sz().name, dims = m(sl) + " × " + m(sw);
    $("#pl-read").innerHTML = big ? "فرش <b>" + nm + "</b> (" + dims + ") روی اتاق " + m(L) + " × " + m(W) + " متر." :
      "فاصلهٔ فرش <b>" + nm + "</b> تا دیوارها:<br>تا پنجره <b>" + m(g.top) + " م</b>، تا دیوار مبل <b>" + m(g.bottom) + " م</b>، تا دیوار در <b>" + m(g.left) + " م</b>، تا دیوار روبه‌رو <b>" + m(g.right) + " م</b>.";
    var w = $("#pl-warn");
    if (big) { w.hidden = false; w.textContent = "این فرش از اتاق بزرگ‌تر است." + (r.h <= L && r.w <= W ? " با چرخاندن ۹۰ درجه جا می‌شود." : " سایز کوچک‌تری انتخاب کنید."); }
    else if (Math.min(g.top, g.bottom, g.left, g.right) < 20) { w.hidden = false; w.textContent = "فرش به دیوار خیلی نزدیک است؛ معمولاً ۲۰ تا ۶۰ سانت فاصله خوش‌نشین‌تر است."; }
    else w.hidden = true;
    bindRug();
  }
  var mvPend = false;
  function plMove() { if (mvPend) return; mvPend = true; requestAnimationFrame(function () { mvPend = false; var g = $("#rugG"); if (g) g.setAttribute("transform", "translate(" + PL.cx + " " + PL.cy + ")"); }); }
  function fit() { var r = plRug(); PL.cx = r.w > PL.L ? PL.L / 2 : clamp(PL.cx, r.w / 2, PL.L - r.w / 2); PL.cy = r.h > PL.W ? PL.W / 2 : clamp(PL.cy, r.h / 2, PL.W - r.h / 2); }
  function bindRug() {
    var g = $("#rugG"), st = null;
    function pt(e) { var p = plan.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(plan.getScreenCTM().inverse()); }
    g.addEventListener("pointerdown", function (e) { var q = pt(e); st = { x: q.x, y: q.y, cx: PL.cx, cy: PL.cy }; g.setPointerCapture(e.pointerId); g.classList.add("drag"); e.preventDefault(); });
    g.addEventListener("pointermove", function (e) { if (!st) return; var q = pt(e); PL.cx = st.cx + (q.x - st.x); PL.cy = st.cy + (q.y - st.y); fit(); plMove(); });
    function end() { if (!st) return; st = null; var had = d.activeElement === g; plRender(false); if (had) $("#rugG").focus(); }
    g.addEventListener("pointerup", end); g.addEventListener("pointercancel", end);
    g.addEventListener("keydown", function (e) {
      var s = e.shiftKey ? 50 : 10, k = e.key;
      if (k === "ArrowLeft") PL.cx -= s; else if (k === "ArrowRight") PL.cx += s; else if (k === "ArrowUp") PL.cy -= s; else if (k === "ArrowDown") PL.cy += s;
      else if (k === "r" || k === "R" || k === "ق") { PL.rot = !PL.rot; plRender(true); $("#rugG").focus(); e.preventDefault(); return; } else return;
      e.preventDefault(); fit(); plRender(false); $("#rugG").focus();
    });
  }

  if (form) { var c0 = picked(); if (c0) c0.dispatchEvent(new Event("change", { bubbles: true })); }
})();
