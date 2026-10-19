/* فرشستان «خانهٔ ایرانی» — صفحهٔ اول: در و سردر، حوض، پنج‌دری و فرشی که باز می‌شود، کارگاه و ذره‌بین تراکم.
   همهٔ محتوا بدون این فایل دیده می‌شود؛ این‌جا فقط حرکت‌ها اضافه می‌شوند. */
(function () {
  "use strict";
  var FH = window.FarshHouse; if (!FH) return;
  var $ = FH.$, $$ = FH.$$, RM = FH.RM, clamp = FH.clamp, fa = FH.fa;

  /* ---------- سردر: باز شدن در با اسکرول */
  var door = $("#door"), scene = $("#door-scene"), dw = $("#doorway"), lr = $("#leaf-r"), ll = $("#leaf-l"),
    hc = $("#hero-copy"), plq = $("#plaque"), hint = $("#door-hint"), spill = $("#spill"), sky = $("#sky-fade");
  var M = {};
  function measure() {
    if (!door) return;
    scene.style.transform = "none";
    var a = scene.getBoundingClientRect(), b = dw.getBoundingClientRect();
    M = { S: Math.max(innerHeight / b.height, innerWidth / b.width) * 1.25 };
    scene.style.transformOrigin = (b.left - a.left + b.width / 2) + "px " + (b.top - a.top + b.height / 2) + "px";
  }
  function updDoor(p) {
    if (RM) p = .4;
    var a = FH.ease(clamp(p / .36)) * 80, sh = (a / 80 * .55).toFixed(3);
    lr.style.transform = "rotateY(" + (-a) + "deg)"; ll.style.transform = "rotateY(" + a + "deg)";
    lr.style.setProperty("--shade", sh); ll.style.setProperty("--shade", sh);
    spill.style.opacity = (clamp(p / .3) * .9).toFixed(3);
    var c = clamp((p - .02) / .2);
    hc.style.opacity = (1 - c).toFixed(3); hc.style.transform = "translateY(" + (-c * 40) + "px)";
    hc.style.visibility = c >= 1 ? "hidden" : "visible";
    if (plq) plq.style.opacity = (1 - c).toFixed(3);
    if (hint) hint.style.opacity = (1 - clamp(p / .08)).toFixed(3);
    if (!RM) {
      var z = clamp((p - .24) / .5), zz = z * z * (3 - 2 * z), S = 1 + (M.S - 1) * zz * zz;
      scene.style.transform = "scale(" + S.toFixed(4) + ")";
      sky.style.opacity = clamp((p - .46) / .24).toFixed(3);
    }
  }
  function openDoor(e) {
    if (e) e.preventDefault();
    var y = door.offsetTop + (door.offsetHeight - innerHeight) * .5;
    window.scrollTo({ top: y, behavior: RM ? "auto" : "smooth" });
  }
  if (door) {
    $$(".knock", door).forEach(function (k) {
      k.addEventListener("click", function () { k.classList.remove("hit"); void k.offsetWidth; k.classList.add("hit"); setTimeout(openDoor, RM ? 0 : 420); });
    });
    var od = $("#open-door"); if (od) od.addEventListener("click", openDoor);
  }

  /* ---------- پنج‌دری: فرش با اسکرول باز می‌شود */
  var room = $("#room"), rr = $("#room-rug"), roomUR = rr ? FH.Unroll(rr, "x") : null, fl = $("#floor-light");
  if (roomUR) roomUR.set(RM ? 1 : 0);
  function updRoom(p) {
    if (!roomUR) return; if (RM) p = 1;
    roomUR.set(FH.ease(clamp((p - .06) / .6)));
    if (fl) { fl.style.transform = "translateX(-50%) skewX(" + ((p - .5) * -22).toFixed(2) + "deg) scaleY(1.25)"; fl.style.opacity = (.3 + .35 * clamp(p / .7)).toFixed(3); }
  }

  function prog(el, def) { var r = el.getBoundingClientRect(), t = r.height - innerHeight; return t <= 0 ? def : clamp(-r.top / t); }
  function near(el) { var r = el.getBoundingClientRect(); return r.bottom > -50 && r.top < innerHeight + 50; }
  var tick = false;
  function onScroll() {
    if (tick) return; tick = true;
    requestAnimationFrame(function () {
      tick = false;
      if (door && near(door)) updDoor(prog(door, 0));
      if (room && near(room)) updRoom(prog(room, 1));
    });
  }
  addEventListener("scroll", onScroll, { passive: true });
  addEventListener("resize", function () { measure(); onScroll(); });
  if (door) { measure(); updDoor(prog(door, 0)); }
  if (room) updRoom(prog(room, 1));
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { measure(); onScroll(); });

  /* ---------- حوض: موج با زدن روی آب */
  var pw = $("#pool-water");
  if (pw && !RM) pw.addEventListener("pointerdown", function (e) {
    var r = pw.getBoundingClientRect(), s = document.createElement("span"); s.className = "ripple";
    s.style.left = (e.clientX - r.left) + "px"; s.style.top = (e.clientY - r.top) + "px";
    pw.appendChild(s); setTimeout(function () { s.remove(); }, 1700);
  });

  /* ---------- کاشی‌های رنگ: متن روشن یا تیره بر اساس رنگ کاشی */
  $$(".tile[data-hex]").forEach(function (t) {
    var c = parseInt(t.getAttribute("data-hex").slice(1), 16), L = ((c >> 16) * 299 + (c >> 8 & 255) * 587 + (c & 255) * 114) / 1000;
    if (L > 150) t.classList.add("lt");
  });

  /* ---------- کارگاه: دار قالی و ذره‌بین تراکم (فرش‌های این بخش با rug.js ساخته می‌شوند) */
  var loom = $("#loom");
  if (!loom) return;
  var wv = $("#woven"), wc = $("canvas", wv), lens = $("#lens"), lc = $("canvas", lens), say = $("#k-say"), link = $("#k-link"), grp = $("#k-shaneh");
  var K = { sh: +(($("input:checked", grp) || {}).value || 700), x: .5, y: .45 }, Y0 = .38, KD = null, ready = false;
  var SAY = { 700: "گره‌ها درشت‌ترند؛ نقش‌ها ساده‌تر و پررنگ دیده می‌شوند.", 1000: "گره‌ها ریزتر شده‌اند؛ مرز رنگ‌ها نرم‌تر است.",
    1200: "پیچ‌وتاب گل‌ها و برگ‌ها با جزئیات بیشتری بافته شده.", 1500: "ریزترین گره‌ها؛ از فاصلهٔ معمول، نقش تقریباً مثل نقاشی دیده می‌شود." };
  function lensCrop(mx, my) { var w = .12, h = w * 800 / 1200; return { x: clamp(mx - w / 2, 0, 1 - w), y: clamp(my - h / 2, 0, 1 - h), w: w, h: h }; }
  var pend = false;
  function place() {
    var lr2 = loom.getBoundingClientRect(), wr = wv.getBoundingClientRect();
    var x = wr.left - lr2.left + K.x * wr.width, y = wr.top - lr2.top + K.y * wr.height;
    lens.style.transform = "translate(" + x.toFixed(1) + "px," + y.toFixed(1) + "px)";
    if (pend || !ready) return; pend = true;
    requestAnimationFrame(function () {
      pend = false;
      var dpr = Math.min(2, window.devicePixelRatio || 1), W = lc.clientWidth || 170;
      if (lc.width !== Math.round(W * dpr)) lc.width = lc.height = Math.round(W * dpr);
      FarshRug.render(lc, { design: KD, knotsX: Math.round(K.sh / 700 * 14), fringe: false, crop: lensCrop(K.x, Y0 + K.y * (1 - Y0)) });
    });
  }
  function text() {
    var s = K.sh, inp = $('input[value="' + s + '"]', grp);
    say.innerHTML = "در هر ۱۰ سانت از عرض فرش " + fa(s) + " شانه، تقریباً <b>" + fa(Math.round(s / 10)) + " گره</b> کنار هم می‌نشیند.<small>" + (SAY[s] || "") + "</small>";
    link.textContent = "دیدن فرش‌های " + fa(s) + " شانه"; if (inp && inp.dataset.url) link.href = inp.dataset.url;
  }
  function from(e) { var wr = wv.getBoundingClientRect(); K.x = clamp((e.clientX - wr.left) / wr.width, .02, .98); K.y = clamp((e.clientY - wr.top) / wr.height, .02, .98); place(); }
  var drag = false;
  lens.addEventListener("pointerdown", function (e) { drag = true; lens.setPointerCapture(e.pointerId); e.preventDefault(); });
  lens.addEventListener("pointermove", function (e) { if (drag) from(e); });
  lens.addEventListener("pointerup", function () { drag = false; });
  lens.addEventListener("pointercancel", function () { drag = false; });
  wv.addEventListener("click", from);
  wv.addEventListener("pointermove", function (e) { if (e.pointerType === "mouse") from(e); });
  lens.addEventListener("keydown", function (e) {
    var st = e.shiftKey ? .1 : .03, k = e.key;
    if (k === "ArrowLeft") K.x -= st; else if (k === "ArrowRight") K.x += st; else if (k === "ArrowUp") K.y -= st; else if (k === "ArrowDown") K.y += st; else return;
    e.preventDefault(); K.x = clamp(K.x, .02, .98); K.y = clamp(K.y, .02, .98); place();
  });
  grp.addEventListener("change", function (e) { K.sh = +e.target.value; text(); place(); });
  addEventListener("resize", function () { place(); if (ready) paintWoven(); });
  function paintWoven() { FH.drawRug(wc, { design: KD, knotsX: 120, fringe: false, crop: { x: 0, y: Y0, w: 1, h: 1 - Y0 } }); }
  text(); place();
  // rug.js فقط وقتی کارگاه نزدیک دید است بار می‌شود
  var kio = new IntersectionObserver(function (es) {
    if (!es[0].isIntersecting) return; kio.disconnect();
    FH.rug().then(function () { KD = FarshRug.design(91, "lacquer"); ready = true; paintWoven(); place(); });
  }, { rootMargin: "500px 0px" });
  kio.observe(loom);
})();
