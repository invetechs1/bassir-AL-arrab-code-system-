/* Alarrab CodeVision AI — Arabic RTL frontend + 2D drawing generator.
 * Vanilla JS, no build step. Served by app/api/routes_ui.py at /ui.
 *
 * Two parts:
 *   1. UI shell: tabs, project form, review, permit, assistant, sources.
 *   2. Drawing engine (DRAW.*): generates seven schematic CAD sheets as inline SVG
 *      from the project record. Fully client-side and deterministic.
 *
 * The compliance checks in CHECKS mirror data/rules_seed.json. They are DRAFT
 * values, not official Saudi Building Code requirements. When /v1/assess is
 * reachable and authenticated, prefer the server result — see loadServerAssessment().
 */
"use strict";

var API_BASE = "";

/* ============================ state ============================ */

var S = {
  tab: "project",
  lang: "ar",
  sheet: "site",
  docs: {},
  p: {
    project_name: "فيلا سكنية - حي النرجس",
    city: "الرياض",
    office: "مكتب بصير الهندسي",
    land_use: "residential",
    building_type: "villa",
    plot_w: 20,
    plot_d: 25,
    sb_f: 3,
    sb_s: 2,
    sb_r: 2.5,
    floors: 2,
    floor_h: 3.2,
    units: 1,
    parking: 2
  }
};

var INK = "#14201c", THIN = "#7b8a84", RED = "#b3372f", AMBER = "#a8790f", PASS = "#1e7d4f";
var MONO = "'IBM Plex Mono', monospace", SANS = "'IBM Plex Sans Arabic', sans-serif";

