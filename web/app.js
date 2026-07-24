/* Alarrab CodeVision AI — Arabic RTL frontend (vanilla JS, no build step). */
"use strict";

var API_BASE = "";

var STATUS_LABELS = {
  pass: "مستوفى مبدئيًا",
  fail: "غير مستوفى",
  needs_review: "يحتاج مراجعة"
};

var PERMIT_DOCS = [
  { key: "title_deed", label: "صك الملكية الإلكتروني" },
  { key: "survey_report", label: "الرفع المساحي / تقرير المساح" },
  { key: "soil_report", label: "تقرير فحص التربة" },
  { key: "architectural_drawings", label: "المخططات المعمارية" },
  { key: "structural_drawings", label: "المخططات الإنشائية" },
  { key: "mep_drawings", label: "مخططات الكهروميكانيك" },
  { key: "energy_compliance", label: "متطلبات كفاءة الطاقة" },
  { key: "civil_defense_requirements", label: "متطلبات الدفاع المدني" },
  { key: "engineering_office_contract", label: "عقد مكتب هندسي مرخص" },
  { key: "contractor_classification", label: "تصنيف المقاول (إن وجد)" }
];

function $(id) { return document.getElementById(id); }

function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function showError(el, message) {
  el.hidden = false;
  el.innerHTML = '<div class="error">تعذر تنفيذ الطلب: ' + escapeHtml(message) + "</div>";
}

async function postJson(path, payload) {
  var response = await fetch(API_BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  var data = await response.json().catch(function () { return {}; });
  if (!response.ok) {
    var detail = data && data.detail ? JSON.stringify(data.detail) : ("HTTP " + response.status);
    throw new Error(detail);
  }
  return data;
}

async function getJson(path) {
  var response = await fetch(API_BASE + path);
  var data = await response.json().catch(function () { return {}; });
  if (!response.ok) { throw new Error("HTTP " + response.status); }
  return data;
}

function formToObject(form) {
  var payload = {};
  var elements = form.querySelectorAll("input, select");
  elements.forEach(function (el) {
    if (!el.name || el.value === "") { return; }
    payload[el.name] = el.type === "number" ? Number(el.value) : el.value;
  });
  return payload;
}

/* ---------- tabs ---------- */

function initTabs() {
  var tabs = document.querySelectorAll(".tab");
  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("active"); });
      document.querySelectorAll(".panel").forEach(function (p) { p.classList.remove("active"); });
      tab.classList.add("active");
      $(tab.dataset.panel).classList.add("active");
    });
  });
}

/* ---------- assessment ---------- */

function renderAssessment(el, result) {
  var html = '<div class="scorebox">النتيجة الأولية: <b>' + escapeHtml(result.score) +
    "</b>/100 — الحالة: " + escapeHtml(result.overall_status) +
    "<br><small>" + escapeHtml(result.note_ar || "") + "</small></div>";

  html += "<table><tr><th>الفحص</th><th>التصنيف</th><th>الحالة</th><th>التفاصيل</th></tr>";
  (result.findings || []).forEach(function (f) {
    html += "<tr><td>" + escapeHtml(f.title_ar) + "</td><td>" + escapeHtml(f.category) +
      '</td><td class="st-' + escapeHtml(f.status) + '">' +
      escapeHtml(STATUS_LABELS[f.status] || f.status) +
      '</td><td dir="ltr">' + escapeHtml(f.detail) + "</td></tr>";
  });
  html += "</table>";
  el.hidden = false;
  el.innerHTML = html;
}

function initAssess() {
  $("assess-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var out = $("assess-result");
    try {
      var result = await postJson("/v1/assess", formToObject(event.target));
      renderAssessment(out, result);
    } catch (err) {
      showError(out, err.message);
    }
  });
}

/* ---------- permit readiness ---------- */

function initPermit() {
  var form = $("permit-form");
  form.innerHTML = PERMIT_DOCS.map(function (doc) {
    return "<label><input type='checkbox' name='" + doc.key + "'> " + escapeHtml(doc.label) + "</label>";
  }).join("");

  $("permit-run").addEventListener("click", async function () {
    var documents = {};
    form.querySelectorAll("input[type=checkbox]").forEach(function (box) {
      documents[box.name] = box.checked;
    });
    var out = $("permit-result");
    try {
      var result = await postJson("/v1/permit/readiness", { documents: documents });
      var html = '<div class="scorebox">مؤشر الجاهزية: <b>' + escapeHtml(result.readiness_score) +
        "</b>/100 (" + escapeHtml(result.readiness_level) + ")</div>";
      if (result.missing && result.missing.length) {
        html += "<h3>المتطلبات الناقصة</h3><ul class='plain'>" +
          result.missing.map(function (m) { return "<li>" + escapeHtml(m.ar) + "</li>"; }).join("") +
          "</ul>";
      }
      html += "<h3>الخطوات التالية</h3><ul class='plain'>" +
        (result.next_steps || []).map(function (s) { return "<li>" + escapeHtml(s.ar) + "</li>"; }).join("") +
        "</ul>";
      out.hidden = false;
      out.innerHTML = html;
    } catch (err) {
      showError(out, err.message);
    }
  });
}

/* ---------- design assistant ---------- */

function initDesign() {
  $("design-form").addEventListener("submit", async function (event) {
    event.preventDefault();
    var out = $("design-result");
    try {
      var result = await postJson("/v1/design/suggest", formToObject(event.target));
      var html = "";
      var est = result.estimates || {};
      if (est.indicative_footprint_m2) {
        html += '<div class="scorebox">البصمة البنائية الاسترشادية: <b>' +
          escapeHtml(est.indicative_footprint_m2) + '</b> م² — إجمالي المسطحات الاسترشادي: <b>' +
          escapeHtml(est.indicative_gross_floor_area_m2) + "</b> م²</div>";
      }
      html += "<ul class='plain'>" +
        (result.suggestions || []).map(function (s) { return "<li>" + escapeHtml(s.ar) + "</li>"; }).join("") +
        "</ul><p><small>" + escapeHtml(result.note_ar || "") + "</small></p>";
      out.hidden = false;
      out.innerHTML = html;
    } catch (err) {
      showError(out, err.message);
    }
  });
}

/* ---------- regulatory sources ---------- */

async function loadSources() {
  var out = $("sources-result");
  try {
    var data = await getJson("/v1/regulatory-resources");
    var html = "<table><tr><th>المصدر</th><th>الجهة</th><th>الأولوية</th><th>الحالة</th><th>ملزم؟</th></tr>";
    (data.resources || []).forEach(function (res) {
      html += "<tr><td>" + escapeHtml(res.title_ar) + "</td><td>" + escapeHtml(res.issuer) +
        "</td><td>" + escapeHtml(res.priority) + "</td><td>" + escapeHtml(res.status) +
        "</td><td>" + (res.binding ? "نعم" : "لا") + "</td></tr>";
    });
    html += "</table>";
    out.innerHTML = html;
  } catch (err) {
    showError(out, err.message);
  }
}

/* ---------- boot ---------- */

document.addEventListener("DOMContentLoaded", function () {
  initTabs();
  initAssess();
  initPermit();
  initDesign();
  loadSources();
});
