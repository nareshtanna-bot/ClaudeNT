/* ── Travel Intelligence Dashboard ─────────────────────────── */

if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}

/* ── State ──────────────────────────────────────────────────── */
let trips    = [];
let projects = [];
let streaming = false;
let activeES  = null;
let rawMd     = '';
let importCandidates = [];   // trips from Gmail/Calendar

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
    // Google state
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
    $('status-dot').className  = 'status-dot err';
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
function openModal(id) {
  $(id).classList.add('open');
}
function closeModal(id) {
  $(id).classList.remove('open');
}

document.querySelectorAll('[data-close]').forEach(btn => {
  btn.addEventListener('click', () => closeModal(btn.dataset.close));
});

document.querySelectorAll('.modal-backdrop').forEach(bd => {
  bd.addEventListener('click', e => {
    if (e.target === bd) closeModal(bd.id);
  });
});

document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-backdrop.open').forEach(bd => closeModal(bd.id));
  }
});

/* ══════════════════════════════════════════════════════════════
   TRAVEL SCHEDULE
══════════════════════════════════════════════════════════════ */

function tripStatus(trip) {
  const today = new Date().toISOString().slice(0,10);
  if (today >= trip.start_date && today <= trip.end_date) return {label:'Now',      cls:'now'};
  if (trip.start_date > today)                            return {label:'Upcoming', cls:'upcoming'};
  return                                                         {label:'Past',     cls:'past'};
}

async function loadTripRecStatus(trip) {
  try {
    return await api('GET', `/api/recommendations/${trip.id}/status`);
  } catch { return null; }
}

function renderTripList() {
  const list = $('trip-list');
  const sel  = $('trip-selector');
  list.innerHTML = '';
  sel.innerHTML  = '<option value="">— Choose a trip —</option>';

  if (!trips.length) {
    list.innerHTML = `
      <div class="trip-list-empty">
        <span class="icon">✈️</span>No trips yet — add one!
      </div>`;
    return;
  }

  [...trips]
    .sort((a,b) => a.start_date.localeCompare(b.start_date))
    .forEach(async trip => {
      const { label, cls } = tripStatus(trip);

      const card = document.createElement('div');
      card.className = 'trip-card';
      card.dataset.id = trip.id;
      card.innerHTML = `
        <div class="trip-card-city">${esc(trip.city)}</div>
        <div class="trip-card-country">${esc(trip.country)}</div>
        <div class="trip-card-dates">${fmtDate(trip.start_date)} – ${fmtDate(trip.end_date)}</div>
        <span class="trip-badge ${cls}">${label}</span>
        <div class="rec-age" id="rec-age-${trip.id}"></div>
        <button class="trip-card-del" data-id="${trip.id}" title="Remove">✕</button>
      `;
      list.appendChild(card);

      const opt = document.createElement('option');
      opt.value       = trip.id;
      opt.textContent = `${trip.city}, ${trip.country} (${fmtDate(trip.start_date)} – ${fmtDate(trip.end_date)})`;
      sel.appendChild(opt);

      // Async: load rec cache status and show age
      const status = await loadTripRecStatus(trip);
      if (status && status.has_cache) {
        const ageEl = $(`rec-age-${trip.id}`);
        if (ageEl) {
          const stale = status.needs_refresh;
          ageEl.className = `rec-age ${stale ? 'stale' : 'fresh'}`;
          ageEl.innerHTML = stale
            ? `⚠ Recs ${status.age_days}d old`
            : `✓ Recs updated ${status.age_days}d ago`;
        }
      }
    });
}

async function loadSchedule() {
  try {
    trips = await api('GET', '/api/schedule');
    renderTripList();
  } catch (e) {
    showToast('Could not load schedule', 'error');
  }
}