function t(ar, en) { return S.lang === "ar" ? ar : en; }
function num(v) { var x = Number(v); return isFinite(x) ? x : 0; }
function fmt(v, d) { return Number(v).toFixed(d === undefined ? 1 : d); }
function f2(v) { return Math.round(v * 100) / 100; }
function esc(v) {
  return String(v == null ? "" : v)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

/* ============================ geometry ============================ */

function geom() {
  var p = S.p;
  var pw = Math.max(6, num(p.plot_w)), pd = Math.max(6, num(p.plot_d));
  var sbF = Math.max(0, num(p.sb_f)), sbS = Math.max(0, num(p.sb_s)), sbR = Math.max(0, num(p.sb_r));
  var plotArea = pw * pd;
  var bw = Math.max(2, pw - 2 * sbS), bd = Math.max(2, pd - sbF - sbR);
  var floors = Math.max(1, Math.round(num(p.floors)) || 1);
  var fh = Math.max(2.4, num(p.floor_h) || 3.2);
  var footprint = bw * bd;
  return {
    pw: pw, pd: pd, sbF: sbF, sbS: sbS, sbR: sbR, plotArea: plotArea,
    bw: bw, bd: bd, floors: floors, fh: fh, footprint: footprint,
    coverage: footprint / plotArea, gfa: footprint * floors, far: (footprint * floors) / plotArea,
    height: floors * fh + 1.0,
    units: Math.max(1, Math.round(num(p.units)) || 1),
    parking: Math.round(num(p.parking))
  };
}

/* ============================ draft rule checks ============================ */

function checks() {
  var g = geom(), p = S.p, r = [];
  function mk(code, ar, en, cat, sev, status, detail) {
    return { code: code, ar: ar, en: en, cat: cat, sev: sev, status: status, detail: detail };
  }
  r.push(mk("PRELIM-SETBACK-FRONT", "الارتداد الأمامي لا يقل عن ٣٫٠ م", "Front setback ≥ 3.0 m", "setbacks", "high",
    g.sbF >= 3 ? "pass" : "fail", "setback_front_m=" + fmt(g.sbF) + " (draft: >= 3.0 m)"));
  r.push(mk("PRELIM-SETBACK-SIDE", "الارتداد الجانبي لا يقل عن ٢٫٠ م", "Side setback ≥ 2.0 m", "setbacks", "high",
    g.sbS >= 2 ? "pass" : "fail", "setback_side_m=" + fmt(g.sbS) + " (draft: >= 2.0 m)"));
  r.push(mk("PRELIM-SETBACK-REAR", "الارتداد الخلفي لا يقل عن ٢٫٠ م", "Rear setback ≥ 2.0 m", "setbacks", "medium",
    g.sbR >= 2 ? "pass" : "fail", "setback_rear_m=" + fmt(g.sbR) + " (draft: >= 2.0 m)"));
  r.push(mk("PRELIM-COVERAGE-RATIO", "نسبة التغطية لا تتجاوز ٠٫٦٠", "Coverage ratio ≤ 0.60", "massing", "high",
    g.coverage <= 0.6 ? "pass" : "fail", "coverage_ratio=" + fmt(g.coverage, 2) + " (draft: <= 0.60)"));
  r.push(mk("PRELIM-MAX-FLOORS", "عدد الأدوار لا يتجاوز ٤", "Floor count ≤ 4", "massing", "high",
    g.floors <= 4 ? "pass" : "fail", "floors=" + g.floors + " (draft: <= 4)"));
  r.push(mk("PRELIM-HEIGHT-LIMIT", "ارتفاع المبنى لا يتجاوز ١٨٫٠ م", "Building height ≤ 18.0 m", "massing", "medium",
    g.height <= 18 ? "pass" : "fail", "building_height_m=" + fmt(g.height) + " (draft: <= 18.0 m)"));
  r.push(mk("PRELIM-FAR-MAX", "معامل البناء لا يتجاوز ٢٫٠", "Floor area ratio ≤ 2.0", "massing", "medium",
    g.far <= 2 ? "pass" : "fail", "far=" + fmt(g.far, 2) + " (draft: <= 2.0)"));
  r.push(mk("PRELIM-PARKING-MIN", "موقف واحد على الأقل لكل وحدة", "≥ 1 parking space per unit", "parking", "medium",
    g.parking >= g.units ? "pass" : "fail", "parking/units=" + fmt(g.parking / g.units, 2) + " (draft: >= 1.0)"));
  r.push(mk("PRELIM-PLOT-AREA-MIN", "مساحة الأرض لا تقل عن ٢٠٠ م²", "Plot area ≥ 200 m²", "plot", "low",
    g.plotArea >= 200 ? "pass" : "fail", "plot_area_m2=" + fmt(g.plotArea, 0) + " (draft: >= 200)"));
  r.push(mk("PRELIM-LANDUSE-DECLARED", "تحديد استخدام الأرض", "Land use declared", "documentation", "high",
    p.land_use ? "pass" : "needs_review", "land_use='" + (p.land_use || "") + "'"));
  return r;
}

function score() {
  var w = { high: 3, medium: 2, low: 1 }, tot = 0, pass = 0;
  checks().forEach(function (c) {
    if (c.status === "needs_review") { return; }
    tot += w[c.sev];
    if (c.status === "pass") { pass += w[c.sev]; }
  });
  return tot ? Math.round(1000 * pass / tot) / 10 : 0;
}

/* ============================ space programs ============================ */

function A(ar, en, w) { return { ar: ar, en: en, w: w }; }

function program(level) {
  var bt = S.p.building_type;
  if (bt === "villa") {
    return level === "ground"
      ? [A("مجلس رجال", "Majlis", 22), A("مقلط", "Guest lounge", 10), A("صالة معيشة", "Living", 20),
         A("مطبخ", "Kitchen", 11), A("غرفة خادمة", "Maid", 7), A("دورة مياه", "WC", 4),
         A("درج", "Stair", 7), A("مستودع", "Store", 5)]
      : [A("غرفة نوم رئيسية", "Master bedroom", 20), A("حمام رئيسي", "Master bath", 6),
         A("غرفة نوم ٢", "Bedroom 2", 13), A("غرفة نوم ٣", "Bedroom 3", 12),
         A("صالة عائلية", "Family living", 18), A("حمام", "Bath", 5), A("درج", "Stair", 7), A("شرفة", "Balcony", 8)];
  }
  if (bt === "apartment") {
    return level === "ground"
      ? [A("مدخل ولوبي", "Entrance lobby", 20), A("درج ومصعد", "Stair + lift", 14),
         A("غرفة كهرباء", "Electrical", 6), A("غرفة حراسة", "Guard", 7),
         A("مواقف مغطاة", "Covered parking", 40), A("مستودع", "Store", 7)]
      : null;
  }
  if (bt === "commercial") {
    return level === "ground"
      ? [A("معرض تجاري ١", "Retail 1", 26), A("معرض تجاري ٢", "Retail 2", 24),
         A("معرض تجاري ٣", "Retail 3", 20), A("درج ومصعد", "Stair + lift", 10),
         A("دورات مياه", "Toilets", 9), A("مخزن", "Storage", 11)]
      : [A("مساحة مكتبية ١", "Office 1", 30), A("مساحة مكتبية ٢", "Office 2", 26),
         A("قاعة اجتماعات", "Meeting", 12), A("درج ومصعد", "Stair + lift", 10),
         A("دورات مياه", "Toilets", 9), A("مطبخ صغير", "Pantry", 6), A("مخزن", "Storage", 7)];
  }
  if (bt === "mixed") {
    return level === "ground"
      ? [A("معرض تجاري ١", "Retail 1", 28), A("معرض تجاري ٢", "Retail 2", 24),
         A("مدخل سكني", "Residential entry", 14), A("درج ومصعد", "Stair + lift", 12),
         A("دورات مياه", "Toilets", 8), A("مستودع", "Store", 14)]
      : null;
  }
  return level === "ground"
    ? [A("صالة إنتاج", "Production hall", 52), A("مستودع مواد", "Material store", 18),
       A("مكتب إداري", "Office", 12), A("غرفة كهرباء", "Electrical", 6),
       A("دورات مياه", "Toilets", 6), A("مصلى", "Prayer room", 6)]
    : [A("مستودع علوي", "Upper store", 60), A("مكاتب", "Offices", 22),
       A("درج", "Stair", 9), A("دورات مياه", "Toilets", 9)];
}

function unitsPerFloor() {
  var g = geom(), bt = S.p.building_type;
  if (bt === "apartment" || bt === "mixed") {
    return Math.max(1, Math.min(6, Math.ceil(g.units / Math.max(1, g.floors - 1))));
  }
  return 1;
}

function unitProgram(i) {
  var idx = S.lang === "ar" ? "شقة " + (i + 1) : "Apt " + (i + 1);
  return [A("صالة - " + idx, "Living - " + idx, 26), A("مطبخ", "Kitchen", 12),
    A("غرفة نوم ١", "Bedroom 1", 18), A("غرفة نوم ٢", "Bedroom 2", 15),
    A("حمام", "Bath", 7), A("مدخل", "Hall", 8)];
}

/* Slice-and-dice partition: splits a rectangle by target area weights,
 * always cutting across the longer axis so rooms stay roughly proportionate. */
function partition(items, x, y, w, h) {
  if (!items.length) { return []; }
  if (items.length === 1) {
    return [{ ar: items[0].ar, en: items[0].en, x: x, y: y, w: w, h: h }];
  }
  var total = items.reduce(function (s, i) { return s + i.w; }, 0);
  var run = 0, idx = 1, diff = Infinity;
  for (var k = 1; k < items.length; k++) {
    run += items[k - 1].w;
    var d = Math.abs(run - total / 2);
    if (d < diff) { diff = d; idx = k; }
  }
  var a = items.slice(0, idx), b = items.slice(idx);
  var fa = a.reduce(function (s, i) { return s + i.w; }, 0) / total;
  if (w >= h) {
    return partition(a, x, y, w * fa, h).concat(partition(b, x + w * fa, y, w * (1 - fa), h));
  }
  return partition(a, x, y, w, h * fa).concat(partition(b, x, y + h * fa, w, h * (1 - fa)));
}

/* ============================ SVG primitives ============================ */

var DRAW = {};

DRAW.ln = function (x1, y1, x2, y2, sw, dash, color) {
  return '<line x1="' + f2(x1) + '" y1="' + f2(y1) + '" x2="' + f2(x2) + '" y2="' + f2(y2) +
    '" stroke="' + (color || INK) + '" stroke-width="' + (sw || 0.9) + '"' +
    (dash ? ' stroke-dasharray="' + dash + '"' : "") + ' stroke-linecap="square"/>';
};

DRAW.rc = function (x, y, w, h, o) {
  o = o || {};
  return '<rect x="' + f2(x) + '" y="' + f2(y) + '" width="' + f2(Math.max(0, w)) + '" height="' + f2(Math.max(0, h)) +
    '" fill="' + (o.fill || "none") + '" stroke="' + (o.stroke === null ? "none" : (o.stroke || INK)) +
    '" stroke-width="' + (o.sw || 0.9) + '"' + (o.dash ? ' stroke-dasharray="' + o.dash + '"' : "") + "/>";
};

/* Arabic labels: unicode-bidi isolate keeps mixed Arabic/latin runs intact.
 * direction:rtl is only safe with middle/end anchors — with anchor "start" it
 * would anchor the string's right edge at x and run the text backwards. */
DRAW.tx = function (x, y, s, o) {
  o = o || {};
  var anchor = o.anchor || "start";
  // An Arabic label needs an RTL base direction, otherwise a name carrying an
  // embedded latin run ("بورسلين R11 مع عزل مائي") has its words ordered
  // left to right and reads backwards. RTL also flips where text-anchor
  // "start" puts the string, so swap the anchor to keep every call site's
  // x meaning the same edge it meant before.
  if (o.rtl) {
    if (anchor === "start") { anchor = "end"; }
    else if (anchor === "end") { anchor = "start"; }
  }
  return '<text x="' + f2(x) + '" y="' + f2(y) + '" font-size="' + (o.size || 9) +
    '" font-family="' + (o.mono === false ? SANS : MONO) + '" fill="' + (o.fill || INK) +
    '" text-anchor="' + anchor + '" font-weight="' + (o.weight || 400) + '"' +
    (o.rot ? ' transform="rotate(' + o.rot + " " + f2(x) + " " + f2(y) + ')"' : "") +
    (o.ls ? ' letter-spacing="' + o.ls + '"' : "") +
    // Arabic labels resolve their own base direction, so a name carrying an
    // embedded latin run ("بورسلين R11 مع عزل مائي") keeps its word order.
    // Everything else is pinned to LTR so numerals and units never reorder.
    (o.rtl ? ' direction="rtl" style="unicode-bidi:isolate"'
           : ' direction="ltr" style="unicode-bidi:isolate"') + ">" + esc(s) + "</text>";
};

DRAW.dimH = function (x1, x2, y, label, flag) {
  var c = flag ? RED : INK;
  return DRAW.ln(x1, y, x2, y, 0.6, null, c) +
    DRAW.ln(x1, y - 3.5, x1, y + 3.5, 0.8, null, c) +
    DRAW.ln(x2, y - 3.5, x2, y + 3.5, 0.8, null, c) +
    DRAW.tx((x1 + x2) / 2, y - 4, label, { size: 8.5, anchor: "middle", fill: c });
};

DRAW.dimV = function (y1, y2, x, label, flag) {
  var c = flag ? RED : INK;
  return DRAW.ln(x, y1, x, y2, 0.6, null, c) +
    DRAW.ln(x - 3.5, y1, x + 3.5, y1, 0.8, null, c) +
    DRAW.ln(x - 3.5, y2, x + 3.5, y2, 0.8, null, c) +
    DRAW.tx(x - 4, (y1 + y2) / 2, label, { size: 8.5, anchor: "middle", fill: c, rot: -90 });
};

/* ============================ sheet chrome ============================ */

var SHEETS = ["site", "ground", "typical", "interior", "interior2", "finishes", "elevation", "section", "parking", "roof"];

function sheetMeta(key) {
  var M = {
    site: [t("مخطط الموقع العام", "Site Plan"), "A-101"],
    ground: [t("مخطط الدور الأرضي", "Ground Floor Plan"), "A-102"],
    typical: S.p.building_type === "villa"
      ? [t("مخطط الدور الأول", "First Floor Plan"), "A-103"]
      : [t("مخطط الدور المتكرر", "Typical Floor Plan"), "A-103"],
    interior: [t("التصميم الداخلي والفرش — الأرضي", "Interior and Furniture — Ground"), "A-106"],
    interior2: [t("التصميم الداخلي والفرش — الأول", "Interior and Furniture — First"), "A-107"],
    finishes: [t("جدول تشطيبات الغرف", "Room Finishes Schedule"), "A-108"],
    elevation: [t("الواجهة الأمامية", "Front Elevation"), "A-201"],
    section: [t("مقطع رأسي أ-أ", "Section A-A"), "A-301"],
    parking: [t("مخطط المواقف", "Parking Layout"), "A-104"],
    roof: [t("مخطط السطح", "Roof Plan"), "A-105"]
  };
  return M[key] || M.site;
}

function contentSize(key, g) {
  if (key === "elevation" || key === "section") { return { w: g.bw + 8, h: g.height + 6 }; }
  if (key === "finishes") { return { w: 100, h: 70 }; }
  if (key === "ground" || key === "typical" || key === "interior" || key === "interior2") {
    var pd = planPad(g);
    return { w: g.bw + 2 * pd, h: g.bd + 2 * pd };
  }
  if (key === "roof") { return { w: g.bw + 8, h: g.bd + 8 }; }
  return { w: g.pw + 8, h: g.pd + 8 };
}

DRAW.northArrow = function (cx, cy) {
  return '<circle cx="' + cx + '" cy="' + cy + '" r="17" fill="none" stroke="' + THIN + '" stroke-width="0.6"/>' +
    '<path d="M' + cx + " " + (cy - 14) + " L" + (cx + 6) + " " + (cy + 10) + " L" + cx + " " + (cy + 4) +
    " L" + (cx - 6) + " " + (cy + 10) + ' Z" fill="' + INK + '"/>' +
    DRAW.tx(cx, cy + 30, "N", { size: 9, anchor: "middle", weight: 500 });
};

DRAW.scaleBar = function (x, y, den) {
  var out = "", seg = 26;
  for (var i = 0; i < 4; i++) {
    out += DRAW.rc(x + i * seg, y, seg, 6, { fill: i % 2 ? "#fff" : INK, sw: 0.6 });
  }
  return out + DRAW.tx(x, y + 18, "0", { size: 7.5, anchor: "middle" }) +
    DRAW.tx(x + 4 * seg, y + 18, "1:" + den, { size: 7.5, anchor: "middle" }) +
    DRAW.tx(x + 2 * seg, y - 5, t("مقياس الرسم", "SCALE"), { size: 7.5, anchor: "middle", fill: THIN });
};

DRAW.legend = function (key, x, y) {
  var sets = {
    site: [[t("حدود الأرض", "Plot boundary"), "solid"], [t("خط الارتداد", "Setback line"), "dash"], [t("بصمة المبنى", "Building footprint"), "fill"]],
    ground: [[t("جدار خارجي", "External wall"), "thick"], [t("قاطع داخلي", "Partition"), "solid"], [t("فتحة/باب", "Opening"), "dash"]],
    typical: [[t("جدار خارجي", "External wall"), "thick"], [t("قاطع داخلي", "Partition"), "solid"], [t("حد الوحدة", "Unit boundary"), "dash"]],
    interior: [[t("أثاث وتجهيزات", "Furniture and fixtures"), "fill"], [t("رقم الفرش", "Furniture tag"), "solid"], [t("سجادة", "Rug"), "dash"]],
    interior2: [[t("أثاث وتجهيزات", "Furniture and fixtures"), "fill"], [t("رقم الفرش", "Furniture tag"), "solid"], [t("سجادة", "Rug"), "dash"]],
    elevation: [[t("خط الأرض", "Ground line"), "thick"], [t("فتحة نافذة", "Window"), "fill"], [t("خط منسوب", "Level line"), "dash"]],
    section: [[t("بلاطة خرسانية", "Concrete slab"), "fill"], [t("أساسات", "Foundation"), "thick"], [t("منسوب دور", "Floor level"), "dash"]],
    parking: [[t("موقف سيارة", "Parking bay"), "solid"], [t("مسار حركة", "Drive aisle"), "dash"], [t("بصمة المبنى", "Footprint"), "fill"]],
    roof: [[t("سطح", "Roof slab"), "solid"], [t("جدار الحماية", "Parapet"), "thick"], [t("ميل التصريف", "Drainage slope"), "dash"]]
  };
  var items = sets[key] || [];
  if (!items.length) { return ""; }
  var out = DRAW.tx(x, y - 8, t("مفتاح الرسم", "LEGEND"), { size: 8, fill: THIN, ls: "1px" });
  items.forEach(function (it, i) {
    var yy = y + i * 15;
    if (it[1] === "fill") { out += DRAW.rc(x, yy - 5, 20, 7, { fill: "#dfe4e1", sw: 0.6 }); }
    else if (it[1] === "thick") { out += DRAW.ln(x, yy - 2, x + 20, yy - 2, 2.4); }
    else if (it[1] === "dash") { out += DRAW.ln(x, yy - 2, x + 20, yy - 2, 0.8, "4 3"); }
    else { out += DRAW.ln(x, yy - 2, x + 20, yy - 2, 0.9); }
    out += DRAW.tx(x + 26, yy, it[0], { size: 8, mono: false, rtl: true });
  });
  return out;
};

DRAW.titleBlock = function (W, H, TB, meta, den) {
  var y = H - TB - 18, p = S.p;
  var rows = [
    [t("المشروع", "PROJECT"), p.project_name || "—"],
    [t("المدينة", "CITY"), p.city || "—"],
    [t("المكتب الهندسي", "OFFICE"), p.office || "—"],
    [t("التاريخ", "DATE"), new Date().toISOString().slice(0, 10)],
    [t("مقياس", "SCALE"), "1:" + den],
    [t("رقم اللوحة", "SHEET"), meta[1]]
  ];
  var out = DRAW.ln(18, y, W - 18, y, 1.2) +
    DRAW.tx(34, y + 30, meta[0], { size: 15, weight: 600, mono: false, rtl: true }) +
    DRAW.tx(34, y + 48, "Alarrab CodeVision AI · " + t("مخطط استرشادي مولّد آليًا", "AI-generated schematic — not for construction"), { size: 8, fill: THIN }) +
    DRAW.tx(34, y + 64, t("مراجعة أولية غير رسمية — يجب اعتمادها من مهندس مرخص", "Preliminary, unofficial — must be certified by a licensed engineer"), { size: 8, fill: AMBER });
  var colW = 138, startX = W - 30 - colW * 3;
  rows.forEach(function (r, i) {
    var cx = startX + (i % 3) * colW, cy = y + 22 + Math.floor(i / 3) * 34;
    out += DRAW.tx(cx, cy, r[0], { size: 7, fill: THIN, ls: ".6px" });
    var val = String(r[1]);
    // ellipsis on a word boundary rather than a hard cut mid-word
    if (val.length > 30) {
      var cut = val.slice(0, 30), sp = cut.lastIndexOf(" ");
      val = (sp > 16 ? cut.slice(0, sp) : cut) + "…";
    }
    out += DRAW.tx(cx, cy + 13, val, { size: val.length > 24 ? 8.5 : 9.5, mono: false, weight: 500, rtl: true });
  });
  return out + DRAW.ln(startX - 16, y, startX - 16, H - 18, 0.6, null, THIN);
};

DRAW.flags = function (key, W) {
  var rel = {
    site: ["setbacks", "plot", "massing"], ground: ["massing"], typical: ["massing"],
    elevation: ["massing"], section: ["massing"], parking: ["parking"], roof: ["massing"]
  }[key] || [];
  var list = checks().filter(function (c) {
    return c.status === "fail" && rel.indexOf(c.cat) >= 0;
  }).slice(0, 4);
  if (!list.length) { return ""; }
  var x = W - 330, y = 100;
  var out = DRAW.rc(x, y, 296, 22 + list.length * 16, { fill: "#fdf2f1", stroke: RED, sw: 0.7 }) +
    DRAW.tx(x + 10, y + 15, t("تنبيهات مطابقة (مسودة)", "COMPLIANCE FLAGS (draft)"), { size: 8, fill: RED, ls: ".5px" });
  list.forEach(function (c, i) {
    out += DRAW.tx(x + 286, y + 31 + i * 16, t(c.ar, c.en) + " ▲", { size: 8.5, fill: RED, mono: false, anchor: "end", rtl: true });
  });
  return out;
};

/* ============================ sheet assembly ============================ */

/* ==================== architectural plan engine ====================
 * Replaces the earlier area-slicing with a designed villa layout: rooms are
 * placed in three bands, walls carry real thickness, openings are cut out of
 * the walls, doors get swing arcs and rooms are furnished per type.
 * All dimensions are metres in the envelope's own coordinate space (0..W, 0..D)
 * with the street/front edge at y = 0.
 */

var WALL_EXT = 0.20, WALL_INT = 0.10, DOOR_W = 0.90;

/* Room layout as fractions of the buildable envelope. side: n=front, s=rear. */
function villaRooms(level, W, D) {
  var R = [];
  function add(key, ar, en, x0, y0, x1, y1, type, door, win) {
    R.push({ key: key, ar: ar, en: en, x: x0 * W, y: y0 * D,
             w: (x1 - x0) * W, h: (y1 - y0) * D, type: type,
             door: door || null, win: win || [] });
  }

  if (level === "ground") {
    add("majlis", "مجلس", "Majlis", 0, 0, 0.58, 0.34, "majlis",
        { side: "s", at: 0.72 },
        [{ side: "n", at: 0.5, len: 2.0 }, { side: "w", at: 0.5, len: 1.6 }]);
    add("entry", "مدخل", "Entry", 0.58, 0, 1, 0.34, "entry",
        { side: "n", at: 0.5, main: true },
        [{ side: "e", at: 0.5, len: 1.2 }]);
    add("wc", "دورة مياه", "WC", 0, 0.34, 0.26, 0.56, "wc",
        { side: "e", at: 0.5 },
        [{ side: "w", at: 0.5, len: 0.6 }]);
    add("hall", "صالة توزيع ودرج", "Hall and stair", 0.26, 0.34, 1, 0.56, "stair", null, []);
    add("living", "صالة معيشة", "Family living", 0, 0.56, 0.58, 1, "living",
        { side: "n", at: 0.55 },
        [{ side: "w", at: 0.55, len: 1.8 }, { side: "s", at: 0.5, len: 2.0 }]);
    add("kitchen", "مطبخ", "Kitchen", 0.58, 0.56, 1, 1, "kitchen",
        { side: "n", at: 0.5 },
        [{ side: "s", at: 0.5, len: 1.4 }, { side: "e", at: 0.6, len: 1.2 }]);
  } else {
    add("master", "غرفة نوم رئيسية", "Master bedroom", 0, 0, 0.60, 0.38, "bed_master",
        { side: "s", at: 0.75 },
        [{ side: "n", at: 0.5, len: 1.8 }, { side: "w", at: 0.5, len: 1.4 }]);
    add("mbath", "حمام رئيسي", "Master bath", 0.60, 0, 1, 0.38, "bath",
        { side: "s", at: 0.5 },
        [{ side: "e", at: 0.5, len: 0.8 }]);
    add("bath", "حمام", "Bathroom", 0, 0.38, 0.26, 0.56, "wc",
        { side: "e", at: 0.5 },
        [{ side: "w", at: 0.5, len: 0.6 }]);
    add("landing", "بسطة ودرج", "Landing and stair", 0.26, 0.38, 1, 0.56, "stair", null, []);
    add("bed2", "غرفة نوم ٢", "Bedroom 2", 0, 0.56, 0.50, 1, "bed",
        { side: "n", at: 0.6 },
        [{ side: "w", at: 0.55, len: 1.4 }, { side: "s", at: 0.5, len: 1.4 }]);
    add("bed3", "غرفة نوم ٣", "Bedroom 3", 0.50, 0.56, 1, 1, "bed",
        { side: "n", at: 0.4 },
        [{ side: "s", at: 0.5, len: 1.4 }, { side: "e", at: 0.55, len: 1.4 }]);
  }
  return R;
}

/* Absolute coordinates of an opening on a room edge, in metres. */
function edgePoint(r, side, at, len) {
  if (side === "n") { return { x: r.x + r.w * at - len / 2, y: r.y, horiz: true, len: len }; }
  if (side === "s") { return { x: r.x + r.w * at - len / 2, y: r.y + r.h, horiz: true, len: len }; }
  if (side === "w") { return { x: r.x, y: r.y + r.h * at - len / 2, horiz: false, len: len }; }
  return { x: r.x + r.w, y: r.y + r.h * at - len / 2, horiz: false, len: len };
}

/* Door: white gap through the wall, leaf line and quarter-circle swing. */
function drawDoor(r, m, ox, oy) {
  var d = r.door;
  if (!d) { return ""; }
  var X = m.X, Y = m.Y, Sc = m.S;
  var p = edgePoint(r, d.side, d.at, DOOR_W);
  var t = (d.side === "n" || d.side === "s") ? WALL_INT : WALL_INT;
  var out = "";
  if (p.horiz) {
    out += DRAW.rc(X(ox + p.x), Y(oy + p.y) - Sc(t) / 2 - 0.4, Sc(DOOR_W), Sc(t) + 0.8,
      { fill: "#fff", stroke: null });
    var yy = Y(oy + p.y), x0 = X(ox + p.x), x1 = X(ox + p.x + DOOR_W);
    var dir = d.side === "n" ? 1 : -1;
    out += DRAW.ln(x0, yy, x0, yy + dir * Sc(DOOR_W), 0.7);
    out += '<path d="M' + f2(x0) + " " + f2(yy + dir * Sc(DOOR_W)) + " A" + f2(Sc(DOOR_W)) + " " +
      f2(Sc(DOOR_W)) + " 0 0 " + (dir > 0 ? 0 : 1) + " " + f2(x1) + " " + f2(yy) +
      '" fill="none" stroke="' + THIN + '" stroke-width="0.45"/>';
  } else {
    out += DRAW.rc(X(ox + p.x) - Sc(t) / 2 - 0.4, Y(oy + p.y), Sc(t) + 0.8, Sc(DOOR_W),
      { fill: "#fff", stroke: null });
    var xx = X(ox + p.x), y0 = Y(oy + p.y), y1 = Y(oy + p.y + DOOR_W);
    var dx = d.side === "w" ? 1 : -1;
    out += DRAW.ln(xx, y0, xx + dx * Sc(DOOR_W), y0, 0.7);
    out += '<path d="M' + f2(xx + dx * Sc(DOOR_W)) + " " + f2(y0) + " A" + f2(Sc(DOOR_W)) + " " +
      f2(Sc(DOOR_W)) + " 0 0 " + (dx > 0 ? 1 : 0) + " " + f2(xx) + " " + f2(y1) +
      '" fill="none" stroke="' + THIN + '" stroke-width="0.45"/>';
  }
  return out;
}

/* Window: gap in the external wall with two sill lines. */
function drawWindow(r, w, m, ox, oy, W, D) {
  var X = m.X, Y = m.Y, Sc = m.S;
  var p = edgePoint(r, w.side, w.at, w.len);
  // only cut windows in the external envelope
  var onEdge = (w.side === "n" && Math.abs(p.y) < 0.01) || (w.side === "s" && Math.abs(p.y - D) < 0.01) ||
               (w.side === "w" && Math.abs(p.x) < 0.01) || (w.side === "e" && Math.abs(p.x - W) < 0.01);
  if (!onEdge) { return ""; }
  var out = "", t = WALL_EXT;
  if (p.horiz) {
    out += DRAW.rc(X(ox + p.x), Y(oy + p.y) - Sc(t) / 2 - 0.3, Sc(w.len), Sc(t) + 0.6, { fill: "#fff", stroke: null });
    out += DRAW.ln(X(ox + p.x), Y(oy + p.y) - Sc(t) / 3, X(ox + p.x + w.len), Y(oy + p.y) - Sc(t) / 3, 0.5);
    out += DRAW.ln(X(ox + p.x), Y(oy + p.y) + Sc(t) / 3, X(ox + p.x + w.len), Y(oy + p.y) + Sc(t) / 3, 0.5);
  } else {
    out += DRAW.rc(X(ox + p.x) - Sc(t) / 2 - 0.3, Y(oy + p.y), Sc(t) + 0.6, Sc(w.len), { fill: "#fff", stroke: null });
    out += DRAW.ln(X(ox + p.x) - Sc(t) / 3, Y(oy + p.y), X(ox + p.x) - Sc(t) / 3, Y(oy + p.y + w.len), 0.5);
    out += DRAW.ln(X(ox + p.x) + Sc(t) / 3, Y(oy + p.y), X(ox + p.x) + Sc(t) / 3, Y(oy + p.y + w.len), 0.5);
  }
  return out;
}

/* ---------------- furniture catalogue ----------------
 * Each piece is drawn as a recognisable symbol and carries a tag number so
 * the interior sheets can key a schedule to it. FF_USED collects the codes
 * used while a sheet is being built. */
var FF = {
  bench:    ["01", "جلسة مجلس عربي", "Arabic majlis seating"],
  ctable:   ["02", "طاولة وسط", "Coffee table"],
  sofa:     ["03", "كنبة ٣ مقاعد", "Three-seat sofa"],
  armchair: ["04", "كرسي مفرد", "Armchair"],
  tv:       ["05", "وحدة تلفزيون", "TV unit"],
  rug:      ["06", "سجادة", "Rug"],
  dining:   ["07", "طاولة طعام ٤ كراسي", "Dining table, 4 chairs"],
  counter:  ["08", "كاونتر مطبخ", "Kitchen counter"],
  sink:     ["09", "حوض جلي", "Kitchen sink"],
  hob:      ["10", "موقد وشفاط", "Hob and hood"],
  fridge:   ["11", "ثلاجة", "Refrigerator"],
  bed2:     ["12", "سرير مزدوج ١٨٠×٢٠٠", "Double bed 180x200"],
  bed1:     ["13", "سرير مفرد ١٢٠×٢٠٠", "Single bed 120x200"],
  night:    ["14", "كومودينو", "Bedside table"],
  wardrobe: ["15", "دولاب ملابس", "Wardrobe"],
  desk:     ["16", "مكتب دراسة", "Study desk"],
  wc:       ["17", "مرحاض", "WC pan"],
  basin:    ["18", "مغسلة", "Wash basin"],
  shower:   ["19", "دش", "Shower"],
  console:  ["20", "كونسول مدخل", "Entry console"]
};
var FF_USED = [];
function ffUse(k) { if (FF[k] && FF_USED.indexOf(k) < 0) { FF_USED.push(k); } }

var FURN = "#7d8c86", FURN_FILL = "#eef1f0", FURN_SOFT = "#f7f9f8";

function planFurniture(r, m, ox, oy, opts) {
  opts = opts || {};
  var X = m.X, Y = m.Y, Sc = m.S, out = "", pad = 0.12;
  var W = r.w, D = r.h;

  function box(x, y, w, h, o) {
    o = o || {};
    if (w <= 0.04 || h <= 0.04) { return ""; }
    return DRAW.rc(X(ox + r.x + x), Y(oy + r.y + y), Sc(w), Sc(h),
      { sw: o.sw || 0.5, fill: o.fill === null ? "none" : (o.fill || FURN_FILL),
        stroke: o.stroke || FURN, dash: o.dash });
  }
  function ln(x1, y1, x2, y2, sw) {
    return DRAW.ln(X(ox + r.x + x1), Y(oy + r.y + y1), X(ox + r.x + x2), Y(oy + r.y + y2),
      sw || 0.4, null, FURN);
  }
  function circ(cx, cy, rad, fill) {
    return '<circle cx="' + f2(X(ox + r.x + cx)) + '" cy="' + f2(Y(oy + r.y + cy)) + '" r="' +
      f2(Sc(rad)) + '" fill="' + (fill || FURN_SOFT) + '" stroke="' + FURN + '" stroke-width="0.4"/>';
  }
  function ell(cx, cy, rx, ry) {
    return '<ellipse cx="' + f2(X(ox + r.x + cx)) + '" cy="' + f2(Y(oy + r.y + cy)) + '" rx="' +
      f2(Sc(rx)) + '" ry="' + f2(Sc(ry)) + '" fill="' + FURN_SOFT + '" stroke="' + FURN + '" stroke-width="0.4"/>';
  }
  /* numbered tag, interior sheets only */
  function tag(k, cx, cy) {
    ffUse(k);
    if (!opts.tags) { return ""; }
    return '<circle cx="' + f2(X(ox + r.x + cx)) + '" cy="' + f2(Y(oy + r.y + cy)) +
      '" r="5.6" fill="#fff" stroke="#0f6b54" stroke-width="0.7"/>' +
      DRAW.tx(X(ox + r.x + cx), Y(oy + r.y + cy) + 2.6, FF[k][0],
        { size: 5.6, anchor: "middle", fill: "#0f6b54", weight: 600 });
  }

  /* ---- seating: a bench with individual cushions ---- */
  function bench(x, y, w, h, horiz) {
    var s = "", n = Math.max(1, Math.round((horiz ? w : h) / 0.62));
    s += box(x, y, w, h);
    for (var i = 1; i < n; i++) {
      s += horiz ? ln(x + w * i / n, y, x + w * i / n, y + h)
                 : ln(x, y + h * i / n, x + w, y + h * i / n);
    }
    // back cushion strip
    s += horiz ? ln(x, y + h * 0.26, x + w, y + h * 0.26)
               : ln(x + w * 0.26, y, x + w * 0.26, y + h);
    return s;
  }

  if (r.type === "majlis") {
    var sd = Math.min(0.80, W * 0.2, D * 0.2);
    out += bench(pad, pad, W - 2 * pad, sd, true);
    out += bench(pad, pad + sd, sd, D - 2 * pad - sd, false);
    out += bench(W - pad - sd, pad + sd, sd, D - 2 * pad - sd, false);
    out += tag("bench", pad + sd * 0.5, pad + sd * 0.5);
    var rw = Math.max(0.5, W - 2 * (pad + sd) - 0.3), rh = Math.max(0.5, D - 2 * pad - sd - 0.5);
    out += box((W - rw) / 2, pad + sd + 0.25, rw, rh, { fill: null, dash: "3 2", sw: 0.4 });
    out += tag("rug", (W - rw) / 2 + rw * 0.18, pad + sd + 0.25 + rh * 0.82);
    var tw = Math.min(1.1, rw * 0.55), th = Math.min(0.55, rh * 0.32);
    out += box((W - tw) / 2, pad + sd + 0.25 + (rh - th) / 2, tw, th);
    out += tag("ctable", W / 2, pad + sd + 0.25 + rh / 2);

  } else if (r.type === "living") {
    var sofaD = Math.min(0.85, D * 0.2), sofaW = Math.min(2.4, W - 2 * pad - 0.4);
    var sx = (W - sofaW) / 2, sy = D - pad - sofaD;
    out += box(sx, sy, sofaW, sofaD);                       // sofa body
    out += box(sx, sy, sofaW, sofaD * 0.3);                 // back
    out += box(sx, sy + sofaD * 0.3, 0.2, sofaD * 0.7);     // arms
    out += box(sx + sofaW - 0.2, sy + sofaD * 0.3, 0.2, sofaD * 0.7);
    out += ln(sx + sofaW / 3, sy + sofaD * 0.3, sx + sofaW / 3, sy + sofaD);
    out += ln(sx + 2 * sofaW / 3, sy + sofaD * 0.3, sx + 2 * sofaW / 3, sy + sofaD);
    out += tag("sofa", sx + sofaW * 0.5, sy + sofaD * 0.62);
    var tvW = Math.min(1.8, W * 0.5);
    out += box((W - tvW) / 2, pad, tvW, Math.min(0.42, D * 0.1));
    out += ln((W - tvW) / 2 + tvW * 0.2, pad + 0.06, (W + tvW) / 2 - tvW * 0.2, pad + 0.06, 0.8);
    out += tag("tv", W / 2, pad + 0.2);
    var acw = Math.min(0.75, W * 0.18);
    if (W > 3.2) {
      out += box(pad, D * 0.45, acw, acw); out += ln(pad, D * 0.45, pad + acw, D * 0.45);
      out += tag("armchair", pad + acw / 2, D * 0.45 + acw / 2);
    }
    var ctw = Math.min(1.1, W * 0.34), cth = Math.min(0.55, D * 0.13);
    out += box((W - ctw) / 2, sy - cth - 0.35, ctw, cth);
    out += tag("ctable", W / 2, sy - cth - 0.35 + cth / 2);

  } else if (r.type === "kitchen") {
    var c = Math.min(0.62, W * 0.26, D * 0.22);
    out += box(pad, pad, W - 2 * pad, c);                    // main run
    out += box(pad, pad + c, c, D * 0.5);                    // return leg
    out += tag("counter", W * 0.5, pad + c * 0.5);
    out += ell(W * 0.34, pad + c / 2, Math.min(0.24, c * 0.4), Math.min(0.17, c * 0.3));
    out += tag("sink", W * 0.34, pad + c + 0.22);
    var hx = W * 0.62;
    out += box(hx, pad + c * 0.12, c * 0.9, c * 0.76, { fill: FURN_SOFT });
    out += circ(hx + c * 0.24, pad + c * 0.3, c * 0.11) + circ(hx + c * 0.66, pad + c * 0.3, c * 0.11) +
           circ(hx + c * 0.24, pad + c * 0.62, c * 0.11) + circ(hx + c * 0.66, pad + c * 0.62, c * 0.11);
    out += tag("hob", hx + c * 0.45, pad + c + 0.22);
    out += box(pad, pad + c + D * 0.5, c, Math.min(0.7, D * 0.16));
    out += ln(pad + c * 0.75, pad + c + D * 0.5, pad + c * 0.75, pad + c + D * 0.5 + Math.min(0.7, D * 0.16));
    out += tag("fridge", pad + c * 0.45, pad + c + D * 0.5 + 0.3);
    var chair = 0.30, gap = 0.08;
    var dw = Math.min(1.0, W - c - 2 * pad - 0.3), dh = Math.min(0.70, D * 0.18);
    // keep the chair ring inside the room: it must clear the walls on both sides
    var need = dh + 2 * (chair + gap);
    if (dw > 0.55 && dh > 0.38 && need < D - 2 * pad - c) {
      // centre the table in the floor left free by the counter return
      var dx = pad + c + (W - 2 * pad - c - dw) / 2, dy = D - pad - chair - gap - dh;
      out += ell(dx + dw / 2, dy + dh / 2, dw / 2, dh / 2);
      for (var q = 0; q < 4; q++) {
        var ax = dx + dw * (q < 2 ? 0.28 : 0.72);
        var ay = (q % 2) ? dy + dh + gap : dy - gap - chair;
        if (ay >= pad && ay + chair <= D - pad) { out += box(ax - 0.16, ay, 0.32, chair); }
      }
      out += tag("dining", dx + dw / 2, dy + dh / 2);
    }

  } else if (r.type === "bed_master" || r.type === "bed") {
    var isM = r.type === "bed_master";
    var bw = Math.min(isM ? 1.8 : 1.2, W * 0.5), bh = Math.min(2.0, D * 0.48);
    var bx = (W - bw) / 2, by = pad + 0.06;
    out += box(bx, by, bw, bh);                              // mattress
    out += box(bx, by, bw, bh * 0.2, { fill: FURN_SOFT });   // pillow band
    if (isM) {
      out += box(bx + 0.06, by + 0.05, bw / 2 - 0.09, bh * 0.15, { fill: "#fff" });
      out += box(bx + bw / 2 + 0.03, by + 0.05, bw / 2 - 0.09, bh * 0.15, { fill: "#fff" });
    } else {
      out += box(bx + bw * 0.2, by + 0.05, bw * 0.6, bh * 0.15, { fill: "#fff" });
    }
    out += ln(bx, by + bh * 0.42, bx + bw, by + bh * 0.42);  // duvet fold
    out += tag(isM ? "bed2" : "bed1", bx + bw / 2, by + bh * 0.72);
    var nt = Math.min(0.45, (W - bw) / 2 - pad - 0.04);
    if (nt > 0.22) {
      out += box(bx - nt - 0.05, by, nt, nt); out += box(bx + bw + 0.05, by, nt, nt);
      out += tag("night", bx - nt / 2 - 0.05, by + nt / 2);
    }
    var ww = Math.min(2.0, W - 2 * pad), wd = Math.min(0.6, D * 0.15);
    out += box((W - ww) / 2, D - pad - wd, ww, wd);
    out += ln((W - ww) / 2, D - pad - wd * 0.7, (W + ww) / 2, D - pad - wd * 0.7);
    for (var k2 = 1; k2 < 3; k2++) { out += ln((W - ww) / 2 + ww * k2 / 3, D - pad - wd, (W - ww) / 2 + ww * k2 / 3, D - pad); }
    out += tag("wardrobe", W / 2, D - pad - wd / 2);
    if (!isM && W > 2.8) {
      var dk = Math.min(1.0, W * 0.35);
      out += box(pad, D * 0.52, dk, Math.min(0.55, D * 0.13));
      out += tag("desk", pad + dk / 2, D * 0.52 + 0.2);
    }

  } else if (r.type === "bath" || r.type === "wc") {
    var bs = Math.min(0.40, W * 0.26, D * 0.2);
    out += ell(pad + bs * 0.75, pad + bs * 0.5, bs * 0.75, bs * 0.5);   // basin
    out += tag("basin", pad + bs * 0.75, pad + bs * 0.5);
    var ty = pad + bs + 0.28;
    out += box(pad, ty, bs * 0.95, bs * 0.34, { fill: FURN_SOFT });      // cistern
    out += ell(pad + bs * 0.48, ty + bs * 0.34 + bs * 0.42, bs * 0.42, bs * 0.5);
    out += tag("wc", pad + bs * 0.48, ty + bs * 0.75);
    if (r.type === "bath") {
      var sh = Math.min(0.95, W - 2 * pad - bs * 1.6 - 0.1, D * 0.38);
      if (sh > 0.5) {
        var shx = W - pad - sh, shy = D - pad - sh;
        out += box(shx, shy, sh, sh, { fill: FURN_SOFT });
        out += ln(shx, shy, shx + sh, shy + sh); out += ln(shx + sh, shy, shx, shy + sh);
        out += circ(shx + sh / 2, shy + sh / 2, sh * 0.09, "#fff");
        out += tag("shower", shx + sh / 2, shy + sh * 0.2);
      }
    }

  } else if (r.type === "stair") {
    var run = Math.min(D - 2 * pad, 3.4), fl = Math.min(1.1, W * 0.4), steps = 9;
    var sx2 = pad + 0.08, sy2 = (D - run) / 2;
    out += box(sx2, sy2, fl, run, { fill: null });
    for (var i2 = 1; i2 < steps; i2++) { out += ln(sx2, sy2 + run * i2 / steps, sx2 + fl, sy2 + run * i2 / steps); }
    out += ln(sx2 + fl / 2, sy2 + run * 0.88, sx2 + fl / 2, sy2 + run * 0.10, 0.7);
    out += ln(sx2 + fl / 2, sy2 + run * 0.10, sx2 + fl * 0.3, sy2 + run * 0.24, 0.7);
    out += ln(sx2 + fl / 2, sy2 + run * 0.10, sx2 + fl * 0.7, sy2 + run * 0.24, 0.7);

  } else if (r.type === "entry") {
    var cw = Math.min(1.1, W * 0.45);
    out += box((W - cw) / 2, D - pad - 0.36, cw, 0.36);
    out += tag("console", W / 2, D - pad - 0.18);
    var rw2 = Math.min(1.4, W * 0.5), rh2 = Math.min(0.9, D * 0.3);
    out += box((W - rw2) / 2, D * 0.3, rw2, rh2, { fill: null, dash: "3 2", sw: 0.4 });
    out += tag("rug", (W - rw2) / 2 + rw2 * 0.2, D * 0.3 + rh2 * 0.8);
  }
  return out;
}

/* ---------------- finishes (mirrors app/agents/interior.py FINISHES) ----------------
 * [code, floor_ar, floor_en, wall_ar, wall_en, ceiling_ar, ceiling_en] */
var FINISH = {
  majlis: ["F1",
    "رخام أو بورسلين مقاس كبير", "Large-format porcelain or marble",
    "دهان مع كسوة خشبية جزئية", "Paint with partial timber panelling",
    "جبسبورد مع كورنيش وإنارة مخفية", "Gypsum board with cove lighting"],
  entry: ["F1",
    "رخام أو بورسلين مقاس كبير", "Large-format porcelain or marble",
    "دهان مع كسوة خشبية جزئية", "Paint with partial timber panelling",
    "جبسبورد مع كورنيش وإنارة مخفية", "Gypsum board with cove lighting"],
  living: ["F2",
    "بورسلين مصقول", "Polished porcelain",
    "دهان قابل للغسل", "Washable paint",
    "جبسبورد مع إنارة موزعة", "Gypsum board with distributed lighting"],
  bed: ["F3",
    "بورسلين أو باركيه هندسي", "Porcelain or engineered timber",
    "دهان مطفي", "Matt paint",
    "جبسبورد مع إنارة محيطية", "Gypsum board with perimeter lighting"],
  bed_master: ["F3",
    "بورسلين أو باركيه هندسي", "Porcelain or engineered timber",
    "دهان مطفي", "Matt paint",
    "جبسبورد مع إنارة محيطية", "Gypsum board with perimeter lighting"],
  kitchen: ["F4",
    "بورسلين مقاوم للانزلاق R10", "Anti-slip porcelain R10",
    "سيراميك حتى السقف خلف مناطق العمل", "Full-height ceramic behind work zones",
    "جبسبورد مقاوم للرطوبة", "Moisture-resistant gypsum board"],
  bath: ["F5",
    "بورسلين مقاوم للانزلاق R11 مع عزل مائي", "Anti-slip porcelain R11 over tanking",
    "سيراميك حتى السقف مع عزل مائي", "Full-height ceramic over tanking",
    "جبسبورد مقاوم للرطوبة مع فتحة خدمة", "Moisture-resistant gypsum with access hatch"],
  wc: ["F5",
    "بورسلين مقاوم للانزلاق R11 مع عزل مائي", "Anti-slip porcelain R11 over tanking",
    "سيراميك حتى السقف مع عزل مائي", "Full-height ceramic over tanking",
    "جبسبورد مقاوم للرطوبة مع فتحة خدمة", "Moisture-resistant gypsum with access hatch"],
  stair: ["F6",
    "بورسلين مقاوم للتآكل", "Hard-wearing porcelain",
    "دهان قابل للغسل مع حماية زوايا", "Washable paint with corner guards",
    "جبسبورد مع إنارة خطية", "Gypsum board with linear lighting"]
};

/* Slab depth from the span, mirroring app/agents/structural.py so the section
 * and the structural report describe the same building. */
/* Margin around a floor plan, in metres. A fixed margin left a small villa
 * floating in white space on an A3 sheet. */
function planPad(g) { return Math.max(1.4, 0.13 * Math.max(g.bw, g.bd)); }

function slabThickness(g) {
  var bw = Math.max(1, g.bw), bd = Math.max(1, g.bd);
  var nw = Math.max(1, Math.ceil(bw / 6)), nd = Math.max(1, Math.ceil(bd / 6));
  var span = Math.max(bw / nw, bd / nd);
  var ratio = span <= 5 ? 28 : (span <= 7.5 ? 33 : (span <= 9.5 ? 36 : 42));
  return Math.max(0.15, Math.ceil(span * 1000 / ratio / 10) * 10 / 1000);
}

/* ---------------- the plan renderer ---------------- */
function drawPlan(m, level, opts) {
  opts = opts || {};
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, ox = planPad(g), oy = planPad(g);
  var W = g.bw, D = g.bd, out = "";
  var rooms = villaRooms(level, W, D);

  // slab / floor field
  out += DRAW.rc(X(ox), Y(oy), Sc(W), Sc(D), { fill: "#fff", sw: 0 });

  // internal partitions: stroking each room draws shared walls at full thickness
  rooms.forEach(function (r) {
    out += DRAW.rc(X(ox + r.x), Y(oy + r.y), Sc(r.w), Sc(r.h),
      { sw: Math.max(1.1, Sc(WALL_INT)), fill: "none" });
  });
  // external envelope
  out += DRAW.rc(X(ox), Y(oy), Sc(W), Sc(D), { sw: Math.max(2, Sc(WALL_EXT)), fill: "none" });

  // openings cut through the walls
  rooms.forEach(function (r) {
    r.win.forEach(function (w) { out += drawWindow(r, w, m, ox, oy, W, D); });
  });
  rooms.forEach(function (r) { out += drawDoor(r, m, ox, oy); });

  // furniture
  rooms.forEach(function (r) { out += planFurniture(r, m, ox, oy, opts); });

  // labels
  rooms.forEach(function (r) {
    var cx = X(ox + r.x + r.w / 2), cy = Y(oy + r.y + r.h / 2);
    var area = r.w * r.h;
    var fits = Sc(r.w) > 42 && Sc(r.h) > 26;
    if (!fits) {
      out += DRAW.tx(cx, cy, t(r.ar, r.en).slice(0, 9),
        { size: 6.5, anchor: "middle", mono: false, rtl: true, fill: THIN });
      return;
    }
    var lift = r.type === "stair" ? Sc(r.h) * 0.34 : 0;
    var fs = Math.min(10, Math.max(7.5, Sc(r.w) / 10));
    var name = t(r.ar, r.en);
    var extra = (opts.finishes && FINISH[r.type]) ? 11 : 0;
    // white halo keeps the label legible where it lands on furniture
    var hw = Math.max(46, name.length * fs * 0.52), hh = 20 + extra;
    out += DRAW.rc(cx - hw / 2, cy - 13 - lift, hw, hh, { fill: "#fff", stroke: null });
    out += DRAW.tx(cx, cy - 3 - lift, name,
      { size: fs, anchor: "middle", mono: false, weight: 500, rtl: true });
    out += DRAW.tx(cx, cy + 7 - lift, fmt(area, 1) + " m²",
      { size: 7.2, anchor: "middle", fill: THIN });
    if (extra) {
      out += DRAW.tx(cx, cy + 17 - lift, FINISH[r.type][0],
        { size: 7, anchor: "middle", fill: "#0f6b54", weight: 600 });
    }
  });

  // dimension chains from the room grid
  var xs = [0], ys = [0];
  rooms.forEach(function (r) {
    [r.x, r.x + r.w].forEach(function (v) { if (!xs.some(function (a) { return Math.abs(a - v) < 0.05; })) { xs.push(v); } });
    [r.y, r.y + r.h].forEach(function (v) { if (!ys.some(function (a) { return Math.abs(a - v) < 0.05; })) { ys.push(v); } });
  });
  xs.sort(function (a, b) { return a - b; });
  ys.sort(function (a, b) { return a - b; });
  for (var i = 0; i < xs.length - 1; i++) {
    if (xs[i + 1] - xs[i] < 0.4) { continue; }
    out += DRAW.dimH(X(ox + xs[i]), X(ox + xs[i + 1]), Y(oy) - 15, fmt(xs[i + 1] - xs[i], 2));
  }
  for (var j = 0; j < ys.length - 1; j++) {
    if (ys[j + 1] - ys[j] < 0.4) { continue; }
    out += DRAW.dimV(Y(oy + ys[j]), Y(oy + ys[j + 1]), X(ox + W) + 17, fmt(ys[j + 1] - ys[j], 2));
  }
  out += DRAW.dimH(X(ox), X(ox + W), Y(oy) - 34, fmt(W, 2) + " m");
  out += DRAW.dimV(Y(oy), Y(oy + D), X(ox + W) + 36, fmt(D, 2) + " m");
  return out;
}

function buildSheet(key) {
  var W = 1160, H = 800, TB = 92, pad = 44, top = 40, bot = H - TB - 56;
  var g = geom(), meta = sheetMeta(key), spec = contentSize(key, g);
  var areaW = W - pad * 2 - 130, areaH = bot - top;
  var s = Math.min(areaW / spec.w, areaH / spec.h);
  var ox = pad + 40 + (areaW - spec.w * s) / 2, oy = top + (areaH - spec.h * s) / 2;
  var m = {
    g: g, s: s, W: W, H: H,
    X: function (v) { return ox + v * s; },
    Y: function (v) { return oy + v * s; },
    S: function (v) { return v * s; }
  };
  var den = Math.max(20, Math.round((spec.w * 1000) / (spec.w * s * 0.362) / 50) * 50);
  var body = ({
    site: bodySite, ground: function (mm) { return bodyPlan(mm, "ground"); },
    typical: function (mm) { return bodyPlan(mm, "typical"); },
    interior: function (mm) { return bodyInterior(mm, "ground"); },
    interior2: function (mm) { return bodyInterior(mm, "first"); },
    finishes: bodyFinishes,
    elevation: bodyElevation, section: bodySection, parking: bodyParking, roof: bodyRoof
  }[key] || bodySite)(m);

  return '<svg viewBox="0 0 ' + W + " " + H + '" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="' + esc(meta[0]) + '">' +
    DRAW.rc(10, 10, W - 20, H - 20, { sw: 1.4 }) +
    DRAW.rc(18, 18, W - 36, H - 36, { sw: 0.6, stroke: THIN }) +
    (key === "finishes" ? "" : DRAW.northArrow(W - 96, 54)) +
    body +
    DRAW.legend(key, 34, H - TB - 150) +
    (key === "finishes" ? "" : DRAW.scaleBar(W - 300, H - TB - 34, den)) +
    DRAW.titleBlock(W, H, TB, meta, den) +
    DRAW.flags(key, W) +
    "</svg>";
}

/* ---------- A-101 site plan ---------- */
function bodySite(m) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, px = 4, py = 4;
  var bx = px + g.sbS, by = py + g.sbF, out = "";
  out += DRAW.rc(X(px), Y(py), Sc(g.pw), Sc(g.pd), { sw: 1.8 });
  out += DRAW.rc(X(bx), Y(by), Sc(g.bw), Sc(g.bd), { sw: 0.7, dash: "5 4", stroke: THIN });
  out += DRAW.rc(X(bx), Y(by), Sc(g.bw), Sc(g.bd), { sw: 1.4, fill: "#e7ebe9" });
  out += DRAW.tx(X(bx + g.bw / 2), Y(by + g.bd / 2) - 4, t("بصمة المبنى", "BUILDING FOOTPRINT"), { size: 9, anchor: "middle", weight: 500, rtl: true });
  out += DRAW.tx(X(bx + g.bw / 2), Y(by + g.bd / 2) + 10, fmt(g.footprint, 1) + " m²  ·  " + g.floors + t(" أدوار", " floors"), { size: 8.5, anchor: "middle", fill: THIN, rtl: true });
  out += DRAW.dimV(Y(py), Y(by), X(px) - 14, fmt(g.sbF) + " m", g.sbF < 3);
  out += DRAW.dimV(Y(by + g.bd), Y(py + g.pd), X(px) - 14, fmt(g.sbR) + " m", g.sbR < 2);
  out += DRAW.dimH(X(px), X(bx), Y(py + g.pd) + 16, fmt(g.sbS) + " m", g.sbS < 2);
  out += DRAW.dimH(X(px), X(px + g.pw), Y(py) - 22, fmt(g.pw) + " m");
  out += DRAW.dimV(Y(py), Y(py + g.pd), X(px + g.pw) + 30, fmt(g.pd) + " m");
  out += DRAW.ln(X(px) - 4, Y(py) - 8, X(px + g.pw) + 4, Y(py) - 8, 1.2, "10 5", THIN);
  out += DRAW.tx(X(px + g.pw / 2), Y(py) - 34, t("الشارع", "STREET"), { size: 8, anchor: "middle", fill: THIN, ls: "1px", rtl: true });
  out += DRAW.tx(X(px), Y(py + g.pd) + 38, t("مساحة الأرض", "PLOT AREA") + " " + fmt(g.plotArea, 0) + " m²   ·   " +
    t("نسبة التغطية", "COVERAGE") + " " + fmt(g.coverage, 2) + "   ·   FAR " + fmt(g.far, 2), { size: 8.5 });
  return out;
}

