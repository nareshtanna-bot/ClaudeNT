/* ── Travel Intelligence Dashboard ─────────────────────────── */

if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}

/* ── State ──────────────────────────────────────────────────── */
let trips           = [];
let projects        = [];
let family          = [];
let emailLog        = {};
let currentTripIdx  = -1;
let streaming       = false;
let activeES        = null;
let rawMd           = '';
let importCandidates = [];

/* ── DOM ────────────────────────────────────────────────────── */
const $ = id => document.getElementById(id);

/* ── Utility ────────────────────────────────────────────────── */
async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const e = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(e.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function esc(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function fmtDate(d) {
  if (!d) return '';
  const [y,m,day] = d.split('-');
  return `${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][+m-1]} ${+day}, ${y}`;
}

function fmtMoney(n) {
  if (n === null || n === undefined) return '—';
  return '$' + Number(n).toLocaleString('en-US');
}

function showToast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  $('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0,0,0,0);
  const d     = new Date(dateStr + 'T00:00:00');
  return Math.round((d - today) / 86400000);
}

/* ── Health ─────────────────────────────────────────────────── */
async function checkHealth() {
  try {
    const d = await api('GET', '/api/health');
    const dot  = $('status-dot');
    const text = $('status-text');
    if (d.api_key_configured) {
      dot.className = 'status-dot ok';
      text.textContent = 'API ready';
    } else {
      dot.className = 'status-dot err';
      text.textContent = 'No API key';
    }
    if (d.google_connected) {
      $('google-disconnected').style.display = 'none';
      $('google-connected').style.display    = '';
      $('google-setup-section').style.display = 'none';
    } else {
      $('google-disconnected').style.display = '';
      $('google-connected').style.display    = 'none';
      $('google-setup-section').style.display = d.google_credentials_present ? 'none' : '';
    }
  } catch {
    $('status-dot').className   = 'status-dot err';
    $('status-text').textContent = 'Offline';
  }
}

/* ── Tabs ───────────────────────────────────────────────────── */
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
  });
});

/* ── Modal helpers ──────────────────────────────────────────── */
function openModal(id)  { $(id).classList.add('open'); }
function closeModal(id) { $(id).classList.remove('open'); }

document.querySelectorAll('[data-close]').forEach(btn => {
  btn.addEventListener('click', () => closeModal(btn.dataset.close));
});
document.querySelectorAll('.modal-backdrop').forEach(bd => {
  bd.addEventListener('click', e => { if (e.target === bd) closeModal(bd.id); });
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape')
    document.querySelectorAll('.modal-backdrop.open').forEach(bd => closeModal(bd.id));
});

/* ══════════════════════════════════════════════════════════════
   TRIP HERO — auto-selects the next upcoming trip
══════════════════════════════════════════════════════════════ */

function sortedUpcoming() {
  const today = new Date().toISOString().slice(0,10);
  return [...trips].sort((a,b) => a.start_date.localeCompare(b.start_date));
}

function autoSelectNextTrip() {
  if (!trips.length) { currentTripIdx = -1; renderHero(); return; }
  const today  = new Date().toISOString().slice(0,10);
  const sorted = sortedUpcoming();
  // Prefer trips that haven't ended yet
  let idx = sorted.findIndex(t => t.end_date >= today);
  if (idx === -1) idx = sorted.length - 1;  // fall back to last trip
  currentTripIdx = idx;
  renderHero();
  autoLoadRecs();
}

