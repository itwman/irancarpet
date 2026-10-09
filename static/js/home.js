/* صفحهٔ اصلی ایران کارپت: گره‌ها (برگرفته از افکت کلمات ICSD)، چیدمان اتاق، فیلتر شانه */
(function () {
  "use strict";
  var dataEl = document.getElementById("room-data");
  var DATA = dataEl ? JSON.parse(dataEl.textContent) : { carpets: [], sizes: [] };
  var CARPETS = DATA.carpets || [];
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  function fa(n) {
    return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, "٬").replace(/\d/g, function (d) { return FA[d]; });
  }
  var reduced = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------------------------------------------------------------- گره‌ها */
  function Knots(cv) {
    var box = cv.parentNode;
    var ctx = cv.getContext && cv.getContext("2d");
    if (!ctx) { box.classList.add("no-canvas"); return null; }
    var words = ["فرش", "کاشان", "۱۵۰۰ شانه"];
    var PAL = [[229, 57, 91], [255, 178, 30], [18, 169, 184], [124, 196, 107]];
    var off = document.createElement("canvas");
    var octx = off.getContext("2d", { willReadFrequently: true });
    var W = 0, H = 0, G = 8, parts = [], target = [], stage = 0, turn = 0;
    var mx = -1e4, my = -1e4, raf = 0, timer = 0, t = 0, running = false, visible = true;
    var images = {};
    var link = document.getElementById("knotLink"), nameEl = document.getElementById("knotName"),
      infoEl = document.getElementById("knotInfo"), hint = document.getElementById("knotHint");

    function caption(c) {
      if (!link) return;
      if (c) {
        nameEl.textContent = c.name.replace(/\d/g, function (d) { return FA[d]; });
        infoEl.textContent = fa(c.reeds) + " شانه، ۶ متری از " + fa(c.prices[0]) + " تومان";
        link.href = c.url;
        link.hidden = false; hint.hidden = true;
      } else {
        link.hidden = true; hint.hidden = false;
      }
    }

    function fit() {
      var dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = cv.clientWidth || 520; H = cv.clientHeight || 650;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      G = W < 420 ? 6 : 8;
      off.width = W; off.height = H;
    }

    function wordShape(word, wi) {
      octx.clearRect(0, 0, W, H);
      octx.direction = "rtl"; octx.textAlign = "center"; octx.textBaseline = "alphabetic";
      octx.font = "900 100px Vazirmatn, Tahoma, sans-serif";
      var w = octx.measureText(word).width || 1;
      var size = Math.min(100 * (W * 0.9) / w, H * 0.42);
      octx.font = "900 " + size + "px Vazirmatn, Tahoma, sans-serif";
      octx.fillStyle = "#000";
      octx.fillText(word, W / 2, H / 2 + size * 0.3);
      var d = octx.getImageData(0, 0, W, H).data, pts = [];
      for (var y = 0; y < H; y += G) for (var x = 0; x < W; x += G) {
        if (d[(y * W + x) * 4 + 3] > 120) {
          var k = (x / W + y / H * 0.6 + wi * 0.33) % 1;
          pts.push({ x: x, y: y, c: PAL[Math.floor(k * 3) % 4] });
        }
      }
      return pts;
    }

    function imageShape(img) {
      octx.clearRect(0, 0, W, H);
      var r = img.naturalWidth / img.naturalHeight, R = W / H;
      var sw = img.naturalWidth, sh = img.naturalHeight, sx = 0, sy = 0;
      if (r > R) { sw = sh * R; sx = (img.naturalWidth - sw) / 2; } else { sh = sw / R; sy = (img.naturalHeight - sh) / 2; }
      octx.drawImage(img, sx, sy, sw, sh, 0, 0, W, H);
      var d = octx.getImageData(0, 0, W, H).data, pts = [];
      for (var y = 0; y < H; y += G) for (var x = 0; x < W; x += G) {
        var rr = 0, gg = 0, bb = 0, n = 0;
        for (var yy = 0; yy < G; yy += 2) for (var xx = 0; xx < G; xx += 2) {
          var i = ((y + yy) * W + (x + xx)) * 4;
          if (i < d.length) { rr += d[i]; gg += d[i + 1]; bb += d[i + 2]; n++; }
        }
        pts.push({ x: x, y: y, c: [rr / n, gg / n, bb / n] });
      }
      return pts;
    }

    function setTarget(pts) {
      target = pts;
      while (parts.length < pts.length) {
        var a = PAL[parts.length % 4];
        parts.push({ x: Math.random() * W, y: Math.random() * H, vx: 0, vy: 0, r: a[0], g: a[1], b: a[2], ph: Math.random() * 6.283 });
      }
    }

    function kick(p) {
      for (var i = 0; i < parts.length; i++) {
        var a = Math.random() * 6.283, s = Math.random() * p;
        parts[i].vx += Math.cos(a) * s; parts[i].vy += Math.sin(a) * s;
      }
    }

    function loadImg(src) {
      if (images[src]) return Promise.resolve(images[src]);
      return new Promise(function (res, rej) {
        var im = new Image();
        im.decoding = "async";
        im.onload = function () { images[src] = im; res(im); };
        im.onerror = rej;
        im.src = src;
      });
    }

    function next() {
      clearTimeout(timer);
      if (stage < words.length) {
        setTarget(wordShape(words[stage], stage));
        caption(null);
        kick(2.5);
        stage++;
        timer = setTimeout(next, 2400);
      } else if (CARPETS.length) {
        var c = CARPETS[turn % CARPETS.length];
        loadImg(c.img).then(function (im) {
          try { setTarget(imageShape(im)); } catch (e) { stage = 0; timer = setTimeout(next, 500); return; }
          caption(c);
          kick(3);
          turn++;
          stage = 0;
          timer = setTimeout(next, 6500);
        }, function () { turn++; stage = 0; timer = setTimeout(next, 500); });
      } else {
        stage = 0; timer = setTimeout(next, 500);
      }
    }

    function frame() {
      if (!running) return;
      t += 0.04;
      ctx.clearRect(0, 0, W, H);
      var n = target.length, sz = G - 1.2, R = Math.max(70, W / 6);
      for (var i = 0; i < parts.length; i++) {
        var p = parts[i], q = n ? target[i % n] : null;
        if (!q) continue;
        var tx = q.x + Math.sin(t + p.ph) * 0.6, ty = q.y + Math.cos(t * 0.8 + p.ph) * 0.6;
        p.vx = p.vx * 0.82 + (tx - p.x) * 0.055;
        p.vy = p.vy * 0.82 + (ty - p.y) * 0.055;
        var ex = p.x - mx, ey = p.y - my, dd = Math.sqrt(ex * ex + ey * ey) || 1;
        if (dd < R) { var k = 1 - dd / R; p.vx += ex / dd * k * 6; p.vy += ey / dd * k * 6; }
        p.x += p.vx; p.y += p.vy;
        p.r += (q.c[0] - p.r) * 0.08; p.g += (q.c[1] - p.g) * 0.08; p.b += (q.c[2] - p.b) * 0.08;
        if (i >= n) continue;
        ctx.fillStyle = "rgb(" + (p.r | 0) + "," + (p.g | 0) + "," + (p.b | 0) + ")";
        ctx.fillRect(p.x, p.y, sz, sz);
      }
      raf = requestAnimationFrame(frame);
    }

    function start() { if (!running && visible && !document.hidden) { running = true; frame(); } }
    function stop() { running = false; cancelAnimationFrame(raf); }

    function paintStatic(pts) {
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < pts.length; i++) {
        var q = pts[i];
        ctx.fillStyle = "rgb(" + (q.c[0] | 0) + "," + (q.c[1] | 0) + "," + (q.c[2] | 0) + ")";
        ctx.fillRect(q.x, q.y, G - 1.2, G - 1.2);
      }
    }

    function setPtr(e) { var r = cv.getBoundingClientRect(); mx = e.clientX - r.left; my = e.clientY - r.top; }
    function clearPtr() { mx = -1e4; my = -1e4; }
    cv.addEventListener("pointermove", setPtr);
    cv.addEventListener("pointerdown", setPtr);
    cv.addEventListener("pointerleave", clearPtr);
    cv.addEventListener("pointerup", function (e) { if (e.pointerType !== "mouse") clearPtr(); });
    cv.addEventListener("click", function () { if (!reduced) kick(16); });

    fit();
    if (reduced) {
      if (CARPETS[0]) loadImg(CARPETS[0].img).then(function (im) {
        try { paintStatic(imageShape(im)); caption(CARPETS[0]); } catch (e) { box.classList.add("no-canvas"); }
      });
      return { reweave: function () {} };
    }

    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) {
        visible = es[0].isIntersecting;
        if (visible) start(); else stop();
      }).observe(cv);
    }
    document.addEventListener("visibilitychange", function () { if (document.hidden) stop(); else start(); });
    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () { var w = W; fit(); if (Math.abs(w - W) > 30) { stage = 0; next(); } }, 250);
    });
    next();
    start();
    return { reweave: function () { kick(18); } };
  }

  var cv = document.getElementById("knots");
  if (cv) {
    var boot = function () {
      if (cv.dataset.on) return;
      cv.dataset.on = "1";
      var k = Knots(cv);
      var b = document.getElementById("reweave");
      if (b) b.addEventListener("click", function () { if (k) k.reweave(); });
    };
    if (document.fonts && document.fonts.load) {
      document.fonts.load("900 100px Vazirmatn").then(boot, boot);
      setTimeout(boot, 1800);
    } else { boot(); }
  }

  /* ---------------------------------------------------------- چیدمان اتاق */
  var rug = document.getElementById("roomRug");
  if (rug && CARPETS.length) {
    var ci = 0, si = DATA.sizes.length - 1, RW = DATA.room[0], RH = DATA.room[1];
    var img = document.getElementById("roomImg"), nm = document.getElementById("roomName"),
      pr = document.getElementById("roomPrice"), buy = document.getElementById("roomBuy"), dim = document.getElementById("roomDim");
    var render = function () {
      var c = CARPETS[ci], s = DATA.sizes[si];
      rug.style.width = (s.w / RW * 100).toFixed(1) + "%";
      rug.style.height = (s.h / RH * 100).toFixed(1) + "%";
      img.src = c.img;
      nm.textContent = c.name.replace(/\d/g, function (d) { return FA[d]; }) + "، " + s.label;
      pr.textContent = fa(c.prices[si]);
      dim.textContent = s.dim + " متر";
      buy.href = c.url + "?size=" + encodeURIComponent(s.slug);
      document.querySelectorAll(".room__carpet").forEach(function (b) { b.setAttribute("aria-pressed", String(+b.dataset.i === ci)); });
      document.querySelectorAll(".room__sizes .pill").forEach(function (b) { b.setAttribute("aria-pressed", String(+b.dataset.s === si)); });
    };
    document.addEventListener("click", function (e) {
      var b = e.target.closest(".room__carpet");
      if (b) { ci = +b.dataset.i; render(); return; }
      b = e.target.closest(".room__sizes .pill");
      if (b) { si = +b.dataset.s; render(); }
    });
    render();
  }

  /* ------------------------------------------------------------ فیلتر شانه */
  var grid = document.querySelector(".reeds-grid");
  if (grid) {
    var apply = function (r) {
      grid.querySelectorAll(".p-card").forEach(function (c) {
        var show = r ? c.dataset.reeds === r : +c.dataset.rank < 2;
        if (show) c.removeAttribute("data-hidden"); else c.setAttribute("data-hidden", "");
      });
      document.querySelectorAll(".reeds-filter .pill").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.reeds === r)); });
      document.querySelectorAll(".reeds-more [data-more]").forEach(function (a) { a.hidden = a.dataset.more !== r; });
    };
    document.querySelectorAll(".reeds-filter .pill").forEach(function (b) {
      b.addEventListener("click", function () { apply(b.dataset.reeds); });
    });
    apply("");
  }
})();

