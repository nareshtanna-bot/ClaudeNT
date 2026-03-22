/* ── Travel Intelligence Dashboard ─────────────────────────
   app.js — all client-side logic
   ──────────────────────────────────────────────────────── */

// Configure marked for safe rendering
if (typeof marked !== 'undefined') {
  marked.setOptions({ breaks: true, gfm: true });
}

/* ── State ─────────────────────────────────────────────────── */
let trips      = [];       // local cache of schedule
let streaming  = false;    // is the agent currently running?
let activeEventSource = null;

/* ── DOM refs ──────────────────────────────────────────────── */
const tripList       = document.getElementById('trip-list');
const tripSelector   = document.getElementById('trip-selector');
const getRecsBtn     = document.getElementById('get-recs-btn');
const btnIcon        = document.getElementById('btn-icon');
const btnLabel       = document.getElementById('btn-label');
const agentOutput    = document.getElementById('agent-output');
const outputWrap     = document.getElementById('output-wrap');
const outputStatus   = document.getElementById('output-status');
const thinkingDots   = document.getElementById('thinking-dots');
const copyBtn        = document.getElementById('copy-btn');
const agentError     = document.getElementById('agent-error');
const statusDot      = document.getElementById('status-dot');
const statusText     = document.getElementById('status-text');
const addTripBtn     = document.getElementById('add-trip-btn');
const modal          = document.getElementById('add-trip-modal');
const modalClose     = document.getElementById('modal-close');
const modalCancel    = document.getElementById('modal-cancel');
const modalSave      = document.getElementById('modal-save');
const addTripForm    = document.getElementById('add-trip-form');
const toastContainer = document.getElementById('toast-container');

/* ── API helpers ───────────────────────────────────────────── */
async function api(method, path, body) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

/* ── Toast ─────────────────────────────────────────────────── */
function showToast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* ── Health check ──────────────────────────────────────────── */
async function checkHealth() {
  try {
    const data = await api('GET', '/api/health');
    if (data.api_key_configured) {
      statusDot.className  = 'status-dot ok';
      statusText.textContent = 'API connected';
    } else {
      statusDot.className  = 'status-dot err';
      statusText.textContent = 'No API key';
    }
  } catch {
    statusDot.className  = 'status-dot err';
    statusText.textContent = 'Offline';
  }
}

/* ── Trip status label ─────────────────────────────────────── */
function getTripStatus(trip) {
  const today      = new Date().toISOString().slice(0, 10);
  const { start_date: s, end_date: e } = trip;
  if (today >= s && today <= e) return { label: 'Now',      cls: '' };
  if (s > today)                return { label: 'Upcoming', cls: 'upcoming' };
  return                               { label: 'Past',     cls: 'past' };
}

/* ── Render sidebar trip list ──────────────────────────────── */
function renderTripList() {
  tripList.innerHTML = '';
  tripSelector.innerHTML = '<option value="">— Choose a trip —</option>';

  if (trips.length === 0) {
    tripList.innerHTML = `
      <div class="trip-list-empty">
        <span class="icon">✈️</span>
        No trips yet — add one!
      </div>`;
    return;
  }

  // Sort by start date ascending
  const sorted = [...trips].sort((a, b) => a.start_date.localeCompare(b.start_date));

  sorted.forEach(trip => {
    const { label, cls } = getTripStatus(trip);

    // Sidebar card
    const card = document.createElement('div');
    card.className = 'trip-card';
    card.dataset.id = trip.id;
    card.innerHTML = `
      <div class="trip-card-city">${esc(trip.city)}</div>
      <div class="trip-card-country">${esc(trip.country)}</div>
      <div class="trip-card-dates">${fmt(trip.start_date)} – ${fmt(trip.end_date)}</div>
      <span class="trip-card-badge ${cls}">${label}</span>
      <button class="trip-card-delete" data-id="${trip.id}" title="Remove">✕</button>
    `;
    tripList.appendChild(card);

    // Dropdown option
    const opt = document.createElement('option');
    opt.value = trip.id;
    opt.textContent = `${trip.city}, ${trip.country}  (${fmt(trip.start_date)} – ${fmt(trip.end_date)})`;
    tripSelector.appendChild(opt);
  });
}

