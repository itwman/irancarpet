/* ماشین‌حساب اقساط (صفحهٔ خرید اقساطی، تسویه حساب، صفحهٔ محصول). محاسبهٔ اصلی روی سرور است: /installments/quote/ */
(function () {
  "use strict";
  var FA = "۰۱۲۳۴۵۶۷۸۹";
  function fa(s) { return String(s).replace(/\d/g, function (d) { return FA[d]; }); }
  function money(n) { return fa(String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, "٬")); }
  function latin(s) {
    return String(s || "").replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); })
      .replace(/[٠-٩]/g, function (d) { return "٠١٢٣٤٥٦٧٨٩".indexOf(d); }).replace(/[^\d]/g, "");
  }

  function init(root) {
    var plans = [];
    try { plans = JSON.parse(root.dataset.plans || "[]"); } catch (e) { return; }
    if (!plans.length) return;
    var form = root.closest("form");
    var amountIn = root.querySelector("[data-amount]");
    var down = root.querySelector("[data-down]");
    var months = root.querySelector("[data-months]");
    var stepWrap = root.querySelector("[data-step-wrap]");
    var out = root.querySelector("[data-result]");
    var err = root.querySelector("[data-err]");
    var want = { down: root.dataset.down, months: root.dataset.months, step: root.dataset.step };
    var timer = null, seq = 0;

    function plan() {
      var r = root.querySelector("input[name=inst_plan]:checked");
      var id = r ? +r.value : plans[0].id;
      for (var i = 0; i < plans.length; i++) if (plans[i].id === id) return plans[i];
      return plans[0];
    }
    function total() { return amountIn ? +latin(amountIn.value) : +root.dataset.total; }
    function step() {
      var r = root.querySelector("input[name=inst_step]:checked:not([disabled])");
      return r ? +r.value : plan().steps[0];
    }
    function fill(sel, vals, cur, label) {
      var keep = String(cur);
      sel.innerHTML = "";
      vals.forEach(function (v) {
        var o = document.createElement("option");
        o.value = v; o.textContent = label(v);
        sel.appendChild(o);
      });
      if (vals.map(String).indexOf(keep) >= 0) sel.value = keep;
    }
    function downLabel(v) {
      if (!+v) return "بدون پیش‌پرداخت";
      var t = total();
      if (!t) return fa(v) + "٪";
      var m = Math.ceil(t * v / 100 / 1000) * 1000 / 1e6;
      return fa(v) + "٪ — " + fa(String(+m.toFixed(m >= 10 ? 1 : 2)).replace(".", "٫")) + " میلیون";
    }
    function fillDown() {
      var p = plan();
      fill(down, p.down, want.down != null ? want.down : (down.value || p.down[0]), downLabel);
      if (!down.value) down.value = p.down[0];
      want.down = null;
    }
    function onPlan() {
      var p = plan();
      fillDown();
      var radios = root.querySelectorAll("input[name=inst_step]");
      radios.forEach(function (r) { r.disabled = p.steps.indexOf(+r.value) < 0; });
      if (stepWrap) stepWrap.hidden = p.steps.length < 2;
      var s = want.step != null ? +want.step : step();
      if (p.steps.indexOf(s) < 0) s = p.steps[0];
      radios.forEach(function (r) { r.checked = +r.value === s; });
      want.step = null;
      if (form) {
        form.querySelectorAll("[data-plan-fields]").forEach(function (fs) {
          var on = +fs.dataset.planFields === p.id;
          fs.hidden = !on;
          fs.querySelectorAll("input,select,textarea").forEach(function (i) { i.disabled = !on; });
        });
      }
      onStep();
    }
    function onStep() {
      var p = plan(), s = step();
      var ms = p.months[String(s)] || [];
      var cur = want.months != null ? want.months : (months.value || ms[ms.length - 1]);
      fill(months, ms, cur, function (v) {
        var n = v / s;
        return fa(v) + " ماه — " + fa(n) + " قسط";
      });
      if (!months.value && ms.length) months.value = ms[ms.length - 1];
      want.months = null;
      quote();
    }
    function quote() {
      clearTimeout(timer);
      timer = setTimeout(function () {
        var p = plan(), t = total();
        if (!t || t < 100000) { show({ error: "مبلغ خرید را وارد کنید." }); return; }
        var my = ++seq;
        var q = "plan=" + p.id + "&total=" + t + "&down=" + down.value + "&months=" + months.value + "&step=" + step();
        root.classList.add("is-loading");
        fetch("/installments/quote/?" + q, { headers: { Accept: "application/json" } })
          .then(function (r) { return r.json(); })
          .then(function (d) { if (my === seq) show(d); })
          .catch(function () { if (my === seq) show({ error: "اتصال برقرار نشد؛ دوباره امتحان کنید." }); })
          .then(function () { if (my === seq) root.classList.remove("is-loading"); });
      }, 180);
    }
    function set(name, text) {
      root.querySelectorAll('[data-o="' + name + '"]').forEach(function (el) { el.textContent = text; });
    }
    function show(d) {
      if (d.error) {
        err.textContent = d.error; err.hidden = false; out.classList.add("is-err");
        root.dispatchEvent(new CustomEvent("inst:quote", { detail: null, bubbles: true }));
        return;
      }
      err.hidden = true; out.classList.remove("is-err");
      var per = d.step === 2 ? "هر دو ماه" : "ماهانه";
      set("installment", money(d.installment));
      set("per", per);
      set("count", fa(d.count) + " قسط " + per);
      set("down", d.down ? money(d.down) + " تومان" : "ندارد");
      set("principal", money(d.principal) + " تومان");
      set("interest", fa(String(+d.interest_percent.toFixed(2))) + "٪");
      set("ras", fa(Math.round(d.ras_days)) + " روز");
      set("interest_amount", money(d.interest_amount) + " تومان");
      set("payable", money(d.payable_total) + " تومان");
      set("first", fa(d.schedule[0].jdate));
      var tb = root.querySelector("[data-schedule]");
      if (tb) {
        tb.innerHTML = "";
        d.schedule.forEach(function (r) {
          var tr = document.createElement("tr");
          tr.innerHTML = "<td>" + fa(r.n) + "</td><td><bdi>" + fa(r.jdate) + "</bdi></td><td>" + money(r.amount) + "</td>";
          tb.appendChild(tr);
        });
      }
      root.dispatchEvent(new CustomEvent("inst:quote", { detail: d, bubbles: true }));
    }

    root.addEventListener("change", function (e) {
      var n = e.target.name;
      if (n === "inst_plan") onPlan();
      else if (n === "inst_step") onStep();
      else if (n === "inst_down" || n === "inst_months") quote();
    });
    if (amountIn) {
      amountIn.addEventListener("input", function () {
        var v = latin(amountIn.value);
        amountIn.value = v ? money(v) : "";
        fillDown();
        quote();
      });
      amountIn.value = money(latin(amountIn.value));
    }
    root.refresh = function (t) { root.dataset.total = t; fillDown(); quote(); };
    onPlan();
  }

  document.querySelectorAll("[data-inst-calc]").forEach(init);
})();
