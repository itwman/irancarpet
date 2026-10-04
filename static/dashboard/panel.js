/* پنل مدیریت ایران کارپت */
(function () {
  "use strict";
  var FA = "۰۱۲۳۴۵۶۷۸۹", AR = "٠١٢٣٤٥٦٧٨٩";
  function toEn(s) {
    return String(s).replace(/[۰-۹]/g, function (d) { return FA.indexOf(d); }).replace(/[٠-٩]/g, function (d) { return AR.indexOf(d); });
  }
  function cookie(name) {
    var m = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return m ? decodeURIComponent(m[1]) : "";
  }
  function csrf() {
    var i = document.querySelector("input[name=csrfmiddlewaretoken]");
    return (i && i.value) || cookie("csrftoken");
  }
  function esc(s) { var d = document.createElement("div"); d.textContent = s == null ? "" : s; return d.innerHTML; }

  /* ------------------------------------------------ انتخاب آژاکسی (Tom Select) */
  function initAc(el) {
    if (el.tomselect || !window.TomSelect) return;
    var url = el.dataset.ac, isMedia = !!el.dataset.acMedia, canCreate = !!el.dataset.acCreate, multi = el.multiple;
    var empty = el.querySelector('option[value=""]'), placeholder = el.dataset.placeholder || (empty && empty.text !== "—" ? empty.text : "جستجو و انتخاب…");
    if (empty) empty.remove();
    var opts = {
      valueField: "value", labelField: "text", searchField: ["text"], maxOptions: 20, loadThrottle: 250,
      persist: false, preload: "focus", allowEmptyOption: false, dropdownParent: "body", placeholder: placeholder,
      // فیلتر را سرور انجام می‌دهد (با ارقام فارسی و لاتین)؛ اینجا دوباره فیلتر نشود
      score: function () { return function () { return 1; }; },
      plugins: multi ? ["remove_button"] : ["clear_button"],
      load: function (q, cb) {
        var self = this;
        fetch(url + "?q=" + encodeURIComponent(toEn(q)), { headers: { "X-Requested-With": "XMLHttpRequest" } })
          .then(function (r) { return r.json(); })
          .then(function (j) { self.clearOptions(); cb(j.results); })   // نتیجه‌های قبلی جست‌وجو نمانند
          .catch(function () { cb(); });
      },
      render: {
        no_results: function () { return '<div class="no-results">موردی یافت نشد</div>'; },
        option_create: function (d, e) { return '<div class="create">افزودن <strong>' + e(d.input) + "</strong>…</div>"; },
        loading: function () { return '<div class="spinner"></div>'; }
      }
    };
    if (isMedia) {
      var mrow = function (d, e) { return '<div class="ts-opt-media">' + (d.thumb ? '<img src="' + e(d.thumb) + '" alt="">' : "") + e(d.text) + "</div>"; };
      opts.render.option = mrow;
      opts.render.item = mrow;
    }
    if (canCreate) {
      opts.create = function (input, cb) {
        fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() }, body: JSON.stringify({ text: input }) })
          .then(function (r) { return r.json(); }).then(cb).catch(function () { cb(); });
      };
    }
    // تصویر کوچک گزینه‌های از پیش انتخاب‌شده
    if (isMedia) {
      Array.prototype.forEach.call(el.options, function (o) { if (o.dataset.thumb) o.setAttribute("data-data", JSON.stringify({ value: o.value, text: o.text, thumb: o.dataset.thumb })); });
    }
    var ts = new TomSelect(el, opts);
    if (el.closest(".filters-p")) ts.on("change", function () { el.form.submit(); });
    if (isMedia && el.id !== "galleryPick" && !multi) mediaExtras(el, ts);
    return ts;
  }

  function mediaExtras(el, ts) {
    var wrap = document.createElement("div");
    wrap.className = "media-preview";
    var up = document.createElement("label");
    up.className = "btn btn-light btn-sm mb-0";
    up.innerHTML = 'آپلود تصویر تازه<input type="file" accept="image/*" hidden>';
    el.parentNode.appendChild(up);
    el.parentNode.appendChild(wrap);
    function show() {
      var v = ts.getValue(), o = v && ts.options[v];
      wrap.innerHTML = o && o.thumb ? '<img src="' + esc(o.thumb) + '" alt="">' : "";
    }
    ts.on("change", show);
    show();
    up.querySelector("input").addEventListener("change", function () {
      upload(this.files, function (files) {
        files.forEach(function (f) { ts.addOption(f); ts.setValue(f.value); });
      });
      this.value = "";
    });
  }

  function upload(fileList, done) {
    if (!fileList || !fileList.length) return;
    var fd = new FormData();
    Array.prototype.forEach.call(fileList, function (f) { fd.append("file", f); });
    var note = document.createElement("div");
    note.className = "flash-p"; note.innerHTML = "<li class='info'>در حال آپلود…</li>";
    document.querySelector(".content").prepend(note);
    fetch("/panel/media/upload/", { method: "POST", headers: { "X-CSRFToken": csrf() }, body: fd })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        note.innerHTML = (j.errors || []).map(function (e) { return "<li class='error'>" + esc(e) + "</li>"; }).join("") +
          (j.files && j.files.length ? "<li>" + j.files.length + " فایل آپلود شد.</li>" : "");
        setTimeout(function () { note.remove(); }, 6000);
        if (j.files && j.files.length) done(j.files);
      })
      .catch(function () { note.innerHTML = "<li class='error'>آپلود ناموفق بود.</li>"; });
  }

  /* --------------------------------------------------------- ویرایشگر متن */
  function initEditor(t) {
    if (t.dataset.on || !window.Jodit) return;
    t.dataset.on = "1";
    Jodit.make(t, {
      language: "fa", direction: "rtl", height: 380, minHeight: 200, toolbarAdaptive: true, askBeforePasteHTML: false,
      askBeforePasteFromWord: false, defaultActionOnPaste: "insert_clear_html", showCharsCounter: false, showWordsCounter: true,
      showXPathInStatusbar: false, beautifyHTML: false, sourceEditor: "area",
      buttons: "paragraph,bold,italic,underline,|,ul,ol,|,link,image,table,|,align,brush,|,undo,redo,|,source,fullsize",
      uploader: {
        url: "/panel/media/upload/", headers: { "X-CSRFToken": csrf() }, format: "json",
        filesVariableName: function () { return "file"; },
        isSuccess: function (r) { return r.files && r.files.length; },
        getMessage: function (r) { return (r.errors || []).join(" "); },
        process: function (r) { return { files: (r.files || []).map(function (f) { return f.url; }), path: "", baseurl: "", error: (r.errors || []).join(" "), msg: "" }; },
        defaultHandlerSuccess: function (data) {
          var j = this.j || this.jodit;
          (data.files || []).forEach(function (u) { j.s.insertImage(u, null, 600); });
        }
      }
    });
  }

  /* ---------------------------------------------------------- ورودی‌ها */
  function initMoney(inp) {
    inp.addEventListener("input", function () {
      var v = toEn(inp.value).replace(/[^\d.\-]/g, "");
      if (v === "" || v === "-") { inp.value = v; return; }
      var parts = v.split(".");
      parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
      inp.value = parts.join(".");
    });
  }

  function initIn(root) {
    root.querySelectorAll("select[data-ac]").forEach(initAc);
    root.querySelectorAll("textarea.rich").forEach(initEditor);
    root.querySelectorAll("input.money").forEach(initMoney);
  }

  document.addEventListener("DOMContentLoaded", function () {
    initIn(document);
    if (window.jalaliDatepicker) {
      jalaliDatepicker.startWatch({ persianDigits: true, autoShow: true, autoHide: true, showTodayBtn: true, showEmptyBtn: true,
        hideAfterChange: true, time: true, hasSecond: false, separatorChars: { date: "/", between: " ", time: ":" } });
    }
  });

  // پیش از ارسال: ارقام فارسی ← لاتین، حذف جداکنندهٔ هزارگان
  document.addEventListener("submit", function (e) {
    var f = e.target;
    f.querySelectorAll("input.money").forEach(function (i) { i.value = toEn(i.value).replace(/[^\d.\-]/g, ""); });
    f.querySelectorAll('input[inputmode="numeric"], input[data-jdp], input.ltr-num').forEach(function (i) { i.value = toEn(i.value); });
    dirty = false;
    var del = f.querySelector("[data-bulk-action]");
    if (del && del.selectedOptions[0] && del.selectedOptions[0].dataset.danger) {
      if (!confirm("موارد انتخاب‌شده حذف شوند؟ این کار برگشت‌پذیر نیست.")) e.preventDefault();
    }
  }, true);

  /* ---------------------------------------- کلیک روی ردیف جدول = باز کردن */
  document.addEventListener("click", function (e) {
    var tr = e.target.closest("tr[data-href]");
    if (!tr || e.target.closest("a,button,input,label,select,.ts-wrapper")) return;
    if (e.ctrlKey || e.metaKey) window.open(tr.dataset.href); else location.href = tr.dataset.href;
  });

  /* ------------------------------------------------------- عملیات گروهی */
  var bulkForm = document.getElementById("bulkForm");
  if (bulkForm) {
    var bar = bulkForm.querySelector(".bulk");
    var sync = function () {
      var boxes = bulkForm.querySelectorAll("input[name=ids]"), n = 0;
      boxes.forEach(function (b) { if (b.checked) n++; var tr = b.closest("tr"); if (tr) tr.classList.toggle("is-checked", b.checked); });
      if (bar) { bar.hidden = n === 0; bar.querySelector("[data-count]").textContent = String(n).replace(/\d/g, function (d) { return FA[d]; }); }
    };
    bulkForm.addEventListener("change", function (e) {
      if (e.target.matches("[data-check-all]")) bulkForm.querySelectorAll("input[name=ids]").forEach(function (b) { b.checked = e.target.checked; });
      if (e.target.matches("[data-bulk-action]")) {
        var o = e.target.selectedOptions[0], inp = bulkForm.querySelector("[data-bulk-input]");
        inp.hidden = !(o && o.dataset.input);
        inp.placeholder = (o && o.dataset.input) || "";
      }
      sync();
    });
    sync();
  }

  /* ------------------------------------------------ ردیف تازه در جدول‌ها */
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-add-row]");
    if (!b) return;
    var prefix = b.dataset.addRow, table = document.querySelector('table[data-formset="' + prefix + '"]');
    var total = document.getElementById("id_" + prefix + "-TOTAL_FORMS"), n = +total.value;
    var html = table.querySelector("template").innerHTML.replace(/__prefix__/g, n);
    var tbody = table.querySelector("tbody");
    tbody.insertAdjacentHTML("beforeend", html);
    total.value = n + 1;
    var row = tbody.lastElementChild;
    row.querySelectorAll(".ts-wrapper").forEach(function (w) { w.remove(); });
    initIn(row);
  });
  document.addEventListener("change", function (e) {
    if (e.target.name && /-DELETE$/.test(e.target.name)) e.target.closest("tr").classList.toggle("is-deleted", e.target.checked);
  });

  /* ------------------------------------------------------------ گالری */
  var gal = document.getElementById("gallery");
  if (gal) {
    var ids = document.getElementById("galleryIds");
    var save = function () { ids.value = Array.prototype.map.call(gal.querySelectorAll("figure"), function (f) { return f.dataset.id; }).join(","); dirty = true; };
    var add = function (id, url) {
      if (gal.querySelector('figure[data-id="' + id + '"]')) return;
      gal.insertAdjacentHTML("beforeend", '<figure data-id="' + esc(id) + '"><img src="' + esc(url) + '" alt=""><button type="button" class="x" aria-label="برداشتن">×</button></figure>');
      save();
    };
    if (window.Sortable) Sortable.create(gal, { animation: 150, onSort: save });
    gal.addEventListener("click", function (e) { if (e.target.closest(".x")) { e.target.closest("figure").remove(); save(); } });
    var pick = document.getElementById("galleryPick");
    if (pick) {
      document.addEventListener("DOMContentLoaded", function () {
        var ts = pick.tomselect;
        if (ts) ts.on("change", function (v) { var o = v && ts.options[v]; if (o) { add(o.value, o.thumb); ts.clear(true); } });
      });
    }
  }

  /* ----------------------------------------------------- آپلود و رهاسازی */
  document.addEventListener("change", function (e) {
    var inp = e.target.closest("input[data-upload-to]");
    if (!inp) return;
    var to = inp.dataset.uploadTo;
    upload(inp.files, function (files) {
      if (to === "reload") location.reload();
      if (to === "gallery") files.forEach(function (f) {
        var g = document.getElementById("gallery");
        g.insertAdjacentHTML("beforeend", '<figure data-id="' + esc(f.value) + '"><img src="' + esc(f.url) + '" alt=""><button type="button" class="x" aria-label="برداشتن">×</button></figure>');
        document.getElementById("galleryIds").value = Array.prototype.map.call(g.querySelectorAll("figure"), function (x) { return x.dataset.id; }).join(",");
      });
    });
    inp.value = "";
  });
  var dz = document.getElementById("dropzone");
  if (dz) {
    ["dragenter", "dragover"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.add("drag"); }); });
    ["dragleave", "drop"].forEach(function (ev) { dz.addEventListener(ev, function (e) { e.preventDefault(); dz.classList.remove("drag"); }); });
    dz.addEventListener("drop", function (e) { upload(e.dataTransfer.files, function () { location.reload(); }); });
  }

  /* ------------------------------------------- امتیازهای فروشگاه (تنظیمات) */
  var addTrust = document.getElementById("addTrust");
  if (addTrust) addTrust.addEventListener("click", function () {
    document.getElementById("trust").insertAdjacentHTML("beforeend", document.getElementById("trustTpl").innerHTML);
  });
  document.addEventListener("click", function (e) { var b = e.target.closest("[data-remove-row]"); if (b) b.parentNode.remove(); });

  /* ------------------------------------------------ هشدار تغییرات ذخیره‌نشده */
  var dirty = false;
  document.querySelectorAll("form.edit").forEach(function (f) { f.addEventListener("input", function () { dirty = true; }); });
  window.addEventListener("beforeunload", function (e) { if (dirty) { e.preventDefault(); e.returnValue = ""; } });
})();
