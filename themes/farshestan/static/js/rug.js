/* FarshRug — مولد رویه‌ای فرش ایرانی روی canvas (برای پروتوتایپ‌های فرشستان)
 *
 *   FarshRug.render(canvas, opts)          فرش کامل با ترنج، لچک، حاشیه‌ها، زمینهٔ افشان، ریشه و بافت گره
 *   FarshRug.design(seed, paletteName)      شیء طرح (برای کشیدن دوبارهٔ همان طرح با تراکم دیگر)
 *   FarshRug.PALETTES                       پالت‌ها: lacquer, cream, silver, navy, turquoise, charcoal, beige, metallic
 *
 * opts = { seed, palette, knotsX (تعداد گره در عرض؛ تراکم)، fringe (true/false)، shade (true/false)،
 *          crop: {x,y,w,h} بخشی از فرش به نسبت ۰..۱ (برای ذره‌بین)، bg }
 * اندازهٔ canvas از width/height خودش خوانده می‌شود. نسبت فرش ۲ به ۳ است (عرض به طول).
 */
(function (g) {
  "use strict";
  var PALETTES = {
    lacquer:   { field: "#8E1F22", field2: "#7A181C", border: "#1F2A4A", guard: "#E9D9B6", medal: "#1F2A4A", medal2: "#E9D9B6", accent: "#C9962E", ink: "#2A1A14", motif: "#E9D9B6", motif2: "#3F6E7A" },
    cream:     { field: "#E9DCC2", field2: "#E1D2B4", border: "#7A2E2A", guard: "#2E3A5C", medal: "#7A2E2A", medal2: "#C9962E", accent: "#2E3A5C", ink: "#3B241A", motif: "#B5653E", motif2: "#5E7A6A" },
    silver:    { field: "#C9C6C0", field2: "#BFBCB6", border: "#5A5753", guard: "#E7E4DE", medal: "#6E6A66", medal2: "#ECE9E3", accent: "#9A8F80", ink: "#3A3836", motif: "#8E8A85", motif2: "#A7A39D" },
    navy:      { field: "#1E2A4A", field2: "#18223D", border: "#8E1F22", guard: "#E7D7B2", medal: "#8E1F22", medal2: "#E7D7B2", accent: "#C9962E", ink: "#0F1528", motif: "#C9A86A", motif2: "#6E8FA8" },
    turquoise: { field: "#1F6F70", field2: "#1A6162", border: "#E9DCC2", guard: "#8E1F22", medal: "#E9DCC2", medal2: "#8E1F22", accent: "#C9962E", ink: "#0E2E2E", motif: "#E9DCC2", motif2: "#C9962E" },
    charcoal:  { field: "#3B3936", field2: "#33312E", border: "#A9A6A1", guard: "#5E5B57", medal: "#A9A6A1", medal2: "#6E6A66", accent: "#C9C6C0", ink: "#1E1D1B", motif: "#77736E", motif2: "#8E8A85" },
    beige:     { field: "#D8C3A0", field2: "#CFB893", border: "#5A3A2A", guard: "#EFE4CF", medal: "#5A3A2A", medal2: "#EFE4CF", accent: "#8E5A3A", ink: "#3A2618", motif: "#8E5A3A", motif2: "#6E7A5A" },
    metallic:  { field: "#9AA0A3", field2: "#8F9598", border: "#3E4447", guard: "#D3D7D9", medal: "#3E4447", medal2: "#D3D7D9", accent: "#C3C7C9", ink: "#24292B", motif: "#C3C7C9", motif2: "#6A7275" }
  };

  function rng(seed) { var s = (seed >>> 0) || 1; return function () { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return ((s >>> 0) % 100000) / 100000; }; }

  function design(seed, paletteName) {
    var r = rng(seed || 7);
    return {
      seed: seed || 7,
      pal: PALETTES[paletteName] || PALETTES.lacquer,
      medalPoints: [8, 12, 16][Math.floor(r() * 3)],
      medalLobes: 6 + Math.floor(r() * 6),
      latticeN: 5 + Math.floor(r() * 3),
      borderMotif: Math.floor(r() * 3),   // ۰ گل‌وبوته، ۱ کتیبه‌ای، ۲ لوزی زنجیره
      fieldMotif: Math.floor(r() * 3),    // ۰ هراتی، ۱ افشان گل، ۲ خشتی
      corner: r() > 0.25
    };
  }

  // ---------------------------------------------------------------- شکل‌های پایه
  function star(ctx, cx, cy, rO, rI, n, rot) {
    ctx.beginPath();
    for (var i = 0; i < n * 2; i++) {
      var a = rot + i * Math.PI / n, rr = i % 2 ? rI : rO;
      ctx.lineTo(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr);
    }
    ctx.closePath();
  }
  function lobed(ctx, cx, cy, rx, ry, lobes, depth) {
    ctx.beginPath();
    for (var i = 0; i <= 240; i++) {
      var t = i / 240 * Math.PI * 2, k = 1 + depth * Math.cos(lobes * t);
      ctx.lineTo(cx + Math.cos(t) * rx * k, cy + Math.sin(t) * ry * k);
    }
    ctx.closePath();
  }
  function rosette(ctx, cx, cy, r, petals, c1, c2) {
    ctx.fillStyle = c1;
    for (var i = 0; i < petals; i++) {
      var a = i * Math.PI * 2 / petals;
      ctx.beginPath();
      ctx.ellipse(cx + Math.cos(a) * r * .55, cy + Math.sin(a) * r * .55, r * .48, r * .2, a, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = c2; ctx.beginPath(); ctx.arc(cx, cy, r * .28, 0, Math.PI * 2); ctx.fill();
  }
  function leaf(ctx, cx, cy, len, ang, c) {
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang); ctx.fillStyle = c;
    ctx.beginPath(); ctx.moveTo(0, 0); ctx.quadraticCurveTo(len * .5, -len * .28, len, 0); ctx.quadraticCurveTo(len * .5, len * .28, 0, 0); ctx.fill();
    ctx.restore();
  }
  function boteh(ctx, cx, cy, s, ang, c1, c2) {   // بته‌جقه
    ctx.save(); ctx.translate(cx, cy); ctx.rotate(ang); ctx.scale(s, s);
    ctx.fillStyle = c1; ctx.beginPath();
    ctx.moveTo(0, -10); ctx.bezierCurveTo(9, -10, 10, 4, 2, 9); ctx.bezierCurveTo(-6, 13, -10, 3, -5, -2); ctx.bezierCurveTo(-2, -6, 2, -6, 0, -10); ctx.fill();
    ctx.fillStyle = c2; ctx.beginPath(); ctx.arc(0.5, 2.5, 3.2, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  // ---------------------------------------------------------------- کشیدن طرح برداری (W×H، نسبت ۲:۳)
  function paint(ctx, W, H, d) {
    var p = d.pal, r = rng(d.seed * 31 + 3);
    // زمینه با «ابرش» (نوارهای افقی رنگ کمی متفاوت؛ نشانهٔ فرش واقعی)
    ctx.fillStyle = p.field; ctx.fillRect(0, 0, W, H);
    for (var y = 0; y < H; y += H / 18) { if (r() > .55) { ctx.fillStyle = p.field2; ctx.globalAlpha = .35 + r() * .3; ctx.fillRect(0, y, W, H / 18 * (0.4 + r())); } }
    ctx.globalAlpha = 1;

    var b1 = W * .045, b2 = W * .11, b3 = W * .135; // حاشیه‌ها
    // حاشیهٔ بیرونی، اصلی و باریکه‌ها
    ctx.fillStyle = p.guard; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = p.border; ctx.fillRect(b1 * .45, b1 * .45, W - b1 * .9, H - b1 * .9);
    ctx.fillStyle = p.guard; ctx.fillRect(b1, b1, W - 2 * b1, H - 2 * b1);
    ctx.fillStyle = p.border; ctx.fillRect(b1 * 1.25, b1 * 1.25, W - 2.5 * b1, H - 2.5 * b1);
    // نقش حاشیهٔ اصلی
    var inner = { x: b2, y: b2, w: W - 2 * b2, h: H - 2 * b2 };
    function borderMotifs(x0, y0, x1, y1, horiz) {
      var len = horiz ? x1 - x0 : y1 - y0, n = Math.max(4, Math.round(len / (W * .085))), step = len / n, mid = horiz ? (y0 + y1) / 2 : (x0 + x1) / 2;
      for (var i = 0; i < n; i++) {
        var c = (horiz ? x0 : y0) + step * (i + .5), cx = horiz ? c : mid, cy = horiz ? mid : c, s = W * .024;
        if (d.borderMotif === 0) {
          rosette(ctx, cx, cy, s, 6, i % 2 ? p.motif : p.accent, p.guard);
          leaf(ctx, cx + (horiz ? step / 2 : 0), cy + (horiz ? 0 : step / 2), s * 1.1, horiz ? (i % 2 ? .5 : -.5) : Math.PI / 2 + (i % 2 ? .5 : -.5), p.motif2);
        } else if (d.borderMotif === 1) {
          ctx.fillStyle = i % 2 ? p.accent : p.motif; star(ctx, cx, cy, s * 1.15, s * .55, 8, 0); ctx.fill();
          ctx.fillStyle = p.border; ctx.beginPath(); ctx.arc(cx, cy, s * .35, 0, 7); ctx.fill();
        } else {
          ctx.fillStyle = p.motif; ctx.beginPath(); ctx.moveTo(cx, cy - s); ctx.lineTo(cx + s * .8, cy); ctx.lineTo(cx, cy + s); ctx.lineTo(cx - s * .8, cy); ctx.closePath(); ctx.fill();
          ctx.fillStyle = p.accent; ctx.beginPath(); ctx.arc(cx, cy, s * .3, 0, 7); ctx.fill();
        }
      }
    }
    var m1 = b1 * 1.25, m2 = b2 - b1 * .35;
    borderMotifs(m1, m1, W - m1, m2, true); borderMotifs(m1, H - m2, W - m1, H - m1, true);
    borderMotifs(m1, m2, m2, H - m2, false); borderMotifs(W - m2, m2, W - m1, H - m2, false);
    // باریکهٔ داخلی
    ctx.fillStyle = p.guard; ctx.fillRect(b2 - b1 * .35, b2 - b1 * .35, W - 2 * b2 + b1 * .7, H - 2 * b2 + b1 * .7);
    ctx.fillStyle = p.field; ctx.fillRect(inner.x, inner.y, inner.w, inner.h);
    for (var yy = inner.y; yy < inner.y + inner.h; yy += inner.h / 14) { if (r() > .6) { ctx.fillStyle = p.field2; ctx.globalAlpha = .4; ctx.fillRect(inner.x, yy, inner.w, inner.h / 14 * (0.5 + r())); } }
    ctx.globalAlpha = 1;

    ctx.save(); ctx.beginPath(); ctx.rect(inner.x, inner.y, inner.w, inner.h); ctx.clip();
    // زمینهٔ افشان / هراتی / خشتی
    var N = d.latticeN, cw = inner.w / N, ch = cw * 1.15;
    for (var row = -1; row < inner.h / ch + 1; row++) {
      for (var col = -1; col <= N; col++) {
        var cx = inner.x + cw * (col + (row % 2 ? .5 : 0)) + cw / 2, cy = inner.y + ch * row + ch / 2;
        if (d.fieldMotif === 0) {
          ctx.strokeStyle = p.motif2; ctx.lineWidth = W * .004; ctx.globalAlpha = .55;
          ctx.beginPath(); ctx.moveTo(cx, cy - ch * .45); ctx.lineTo(cx + cw * .42, cy); ctx.lineTo(cx, cy + ch * .45); ctx.lineTo(cx - cw * .42, cy); ctx.closePath(); ctx.stroke();
          ctx.globalAlpha = 1; rosette(ctx, cx, cy, cw * .12, 5, p.motif, p.accent);
          leaf(ctx, cx, cy - ch * .45, cw * .22, -2.4, p.motif2); leaf(ctx, cx, cy + ch * .45, cw * .22, .8, p.motif2);
        } else if (d.fieldMotif === 1) {
          boteh(ctx, cx, cy, cw / 34, (row + col) % 2 ? .6 : -.6 + Math.PI, p.motif, p.accent);
          rosette(ctx, cx + cw * .5, cy + ch * .5, cw * .07, 6, p.motif2, p.guard);
        } else {
          ctx.strokeStyle = p.motif; ctx.lineWidth = W * .005; ctx.globalAlpha = .7;
          ctx.strokeRect(cx - cw * .45, cy - ch * .45, cw * .9, ch * .9); ctx.globalAlpha = 1;
          ctx.fillStyle = p.motif2; star(ctx, cx, cy, cw * .2, cw * .09, 8, 0); ctx.fill();
          ctx.fillStyle = p.accent; ctx.beginPath(); ctx.arc(cx, cy, cw * .05, 0, 7); ctx.fill();
        }
      }
    }
    // لچک‌ها (یک‌چهارم ترنج در گوشه‌ها)
    if (d.corner) {
      [[inner.x, inner.y], [inner.x + inner.w, inner.y], [inner.x, inner.y + inner.h], [inner.x + inner.w, inner.y + inner.h]].forEach(function (c) {
        ctx.fillStyle = p.medal; lobed(ctx, c[0], c[1], inner.w * .3, inner.w * .3, d.medalLobes, .07); ctx.fill();
        ctx.fillStyle = p.medal2; lobed(ctx, c[0], c[1], inner.w * .22, inner.w * .22, d.medalLobes, .07); ctx.fill();
        ctx.fillStyle = p.field2; lobed(ctx, c[0], c[1], inner.w * .16, inner.w * .16, d.medalLobes, .06); ctx.fill();
        rosette(ctx, c[0] + (c[0] > W / 2 ? -1 : 1) * inner.w * .08, c[1] + (c[1] > H / 2 ? -1 : 1) * inner.w * .08, inner.w * .045, 6, p.accent, p.medal);
      });
    }
    // ترنج مرکزی و سرترنج‌ها
    var mx = W / 2, my = H / 2, mrx = inner.w * .34, mry = inner.h * .27;
    ctx.fillStyle = p.medal; ctx.beginPath(); ctx.moveTo(mx, my - mry * 1.42); ctx.lineTo(mx + mrx * .2, my - mry * 1.05); ctx.lineTo(mx - mrx * .2, my - mry * 1.05); ctx.fill();
    ctx.beginPath(); ctx.moveTo(mx, my + mry * 1.42); ctx.lineTo(mx + mrx * .2, my + mry * 1.05); ctx.lineTo(mx - mrx * .2, my + mry * 1.05); ctx.fill();
    [-1, 1].forEach(function (s) { ctx.fillStyle = p.medal; lobed(ctx, mx, my + s * mry * 1.16, mrx * .26, mry * .16, 6, .12); ctx.fill(); ctx.fillStyle = p.accent; ctx.beginPath(); ctx.arc(mx, my + s * mry * 1.16, mrx * .07, 0, 7); ctx.fill(); });
    ctx.fillStyle = p.medal; lobed(ctx, mx, my, mrx, mry, d.medalLobes, .09); ctx.fill();
    ctx.fillStyle = p.medal2; lobed(ctx, mx, my, mrx * .86, mry * .86, d.medalLobes, .09); ctx.fill();
    ctx.fillStyle = p.field; lobed(ctx, mx, my, mrx * .74, mry * .74, d.medalLobes, .08); ctx.fill();
    // تزیین داخل ترنج
    for (var k = 0; k < d.medalPoints; k++) {
      var a = k * Math.PI * 2 / d.medalPoints;
      leaf(ctx, mx + Math.cos(a) * mrx * .28, my + Math.sin(a) * mry * .28, mrx * .34, a, k % 2 ? p.motif2 : p.motif);
    }
    ctx.fillStyle = p.medal; star(ctx, mx, my, mrx * .36, mrx * .2, d.medalPoints, -Math.PI / 2); ctx.fill();
    ctx.fillStyle = p.medal2; star(ctx, mx, my, mrx * .27, mrx * .15, d.medalPoints, -Math.PI / 2 + Math.PI / d.medalPoints); ctx.fill();
    rosette(ctx, mx, my, mrx * .14, 8, p.accent, p.medal);
    ctx.restore();
  }

  // ---------------------------------------------------------------- رندر نهایی با بافت گره
  var cache = {};
  function master(d) {   // طرح برداری با وضوح بالا یک بار کشیده و کش می‌شود
    var key = d.seed + "|" + JSON.stringify(d.pal);
    if (cache[key]) return cache[key];
    var c = document.createElement("canvas"); c.width = 800; c.height = 1200;
    paint(c.getContext("2d"), 800, 1200, d);
    return (cache[key] = c);
  }

  function render(canvas, opts) {
    opts = opts || {};
    var d = opts.design || design(opts.seed, opts.palette);
    var ctx = canvas.getContext("2d"), CW = canvas.width, CH = canvas.height;
    var fringe = opts.fringe !== false, fr = fringe ? Math.round(CH * .045) : 0;
    var bodyH = CH - 2 * fr, src = master(d);
    var crop = opts.crop || { x: 0, y: 0, w: 1, h: 1 };
    var kx = opts.knotsX || 90, ky = Math.round(kx * 1.5 * crop.h / crop.w * (crop.w / 1) / (crop.h / 1)) || Math.round(kx * 1.5);
    ky = Math.round(kx * (bodyH / CW));
    // نمونه‌برداری: هر گره یک خانه
    var t = document.createElement("canvas"); t.width = kx; t.height = ky;
    var tc = t.getContext("2d");
    tc.drawImage(src, crop.x * 800, crop.y * 1200, crop.w * 800, crop.h * 1200, 0, 0, kx, ky);
    var px = tc.getImageData(0, 0, kx, ky).data;
    if (opts.bg) { ctx.fillStyle = opts.bg; ctx.fillRect(0, 0, CW, CH); } else ctx.clearRect(0, 0, CW, CH);
    var gw = CW / kx, gh = bodyH / ky, r = rng(d.seed * 7 + 1);
    for (var y = 0; y < ky; y++) {
      for (var x = 0; x < kx; x++) {
        var i = (y * kx + x) * 4, n = opts.shade === false ? 0 : (r() - .5) * 18;
        ctx.fillStyle = "rgb(" + (px[i] + n | 0) + "," + (px[i + 1] + n | 0) + "," + (px[i + 2] + n | 0) + ")";
        ctx.fillRect(x * gw, fr + y * gh, gw + .6, gh + .6);
      }
    }
    // سایه‌روشن گره (وقتی گره‌ها درشت‌اند دیده می‌شود)
    if (gw > 3 && opts.shade !== false) {
      ctx.globalAlpha = .18; ctx.fillStyle = "#000";
      for (var yy = 0; yy < ky; yy++) for (var xx = 0; xx < kx; xx++) ctx.fillRect(xx * gw + gw * .55, fr + yy * gh, gw * .45, gh);
      ctx.globalAlpha = .12; ctx.fillStyle = "#fff";
      for (var y2 = 0; y2 < ky; y2++) ctx.fillRect(0, fr + y2 * gh, CW, gh * .18);
      ctx.globalAlpha = 1;
    }
    // ریشه
    if (fringe) {
      ctx.strokeStyle = "#EFE6D3"; ctx.lineWidth = Math.max(1, CW / 160);
      for (var fx = CW * .02; fx < CW * .98; fx += CW / 70) {
        var l1 = fr * (.75 + r() * .25), l2 = fr * (.75 + r() * .25);
        ctx.beginPath(); ctx.moveTo(fx, fr); ctx.lineTo(fx + (r() - .5) * 2, fr - l1); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(fx, CH - fr); ctx.lineTo(fx + (r() - .5) * 2, CH - fr + l2); ctx.stroke();
      }
    }
    return d;
  }

  /* کمکی: همهٔ <canvas data-rug="seed,palette,knotsX"> صفحه را پر می‌کند (با اندازهٔ واقعی CSS و devicePixelRatio) */
  function hydrate(root) {
    (root || document).querySelectorAll("canvas[data-rug]").forEach(function (c) {
      var a = c.getAttribute("data-rug").split(","), dpr = Math.min(2, window.devicePixelRatio || 1);
      var w = c.clientWidth || 200, h = c.clientHeight || w * 1.6;
      c.width = Math.round(w * dpr); c.height = Math.round(h * dpr);
      render(c, { seed: +a[0], palette: a[1], knotsX: +(a[2] || 90), fringe: a[3] !== "nofringe" });
    });
  }

  g.FarshRug = { render: render, design: design, hydrate: hydrate, PALETTES: PALETTES };
})(window);