/* ---------- A-102 / A-103 floor plans ---------- */
function bodyPlan(m, level) {
  /* Villas get the designed layout with walls, openings and furniture; the
   * other building types still use the area slicer. */
  if (S.p.building_type === "villa") {
    var lv = level === "ground" ? "ground" : "first";
    return drawPlan(m, lv, { finishes: level === "interior" }) +
      DRAW.tx(m.X(planPad(m.g)), m.Y(planPad(m.g) + m.g.bd) + 42,
        (level === "ground" ? t("الدور الأرضي", "GROUND FLOOR") : t("الدور الأول", "FIRST FLOOR")) +
        "   ·   " + fmt(m.g.footprint, 1) + " m² " + t("مسطح الدور", "floor area"),
        { size: 8.5, rtl: true });
  }
  return bodyPlanGeneric(m, level);
}

function bodyPlanGeneric(m, level) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, ox = 4, oy = 4, wallT = 0.25, out = "";
  out += DRAW.rc(X(ox), Y(oy), Sc(g.bw), Sc(g.bd), { sw: 2.2 });
  out += DRAW.rc(X(ox + wallT), Y(oy + wallT), Sc(g.bw - 2 * wallT), Sc(g.bd - 2 * wallT), { sw: 0.7 });
  var ix = ox + wallT, iy = oy + wallT, iw = g.bw - 2 * wallT, ih = g.bd - 2 * wallT;
  var bt = S.p.building_type;
  var multiUnit = (bt === "apartment" || bt === "mixed") && level === "typical";
  var rooms = [];
  if (multiUnit) {
    var nu = unitsPerFloor(), horiz = iw >= ih;
    for (var u = 0; u < nu; u++) {
      var uw = horiz ? iw / nu : iw, uh = horiz ? ih : ih / nu;
      var ux = horiz ? ix + u * uw : ix, uy = horiz ? iy : iy + u * uh;
      rooms = rooms.concat(partition(unitProgram(u), ux, uy, uw, uh));
      if (u > 0) {
        out += horiz ? DRAW.ln(X(ux), Y(uy), X(ux), Y(uy + uh), 2)
                     : DRAW.ln(X(ux), Y(uy), X(ux + uw), Y(uy), 2);
      }
    }
  } else {
    rooms = partition(program(level), ix, iy, iw, ih);
  }
  rooms.forEach(function (r) {
    out += DRAW.rc(X(r.x), Y(r.y), Sc(r.w), Sc(r.h), { sw: 0.9 });
    var cw = Sc(r.w), ch = Sc(r.h), cx = X(r.x + r.w / 2), cy = Y(r.y + r.h / 2);
    var name = t(r.ar, r.en);
    if (cw > 46 && ch > 26) {
      out += DRAW.tx(cx, cy - 1, name, { size: Math.min(9.5, Math.max(7, cw / 9)), anchor: "middle", mono: false, weight: 500, rtl: true });
      out += DRAW.tx(cx, cy + 11, fmt(r.w * r.h, 1) + " m²", { size: 7.5, anchor: "middle", fill: THIN });
    } else if (cw > 24 && ch > 14) {
      out += DRAW.tx(cx, cy + 3, name.slice(0, 7), { size: 7, anchor: "middle", mono: false, rtl: true });
    }
    if (cw > 40) { out += DRAW.ln(X(r.x + r.w / 2 - 0.45), Y(r.y), X(r.x + r.w / 2 + 0.45), Y(r.y), 1.6, null, "#fff"); }
  });
  if (level === "ground") {
    out += DRAW.ln(X(ox + g.bw / 2 - 0.75), Y(oy + g.bd), X(ox + g.bw / 2 + 0.75), Y(oy + g.bd), 2.6, null, "#fff");
    out += DRAW.tx(X(ox + g.bw / 2), Y(oy + g.bd) + 26, t("المدخل الرئيسي", "MAIN ENTRANCE"), { size: 8, anchor: "middle", fill: THIN, rtl: true });
  }
  out += DRAW.dimH(X(ox), X(ox + g.bw), Y(oy) - 22, fmt(g.bw) + " m");
  out += DRAW.dimV(Y(oy), Y(oy + g.bd), X(ox + g.bw) + 26, fmt(g.bd) + " m");
  var label = level === "ground" ? t("الدور الأرضي", "GROUND FLOOR")
    : (multiUnit ? t("الدور المتكرر · " + unitsPerFloor() + " شقق/دور", "TYPICAL FLOOR · " + unitsPerFloor() + " units/floor")
                 : t("الدور المتكرر", "TYPICAL FLOOR"));
  out += DRAW.tx(X(ox), Y(oy + g.bd) + 40, label + "   ·   " + fmt(g.footprint, 1) + " m² " + t("مسطح الدور", "floor area"), { size: 8.5, rtl: true });
  return out;
}

