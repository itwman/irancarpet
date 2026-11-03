/* بازارچه: اسلاید ویترین، هم‌رسانی فروشگاه و ریزکارهای پنل فروشنده. */
(function () {
  "use strict";

  // اسلاید: با انگشت یا نقطه‌ها ورق می‌خورد؛ هر ۶ ثانیه خودکار، و با اولین لمس/ماوس/فوکوس برای همیشه می‌ایستد.
  document.querySelectorAll("[data-slider]").forEach(function (box) {
    var track = box.querySelector(".st-slides__track");
    var dots = Array.prototype.slice.call(box.querySelectorAll("[data-slide]"));
    var slides = track ? track.children : [];
    if (!track || slides.length < 2) return;
    var cur = 0, timer = null;
    var rtl = getComputedStyle(track).direction === "rtl";
    function go(i) {  // فقط خود نوار اسلاید جابه‌جا می‌شود، نه صفحه (در RTL، scrollLeft منفی است)
      cur = (i + slides.length) % slides.length;
      track.scrollTo({ left: (rtl ? -1 : 1) * cur * track.clientWidth });
    }
    function mark(i) {
      cur = i;
      dots.forEach(function (d, k) { d.setAttribute("aria-current", k === i ? "true" : "false"); });
    }
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (e.isIntersecting && e.intersectionRatio > 0.6) mark(Array.prototype.indexOf.call(slides, e.target));
        });
      }, { root: track, threshold: [0.6] });
      Array.prototype.forEach.call(slides, function (s) { io.observe(s); });
    }
    dots.forEach(function (d) {
      d.addEventListener("click", function () { stop(); go(+d.getAttribute("data-slide")); });
    });
    function stop() { if (timer) { clearInterval(timer); timer = null; } }
    ["pointerdown", "touchstart", "focusin", "mouseenter", "wheel"].forEach(function (ev) {
      box.addEventListener(ev, stop, { passive: true });
    });
    var reduce = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!reduce) {
      timer = setInterval(function () {
        if (document.visibilityState === "visible") go(cur + 1);
      }, 6000);
    }
  });

  // هم‌رسانی: منوی هم‌رسانی گوشی، وگرنه کپی پیوند.
  document.addEventListener("click", function (e) {
    var b = e.target.closest && e.target.closest("[data-share]");
    if (!b) return;
    var url = new URL(b.getAttribute("data-share"), location.href).href;
    if (navigator.share) {
      navigator.share({ title: document.title, url: url }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(url).then(function () {
        b.setAttribute("aria-label", "پیوند کپی شد");
        b.classList.add("is-done");
      });
    }
  });

  // پنل: کلید موجود/ناموجود با یک لمس (بدون بارگذاری دوبارهٔ صفحه)
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest("[data-stock-toggle]");
    if (!t) return;
    e.preventDefault();
    var on = t.getAttribute("aria-pressed") !== "true";
    t.setAttribute("aria-pressed", on ? "true" : "false");
    t.disabled = true;
    var fd = new FormData();
    fd.append("on", on ? "1" : "0");
    fd.append("csrfmiddlewaretoken", (document.querySelector("[name=csrfmiddlewaretoken]") || {}).value || "");
    fetch(t.getAttribute("data-stock-toggle"), { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        t.setAttribute("aria-pressed", j.on ? "true" : "false");
        var lab = t.closest("[data-row]") && t.closest("[data-row]").querySelector("[data-stock-label]");
        if (lab) lab.textContent = j.on ? "موجود" : "ناموجود";
      })
      .catch(function () { t.setAttribute("aria-pressed", on ? "false" : "true"); })
      .finally(function () { t.disabled = false; });
  });

  // پنل: نوار کار گروهی فقط وقتی کالایی انتخاب شده
  var bulk = document.querySelector("[data-bulk]");
  if (bulk) {
    document.addEventListener("change", function (e) {
      if (!e.target.matches || !e.target.matches("input[form=bulkf]")) return;
      var n = document.querySelectorAll("input[form=bulkf]:checked").length;
      bulk.hidden = !n;
      var lab = bulk.querySelector("[data-bulk-n]");
      if (lab) lab.textContent = n.toLocaleString("fa-IR") + " کالا";
    });
  }

  // پنل: پیش‌نمایش زندهٔ رنگ فروشگاه
  document.querySelectorAll("[data-accent-pick]").forEach(function (inp) {
    inp.addEventListener("change", function () {
      var h = document.getElementById("accentHidden");
      if (h) h.disabled = true;
      var box = document.querySelector("[data-accent-preview]");
      if (box) box.style.setProperty("--acc", inp.value);
    });
  });
  // پنل: راهنمای هر بخش؛ بسته‌ها در همین گوشی یادشان می‌ماند و دکمهٔ «راهنما» دوباره بازشان می‌کند.
  function guideOff(key, off) {
    try {
      var list = (localStorage.getItem("sp-guide-off") || "").split(",").filter(Boolean);
      list = list.filter(function (k) { return k !== key; });
      if (off) list.push(key);
      localStorage.setItem("sp-guide-off", list.join(","));
    } catch (e) {}
  }
  document.addEventListener("click", function (e) {
    var c = e.target.closest && e.target.closest("[data-guide-close]");
    if (c) {
      var box = c.closest("[data-guide]");
      box.hidden = true;
      guideOff(box.getAttribute("data-guide"), true);
      var o = document.querySelector("[data-guide-open]");
      if (o) o.focus();
      return;
    }
    var op = e.target.closest && e.target.closest("[data-guide-open]");
    if (op) {
      var g = document.getElementById("guide-" + op.getAttribute("data-guide-open"));
      if (!g) return;
      g.hidden = !g.hidden;
      guideOff(op.getAttribute("data-guide-open"), g.hidden);
      if (!g.hidden) g.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });

  // نوار بالا: منوی حساب با کلیک بیرون بسته می‌شود
  document.addEventListener("click", function (e) {
    document.querySelectorAll("details.sp-menu[open]").forEach(function (d) {
      if (!d.contains(e.target)) d.removeAttribute("open");
    });
  });
})();
