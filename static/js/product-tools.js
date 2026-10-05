/* ابزارهای صفحهٔ فرش: ویدیو (بار شدن فقط با کلیک) و «ببین در اتاق خودت» (عکس اتاق فقط روی گوشی خود مشتری می‌ماند) */
(function () {
  "use strict";
  var vb = document.getElementById("videoBtn"), pv = document.getElementById("pVideo");
  if (vb && pv) vb.addEventListener("click", function () {
    if (!pv.hidden) { pv.hidden = true; pv.innerHTML = ""; return; }
    var k = pv.dataset.kind, src = pv.dataset.src;
    if (k === "link") { window.open(src, "_blank", "noopener"); return; }
    pv.innerHTML = k === "aparat"
      ? '<div class="p-video__box"><iframe src="' + src + '" allowfullscreen loading="lazy" title="ویدیوی فرش"></iframe></div>'
      : '<video src="' + src + '" controls autoplay playsinline preload="metadata"' + (pv.dataset.poster ? ' poster="' + pv.dataset.poster + '"' : "") + "></video>";
    pv.hidden = false;
    pv.scrollIntoView({ behavior: "smooth", block: "center" });
  });

  var rb = document.getElementById("roomBtn");
  if (!rb) return;
  var st = { x: 0, y: 0, s: 0.55, r: 0, p: 55, o: 1 }, el, stage, rug, pick;
  function apply() {
    rug.style.transform = "translate(-50%,-50%) translate(" + st.x + "px," + st.y + "px) perspective(900px) rotateX(" + st.p + "deg) rotateZ(" + st.r + "deg) scale(" + st.s + ")";
    rug.style.opacity = st.o;
  }
  function build() {
    el = document.createElement("div");
    el.className = "myroom";
    el.setAttribute("role", "dialog");
    el.setAttribute("aria-label", "فرش در اتاق شما");
    el.innerHTML =
      '<div class="myroom__bar"><strong>فرش در اتاق شما</strong><button type="button" class="myroom__x" aria-label="بستن">×</button></div>' +
      '<div class="myroom__stage"><div class="myroom__empty"><p>از اتاقت یک عکس بگیر یا از گالری انتخاب کن؛ عکس فقط روی گوشی خودت می‌ماند و جایی فرستاده نمی‌شود.</p>' +
      '<label class="btn-ic btn-ic--pink">انتخاب عکس اتاق<input type="file" accept="image/*" capture="environment" hidden></label></div>' +
      '<img class="myroom__bg" alt="" hidden><img class="myroom__rug" alt="فرش" src="' + rb.dataset.img + '" hidden></div>' +
      '<div class="myroom__ctl">' +
      '<label>اندازه<input type="range" min="15" max="160" value="55" data-k="s"></label>' +
      '<label>چرخش<input type="range" min="-90" max="90" value="0" data-k="r"></label>' +
      '<label>زاویهٔ دید<input type="range" min="0" max="75" value="55" data-k="p"></label>' +
      '<label class="myroom__pick">عکس دیگر<input type="file" accept="image/*" hidden></label></div>';
    document.body.appendChild(el);
    stage = el.querySelector(".myroom__stage");
    rug = el.querySelector(".myroom__rug");
    el.querySelector(".myroom__x").addEventListener("click", close);
    el.querySelectorAll("input[type=file]").forEach(function (inp) { inp.addEventListener("change", load); });
    el.querySelectorAll("input[type=range]").forEach(function (r) {
      r.addEventListener("input", function () {
        var k = r.dataset.k; st[k] = k === "s" ? r.value / 100 : +r.value; apply();
      });
    });
    var drag = null;
    rug.addEventListener("pointerdown", function (e) { drag = { x: e.clientX - st.x, y: e.clientY - st.y }; rug.setPointerCapture(e.pointerId); e.preventDefault(); });
    rug.addEventListener("pointermove", function (e) { if (!drag) return; st.x = e.clientX - drag.x; st.y = e.clientY - drag.y; apply(); });
    rug.addEventListener("pointerup", function () { drag = null; });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && el && !el.hidden) close(); });
  }
  function load(e) {
    var f = e.target.files && e.target.files[0];
    if (!f) return;
    var bg = el.querySelector(".myroom__bg");
    if (bg.src) URL.revokeObjectURL(bg.src);
    bg.src = URL.createObjectURL(f);
    bg.hidden = false; rug.hidden = false;
    el.querySelector(".myroom__empty").hidden = true;
    st.x = 0; st.y = stage.clientHeight * 0.18; apply();
  }
  function close() { el.hidden = true; document.body.style.overflow = ""; }
  rb.addEventListener("click", function () {
    if (!el) build();
    el.hidden = false;
    document.body.style.overflow = "hidden";
    apply();
  });
})();