/* ---------- A-106 / A-107 interior design and furniture layout ---------- */
function bodyInterior(m, level) {
  var g = m.g, out = "";
  if (S.p.building_type !== "villa") {
    return bodyPlanGeneric(m, "ground") +
      DRAW.tx(m.X(planPad(g)), m.Y(planPad(g) + g.bd) + 42,
        t("مخطط التصميم الداخلي متاح لنمط الفيلا في هذه النسخة.",
          "The interior layout is available for the villa type in this release."),
        { size: 8.5, rtl: true });
  }
  FF_USED = [];
  out += drawPlan(m, level, { finishes: true, tags: true });

  // furniture schedule keyed to the tag numbers on the plan
  var x = m.W - 312, y = 120, rowH = 15.5;
  out += DRAW.rc(x - 12, y - 24, 302, 34 + FF_USED.length * rowH,
    { fill: "#fbfaf8", sw: 0.6, stroke: THIN });
  out += DRAW.tx(x, y - 10, t("جدول الفرش", "FURNITURE SCHEDULE"), { size: 8, fill: THIN, ls: "1px" });
  FF_USED.forEach(function (k, i) {
    var yy = y + 8 + i * rowH, f = FF[k];
    out += '<circle cx="' + f2(x + 7) + '" cy="' + f2(yy - 3) + '" r="6" fill="#fff" stroke="#0f6b54" stroke-width="0.7"/>';
    out += DRAW.tx(x + 7, yy, f[0], { size: 6, anchor: "middle", fill: "#0f6b54", weight: 600 });
    out += DRAW.tx(x + 24, yy, t(f[1], f[2]), { size: 7.6, mono: false, rtl: true });
  });

  var lvAr = level === "ground" ? "الدور الأرضي" : "الدور الأول";
  var lvEn = level === "ground" ? "GROUND FLOOR" : "FIRST FLOOR";
  out += DRAW.tx(m.X(planPad(g)), m.Y(planPad(g) + g.bd) + 42,
    t("التصميم الداخلي والفرش · " + lvAr, "INTERIOR DESIGN AND FURNITURE · " + lvEn) +
    "   ·   " + t("الأثاث استرشادي غير مقيد", "furniture indicative, not binding"),
    { size: 8.5, rtl: true });
  return out;
}

