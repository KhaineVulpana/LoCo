const LOGS_STORAGE_KEY = 'loco-3d-gen-logs';
const logsList = document.getElementById('logs-list');
const backBtn = document.getElementById('logs-back');
const clearBtn = document.getElementById('logs-clear');

function loadLogs() {
  const raw = localStorage.getItem(LOGS_STORAGE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function buildLogEntry(entry) {
  const hasDetails = Boolean(entry.details);
  const container = document.createElement(hasDetails ? 'details' : 'div');
  container.className = `log-entry log-${entry.level || 'info'}`;
  if (hasDetails) {
    container.open = false;
  }

  const summary = document.createElement(hasDetails ? 'summary' : 'div');
  summary.className = 'log-summary';

  const timeEl = document.createElement('span');
  timeEl.className = 'log-time';
  timeEl.textContent = entry.time || '';

  const levelEl = document.createElement('span');
  levelEl.className = 'log-level';
  levelEl.textContent = (entry.level || 'info').toUpperCase();

  const messageEl = document.createElement('span');
  messageEl.className = 'log-message';
  messageEl.textContent = entry.message || '';

  summary.appendChild(timeEl);
  summary.appendChild(levelEl);
  summary.appendChild(messageEl);
  container.appendChild(summary);

  if (hasDetails) {
    const detailsEl = document.createElement('pre');
    detailsEl.className = 'log-details';
    detailsEl.textContent = entry.details;
    container.appendChild(detailsEl);
  }

  return container;
}

function renderLogs() {
  if (!logsList) {
    return;
  }
  logsList.innerHTML = '';
  const logs = loadLogs();
  if (!logs.length) {
    const empty = document.createElement('div');
    empty.className = 'logs-empty';
    empty.textContent = 'No logs yet.';
    logsList.appendChild(empty);
    return;
  }
  logs.forEach((entry) => {
    logsList.appendChild(buildLogEntry(entry));
  });
  logsList.scrollTop = logsList.scrollHeight;
}

function clearLogs() {
  localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify([]));
  renderLogs();
}

if (backBtn) {
  backBtn.addEventListener('click', () => {
    window.location.href = 'index.html';
  });
}

if (clearBtn) {
  clearBtn.addEventListener('click', () => {
    clearLogs();
  });
}

window.addEventListener('storage', (event) => {
  if (event.key === LOGS_STORAGE_KEY) {
    renderLogs();
  }
});

renderLogs();