/* ردیف فرصت‌های ویژه: دکمه‌های ‹ › (بدون حرکت خودکار) */
(function () {
  "use strict";
  Array.prototype.forEach.call(document.querySelectorAll("[data-row-scroll]"), function (box) {
    var track = box.querySelector("[data-row-track]");
    var prev = box.querySelector('[data-dir="prev"]');
    var next = box.querySelector('[data-dir="next"]');
    if (!track || !prev || !next) return;
    var rtl = getComputedStyle(track).direction === "rtl";
    function pos() { return Math.abs(track.scrollLeft); }
    function update() {
      var max = track.scrollWidth - track.clientWidth;
      var scrollable = max > 4;
      prev.hidden = next.hidden = !scrollable;
      prev.disabled = pos() <= 4;
      next.disabled = pos() >= max - 4;
    }
    function step(dir) {
      var card = track.firstElementChild;
      var w = card ? card.getBoundingClientRect().width + 16 : track.clientWidth * 0.8;
      var n = Math.max(1, Math.floor(track.clientWidth / w));
      var dx = w * n * (dir === "next" ? 1 : -1) * (rtl ? -1 : 1);
      track.scrollBy({ left: dx, behavior: "smooth" });
    }
    prev.addEventListener("click", function () { step("prev"); });
    next.addEventListener("click", function () { step("next"); });
    track.addEventListener("scroll", function () { window.requestAnimationFrame(update); }, { passive: true });
    window.addEventListener("resize", update);
    update();
  });
})();