/* ---------- A-108 room finishes schedule ---------- */
function bodyFinishes(m) {
  var g = m.g, out = "", W = m.W;
  if (S.p.building_type !== "villa") {
    return DRAW.tx(W / 2, 300, t("جدول التشطيبات متاح لنمط الفيلا في هذه النسخة.",
      "The finishes schedule is available for the villa type in this release."),
      { size: 11, anchor: "middle", mono: false, rtl: true });
  }
  var rows = [];
  [["ground", "الدور الأرضي", "Ground floor"], ["first", "الدور الأول", "First floor"]].forEach(function (lv) {
    rows.push({ head: true, ar: lv[1], en: lv[2] });
    villaRooms(lv[0], g.bw, g.bd).forEach(function (r) {
      var f = FINISH[r.type];
      if (f) { rows.push({ room: r, f: f }); }
    });
  });

  var x0 = 52, x1 = W - 52, y = 74, rowH = 25.5;
  var cols = [x0 + 8, x0 + 152, x0 + 205, x0 + 455, x0 + 715];
  out += DRAW.tx(x0, y - 22, t("جدول تشطيبات الغرف", "ROOM FINISHES SCHEDULE"),
    { size: 10, fill: INK, weight: 600, ls: "1px" });
  out += DRAW.tx(x0 + 210, y - 22, t("مستخرج من مخرجات وكيل التصميم الداخلي",
    "derived from the interior design agent"), { size: 7.6, fill: THIN, mono: false, rtl: true });

  // header
  out += DRAW.rc(x0, y - 14, x1 - x0, 22, { fill: "#f2f0ec", sw: 0.6, stroke: THIN });
  [[cols[0], t("الفراغ", "SPACE")], [cols[1], t("الرمز", "CODE")], [cols[2], t("الأرضيات", "FLOOR")],
   [cols[3], t("الجدران", "WALLS")], [cols[4], t("الأسقف", "CEILING")]].forEach(function (c) {
    out += DRAW.tx(c[0], y + 1, c[1], { size: 7.4, fill: THIN, ls: ".6px" });
  });
  y += 14;

  rows.forEach(function (r) {
    if (r.head) {
      out += DRAW.rc(x0, y, x1 - x0, 19, { fill: "#eef2f0", sw: 0.5, stroke: THIN });
      out += DRAW.tx(cols[0], y + 13, t(r.ar, r.en), { size: 8, mono: false, weight: 600, rtl: true, fill: "#0f6b54" });
      y += 19;
      return;
    }
    out += DRAW.rc(x0, y, x1 - x0, rowH, { fill: "none", sw: 0.4, stroke: "#e2e0da" });
    out += DRAW.tx(cols[0], y + 16, t(r.room.ar, r.room.en), { size: 8, mono: false, weight: 500, rtl: true });
    out += DRAW.tx(cols[1], y + 16, r.f[0], { size: 7.6, fill: "#0f6b54", weight: 600 });
    out += DRAW.tx(cols[2], y + 16, t(r.f[1], r.f[2]), { size: 7.4, mono: false, rtl: true });
    out += DRAW.tx(cols[3], y + 16, t(r.f[3], r.f[4]), { size: 7.4, mono: false, rtl: true });
    out += DRAW.tx(cols[4], y + 16, t(r.f[5], r.f[6]), { size: 7.4, mono: false, rtl: true });
    y += rowH;
  });

  out += DRAW.tx(x0, y + 24, t(
    "التشطيبات مقترحات نوعية وليست مواصفات فنية أو أسماء تجارية — تُعتمد من المصمم قبل التنفيذ.",
    "Finishes are generic proposals, not technical specifications or brand selections — the designer signs them off before construction."),
    { size: 7.8, mono: false, rtl: true, fill: THIN });
  return out;
}

/* ---------- A-201 front elevation ---------- */
function bodyElevation(m) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, ox = 4, base = 4 + g.height, top = base - g.height, out = "";
  out += DRAW.rc(X(ox), Y(top), Sc(g.bw), Sc(g.height), { sw: 1.6 });
  out += DRAW.ln(X(ox) - 30, Y(base), X(ox + g.bw) + 30, Y(base), 2.4);
  for (var i = 0; i < 14; i++) {
    var gx = X(ox) - 26 + i * (Sc(g.bw) + 52) / 14;
    out += DRAW.ln(gx, Y(base), gx - 7, Y(base) + 8, 0.6, null, THIN);
  }
  var nWin = Math.max(2, Math.min(6, Math.round(g.bw / 3.6)));
  for (var fl = 0; fl < g.floors; fl++) {
    var fy = base - (fl + 1) * g.fh;
    out += DRAW.ln(X(ox), Y(fy), X(ox + g.bw), Y(fy), 0.7, "5 4", THIN);
    out += DRAW.tx(X(ox + g.bw) + 8, Y(fy) + 3, "+" + fmt(fl === 0 ? 0 : fl * g.fh, 2), { size: 7.5, fill: THIN });
    for (var w = 0; w < nWin; w++) {
      var step = g.bw / nWin, wx = ox + w * step + step / 2 - 0.7;
      if (fl === 0 && w === Math.floor(nWin / 2)) {
        out += DRAW.rc(X(wx - 0.35), Y(base - 2.4), Sc(2.1), Sc(2.4), { sw: 1.1, fill: "#e7ebe9" });
      } else {
        out += DRAW.rc(X(wx), Y(fy + g.fh - 2.4), Sc(1.4), Sc(1.5), { sw: 1, fill: "#dfe4e1" });
        out += DRAW.ln(X(wx + 0.7), Y(fy + g.fh - 2.4), X(wx + 0.7), Y(fy + g.fh - 0.9), 0.6);
      }
    }
  }
  out += DRAW.ln(X(ox) - 2, Y(top + 1), X(ox + g.bw) + 2, Y(top + 1), 1.1, null, THIN);
  out += DRAW.dimV(Y(top), Y(base), X(ox) - 22, fmt(g.height) + " m", g.height > 18);
  out += DRAW.dimH(X(ox), X(ox + g.bw), Y(top) - 20, fmt(g.bw) + " m");
  out += DRAW.tx(X(ox), Y(base) + 34, t("الواجهة الأمامية", "FRONT ELEVATION") + "   ·   " + g.floors + t(" أدوار × ", " floors × ") + fmt(g.fh, 2) + " m", { size: 8.5, rtl: true });
  return out;
}

/* ---------- A-301 section A-A ---------- */
function bodySection(m) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, ox = 4, base = 4 + g.height, top = base - g.height, slab = slabThickness(g), out = "";
  out += DRAW.rc(X(ox - 0.5), Y(base), Sc(g.bw + 1), Sc(1.2), { sw: 1.8, fill: "#d9ded9" });
  out += DRAW.ln(X(ox) - 30, Y(base), X(ox + g.bw) + 30, Y(base), 1.2, "8 4", THIN);
  for (var fl = 0; fl < g.floors; fl++) {
    var fBot = base - fl * g.fh, fTop = fBot - g.fh;
    out += DRAW.rc(X(ox), Y(fBot - slab), Sc(g.bw), Sc(slab), { sw: 0.8, fill: "#c9d0cb" });
    out += DRAW.ln(X(ox), Y(fBot), X(ox), Y(fTop), 1.8);
    out += DRAW.ln(X(ox + g.bw), Y(fBot), X(ox + g.bw), Y(fTop), 1.8);
    out += DRAW.tx(X(ox + g.bw / 2), Y(fBot - g.fh / 2), t("دور " + (fl + 1), "Level " + (fl + 1)), { size: 9, anchor: "middle", mono: false, fill: THIN, rtl: true });
    out += DRAW.dimV(Y(fTop), Y(fBot - slab), X(ox) - 20, fmt(g.fh - slab, 2));
    for (var k = 0; k < 6; k++) {
      var sx = ox + 0.6 + k * 0.42, sy = fBot - (k + 1) * (g.fh / 6);
      out += DRAW.ln(X(sx), Y(sy + g.fh / 6), X(sx), Y(sy), 0.6, null, THIN);
      out += DRAW.ln(X(sx), Y(sy), X(sx + 0.42), Y(sy), 0.6, null, THIN);
    }
  }
  out += DRAW.rc(X(ox), Y(top - slab), Sc(g.bw), Sc(slab), { sw: 0.9, fill: "#c9d0cb" });
  out += DRAW.rc(X(ox), Y(top - slab - 0.9), Sc(0.25), Sc(0.9), { sw: 0.9, fill: "#dfe4e1" });
  out += DRAW.rc(X(ox + g.bw - 0.25), Y(top - slab - 0.9), Sc(0.25), Sc(0.9), { sw: 0.9, fill: "#dfe4e1" });
  out += DRAW.dimV(Y(top - slab - 0.9), Y(base), X(ox + g.bw) + 26, fmt(g.height) + " m", g.height > 18);
  out += DRAW.tx(X(ox), Y(base) + 40, t("مقطع رأسي أ-أ", "SECTION A-A") + "   ·   " + t("سماكة البلاطة", "slab") + " " + fmt(slab, 2) + " m   ·   " + t("منسوب التأسيس", "footing") + " -1.20 m", { size: 8.5, rtl: true });
  return out;
}

