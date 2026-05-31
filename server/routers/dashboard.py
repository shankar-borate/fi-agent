"""
FI Case Dashboard — web UI + supporting JSON APIs.

GET /                       → HTML dashboard
GET /api/cases              → list of all cases (summary)
GET /api/cases/{case_id}    → full detail for one case
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from config import get_storage_root

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dashboard"])

# ── Dashboard HTML ────────────────────────────────────────────────────────────

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FI Case Dashboard</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    html, body { height: 100%; margin: 0; overflow: hidden; font-family: sans-serif; }
    .sidebar {
      width: 300px; min-width: 300px; height: 100vh; overflow-y: auto;
      background: #1A237E; color: #fff; flex-shrink: 0;
    }
    .sidebar-header { padding: 14px 16px; border-bottom: 1px solid rgba(255,255,255,.15); }
    .main-panel { flex: 1; height: 100vh; overflow-y: auto; background: #f4f6fb; }
    .case-card {
      cursor: pointer; border-radius: 8px; margin-bottom: 8px;
      border-left: 4px solid transparent; background: rgba(255,255,255,.12);
      color: #fff; padding: 10px 12px; transition: .15s;
    }
    .case-card:hover  { background: rgba(255,255,255,.22); border-left-color: #E53935; }
    .case-card.active { background: rgba(255,255,255,.28); border-left-color: #E53935; }
    .section-hdr {
      background: #1A237E; color: #fff; padding: 7px 14px;
      border-radius: 5px; font-weight: 600; margin-bottom: 12px; font-size: .9rem;
    }
    .qa-table td:first-child { width: 42%; background: #e8eaf6; font-weight: 500; }
    .analysis-box {
      font-size: .8rem; white-space: pre-wrap; background: #f9fafb;
      padding: 10px; border-radius: 4px; max-height: 260px;
      overflow-y: auto; border: 1px solid #dee2e6;
    }
    .photo-thumb { width: 100%; height: 180px; object-fit: cover; border-radius: 4px 4px 0 0; }
    .empty-panel { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; color:#aaa; }
  </style>
</head>
<body>
<div class="d-flex" style="height:100vh">

  <!-- ── LEFT SIDEBAR ──────────────────────────────────────── -->
  <div class="sidebar">
    <div class="sidebar-header d-flex justify-content-between align-items-center">
      <div>
        <div class="fw-bold fs-6">FI Case Dashboard</div>
        <div class="text-white-50 small" id="caseCount">Loading…</div>
      </div>
      <button class="btn btn-sm btn-outline-light py-0 px-2" onclick="loadCases()">⟳</button>
    </div>
    <div id="caseList" class="p-2"></div>
  </div>

  <!-- ── MAIN PANEL ─────────────────────────────────────────── -->
  <div class="main-panel p-4" id="mainPanel">
    <div class="empty-panel">
      <div style="font-size:3.5rem">📋</div>
      <p class="mt-2">Select a case from the left panel</p>
    </div>
  </div>
</div>

<script>
// ── Case list ──────────────────────────────────────────────────────────────
async function loadCases() {
  document.getElementById('caseCount').textContent = 'Loading…';
  const cases = await apiFetch('/api/cases');
  if (!cases) return;
  document.getElementById('caseCount').textContent =
    `${cases.length} case${cases.length !== 1 ? 's' : ''}`;
  document.getElementById('caseList').innerHTML = cases.map(c => `
    <div class="case-card" id="card-${c.case_id}" onclick="loadCase('${c.case_id}')">
      <div class="d-flex justify-content-between align-items-start">
        <span class="fs-5 fw-bold">#${c.case_id}</span>
        ${c.has_report ? '<span class="badge bg-success" style="font-size:.65rem">PDF</span>' : ''}
      </div>
      <div class="small text-white-50">${fmtDate(c.started_at)}</div>
      <div class="mt-1">
        <span class="badge bg-primary me-1">${c.question_count} Q&amp;A</span>
        <span class="badge bg-secondary me-1">${c.photo_count} photos</span>
        ${c.has_recording ? '<span class="badge bg-info text-dark">REC</span>' : ''}
      </div>
    </div>`).join('');
}

// ── Case detail ────────────────────────────────────────────────────────────
async function loadCase(caseId) {
  document.querySelectorAll('.case-card').forEach(c => c.classList.remove('active'));
  const card = document.getElementById(`card-${caseId}`);
  if (card) card.classList.add('active');
  document.getElementById('mainPanel').innerHTML =
    '<div class="empty-panel"><div class="spinner-border text-primary"></div></div>';
  const data = await apiFetch(`/api/cases/${caseId}`);
  if (!data) return;
  renderCase(data);
}

// ── Render ─────────────────────────────────────────────────────────────────
function renderCase(d) {
  const meta = d.metadata || {};
  const questions = meta.questions || [];
  const photos    = meta.photos   || [];
  const responses = d.responses   || {};

  // ── Section 1: Session info + Q&A
  const qaRows = questions.length
    ? questions.map((q, i) => `
        <tr>
          <td>Q${i+1}: ${esc(q.question)}</td>
          <td>${esc(q.answer)}</td>
        </tr>`).join('')
    : '<tr><td colspan="2" class="text-muted small">No Q&amp;A recorded</td></tr>';

  // ── Section 2: Photos
  const photoCards = photos.length ? photos.map((p, i) => {
    const analysis = responses[`photo_${i}_analysis.txt`] || '';
    return `
      <div class="col-md-6 col-lg-4">
        <div class="card shadow-sm h-100">
          <img src="/storage/${d.case_id}/${p.filename}" class="photo-thumb"
               onerror="this.src=''" alt="${esc(p.prompt)}">
          <div class="card-body p-2">
            <p class="small fw-semibold text-truncate mb-1" title="${esc(p.prompt)}">${esc(p.prompt)}</p>
            ${analysis
              ? `<div class="analysis-box">${esc(analysis)}</div>`
              : '<p class="text-muted small mb-0">Analysis not yet available</p>'}
          </div>
        </div>
      </div>`;
  }).join('') : '<div class="col text-muted small">No photos recorded</div>';

  // ── Section 3: Geo
  const geoHtml = d.geo_result ? buildGeoHtml(d.geo_result) : '';

  // ── Section 4: Files
  const fileLinks = (d.files || []).map(f => `
    <li class="list-group-item d-flex justify-content-between align-items-center py-1">
      <span class="small font-monospace">${esc(f)}</span>
      <a href="/storage/${d.case_id}/${f}" target="_blank"
         class="btn btn-outline-secondary btn-sm py-0 px-2">⬇</a>
    </li>`).join('');

  document.getElementById('mainPanel').innerHTML = `
    <div class="border-bottom pb-3 mb-4 d-flex align-items-start justify-content-between flex-wrap gap-2">
      <div>
        <h4 class="mb-0">Case <span class="text-primary fw-bold">#${d.case_id}</span></h4>
        <div class="text-muted small">
          Device: ${esc(meta.device_id || '—')} &nbsp;|&nbsp;
          Started: ${fmtDate(meta.started_at)} &nbsp;|&nbsp;
          Ended: ${fmtDate(meta.ended_at)}
        </div>
      </div>
      ${d.report_url
        ? `<a href="${d.report_url}" target="_blank" class="btn btn-danger btn-sm">⬇ Download Report PDF</a>`
        : '<span class="text-muted small align-self-center">Report not yet generated</span>'}
    </div>

    <div class="section-hdr">1. Field Q&amp;A</div>
    <div class="table-responsive mb-4">
      <table class="table table-bordered table-sm qa-table mb-0">
        <tbody>${qaRows}</tbody>
      </table>
    </div>

    <div class="section-hdr">2. Photos &amp; AI Analysis</div>
    <div class="row g-3 mb-4">${photoCards}</div>

    ${geoHtml ? `<div class="section-hdr">3. Geo Verification</div>
    <div class="mb-4">${geoHtml}</div>` : ''}

    <div class="section-hdr">${geoHtml ? '4' : '3'}. Session Files</div>
    <ul class="list-group mb-5">${fileLinks || '<li class="list-group-item text-muted small">No files found</li>'}</ul>
  `;
}

function buildGeoHtml(geo) {
  const ok = geo.verified;
  const detailRows = (geo.details || []).map(d => `
    <tr class="${d.within_radius ? 'table-success' : 'table-danger'}">
      <td>${esc(d.label)}</td>
      <td>${(d.latitude  || 0).toFixed(6)}</td>
      <td>${(d.longitude || 0).toFixed(6)}</td>
      <td>${Math.round(d.distance_from_centroid_m || 0)}</td>
      <td class="text-center">${d.within_radius ? '✔' : '✘'}</td>
    </tr>`).join('');

  return `
    <div class="alert ${ok ? 'alert-success' : 'alert-danger'} py-2 mb-2">
      ${ok ? '✔ LOCATION VERIFIED' : '✘ LOCATION FAILED'} —
      ${geo.points_checked} points checked, max distance
      <strong>${Math.round(geo.max_distance_m || 0)} m</strong>
      (radius: ${geo.radius_m} m)
    </div>
    ${detailRows ? `
    <div class="table-responsive">
      <table class="table table-sm table-bordered small mb-0">
        <thead class="table-dark">
          <tr><th>Event</th><th>Latitude</th><th>Longitude</th><th>Dist (m)</th><th>OK?</th></tr>
        </thead>
        <tbody>${detailRows}</tbody>
      </table>
    </div>` : ''}`;
}

// ── Helpers ────────────────────────────────────────────────────────────────
async function apiFetch(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return await res.json();
  } catch (e) {
    document.getElementById('mainPanel').innerHTML =
      `<div class="alert alert-danger m-4">Error: ${e.message}</div>`;
    return null;
  }
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString(); } catch { return iso; }
}

function esc(s) {
  return String(s || '')
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadCases();
</script>
</body>
</html>"""


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return _DASHBOARD_HTML


