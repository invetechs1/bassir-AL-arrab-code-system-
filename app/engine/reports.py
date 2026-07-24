"""Report generation: structured JSON plus an Arabic-first RTL HTML file."""

import html
import json
import uuid
from datetime import datetime, timezone

from app.config import settings
from app.legal import DISCLAIMER_AR, DISCLAIMER_EN
from app.version import APP_NAME, APP_VENDOR, __version__

STATUS_LABELS_AR = {
    "pass": "مستوفى مبدئيًا",
    "fail": "غير مستوفى",
    "needs_review": "يحتاج مراجعة",
}


def _findings_rows(findings) -> str:
    rows = []
    for f in findings:
        status = f.get("status", "needs_review")
        rows.append(
            "<tr class='st-{s}'><td>{code}</td><td>{title}</td><td>{cat}</td>"
            "<td>{status}</td><td dir='ltr'>{detail}</td></tr>".format(
                s=status,
                code=html.escape(str(f.get("rule_code", ""))),
                title=html.escape(str(f.get("title_ar", ""))),
                cat=html.escape(str(f.get("category", ""))),
                status=STATUS_LABELS_AR.get(status, status),
                detail=html.escape(str(f.get("detail", ""))),
            )
        )
    return "\n".join(rows)


def build_report(payload: dict) -> dict:
    """payload: {title?, project?, assessment?, permit?, extra_sections?}"""
    report_id = uuid.uuid4().hex
    created_at = datetime.now(timezone.utc).isoformat()
    title = payload.get("title") or "تقرير المراجعة الأولية"
    project = payload.get("project") or {}
    assessment = payload.get("assessment") or {}
    permit = payload.get("permit") or {}

    report = {
        "report_id": report_id,
        "created_at": created_at,
        "generator": f"{APP_NAME} v{__version__} — {APP_VENDOR}",
        "title": title,
        "project": project,
        "assessment_summary": {
            "overall_status": assessment.get("overall_status"),
            "score": assessment.get("score"),
            "counts": assessment.get("counts"),
        } if assessment else None,
        "findings": assessment.get("findings", []),
        "permit_readiness": {
            "score": permit.get("readiness_score"),
            "level": permit.get("readiness_level"),
            "missing": permit.get("missing", []),
        } if permit else None,
        "official_basis": False,
        "disclaimer": {"ar": DISCLAIMER_AR, "en": DISCLAIMER_EN},
    }

    project_rows = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td dir='ltr'>{html.escape(str(v))}</td></tr>"
        for k, v in project.items()
    )

    score_block = ""
    if assessment:
        score_block = (
            f"<div class='score'>نتيجة المراجعة الأولية: <b>{assessment.get('score', '—')}</b>/100 "
            f"({html.escape(str(assessment.get('overall_status', '')))})</div>"
        )

    permit_block = ""
    if permit:
        missing = "".join(f"<li>{html.escape(m.get('ar', ''))}</li>" for m in permit.get("missing", []))
        permit_block = (
            f"<h2>جاهزية الرخصة (استرشادي)</h2>"
            f"<div class='score'>المؤشر: <b>{permit.get('readiness_score', '—')}</b>/100</div>"
            f"<h3>المتطلبات الناقصة</h3><ul>{missing or '<li>لا يوجد</li>'}</ul>"
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
  body {{ font-family: 'Segoe UI', Tahoma, Arial, sans-serif; margin: 2rem; color: #1a2332; }}
  header {{ border-bottom: 3px solid #0f6b54; padding-bottom: .75rem; margin-bottom: 1.5rem; }}
  h1 {{ margin: 0 0 .25rem; font-size: 1.5rem; }}
  .meta {{ color: #5a6a7a; font-size: .85rem; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; font-size: .9rem; }}
  th, td {{ border: 1px solid #d5dce3; padding: .5rem .6rem; text-align: right; }}
  th {{ background: #f0f4f7; }}
  .score {{ background: #eef7f3; border: 1px solid #bfe0d3; border-radius: 8px; padding: .75rem 1rem; margin: 1rem 0; }}
  .st-pass td {{ background: #f2faf5; }}
  .st-fail td {{ background: #fdf1f1; }}
  .st-needs_review td {{ background: #fdf8ec; }}
  .disclaimer {{ background: #fff8e6; border: 1px solid #e8d28a; border-radius: 8px; padding: 1rem; margin-top: 2rem; font-size: .85rem; }}
  .disclaimer p[dir='ltr'] {{ text-align: left; color: #6a5d2e; }}
</style>
</head>
<body>
<header>
  <h1>{html.escape(title)}</h1>
  <div class="meta">{html.escape(APP_NAME)} — {html.escape(APP_VENDOR)} | الإصدار {__version__} | معرف التقرير: {report_id} | {created_at}</div>
  <div class="meta"><b>وثيقة أولية غير رسمية — مسودة قواعد غير معتمدة</b></div>
</header>
<h2>بيانات المشروع</h2>
<table>{project_rows or '<tr><td>لا توجد بيانات مشروع</td></tr>'}</table>
{score_block}
<h2>نتائج الفحوصات الأولية (قواعد مسودة)</h2>
<table>
<tr><th>الكود</th><th>الفحص</th><th>التصنيف</th><th>الحالة</th><th>التفاصيل</th></tr>
{_findings_rows(assessment.get('findings', []))}
</table>
{permit_block}
<div class="disclaimer">
  <p>{html.escape(DISCLAIMER_AR)}</p>
  <p dir="ltr">{html.escape(DISCLAIMER_EN)}</p>
</div>
</body>
</html>"""

    settings.ensure_dirs()
    html_path = settings.reports_dir / f"{report_id}.html"
    json_path = settings.reports_dir / f"{report_id}.json"
    html_path.write_text(html_doc, encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    report["files"] = {"html": str(html_path), "json": str(json_path)}
    return report