/* ---------- A-104 parking layout ----------
 * Bays are 2.50 × 5.00 m. A yard strip deep enough (>= 5.0 m) takes 90° bays;
 * shallower strips (>= 2.5 m) take parallel bays, so realistic Saudi setbacks
 * (3 m front / 2 m side) still produce a drawn layout. */
function bodyParking(m) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, px = 4, py = 4;
  var bx = px + g.sbS, by = py + g.sbF, bayW = 2.5, bayD = 5.0, out = "";
  out += DRAW.rc(X(px), Y(py), Sc(g.pw), Sc(g.pd), { sw: 1.8 });
  out += DRAW.rc(X(bx), Y(by), Sc(g.bw), Sc(g.bd), { sw: 1.2, fill: "#eef1ef" });
  out += DRAW.tx(X(bx + g.bw / 2), Y(by + g.bd / 2), t("المبنى", "BUILDING"), { size: 9, anchor: "middle", fill: THIN, ls: "1px", rtl: true });

  var want = Math.max(0, g.parking), placed = 0, parallelUsed = false;
  var strips = [
    { x: px, y: py + 0.15, len: g.pw, depth: g.sbF, axis: "h", grow: 1 },
    { x: px + 0.15, y: py + g.sbF, len: g.pd - g.sbF - g.sbR, depth: g.sbS, axis: "v", grow: 1 },
    { x: px + g.pw - 0.15, y: py + g.sbF, len: g.pd - g.sbF - g.sbR, depth: g.sbS, axis: "v", grow: -1 },
    { x: px, y: py + g.pd - 0.15, len: g.pw, depth: g.sbR, axis: "h", grow: -1 }
  ];
  strips.forEach(function (sp) {
    if (placed >= want || sp.depth < bayW - 0.05 || sp.len < bayW) { return; }
    var perp = sp.depth >= bayD - 0.05;
    var along = perp ? bayW : bayD, deep = perp ? bayD : bayW;
    if (!perp) { parallelUsed = true; }
    var cap = Math.floor(sp.len / along);
    for (var i = 0; i < cap && placed < want; i++, placed++) {
      var bx0, by0, bw0, bh0;
      if (sp.axis === "h") {
        bw0 = along; bh0 = deep;
        bx0 = sp.x + i * along;
        by0 = sp.grow > 0 ? sp.y : sp.y - deep;
      } else {
        bw0 = deep; bh0 = along;
        by0 = sp.y + i * along;
        bx0 = sp.grow > 0 ? sp.x : sp.x - deep;
      }
      out += DRAW.rc(X(bx0), Y(by0), Sc(bw0), Sc(bh0), { sw: 0.8, fill: "#f6f7f6" });
      out += DRAW.tx(X(bx0 + bw0 / 2), Y(by0 + bh0 / 2) + 3, String(placed + 1),
        { size: Math.min(7.5, Math.max(5.5, Sc(bw0) / 4)), anchor: "middle", fill: THIN });
    }
  });

  out += DRAW.ln(X(px), Y(py + g.sbF - 0.3), X(px + g.pw), Y(py + g.sbF - 0.3), 0.8, "7 5", THIN);
  out += DRAW.tx(X(px + g.pw / 2), Y(py + g.sbF - 0.9), t("مسار الحركة", "DRIVE AISLE"), { size: 7.5, anchor: "middle", fill: THIN, rtl: true });
  out += DRAW.tx(X(px), Y(py + g.pd) + 30,
    t("المواقف المطلوبة", "REQUIRED") + " " + g.units + "   ·   " + t("المدخلة", "ENTERED") + " " + want + "   ·   " +
    t("المرسومة داخل الأرض", "PLOTTED ON SITE") + " " + placed + "   ·   " + t("مقاس الموقف", "BAY") + " 2.50 × 5.00 m" +
    (parallelUsed ? "   ·   " + t("مواقف موازية حيث لا يسمح عمق الارتداد", "parallel bays where setback depth is limited") : ""),
    { size: 8.5, rtl: true });
  if (want - placed > 0) {
    out += DRAW.tx(X(px), Y(py + g.pd) + 46,
      "▲ " + t((want - placed) + " موقفًا لا يمكن استيعابها داخل الارتدادات الحالية", (want - placed) + " bay(s) cannot fit within the current setbacks"),
      { size: 8.5, fill: RED, mono: false, rtl: true });
  }
  return out;
}

/* ---------- A-105 roof plan ---------- */
function bodyRoof(m) {
  var g = m.g, X = m.X, Y = m.Y, Sc = m.S, ox = 4, oy = 4, pt = 0.25, out = "";
  out += DRAW.rc(X(ox), Y(oy), Sc(g.bw), Sc(g.bd), { sw: 2.2 });
  out += DRAW.rc(X(ox + pt), Y(oy + pt), Sc(g.bw - 2 * pt), Sc(g.bd - 2 * pt), { sw: 0.8 });
  var sw2 = Math.min(3.2, g.bw * 0.3), sd = Math.min(4, g.bd * 0.3);
  out += DRAW.rc(X(ox + 1), Y(oy + 1), Sc(sw2), Sc(sd), { sw: 1.1, fill: "#eef1ef" });
  out += DRAW.tx(X(ox + 1 + sw2 / 2), Y(oy + 1 + sd / 2), t("مخرج الدرج", "STAIR"), { size: 8, anchor: "middle", mono: false, rtl: true });
  for (var i = 0; i < 2; i++) {
    var tx0 = ox + g.bw - 3.2, ty0 = oy + 1 + i * 2.4;
    out += DRAW.rc(X(tx0), Y(ty0), Sc(2.2), Sc(1.8), { sw: 1, fill: "#e7ebe9" });
    out += DRAW.tx(X(tx0 + 1.1), Y(ty0 + 1.05), t("خزان", "TANK"), { size: 7, anchor: "middle", rtl: true });
  }
  var acN = Math.max(2, Math.min(8, g.floors * 2));
  for (var a = 0; a < acN; a++) {
    var axp = ox + 1.4 + (a % 4) * 2.2, ayp = oy + g.bd - 2.6 - Math.floor(a / 4) * 1.9;
    out += DRAW.rc(X(axp), Y(ayp), Sc(1.4), Sc(1.1), { sw: 0.7, fill: "#f2f4f3" });
  }
  out += DRAW.tx(X(ox + 1.4), Y(oy + g.bd - 3.0), t("وحدات تكييف", "A/C UNITS"), { size: 7.5, fill: THIN, rtl: true });
  for (var k = 0; k < 2; k++) {
    var yy = oy + g.bd * (k ? 0.72 : 0.34);
    out += DRAW.ln(X(ox + g.bw * 0.25), Y(yy), X(ox + g.bw * 0.75), Y(yy), 0.7, "6 4", THIN);
    out += DRAW.tx(X(ox + g.bw * 0.5), Y(yy) - 4, t("ميل ١٪", "SLOPE 1%"), { size: 7.5, anchor: "middle", fill: THIN, rtl: true });
    out += '<circle cx="' + f2(X(ox + g.bw * 0.78)) + '" cy="' + f2(Y(yy)) + '" r="4" fill="none" stroke="' + INK + '" stroke-width="0.8"/>';
  }
  out += DRAW.dimH(X(ox), X(ox + g.bw), Y(oy) - 22, fmt(g.bw) + " m");
  out += DRAW.dimV(Y(oy), Y(oy + g.bd), X(ox + g.bw) + 26, fmt(g.bd) + " m");
  out += DRAW.tx(X(ox), Y(oy + g.bd) + 36, t("مخطط السطح", "ROOF PLAN") + "   ·   " + t("جدار حماية", "parapet") + " 0.90 m   ·   " + fmt(g.footprint, 1) + " m²", { size: 8.5, rtl: true });
  return out;
}

/* ============================ reference data ============================ */

var PERMIT_DOCS = [
  ["title_deed", "صك الملكية الإلكتروني", "Electronic title deed"],
  ["survey_report", "الرفع المساحي / تقرير المساح", "Survey report"],
  ["soil_report", "تقرير فحص التربة", "Soil investigation report"],
  ["architectural_drawings", "المخططات المعمارية", "Architectural drawings"],
  ["structural_drawings", "المخططات الإنشائية", "Structural drawings"],
  ["mep_drawings", "مخططات الكهروميكانيك", "MEP drawings"],
  ["energy_compliance", "متطلبات كفاءة الطاقة", "Energy efficiency compliance"],
  ["civil_defense_requirements", "متطلبات الدفاع المدني", "Civil Defense requirements"],
  ["engineering_office_contract", "عقد مكتب هندسي مرخص", "Licensed engineering office contract"],
  ["contractor_classification", "تصنيف المقاول (إن وجد)", "Contractor classification (if applicable)"]
];

var SOURCES = [
  ["كود البناء السعودي — الإصدارات الرسمية", "Saudi Building Code — official editions", "اللجنة الوطنية لكود البناء السعودي", "P0", true],
  ["اشتراطات البناء البلدية (بلدي)", "Municipal building requirements (Balady)", "وزارة الشؤون البلدية والقروية والإسكان", "P0", true],
  ["متطلبات السلامة والوقاية", "Fire and life safety requirements", "المديرية العامة للدفاع المدني", "P0", true],
  ["مخططات التنظيم والاستخدام", "Zoning and land-use plans", "الأمانات والبلديات", "P0", true],
  ["كود ترشيد الطاقة للمباني", "Building energy conservation code", "اللجنة الوطنية لكود البناء السعودي", "P1", true],
  ["متطلبات توصيل الخدمات الكهربائية", "Electrical connection requirements", "الشركة السعودية للكهرباء", "P1", true],
  ["متطلبات المياه والصرف الصحي", "Water and sewage requirements", "المؤسسة العامة للمياه", "P1", true],
  ["أدلة إرشادية ومسودات تحت التشاور", "Guidance notes and drafts under consultation", "جهات متعددة", "P2", false]
];

/* ============================ panels ============================ */

function fieldGroups() {
  var p = S.p;
  function n(name, label) { return { name: name, label: label, kind: "number", value: p[name] }; }
  function x(name, label) { return { name: name, label: label, kind: "text", value: p[name] }; }
  function sel(name, label, opts) { return { name: name, label: label, kind: "select", value: p[name], options: opts }; }
  return [
    { title: t("هوية المشروع", "PROJECT IDENTITY"), fields: [
      x("project_name", t("اسم المشروع", "Project name")),
      x("city", t("المدينة", "City")),
      x("office", t("المكتب الهندسي", "Engineering office")),
      sel("land_use", t("استخدام الأرض", "Land use"), [
        ["residential", t("سكني", "Residential")], ["commercial", t("تجاري", "Commercial")],
        ["mixed", t("مختلط", "Mixed use")], ["industrial", t("صناعي", "Industrial")]]),
      sel("building_type", t("نوع المبنى", "Building type"), [
        ["villa", t("فيلا / مسكن خاص", "Villa / single family")],
        ["apartment", t("عمارة سكنية", "Apartment building")],
        ["commercial", t("تجاري / معارض", "Commercial / retail")],
        ["mixed", t("مختلط", "Mixed use")],
        ["industrial", t("صناعي / مستودع", "Industrial / warehouse")]])
    ] },
    { title: t("الأرض والارتدادات", "PLOT & SETBACKS"), fields: [
      n("plot_w", t("عرض الأرض (م)", "Plot width (m)")),
      n("plot_d", t("عمق الأرض (م)", "Plot depth (m)")),
      n("sb_f", t("الارتداد الأمامي (م)", "Front setback (m)")),
      n("sb_s", t("الارتداد الجانبي (م)", "Side setback (m)")),
      n("sb_r", t("الارتداد الخلفي (م)", "Rear setback (m)"))
    ] },
    { title: t("المبنى", "BUILDING"), fields: [
      n("floors", t("عدد الأدوار", "Floors")),
      n("floor_h", t("ارتفاع الدور (م)", "Floor height (m)")),
      n("units", t("عدد الوحدات", "Units")),
      n("parking", t("عدد المواقف", "Parking spaces"))
    ] }
  ];
}

function panelProject() {
  var g = geom();
  var html = '<div class="rowhead"><h2 class="section">' + t("بيانات المشروع", "Project Data") + "</h2>" +
    '<span class="derived" dir="ltr">' + fmt(g.plotArea, 0) + " m² · " + fmt(g.bw, 1) + "×" + fmt(g.bd, 1) +
    " m · " + g.floors + "F · FAR " + fmt(g.far, 2) + "</span></div>" +
    '<p class="hint">' + t("أدخل بيانات المبنى مرة واحدة. تُستخدم نفس البيانات لتوليد المخططات ثنائية الأبعاد، ولحساب المراجعة الأولية، ولمؤشر جاهزية الرخصة.",
      "Enter the building data once. The same record drives the 2D drawing generation, the preliminary code review, and the permit readiness index.") + "</p>" +
    '<div class="card">';
  fieldGroups().forEach(function (grp) {
    html += '<div class="fieldgroup"><div class="grouptitle">' + esc(grp.title) + '</div><div class="grid">';
    grp.fields.forEach(function (f) {
      html += "<label><span>" + esc(f.label) + "</span>";
      if (f.kind === "select") {
        html += '<select data-field="' + f.name + '">' + f.options.map(function (o) {
          return '<option value="' + esc(o[0]) + '"' + (String(f.value) === o[0] ? " selected" : "") + ">" + esc(o[1]) + "</option>";
        }).join("") + "</select>";
      } else {
        html += '<input data-field="' + f.name + '" type="' + f.kind + '"' +
          (f.kind === "number" ? ' step="any" min="0"' : "") + ' value="' + esc(f.value) + '">';
      }
      html += "</label>";
    });
    html += "</div></div>";
  });
  html += '<div class="formactions">' +
    '<button class="primary" data-go="drawings" type="button">' + t("توليد المخططات ثنائية الأبعاد", "Generate 2D drawings") + "</button>" +
    '<button class="secondary" data-go="review" type="button">' + t("تشغيل المراجعة الأولية", "Run preliminary review") + "</button>" +
    '<span class="actionhint">' + t("سبع لوحات: الموقع، الأرضي، المتكرر، الواجهة، المقطع، المواقف، السطح.",
      "Seven sheets: site, ground, typical, elevation, section, parking, roof.") + "</span></div></div>";
  return html;
}