async function renderHero() {
  const sorted = sortedUpcoming();

  $('prev-trip-btn').disabled = currentTripIdx <= 0;
  $('next-trip-btn').disabled = currentTripIdx < 0 || currentTripIdx >= sorted.length - 1;

  if (currentTripIdx < 0 || !sorted.length) {
    $('hero-city').textContent    = 'Your Next Trip';
    $('hero-country').textContent = 'Add trips in the sidebar to get started';
    $('hero-info').style.display    = 'none';
    $('hero-actions').style.display = 'none';
    $('output-wrap').style.display  = 'none';
    $('agent-error').style.display  = 'none';
    return;
  }

  const trip    = sorted[currentTripIdx];
  const days    = daysUntil(trip.start_date);
  const daysEnd = daysUntil(trip.end_date);

  $('hero-city').textContent    = trip.city;
  $('hero-country').textContent = trip.country;
  $('hero-dates').textContent   = `${fmtDate(trip.start_date)} – ${fmtDate(trip.end_date)}`;

  // Countdown pill
  const cdEl = $('hero-countdown');
  if (days > 0) {
    cdEl.className   = 'hero-pill pill-upcoming';
    cdEl.textContent = `${days} day${days !== 1 ? 's' : ''} away`;
  } else if (daysEnd >= 0) {
    cdEl.className   = 'hero-pill pill-now';
    cdEl.textContent = 'In progress';
  } else {
    cdEl.className   = 'hero-pill pill-past';
    cdEl.textContent = 'Past';
  }

  $('hero-info').style.display    = 'flex';
  $('hero-actions').style.display = 'flex';
  $('get-recs-btn').disabled      = false;

  // Rec cache status
  try {
    const s = await api('GET', `/api/recommendations/${trip.id}/status`);
    const recBadge = $('hero-rec-badge');
    if (s.has_cache) {
      recBadge.className   = `hero-pill ${s.needs_refresh ? 'pill-stale' : 'pill-fresh'}`;
      recBadge.textContent = s.needs_refresh
        ? `⚠ Recs ${s.age_days}d old`
        : `✓ Recs ${s.age_days === 0 ? 'fresh' : s.age_days + 'd ago'}`;
      $('force-refresh-btn').style.display = '';
      const meta = $('rec-meta');
      meta.className   = `rec-meta ${s.needs_refresh ? 'stale' : 'fresh'}`;
      meta.textContent = s.needs_refresh
        ? `⚠ Recommendations are ${s.age_days} days old`
        : `✓ Refreshed ${s.age_days === 0 ? 'today' : s.age_days + 'd ago'}`;
      meta.style.display = 'flex';
    } else {
      $('hero-rec-badge').textContent = '';
      $('hero-rec-badge').className   = '';
      $('rec-meta').style.display     = 'none';
      $('force-refresh-btn').style.display = 'none';
    }
  } catch { /* ignore */ }

  // Email log status
  const emailBadge = $('hero-email-badge');
  if (emailLog[trip.id]) {
    const sentDate = new Date(emailLog[trip.id]);
    const daysAgo  = Math.floor((Date.now() - sentDate) / 86400000);
    emailBadge.className   = 'hero-pill pill-email';
    emailBadge.textContent = `✉ Brief sent${daysAgo === 0 ? ' today' : ` ${daysAgo}d ago`}`;
  } else if (days !== null && days > 0 && days <= 8) {
    emailBadge.className   = 'hero-pill pill-email-soon';
    emailBadge.textContent = '✉ Brief sends in ' + (days - 7 <= 0 ? 'soon' : `${days - 7}d`);
  } else {
    emailBadge.textContent = '';
    emailBadge.className   = '';
  }

  // Show send brief button if Google is connected
  const googleConnected = $('google-connected').style.display !== 'none';
  $('send-brief-btn').style.display = googleConnected ? '' : 'none';
}

async function autoLoadRecs() {
  const sorted = sortedUpcoming();
  if (currentTripIdx < 0 || !sorted.length) return;
  const trip = sorted[currentTripIdx];

  try {
    const s = await api('GET', `/api/recommendations/${trip.id}/status`);
    if (s.has_cache && !s.needs_refresh) {
      // Cache is fresh — stream it immediately
      getRecommendations(false);
    }
  } catch { /* ignore */ }
}

/* ── Trip navigation ────────────────────────────────────────── */
$('prev-trip-btn').addEventListener('click', () => {
  if (currentTripIdx > 0) {
    currentTripIdx--;
    clearOutput();
    renderHero();
    autoLoadRecs();
  }
});

$('next-trip-btn').addEventListener('click', () => {
  const sorted = sortedUpcoming();
  if (currentTripIdx < sorted.length - 1) {
    currentTripIdx++;
    clearOutput();
    renderHero();
    autoLoadRecs();
  }
});