async function saveTrip() {
  const city    = $('trip-city').value.trim();
  const country = $('trip-country').value.trim();
  const start   = $('trip-start').value;
  const end     = $('trip-end').value;
  const notes   = $('trip-notes').value.trim();

  if (!city || !country || !start || !end) {
    showToast('Fill in all required fields', 'error'); return;
  }
  if (start > end) {
    showToast('Departure must be after arrival', 'error'); return;
  }
  try {
    $('trip-save-btn').disabled = true;
    const trip = await api('POST', '/api/schedule', { city, country, start_date: start, end_date: end, notes });
    trips.push(trip);
    renderTripList();
    closeModal('add-trip-modal');
    showToast(`${city} added ✓`, 'success');
    $('add-trip-form').reset();
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
    // Clear recs if this trip was selected
    if ($('trip-selector').value === id) {
      $('trip-selector').value = '';
      $('get-recs-btn').disabled = true;
      $('output-wrap').style.display = 'none';
      $('rec-meta').style.display    = 'none';
      $('force-refresh-btn').style.display = 'none';
    }
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
  const del = e.target.closest('.trip-card-del');
  if (del) { e.stopPropagation(); deleteTrip(del.dataset.id); }
});

/* ══════════════════════════════════════════════════════════════
   RESTAURANT AGENT
══════════════════════════════════════════════════════════════ */

async function onTripSelect() {
  const id = $('trip-selector').value;
  $('get-recs-btn').disabled = !id;
  $('rec-meta').style.display = 'none';
  $('force-refresh-btn').style.display = 'none';

  if (!id) return;

  // Show rec cache status
  try {
    const s = await api('GET', `/api/recommendations/${id}/status`);
    const meta = $('rec-meta');
    if (s.has_cache) {
      const stale = s.needs_refresh;
      meta.className = `rec-meta ${stale ? 'stale' : 'fresh'}`;
      const when = stale
        ? `⚠ Recommendations are ${s.age_days} days old — will auto-refresh`
        : `✓ Refreshed ${s.age_days === 0 ? 'today' : s.age_days + 'd ago'}`;
      meta.textContent = when;
      meta.style.display = 'flex';
      $('force-refresh-btn').style.display = '';
    }
  } catch { /* ignore */ }
}