function fmt(dateStr) {
  const [y, m, d] = dateStr.split('-');
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${months[parseInt(m,10)-1]} ${parseInt(d,10)}, ${y}`;
}

function esc(str) {
  return String(str)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

/* ── Load schedule from server ─────────────────────────────── */
async function loadSchedule() {
  try {
    trips = await api('GET', '/api/schedule');
    renderTripList();
  } catch (e) {
    showToast('Could not load schedule: ' + e.message, 'error');
  }
}

/* ── Delete trip ────────────────────────────────────────────── */
async function deleteTrip(id) {
  try {
    await api('DELETE', `/api/schedule/${id}`);
    trips = trips.filter(t => t.id !== id);
    renderTripList();
    showToast('Trip removed', 'success');
  } catch (e) {
    showToast('Delete failed: ' + e.message, 'error');
  }
}

/* ── Add trip ───────────────────────────────────────────────── */
async function saveTrip() {
  const city       = document.getElementById('input-city').value.trim();
  const country    = document.getElementById('input-country').value.trim();
  const start_date = document.getElementById('input-start').value;
  const end_date   = document.getElementById('input-end').value;
  const notes      = document.getElementById('input-notes').value.trim();

  if (!city || !country || !start_date || !end_date) {
    showToast('Please fill in all required fields.', 'error');
    return;
  }
  if (start_date > end_date) {
    showToast('Departure must be after arrival.', 'error');
    return;
  }

  try {
    modalSave.disabled = true;
    const trip = await api('POST', '/api/schedule', { city, country, start_date, end_date, notes });
    trips.push(trip);
    renderTripList();
    closeModal();
    showToast(`${city} added to schedule ✓`, 'success');
  } catch (e) {
    showToast('Could not save trip: ' + e.message, 'error');
  } finally {
    modalSave.disabled = false;
  }
}

/* ── Modal ──────────────────────────────────────────────────── */
function openModal() {
  addTripForm.reset();
  modal.classList.add('open');
  document.getElementById('input-city').focus();
}

function closeModal() {
  modal.classList.remove('open');
}

/* ── Restaurant agent ───────────────────────────────────────── */
function setStreaming(active) {
  streaming = active;
  getRecsBtn.disabled = active;
  btnIcon.textContent  = active ? '⏳' : '🔍';
  btnLabel.textContent = active ? 'Searching…' : 'Find Restaurants';
  thinkingDots.classList.toggle('active', active);
  outputStatus.textContent = active ? 'Agent working…' : 'Results';
  if (!active) copyBtn.style.display = 'block';
}

let rawMarkdown = '';

async function getRecommendations() {
  const tripId = tripSelector.value;
  if (!tripId || streaming) return;

  // Reset UI
  rawMarkdown = '';
  agentError.style.display = 'none';
  agentOutput.className    = 'agent-output';
  agentOutput.innerHTML    = '';
  outputWrap.style.display = 'block';
  copyBtn.style.display    = 'none';
  setStreaming(true);

  // Close any existing stream
  if (activeEventSource) { activeEventSource.close(); activeEventSource = null; }

  const evtSource = new EventSource(`/api/recommendations/stream?trip_id=${encodeURIComponent(tripId)}`);
  activeEventSource = evtSource;

  evtSource.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.error) {
      showError(data.error);
      evtSource.close();
      setStreaming(false);
      return;
    }

    if (data.done) {
      // Final render — remove streaming cursor, do a clean markdown pass
      agentOutput.classList.remove('streaming-cursor');
      agentOutput.innerHTML = marked.parse(rawMarkdown);
      evtSource.close();
      setStreaming(false);
      return;
    }

    if (data.text) {
      rawMarkdown += data.text;
      // Live render with cursor indicator
      agentOutput.innerHTML = marked.parse(rawMarkdown);
      agentOutput.classList.add('streaming-cursor');
      // Auto-scroll
      agentOutput.scrollTop = agentOutput.scrollHeight;
    }
  };

  evtSource.onerror = () => {
    showError('Connection lost. Please try again.');
    evtSource.close();
    setStreaming(false);
  };
}

function showError(msg) {
  agentError.innerHTML = `
    <div class="agent-error">
      <strong>⚠ Agent error</strong>${esc(msg)}
    </div>`;
  agentError.style.display = 'block';
}

/* ── Copy button ────────────────────────────────────────────── */
copyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(rawMarkdown);
    copyBtn.textContent = 'Copied ✓';
    setTimeout(() => { copyBtn.textContent = 'Copy'; }, 2000);
  } catch {
    showToast('Clipboard access denied', 'error');
  }
});

/* ── Selector → enable button ───────────────────────────────── */
tripSelector.addEventListener('change', () => {
  getRecsBtn.disabled = !tripSelector.value;
});

/* ── Event listeners ────────────────────────────────────────── */
getRecsBtn.addEventListener('click', getRecommendations);

addTripBtn.addEventListener('click', openModal);
modalClose.addEventListener('click', closeModal);
modalCancel.addEventListener('click', closeModal);
modalSave.addEventListener('click', saveTrip);
modal.addEventListener('click', e => { if (e.target === modal) closeModal(); });

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && modal.classList.contains('open')) closeModal();
  if (e.key === 'Enter'  && modal.classList.contains('open') && e.target.id !== 'input-notes') {
    e.preventDefault();
    saveTrip();
  }
});

tripList.addEventListener('click', e => {
  const deleteBtn = e.target.closest('.trip-card-delete');
  if (deleteBtn) {
    e.stopPropagation();
    deleteTrip(deleteBtn.dataset.id);
  }
});

/* ── Init ───────────────────────────────────────────────────── */
(async () => {
  await checkHealth();
  await loadSchedule();
})();
