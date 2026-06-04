"""
ABC Bank  —  Field Investigation Auditor Portal

Routes:
  GET  /auditor/            → Login page (or redirect to case list if already authenticated)
  GET  /auditor/cases       → Case list page
  GET  /auditor/cases/{id}  → Case detail page (designed to be opened in a new tab)
  POST /auditor/api/login   → Authenticate (credentials: test / test)
  GET  /auditor/api/cases   → JSON list of all cases
  GET  /auditor/api/cases/{id}   → JSON detail for one case
  POST /auditor/api/cases/{id}/decision  → Save Accepted / Rejected decision
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from config import get_storage_root

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auditor", tags=["auditor"])

# ── Simple token store (single-user, in-memory) ───────────────────────────────
_VALID_TOKEN = "abc-bank-auditor-2025"
_CREDENTIALS = {"test": "test"}


def _check_token(request: Request) -> bool:
    token = request.cookies.get("auditor_token") or request.headers.get("x-auditor-token")
    return token == _VALID_TOKEN


# ══════════════════════════════════════════════════════════════════════════════
#  HTML helpers
# ══════════════════════════════════════════════════════════════════════════════

_NAV = """
<nav class="navbar">
  <div class="nav-inner">
    <div class="nav-brand">
      <span class="nav-icon">🏦</span>
      <span>ABC Bank — FI Auditor Portal</span>
    </div>
    <div class="nav-right">
      <span class="nav-badge">Bank Employee</span>
      <button class="btn-logout" onclick="logout()">Logout</button>
    </div>
  </div>
