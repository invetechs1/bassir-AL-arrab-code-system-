# Alarrab CodeVision AI — Powered by Bassir Technology

منصة سعودية للمراجعة الهندسية والتنظيمية الأولية بمساعدة الذكاء الاصطناعي.
AI-assisted preliminary engineering & regulatory review platform foundation for the Saudi market.

> **إخلاء مسؤولية / Disclaimer**
> هذا النظام يقدم مراجعة هندسية وتنظيمية أولية بمساعدة الذكاء الاصطناعي فقط. وهو ليس جهة اعتماد رسمية ولا يغني عن المهندسين المرخصين، أو الوثائق الرسمية لكود البناء السعودي، أو البلديات، أو الدفاع المدني، أو مزودي الخدمات، أو الجهات الحكومية. يجب التحقق من جميع المخرجات بواسطة مختصين مؤهلين قبل التقديم أو التنفيذ.
>
> This system provides AI-assisted preliminary engineering and regulatory review only. It is not an official approval authority and does not replace licensed engineers, Saudi Building Code official documents, municipalities, Civil Defense, utility providers, or government authorities. All outputs must be verified by qualified professionals before submission or construction.

## Features (MVP foundation)

- Preliminary parameter review against **draft** verification rules (never claimed official)
- Permit-readiness scoring with the standard Saudi document checklist
- Heuristic design assistant (advisory only)
- Drawing/file upload with strict security validation (size, extension, magic bytes, path traversal, dangerous names)
- Vision & BIM/IFC review foundations (honest metadata extraction; CV pipeline on roadmap)
- Arabic RTL report generation (HTML + JSON)
- Six-tab Arabic/English web interface with a client-side **2D schematic drawing generator** (7 sheets: site, ground floor, typical floor, elevation, section, parking, roof) and A3-landscape print/PDF
- Regulatory source catalog + governed rule-candidate review workflow (P0/P1/P2)
- JWT + API-key auth, roles/permissions, tenant-scoped data model, audit logs
- FastAPI + SQLAlchemy (SQLite demo / PostgreSQL production), Docker, Nginx

## Quick start (local demo)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.cli seed          # demo tenant + admin + draft rules
python3 -m app.cli serve         # http://localhost:8000/ui
```

Or with Docker:

```bash
docker compose up --build        # http://localhost:8000/ui
```

## Production (Ubuntu VPS + Nginx/Cloudflare)

```bash
cp .env.example .env             # fill in real values (SECRET_KEY, DB password, domain)
./scripts/deploy.sh
./scripts/healthcheck.sh https://your-domain.example
```

Backups: `./scripts/backup-db.sh` (cron daily) — restore with `./scripts/restore-db.sh <file>`.

## API surface

| Endpoint | Purpose |
|---|---|
| `GET /v1/health`, `GET /v1/version` | liveness / build info |
| `POST /v1/assess` | preliminary parameter assessment |
| `POST /v1/assess/file`, `POST /v1/assess/vision` | secure file intake + metadata/vision foundation |
| `POST /v1/assistant/suggest` | source-grounded guidance (no fabricated code values) |
| `POST /v1/design/suggest` | advisory design estimates |
| `POST /v1/permit/readiness` | permit readiness score |
| `POST /v1/bim/review` (+`/file`) | IFC container checks |
| `POST /v1/report/generate` | Arabic RTL report (HTML+JSON) |
| `GET /v1/rules` | draft rule set (all inactive, none official) |
| `GET /v1/regulatory-resources` (+`/summary`) | governed source catalog |
| `GET /v1/rule-candidates/from-resources`, `GET /v1/rule-candidates/review-package` | candidate workflow |
| `POST /v1/rule-candidates/review/validate`, `POST /v1/rule-candidates/review/export-draft-rules` | professional review → inactive draft rules |
| `GET /v1/production/readiness` | deployment self-checks |
| `GET /ui` | Arabic/English RTL web interface + 2D drawing generator |

## Web interface (`/ui`)

Vanilla HTML/CSS/JS served from `web/` by `app/api/routes_ui.py` — no build step,
no bundler, no npm install. Six tabs: Project, Drawings, Review, Permit, Assistant,
Sources; Arabic RTL by default with an EN toggle.

The **Drawings** tab generates seven schematic CAD sheets client-side from the
project record (A-101 site, A-102 ground floor, A-103 typical floor, A-201
elevation, A-301 section, A-104 parking, A-105 roof). Geometry, space planning, and
parking layout are deterministic and dependency-free; compliance failures are drawn
onto the relevant sheets. The print button produces A3-landscape output, one sheet
per page.

The Review tab mirrors the ten rules in `data/rules_seed.json` client-side (same
`high|medium|low` severities and 3/2/1 score weighting as `app/engine/assessment.py`)
so the UI is usable unauthenticated. **These remain DRAFT placeholder values, not
official code requirements** — the governance invariants below still hold, and the
generated sheets are indicative schematics, not approved construction documents.
To use the server engine instead, uncomment `loadServerAssessment()` at the bottom
of `web/app.js`; `/v1/assess` requires an auth token with `assess:run`.

Fonts (IBM Plex Sans Arabic / IBM Plex Mono) load from Google Fonts, which the
Content-Security-Policy in `app/security/headers.py` permits. For a deployment that
must make no third-party requests, self-host both families, swap the `<link>` in
`web/index.html`, and drop `fonts.googleapis.com` / `fonts.gstatic.com` from that
policy — the CSS already falls back to `system-ui` / `monospace`.

## Regulatory governance invariants

1. No source becomes a rule automatically — candidates require professional review.
2. Draft/consultation sources are never binding and can never be exported as rules.
3. Exported rules are always `is_active=false`, `is_official=false`; activation is a separate operational decision.
4. A rule is official only with `source_reference`, exact `clause`, `last_reviewed_date`, `confidence_level`, and `validated_by` (licensed professional) — the shipped seed set satisfies none of these on purpose.

## Tests

```bash
python3 -m unittest discover -s tests -v
node --check web/app.js
docker compose config
docker compose -f docker-compose.prod.yml --env-file .env.example config
```

## CLI

```bash
python3 -m app.cli seed|serve|assess <file.json>|rules|resources|candidates|readiness
```