@router.get("/api/cases", summary="List all cases")
async def list_cases() -> List[Dict[str, Any]]:
    root = get_storage_root()
    result: List[Dict[str, Any]] = []

    for folder in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not folder.is_dir():
            continue
        case_id = folder.name
        meta_file = folder / "metadata.json"

        started_at = ended_at = None
        question_count = photo_count = 0
        has_recording = has_report = False

        if meta_file.exists():
            try:
                m = json.loads(meta_file.read_text(encoding="utf-8"))
                started_at    = m.get("started_at")
                ended_at      = m.get("ended_at")
                question_count = len(m.get("questions", []))
                photo_count   = len(m.get("photos", []))
            except Exception as exc:
                logger.warning("[Dashboard] Cannot parse metadata for %s: %s", case_id, exc)

        for f in folder.iterdir():
            if f.is_file():
                if f.suffix in (".mp4", ".aac", ".m4a", ".webm"):
                    has_recording = True
                if f.suffix == ".pdf":
                    has_report = True

        result.append({
            "case_id":        case_id,
            "started_at":     started_at,
            "ended_at":       ended_at,
            "question_count": question_count,
            "photo_count":    photo_count,
            "has_recording":  has_recording,
            "has_report":     has_report,
        })

    return result


@router.get("/api/cases/{case_id}", summary="Get case detail")
async def get_case(case_id: str) -> Dict[str, Any]:
    folder = get_storage_root() / case_id
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Metadata
    meta_dict: Dict[str, Any] = {}
    meta_file = folder / "metadata.json"
    if meta_file.exists():
        try:
            meta_dict = json.loads(meta_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[Dashboard] Cannot parse metadata for %s: %s", case_id, exc)

    # Main files (exclude metadata.json; responses/ is a sub-folder)
    files = [
        f.name for f in folder.iterdir()
        if f.is_file() and f.name != "metadata.json"
    ]

    # Response files (geo JSON + photo analyses)
    responses: Dict[str, str] = {}
    geo_result: Any = None
    responses_folder = folder / "responses"
    if responses_folder.exists():
        for rf in responses_folder.iterdir():
            if rf.is_file():
                try:
                    content = rf.read_text(encoding="utf-8")
                    responses[rf.name] = content
                    if rf.name == "geo_verification.json":
                        geo_result = json.loads(content)
                except Exception as exc:
                    logger.warning("[Dashboard] Cannot read response file %s: %s", rf.name, exc)

    report_filename = next((f for f in files if f.endswith(".pdf")), None)
    report_url = f"/storage/{case_id}/{report_filename}" if report_filename else None

    return {
        "case_id":          case_id,
        "metadata":         meta_dict,
        "files":            sorted(files),
        "responses":        responses,
        "geo_result":       geo_result,
        "report_url":       report_url,
        "report_filename":  report_filename,
    }