</nav>
"""

_BASE_STYLES = """
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#F0F4FF;color:#1a1a2e;min-height:100vh}
.navbar{background:#0D47A1;color:#fff;position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.nav-inner{max-width:1400px;margin:0 auto;padding:12px 24px;display:flex;align-items:center;justify-content:space-between}
.nav-brand{display:flex;align-items:center;gap:10px;font-size:17px;font-weight:700}
.nav-icon{font-size:22px}
.nav-right{display:flex;align-items:center;gap:12px}
.nav-badge{background:rgba(255,255,255,.2);border-radius:20px;padding:4px 12px;font-size:12px;font-weight:600}
.btn-logout{background:transparent;border:1px solid rgba(255,255,255,.5);color:#fff;
  border-radius:6px;padding:5px 14px;font-size:13px;cursor:pointer}
.btn-logout:hover{background:rgba(255,255,255,.15)}

/* Card */
.card{background:#fff;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.08);overflow:hidden}
.card-header{padding:16px 20px;border-bottom:1px solid #e8ecf4;display:flex;align-items:center;
  justify-content:space-between;flex-wrap:wrap;gap:8px}
.card-title{font-size:16px;font-weight:700;color:#0D47A1}
.card-body{padding:20px}

/* Buttons */
.btn{border:none;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;
  padding:10px 22px;transition:opacity .15s}
.btn:hover{opacity:.88}
.btn-primary{background:#0D47A1;color:#fff}
.btn-success{background:#2E7D32;color:#fff}
.btn-danger {background:#C62828;color:#fff}
.btn-outline{background:transparent;border:2px solid #0D47A1;color:#0D47A1}
.btn-sm{padding:6px 14px;font-size:12px}
.btn-gold{background:#F9A825;color:#1a1a1a}

/* Status badge */
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;
  letter-spacing:.3px}
.badge-complete  {background:#E8F5E9;color:#1B5E20}
.badge-incomplete{background:#FFF3E0;color:#E65100}
.badge-accepted  {background:#E3F2FD;color:#0D47A1}
.badge-rejected  {background:#FCE4EC;color:#880E4F}
.badge-pending   {background:#F3E5F5;color:#4A148C}

/* Table */
.data-table{width:100%;border-collapse:collapse;font-size:14px}
.data-table th{background:#0D47A1;color:#fff;padding:12px 14px;text-align:left;font-weight:600;
  font-size:13px;letter-spacing:.3px}
.data-table td{padding:11px 14px;border-bottom:1px solid #e8ecf4;vertical-align:middle}
.data-table tr:hover td{background:#F7F9FF}
.data-table .case-link{color:#0D47A1;font-weight:700;cursor:pointer;text-decoration:none}
.data-table .case-link:hover{text-decoration:underline}

/* Forms */
.form-group{margin-bottom:18px}
.form-label{display:block;font-size:13px;font-weight:600;color:#555;margin-bottom:6px}
.form-control{width:100%;border:1.5px solid #cdd5e0;border-radius:8px;padding:11px 14px;
  font-size:15px;font-family:inherit;outline:none;transition:border-color .15s}
.form-control:focus{border-color:#0D47A1}

/* Misc */
.page-wrap{max-width:1400px;margin:0 auto;padding:28px 24px}
.section-title{font-size:22px;font-weight:800;color:#0D47A1;margin-bottom:20px}
.kv-row{display:flex;border-bottom:1px solid #eef0f5;padding:9px 0}
.kv-key{min-width:180px;font-size:13px;font-weight:600;color:#667}
.kv-val{font-size:13px;color:#1a1a2e;flex:1}
.incomplete-flag{color:#6A1B9A;font-weight:700}
.photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.photo-card img{width:100%;height:180px;object-fit:cover;border-radius:8px 8px 0 0;display:block}
.photo-meta{padding:10px 12px}
.photo-tag{font-size:11px;background:#E3F2FD;color:#0D47A1;border-radius:4px;
  padding:2px 8px;font-weight:700;margin-bottom:6px;display:inline-block}
.photo-analysis{font-size:12px;color:#444;white-space:pre-wrap;max-height:200px;
  overflow-y:auto;margin-top:6px;background:#f8f9fe;padding:8px;border-radius:4px}
.decision-bar{position:fixed;bottom:0;left:0;right:0;background:#fff;
  border-top:2px solid #e8ecf4;padding:14px 24px;
  display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 -4px 16px rgba(0,0,0,.1);z-index:200}
.decision-label{font-size:14px;font-weight:600;color:#555}
.decision-btns{display:flex;gap:12px}
.incomplete-notice{background:#F3E5F5;border:1.5px solid #6A1B9A;border-radius:8px;
  padding:10px 16px;color:#4A148C;font-weight:600;font-size:13px;margin:8px 0}
.spinner{display:inline-block;width:20px;height:20px;border:3px solid rgba(0,0,0,.1);
  border-top-color:#0D47A1;border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.empty-state{text-align:center;padding:60px 20px;color:#999}
.empty-state-icon{font-size:48px;margin-bottom:12px}
</style>
"""

_SCRIPT_COMMON = """
<script>
function logout(){document.cookie='auditor_token=;max-age=0;path=/';location.href='/fi/auditor/'}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;')
  .replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function fmtDate(iso){
  if(!iso) return '—';
  try{
    return new Date(iso).toLocaleString('en-IN',{
      timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric',
      hour:'2-digit',minute:'2-digit',hour12:true
    }) + ' IST';
  }catch{return iso;}
}
function fmtDateOnly(iso){
  if(!iso) return '—';
  try{
    return new Date(iso).toLocaleDateString('en-IN',{
      timeZone:'Asia/Kolkata',day:'2-digit',month:'short',year:'numeric'
    });
  }catch{return iso;}
}
</script>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  LOGIN PAGE
# ══════════════════════════════════════════════════════════════════════════════

_LOGIN_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ABC Bank — Auditor Login</title>
  {_BASE_STYLES}
  <style>
    body{{background:linear-gradient(135deg,#0D47A1 0%,#1565C0 100%);display:flex;
      align-items:center;justify-content:center;min-height:100vh}}
    .login-card{{background:#fff;border-radius:16px;padding:40px;width:100%;max-width:400px;
      box-shadow:0 8px 40px rgba(0,0,0,.25)}}
    .login-logo{{text-align:center;margin-bottom:28px}}
    .login-logo .icon{{font-size:48px}}
    .login-logo h1{{font-size:22px;font-weight:800;color:#0D47A1;margin-top:8px}}
    .login-logo p{{font-size:13px;color:#777;margin-top:4px}}
    .err{{color:#C62828;font-size:13px;text-align:center;margin:8px 0}}
  </style>
</head>
<body>
  <div class="login-card">
    <div class="login-logo">
      <div class="icon">🏦</div>
      <h1>ABC Bank</h1>
      <p>Field Investigation Auditor Portal</p>
    </div>
    <div id="errMsg" class="err hidden"></div>
    <div class="form-group">
      <label class="form-label">Username</label>
      <input class="form-control" id="username" type="text" placeholder="Enter username"
             autocomplete="username" />
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-control" id="password" type="password" placeholder="Enter password"
             autocomplete="current-password" />
    </div>
    <button class="btn btn-primary" style="width:100%;margin-top:8px" id="btnLogin">
      Login
    </button>
  </div>
  {_SCRIPT_COMMON}
  <script>
  document.getElementById('btnLogin').addEventListener('click', doLogin);
  document.getElementById('password').addEventListener('keydown', e => {{
    if(e.key==='Enter') doLogin();
  }});

  async function doLogin(){{
    const u = document.getElementById('username').value.trim();
    const p = document.getElementById('password').value;
    const btn = document.getElementById('btnLogin');
    btn.disabled = true; btn.textContent = 'Logging in…';
    try{{
      const r = await fetch('/fi/auditor/api/login',{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{username:u, password:p}}),
      }});
      const data = await r.json();
      if(r.ok && data.token){{
        document.cookie = `auditor_token=${{data.token}};path=/;max-age=86400`;
        localStorage.setItem('auditor_username', u);
        location.href = '/fi/auditor/cases';
      }} else {{
        showErr(data.detail || 'Invalid credentials');
      }}
    }} catch(e){{ showErr('Login failed: '+e.message); }}
    finally{{ btn.disabled=false; btn.textContent='Login'; }}
  }}

  function showErr(msg){{
    const el=document.getElementById('errMsg');
    el.textContent=msg; el.classList.remove('hidden');
  }}
  </script>
<div id='lightbox' class='lightbox' onclick='closeLightbox()'>
  <div class='lightbox-close' onclick='closeLightbox()'>&#x2715;</div>
  <img id='lightboxImg' src='' alt=''/>
  <div class='lightbox-caption' id='lightboxCaption'></div>
</div>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
#  CASE LIST PAGE
# ══════════════════════════════════════════════════════════════════════════════

_CASE_LIST_HTML = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>ABC Bank — FI Cases</title>
  {_BASE_STYLES}
</head>
<body>
  {_NAV}
  <div class="page-wrap">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
      <h1 class="section-title" style="margin:0">Field Investigation Cases</h1>
      <div style="display:flex;gap:10px;align-items:center">
        <input id="searchBox" class="form-control" style="width:220px;padding:8px 12px"
               placeholder="Search case ID or name…" oninput="filterTable()" />
        <button class="btn btn-outline btn-sm" onclick="loadCases()">↻ Refresh</button>
      </div>
    </div>

    <div class="card">
      <div class="card-header">
        <span class="card-title">All Cases</span>
        <span id="caseCount" style="font-size:13px;color:#888">Loading…</span>
      </div>
      <div id="tableWrap" style="overflow-x:auto">
        <div class="empty-state"><div class="spinner"></div><p>Loading cases…</p></div>
      </div>
    </div>
  </div>

  {_SCRIPT_COMMON}
  <script>
  let _allRows = [];

  async function loadCases(){{
    document.getElementById('tableWrap').innerHTML =
      '<div class="empty-state"><div class="spinner"></div><p>Loading…</p></div>';
    try{{
      const cases = await fetch('/fi/auditor/api/cases',{{
        headers:{{'x-auditor-token': getCookie('auditor_token')}}
      }}).then(r=>{{if(!r.ok)throw new Error(r.status);return r.json()}});

      document.getElementById('caseCount').textContent =
        `${{cases.length}} case${{cases.length!==1?'s':''}}`;

      if(!cases.length){{
        document.getElementById('tableWrap').innerHTML =
          '<div class="empty-state"><div class="empty-state-icon">📂</div><p>No cases found</p></div>';
        return;
      }}

      _allRows = cases;
      renderTable(cases);
    }} catch(e){{
      document.getElementById('tableWrap').innerHTML =
        `<div class="empty-state"><p style="color:#C62828">Error: ${{esc(e.message)}}</p></div>`;
      if(String(e.message).includes('401')) location.href='/fi/auditor/';
    }}
  }}

  function renderTable(rows){{
    const tbody = rows.map((c,idx) => {{
      const statusCls  = c.is_complete ? 'badge-complete' : 'badge-incomplete';
      const statusText = c.is_complete ? 'Complete' : 'Incomplete';
      const decisionBadge = c.decision
        ? `<span class="badge badge-${{c.decision}}">${{c.decision.toUpperCase()}}</span>`
        : '<span class="badge badge-pending">Pending</span>';
      return `<tr>
        <td style="color:#888;font-size:13px">${{idx+1}}</td>
        <td style="white-space:nowrap;font-size:13px">${{fmtDate(c.started_at)}}</td>
        <td>
          <a class="case-link" href="/fi/auditor/cases/${{esc(c.case_id)}}" target="_blank">
            ${{esc(c.case_id)}}
          </a>
        </td>
        <td>${{esc(c.customer_name || '—')}}</td>
        <td>${{esc(c.pan_number || '—')}}</td>
        <td><span class="badge ${{statusCls}}">${{statusText}}</span></td>
        <td>${{decisionBadge}}</td>
        <td>${{c.decided_by
          ? `<div style="font-weight:600;font-size:13px">${{esc(c.decided_by)}}</div>`
             + (c.decided_at ? `<div style="font-size:11px;color:#888">${{fmtDate(c.decided_at)}}</div>` : '')
          : '<span style="color:#ccc;font-size:12px">—</span>'}}
        </td>
        <td>
          ${{c.report_url
            ? `<a href="${{c.report_url}}" target="_blank" class="btn btn-sm btn-gold">⬇ PDF</a>`
            : '<span style="color:#ccc;font-size:12px">—</span>'}}
        </td>
      </tr>`;
    }}).join('');

    document.getElementById('tableWrap').innerHTML = `
      <table class="data-table">
        <thead><tr>
          <th>#</th><th>Date &amp; Time</th><th>Case ID</th>
          <th>Customer Name</th><th>PAN</th>
          <th>Status</th><th>Decision</th><th>Reviewed By</th><th>Report</th>
        </tr></thead>
        <tbody>${{tbody}}</tbody>
      </table>`;
  }}

  function filterTable(){{
    const q = document.getElementById('searchBox').value.toLowerCase();
    const filtered = _allRows.filter(c =>
      (c.case_id||'').toLowerCase().includes(q) ||
      (c.customer_name||'').toLowerCase().includes(q)
    );
    renderTable(filtered);
    document.getElementById('caseCount').textContent =
      `${{filtered.length}} of ${{_allRows.length}} case(s)`;
  }}

  function getCookie(name){{
    return document.cookie.split(';').map(c=>c.trim())
      .find(c=>c.startsWith(name+'='))?.split('=')[1]||'';
  }}

  loadCases();
  </script>
</body>
</html>"""




# ══════════════════════════════════════════════════════════════════════════════
#  CASE DETAIL PAGE  (single scrollable page)
# ══════════════════════════════════════════════════════════════════════════════

def _case_detail_html(case_id: str) -> str:
    cid_js = json.dumps(case_id)
    return (
        f"<!DOCTYPE html>\n<html lang='en'>\n<head>\n"
        f"<meta charset='UTF-8'><meta name='viewport' content='width=device-width,initial-scale=1'>\n"
        f"<title>FI Case {case_id}</title>\n"
        + _BASE_STYLES
        + """
<style>
body{padding-bottom:90px}
.sticky-header{position:sticky;top:0;z-index:100;background:#0D47A1;color:#fff;
  padding:10px 24px;display:flex;align-items:center;justify-content:space-between;
  box-shadow:0 2px 8px rgba(0,0,0,.3)}
.sticky-header h2{font-size:18px;font-weight:800;margin:0;color:#fff}
.sub{color:rgba(255,255,255,.65);font-size:12px;margin-top:2px}
.jump-nav{background:#E8EDF8;border-bottom:1px solid #dce3f3;padding:8px 24px;
  display:flex;gap:6px;flex-wrap:wrap;position:sticky;top:54px;z-index:99}
.jump-link{color:#0D47A1;font-size:12px;font-weight:600;text-decoration:none;
  padding:4px 10px;border-radius:6px;background:rgba(13,71,161,.08)}
.jump-link:hover{background:rgba(13,71,161,.2)}
.page-section{max-width:1200px;margin:0 auto;padding:24px 24px 0}
.sec-card{margin-bottom:24px}
.sec-hdr{background:#0D47A1;color:#fff;padding:10px 16px;border-radius:8px 8px 0 0;font-weight:700;font-size:14px}
.sec-body{background:#fff;border:1px solid #e8ecf4;border-top:none;border-radius:0 0 8px 8px;padding:16px}
.kv-row{display:flex;border-bottom:1px solid #eef0f5;padding:8px 0}
.kv-key{min-width:190px;font-size:13px;font-weight:600;color:#667;flex-shrink:0}
.kv-val{font-size:13px;color:#1a1a2e;flex:1}
.kv-val.inc{color:#6A1B9A;font-weight:700}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:640px){.two-col{grid-template-columns:1fr}}
.photo-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.photo-tag{font-size:11px;background:#E3F2FD;color:#0D47A1;border-radius:4px;padding:2px 8px;font-weight:700;margin-bottom:6px;display:inline-block}
.photo-analysis{font-size:12px;color:#444;white-space:pre-wrap;max-height:200px;overflow-y:auto;margin-top:6px;background:#f8f9fe;padding:8px;border-radius:4px}
.itv-table{width:100%;border-collapse:collapse;font-size:14px}
.itv-table th{background:#0D47A1;color:#fff;padding:10px 12px;text-align:left;font-weight:600}
.itv-table td{padding:10px 12px;border-bottom:1px solid #eef0f5;vertical-align:top}
.inc-notice{background:#F3E5F5;border:1.5px solid #6A1B9A;border-radius:8px;padding:10px 16px;color:#4A148C;font-weight:600;font-size:13px;margin:8px 0}
.score-big{font-size:56px;font-weight:900;color:#0D47A1;text-align:center;line-height:1}
.pdf-frame{width:100%;height:800px;border:none;border-radius:8px}
    .lightbox{display:none;position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.92);align-items:center;justify-content:center;cursor:zoom-out;flex-direction:column;gap:12px}
    .lightbox.open{display:flex}
    .lightbox img{max-width:95vw;max-height:88vh;object-fit:contain;border-radius:6px;box-shadow:0 4px 40px rgba(0,0,0,.6)}
    .lightbox-caption{color:rgba(255,255,255,.8);font-size:13px;text-align:center;max-width:80vw}
    .lightbox-close{position:fixed;top:16px;right:20px;color:#fff;font-size:28px;cursor:pointer;background:rgba(0,0,0,.5);border-radius:50%;width:40px;height:40px;display:flex;align-items:center;justify-content:center;line-height:1}
.decision-bar{position:fixed;bottom:0;left:0;right:0;background:#fff;
  border-top:2px solid #e8ecf4;padding:12px 24px;
  display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;
  box-shadow:0 -4px 16px rgba(0,0,0,.1);z-index:200}
</style>
</head>
<body>
"""
        + f"<div class='sticky-header'><div><h2>Case: {case_id}</h2>"
        + "<div class='sub' id='caseSubtitle'>Loading...</div></div>"
        + "<div id='downloadBtnWrap'></div></div>\n"
        + """
<div class="jump-nav">
  <a class="jump-link" href="#s-overview">Overview</a>
  <a class="jump-link" href="#s-interview">Interview</a>
  <a class="jump-link" href="#s-photos">Home Evidence</a>
  <a class="jump-link" href="#s-pan">PAN Verification</a>
  <a class="jump-link" href="#s-income">Income Analysis</a>
  <a class="jump-link" href="#s-location">Location</a>
  <a class="jump-link" href="#s-income">Income</a>
  <a class="jump-link" href="#s-cibil">CIBIL Score</a>
  <a class="jump-link" href="#s-credit">AI Credit</a>
  <a class="jump-link" href="#s-report">Report PDF</a>
  <a class="jump-link" href="#s-recording">Recording</a>
</div>
<div class="page-section">
  <div id="loadMsg" style="text-align:center;padding:60px 0;color:#888">
    <div class="spinner" style="width:32px;height:32px;border-width:4px;margin:0 auto 12px"></div>
    Loading...
  </div>
  <div id="allSecs" style="display:none">
    <div id="s-overview"></div><div id="s-interview"></div>
    <div id="s-photos"></div><div id="s-pan"></div>
    <div id="s-income"></div><div id="s-cibil"></div><div id="s-location"></div>
    <div id="s-credit"></div><div id="s-report"></div><div id="s-recording"></div>
  </div>
</div>
<div class="decision-bar">
  <div style="display:flex;align-items:center;gap:12px">
    <span style="font-size:14px;font-weight:600;color:#555">Decision:</span>
    <span id="curDecision"><em style="color:#888">Not reviewed</em></span>
  </div>
  <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
    <textarea id="decNotes" rows="1" class="form-control"
              style="width:260px;padding:6px 10px;font-size:13px;resize:none"
              placeholder="Optional notes..."></textarea>
    <button class="btn btn-success" onclick="decide('accepted')">Accept</button>
    <button class="btn btn-danger"  onclick="decide('rejected')">Reject</button>
  </div>
</div>
"""
        + _SCRIPT_COMMON
        + f"<script>\nconst CASE_ID={cid_js};\nlet D=null;\n"
        + """
function gc(n){return document.cookie.split(';').map(c=>c.trim()).find(c=>c.startsWith(n+'='))?.split('=')[1]||''}
function tryJ(s){try{return s?JSON.parse(s):null}catch{return null}}
function kv(k,v,f){return`<div class="kv-row"><span class="kv-key">${k}</span><span class="kv-val ${f?'inc':''}">${esc(v)}</span></div>`}
function inc(m){return`<div class="inc-notice">INCOMPLETE - ${esc(m)}</div>`}
function card(id,title,body){return`<div class="sec-card" id="${id}"><div class="sec-hdr">${title}</div><div class="sec-body">${body}</div></div>`}

async function load(){
  try{
    const r=await fetch(`/fi/auditor/api/cases/${CASE_ID}`,{headers:{'x-auditor-token':gc('auditor_token')}});
    if(r.status===401){location.href='/fi/auditor/';return}
    if(!r.ok) throw new Error('HTTP '+r.status);
    D=await r.json();renderAll();
  }catch(e){document.getElementById('loadMsg').innerHTML=`<p style="color:#C62828">Error: ${esc(e.message)}</p>`;}
}

function renderAll(){
  const sd=D.session_data||{}, meta=D.metadata||{};
  const bi=sd.basic_info||meta.basic_info||{};
  const name=[bi.first_name,bi.last_name].filter(Boolean).join(' ')||'—';
  document.getElementById('caseSubtitle').textContent=`${name}  |  ${fmtDate(meta.started_at)}`;
  if(D.report_url) document.getElementById('downloadBtnWrap').innerHTML=
    `<a href="${D.report_url}" target="_blank" download class="btn btn-gold">Download PDF</a>`;
  if(D.decision){
    const cls=D.decision==='accepted'?'badge-accepted':'badge-rejected';
    document.getElementById('curDecision').innerHTML=
      `<span class="badge ${cls}">${D.decision.toUpperCase()}</span>`+
      (D.decision_notes?`<span style="color:#888;font-size:13px;margin-left:8px">${esc(D.decision_notes)}</span>`:'');
  }
  const qs=sd.interview||meta.questions||[];
  const photos=sd.photos||meta.photos||[];
  const resp=D.responses||{};
  const panV=sd.pan_verification||tryJ(resp['pan_verification.json']);
  const incA=sd.income_document?.analysis||tryJ(resp['income_analysis.json']);
  const credA=sd.credit_analysis||D.credit_analysis||tryJ(resp['credit_analysis.json']);
  const geoR=sd.location||D.geo_result||{};

  document.getElementById('s-overview').innerHTML=bldOverview(D,bi,qs,photos,meta);
  document.getElementById('s-interview').innerHTML=bldInterview(qs);
  document.getElementById('s-photos').innerHTML=bldPhotos(photos,D.case_id);
  document.getElementById('s-pan').innerHTML=bldPan(panV,D.case_id);
  document.getElementById('s-income').innerHTML=bldIncome(incA);
  document.getElementById('s-cibil').innerHTML=bldCibil(sd.cibil_score||D.cibil_score);
  document.getElementById('s-location').innerHTML=bldLocation(geoR);
  document.getElementById('s-credit').innerHTML=bldCredit(credA);
  document.getElementById('s-report').innerHTML=bldReport(D.report_url);
  document.getElementById('s-recording').innerHTML=bldRecording(D,meta);
  document.getElementById('loadMsg').style.display='none';
  document.getElementById('allSecs').style.display='block';
}

function bldOverview(d,bi,qs,photos,meta){
  const ua=qs.filter(q=>!q.answer?.trim()).length;
  const selfie=photos.some(p=>p.is_selfie);
  const hasPan=!!(d.session_data?.pan_verification||d.responses?.['pan_verification.json']);
  const _incA=d.session_data?.income_document?.analysis;
  const hasInc=!!(_incA?.avg_monthly_income||_incA?.creditworthiness_score!=null||d.session_data?.income_document?.documents?.length);
  const pi=d.session_data?.property_info||d.property_info||{};
  const propTypeLabel={'flat':'Flat / Apartment','bungalow':'Bungalow / House'}[pi.property_type]||pi.property_type||'—';
  const hallLabel=pi.hall===0||pi.hall==='0'?'No':'Yes';
  return card('s-overview','Applicant & Session Overview',`
    <div class="two-col">
      <div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:8px">APPLICANT</div>
        ${kv('Full Name',[bi.first_name,bi.last_name].filter(Boolean).join(' ')||'—',false)}
        ${kv('Date of Birth',bi.dob||'—',!bi.dob)}
        ${kv('Address',bi.address||'—',!bi.address)}
        ${kv('City',bi.city||'—',!bi.city)}
        ${kv('PAN',bi.pan_number||'—',!bi.pan_number)}
        ${kv('Mobile',bi.mobile_number?'+91 '+bi.mobile_number:'—',!bi.mobile_number)}
        ${kv('Income',bi.income_range||'—',false)}
        ${pi.property_type?`
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin:10px 0 6px">PROPERTY INFO</div>
        ${kv('Type',propTypeLabel,false)}
        ${kv('Bedrooms',pi.bedrooms||'—',false)}
        ${kv('Hall / Living Room',hallLabel,false)}`:''}
      </div>
      <div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:8px">SESSION</div>
        ${kv('Case ID',d.case_id,false)}
        ${kv('Device ID',meta.device_id||'—',false)}
        ${kv('Started',fmtDate(meta.started_at),false)}
        ${kv('Ended',fmtDate(meta.ended_at),false)}
        ${kv('Recording',meta.recording_filename||'Not available',false)}
        ${(()=>{const di=(d.session_data&&d.session_data.session&&d.session_data.session.device_info)||{};
          return di.browser?`
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin:10px 0 6px">DEVICE</div>
        ${kv('Browser',di.browser||'—',false)}
        ${kv('OS / Platform',di.os||'—',false)}
        ${kv('Device Type',di.device_type||'—',false)}
        ${kv('Screen Size',di.screen_size||'—',false)}
        ${kv('Language',di.language||'—',false)}`:'';
        })()}
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin:12px 0 8px">COMPLETENESS</div>
        ${kv('Q&A',ua===0?`All ${qs.length} answered`:`${ua} unanswered`,ua>0)}
        ${kv('Selfie',selfie?'Captured':'INCOMPLETE',!selfie)}
        ${kv('PAN',hasPan?'Verified':'INCOMPLETE',!hasPan)}
        ${kv('Income',hasInc?'Analysed':'INCOMPLETE',!hasInc)}
        ${kv('Report',d.report_url?'Generated':'INCOMPLETE',!d.report_url)}
      </div>
    </div>`);
}

function bldInterview(qs){
  if(!qs.length) return card('s-interview','Field Interview',inc('No Q&A recorded'));
  const ua=qs.filter(q=>!q.answer?.trim()).length;
  const warn=ua?inc(`${ua} of ${qs.length} questions unanswered`):'';
  const rows=qs.map((q,i)=>{
    const ans=q.answer?.trim()||'<span class="inc">No answer</span>';
    const geo=q.geo?.latitude?`${q.geo.latitude.toFixed(5)}N ${q.geo.longitude.toFixed(5)}E`:'<span style="color:#999;font-size:11px">—</span>';
    return`<tr><td style="width:28px;color:#888;text-align:center">${i+1}</td><td>${esc(q.question)}</td><td>${ans}</td><td style="font-size:12px;color:#666">${geo}</td></tr>`;
  }).join('');
  return card('s-interview','Field Interview',warn+`
    <table class="itv-table"><thead><tr><th>#</th><th>Question</th><th>Answer</th><th>GPS</th></tr></thead>
    <tbody>${rows}</tbody></table>`);
}

function bldPhotos(photos,cid){
  const scene=photos.filter(p=>p.tag!=='pan');
  if(!scene.length) return card('s-photos','Home Evidence',inc('No home photos captured'));
  const cards=scene.map(p=>{
    const blur=p.blur_score?`Blur: ${Math.round(p.blur_score)}`:'';
    const geo=p.geo?.latitude?`GPS: ${p.geo.latitude.toFixed(5)}N ${p.geo.longitude.toFixed(5)}E`:'<span style="color:#999;font-size:11px">— GPS not captured</span>';
    return`<div class="card">
      <img src="/fi/storage/${cid}/${esc(p.filename)}" onerror="this.style.display='none'" alt="${esc(p.prompt)}" onclick="openLightbox('/fi/storage/${cid}/${esc(p.filename)}','${esc(p.tag||p.prompt)}')" style="width:100%;height:180px;object-fit:cover;border-radius:8px 8px 0 0;cursor:zoom-in">
      <div style="padding:10px 12px">
        <div class="photo-tag">${esc(p.tag||'photo')}</div>
        ${blur?`<span style="font-size:11px;color:#888;margin-left:6px">${blur}</span>`:''}
        <div style="font-size:12px;color:#555;margin-top:4px">${esc(p.prompt)}</div>
        <div style="font-size:11px;margin-top:3px">${geo}</div>
        ${p.nameplate_ocr?.raw_text?`<div style="background:#E8F5E9;padding:6px;border-radius:4px;font-size:12px;margin-top:6px"><strong>Nameplate:</strong> ${esc(p.nameplate_ocr.raw_text)}</div>`:''}
        ${p.analysis?`<div class="photo-analysis">${formatAnalysis(p.analysis)}</div>`:''}
      </div></div>`;
  }).join('');
  return card('s-photos','Home Evidence',`<div class="photo-grid">${cards}</div>`);
}

function bldPan(pv,cid){
  if(!pv) return card('s-pan','PAN Card Verification',inc('PAN card not captured'));
  const o=pv.ocr||{},nm=pv.name_match||{},tw=pv.three_way_match||{},n=pv.nsdl||{},fm=pv.face_match||{};
  const fmHtml=fm.error?inc('Face match: '+fm.error):
    (fm.similarity_score!=null?kv('Face Match',`${(fm.similarity_score||0).toFixed(1)}% - ${fm.comparison_status}`,!fm.matched):'');
  // PAN card photo
  const panImgHtml=pv.filename?`
    <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:14px">
      <div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:6px">PAN Card Photo</div>
        <img src="/fi/storage/${cid}/${esc(pv.filename)}"
             onerror="this.style.display='none'"
             onclick="openLightbox('/fi/storage/${cid}/${esc(pv.filename)}','PAN Card')"
             style="width:260px;height:160px;object-fit:contain;border:1px solid #DDE4F0;border-radius:8px;background:#F8F9FC;cursor:zoom-in">
      </div>
      ${pv.selfie_filename?`<div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:6px">Applicant Selfie</div>
        <img src="/fi/storage/${cid}/${esc(pv.selfie_filename)}"
             onerror="this.style.display='none'"
             onclick="openLightbox('/fi/storage/${cid}/${esc(pv.selfie_filename)}','Applicant Selfie')"
             style="width:140px;height:160px;object-fit:cover;border:1px solid #DDE4F0;border-radius:8px;background:#F8F9FC;cursor:zoom-in">
      </div>`:''}
    </div>`:'';
  return card('s-pan','PAN Card Verification',panImgHtml+`
    <div class="two-col">
      <div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:8px">OCR (AWS Textract)</div>
        ${kv('PAN Number',o.pan_number||'Not detected',!o.pan_number)}
        ${kv('Name',o.name||'Not detected',!o.name)}
        ${kv("Father Name",o.father_name||'Not detected',!o.father_name)}
        ${kv('DOB',o.dob||'Not detected',!o.dob)}
        ${fmHtml}
      </div>
      <div>
        <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:8px">NSDL Verification</div>
        ${kv('PAN Status',n.pan_status||'—',!n.verified)}
        ${kv('Name Match',n.name_match?'MATCHED':'NOT MATCHED',!n.name_match)}
        ${kv('Father Name',n.father_name_match?'MATCHED':'NOT MATCHED',!n.father_name_match)}
        ${kv('DOB Match',n.dob_match?'MATCHED':'NOT MATCHED',!n.dob_match)}
        ${kv('Aadhaar Seeded',n.aadhaar_seeded?'YES':'Not confirmed',false)}
      </div>
    </div>
    <div style="margin-top:14px">
      <div style="font-weight:700;color:#0D47A1;font-size:12px;margin-bottom:8px">3-WAY NAME MATCH</div>
      ${kv('Form First Name',tw.form_first_name||'—',!tw.form_first_name)}
      ${kv('PAN First Name',tw.pan_first_name||'—',!tw.pan_first_name)}
      ${kv('Nameplate First Name',tw.nameplate_first_name||'Not detected',!tw.nameplate_first_name)}
      ${kv('Form vs PAN',tw.form_vs_pan?'MATCHED':'NOT MATCHED',!tw.form_vs_pan)}
      ${kv('Overall',tw.all_match?'ALL NAMES MATCH':'DISCREPANCY DETECTED',!tw.all_match)}
    </div>`);
}

function bldIncome(ia){
  if(!ia) return card('s-income','Income & Financial Analysis',inc('Bank statement not uploaded'));
  if(ia.error) return card('s-income','Income & Financial Analysis',inc('Analysis failed: '+ia.error));
  function inr(v){try{return'Rs '+Number(v).toLocaleString('en-IN')}catch{return v||'—'}}
  function pct(v){try{return(Number(v)*100).toFixed(1)+'%'}catch{return v||'—'}}
  return card('s-income','Income & Financial Analysis',`
    <div class="two-col">
      <div>
        ${kv('Months Covered',String(ia.months_covered||'—'),false)}
        ${kv('Avg Monthly Income',inr(ia.avg_monthly_income),false)}
        ${kv('Avg Monthly Expenses',inr(ia.avg_monthly_expenses),false)}
        ${kv('Avg Monthly Savings',inr(ia.avg_monthly_savings),false)}
        ${kv('Expense Ratio',pct(ia.expense_to_income_ratio),false)}
      </div>
      <div>
        ${kv('Salary Detected',ia.salary_detected?'YES':'NO',!ia.salary_detected)}
        ${kv('EMI Payments',String(ia.emi_count||0),false)}
        ${kv('Bounced Transactions',String(ia.bounce_count||0),ia.bounce_count>0)}
        ${kv('Creditworthiness',(ia.creditworthiness_score||0)+' / 10',false)}
      </div>
    </div>
    ${ia.summary?`<div style="margin-top:12px;background:#F0F4FF;border-radius:8px;padding:12px;font-size:14px"><strong>AI Summary:</strong> ${esc(ia.summary)}</div>`:''}
    ${(ia.risk_flags?.length||ia.positive_indicators?.length)?`<div class="two-col" style="margin-top:12px">
      <div><div style="font-weight:700;font-size:12px;color:#C62828;margin-bottom:6px">RISK FLAGS</div>
        ${(ia.risk_flags||[]).map(f=>`<div style="font-size:13px;color:#C62828">x ${esc(f)}</div>`).join('')||'<div style="color:#888">None</div>'}
      </div>
      <div><div style="font-weight:700;font-size:12px;color:#2E7D32;margin-bottom:6px">POSITIVE</div>
        ${(ia.positive_indicators||[]).map(f=>`<div style="font-size:13px;color:#2E7D32">+ ${esc(f)}</div>`).join('')||'<div style="color:#888">None</div>'}
      </div>
    </div>`:''}`);
}

function bldCibil(c){
  if(!c||!c.score) return card('s-cibil','CIBIL Credit Score',inc('CIBIL score not available'));
  const score=c.score||0;
  const grade=c.grade||'';
  const label=c.label||'';
  const color=c.color||'#555';
  const threshold=c.cibil_threshold||800;
  const eligible=c.loan_eligible;
  const recText=c.recommendation||'';
  const eligibleBadge=eligible
    ?'<span style="background:#E8F5E9;color:#1B5E20;border:1px solid #A5D6A7;border-radius:10px;padding:3px 12px;font-size:12px;font-weight:700">Loan Eligible</span>'
    :'<span style="background:#FFEBEE;color:#C62828;border:1px solid #EF9A9A;border-radius:10px;padding:3px 12px;font-size:12px;font-weight:700">Not Eligible</span>';
  return card('s-cibil','CIBIL Credit Score (TransUnion CIBIL)',`
    <div style="text-align:center;padding:20px 0;border-bottom:1px solid #eef0f5;margin-bottom:16px">
      <div style="font-size:52px;font-weight:900;color:${color};line-height:1">${score}</div>
      <div style="font-size:13px;color:#888;margin:4px 0">Credit Score / 900</div>
      <div style="font-size:18px;font-weight:700;color:${color};margin:6px 0">${esc(label)}  —  ${esc(grade)}</div>
      <div style="margin:10px 0">${eligibleBadge}</div>
      <div style="font-size:13px;color:#555;margin-top:6px">${esc(recText)}</div>
      <div style="font-size:12px;color:#888;margin-top:4px">Threshold: ${threshold}+ considered Good</div>
    </div>
    ${kv('CIBIL Score',String(score),false)}
    ${kv('Grade',grade+' — '+label,false)}
    ${kv('Eligible',eligible?'YES':'NO',!eligible)}
    ${kv('Threshold',String(threshold),false)}
    ${kv('PAN Number',c.pan_number||'—',false)}
    ${kv('Bureau',c.bureau||'TransUnion CIBIL',false)}
    ${kv('Report Date',c.report_date||'—',false)}`);
}
function bldLocation(g){
  if(!g||!g.points_checked) return card('s-location','Location Report',inc('No GPS data captured'));
  const ok=g.status==='PASS'||g.verified;
  const spread=g.max_pairwise_m||g.max_pairwise_distance_m||0;

  // City match banner
  const cm=g.city_match;
  let cityHtml='';
  if(cm){
    const cok=cm.matched;
    cityHtml=`<div style="background:${cok?'#E8F5E9':'#FFEBEE'};border:1.5px solid ${cok?'#2E7D32':'#C62828'};
         border-radius:8px;padding:10px 16px;margin-bottom:10px;display:flex;align-items:flex-start;gap:12px">
      <span style="font-size:20px;margin-top:1px">${cok?'✓':'✗'}</span>
      <div>
        <div style="font-weight:700;color:${cok?'#1B5E20':'#C62828'};font-size:13px">
          City Match: ${cok?'PASS — city confirmed in GPS address':'FAIL — declared city not found in GPS address'}
        </div>
        <div style="font-size:12px;color:#555;margin-top:3px">
          Declared city: <strong>${esc(cm.declared_city)}</strong>
        </div>
        <div style="font-size:12px;color:#555;margin-top:2px">
          Google Maps: ${esc(cm.google_address)}
        </div>
      </div>
    </div>`;
  }

  const rows=(g.details||[]).map(p=>{
    const w=p.within_radius;
    return`<tr style="background:${w?'#E8F5E9':'#FFF3E0'}">
      <td>${esc(p.label||'')}</td><td>${(p.latitude||0).toFixed(5)}</td>
      <td>${(p.longitude||0).toFixed(5)}</td>
      <td>${esc((p.timestamp||'').slice(0,19).replace('T',' '))}</td>
      <td style="text-align:center">${Math.round(p.distance_from_centroid_m||0)} m</td>
      <td style="text-align:center;font-weight:700;color:${w?'#2E7D32':'#C62828'}">${w?'OK':'FAIL'}</td>
    </tr>`;
  }).join('');
  return card('s-location','Location Report',
    `<div style="background:${ok?'#E8F5E9':'#FFF3E0'};border:1.5px solid ${ok?'#2E7D32':'#E65100'};border-radius:8px;padding:12px 16px;margin-bottom:12px;font-weight:700;color:${ok?'#1B5E20':'#E65100'}">
      ${ok?'LOCATION VERIFIED':'LOCATION FAILED'} — Max spread: ${Math.round(spread)} m (threshold 500 m)
    </div>`+
    cityHtml+
    kv('Centroid',`${(g.centroid_lat||0).toFixed(5)}N  ${(g.centroid_lon||0).toFixed(5)}E`,false)+
    kv('Points Checked',String(g.points_checked||0),false)+
    (rows?`<div style="overflow-x:auto;margin-top:12px"><table style="width:100%;border-collapse:collapse;font-size:13px">
      <thead style="background:#0D47A1;color:#fff">
        <tr><th style="padding:8px">Event</th><th>Lat</th><th>Lon</th><th>Time</th><th>Dist</th><th>Status</th></tr>
      </thead><tbody>${rows}</tbody></table></div>`:''));
}

function bldCredit(ca){
  if(!ca) return card('s-credit','AI Credit Analysis',inc('AI analysis not performed'));
  if(ca.error) return card('s-credit','AI Credit Analysis',inc('Failed: '+ca.error));
  const rcol={APPROVE:'#1B5E20',APPROVE_WITH_CONDITIONS:'#1565C0',REFER:'#E65100',DECLINE:'#880E4F'}[ca.recommendation]||'#555';
  return card('s-credit','AI Credit Analysis',`
    <div style="text-align:center;padding:20px 0;border-bottom:1px solid #eef0f5;margin-bottom:16px">
      <div class="score-big">${ca.overall_credit_score||0}</div>
      <div style="font-size:13px;color:#888">Credit Score / 100</div>
      <div style="font-size:18px;font-weight:700;color:#0D47A1;margin-top:6px">${esc(ca.risk_grade||'')}</div>
      <div style="font-size:18px;font-weight:800;color:${rcol};margin-top:4px">${esc(ca.recommendation||'')}</div>
      ${ca.loan_eligibility_inr?`<div style="font-size:14px;color:#555;margin-top:6px">Eligibility: <strong>Rs ${Number(ca.loan_eligibility_inr).toLocaleString('en-IN')}</strong></div>`:''}
    </div>
    ${ca.executive_summary?`<div style="background:#F0F4FF;border-radius:8px;padding:14px;font-size:14px;margin-bottom:16px">${esc(ca.executive_summary)}</div>`:''}
    <div class="two-col">
      ${['identity_assessment','residence_assessment','income_assessment','location_assessment'].map(k=>{
        const p=ca[k]||{};
        return`<div style="background:#F7F9FF;border-radius:8px;padding:14px">
          <div style="font-weight:700;font-size:13px;color:#0D47A1;margin-bottom:6px">${k.replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase())} (${p.score||0}/25)</div>
          <div style="font-size:13px;color:#555">${esc(p.summary||'—')}</div>
          ${(p.flags||[]).map(f=>`<div style="font-size:12px;color:#C62828;margin-top:3px">x ${esc(f)}</div>`).join('')}
        </div>`;
      }).join('')}
    </div>
    <div class="two-col" style="margin-top:12px">
      <div><div style="font-weight:700;font-size:12px;color:#2E7D32;margin-bottom:6px">POSITIVE</div>
        ${(ca.positive_factors||[]).map(f=>`<div style="font-size:13px;color:#2E7D32">+ ${esc(f)}</div>`).join('')||'<div style="color:#888">None</div>'}
      </div>
      <div><div style="font-weight:700;font-size:12px;color:#C62828;margin-bottom:6px">RISKS</div>
        ${(ca.risk_factors||[]).map(f=>`<div style="font-size:13px;color:#C62828">x ${esc(f)}</div>`).join('')||'<div style="color:#888">None</div>'}
      </div>
    </div>`);
}

function formatAnalysis(text){
  if(!text) return '';
  const lines = text.replace(new RegExp(String.fromCharCode(13),'g'),'').split(String.fromCharCode(10));
  return lines.map(raw=>{
    const line = raw.trim();
    if(!line) return '';
    const hdr = line.match(/^\*\*(.+?)\*\*[:\-]?\s*(.*)/);
    if(hdr){
      const k=hdr[1].replace(/\*+/g,'').trim();
      const v=hdr[2].trim();
      return `<div style="margin-top:5px"><span style="font-weight:700;color:#0D47A1">${esc(k)}:</span>${v?' '+esc(v):''}</div>`;
    }
    if(line.match(/^[-•*] /)){
      const body=line.slice(2).trim();
      if(body.includes(':')&&body.split(':')[0].length<20){
        const idx2=body.indexOf(':');
        const lbl=body.slice(0,idx2),rest=body.slice(idx2+1).trim();
        return `<div style="padding-left:10px;margin:1px 0">&bull; <strong>${esc(lbl.trim())}:</strong> ${esc(rest)}</div>`;
      }
      return `<div style="padding-left:10px;margin:1px 0">&bull; ${esc(body)}</div>`;
    }
    if(/score|assessment/i.test(line)){
      return `<div style="margin-top:5px;font-weight:700;color:#333">${esc(line.replace(/\*+/g,'').trim())}</div>`;
    }
    const clean=line.replace(/\*+/g,'').trim();
    return clean?`<div style="margin:1px 0">${esc(clean)}</div>`:'';
  }).join('');
}
function bldRecording(d,meta){
  // Find recording filename from metadata or files list
  const recName = (meta.recording_filename) ||
    (d.session_data&&d.session_data.session&&d.session_data.session.recording) ||
    (d.files||[]).find(f=>f.endsWith('.webm')||f.endsWith('.mp4')||f.endsWith('.ogg')) || '';
  if(!recName) return card('s-recording','Session Recording',inc('No recording found for this session'));
  const recUrl = `/fi/storage/${d.case_id}/${recName}`;
  return card('s-recording','Session Recording',`
    <div style="margin-bottom:10px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
      <span style="font-size:13px;color:#555">${esc(recName)}</span>
      <a href="${recUrl}" download class="btn btn-gold btn-sm">Download Recording</a>
    </div>
    <video controls preload="metadata"
           style="width:100%;border-radius:8px;background:#000;max-height:480px;display:block">
      <source src="${recUrl}" type="video/webm">
      <source src="${recUrl}" type="video/mp4">
      Your browser does not support the video element.
    </video>
    <div style="font-size:12px;color:#888;margin-top:6px">
      Full session video+audio recording. Use the controls to play, pause, and seek.
    </div>`);
}
function bldReport(url){
  if(!url) return card('s-report','Report PDF',inc('PDF not yet generated'));
  return card('s-report','Report PDF',`
    <div style="margin-bottom:10px;display:flex;justify-content:flex-end">
      <a href="${url}" download class="btn btn-gold">Download PDF</a>
    </div>
    <iframe class="pdf-frame" src="${url}"></iframe>`);
}

async function decide(decision){
  const notes=document.getElementById('decNotes').value.trim();
  const auditor=localStorage.getItem('auditor_username')||'auditor';
  try{
    const r=await fetch(`/fi/auditor/api/cases/${CASE_ID}/decision`,{
      method:'POST',
      headers:{'Content-Type':'application/json','x-auditor-token':gc('auditor_token')},
      body:JSON.stringify({decision,notes,auditor_name:auditor}),
    });
    if(!r.ok) throw new Error('HTTP '+r.status);
    const cls=decision==='accepted'?'badge-accepted':'badge-rejected';
    document.getElementById('curDecision').innerHTML=
      `<span class="badge ${cls}">${decision.toUpperCase()}</span>`+
      (notes?`<span style="color:#888;font-size:13px;margin-left:8px">${esc(notes)}</span>`:'');
    alert(`Marked as ${decision.toUpperCase()} by ${auditor}.`);
  }catch(e){alert('Error: '+e.message);}
}

load();
function openLightbox(url,caption){document.getElementById('lightboxImg').src=url;document.getElementById('lightboxCaption').textContent=caption||'';document.getElementById('lightbox').classList.add('open');}
function closeLightbox(){document.getElementById('lightbox').classList.remove('open');document.getElementById('lightboxImg').src='';}
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeLightbox();});
</script>
</body>
</html>"""
    )


# ══════════════════════════════════════════════════════════════════════════════
#  API DATA HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _read_json(path: Path) -> Optional[Dict]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("[Auditor] Cannot parse %s: %s", path, exc)
    return None


def _case_summary(folder: Path) -> Dict[str, Any]:
    case_id    = folder.name
    meta       = _read_json(folder / "metadata.json") or {}
    session_data = _read_json(folder / "session_data.json") or {}
    decision_d = _read_json(folder / "decision.json") or {}

    bi = session_data.get("basic_info") or meta.get("basic_info") or {}
    questions = session_data.get("interview") or meta.get("questions") or []
    photos    = session_data.get("photos")   or meta.get("photos")   or []

    customer_name = (
        f"{bi.get('first_name','')} {bi.get('last_name','')}".strip()
        or _extract_name_from_qa(questions)
    )

    has_answers   = any(q.get("answer", "").strip() for q in questions)
    has_photos    = len([p for p in photos if not p.get("is_pan")]) > 0
    has_report    = any(f.suffix == ".pdf" for f in folder.iterdir() if f.is_file())
    has_pan       = (folder / "responses" / "pan_verification.json").exists()
    is_complete   = has_answers and has_photos and has_report

    report_file  = next((f.name for f in folder.iterdir()
                         if f.is_file() and f.name.startswith("fi_report_") and f.suffix == ".pdf"), None)

    return {
        "case_id":        case_id,
        "started_at":     meta.get("started_at") or session_data.get("session", {}).get("started_at"),
        "customer_name":  customer_name or "—",
        "pan_number":     bi.get("pan_number") or "",
        "mobile_number":  bi.get("mobile_number") or "",
        "is_complete":    is_complete,
        "has_report":     has_report,
        "report_url":     f"/fi/storage/{case_id}/{report_file}" if report_file else None,
        "decision":       decision_d.get("decision"),
        "decision_notes": decision_d.get("notes"),
        "decided_by":     decision_d.get("decided_by"),
        "decided_at":     decision_d.get("decided_at"),
    }


def _extract_name_from_qa(questions: List[Dict]) -> str:
    for q in questions:
        if any(kw in (q.get("question") or "").lower()
               for kw in ("name", "full name", "applicant")):
            return (q.get("answer") or "").strip()
    return ""


# ══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def auditor_root(request: Request) -> str:
    if _check_token(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/fi/auditor/cases")
    return _LOGIN_HTML


@router.get("/cases", response_class=HTMLResponse, include_in_schema=False)
async def auditor_cases_page(request: Request) -> str:
    if not _check_token(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/fi/auditor/")
    return _CASE_LIST_HTML


@router.get("/cases/{case_id}", response_class=HTMLResponse, include_in_schema=False)
async def auditor_case_detail_page(case_id: str, request: Request) -> str:
    if not _check_token(request):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/fi/auditor/")
    return _case_detail_html(case_id)


# ── JSON APIs ─────────────────────────────────────────────────────────────────

@router.post("/api/login")
async def api_login(body: Dict[str, str]) -> Dict:
    username = body.get("username", "")
    password = body.get("password", "")
    if _CREDENTIALS.get(username) == password:
        return {"token": _VALID_TOKEN, "username": username}
    raise HTTPException(status_code=401, detail="Invalid credentials")


@router.get("/api/cases")
async def api_list_cases(request: Request) -> List[Dict[str, Any]]:
    if not _check_token(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
    root   = get_storage_root()
    result = []
    for folder in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if folder.is_dir():
            try:
                result.append(_case_summary(folder))
            except Exception as exc:
                logger.warning("[Auditor] Error summarising %s: %s", folder.name, exc)
    return result


@router.get("/api/cases/{case_id}")
async def api_case_detail(case_id: str, request: Request) -> Dict[str, Any]:
    if not _check_token(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    folder = get_storage_root() / case_id
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    meta         = _read_json(folder / "metadata.json") or {}
    session_data = _read_json(folder / "session_data.json") or {}
    decision_d   = _read_json(folder / "decision.json") or {}

    responses: Dict[str, str] = {}
    geo_result      = None
    credit_analysis = None
    cibil_score     = None
    resp_dir = folder / "responses"
    if resp_dir.exists():
        for rf in resp_dir.iterdir():
            if rf.is_file():
                try:
                    content = rf.read_text(encoding="utf-8")
                    responses[rf.name] = content
                    if rf.name == "geo_verification.json":
                        geo_result = json.loads(content)
                    elif rf.name == "credit_analysis.json":
                        credit_analysis = json.loads(content)
                    elif rf.name == "cibil_score.json":
                        cibil_score = json.loads(content)
                except Exception:
                    pass

    files = sorted(f.name for f in folder.iterdir()
                   if f.is_file() and f.name not in ("metadata.json", "decision.json", "session_data.json"))

    report_file = next((f for f in files if f.startswith("fi_report_") and f.endswith(".pdf")), None)

    # Enrich photos with their analyses
    photos = (session_data.get("photos") or meta.get("photos") or [])
    for i, ph in enumerate(photos):
        key = f"photo_{i}_analysis.txt"
        if key in responses:
            ph["analysis"] = responses[key]

    if session_data:
        session_data["photos"] = photos

    # credit_analysis and cibil_score: prefer session_data, fall back to parsed JSON
    if not session_data.get("credit_analysis") and credit_analysis:
        session_data["credit_analysis"] = credit_analysis
    if not session_data.get("cibil_score") and cibil_score:
        session_data["cibil_score"] = cibil_score

    # Inject selfie filename into pan_verification so the auditor can show both photos
    pan_v = session_data.get("pan_verification") or {}
    if pan_v and not pan_v.get("selfie_filename"):
        selfie = next((p for p in photos if p.get("is_selfie")), None)
        if selfie:
            pan_v["selfie_filename"] = selfie.get("filename", "")
            session_data["pan_verification"] = pan_v

    return {
        "case_id":          case_id,
        "metadata":         meta,
        "session_data":     session_data,
        "files":            files,
        "responses":        {k: v for k, v in responses.items()
                             if k not in ("pan_verification.json", "income_analysis.json",
                                          "credit_analysis.json", "geo_verification.json")},
        "geo_result":       geo_result,
        "credit_analysis":  credit_analysis,
        "report_url":       f"/fi/storage/{case_id}/{report_file}" if report_file else None,
        "report_filename":  report_file,
        "decision":         decision_d.get("decision"),
        "decision_notes":   decision_d.get("notes"),
    }


@router.post("/api/cases/{case_id}/decision")
async def api_save_decision(case_id: str, body: Dict[str, str], request: Request) -> Dict:
    if not _check_token(request):
        raise HTTPException(status_code=401, detail="Unauthorized")

    folder = get_storage_root() / case_id
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    decision = body.get("decision", "").lower()
    if decision not in ("accepted", "rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'accepted' or 'rejected'")

    payload = {
        "decision":   decision,
        "notes":      body.get("notes", ""),
        "decided_at": datetime.now(timezone.utc).isoformat(),
        "decided_by": body.get("auditor_name", "auditor"),
    }
    (folder / "decision.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    logger.info("[Auditor] Decision saved: case=%s  decision=%s", case_id, decision)
    return {"status": "ok", "case_id": case_id, "decision": decision}