function panelDrawings() {
  var g = geom(), failing = checks().filter(function (c) { return c.status === "fail"; });
  var html = '<div class="rowhead noprint"><h2 class="section">' + t("المخططات المولّدة", "Generated Drawings") + "</h2>" +
    '<button class="dark" id="print-sheet" type="button">' + t("طباعة / تصدير PDF", "Print / export PDF") + "</button></div>" +
    '<div class="sheettabs noprint">' + SHEETS.map(function (k) {
      return '<button class="sheettab' + (S.sheet === k ? " active" : "") + '" data-sheet="' + k + '" type="button">' + esc(sheetMeta(k)[0]) + "</button>";
    }).join("") + "</div>" +
    '<div class="sheetwrap">' + buildSheet(S.sheet) + "</div>" +
    '<div class="notes noprint">' +
      '<div class="note">' + t("مقاسات اللوحة مشتقة مباشرة من بيانات المشروع: بصمة " + fmt(g.footprint, 1) + " م² داخل أرض " + fmt(g.plotArea, 0) + " م².",
        "Sheet geometry is derived directly from the project record: a " + fmt(g.footprint, 1) + " m² footprint inside a " + fmt(g.plotArea, 0) + " m² plot.") + "</div>" +
      '<div class="note ' + (failing.length ? "fail" : "") + '">' + (failing.length
        ? t(failing.length + " تنبيه مطابقة (مسودة) معروض على اللوحات ذات الصلة.", failing.length + " draft compliance flag(s) are annotated on the relevant sheets.")
        : t("لا توجد تنبيهات مطابقة على قواعد المسودة الحالية.", "No compliance flags against the current draft rules.")) + "</div>" +
      '<div class="note warn">' + t("المخططات تخطيطية استرشادية: توزيع الفراغات آلي ويحتاج مراجعة معماري مرخص قبل أي استخدام.",
        "Drawings are indicative schematics: the space planning is automatic and needs licensed architect review before any use.") + "</div>" +
    "</div>";
  return html;
}

function panelReview() {
  var cs = checks(), counts = { pass: 0, fail: 0, needs_review: 0 };
  cs.forEach(function (c) { counts[c.status]++; });
  var sc = score();
  var labels = { pass: t("مستوفى مبدئيًا", "Preliminary pass"), fail: t("غير مستوفى", "Not met"), needs_review: t("يحتاج مراجعة", "Needs review") };
  var cards = [
    [t("النتيجة الأولية / ١٠٠", "Preliminary score / 100"), fmt(sc, 1), sc >= 80 ? PASS : sc >= 50 ? AMBER : RED],
    [t("مستوفى", "Passing"), counts.pass, PASS],
    [t("غير مستوفى", "Failing"), counts.fail, counts.fail ? RED : "#6b7a74"],
    [t("يحتاج مراجعة", "Needs review"), counts.needs_review, AMBER]
  ];
  return '<h2 class="section">' + t("المراجعة الأولية للمطابقة", "Preliminary Compliance Review") + "</h2>" +
    '<p class="hint">' + t("تُقاس معاملات المشروع مقابل قواعد تحقق مسودة (غير رسمية) مطابقة لمجموعة القواعد في النظام. القيم النهائية تؤخذ من الوثائق الرسمية فقط.",
      "Project parameters are measured against DRAFT (unofficial) verification rules mirroring the system rule set. Final values come from official documents only.") + "</p>" +
    '<div class="cards">' + cards.map(function (c) {
      return '<div class="metric"><div class="k">' + esc(c[0]) + '</div><div class="v" style="color:' + c[2] + '">' + esc(c[1]) + "</div></div>";
    }).join("") + "</div>" +
    '<div class="tablewrap"><table><thead><tr>' +
      "<th>" + t("الفحص", "Check") + "</th><th>" + t("التصنيف", "Category") + "</th>" +
      "<th>" + t("الحالة", "Status") + "</th><th>" + t("التفاصيل", "Detail") + "</th>" +
    "</tr></thead><tbody>" + cs.map(function (c) {
      return "<tr><td>" + esc(t(c.ar, c.en)) + '</td><td class="mono">' + esc(c.cat) + "</td>" +
        '<td class="st-' + c.status + '">' + esc(labels[c.status]) + "</td>" +
        '<td class="detail" dir="ltr">' + esc(c.detail) + "</td></tr>";
    }).join("") + "</tbody></table></div>" +
    '<p class="footnote">' + t("القيم المستخدمة في الفحص قيم مسودة للاختبار فقط، ولم يتم اعتمادها مقابل بنود الكود الرسمية.",
      "The values used in these checks are draft test values, not verified against official code clauses.") + "</p>";
}

function panelPermit() {
  var have = PERMIT_DOCS.filter(function (d) { return S.docs[d[0]]; }).length;
  var pct = Math.round(100 * have / PERMIT_DOCS.length);
  var missing = PERMIT_DOCS.filter(function (d) { return !S.docs[d[0]]; });
  return '<h2 class="section">' + t("مؤشر جاهزية رخصة البناء", "Building Permit Readiness") + "</h2>" +
    '<p class="hint">' + t("حدد المستندات المتوفرة للحصول على مؤشر جاهزية استرشادي وقائمة النواقص.",
      "Select the documents you have to get an indicative readiness index and a list of gaps.") + "</p>" +
    '<div class="permitgrid"><div class="card">' + PERMIT_DOCS.map(function (d) {
      return '<label class="checkrow"><input type="checkbox" data-doc="' + d[0] + '"' + (S.docs[d[0]] ? " checked" : "") +
        "><span>" + esc(t(d[1], d[2])) + "</span></label>";
    }).join("") + "</div>" +
    '<div class="scorepanel"><div class="k">' + t("مؤشر الجاهزية / ١٠٠", "Readiness index / 100") + "</div>" +
    '<div class="v">' + pct + '</div><div class="bar"><i style="width:' + pct + '%"></i></div>' +
    "<h4>" + t("المتطلبات الناقصة", "Missing requirements") + "</h4><ul>" +
    (missing.length ? missing.map(function (d) { return "<li>" + esc(t(d[1], d[2])) + "</li>"; }).join("")
                    : "<li>" + t("لا توجد نواقص", "No gaps") + "</li>") +
    "</ul></div></div>";
}

function panelAssistant() {
  var g = geom(), sug = [];
  function push(ar, en) { sug.push(t(ar, en)); }
  push("البصمة القابلة للبناء " + fmt(g.bw, 1) + " × " + fmt(g.bd, 1) + " م بعد تطبيق الارتدادات المدخلة.",
    "Buildable footprint is " + fmt(g.bw, 1) + " × " + fmt(g.bd, 1) + " m after applying the entered setbacks.");
  push("إجمالي المسطحات الاسترشادي " + fmt(g.gfa, 0) + " م² على " + g.floors + " أدوار، بمعامل بناء " + fmt(g.far, 2) + ".",
    "Indicative gross floor area is " + fmt(g.gfa, 0) + " m² over " + g.floors + " floors, at a floor area ratio of " + fmt(g.far, 2) + ".");
  if (g.coverage > 0.6) {
    push("نسبة التغطية " + fmt(g.coverage, 2) + " أعلى من حد المسودة ٠٫٦٠ — يمكن تقليصها بزيادة الارتداد الجانبي أو الخلفي.",
      "Coverage of " + fmt(g.coverage, 2) + " exceeds the 0.60 draft limit — increasing the side or rear setback would reduce it.");
  } else {
    push("نسبة التغطية " + fmt(g.coverage, 2) + " ضمن حد المسودة ٠٫٦٠.", "Coverage of " + fmt(g.coverage, 2) + " sits within the 0.60 draft limit.");
  }
  if (g.parking < g.units) {
    push("المواقف المدخلة أقل من عدد الوحدات — راجع اشتراطات المواقف للاستخدام المحدد لدى الأمانة.",
      "Entered parking is below the unit count — check the municipality's parking requirement for this land use.");
  }
  push("سعة المواقف داخل الارتداد الأمامي تقارب " + (g.sbF >= 5 ? Math.floor(g.pw / 2.5) : Math.floor(g.pw / 5)) + " موقفًا بمقاس ٢٫٥٠ × ٥٫٠٠ م.",
    "The front setback strip fits roughly " + (g.sbF >= 5 ? Math.floor(g.pw / 2.5) : Math.floor(g.pw / 5)) + " bays at 2.50 × 5.00 m.");
  push("ارتفاع المبنى الاسترشادي " + fmt(g.height, 1) + " م مع جدار حماية ١٫٠٠ م.",
    "Indicative building height is " + fmt(g.height, 1) + " m including a 1.00 m parapet.");

  var est = [
    [t("البصمة البنائية", "Footprint"), fmt(g.footprint, 1) + " m²"],
    [t("إجمالي المسطحات", "Gross floor area"), fmt(g.gfa, 0) + " m²"],
    [t("نسبة التغطية", "Coverage ratio"), fmt(g.coverage, 2)],
    [t("معامل البناء FAR", "Floor area ratio"), fmt(g.far, 2)]
  ];
  return '<h2 class="section">' + t("مساعد التصميم الاسترشادي", "Advisory Design Assistant") + "</h2>" +
    '<p class="hint">' + t("تقديرات وتوصيات مشتقة من هندسة الأرض والمعاملات المدخلة.",
      "Estimates and recommendations derived from the plot geometry and the entered parameters.") + "</p>" +
    '<div class="cards">' + est.map(function (e) {
      return '<div class="metric"><div class="k">' + esc(e[0]) + '</div><div class="v">' + esc(e[1]) + "</div></div>";
    }).join("") + "</div>" +
    '<div class="card">' + sug.map(function (s, i) {
      return '<div class="suggest"><span class="n">' + String(i + 1).padStart(2, "0") + "</span><span>" + esc(s) + "</span></div>";
    }).join("") + "</div>";
}