function clearOutput() {
  if (activeES) { activeES.close(); activeES = null; }
  streaming = false;
  rawMd = '';
  $('output-wrap').style.display  = 'none';
  $('agent-error').style.display  = 'none';
  $('copy-btn').style.display     = 'none';
  $('btn-icon').textContent        = '🔍';
  $('btn-label').textContent       = 'Find Restaurants';
  $('thinking-dots').classList.remove('active');
}

/* ══════════════════════════════════════════════════════════════
   TRAVEL SCHEDULE SIDEBAR
══════════════════════════════════════════════════════════════ */

function tripStatus(trip) {
  const today = new Date().toISOString().slice(0,10);
  if (today >= trip.start_date && today <= trip.end_date) return { label:'Now',      cls:'now' };
  if (trip.start_date > today)                            return { label:'Upcoming', cls:'upcoming' };
  return                                                         { label:'Past',     cls:'past' };
}

function renderTripList() {
  const list = $('trip-list');
  list.innerHTML = '';

  if (!trips.length) {
    list.innerHTML = `
      <div class="trip-list-empty">
        <span class="icon">✈️</span>No trips yet — add one!
      </div>`;
    return;
  }

  sortedUpcoming().forEach((trip, idx) => {
    const { label, cls } = tripStatus(trip);
    const isSelected     = idx === currentTripIdx;

    const card = document.createElement('div');
    card.className = `trip-card${isSelected ? ' selected' : ''}`;
    card.dataset.idx = idx;

    const emailSent = emailLog[trip.id]
      ? `<span class="rec-age fresh" style="margin-top:2px;">✉ Brief sent</span>` : '';

    card.innerHTML = `
      <div class="trip-card-city">${esc(trip.city)}</div>
      <div class="trip-card-country">${esc(trip.country)}</div>
      <div class="trip-card-dates">${fmtDate(trip.start_date)} – ${fmtDate(trip.end_date)}</div>
      <span class="trip-badge ${cls}">${label}</span>
      <div class="rec-age" id="rec-age-${trip.id}"></div>
      ${emailSent}
      <button class="trip-card-del" data-id="${trip.id}" title="Remove">✕</button>
    `;
    list.appendChild(card);

    // Async rec age badge
    api('GET', `/api/recommendations/${trip.id}/status`).then(s => {
      const el = $(`rec-age-${trip.id}`);
      if (el && s.has_cache) {
        el.className = `rec-age ${s.needs_refresh ? 'stale' : 'fresh'}`;
        el.textContent = s.needs_refresh
          ? `⚠ Recs ${s.age_days}d old`
          : `✓ Recs ${s.age_days}d ago`;
      }
    }).catch(() => {});
  });
}

async function loadSchedule() {
  try {
    trips = await api('GET', '/api/schedule');
    renderTripList();
  } catch {
    showToast('Could not load schedule', 'error');
  }
}

async function saveTrip() {
  const city    = $('trip-city').value.trim();
  const country = $('trip-country').value.trim();
  const start   = $('trip-start').value;
  const end     = $('trip-end').value;
  const notes   = $('trip-notes').value.trim();

  if (!city || !country || !start || !end) { showToast('Fill in all required fields', 'error'); return; }
  if (start > end)                          { showToast('Departure must be after arrival', 'error'); return; }

  try {
    $('trip-save-btn').disabled = true;
    const trip = await api('POST', '/api/schedule', { city, country, start_date: start, end_date: end, notes });
    trips.push(trip);
    renderTripList();
    closeModal('add-trip-modal');
    showToast(`${city} added ✓`, 'success');
    $('add-trip-form').reset();
    // If no trip was selected, auto-select this one
    if (currentTripIdx === -1) autoSelectNextTrip();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    $('trip-save-btn').disabled = false;
  }
}

