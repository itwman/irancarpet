/* فرشستان «فروشگاه تخصصی» — صفحهٔ فرش: عکس‌ها و بزرگ‌نمایی، نمای نزدیک بافت (گره‌ها از روی عکس خود فرش)، انتخاب سایز و قیمت،
   جدول سایز، «اندازه در اتاق شما»، مقایسه و زبانه‌ها. خرید بدون این فایل هم کار می‌کند (فرم buyForm و رادیوهای variation). */
(function () {
  "use strict";
  var FS = window.FS; if (!FS) return;
  var d = document, $ = FS.$, $$ = FS.$$, RM = FS.RM, clamp = FS.clamp, fa = FS.fa, money = FS.money, num = FS.num, ic = FS.ic, esc = FS.esc;
  var form = $("#buyForm");
  function radios() { return form ? Array.prototype.filter.call(form.elements, function (e) { return e.name === "variation"; }) : []; }
  function picked() { var r = radios().filter(function (x) { return x.checked; }); return r[0] || null; }
  function qtyInput() { return form ? Array.prototype.filter.call(form.elements, function (e) { return e.name === "qty"; })[0] : null; }
  function rawPrice(r) { return r ? +r.dataset.price || 0 : 0; }

  /* ---------- قیمت سایز انتخاب‌شده در جعبهٔ خرید، نوار موبایل، خرید سریع کناری و جدول سایز */
  var buyPrice = $("#buyPrice"), price0 = buyPrice ? buyPrice.innerHTML : "", mPrice = $("#mPrice"), m0 = mPrice ? mPrice.innerHTML : "";
  function onSize() {
    var r = picked(); if (!r) return;
    var label = r.dataset.label || "", dims = r.dataset.dims ? r.dataset.dims + " متر" : "";
    var szSel = $("#szSel"); if (szSel) szSel.innerHTML = label ? "<b>" + esc(label) + "</b>" + (dims ? " · " + esc(dims) : "") : "";
    var rc = $("#rcSize"); if (rc && label) rc.textContent = label + (r.dataset.dims ? " (" + r.dataset.dims + ")" : "");
    var q = qtyInput(), n = q ? Math.max(1, num(q.value) || 1) : 1;
    if (r.dataset.pt) {
      var top = r.dataset.was ? '<div class="pr-top"><del>' + r.dataset.was + "</del></div>" : "";
      var total = n > 1 && rawPrice(r) ? '<div class="pr-note">' + fa(n) + " عدد: " + money(rawPrice(r) * n) + " تومان</div>" : "";
      if (buyPrice) buyPrice.innerHTML = top + '<div class="pr-now">' + r.dataset.pt + "<small>تومان</small></div>" + '<div class="pr-note">قیمت ' + esc(label) + (dims ? " (" + esc(dims) + ")" : "") + "</div>" + total;
      if (mPrice) mPrice.innerHTML = (r.dataset.was ? '<div class="pr-top"><del>' + r.dataset.was + "</del></div>" : "") + "<b>" + r.dataset.pt + " <small>تومان</small></b><small>" + esc(label) + "</small>";
      var sb = $("#sbPrice"); if (sb) sb.innerHTML = '<span class="pr-note">' + esc(label) + '</span><span class="pr-now">' + r.dataset.pt + "<small>تومان</small></span>";
    } else {
      if (buyPrice) buyPrice.innerHTML = price0;
      if (mPrice) mPrice.innerHTML = m0;
    }
    var sbs = $("#sbSize"); if (sbs) sbs.textContent = label + (dims ? " · " + dims : "");
    var sl = $("#stockLine");
    if (sl && r.dataset.q) sl.innerHTML = ic("box") + '<span class="warn">از این سایز فقط ' + fa(r.dataset.q) + " عدد مانده</span>";
    else if (sl && sl.dataset.orig) sl.innerHTML = sl.dataset.orig;
    if (r.dataset.pair && q) { var v = num(q.value) || 1; if (v % 2) q.value = String(v + 1); }
    var p = rawPrice(r);
    var tl = $("#torobLine");
    if (tl && p) { tl.hidden = p > +tl.dataset.max; $("span", tl).textContent = p <= +tl.dataset.eachMax ? "۴ قسط " + money(Math.ceil(p / 4)) + " تومان، بدون چک و ضامن" : "خرید ۴ قسطی بر اساس اعتبار شما در ترب‌پی"; }
    var it = $("#instTeaser"); if (it && it.dataset.base && p) it.href = it.dataset.base + "?amount=" + p;
    $$("#sizeTbl tr[data-row]").forEach(function (tr) {
      var on = tr.dataset.row === r.value; tr.classList.toggle("sel", on);
      var b = $("[data-pick]", tr); if (b) b.textContent = on ? "انتخاب‌شده" : "انتخاب";
    });
    if (PL.ready) { var k = sizeKey(r); if (k && k !== PL.key) { PL.key = k; if (FS.isOpen(roomModal)) { plSizes(); plRender(true); } } }
    if (K.on) drawTex();
  }
  var slEl = $("#stockLine"); if (slEl) slEl.dataset.orig = slEl.innerHTML;
  if (form) {
    radios().forEach(function (r) { r.addEventListener("change", onSize); });
    $$("[data-q]").forEach(function (b) {
      b.addEventListener("click", function () {
        var q = qtyInput(); if (!q) return;
        var r = picked(), st = r && r.dataset.pair ? 2 : 1, v = (num(q.value) || 1) + (+b.dataset.q) * st;
        q.value = String(clamp(v, st, 20)); onSize();
      });
    });
    var q0 = qtyInput(); if (q0) q0.addEventListener("input", onSize);
  }
  d.addEventListener("click", function (e) {
    var b = e.target.closest("[data-pick]"); if (!b) return;
    var r = radios().filter(function (x) { return x.value === b.dataset.pick; })[0];
    if (r && !r.disabled) { r.checked = true; onSize(); var g = $("#buy"); if (g && FS.isMobile()) g.scrollIntoView({ behavior: RM ? "auto" : "smooth", block: "center" }); FS.toast("سایز " + esc(r.dataset.label || "") + " انتخاب شد."); }
  });

  /* ---------- عکس‌ها */
  var stage = $("#stageImg"), crop = ((stage && stage.dataset.crop) || "0,0,100,100,0.6667").split(",").map(Number), full = null;
  $$(".thumbs .thumb[data-src]").forEach(function (b) {
    b.addEventListener("click", function () {
      setTex(false);
      $$(".thumbs .thumb[data-src]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      var box = $(".rugimg", stage), img = $("img", stage); if (!box || !img) return;
      crop = b.dataset.crop.split(",").map(Number);
      var st = "--ar:" + crop[4] + (crop[2] < 100 || crop[3] < 100 ? ";--cx:" + crop[0] + ";--cy:" + crop[1] + ";--cw:" + crop[2] + ";--ch:" + crop[3] : "");
      box.setAttribute("style", st);
      img.srcset = b.dataset.set; img.src = b.dataset.src; stage.dataset.full = b.dataset.full; full = null;
      var mini = $("#texMini .rugimg"), mimg = mini && $("img", mini); if (mini) mini.setAttribute("style", st); if (mimg) { mimg.removeAttribute("srcset"); mimg.src = b.dataset.src; }
      K.x = .5; K.y = .5;
    });
  });

  /* ---------- بزرگ‌نمایی با نشانگر (فقط موس) */
  var lens = $("#zoomLens"), Z = 2.6;
  function source() {
    var img = stage && $("img", stage);
    if (full && full.complete && full.naturalWidth) return full;
    if (!full && stage && stage.dataset.full) { full = new Image(); full.decoding = "async"; full.onload = function () { if (K.on) drawTex(); }; full.src = stage.dataset.full; }
    return img && img.complete && img.naturalWidth ? img : null;
  }
  if (lens && stage) {
    stage.addEventListener("pointermove", function (e) {
      if (e.pointerType !== "mouse") return;
      var img = $("img", stage); if (!img) return;
      var box = $(".rugimg", stage).getBoundingClientRect(), ir = img.getBoundingClientRect(), sr = stage.getBoundingClientRect();
      if (e.clientX < box.left || e.clientX > box.right || e.clientY < box.top || e.clientY > box.bottom) { lens.hidden = true; return; }
      var hi = source(); if (hi && hi !== img && lens.dataset.src !== hi.src) { lens.style.backgroundImage = "url('" + hi.src + "')"; lens.dataset.src = hi.src; }
      else if (!lens.dataset.src) { lens.style.backgroundImage = "url('" + (img.currentSrc || img.src) + "')"; lens.dataset.src = img.currentSrc || img.src; }
      var fx = (e.clientX - ir.left) / ir.width, fy = (e.clientY - ir.top) / ir.height, bw = ir.width * Z, bh = ir.height * Z, R = 100;
      lens.hidden = false;
      lens.style.left = (e.clientX - sr.left - R) + "px"; lens.style.top = (e.clientY - sr.top - R) + "px";
      lens.style.backgroundSize = bw + "px " + bh + "px";
      lens.style.backgroundPosition = (R - fx * bw) + "px " + (R - fy * bh) + "px";
    });
    stage.addEventListener("pointerleave", function () { lens.hidden = true; });
  }

  /* ---------- نمای نزدیک بافت: گره‌ها از روی عکس خود فرش با شانهٔ انتخاب‌شده (۴ سانتی‌متر از فرش زیر ذره‌بین) */
  var tex = $("#stageTex"), texBar = $("#texbar"), texCv = $("#texCv"), seg = $("#texSeg"), texBtn = $("#texBtn");
  var K = { on: false, x: .5, y: .5, sh: 700 }, PATCH = .04;
  var mine = seg ? $('[aria-checked="true"]', seg) : null; if (mine) K.sh = +mine.dataset.tsh;
  var REEDS = +(($(".texseg .mine") || {}).parentNode || { dataset: { tsh: 0 } }).dataset.tsh || 0;
  function rugWidthM() { var r = picked(); var w = r && +r.dataset.w, l = r && +r.dataset.l; return w && l ? Math.min(w, l) : 2; }
  function knotPaint(c) {
    var img = source(); if (!img || !c) return false;
    var dpr = Math.min(2, window.devicePixelRatio || 1), W = c.clientWidth || 400, H = c.clientHeight || W, S = Math.round(W * dpr), SH = Math.round(H * dpr);
    if (c.width !== S || c.height !== SH) { c.width = S; c.height = SH; }
    var n = Math.max(8, Math.round(K.sh * PATCH)), ny = Math.max(8, Math.round(n * SH / S)), iw = img.naturalWidth, ih = img.naturalHeight;
    var f = PATCH / rugWidthM(), cw = iw * crop[2] / 100, ch = ih * crop[3] / 100, sw = Math.max(2, cw * f), sh = sw * ny / n;
    var sx = clamp(iw * crop[0] / 100 + K.x * cw - sw / 2, 0, iw - sw), sy = clamp(ih * crop[1] / 100 + K.y * ch - sh / 2, 0, ih - sh);
    var t = d.createElement("canvas"); t.width = n; t.height = ny;
    var tx = t.getContext("2d"); tx.imageSmoothingEnabled = true; tx.imageSmoothingQuality = "high";
    var px;
    try { tx.drawImage(img, sx, sy, sw, sh, 0, 0, n, ny); px = tx.getImageData(0, 0, n, ny).data; } catch (e) { return false; }
    var g = c.getContext("2d"), cell = S / n, cellY = SH / ny;
    g.fillStyle = "#1a120c"; g.fillRect(0, 0, S, SH);
    for (var j = 0; j < ny; j++) for (var i = 0; i < n; i++) {
      var k = (j * n + i) * 4, r = px[k], gg = px[k + 1], b = px[k + 2], cx = (i + .5) * cell, cy = (j + .5) * cellY;
      g.fillStyle = "rgb(" + (r * .62 | 0) + "," + (gg * .62 | 0) + "," + (b * .62 | 0) + ")";
      g.fillRect(i * cell, j * cellY, cell + .5, cellY + .5);
      g.fillStyle = "rgb(" + r + "," + gg + "," + b + ")"; // گره فارسی: دو بازوی کج کنار هم
      g.beginPath(); g.ellipse(cx - cell * .2, cy, cell * .26, cellY * .44, .32, 0, 6.2832); g.fill();
      g.beginPath(); g.ellipse(cx + cell * .2, cy, cell * .26, cellY * .44, -.32, 0, 6.2832); g.fill();
      if (cell > 4) {
        g.fillStyle = "rgba(255,255,255,.16)";
        g.beginPath(); g.ellipse(cx - cell * .24, cy - cellY * .14, cell * .08, cellY * .2, .32, 0, 6.2832); g.fill();
        g.beginPath(); g.ellipse(cx + cell * .16, cy - cellY * .14, cell * .08, cellY * .2, -.32, 0, 6.2832); g.fill();
      }
    }
    return true;
  }
  var SAY = { 700: "گره‌ها درشت‌ترند؛ نقش‌ها ساده‌تر و پررنگ دیده می‌شوند.", 1000: "گره‌ها ریزترند؛ مرز رنگ‌ها نرم‌تر است.",
    1200: "پیچ‌وتاب گل‌ها و برگ‌ها با جزئیات بیشتری بافته می‌شود.", 1500: "ریزترین گره‌ها؛ از فاصلهٔ معمول، نقش تقریباً مثل نقاشی دیده می‌شود." };
  function drawTex() {
    if (!texCv || !K.on) return;
    if (!knotPaint(texCv)) { var im = $("img", stage); if (im) im.addEventListener("load", drawTex, { once: true }); }
    var n = Math.round(K.sh * PATCH);
    $("#texLabel").textContent = fa(K.sh) + " شانه";
    var ru = $("#texRuler"); if (ru) ru.style.width = Math.max(10, texCv.clientWidth / (PATCH * 100)) + "px";
    var mini = $("#texMini .tex-mini-in"), bx = $("#texBox");
    if (mini && bx) {
      var mw = mini.clientWidth, mh = mini.clientHeight, f = PATCH / rugWidthM(), bw = Math.max(6, f * mw), bh = Math.max(6, bw * (texCv.clientHeight / texCv.clientWidth) * (mw / mh) * (mh / mw));
      bx.style.width = bw + "px"; bx.style.height = bh + "px";
      bx.style.left = (4 + clamp(K.x * mw - bw / 2, 0, mw - bw)) + "px"; bx.style.top = (4 + clamp(K.y * mh - bh / 2, 0, mh - bh)) + "px";
    }
    var cap = $("#texCap");
    if (cap) cap.innerHTML = "نمای ۴ سانتی‌متری از همین فرش: <b>" + fa(Math.round(K.sh / 10)) + " گره</b> در هر ۱۰ سانتی‌متر از عرض فرش. " + (SAY[K.sh] || "") +
      (REEDS && K.sh !== REEDS ? " این شبیه‌سازی همین نقش با " + fa(K.sh) + " شانه است؛ این فرش " + fa(REEDS) + " شانه است." : REEDS ? " این همان بافت این فرش است." : "");
    if (tex) tex.setAttribute("aria-label", "نمای نزدیک بافت با " + fa(K.sh) + " شانه؛ با کلیدهای جهت جابه‌جا کنید" + (n ? "" : ""));
  }
  function setTex(on) {
    if (!tex) return;
    K.on = on; tex.hidden = !on; if (texBar) texBar.hidden = !on; if (stage) stage.hidden = on;
    if (texBtn) texBtn.setAttribute("aria-pressed", String(on));
    if (on) { $$(".thumbs .thumb[data-src]").forEach(function (x) { x.setAttribute("aria-pressed", "false"); }); requestAnimationFrame(drawTex); }
    else { var f0 = $(".thumbs .thumb[data-src]"); if (f0 && !$('.thumbs .thumb[data-src][aria-pressed="true"]')) f0.setAttribute("aria-pressed", "true"); }
  }
  function pickTex(sh, focus) {
    K.sh = sh;
    $$("[data-tsh]", seg).forEach(function (b) { var on = +b.dataset.tsh === sh; b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
    drawTex();
  }
  if (tex && seg) {
    if (texBtn) texBtn.addEventListener("click", function () { setTex(!K.on); });
    $$("[data-texopen]").forEach(function (b) { b.addEventListener("click", function () { setTex(true); $("#gal").scrollIntoView({ behavior: RM ? "auto" : "smooth", block: "start" }); }); });
    $$("[data-tsh]", seg).forEach(function (b) { b.tabIndex = b.getAttribute("aria-checked") === "true" ? 0 : -1; });
    seg.addEventListener("click", function (e) { var b = e.target.closest("[data-tsh]"); if (b) pickTex(+b.dataset.tsh, true); });
    var LIST = [700, 1000, 1200, 1500];
    seg.addEventListener("keydown", function (e) {
      var i = LIST.indexOf(K.sh);
      if (e.key === "ArrowLeft" || e.key === "ArrowDown") { e.preventDefault(); pickTex(LIST[Math.min(LIST.length - 1, i + 1)], true); }
      else if (e.key === "ArrowRight" || e.key === "ArrowUp") { e.preventDefault(); pickTex(LIST[Math.max(0, i - 1)], true); }
    });
    tex.addEventListener("keydown", function (e) {
      var st = e.shiftKey ? .1 : .03, k = e.key;
      if (k === "ArrowLeft") K.x -= st; else if (k === "ArrowRight") K.x += st; else if (k === "ArrowUp") K.y -= st; else if (k === "ArrowDown") K.y += st; else if (k === "Escape") { setTex(false); return; } else return;
      e.preventDefault(); K.x = clamp(K.x, .02, .98); K.y = clamp(K.y, .02, .98); drawTex();
    });
    var mini = $("#texMini");
    mini.addEventListener("click", function (e) {
      var r = $(".tex-mini-in", mini).getBoundingClientRect();
      K.x = clamp((e.clientX - r.left) / r.width, .02, .98); K.y = clamp((e.clientY - r.top) / r.height, .02, .98); drawTex();
    });
    var drag = null;
    texCv.addEventListener("pointerdown", function (e) { drag = { x: e.clientX, y: e.clientY, kx: K.x, ky: K.y }; texCv.setPointerCapture(e.pointerId); });
    texCv.addEventListener("pointermove", function (e) {
      if (!drag) return; var f = PATCH / rugWidthM();
      K.x = clamp(drag.kx - (e.clientX - drag.x) / texCv.clientWidth * f * 1.2, .02, .98); K.y = clamp(drag.ky - (e.clientY - drag.y) / texCv.clientHeight * f * 1.2, .02, .98);
      requestAnimationFrame(drawTex);
    });
    texCv.addEventListener("pointerup", function () { drag = null; });
    addEventListener("resize", function () { if (K.on) drawTex(); });
  }

  /* ---------- اشتراک‌گذاری */
  var sh = $("#shareBtn");
  if (sh) sh.addEventListener("click", function () {
    var data = { title: d.title, url: location.href.split("#")[0] };
    if (navigator.share) { navigator.share(data).catch(function () {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(data.url).then(function () { FS.toast("پیوند این فرش کپی شد."); }, function () { FS.toast(esc(data.url)); });
    else FS.toast(esc(data.url));
  });

  /* ---------- مقایسه با فرش‌های دیگر (سینی مقایسه؛ اگر خالی بود، فرش‌های مشابه همین صفحه) */
  var self = $("#pdSelf"), cmpBox = $("#cmpBox"), selfData = null;
  if (self) { var ds = self.dataset; selfData = { id: +ds.id, t: ds.t, u: ds.u, img: ds.img, r: ds.r, tex: ds.tex, p: +ds.p || 0, rt: ds.rt || "", rc: +ds.rc || 0, out: !!ds.out }; }
  function renderCompare() {
    if (!cmpBox || !selfData) return;
    var others = FS.cmp.list().filter(function (x) { return x.id !== selfData.id; }), note;
    if (others.length) note = "فرش‌هایی که تیک «مقایسه» را برایشان زده‌اید، کنار همین فرش.";
    else {
      others = $$("#rel article.pc[data-id]").slice(0, 2).map(function (a) { var s = a.dataset; return { id: +s.id, t: s.t, u: s.u, img: s.img, r: s.r, tex: s.tex, p: +s.p || 0, rt: s.rt || "", rc: +s.rc || 0, out: !!s.out, sim: 1 }; });
      note = others.length ? "این فرش در کنار دو فرش مشابه؛ با تیک «مقایسه» روی کارت‌ها، فرش‌های دلخواه خود را بگذارید." : "";
    }
    if (!others.length) { cmpBox.innerHTML = '<p class="muted">با تیک «مقایسه» روی کارت فرش‌ها، آن‌ها را این‌جا کنار همین فرش ببینید.</p>'; return; }
    cmpBox.innerHTML = '<div class="cmp-tools"><p>' + note + "</p></div>" + FS.cmpTable([selfData].concat(others.slice(0, 3)), selfData.id);
    if (others[0] && others[0].sim) $$("[data-uncmp-t]", cmpBox).forEach(function (b) { b.remove(); });
  }
  d.addEventListener("fs:cmp", renderCompare);
  var cs = $("#cmpSelf");
  if (cs && selfData) cs.addEventListener("click", function () {
    var on = !FS.cmp.has(selfData.id);
    if (FS.cmpToggle(selfData, on)) FS.toast(on ? "به سینی مقایسه اضافه شد؛ فرش‌های دیگر را هم تیک بزنید." : "از مقایسه حذف شد.");
  });
  renderCompare();

  /* ---------- زبانه‌ها: پررنگ شدن بخش جاری */
  var links = $$(".ptabs a");
  if (links.length && "IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (en.isIntersecting) links.forEach(function (l) { l.setAttribute("aria-current", String(l.getAttribute("href") === "#" + en.target.id)); }); });
    }, { rootMargin: "-40% 0px -55% 0px" });
    $$(".psec[id]").forEach(function (s) { io.observe(s); });
  }

  /* ---------- اندازه در اتاق شما: نقشهٔ ساده از بالا به مقیاس واقعی */
  var roomModal = $("#roomModal"), plan = $("#plan");
  var PL = { L: 500, W: 400, key: null, rot: false, cx: 250, cy: 200, ready: false, sizes: [] };
  function sizeKey(r) { var l = +r.dataset.l, w = +r.dataset.w; return l > 0 && w > 0 && r.dataset.t !== "round" ? (Math.round(l * 100) + "x" + Math.round(w * 100)) : null; }
  function m(v) { return fa(Math.round(v) / 100); }
  if (plan && roomModal) {
    var seen = {};
    radios().forEach(function (r) {
      var k = sizeKey(r); if (!k || seen[k]) return; seen[k] = 1;
      PL.sizes.push({ key: k, l: Math.round(Math.max(+r.dataset.l, +r.dataset.w) * 100), w: Math.round(Math.min(+r.dataset.l, +r.dataset.w) * 100), name: r.dataset.label || "", radio: r });
    });
    if (!PL.sizes.length) $$("[data-room-open]").forEach(function (b) { b.hidden = true; });
    else { var pr = picked(); PL.key = (pr && sizeKey(pr)) || PL.sizes[0].key; PL.ready = true; }
  }
  function sz() { for (var i = 0; i < PL.sizes.length; i++) if (PL.sizes[i].key === PL.key) return PL.sizes[i]; return PL.sizes[0]; }
  function plSizes() {
    $("#rsz").innerHTML = PL.sizes.map(function (s) {
      return '<button type="button" role="radio" aria-checked="' + (s.key === PL.key) + '" tabindex="' + (s.key === PL.key ? 0 : -1) + '" data-k="' + s.key + '">' + esc(s.name) + "<small>" + fa(s.l / 100) + "×" + fa(s.w / 100) + "</small></button>";
    }).join("");
  }
  function plRug() { var s = sz(), horiz = (PL.L >= PL.W) !== PL.rot; return { w: horiz ? s.l : s.w, h: horiz ? s.w : s.l, s: s, horiz: horiz }; }
  function fit() { var r = plRug(); PL.cx = r.w > PL.L ? PL.L / 2 : clamp(PL.cx, r.w / 2, PL.L - r.w / 2); PL.cy = r.h > PL.W ? PL.W / 2 : clamp(PL.cy, r.h / 2, PL.W - r.h / 2); }
  function plRender(reclamp) {
    if (!PL.ready) return;
    var L = PL.L, W = PL.W, r = plRug(), t = 18, M = 90, img = stage && $("img", stage), src = img ? (img.currentSrc || img.src) : "";
    if (reclamp) fit();
    var x0 = PL.cx - r.w / 2, y0 = PL.cy - r.h / 2, g = { top: y0, bottom: W - (y0 + r.h), right: L - (x0 + r.w), left: x0 },
      big = r.w > L || r.h > W, fs = Math.max(L, W) / (FS.isMobile() ? 20 : 30), s = [];
    plan.setAttribute("viewBox", (-M) + " " + (-M) + " " + (L + 2 * M) + " " + (W + 2 * M));
    plan.setAttribute("font-family", "Vazirmatn, Tahoma, sans-serif");
    var grid = "";
    for (var gx = 50; gx < L; gx += 50) grid += '<line x1="' + gx + '" y1="0" x2="' + gx + '" y2="' + W + '" stroke="#E2E6ED" stroke-width="' + (gx % 100 ? 1 : 2) + '"/>';
    for (var gy = 50; gy < W; gy += 50) grid += '<line x1="0" y1="' + gy + '" x2="' + L + '" y2="' + gy + '" stroke="#E2E6ED" stroke-width="' + (gy % 100 ? 1 : 2) + '"/>';
    s.push('<rect x="' + (-t) + '" y="' + (-t) + '" width="' + (L + 2 * t) + '" height="' + (W + 2 * t) + '" fill="#323C52" rx="3"/><rect x="0" y="0" width="' + L + '" height="' + W + '" fill="#fff"/>' + grid);
    var ow = Math.min(L * .5, 300), ox = (L - ow) / 2;
    s.push('<rect x="' + ox + '" y="' + (-t) + '" width="' + ow + '" height="' + t + '" fill="#9CC3E6"/><text x="' + (L / 2) + '" y="' + (-t - 10) + '" text-anchor="middle" font-size="' + fs * .8 + '" fill="#5A6377">پنجره</text>');
    var dy = W - Math.min(110, W * .4), dl = Math.min(90, W * .3);
    s.push('<rect x="' + (-t - 1) + '" y="' + dy + '" width="' + (t + 2) + '" height="' + dl + '" fill="#fff"/><path d="M0 ' + dy + " A" + dl + " " + dl + " 0 0 1 " + dl + " " + (dy + dl) + '" fill="none" stroke="#8A92A3" stroke-width="1.5" stroke-dasharray="6 5"/><line x1="0" y1="' + dy + '" x2="' + dl + '" y2="' + dy + '" stroke="#8A92A3" stroke-width="2.5"/><text x="' + (-t - 10) + '" y="' + (dy + dl / 2) + '" text-anchor="middle" font-size="' + fs * .7 + '" fill="#8A92A3" transform="rotate(-90 ' + (-t - 10) + " " + (dy + dl / 2) + ')">در</text>');
    var sw = Math.min(r.w, r.h), sl = Math.max(r.w, r.h), vb = crop[2] < 100 || crop[3] < 100 ? crop[0] + " " + crop[1] + " " + crop[2] + " " + crop[3] : "0 0 100 100", col = big ? "#B4352F" : "#1D3F8F";
    s.push('<g id="rugG" tabindex="0" role="img" aria-label="فرش ' + esc(sz().name) + "، " + m(sl) + " در " + m(sw) + ' متر؛ با کلیدهای جهت جابه‌جا کنید و با R بچرخانید" transform="translate(' + PL.cx + " " + PL.cy + ')">' +
      '<rect x="' + (-r.w / 2 + fs * .25) + '" y="' + (-r.h / 2 + fs * .35) + '" width="' + r.w + '" height="' + r.h + '" fill="rgba(20,29,51,.18)"/>' +
      '<g transform="rotate(' + (r.horiz ? 90 : 0) + ')"><rect x="' + (-sw / 2) + '" y="' + (-sl / 2) + '" width="' + sw + '" height="' + sl + '" fill="#C3D0EC"/>' +
      (src ? '<svg x="' + (-sw / 2) + '" y="' + (-sl / 2) + '" width="' + sw + '" height="' + sl + '" viewBox="' + vb + '" preserveAspectRatio="none"><image href="' + esc(src) + '" width="100" height="100" preserveAspectRatio="none"/></svg>' : "") +
      '</g><rect class="rug-out" x="' + (-r.w / 2) + '" y="' + (-r.h / 2) + '" width="' + r.w + '" height="' + r.h + '" fill="none" stroke="' + col + '" stroke-width="' + (big ? 5 : 3) + '"/>' +
      '<rect x="' + (-fs * 3.2) + '" y="' + (-fs * .8) + '" width="' + (fs * 6.4) + '" height="' + (fs * 1.6) + '" rx="' + (fs * .8) + '" fill="rgba(11,28,66,.86)"/><text x="0" y="' + (fs * .3) + '" font-size="' + fs * .8 + '" font-weight="800" fill="#fff" text-anchor="middle">' + m(sl) + "×" + m(sw) + " متر</text></g>");
    var dim = [];
    function dl1(x1, y1, x2, y2, val, tx, ty) {
      if (val <= .5) return;
      dim.push('<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 + '" stroke="#C99A2E" stroke-width="' + fs * .12 + '" stroke-dasharray="' + fs * .4 + " " + fs * .3 + '"/>' +
        '<text x="' + tx + '" y="' + ty + '" font-size="' + fs * .78 + '" font-weight="800" fill="#3A2A05" text-anchor="middle" dominant-baseline="middle" paint-order="stroke" stroke="#fff" stroke-width="' + fs * .3 + '">' + fa(Math.round(val)) + "</text>");
    }
    if (!big) {
      dl1(PL.cx, 0, PL.cx, y0, g.top, PL.cx + fs * 1.2, y0 / 2); dl1(PL.cx, y0 + r.h, PL.cx, W, g.bottom, PL.cx + fs * 1.2, (y0 + r.h + W) / 2);
      dl1(0, PL.cy, x0, PL.cy, g.left, x0 / 2, PL.cy - fs * .6); dl1(x0 + r.w, PL.cy, L, PL.cy, g.right, (x0 + r.w + L) / 2, PL.cy - fs * .6);
    }
    s.push('<g pointer-events="none">' + dim.join("") + "</g>");
    s.push('<text x="' + (L / 2) + '" y="' + (W + t + fs * 1.4) + '" text-anchor="middle" font-size="' + fs + '" font-weight="700" fill="#5A6377">طول اتاق ' + m(L) + " متر</text>");
    s.push('<text transform="translate(' + (L + t + fs * 1.1) + " " + (W / 2) + ') rotate(90)" text-anchor="middle" font-size="' + fs + '" font-weight="700" fill="#5A6377">عرض ' + m(W) + " متر</text>");
    plan.innerHTML = s.join("");
    var cov = Math.round(sw * sl / (L * W) * 100), minM = Math.min(g.top, g.bottom, g.left, g.right);
    $("#rmRead").innerHTML = "<div>ابعاد فرش<b>" + m(sl) + "×" + m(sw) + " متر</b></div><div>پوشش کف اتاق<b>" + fa(Math.min(cov, 999)) + "٪</b></div>" +
      (big ? "" : "<div>چپ و راست<b>" + fa(Math.round(g.left)) + " · " + fa(Math.round(g.right)) + " س‌م</b></div><div>بالا و پایین<b>" + fa(Math.round(g.top)) + " · " + fa(Math.round(g.bottom)) + " س‌م</b></div>");
    var warn;
    if (big) {
      var fitsRot = r.h <= L && r.w <= W;
      if (fitsRot) warn = '<div class="rwarn">' + ic("warn") + '<span>در این جهت جا نمی‌شود؛ <button type="button" id="rmRot2">فرش را ۹۰ درجه بچرخانید</button>.</span></div>';
      else {
        var ok = PL.sizes.filter(function (z) { return z.w <= Math.min(L, W) - 40 && z.l <= Math.max(L, W) - 40; }).sort(function (a, b) { return b.l * b.w - a.l * a.w; })[0];
        warn = '<div class="rwarn">' + ic("warn") + "<span>این فرش از اتاق " + m(L) + "×" + m(W) + " متری بزرگ‌تر است." + (ok ? ' سایز <button type="button" data-k="' + ok.key + '">' + esc(ok.name) + "</button> را امتحان کنید." : "") + "</span></div>";
      }
    } else if (minM < 20) warn = '<div class="rwarn">' + ic("info") + "<span>فاصلهٔ فرش تا دیوار کمتر از ۲۰ سانتی‌متر است؛ معمولاً ۳۰ تا ۶۰ سانتی‌متر فاصله خوش‌نشین‌تر است.</span></div>";
    else warn = '<div class="rwarn ok">' + ic("check") + "<span>این سایز در اتاق شما جا می‌شود.</span></div>";
    $("#rmWarn").innerHTML = warn;
    $$("#rsz [data-k]").forEach(function (b) { b.setAttribute("aria-checked", String(b.dataset.k === PL.key)); b.tabIndex = b.dataset.k === PL.key ? 0 : -1; });
    var rad = sz().radio;
    $("#rmApply").textContent = "انتخاب سایز " + sz().name;
    $("#rmApply").disabled = !rad || rad.disabled;
    $("#rmFoot").innerHTML = rad && rad.dataset.pt ? "قیمت این سایز: <b>" + rad.dataset.pt + " تومان</b>" : rad && rad.disabled ? "این سایز فعلاً ناموجود است." : "";
    bindRug();
  }
  function bindRug() {
    var g = $("#rugG"), st = null;
    function pt(e) { var p = plan.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(plan.getScreenCTM().inverse()); }
    g.addEventListener("pointerdown", function (e) { var q = pt(e); st = { x: q.x, y: q.y, cx: PL.cx, cy: PL.cy }; g.setPointerCapture(e.pointerId); e.preventDefault(); });
    g.addEventListener("pointermove", function (e) { if (!st) return; var q = pt(e); PL.cx = Math.round((st.cx + q.x - st.x) / 5) * 5; PL.cy = Math.round((st.cy + q.y - st.y) / 5) * 5; fit(); g.setAttribute("transform", "translate(" + PL.cx + " " + PL.cy + ")"); });
    function end() { if (!st) return; st = null; plRender(false); $("#rugG").focus(); }
    g.addEventListener("pointerup", end); g.addEventListener("pointercancel", end);
    g.addEventListener("keydown", function (e) {
      var s = e.shiftKey ? 50 : 10, k = e.key;
      if (k === "ArrowLeft") PL.cx -= s; else if (k === "ArrowRight") PL.cx += s; else if (k === "ArrowUp") PL.cy -= s; else if (k === "ArrowDown") PL.cy += s;
      else if (k === "r" || k === "R" || k === "ق") { PL.rot = !PL.rot; plRender(true); $("#rugG").focus(); e.preventDefault(); return; } else return;
      e.preventDefault(); fit(); plRender(false); $("#rugG").focus();
    });
  }
  function openRoom(opener) {
    if (!PL.ready) return;
    var pr = picked(); var k = pr && sizeKey(pr); if (k) PL.key = k;
    PL.cx = PL.L / 2; PL.cy = PL.W / 2; PL.rot = false;
    plSizes(); FS.open(roomModal, opener); plRender(true);
    setTimeout(function () { var g = $("#rugG"); if (g) g.focus(); }, 60);
  }
  if (PL.ready) {
    $$("[data-room-open]").forEach(function (b) { b.addEventListener("click", function () { openRoom(b); }); });
    var pickPl = function (k, focus) { PL.key = k; PL.rot = false; PL.cx = PL.L / 2; PL.cy = PL.W / 2; plSizes(); plRender(true); var nb = $('#rsz [data-k="' + k + '"]'); if (focus && nb) nb.focus(); };
    $("#rsz").addEventListener("click", function (e) { var b = e.target.closest("[data-k]"); if (b) pickPl(b.dataset.k, true); });
    $("#rsz").addEventListener("keydown", function (e) {
      var k = e.key, i = PL.sizes.indexOf(sz());
      if (k === "ArrowLeft" || k === "ArrowDown") i++; else if (k === "ArrowRight" || k === "ArrowUp") i--; else return;
      e.preventDefault(); i = (i + PL.sizes.length) % PL.sizes.length; pickPl(PL.sizes[i].key, true);
    });
    $("#rmWarn").addEventListener("click", function (e) { var b = e.target.closest("[data-k]"); if (b) pickPl(b.dataset.k); if (e.target.closest("#rmRot2")) { PL.rot = !PL.rot; plRender(true); } });
    $("#rmRot").addEventListener("click", function () { PL.rot = !PL.rot; plRender(true); });
    $("#rmCenter").addEventListener("click", function () { PL.cx = PL.L / 2; PL.cy = PL.W / 2; plRender(false); });
    ["rmL", "rmW"].forEach(function (id) {
      $("#" + id).addEventListener("input", function (e) { var v = clamp(num(e.target.value) || 1, 1, 20); PL[id === "rmL" ? "L" : "W"] = Math.round(v * 100); PL.cx = PL.L / 2; PL.cy = PL.W / 2; plRender(true); });
    });
    $("#rmApply").addEventListener("click", function () {
      var rad = sz().radio;
      if (rad && !rad.disabled) { rad.checked = true; onSize(); FS.toast("سایز " + esc(sz().name) + " انتخاب شد."); }
      FS.close();
    });
  }

  /* ---------- معرفی بلند: کوتاه با دکمهٔ «ادامه» */
  var desc = $(".product-desc");
  if (desc && desc.scrollHeight > 640) {
    desc.classList.add("is-clamped");
    var mb = d.createElement("button"); mb.type = "button"; mb.className = "fbtn fbtn--line fbtn--sm more-btn"; mb.setAttribute("aria-expanded", "false");
    mb.innerHTML = "ادامهٔ معرفی" + ic("chd", "ic-sm");
    mb.addEventListener("click", function () { var open = desc.classList.toggle("is-clamped") === false; mb.setAttribute("aria-expanded", String(open)); mb.innerHTML = (open ? "بستن معرفی" : "ادامهٔ معرفی") + ic(open ? "chd" : "chd", "ic-sm"); if (!open) desc.scrollIntoView({ block: "start" }); });
    desc.parentNode.insertBefore(mb, desc.nextSibling);
  }

  /* ---------- پیوندهای مستقیم: #tex (نمای نزدیک بافت) و #planner (اندازه در اتاق) */
  var h = location.hash;
  if (h === "#tex" && tex) { setTex(true); setTimeout(function () { $("#gal").scrollIntoView({ block: "start" }); }, 50); }
  if (h === "#planner" && PL.ready) setTimeout(function () { openRoom(null); }, 80);

  if (form) onSize();
})();