function panelSources() {
  return '<h2 class="section">' + t("المصادر التنظيمية", "Regulatory Sources") + "</h2>" +
    '<p class="hint">' + t("المصادر التي يتتبعها النظام. لا يتحول أي مصدر إلى قاعدة تحقق تلقائيًا — تتطلب مراجعة مهني مرخص.",
      "Sources tracked by the system. No source becomes a verification rule automatically — licensed professional review is required.") + "</p>" +
    '<div class="tablewrap"><table><thead><tr><th>' + t("المصدر", "Source") + "</th><th>" + t("الجهة", "Issuer") +
    "</th><th>" + t("الأولوية", "Priority") + "</th><th>" + t("ملزم", "Binding") + "</th></tr></thead><tbody>" +
    SOURCES.map(function (r) {
      return "<tr><td>" + esc(t(r[0], r[1])) + "</td><td>" + esc(r[2]) + '</td><td class="mono">' + esc(r[3]) +
        '</td><td class="' + (r[4] ? "st-pass" : "") + '">' + (r[4] ? t("نعم", "Yes") : t("لا", "No")) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
}

/* ==================== Design by Alarrab (seven senior agents) ==================== */

/* The seven agents live on the server in app/agents/. The browser posts the
 * project record to /v1/design/alarrab and renders the package it gets back,
 * so the engineering logic has exactly one home. In demo mode the endpoint
 * answers unauthenticated; where AUTH_REQUIRED is on it returns 401/403 and
 * the panel asks for a token. */

var D = { status: "idle", data: null, error: "", token: "", sig: "" };

/* Signature of the inputs the agents actually read, so a package rendered
 * from stale project values can say so instead of looking current. */
function projSig() {
  var g = geom(), p = S.p;
  return [p.project_name, p.city, p.office, p.land_use, p.building_type,
    g.pw, g.pd, g.sbF, g.sbS, g.sbR, g.floors, g.fh, g.units, g.parking].join("|");
}

var SEV_LABEL = {
  high: ["حرج", "Critical"],
  medium: ["متوسط", "Medium"],
  low: ["منخفض", "Low"]
};

function sevClass(sev) {
  return sev === "high" ? "st-fail" : (sev === "medium" ? "st-needs_review" : "st-pass");
}

function runAlarrab() {
  var box = document.getElementById("alarrab-token");
  if (box && box.value.trim()) { D.token = box.value.trim(); }

  D.status = "running";
  D.error = "";
  render();

  var headers = { "Content-Type": "application/json" };
  if (D.token) { headers.Authorization = "Bearer " + D.token; }

  var g = geom(), p = S.p, sig = projSig();
  fetch(API_BASE + "/v1/design/alarrab", {
    method: "POST",
    headers: headers,
    body: JSON.stringify({
      project_name: p.project_name, city: p.city, office: p.office,
      land_use: p.land_use, building_type: p.building_type,
      plot_w: g.pw, plot_d: g.pd, sb_f: g.sbF, sb_s: g.sbS, sb_r: g.sbR,
      floors: g.floors, floor_h: g.fh, units: g.units, parking: g.parking
    })
  }).then(function (res) {
    if (res.status === 401 || res.status === 403) {
      D.status = "auth";
      D.error = t("يتطلب هذا الإجراء صلاحية design:use. أدخل رمز وصول صالحًا.",
        "This action requires the design:use permission. Enter a valid access token.");
      render();
      return null;
    }
    if (!res.ok) { throw new Error("HTTP " + res.status); }
    return res.json();
  }).then(function (data) {
    if (!data) { return; }
    D.data = data;
    D.sig = sig;
    D.status = "done";
    render();
  }).catch(function (err) {
    D.status = "error";
    D.error = t("تعذّر تشغيل الوكلاء: ", "Could not run the agents: ") + err.message;
    render();
  });
}

function alarrabMetrics(metrics) {
  return '<div class="tablewrap"><table><thead><tr><th>' + t("البند", "Item") + "</th><th>" +
    t("القيمة", "Value") + "</th><th>" + t("الأساس", "Basis") + "</th></tr></thead><tbody>" +
    metrics.map(function (m) {
      var unit = m.unit ? " " + m.unit : "";
      return "<tr><td>" + esc(t(m.key_ar, m.key_en)) + '</td><td class="mono">' +
        esc(m.value) + esc(unit) + '</td><td class="detail">' + esc(m.basis) + "</td></tr>";
    }).join("") + "</tbody></table></div>";
}

function alarrabList(title, items, cls) {
  if (!items || !items.length) { return ""; }
  return "<details class=\"agentfold\"><summary>" + esc(title) + " (" + items.length + ")</summary><ul class=\"" +
    (cls || "") + "\">" + items.map(function (i) {
      var extra = i.source ? ' <span class="src">— ' + esc(i.source) + "</span>" : "";
      return "<li>" + esc(t(i.ar, i.en)) + extra + "</li>";
    }).join("") + "</ul></details>";
}

function alarrabSchedule(agent) {
  var rows = agent.schedule || [];
  if (!rows.length) { return ""; }
  var head, body;

  if (agent.agent_id === "architecture") {
    head = [t("الفراغ", "Space"), t("المساحة", "Area"), t("لكل دور", "Per floor")];
    body = rows.map(function (r) {
      return "<tr><td>" + esc(t(r.ar, r.en)) + '</td><td class="mono">' + esc(r.area_m2) +
        ' m²</td><td class="mono">' + esc(r.per_floor_m2) + " m²</td></tr>";
    });
  } else if (agent.agent_id === "interior") {
    head = [t("الفراغ", "Space"), t("الأرضيات", "Floor"), t("الجدران", "Walls"), t("الأسقف", "Ceiling")];
    body = rows.map(function (r) {
      return "<tr><td>" + esc(t(r.ar, r.en)) + "</td><td>" + esc(t(r.floor_ar, r.floor_en)) +
        "</td><td>" + esc(t(r.wall_ar, r.wall_en)) + "</td><td>" + esc(t(r.ceiling_ar, r.ceiling_en)) + "</td></tr>";
    });
  } else if (agent.agent_id === "quantity") {
    head = [t("العنصر", "Element"), t("الكمية", "Quantity"), t("السعر", "Rate"), t("التكلفة", "Cost")];
    body = rows.map(function (r) {
      return "<tr><td>" + esc(t(r.ar, r.en)) + '</td><td class="mono">' + esc(r.quantity) +
        '</td><td class="mono">' + esc(r.rate_low) + "-" + esc(r.rate_high) +
        '</td><td class="mono">' + Number(r.cost_low).toLocaleString("en") + "-" +
        Number(r.cost_high).toLocaleString("en") + "</td></tr>";
    });
  } else if (agent.agent_id === "electrical") {
    head = [t("الفراغ", "Space"), t("شدة الإضاءة", "Illuminance")];
    body = rows.map(function (r) {
      return "<tr><td>" + esc(t(r.ar, r.en)) + '</td><td class="mono">' + esc(r.lux) + " lux</td></tr>";
    });
  } else if (agent.agent_id === "regulation") {
    head = [t("التخصص", "Discipline"), t("المرجع", "Code part"), t("الجهة", "Authority")];
    body = rows.map(function (r) {
      return "<tr><td>" + esc(t(r.discipline_ar, r.discipline_en)) + '</td><td class="mono">' +
        esc(r.code_part) + "</td><td>" + esc(t(r.authority_ar, r.authority_en)) + "</td></tr>";
    });
  } else {
    return "";
  }

  return "<details class=\"agentfold\"><summary>" + t("الجدول التفصيلي", "Detailed schedule") +
    " (" + rows.length + ")</summary><div class=\"tablewrap\"><table><thead><tr><th>" +
    head.join("</th><th>") + "</th></tr></thead><tbody>" + body.join("") + "</tbody></table></div></details>";
}

function alarrabCashflow(agent) {
  var rows = agent.cashflow || [];
  if (!rows.length) { return ""; }
  return "<details class=\"agentfold\"><summary>" + t("التدفق النقدي", "Cashflow") +
    " (" + rows.length + ")</summary><div class=\"tablewrap\"><table><thead><tr><th>" +
    [t("الفترة", "Period"), t("الأشهر", "Months"), t("الحصة", "Share"), t("من", "From"), t("إلى", "To")].join("</th><th>") +
    "</th></tr></thead><tbody>" + rows.map(function (r) {
      return "<tr><td>" + esc(t(r.period_ar, r.period_en)) + '</td><td class="mono">' + esc(r.months) +
        '</td><td class="mono">' + Math.round(r.share * 100) + '%</td><td class="mono">' +
        Number(r.low).toLocaleString("en") + '</td><td class="mono">' +
        Number(r.high).toLocaleString("en") + "</td></tr>";
    }).join("") + "</tbody></table></div></details>";
}

function alarrabAgent(agent, index) {
  var recs = agent.recommendations || [];
  return '<section class="agentcard">' +
    '<header class="agenthead"><span class="agentno">' + String(index + 1).padStart(2, "0") + "</span>" +
    "<div><h3>" + esc(t(agent.name_ar, agent.name_en)) + "</h3>" +
    '<p class="agentrole">' + esc(t(agent.role_ar, agent.role_en)) + "</p></div></header>" +
    '<p class="agentsum">' + esc(t(agent.summary_ar, agent.summary_en)) + "</p>" +
    alarrabMetrics(agent.metrics || []) +
    (recs.length ? '<div class="agentrecs">' + recs.map(function (r) {
      return '<div class="suggest"><span class="n ' + sevClass(r.priority) + '">' +
        esc(t(SEV_LABEL[r.priority][0], SEV_LABEL[r.priority][1])) + "</span><span>" +
        esc(t(r.ar, r.en)) + "</span></div>";
    }).join("") + "</div>" : "") +
    alarrabSchedule(agent) +
    alarrabCashflow(agent) +
    alarrabList(t("الافتراضات", "Assumptions"), agent.assumptions) +
    alarrabList(t("يحتاج تحقق", "Needs verification"), agent.verify) +
    "</section>";
}

function panelAlarrab() {
  var head = '<div class="rowhead"><h2 class="section">' + t("التصميم بواسطة العرّاب", "Design by Alarrab") +
    "</h2></div>" +
    '<p class="hint">' + t(
      "سبعة وكلاء بخبرة مهندس أول يعملون على بيانات المشروع بالتتابع: معماري، إنشائي، ميكانيكي، كهربائي، تصميم داخلي، مساحة كميات، ومراجعة نظامية. ثم يُفحص تعارض المخرجات بين التخصصات.",
      "Seven senior-level agents work through the project record in sequence — architecture, structural, mechanical, electrical, interior, quantity surveying and regulation review — and their outputs are then cross-checked for clashes between disciplines.") +
    "</p>";

  var button = '<div class="formactions"><button class="primary" id="run-alarrab" type="button"' +
    (D.status === "running" ? " disabled" : "") + ">" +
    (D.status === "running" ? t("جارٍ التشغيل…", "Running…") :
      (D.data ? t("إعادة تشغيل الوكلاء", "Re-run the agents") : t("شغّل الوكلاء السبعة", "Run the seven agents"))) +
    '</button><span class="actionhint">' +
    t("يعمل على بيانات تبويب المشروع الحالية.", "Runs against the current Project tab values.") + "</span></div>";

  if (D.status === "auth") {
    button += '<div class="card authbox"><p>' + esc(D.error) + "</p>" +
      '<div class="grid"><label>' + t("رمز الوصول", "Access token") +
      '<input type="password" id="alarrab-token" autocomplete="off" placeholder="Bearer token"></label></div>' +
      '<p class="footnote">' + t(
        "يمكن الحصول على الرمز من نقطة /v1/auth/token. لا يُحفظ الرمز إلا في الذاكرة أثناء الجلسة.",
        "Get a token from /v1/auth/token. It is held in memory for this session only and never stored.") + "</p></div>";
  } else if (D.status === "error") {
    button += '<div class="note fail"><strong>' + t("خطأ", "Error") + ":</strong> " + esc(D.error) + "</div>";
  }

  if (!D.data) {
    var roster = [
      ["مهندس معماري أول", "Senior Architecture Engineer", "الكتلة والبرنامج والمخارج", "Massing, program, egress"],
      ["مهندس إنشائي أول", "Senior Structural Engineer", "النظام الإنشائي والأساسات", "Framing system, foundations"],
      ["مهندس ميكانيكي أول", "Senior Mechanical Engineer", "التكييف والسباكة والحريق", "HVAC, plumbing, fire"],
      ["مهندس كهربائي أول", "Senior Electrical Engineer", "الأحمال والتغذية والتوزيع", "Loads, service, distribution"],
      ["مصمم داخلي أول", "Senior Interior Designer", "الارتفاعات والتشطيبات", "Clear heights, finishes"],
      ["مساح كميات أول", "Senior Quantity Surveyor", "الكميات وخطة التكلفة", "Quantities, cost plan"],
      ["أخصائي مراجعة نظامية أول", "Senior Regulation Review Specialist", "الفحص النظامي والجهات", "Rule checks, authorities"]
    ];
    return head + button + '<div class="agentgrid">' + roster.map(function (r, i) {
      return '<div class="agentchip"><span class="agentno">' + String(i + 1).padStart(2, "0") + "</span>" +
        "<div><strong>" + esc(t(r[0], r[1])) + "</strong><span>" + esc(t(r[2], r[3])) + "</span></div></div>";
    }).join("") + "</div>";
  }

  var d = D.data, h = d.headline, co = d.coordination;
  var stale = D.sig && D.sig !== projSig()
    ? '<div class="note warn"><strong>' + t("نتائج قديمة", "Stale results") + "</strong> — " +
      t("تغيّرت بيانات المشروع بعد آخر تشغيل. أعد تشغيل الوكلاء لتحديث المخرجات.",
        "The project data changed after the last run. Re-run the agents to refresh these outputs.") + "</div>"
    : "";
  /* Units live in the labels so every value is a pure LTR numeral. Mixing
   * digits and units inside one RTL cell reorders them visually. */
  var cards = [
    [t("إجمالي المسطحات (م²)", "Gross floor area (m²)"), Number(h.gfa_m2).toLocaleString("en")],
    [t("النتيجة الأولية (من ١٠٠)", "Preliminary score (of 100)"), String(h.preliminary_score)],
    [t("نطاق التكلفة (مليون ر.س)", "Cost range (SAR million)"),
      (h.cost_low_sar / 1e6).toFixed(2) + "-" + (h.cost_high_sar / 1e6).toFixed(2)],
    [t("المدة التقديرية (شهر)", "Indicative period (months)"), String(h.months)],
    [t("تعارضات التنسيق", "Coordination issues"), String(h.coordination_issues)],
    [t("بنود التحقق", "Verification items"), String(h.verification_items)]
  ];

  var coordination = '<h3 class="section sub">' + t("سجل التنسيق بين التخصصات", "Cross-discipline coordination register") +
    "</h3>" + (co.total === 0 ?
      '<div class="note"><strong>' + t("لا تعارضات", "No clashes") + "</strong> — " +
      t("لم يُرصد تعارض بين مخرجات التخصصات لهذه المعطيات.",
        "No clash was detected between the disciplines for these inputs.") + "</div>" :
      co.issues.map(function (i) {
        return '<div class="note ' + (i.severity === "high" ? "fail" : (i.severity === "medium" ? "warn" : "")) + '">' +
          '<div class="issuehead"><span class="' + sevClass(i.severity) + '">' +
          esc(t(SEV_LABEL[i.severity][0], SEV_LABEL[i.severity][1])) + '</span><span class="issuedisc">' +
          esc(i.disciplines.join(" · ")) + "</span></div>" +
          "<p>" + esc(t(i.ar, i.en)) + "</p>" +
          '<p class="issueact"><strong>' + t("الإجراء", "Action") + ":</strong> " +
          esc(t(i.action_ar, i.action_en)) + "</p></div>";
      }).join(""));

  return head + button + stale +
    '<div class="cards headline">' + cards.map(function (c) {
      return '<div class="metric"><div class="k">' + esc(c[0]) + '</div><div class="v">' + esc(c[1]) + "</div></div>";
    }).join("") + "</div>" +
    coordination +
    '<h3 class="section sub">' + t("تقارير التخصصات", "Discipline reports") + "</h3>" +
    d.agents.map(alarrabAgent).join("") +
    '<p class="footnote">' + esc(t(d.note_ar, d.note_en)) + "</p>";
}

/* ============================ render + events ============================ */

var TABS = [
  ["project", "بيانات المشروع", "Project"],
  ["drawings", "المخططات", "Drawings"],
  ["review", "المراجعة الأولية", "Review"],
  ["permit", "جاهزية الرخصة", "Permit"],
  ["alarrab", "التصميم بواسطة العرّاب", "Design by Alarrab"],
  ["assistant", "مساعد التصميم", "Assistant"],
  ["sources", "المصادر", "Sources"]
];

function render() {
  document.documentElement.setAttribute("dir", S.lang === "ar" ? "rtl" : "ltr");
  document.documentElement.setAttribute("lang", S.lang);
  document.getElementById("app-title").textContent = t("العرّاب لفحص كود البناء", "Alarrab Building Code Review");
  document.getElementById("preview-badge").textContent = t("نسخة تجريبية — مراجعة أولية غير رسمية", "Preview — unofficial preliminary review");
  document.getElementById("lang-toggle").textContent = S.lang === "ar" ? "EN" : "ع";

  document.getElementById("tabs").innerHTML = TABS.map(function (tb) {
    return '<button class="tab' + (S.tab === tb[0] ? " active" : "") + '" data-tab="' + tb[0] + '" type="button">' +
      esc(t(tb[1], tb[2])) + "</button>";
  }).join("");

  var panel = { project: panelProject, drawings: panelDrawings, review: panelReview,
    permit: panelPermit, alarrab: panelAlarrab, assistant: panelAssistant,
    sources: panelSources }[S.tab] || panelProject;
  document.getElementById("main").innerHTML = panel();
}

function onClick(ev) {
  var el = ev.target.closest("[data-tab], [data-sheet], [data-go], #print-sheet, #lang-toggle, #run-alarrab");
  if (!el) { return; }
  if (el.id === "run-alarrab") { runAlarrab(); return; }
  if (el.id === "lang-toggle") { S.lang = S.lang === "ar" ? "en" : "ar"; render(); return; }
  if (el.id === "print-sheet") { window.print(); return; }
  if (el.dataset.tab) { S.tab = el.dataset.tab; render(); return; }
  if (el.dataset.sheet) { S.sheet = el.dataset.sheet; render(); return; }
  if (el.dataset.go) { S.tab = el.dataset.go; render(); }
}

function onChange(ev) {
  var el = ev.target;
  if (el.dataset && el.dataset.field) {
    S.p[el.dataset.field] = el.value;
    if (S.tab === "project") {
      // keep focus: only refresh the derived summary while typing
      var g = geom(), d = document.querySelector(".derived");
      if (d) { d.textContent = fmt(g.plotArea, 0) + " m² · " + fmt(g.bw, 1) + "×" + fmt(g.bd, 1) + " m · " + g.floors + "F · FAR " + fmt(g.far, 2); }
    } else {
      render();
    }
    return;
  }
  if (el.dataset && el.dataset.doc) {
    S.docs[el.dataset.doc] = el.checked;
    render();
  }
}

/* Optional: use the authenticated server engine instead of the local checks.
 * The local engine mirrors data/rules_seed.json so the UI works unauthenticated.
 *
 * async function loadServerAssessment() {
 *   var g = geom();
 *   var res = await fetch(API_BASE + "/v1/assess", {
 *     method: "POST",
 *     headers: { "Content-Type": "application/json" },
 *     body: JSON.stringify({
 *       project_name: S.p.project_name, city: S.p.city, land_use: S.p.land_use,
 *       plot_area_m2: g.plotArea, floors: g.floors, building_height_m: g.height,
 *       setback_front_m: g.sbF, setback_side_m: g.sbS, setback_rear_m: g.sbR,
 *       coverage_ratio: g.coverage, far: g.far, units: g.units, parking_spaces: g.parking
 *     })
 *   });
 *   return res.ok ? res.json() : null;
 * }
 */

document.addEventListener("DOMContentLoaded", function () {
  render();
  document.addEventListener("click", onClick);
  document.addEventListener("input", onChange);
  document.addEventListener("change", onChange);
});