async function deleteTrip(id) {
  try {
    await api('DELETE', `/api/schedule/${id}`);
    trips = trips.filter(t => t.id !== id);
    renderTripList();
    showToast('Trip removed', 'success');
    clearOutput();
    autoSelectNextTrip();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

$('add-trip-btn').addEventListener('click', () => {
  $('add-trip-form').reset();
  openModal('add-trip-modal');
  setTimeout(() => $('trip-city').focus(), 80);
});
$('trip-save-btn').addEventListener('click', saveTrip);

$('trip-list').addEventListener('click', e => {
  const del  = e.target.closest('.trip-card-del');
  const card = e.target.closest('.trip-card');
  if (del)  { e.stopPropagation(); deleteTrip(del.dataset.id); return; }
  if (card) {
    currentTripIdx = +card.dataset.idx;
    clearOutput();
    renderTripList();
    renderHero();
    autoLoadRecs();
  }
});

/* ══════════════════════════════════════════════════════════════
   RESTAURANT AGENT
══════════════════════════════════════════════════════════════ */

function currentTrip() {
  return sortedUpcoming()[currentTripIdx] || null;
}

function setStreaming(active) {
  streaming = active;
  $('get-recs-btn').disabled = active;
  $('btn-icon').textContent  = active ? '⏳' : '🔍';
  $('btn-label').textContent = active ? 'Searching…' : 'Find Restaurants';
  $('thinking-dots').classList.toggle('active', active);
  $('output-status').textContent = active ? 'Agent searching Yelp, Google, OpenTable…' : 'Results';
  if (!active) $('copy-btn').style.display = 'block';
}

async function getRecommendations(force = false) {
  const trip = currentTrip();
  if (!trip || streaming) return;

  rawMd = '';
  $('agent-error').style.display   = 'none';
  $('agent-output').className      = 'agent-output';
  $('agent-output').innerHTML      = '';
  $('output-wrap').style.display   = 'block';
  $('copy-btn').style.display      = 'none';
  setStreaming(true);

  if (activeES) { activeES.close(); activeES = null; }

  const url = `/api/recommendations/stream?trip_id=${encodeURIComponent(trip.id)}${force ? '&force=true' : ''}`;
  const es  = new EventSource(url);
  activeES  = es;

  es.onmessage = e => {
    const data = JSON.parse(e.data);

    if (data.error) {
      $('agent-error').innerHTML = `<div class="agent-error"><strong>⚠ Error</strong> ${esc(data.error)}</div>`;
      $('agent-error').style.display = '';
      es.close(); setStreaming(false); return;
    }

    if (data.done) {
      $('agent-output').classList.remove('streaming-cursor');
      $('agent-output').innerHTML = marked.parse(rawMd);
      es.close(); setStreaming(false);

      if (data.refreshed_at) {
        const meta = $('rec-meta');
        meta.className   = 'rec-meta fresh';
        meta.textContent = `✓ Just refreshed${data.cached ? ' (from cache)' : ''}`;
        meta.style.display = 'flex';
        $('force-refresh-btn').style.display = '';
        renderTripList();
        renderHero();
      }
      return;
    }

    if (data.text) {
      rawMd += data.text;
      $('agent-output').innerHTML = marked.parse(rawMd);
      $('agent-output').classList.add('streaming-cursor');
      $('agent-output').scrollTop = $('agent-output').scrollHeight;
    }
  };

  es.onerror = () => {
    if (streaming) {
      $('agent-error').innerHTML = '<div class="agent-error"><strong>⚠ Connection lost</strong> Please try again.</div>';
      $('agent-error').style.display = '';
    }
    es.close(); setStreaming(false);
  };
}

$('get-recs-btn').addEventListener('click', () => getRecommendations(false));
$('force-refresh-btn').addEventListener('click', () => getRecommendations(true));

$('copy-btn').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(rawMd);
    $('copy-btn').textContent = 'Copied ✓';
    setTimeout(() => { $('copy-btn').textContent = 'Copy'; }, 2000);
  } catch { showToast('Clipboard access denied', 'error'); }
});

/* ── Send Brief button ──────────────────────────────────────── */
$('send-brief-btn').addEventListener('click', async () => {
  const trip = currentTrip();
  if (!trip) return;
  $('send-brief-btn').disabled = true;
  $('send-brief-btn').textContent = '✉ Sending…';
  try {
    const r = await api('POST', `/api/trips/${trip.id}/send-brief`);
    showToast(`Brief emailed to ${r.recipients} people ✓`, 'success');
    emailLog = await api('GET', '/api/email-log');
    renderHero();
    renderTripList();
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    $('send-brief-btn').disabled = false;
    $('send-brief-btn').textContent = '✉ Send Brief';
  }
});