$('trip-selector').addEventListener('change', onTripSelect);

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
  const id = $('trip-selector').value;
  if (!id || streaming) return;

  rawMd = '';
  $('agent-error').style.display   = 'none';
  $('agent-output').className      = 'agent-output';
  $('agent-output').innerHTML      = '';
  $('output-wrap').style.display   = 'block';
  $('copy-btn').style.display      = 'none';
  setStreaming(true);

  if (activeES) { activeES.close(); activeES = null; }

  const url = `/api/recommendations/stream?trip_id=${encodeURIComponent(id)}${force ? '&force=true' : ''}`;
  const es = new EventSource(url);
  activeES = es;

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

      // Update meta row
      if (data.refreshed_at) {
        const d = new Date(data.refreshed_at);
        const meta = $('rec-meta');
        meta.className = 'rec-meta fresh';
        meta.textContent = `✓ Just refreshed${data.cached ? ' (from cache)' : ''}`;
        meta.style.display = 'flex';
        $('force-refresh-btn').style.display = '';
        // Refresh sidebar age indicators
        renderTripList();
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

/* ══════════════════════════════════════════════════════════════
   HOME PROJECTS
══════════════════════════════════════════════════════════════ */

function updateBudget() {
  const estimated = projects.reduce((s, p) => s + (p.estimated_cost || 0), 0);
  const actual    = projects.reduce((s, p) => s + (p.actual_cost || 0), 0);
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
    updateBudget();
    return;
  }

  const priorityOrder = { high: 0, medium: 1, low: 2 };
  [...projects]
    .sort((a,b) => priorityOrder[a.priority] - priorityOrder[b.priority])
    .forEach(p => {
      const card = document.createElement('div');
      card.className = 'project-card';
      card.innerHTML = `
        <div class="project-card-header">
          <div>
            <div class="project-card-name">${esc(p.name)}</div>
            ${p.description ? `<div class="project-card-desc">${esc(p.description)}</div>` : ''}
          </div>
          <div class="project-card-actions">
            <button class="btn btn-secondary btn-xs proj-edit" data-id="${p.id}" title="Edit">✎ Edit</button>
            <button class="btn btn-danger btn-xs proj-del"  data-id="${p.id}" title="Delete">✕</button>
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
  if (edit) {
    const p = projects.find(x => x.id === edit.dataset.id);
    if (p) openProjectModal(p);
  }
  if (del) deleteProject(del.dataset.id);
});

/* ══════════════════════════════════════════════════════════════
   GOOGLE INTEGRATION
══════════════════════════════════════════════════════════════ */

$('google-disconnect-btn').addEventListener('click', async () => {
  try {
    await api('DELETE', '/auth/google');
    showToast('Google disconnected', 'info');
    checkHealth();
  } catch (e) {
    showToast(e.message, 'error');
  }
});

// Gmail Import
$('gmail-import-btn').addEventListener('click', async () => {
  $('import-loading').style.display   = '';
  $('import-list-wrap').style.display = 'none';
  $('import-add-all-btn').style.display = 'none';
  importCandidates = [];
  openModal('import-modal');

  try {
    const data = await api('POST', '/api/gmail/import');
    const trips_found = data.trips || [];
    $('import-loading').style.display = 'none';

    if (!trips_found.length) {
      $('import-list-wrap').innerHTML = '<p style="font-size:.85rem;color:var(--t2);">No travel booking confirmations found in the last 6 months.</p>';
      $('import-list-wrap').style.display = '';
      return;
    }

    importCandidates = trips_found;
    const list = $('import-list');
    list.innerHTML = '';
    trips_found.forEach((t, i) => {
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

    $('import-list-wrap').style.display  = '';
    $('import-add-all-btn').style.display = '';
  } catch (e) {
    $('import-loading').style.display = 'none';
    $('import-list-wrap').innerHTML = `<div class="agent-error"><strong>Error</strong> ${esc(e.message)}</div>`;
    $('import-list-wrap').style.display = '';
  }
});

$('import-add-all-btn').addEventListener('click', async () => {
  const checked = [...$('import-list').querySelectorAll('input[type=checkbox]:checked')]
    .map(cb => importCandidates[+cb.dataset.i]);

  if (!checked.length) { showToast('No trips selected', 'error'); return; }

  $('import-add-all-btn').disabled = true;
  let added = 0;
  for (const t of checked) {
    try {
      const existing = trips.find(x =>
        x.city.toLowerCase() === t.city.toLowerCase() &&
        x.start_date === t.start_date
      );
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
});

// Calendar Sync
$('calendar-sync-btn').addEventListener('click', async () => {
  showToast('Scanning Google Calendar…', 'info');
  try {
    const data  = await api('GET', '/api/calendar/events');
    const evs   = data.events || [];
    if (!evs.length) {
      showToast('No upcoming travel events found in Calendar', 'info'); return;
    }

    // Reuse import modal with calendar events
    importCandidates = evs;
    $('import-loading').style.display    = 'none';
    $('import-add-all-btn').style.display = '';

    const list = $('import-list');
    list.innerHTML = '';
    evs.forEach((t, i) => {
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

    $('import-list-wrap').style.display = '';
    openModal('import-modal');
  } catch (e) {
    showToast(e.message, 'error');
  }
});

/* ── URL param handling (post-OAuth redirect) ───────────────── */
function handleUrlParams() {
  const params = new URLSearchParams(location.search);
  if (params.get('connected') === 'google') {
    showToast('Google connected ✓', 'success');
    history.replaceState({}, '', '/');
    checkHealth();
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
  await Promise.all([loadSchedule(), loadProjects()]);
})();