/* ══════════════════════════════════════════════════════════════
   FAMILY EMAIL MANAGEMENT
══════════════════════════════════════════════════════════════ */

async function loadFamily() {
  try {
    family = await api('GET', '/api/family');
    renderFamily();
  } catch { /* ignore */ }
}

function renderFamily() {
  const list = $('family-list');
  list.innerHTML = '';
  family.forEach((m, i) => {
    const row = document.createElement('div');
    row.className = 'family-item';
    row.innerHTML = `
      <div class="family-item-info">
        <span class="family-item-name">${esc(m.name)}</span>
        <span class="family-item-email">${esc(m.email)}</span>
      </div>
      <button class="family-item-del" data-i="${i}" title="Remove">✕</button>
    `;
    list.appendChild(row);
  });
}

async function saveFamily() {
  try {
    family = await api('PUT', '/api/family', family);
    renderFamily();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

$('add-family-btn').addEventListener('click', async () => {
  const name  = $('new-family-name').value.trim();
  const email = $('new-family-email').value.trim();
  if (!name || !email) { showToast('Enter name and email', 'error'); return; }
  family.push({ name, email });
  await saveFamily();
  $('new-family-name').value  = '';
  $('new-family-email').value = '';
  showToast(`${name} added ✓`, 'success');
});

$('family-list').addEventListener('click', async e => {
  const btn = e.target.closest('.family-item-del');
  if (!btn) return;
  family.splice(+btn.dataset.i, 1);
  await saveFamily();
});

/* ══════════════════════════════════════════════════════════════
   HOME PROJECTS
══════════════════════════════════════════════════════════════ */

function updateBudget() {
  const estimated = projects.reduce((s, p) => s + (p.estimated_cost || 0), 0);
  const actual    = projects.reduce((s, p) => s + (p.actual_cost    || 0), 0);
  const remaining = estimated - actual;
  $('budget-estimated').textContent = fmtMoney(estimated);
  $('budget-actual').textContent    = fmtMoney(actual);
  const rem = $('budget-remaining');
  rem.textContent = fmtMoney(remaining);
  rem.className   = 'budget-card-value ' + (remaining >= 0 ? 'positive' : 'negative');
}

function renderProjects() {
  const list = $('project-list');
  list.innerHTML = '';

  if (!projects.length) {
    list.innerHTML = `
      <div class="projects-empty">
        <span class="icon">🔨</span>
        No projects yet — add your first home project!
      </div>`;
    updateBudget(); return;
  }

  const priorityOrder = { high: 0, medium: 1, low: 2 };
  [...projects].sort((a,b) => priorityOrder[a.priority] - priorityOrder[b.priority]).forEach(p => {
    const card = document.createElement('div');
    card.className = 'project-card';
    card.innerHTML = `
      <div class="project-card-header">
        <div>
          <div class="project-card-name">${esc(p.name)}</div>
          ${p.description ? `<div class="project-card-desc">${esc(p.description)}</div>` : ''}
        </div>
        <div class="project-card-actions">
          <button class="btn btn-secondary btn-xs proj-edit" data-id="${p.id}">✎ Edit</button>
          <button class="btn btn-danger btn-xs proj-del"  data-id="${p.id}">✕</button>
        </div>
      </div>
      <div class="project-card-meta">
        <span class="priority-badge priority-${p.priority}">${
          p.priority === 'high' ? '🔴 High' : p.priority === 'medium' ? '🟡 Medium' : '⚪ Low'
        }</span>
        <span class="status-badge ${p.status === 'completed' ? 'done' : ''}">${
          p.status === 'planning' ? 'Planning' : p.status === 'in_progress' ? 'In Progress' : '✓ Completed'
        }</span>
      </div>
      <div class="cost-display" style="margin-top:8px;">
        <span>Est: <strong>${fmtMoney(p.estimated_cost)}</strong></span>
        ${p.actual_cost !== null && p.actual_cost !== undefined
          ? `<span>•</span><span>Actual: <strong>${fmtMoney(p.actual_cost)}</strong></span>` : ''}
      </div>
      ${p.notes ? `<div style="margin-top:7px;font-size:.76rem;color:var(--t3);">${esc(p.notes)}</div>` : ''}
    `;
    list.appendChild(card);
  });

  updateBudget();
}

async function loadProjects() {
  try {
    projects = await api('GET', '/api/projects');
    renderProjects();
  } catch { /* ignore */ }
}

function openProjectModal(proj = null) {
  $('project-modal-title').textContent = proj ? 'Edit Project' : 'Add Project';
  $('project-form').reset();
  $('project-id').value        = proj?.id || '';
  $('project-name').value      = proj?.name || '';
  $('project-desc').value      = proj?.description || '';
  $('project-priority').value  = proj?.priority || 'medium';
  $('project-status').value    = proj?.status || 'planning';
  $('project-estimated').value = proj?.estimated_cost ?? '';
  $('project-actual').value    = proj?.actual_cost ?? '';
  $('project-notes').value     = proj?.notes || '';
  openModal('project-modal');
  setTimeout(() => $('project-name').focus(), 80);
}

async function saveProject() {
  const name = $('project-name').value.trim();
  if (!name) { showToast('Project name is required', 'error'); return; }

  const body = {
    name,
    description:    $('project-desc').value.trim(),
    priority:       $('project-priority').value,
    status:         $('project-status').value,
    estimated_cost: $('project-estimated').value ? +$('project-estimated').value : null,
    actual_cost:    $('project-actual').value    ? +$('project-actual').value    : null,
    notes:          $('project-notes').value.trim(),
  };

  const id = $('project-id').value;
  try {
    $('project-save-btn').disabled = true;
    if (id) {
      const updated = await api('PUT', `/api/projects/${id}`, body);
      const idx = projects.findIndex(p => p.id === id);
      if (idx !== -1) projects[idx] = updated;
    } else {
      const proj = await api('POST', '/api/projects', body);
      projects.push(proj);
    }
    renderProjects();
    closeModal('project-modal');
    showToast(id ? 'Project updated ✓' : `${name} added ✓`, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    $('project-save-btn').disabled = false;
  }
}

async function deleteProject(id) {
  try {
    await api('DELETE', `/api/projects/${id}`);
    projects = projects.filter(p => p.id !== id);
    renderProjects();
    showToast('Project removed', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

$('add-project-btn').addEventListener('click', () => openProjectModal());
$('project-save-btn').addEventListener('click', saveProject);

$('project-list').addEventListener('click', e => {
  const edit = e.target.closest('.proj-edit');
  const del  = e.target.closest('.proj-del');
  if (edit) { const p = projects.find(x => x.id === edit.dataset.id); if (p) openProjectModal(p); }
  if (del)  deleteProject(del.dataset.id);
});

/* ══════════════════════════════════════════════════════════════
   GOOGLE INTEGRATION
══════════════════════════════════════════════════════════════ */

$('google-disconnect-btn').addEventListener('click', async () => {
  try {
    await api('DELETE', '/auth/google');
    showToast('Google disconnected', 'info');
    checkHealth();
    renderHero();
  } catch (e) { showToast(e.message, 'error'); }
});

$('gmail-import-btn').addEventListener('click', async () => {
  $('import-modal-title').textContent = 'Import Trips from Gmail';
  $('import-desc').textContent        = 'Scanning your last 6 months of email for travel booking confirmations…';
  $('import-loading').style.display   = '';
  $('import-list-wrap').style.display = 'none';
  $('import-add-all-btn').style.display = 'none';
  importCandidates = [];
  openModal('import-modal');

  try {
    const data       = await api('POST', '/api/gmail/import');
    const found      = data.trips || [];
    $('import-loading').style.display = 'none';

    if (!found.length) {
      $('import-list-wrap').innerHTML = '<p style="font-size:.85rem;color:var(--t2);">No travel confirmations found in the last 6 months.</p>';
      $('import-list-wrap').style.display = '';
      return;
    }
    importCandidates = found;
    renderImportList(found);
  } catch (e) {
    $('import-loading').style.display = 'none';
    $('import-list-wrap').innerHTML = `<div class="agent-error"><strong>Error</strong> ${esc(e.message)}</div>`;
    $('import-list-wrap').style.display = '';
  }
});

$('calendar-sync-btn').addEventListener('click', async () => {
  $('import-modal-title').textContent = 'Sync from Google Calendar';
  $('import-desc').textContent        = 'Looking for upcoming travel events in your calendar…';
  $('import-loading').style.display   = '';
  $('import-list-wrap').style.display = 'none';
  $('import-add-all-btn').style.display = 'none';
  importCandidates = [];
  openModal('import-modal');

  try {
    const data  = await api('GET', '/api/calendar/events');
    const evs   = data.events || [];
    $('import-loading').style.display = 'none';

    if (!evs.length) {
      $('import-list-wrap').innerHTML = '<p style="font-size:.85rem;color:var(--t2);">No upcoming travel events found in Calendar.</p>';
      $('import-list-wrap').style.display = '';
      return;
    }
    importCandidates = evs;
    renderImportList(evs);
  } catch (e) {
    $('import-loading').style.display = 'none';
    $('import-list-wrap').innerHTML = `<div class="agent-error"><strong>Error</strong> ${esc(e.message)}</div>`;
    $('import-list-wrap').style.display = '';
  }
});

function renderImportList(items) {
  const list = $('import-list');
  list.innerHTML = '';
  items.forEach((t, i) => {
    const item = document.createElement('div');
    item.className = 'import-item';
    item.innerHTML = `
      <label style="display:flex;gap:10px;align-items:flex-start;cursor:pointer;flex:1;">
        <input type="checkbox" checked data-i="${i}" style="margin-top:3px;" />
        <div class="import-item-info">
          <div class="import-item-city">${esc(t.city)}, ${esc(t.country)}</div>
          <div class="import-item-dates">${fmtDate(t.start_date)} – ${fmtDate(t.end_date)}</div>
          ${t.notes ? `<div class="import-item-note">${esc(t.notes)}</div>` : ''}
        </div>
      </label>
    `;
    list.appendChild(item);
  });
  $('import-list-wrap').style.display   = '';
  $('import-add-all-btn').style.display = '';
}

$('import-add-all-btn').addEventListener('click', async () => {
  const checked = [...$('import-list').querySelectorAll('input[type=checkbox]:checked')]
    .map(cb => importCandidates[+cb.dataset.i]);
  if (!checked.length) { showToast('No trips selected', 'error'); return; }

  $('import-add-all-btn').disabled = true;
  let added = 0;
  for (const t of checked) {
    try {
      const existing = trips.find(x => x.city.toLowerCase() === t.city.toLowerCase() && x.start_date === t.start_date);
      if (existing) continue;
      const trip = await api('POST', '/api/schedule', t);
      trips.push(trip);
      added++;
    } catch { /* skip duplicates */ }
  }
  renderTripList();
  closeModal('import-modal');
  showToast(`${added} trip${added !== 1 ? 's' : ''} added ✓`, 'success');
  $('import-add-all-btn').disabled = false;
  if (currentTripIdx === -1) autoSelectNextTrip();
});

/* ── URL param handling (post-OAuth redirect) ───────────────── */
function handleUrlParams() {
  const params = new URLSearchParams(location.search);
  if (params.get('connected') === 'google') {
    showToast('Google connected ✓', 'success');
    history.replaceState({}, '', '/');
    checkHealth();
    renderHero();
  }
  if (params.get('error') === 'no_credentials') {
    showToast('credentials.json not found — see setup instructions', 'error');
    history.replaceState({}, '', '/');
    $('google-setup-section').style.display = '';
  }
}

/* ── Init ───────────────────────────────────────────────────── */
(async () => {
  handleUrlParams();
  await checkHealth();
  [emailLog] = await Promise.all([
    api('GET', '/api/email-log').catch(() => ({})),
  ]);
  await Promise.all([loadSchedule(), loadProjects(), loadFamily()]);
  autoSelectNextTrip();
})();
