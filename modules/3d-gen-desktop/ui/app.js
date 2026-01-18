import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFExporter } from 'three/addons/exporters/GLTFExporter.js';
import { STLExporter } from 'three/addons/exporters/STLExporter.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { extractMeshPayload } from './mesh_parser.js';

const statusPill = document.getElementById('status-pill');
const statusPillDup = document.getElementById('status-pill-dup');
const viewerStatus = document.getElementById('viewer-status');
const viewerOverlay = document.getElementById('viewer-overlay');
const viewerOverlayText = document.getElementById('viewer-overlay-text');
const viewerOverlayHint = document.getElementById('viewer-overlay-hint');
const vertexCount = document.getElementById('vertex-count');
const triangleCount = document.getElementById('triangle-count');
const meshStatus = document.getElementById('mesh-status');

const serverInput = document.getElementById('server-url') || document.getElementById('settings-server-url');
const workspaceInput = document.getElementById('workspace-path') || document.getElementById('settings-workspace-path');
const tokenInput = document.getElementById('auth-token') || document.getElementById('settings-auth-token');
const connectBtn = document.getElementById('connect-btn');
const composer = document.getElementById('composer');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-button');
const messagesEl = document.getElementById('messages');
const sessionListEl = document.getElementById('session-list');
const newSessionBtn = document.getElementById('new-session-btn');
const activeSessionTitle = document.getElementById('active-session-title');
const resetViewBtn = document.getElementById('reset-view');
const wireframeBtn = document.getElementById('toggle-wireframe');
const toggleGridBtn = document.getElementById('toggle-grid');
const lightingSelect = document.getElementById('lighting-preset');
const importBtn = document.getElementById('import-mesh');
const importFileInput = document.getElementById('import-file');
const exportGlbBtn = document.getElementById('export-glb');
const exportStlBtn = document.getElementById('export-stl');
const copyMeshStatsBtn = document.getElementById('copy-mesh-stats');
const promptTemplatesEl = document.getElementById('prompt-templates');
const promptHistoryEl = document.getElementById('prompt-history');
const copyPromptBtn = document.getElementById('copy-last-prompt');
const viewerSurface = document.querySelector('.viewer-surface');
const dropOverlay = document.getElementById('drop-overlay');
const errorBanner = document.getElementById('error-banner');
const errorBannerText = document.getElementById('error-banner-text');
const errorBannerDismiss = document.getElementById('error-banner-dismiss');
const toastEl = document.getElementById('toast');
const settingsOpenBtn = document.getElementById('settings-open');
const settingsOverlay = document.getElementById('settings-overlay');
const settingsCloseBtn = document.getElementById('settings-close');
const settingsForm = document.getElementById('settings-form');
const settingsServerInput = document.getElementById('settings-server-url');
const settingsWorkspaceInput = document.getElementById('settings-workspace-path');
const settingsTokenInput = document.getElementById('settings-auth-token');
const settingsAutoConnect = document.getElementById('settings-auto-connect');
const settingsAutoReconnect = document.getElementById('settings-auto-reconnect');
const settingsAutoApprove = document.getElementById('settings-auto-approve');
const settingsGridToggle = document.getElementById('settings-grid');
const settingsWireframeToggle = document.getElementById('settings-wireframe');
const settingsLightingSelect = document.getElementById('settings-lighting');
const settingsResetBtn = document.getElementById('settings-reset');
const logsOpenBtn = document.getElementById('logs-open');
const appRoot = document.querySelector('.app');
const sessionPanel = document.querySelector('.session-panel');
const panelDivider = document.getElementById('panel-divider');

const DEFAULT_SERVER = 'http://localhost:3199';
const MODULE_ID = '3d-gen';
const STORAGE_CONFIG_KEY = 'loco-3d-gen-config';
const STORAGE_STATE_KEY = 'loco-3d-gen-state';
const LOGS_STORAGE_KEY = 'loco-3d-gen-logs';
const LAYOUT_STORAGE_KEY = 'loco-3d-gen-layout';
const MAX_VERTICES = 200000;
const MAX_TRIANGLES = 400000;
const PROMPT_HISTORY_LIMIT = 8;
const REQUEST_TIMEOUT_MS = 12000;
const PING_INTERVAL_MS = 15000;
const RECONNECT_BASE_DELAY_MS = 1200;
const RECONNECT_MAX_DELAY_MS = 15000;
const LOG_LIMIT = 200;
const MIN_CHAT_WIDTH = 360;
const MIN_VIEWER_WIDTH = 320;
const DEFAULT_SETTINGS = {
  serverUrl: DEFAULT_SERVER,
  workspacePath: '',
  token: '',
  autoConnect: false,
  autoReconnect: true,
  autoApprove: false,
  gridVisible: true,
  wireframe: false,
  lightingPreset: 'studio'
};

const PROMPT_TEMPLATES = [
  {
    label: 'Low-poly prop',
    text: 'Create a low-poly prop with clean edges, light bevels, and a single material.'
  },
  {
    label: 'Hero asset',
    text: 'Generate a hero asset with mid-poly detail, clean topology, and a grounded base.'
  },
  {
    label: 'Sci-fi drone',
    text: 'Design a compact sci-fi drone with layered panels and symmetrical geometry.'
  },
  {
    label: 'Stylized chair',
    text: 'Build a stylized chair with chunky proportions and a readable silhouette.'
  }
];

const LIGHTING_PRESETS = {
  studio: {
    label: 'Studio',
    ambient: 0.75,
    key: 0.95,
    fill: 0.4,
    keyPos: [4, 6, 4],
    fillPos: [-3, 2, -2],
    background: '#0d1018'
  },
  noir: {
    label: 'Noir',
    ambient: 0.3,
    key: 1.15,
    fill: 0.15,
    keyPos: [5, 7, 3],
    fillPos: [-5, 1, -3],
    background: '#07090f'
  },
  soft: {
    label: 'Soft',
    ambient: 0.9,
    key: 0.6,
    fill: 0.35,
    keyPos: [3, 4, 2],
    fillPos: [-2, 3, -2],
    background: '#101626'
  }
};

const state = {
  ws: null,
  serverUrl: DEFAULT_SERVER,
  token: '',
  workspaceId: null,
  sessionId: null,
  sessions: [],
  messagesBySession: new Map(),
  currentAssistantIndex: null,
  currentAssistantEl: null,
  assistantBuffer: '',
  wireframe: false,
  gridVisible: true,
  lightingPreset: 'studio',
  mesh: null,
  lastMeshPayload: null,
  lastMeshStats: null,
  promptHistory: [],
  lastPrompt: '',
  reconnectAttempts: 0,
  reconnectTimer: null,
  pingTimer: null,
  persistTimer: null,
  toastTimer: null,
  logs: [],
  layoutRatio: null,
  intentionalClose: false,
  autoConnect: DEFAULT_SETTINGS.autoConnect,
  autoReconnect: DEFAULT_SETTINGS.autoReconnect,
  autoApprove: DEFAULT_SETTINGS.autoApprove,
  isStreaming: false,
  thinkingBuffer: '',
  thinkingEl: null,
  thinkingContentEl: null,
  thinkingCollapsed: false
};

function showToast(message) {
  if (!toastEl) {
    return;
  }
  toastEl.textContent = message;
  toastEl.classList.add('visible');
  if (state.toastTimer) {
    clearTimeout(state.toastTimer);
  }
  state.toastTimer = setTimeout(() => {
    toastEl.classList.remove('visible');
  }, 2400);
}

function updateSendButton() {
  if (!sendBtn) {
    return;
  }
  if (state.isStreaming) {
    sendBtn.textContent = 'Stop';
    sendBtn.classList.add('is-stop');
  } else {
    sendBtn.textContent = 'Send';
    sendBtn.classList.remove('is-stop');
  }
}

function setStreamingState(isStreaming) {
  state.isStreaming = isStreaming;
  updateSendButton();
}

function cancelGeneration() {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    showToast('Not connected.');
    setStreamingState(false);
    return;
  }
  state.ws.send(JSON.stringify({
    type: 'client.cancel'
  }));
  addLog('info', 'Generation cancelled');
  setStreamingState(false);
}

function formatLogDetails(details) {
  if (details === null || details === undefined) {
    return '';
  }
  if (details instanceof Error) {
    return details.stack || details.message || String(details);
  }
  if (typeof details === 'string') {
    return details;
  }
  try {
    return JSON.stringify(details, null, 2);
  } catch (error) {
    return String(details);
  }
}

function trimLogDetails(text) {
  if (!text) {
    return '';
  }
  const limit = 2000;
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, limit)}...`;
}

function loadLogs(options = {}) {
  const { replace = false } = options;
  const raw = localStorage.getItem(LOGS_STORAGE_KEY);
  if (!raw) {
    if (replace) {
      state.logs = [];
    }
    return;
  }
  try {
    const parsed = JSON.parse(raw);
    const stored = Array.isArray(parsed) ? parsed : [];
    if (replace) {
      state.logs = stored.slice(-LOG_LIMIT);
    } else {
      state.logs = [...stored, ...state.logs].slice(-LOG_LIMIT);
    }
  } catch {
    state.logs = replace ? [] : (state.logs || []);
  }
}

function persistLogs() {
  try {
    localStorage.setItem(LOGS_STORAGE_KEY, JSON.stringify(state.logs));
  } catch (error) {
    console.warn('Failed to persist logs', error);
  }
}

function loadLayout() {
  const raw = localStorage.getItem(LAYOUT_STORAGE_KEY);
  if (!raw) {
    return;
  }
  try {
    const value = JSON.parse(raw);
    if (typeof value === 'number' && value > 0.2 && value < 0.8) {
      state.layoutRatio = value;
    }
  } catch {
    state.layoutRatio = null;
  }
}

function persistLayout() {
  if (typeof state.layoutRatio !== 'number') {
    return;
  }
  try {
    localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(state.layoutRatio));
  } catch (error) {
    console.warn('Failed to persist layout', error);
  }
}

function getLayoutMetrics() {
  if (!appRoot || !sessionPanel || !panelDivider) {
    return null;
  }
  const appRect = appRoot.getBoundingClientRect();
  const sessionWidth = sessionPanel.getBoundingClientRect().width;
  const dividerWidth = panelDivider.getBoundingClientRect().width;
  const total = appRect.width - sessionWidth - dividerWidth;
  if (total <= 0) {
    return null;
  }
  return { appRect, sessionWidth, dividerWidth, total };
}

function applyLayoutFromRatio(ratio) {
  if (window.matchMedia('(max-width: 1200px)').matches) {
    if (appRoot) {
      appRoot.style.gridTemplateColumns = '';
    }
    if (typeof renderer !== 'undefined' && renderer) {
      resizeRenderer();
    }
    return;
  }
  const metrics = getLayoutMetrics();
  if (!metrics) {
    return;
  }
  const safeRatio = typeof ratio === 'number' ? ratio : 0.55;
  const minChat = Math.min(MIN_CHAT_WIDTH, metrics.total * 0.6);
  const minViewer = Math.min(MIN_VIEWER_WIDTH, metrics.total * 0.6);
  const maxChat = Math.max(minChat, metrics.total - minViewer);
  let chatWidth = metrics.total * safeRatio;
  if (maxChat <= minChat) {
    chatWidth = metrics.total / 2;
  } else {
    chatWidth = Math.max(minChat, Math.min(maxChat, chatWidth));
  }
  const viewerWidth = metrics.total - chatWidth;
  appRoot.style.gridTemplateColumns = `${metrics.sessionWidth}px ${chatWidth}px ${metrics.dividerWidth}px ${viewerWidth}px`;
  if (typeof renderer !== 'undefined' && renderer) {
    resizeRenderer();
  }
}

function updateLayoutFromPointer(clientX) {
  if (window.matchMedia('(max-width: 1200px)').matches) {
    return;
  }
  const metrics = getLayoutMetrics();
  if (!metrics) {
    return;
  }
  const offset = clientX - metrics.appRect.left - metrics.sessionWidth - metrics.dividerWidth / 2;
  const minChat = Math.min(MIN_CHAT_WIDTH, metrics.total * 0.6);
  const minViewer = Math.min(MIN_VIEWER_WIDTH, metrics.total * 0.6);
  const maxChat = Math.max(minChat, metrics.total - minViewer);
  let chatWidth = offset;
  if (maxChat <= minChat) {
    chatWidth = metrics.total / 2;
  } else {
    chatWidth = Math.max(minChat, Math.min(maxChat, chatWidth));
  }
  const viewerWidth = metrics.total - chatWidth;
  state.layoutRatio = metrics.total ? chatWidth / metrics.total : 0.5;
  appRoot.style.gridTemplateColumns = `${metrics.sessionWidth}px ${chatWidth}px ${metrics.dividerWidth}px ${viewerWidth}px`;
  persistLayout();
  if (typeof renderer !== 'undefined' && renderer) {
    resizeRenderer();
  }
}

function initResizablePanels() {
  if (!panelDivider || !appRoot || !sessionPanel) {
    return;
  }
  applyLayoutFromRatio(state.layoutRatio ?? 0.55);

  panelDivider.addEventListener('pointerdown', (event) => {
    event.preventDefault();
    panelDivider.setPointerCapture(event.pointerId);
    document.body.classList.add('is-resizing');
    updateLayoutFromPointer(event.clientX);
  });

  panelDivider.addEventListener('pointermove', (event) => {
    if (!document.body.classList.contains('is-resizing')) {
      return;
    }
    updateLayoutFromPointer(event.clientX);
  });

  panelDivider.addEventListener('pointerup', () => {
    document.body.classList.remove('is-resizing');
  });

  panelDivider.addEventListener('pointercancel', () => {
    document.body.classList.remove('is-resizing');
  });

  panelDivider.addEventListener('keydown', (event) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
      return;
    }
    event.preventDefault();
    const delta = event.key === 'ArrowLeft' ? -0.04 : 0.04;
    const nextRatio = (state.layoutRatio ?? 0.55) + delta;
    state.layoutRatio = Math.max(0.2, Math.min(0.8, nextRatio));
    applyLayoutFromRatio(state.layoutRatio);
    persistLayout();
  });
}

function addLog(level, message, details) {
  const entry = {
    id: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
    time: new Date().toLocaleTimeString(),
    level,
    message,
    details: trimLogDetails(formatLogDetails(details))
  };

  state.logs.push(entry);
  if (state.logs.length > LOG_LIMIT) {
    state.logs.shift();
  }
  persistLogs();
}

function openSettings() {
  if (!settingsOverlay) {
    return;
  }
  syncSettingsForm();
  settingsOverlay.classList.add('visible');
  settingsOverlay.setAttribute('aria-hidden', 'false');
  document.body.classList.add('settings-open');
  if (settingsServerInput) {
    settingsServerInput.focus();
    settingsServerInput.select();
  }
}

function openLogsWindowWithTauri(url) {
  const tauri = window.__TAURI__;
  const WebviewWindow = tauri?.webviewWindow?.WebviewWindow || tauri?.window?.WebviewWindow;
  if (!WebviewWindow) {
    return false;
  }
  try {
    const label = 'loco-3d-gen-logs';
    const existing = typeof WebviewWindow.getByLabel === 'function'
      ? WebviewWindow.getByLabel(label)
      : null;
    if (existing) {
      existing.show?.();
      existing.setFocus?.();
      return true;
    }
    const logWindow = new WebviewWindow(label, {
      url,
      title: 'LoCo 3D-Gen Logs',
      width: 960,
      height: 720,
      resizable: true
    });
    if (typeof logWindow.once === 'function') {
      logWindow.once('tauri://error', (event) => {
        addLog('error', 'Failed to open logs window', event);
        showToast('Failed to open logs window.');
      });
    }
    return true;
  } catch (error) {
    addLog('warn', 'Failed to open logs window', error);
    return false;
  }
}

function openLogsPage() {
  const url = 'logs.html';
  addLog('info', 'Opening logs page');
  if (openLogsWindowWithTauri(url)) {
    return;
  }
  const opened = window.open(url, 'loco-3d-gen-logs', 'noopener');
  if (!opened) {
    addLog('warn', 'Logs window blocked');
    showToast('Unable to open logs window.');
  }
}

async function initNativeMenuListener() {
  const tauri = window.__TAURI__;
  if (!tauri) {
    console.warn('Tauri API not available');
    return;
  }

  const eventModule = tauri.event;
  if (!eventModule || typeof eventModule.listen !== 'function') {
    console.warn('Tauri event module not available');
    return;
  }

  try {
    await eventModule.listen('menu-action', (event) => {
      const action = typeof event.payload === 'string' ? event.payload : event.payload?.action;
      if (!action) {
        return;
      }
      switch (action) {
        case 'menu_settings':
          openSettings();
          break;
        case 'menu_logs':
          openLogsPage();
          break;
        case 'menu_import':
          if (importFileInput) {
            importFileInput.click();
          }
          break;
        case 'menu_export_glb':
          exportMesh('glb');
          break;
        case 'menu_export_stl':
          exportMesh('stl');
          break;
        default:
          break;
      }
    });
    console.log('Menu listener initialized');
  } catch (error) {
    console.warn('Failed to set up menu listener:', error);
  }
}

function closeSettings() {
  if (!settingsOverlay) {
    return;
  }
  settingsOverlay.classList.remove('visible');
  settingsOverlay.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('settings-open');
}

function syncSettingsForm() {
  if (!settingsForm) {
    return;
  }
  if (settingsServerInput) {
    settingsServerInput.value = serverInput.value.trim() || DEFAULT_SETTINGS.serverUrl;
  }
  if (settingsWorkspaceInput) {
    settingsWorkspaceInput.value = workspaceInput.value.trim();
  }
  if (settingsTokenInput) {
    settingsTokenInput.value = tokenInput.value.trim();
  }
  if (settingsAutoConnect) {
    settingsAutoConnect.checked = state.autoConnect;
  }
  if (settingsAutoReconnect) {
    settingsAutoReconnect.checked = state.autoReconnect;
  }
  if (settingsAutoApprove) {
    settingsAutoApprove.checked = state.autoApprove;
  }
  if (settingsGridToggle) {
    settingsGridToggle.checked = state.gridVisible;
  }
  if (settingsWireframeToggle) {
    settingsWireframeToggle.checked = state.wireframe;
  }
  if (settingsLightingSelect) {
    settingsLightingSelect.value = state.lightingPreset;
  }
}

function resetSettingsForm() {
  if (!settingsForm) {
    return;
  }
  if (settingsServerInput) {
    settingsServerInput.value = DEFAULT_SETTINGS.serverUrl;
  }
  if (settingsWorkspaceInput) {
    settingsWorkspaceInput.value = DEFAULT_SETTINGS.workspacePath;
  }
  if (settingsTokenInput) {
    settingsTokenInput.value = DEFAULT_SETTINGS.token;
  }
  if (settingsAutoConnect) {
    settingsAutoConnect.checked = DEFAULT_SETTINGS.autoConnect;
  }
  if (settingsAutoReconnect) {
    settingsAutoReconnect.checked = DEFAULT_SETTINGS.autoReconnect;
  }
  if (settingsAutoApprove) {
    settingsAutoApprove.checked = DEFAULT_SETTINGS.autoApprove;
  }
  if (settingsGridToggle) {
    settingsGridToggle.checked = DEFAULT_SETTINGS.gridVisible;
  }
  if (settingsWireframeToggle) {
    settingsWireframeToggle.checked = DEFAULT_SETTINGS.wireframe;
  }
  if (settingsLightingSelect) {
    settingsLightingSelect.value = DEFAULT_SETTINGS.lightingPreset;
  }
}

function applySettingsFromForm() {
  if (!settingsForm) {
    return;
  }
  const serverUrl = settingsServerInput?.value.trim() || DEFAULT_SETTINGS.serverUrl;
  const workspacePath = settingsWorkspaceInput?.value.trim() || DEFAULT_SETTINGS.workspacePath;
  const token = settingsTokenInput?.value.trim() || DEFAULT_SETTINGS.token;

  serverInput.value = serverUrl;
  workspaceInput.value = workspacePath;
  tokenInput.value = token;

  if (settingsAutoConnect) {
    state.autoConnect = settingsAutoConnect.checked;
  }
  if (settingsAutoReconnect) {
    state.autoReconnect = settingsAutoReconnect.checked;
    if (!state.autoReconnect) {
      stopReconnect();
    }
  }
  if (settingsAutoApprove) {
    state.autoApprove = settingsAutoApprove.checked;
  }

  if (settingsGridToggle) {
    applyGridVisibility(settingsGridToggle.checked);
  }
  if (settingsWireframeToggle) {
    applyWireframeState(settingsWireframeToggle.checked);
  }
  if (settingsLightingSelect) {
    applyLightingPreset(settingsLightingSelect.value);
  }

  saveConfig();
}

function showError(message) {
  addLog('error', message);
  if (!errorBanner || !errorBannerText) {
    addMessage('assistant', message);
    return;
  }
  errorBannerText.textContent = message;
  errorBanner.classList.add('visible');
}

function clearError() {
  if (!errorBanner) {
    return;
  }
  errorBanner.classList.remove('visible');
}

function setStatus(label) {
  const labels = ['online', 'offline', 'connecting', 'reconnecting'];
  statusPill.textContent = label;
  labels.forEach((item) => statusPill.classList.toggle(item, item === label));
  if (statusPillDup) {
    statusPillDup.textContent = label;
    labels.forEach((item) => statusPillDup.classList.toggle(item, item === label));
  }
}

function setConnectButton(stateLabel) {
  if (!connectBtn) {
    return;
  }
  const labelMap = {
    idle: 'Connect',
    connecting: 'Connecting...',
    online: 'Reconnect',
    reconnecting: 'Reconnecting...',
    offline: 'Reconnect'
  };
  connectBtn.textContent = labelMap[stateLabel] || 'Connect';
  connectBtn.disabled = stateLabel === 'connecting' || stateLabel === 'reconnecting';
}

function saveConfig() {
  localStorage.setItem(STORAGE_CONFIG_KEY, JSON.stringify({
    serverUrl: serverInput.value.trim(),
    workspacePath: workspaceInput.value.trim(),
    token: tokenInput.value.trim(),
    autoConnect: state.autoConnect,
    autoReconnect: state.autoReconnect,
    autoApprove: state.autoApprove
  }));
}

function loadConfig() {
  const raw = localStorage.getItem(STORAGE_CONFIG_KEY);
  if (!raw) {
    serverInput.value = DEFAULT_SETTINGS.serverUrl;
    workspaceInput.value = DEFAULT_SETTINGS.workspacePath;
    tokenInput.value = DEFAULT_SETTINGS.token;
    state.autoConnect = DEFAULT_SETTINGS.autoConnect;
    state.autoReconnect = DEFAULT_SETTINGS.autoReconnect;
    state.autoApprove = DEFAULT_SETTINGS.autoApprove;
    return;
  }

  try {
    const config = JSON.parse(raw);
    serverInput.value = config.serverUrl || DEFAULT_SETTINGS.serverUrl;
    workspaceInput.value = config.workspacePath || DEFAULT_SETTINGS.workspacePath;
    tokenInput.value = config.token || DEFAULT_SETTINGS.token;
    state.autoConnect = typeof config.autoConnect === 'boolean'
      ? config.autoConnect
      : DEFAULT_SETTINGS.autoConnect;
    state.autoReconnect = typeof config.autoReconnect === 'boolean'
      ? config.autoReconnect
      : DEFAULT_SETTINGS.autoReconnect;
    state.autoApprove = typeof config.autoApprove === 'boolean'
      ? config.autoApprove
      : DEFAULT_SETTINGS.autoApprove;
  } catch {
    serverInput.value = DEFAULT_SETTINGS.serverUrl;
    workspaceInput.value = DEFAULT_SETTINGS.workspacePath;
    tokenInput.value = DEFAULT_SETTINGS.token;
    state.autoConnect = DEFAULT_SETTINGS.autoConnect;
    state.autoReconnect = DEFAULT_SETTINGS.autoReconnect;
    state.autoApprove = DEFAULT_SETTINGS.autoApprove;
  }
}

function schedulePersist() {
  if (state.persistTimer) {
    return;
  }
  state.persistTimer = setTimeout(() => {
    state.persistTimer = null;
    persistState();
  }, 350);
}

function persistState() {
  const messages = {};
  for (const [sessionId, entries] of state.messagesBySession.entries()) {
    messages[sessionId] = entries;
  }
  const payload = {
    sessions: state.sessions,
    sessionId: state.sessionId,
    messages,
    promptHistory: state.promptHistory,
    wireframe: state.wireframe,
    gridVisible: state.gridVisible,
    lightingPreset: state.lightingPreset
  };
  try {
    localStorage.setItem(STORAGE_STATE_KEY, JSON.stringify(payload));
  } catch (error) {
    console.warn('Failed to persist state', error);
  }
}

function loadState() {
  const raw = localStorage.getItem(STORAGE_STATE_KEY);
  if (!raw) {
    return;
  }
  try {
    const payload = JSON.parse(raw);
    if (Array.isArray(payload.sessions)) {
      state.sessions = payload.sessions;
    }
    if (payload.sessionId) {
      state.sessionId = payload.sessionId;
    }
    if (payload.messages && typeof payload.messages === 'object') {
      state.messagesBySession = new Map(Object.entries(payload.messages));
    }
    if (Array.isArray(payload.promptHistory)) {
      state.promptHistory = payload.promptHistory.slice(0, PROMPT_HISTORY_LIMIT);
    }
    if (typeof payload.wireframe === 'boolean') {
      state.wireframe = payload.wireframe;
    }
    if (typeof payload.gridVisible === 'boolean') {
      state.gridVisible = payload.gridVisible;
    }
    if (payload.lightingPreset && LIGHTING_PRESETS[payload.lightingPreset]) {
      state.lightingPreset = payload.lightingPreset;
    }
  } catch (error) {
    console.warn('Failed to restore state', error);
  }
}

function getSessionMessages(sessionId) {
  if (!sessionId) {
    return [];
  }
  if (!state.messagesBySession.has(sessionId)) {
    state.messagesBySession.set(sessionId, []);
  }
  return state.messagesBySession.get(sessionId);
}

function renderMessage(role, content) {
  const messageEl = document.createElement('div');
  messageEl.className = `message ${role}`;
  messageEl.textContent = content;
  messagesEl.appendChild(messageEl);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return messageEl;
}

function setThinkingCollapsed(collapsed) {
  state.thinkingCollapsed = collapsed;
  if (!state.thinkingEl) {
    return;
  }
  state.thinkingEl.classList.toggle('is-collapsed', collapsed);
  const toggle = state.thinkingEl.querySelector('.thinking-toggle');
  if (toggle) {
    toggle.textContent = collapsed ? 'Expand' : 'Collapse';
    toggle.setAttribute('aria-expanded', String(!collapsed));
  }
}

function resetThinkingCard() {
  state.thinkingBuffer = '';
  state.thinkingCollapsed = false;
  if (state.thinkingEl) {
    state.thinkingEl.remove();
  }
  state.thinkingEl = null;
  state.thinkingContentEl = null;
}

function ensureThinkingCard() {
  if (state.thinkingEl || !messagesEl) {
    return;
  }
  const card = document.createElement('div');
  card.className = 'thinking-card';

  const header = document.createElement('div');
  header.className = 'thinking-header';

  const title = document.createElement('span');
  title.className = 'thinking-title';
  title.textContent = 'Thinking';

  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.className = 'ghost-btn thinking-toggle';
  toggle.textContent = 'Collapse';
  toggle.setAttribute('aria-expanded', 'true');
  toggle.addEventListener('click', () => {
    setThinkingCollapsed(!state.thinkingCollapsed);
  });

  header.appendChild(title);
  header.appendChild(toggle);

  const body = document.createElement('pre');
  body.className = 'thinking-body';

  card.appendChild(header);
  card.appendChild(body);
  messagesEl.appendChild(card);

  state.thinkingEl = card;
  state.thinkingContentEl = body;
}

function updateThinkingCard(message) {
  if (!message || !messagesEl) {
    return;
  }
  ensureThinkingCard();
  const next = String(message);
  if (!state.thinkingBuffer) {
    state.thinkingBuffer = next;
  } else if (next.startsWith(state.thinkingBuffer)) {
    state.thinkingBuffer = next;
  } else {
    state.thinkingBuffer = `${state.thinkingBuffer}\n${next}`;
  }
  if (state.thinkingContentEl) {
    state.thinkingContentEl.textContent = state.thinkingBuffer;
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function renderMessages(sessionId) {
  messagesEl.innerHTML = '';
  resetThinkingCard();
  const messages = getSessionMessages(sessionId);
  for (const message of messages) {
    renderMessage(message.role, message.content);
  }
}

function addMessage(role, content) {
  if (!state.sessionId) {
    return null;
  }
  const messages = getSessionMessages(state.sessionId);
  const entry = { role, content };
  messages.push(entry);
  schedulePersist();
  return renderMessage(role, content);
}

function renderToolCard(kind, event) {
  if (!messagesEl) {
    return;
  }
  const toolName = event?.tool || event?.command || 'tool';
  const detailsPayload = kind === 'tool_result'
    ? (event?.result ?? {})
    : (event?.arguments ?? event ?? {});

  // Don't render empty tool cards
  const detailsText = formatLogDetails(detailsPayload);
  if (!detailsText || detailsText === '{}' || detailsText === 'null') {
    return;
  }

  const card = document.createElement('details');
  card.className = `tool-card ${kind}`;
  card.open = false;

  const summary = document.createElement('summary');
  summary.className = 'tool-summary';
  const label = kind === 'tool_result' ? 'Result' : 'Tool';
  summary.textContent = `${label}: ${toolName}`;

  const body = document.createElement('pre');
  body.className = 'tool-details';
  body.textContent = detailsText;

  card.appendChild(summary);
  card.appendChild(body);
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function appendAssistantDelta(delta) {
  if (!state.sessionId) {
    return;
  }
  const messages = getSessionMessages(state.sessionId);
  if (!state.currentAssistantEl) {
    const entry = { role: 'assistant', content: '' };
    messages.push(entry);
    state.currentAssistantIndex = messages.length - 1;
    state.currentAssistantEl = renderMessage('assistant', '');
  }
  state.assistantBuffer += delta;
  state.currentAssistantEl.textContent = state.assistantBuffer;
  if (state.currentAssistantIndex !== null) {
    messages[state.currentAssistantIndex].content = state.assistantBuffer;
  }
  messagesEl.scrollTop = messagesEl.scrollHeight;
  schedulePersist();
}

function finalizeAssistantMessage(message) {
  if (!state.sessionId) {
    return;
  }

  const messages = getSessionMessages(state.sessionId);
  if (!state.currentAssistantEl) {
    const entry = { role: 'assistant', content: message };
    messages.push(entry);
    state.currentAssistantEl = renderMessage('assistant', message);
    state.currentAssistantIndex = messages.length - 1;
  } else {
    state.currentAssistantEl.textContent = message;
    if (state.currentAssistantIndex !== null) {
      messages[state.currentAssistantIndex].content = message;
    }
  }

  schedulePersist();

  const meshPayload = extractMeshPayload(message);
  if (meshPayload) {
    setMeshStatus('loading', 'Rendering mesh...');
    renderMesh(meshPayload);
  } else {
    setMeshStatus('idle', 'Waiting for mesh JSON...');
  }

  state.currentAssistantEl = null;
  state.currentAssistantIndex = null;
  state.assistantBuffer = '';
}

async function registerWorkspace(serverUrl, token, workspacePath) {
  addLog('info', 'Registering workspace', { serverUrl, workspacePath });
  const response = await fetchWithTimeout(`${serverUrl}/v1/workspaces/register`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({
      path: workspacePath,
      name: '3d-gen',
      module_id: MODULE_ID
    })
  });

  if (!response.ok) {
    addLog('error', 'Workspace registration failed', {
      status: response.status,
      statusText: response.statusText
    });
    throw new Error(`Workspace registration failed: ${response.statusText}`);
  }

  const payload = await response.json();
  addLog('info', 'Workspace registered', { workspaceId: payload.id });
  return payload;
}

async function createSession(serverUrl, token, workspaceId) {
  addLog('info', 'Creating session', { serverUrl, workspaceId });
  const response = await fetchWithTimeout(`${serverUrl}/v1/sessions`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({
      workspace_id: workspaceId
    })
  });

  if (!response.ok) {
    addLog('error', 'Session creation failed', {
      status: response.status,
      statusText: response.statusText
    });
    throw new Error(`Session creation failed: ${response.statusText}`);
  }

  const payload = await response.json();
  addLog('info', 'Session created', { sessionId: payload.id });
  return payload;
}

function buildHeaders(token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function fetchWithTimeout(url, options) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  const request = fetch(url, {
    ...options,
    signal: controller.signal
  });
  request.finally(() => clearTimeout(timeout));
  return request;
}

function updateActiveSessionTitle(session) {
  if (!activeSessionTitle) {
    return;
  }
  activeSessionTitle.textContent = session?.title || 'New chat';
}

function renderSessions() {
  if (!sessionListEl) {
    return;
  }
  sessionListEl.innerHTML = '';
  if (!state.sessions.length) {
    const empty = document.createElement('div');
    empty.className = 'session-empty';
    empty.textContent = 'No chats yet. Connect to start.';
    sessionListEl.appendChild(empty);
    return;
  }
  state.sessions.forEach((session) => {
    const item = document.createElement('div');
    item.className = `session-item${session.id === state.sessionId ? ' active' : ''}`;
    const title = document.createElement('div');
    title.className = 'session-title';
    title.textContent = session.title;
    const subtitle = document.createElement('div');
    subtitle.className = 'session-subtitle';
    subtitle.textContent = session.meta || 'Ready';
    item.appendChild(title);
    item.appendChild(subtitle);
    item.addEventListener('click', () => {
      if (session.id !== state.sessionId) {
        switchSession(session.id);
      }
    });
    sessionListEl.appendChild(item);
  });
}

function addSession(session) {
  const entry = {
    id: session.id,
    title: session.title || 'New chat',
    meta: 'Connected'
  };
  state.sessions = [entry, ...state.sessions.filter((item) => item.id !== entry.id)];
  renderSessions();
  schedulePersist();
  return entry;
}

function updateSessionTitleFromMessage(message) {
  if (!message || !state.sessionId) {
    return;
  }
  const session = state.sessions.find((item) => item.id === state.sessionId);
  if (!session || session.title !== 'New chat') {
    return;
  }
  const trimmed = message.replace(/\s+/g, ' ').trim();
  session.title = trimmed.slice(0, 40) || 'New chat';
  renderSessions();
  updateActiveSessionTitle(session);
  schedulePersist();
}

function renderPromptTemplates() {
  if (!promptTemplatesEl) {
    return;
  }
  promptTemplatesEl.innerHTML = '';
  PROMPT_TEMPLATES.forEach((template) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-btn';
    btn.textContent = template.label;
    btn.addEventListener('click', () => {
      insertPrompt(template.text);
    });
    promptTemplatesEl.appendChild(btn);
  });
}

function renderPromptHistory() {
  if (!promptHistoryEl) {
    return;
  }
  promptHistoryEl.innerHTML = '';
  if (!state.promptHistory.length) {
    const empty = document.createElement('span');
    empty.className = 'chip-empty';
    empty.textContent = 'No prompts yet';
    promptHistoryEl.appendChild(empty);
    return;
  }
  state.promptHistory.forEach((prompt) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'chip-btn subtle';
    btn.textContent = prompt;
    btn.title = prompt;
    btn.addEventListener('click', () => {
      insertPrompt(prompt);
    });
    promptHistoryEl.appendChild(btn);
  });
}

function insertPrompt(prompt) {
  messageInput.value = prompt;
  messageInput.focus();
}

function recordPromptHistory(prompt) {
  const trimmed = prompt.replace(/\s+/g, ' ').trim();
  if (!trimmed) {
    return;
  }
  state.promptHistory = [trimmed, ...state.promptHistory.filter((item) => item !== trimmed)];
  state.promptHistory = state.promptHistory.slice(0, PROMPT_HISTORY_LIMIT);
  renderPromptHistory();
  schedulePersist();
}

function stopReconnect() {
  if (state.reconnectTimer) {
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = null;
  }
  state.reconnectAttempts = 0;
}

function scheduleReconnect(reason) {
  if (!state.autoReconnect) {
    showError(reason || 'Connection lost.');
    return;
  }
  if (!state.serverUrl || !state.sessionId) {
    return;
  }
  if (state.reconnectTimer) {
    return;
  }
  state.reconnectAttempts += 1;
  const baseDelay = RECONNECT_BASE_DELAY_MS * Math.pow(2, state.reconnectAttempts - 1);
  const delay = Math.min(baseDelay, RECONNECT_MAX_DELAY_MS);
  const jitter = delay * (Math.random() * 0.2);
  const wait = delay + jitter;
  setStatus('reconnecting');
  setConnectButton('reconnecting');
  showError(reason || 'Connection lost. Reconnecting...');
  addLog('warn', reason || 'Connection lost. Reconnecting...');

  state.reconnectTimer = setTimeout(async () => {
    state.reconnectTimer = null;
    try {
      await openWebSocket(state.serverUrl);
      stopReconnect();
      setStatus('online');
      setConnectButton('online');
      clearError();
    } catch (error) {
      scheduleReconnect('Reconnect failed. Retrying...');
    }
  }, wait);
}

function startPing() {
  stopPing();
  state.pingTimer = setInterval(() => {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
      state.ws.send(JSON.stringify({
        type: 'client.ping',
        timestamp: Date.now()
      }));
    }
  }, PING_INTERVAL_MS);
}

function stopPing() {
  if (state.pingTimer) {
    clearInterval(state.pingTimer);
    state.pingTimer = null;
  }
}

function buildWsUrl(serverUrl, sessionId, token) {
  const url = new URL(serverUrl);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  url.pathname = `/v1/sessions/${sessionId}/stream`;
  url.search = '';
  url.hash = '';
  if (token) {
    url.searchParams.set('token', token);
  }
  return url.toString();
}

function openWebSocket(serverUrl) {
  return new Promise((resolve, reject) => {
    addLog('info', 'Opening WebSocket', {
      serverUrl,
      sessionId: state.sessionId
    });
    const wsUrl = buildWsUrl(serverUrl, state.sessionId, state.token);
    let settled = false;
    const ws = new WebSocket(wsUrl);

    ws.addEventListener('open', () => {
      ws.send(JSON.stringify({
        type: 'client.hello',
        protocol_version: '1.0.0',
        client_info: {
          name: '3d-gen-desktop',
          version: '0.1.0',
          platform: 'tauri'
        }
      }));
      startPing();
      addLog('info', 'WebSocket connected', { sessionId: state.sessionId });
      settled = true;
      resolve();
    });

    ws.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
      } catch (error) {
        console.warn('Failed to parse server message', error);
        addLog('warn', 'Failed to parse server message', { error: error.message });
      }
    });

    ws.addEventListener('close', (event) => {
      stopPing();
      state.ws = null;
      setStreamingState(false);
      addLog('warn', 'WebSocket closed', {
        code: event.code,
        reason: event.reason || '',
        wasClean: event.wasClean
      });
      if (state.intentionalClose) {
        state.intentionalClose = false;
        return;
      }
      setStatus('offline');
      setConnectButton('offline');
      scheduleReconnect('Connection dropped.');
    });

    ws.addEventListener('error', (error) => {
      addLog('error', 'WebSocket error');
      setStreamingState(false);
      if (!settled) {
        settled = true;
        reject(error);
        return;
      }
      showError('WebSocket error.');
    });

    state.ws = ws;
  });
}

function closeWebSocket(intentional = false) {
  if (!state.ws) {
    return;
  }
  addLog('info', 'Closing WebSocket', { intentional });
  state.intentionalClose = intentional;
  stopPing();
  state.ws.close();
  state.ws = null;
  setStreamingState(false);
}

async function switchSession(sessionId) {
  const session = state.sessions.find((item) => item.id === sessionId);
  if (!session) {
    return;
  }
  state.sessionId = sessionId;
  state.currentAssistantEl = null;
  state.currentAssistantIndex = null;
  state.assistantBuffer = '';
  renderMessages(sessionId);
  updateActiveSessionTitle(session);
  renderSessions();
  schedulePersist();

  if (!state.serverUrl || !state.workspaceId) {
    return;
  }

  closeWebSocket(true);

  try {
    setStatus('connecting');
    setConnectButton('connecting');
    await openWebSocket(state.serverUrl);
    setStatus('online');
    setConnectButton('online');
  } catch (error) {
    console.error(error);
    addMessage('assistant', 'Failed to switch session.');
    setStatus('offline');
    setConnectButton('offline');
    setStreamingState(false);
  }
}

async function connect() {
  const serverUrl = serverInput.value.trim() || DEFAULT_SERVER;
  const workspacePath = workspaceInput.value.trim();
  const token = tokenInput.value.trim();

  if (!workspacePath) {
    addMessage('assistant', 'Please provide a workspace path before connecting.');
    addLog('warn', 'Workspace path missing');
    return;
  }

  clearError();
  saveConfig();
  stopReconnect();
  closeWebSocket(true);
  setStatus('connecting');
  setConnectButton('connecting');
  addLog('info', 'Connecting', {
    serverUrl,
    workspacePath,
    hasToken: Boolean(token)
  });

  try {
    const workspace = await registerWorkspace(serverUrl, token, workspacePath);
    const session = await createSession(serverUrl, token, workspace.id);

    state.serverUrl = serverUrl;
    state.token = token;
    state.workspaceId = workspace.id;
    state.sessions = [];
    state.messagesBySession.clear();

    const entry = addSession(session);
    state.sessionId = entry.id;
    updateActiveSessionTitle(entry);
    renderMessages(entry.id);

    await openWebSocket(serverUrl);
    setStatus('online');
    setConnectButton('online');
    clearError();
    schedulePersist();
    addLog('info', 'Connected', { sessionId: state.sessionId });
  } catch (error) {
    console.error(error);
    addMessage('assistant', `Connection failed: ${error.message}`);
    showError(`Connection failed: ${error.message}`);
    setStatus('offline');
    setConnectButton('offline');
    addLog('error', 'Connection failed', { message: error.message });
    setStreamingState(false);
  }
}

async function createNewSession() {
  if (!state.serverUrl || !state.workspaceId) {
    addMessage('assistant', 'Connect to a workspace before creating a new chat.');
    return;
  }

  setStatus('connecting');
  setConnectButton('connecting');
  try {
    const session = await createSession(state.serverUrl, state.token, state.workspaceId);
    const entry = addSession(session);
    await switchSession(entry.id);
  } catch (error) {
    console.error(error);
    addMessage('assistant', `Failed to create session: ${error.message}`);
    showError(`Failed to create session: ${error.message}`);
    setStatus('offline');
    setConnectButton('offline');
    setStreamingState(false);
  }
}

function resetAssistantState() {
  state.currentAssistantEl = null;
  state.currentAssistantIndex = null;
  state.assistantBuffer = '';
}

function sendUserMessage(message) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    addMessage('assistant', 'Not connected. Please connect first.');
    addLog('warn', 'Message send failed: not connected');
    return;
  }

  clearError();
  resetThinkingCard();
  resetAssistantState();
  addMessage('user', message);
  updateSessionTitleFromMessage(message);
  recordPromptHistory(message);
  state.lastPrompt = message;

  state.ws.send(JSON.stringify({
    type: 'client.user_message',
    message,
    context: {
      module_id: MODULE_ID
    }
  }));
  addLog('info', 'User message sent', { length: message.length });
  setStreamingState(true);
}

function sendApprovalResponse(requestId, approved) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    showToast('Not connected. Approval not sent.');
    addLog('error', 'Approval response failed: not connected', { requestId });
    return;
  }
  state.ws.send(JSON.stringify({
    type: 'client.approval_response',
    request_id: requestId,
    approved
  }));
  addLog('info', 'Approval response sent', { requestId, approved });
}

function renderApprovalRequest(payload) {
  if (!messagesEl) {
    return;
  }

  const card = document.createElement('div');
  card.className = 'approval-card';
  card.dataset.requestId = payload.request_id || '';

  const header = document.createElement('div');
  header.className = 'approval-header';
  header.textContent = 'Approval required';

  const message = document.createElement('div');
  message.className = 'approval-message';
  message.textContent = payload.message || `Approve ${payload.tool || 'tool'}?`;

  const details = document.createElement('details');
  details.className = 'approval-details';

  const summary = document.createElement('summary');
  summary.textContent = 'View details';

  const detailsBody = document.createElement('pre');
  detailsBody.className = 'approval-details-body';
  detailsBody.textContent = formatLogDetails(payload.arguments || {});

  details.appendChild(summary);
  details.appendChild(detailsBody);

  const actions = document.createElement('div');
  actions.className = 'approval-actions';

  const approveBtn = document.createElement('button');
  approveBtn.type = 'button';
  approveBtn.className = 'approve';
  approveBtn.textContent = 'Approve';
  approveBtn.addEventListener('click', () => {
    sendApprovalResponse(payload.request_id, true);
    card.remove();
  });

  const rejectBtn = document.createElement('button');
  rejectBtn.type = 'button';
  rejectBtn.className = 'reject';
  rejectBtn.textContent = 'Reject';
  rejectBtn.addEventListener('click', () => {
    sendApprovalResponse(payload.request_id, false);
    card.remove();
  });

  actions.appendChild(approveBtn);
  actions.appendChild(rejectBtn);
  card.appendChild(header);
  card.appendChild(message);
  card.appendChild(details);
  card.appendChild(actions);

  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function handleServerEvent(event) {
  switch (event.type) {
    case 'server.hello':
      addLog('info', 'Server hello', event.server_info || {});
      break;
    case 'assistant.message_delta':
      appendAssistantDelta(event.delta || '');
      setStreamingState(true);
      break;
    case 'assistant.message_final':
      finalizeAssistantMessage(event.message || '');
      addLog('info', 'Assistant message final', { length: (event.message || '').length });
      setStreamingState(false);
      break;
    case 'assistant.thinking':
      updateThinkingCard(event.message || 'Thinking...');
      break;
    case 'assistant.tool_use':
      renderToolCard('tool_use', event);
      addLog('info', 'Tool use', { tool: event.tool, arguments: event.arguments });
      if (event.tool === 'write_file' && event.arguments?.content) {
        const meshPayload = extractMeshPayload(event.arguments.content);
        if (meshPayload) {
          setMeshStatus('loading', 'Rendering mesh from file...');
          renderMesh(meshPayload);
        }
      }
      break;
    case 'assistant.tool_result':
      renderToolCard('tool_result', event);
      addLog('info', 'Tool result', { tool: event.tool, result: event.result });
      break;
    case 'tool.request_approval':
    case 'command.request_approval':
      addLog('warn', 'Approval required', {
        requestId: event.request_id,
        tool: event.tool,
        arguments: event.arguments
      });
      if (state.autoApprove) {
        addLog('info', 'Auto-approving request', { requestId: event.request_id });
        sendApprovalResponse(event.request_id, true);
        renderToolCard('tool_use', {
          tool: event.tool,
          arguments: event.arguments,
          autoApproved: true
        });
      } else {
        renderApprovalRequest(event);
      }
      break;
    case 'server.error':
      addMessage('assistant', `Error: ${event.error?.message || 'Unknown error'}`);
      showError(event.error?.message || 'Server error.');
      setStreamingState(false);
      break;
    case 'server.pong':
      break;
    default:
      break;
  }
}

let renderer;
let scene;
let camera;
let controls;
let activeMesh;
let gridHelper;
let axesHelper;
let ambientLight;
let keyLight;
let fillLight;

function initViewer() {
  const canvas = document.getElementById('viewer');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);

  scene = new THREE.Scene();
  scene.background = new THREE.Color(LIGHTING_PRESETS[state.lightingPreset].background);

  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
  camera.position.set(2.5, 1.8, 2.8);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
  keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
  keyLight.position.set(4, 6, 4);
  fillLight = new THREE.DirectionalLight(0xffffff, 0.4);
  fillLight.position.set(-3, 2, -2);

  scene.add(ambientLight, keyLight, fillLight);

  gridHelper = new THREE.GridHelper(10, 20, 0x1c2a3b, 0x111822);
  gridHelper.position.y = -0.01;
  gridHelper.visible = state.gridVisible;
  scene.add(gridHelper);

  axesHelper = new THREE.AxesHelper(0.5);
  axesHelper.visible = false;
  scene.add(axesHelper);

  applyLightingPreset(state.lightingPreset);
  resizeRenderer();
  animate();
}

function applyLightingPreset(presetId) {
  const preset = LIGHTING_PRESETS[presetId] || LIGHTING_PRESETS.studio;
  state.lightingPreset = presetId;
  ambientLight.intensity = preset.ambient;
  keyLight.intensity = preset.key;
  fillLight.intensity = preset.fill;
  keyLight.position.set(...preset.keyPos);
  fillLight.position.set(...preset.fillPos);
  scene.background = new THREE.Color(preset.background);
  if (lightingSelect) {
    lightingSelect.value = presetId;
  }
  if (settingsLightingSelect) {
    settingsLightingSelect.value = presetId;
  }
  schedulePersist();
}

function resizeRenderer() {
  const canvas = renderer.domElement;
  const { clientWidth, clientHeight } = canvas.parentElement;
  renderer.setSize(clientWidth, clientHeight, false);
  camera.aspect = clientWidth / clientHeight;
  camera.updateProjectionMatrix();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

function setMeshStatus(statusLabel, detail) {
  meshStatus.textContent = statusLabel;
  meshStatus.dataset.state = statusLabel;
  if (detail) {
    viewerStatus.textContent = detail;
  }
  if (statusLabel === 'loading') {
    setViewerOverlay('Rendering mesh...', 'Parsing mesh data');
  }
  if (statusLabel === 'idle' && !activeMesh) {
    setViewerOverlay('Send a prompt to generate a mesh.', 'Drop a mesh file to import.');
  }
}

function setViewerOverlay(message, hint, isError = false) {
  if (viewerOverlayText) {
    viewerOverlayText.textContent = message;
  }
  if (viewerOverlayHint) {
    viewerOverlayHint.textContent = hint || '';
  }
  viewerOverlay.classList.toggle('is-error', isError);
  viewerOverlay.classList.remove('hidden');
}

function hideViewerOverlay() {
  viewerOverlay.classList.add('hidden');
  viewerOverlay.classList.remove('is-error');
}

function normalizeVertices(vertices) {
  if (!Array.isArray(vertices) || !vertices.length) {
    return null;
  }
  if (Array.isArray(vertices[0])) {
    return vertices;
  }
  if (typeof vertices[0] === 'number') {
    if (vertices.length % 3 !== 0) {
      return null;
    }
    const result = [];
    for (let i = 0; i < vertices.length; i += 3) {
      result.push([vertices[i], vertices[i + 1], vertices[i + 2]]);
    }
    return result;
  }
  return null;
}

function normalizeTriangles(triangles) {
  if (!Array.isArray(triangles) || !triangles.length) {
    return null;
  }
  if (Array.isArray(triangles[0])) {
    const flattened = [];
    for (const tri of triangles) {
      if (!Array.isArray(tri) || tri.length < 3) {
        return null;
      }
      flattened.push(tri[0], tri[1], tri[2]);
    }
    return flattened;
  }
  if (typeof triangles[0] === 'number') {
    return triangles;
  }
  return null;
}

function normalizeNormals(normals, vertexCount) {
  if (!normals) {
    return null;
  }
  const normalized = normalizeVertices(normals);
  if (!normalized || normalized.length !== vertexCount) {
    return null;
  }
  return normalized;
}

function validateVertexValues(vertices) {
  for (const vertex of vertices) {
    if (!Array.isArray(vertex) || vertex.length < 3) {
      return false;
    }
    for (let i = 0; i < 3; i += 1) {
      if (!Number.isFinite(vertex[i])) {
        return false;
      }
    }
  }
  return true;
}

function validateIndexValues(indices) {
  for (const index of indices) {
    if (!Number.isFinite(index) || !Number.isInteger(index)) {
      return false;
    }
  }
  return true;
}

function getIndexBounds(indices) {
  let min = Infinity;
  let max = -Infinity;
  for (const index of indices) {
    if (index < min) {
      min = index;
    }
    if (index > max) {
      max = index;
    }
  }
  return { min, max };
}

function validateMesh(mesh) {
  if (!mesh || typeof mesh !== 'object') {
    return { ok: false, reason: 'Mesh payload missing.' };
  }
  const vertices = normalizeVertices(mesh.vertices);
  if (!vertices || !vertices.length) {
    return { ok: false, reason: 'Vertices are missing or invalid.' };
  }
  if (!validateVertexValues(vertices)) {
    return { ok: false, reason: 'Vertex values are invalid.' };
  }
  if (vertices.length > MAX_VERTICES) {
    return { ok: false, reason: `Mesh too large (${vertices.length} vertices).` };
  }

  const indices = normalizeTriangles(mesh.triangles);
  if (!indices || !indices.length) {
    return { ok: false, reason: 'Triangles are missing or invalid.' };
  }
  if (indices.length % 3 !== 0) {
    return { ok: false, reason: 'Triangle indices are not a multiple of 3.' };
  }
  if (!validateIndexValues(indices)) {
    return { ok: false, reason: 'Triangle indices are invalid.' };
  }

  const bounds = getIndexBounds(indices);
  if (bounds.min < 0 || bounds.max >= vertices.length) {
    return { ok: false, reason: 'Triangle indices exceed vertex bounds.' };
  }

  const triangleTotal = indices.length / 3;
  if (triangleTotal > MAX_TRIANGLES) {
    return { ok: false, reason: `Mesh too dense (${triangleTotal} triangles).` };
  }

  const normals = normalizeNormals(mesh.normals, vertices.length);

  return {
    ok: true,
    mesh: {
      vertices,
      indices,
      normals,
      maxIndex: bounds.max
    }
  };
}

function handleMeshError(reason) {
  setMeshStatus('error', 'Mesh rejected');
  setViewerOverlay('Mesh could not be rendered', reason || 'Unsupported mesh payload.', true);
  viewerOverlay.classList.remove('hidden');
  viewerStatus.textContent = 'Mesh rejected';
}

function setActiveObject(object, stats) {
  if (activeMesh) {
    scene.remove(activeMesh);
  }
  activeMesh = object;
  scene.add(object);

  if (stats) {
    state.lastMeshStats = stats;
    vertexCount.textContent = stats.vertices;
    triangleCount.textContent = stats.triangles;
  }

  focusObject(object);
  hideViewerOverlay();
  setMeshStatus('ready', 'Mesh loaded');
  schedulePersist();
}

function focusObject(object) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z) || 1;
  const distance = maxDim * 2.2;
  camera.position.set(center.x + distance, center.y + distance * 0.6, center.z + distance);
  controls.target.copy(center);
  controls.update();
}

function renderMesh(mesh) {
  const validation = validateMesh(mesh);
  if (!validation.ok) {
    handleMeshError(validation.reason);
    addMessage('assistant', `Mesh rejected: ${validation.reason}`);
    return;
  }

  const { vertices, indices, normals } = validation.mesh;
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(vertices.flat());
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

  const indexArray = validation.mesh.maxIndex > 65535 ? new Uint32Array(indices) : new Uint16Array(indices);
  geometry.setIndex(new THREE.BufferAttribute(indexArray, 1));

  if (normals) {
    const normalArray = new Float32Array(normals.flat());
    geometry.setAttribute('normal', new THREE.BufferAttribute(normalArray, 3));
  } else {
    geometry.computeVertexNormals();
  }

  const material = new THREE.MeshStandardMaterial({
    color: 0xffb36b,
    roughness: 0.35,
    metalness: 0.1,
    wireframe: state.wireframe
  });

  const newMesh = new THREE.Mesh(geometry, material);
  state.lastMeshPayload = mesh;

  setActiveObject(newMesh, {
    vertices: vertices.length,
    triangles: Math.floor(indices.length / 3)
  });
}

function updateMeshStatsFromObject(object) {
  let vertexTotal = 0;
  let triangleTotal = 0;
  object.traverse((child) => {
    if (child.isMesh) {
      const geometry = child.geometry;
      const position = geometry.getAttribute('position');
      if (position) {
        vertexTotal += position.count;
        const index = geometry.index;
        if (index) {
          triangleTotal += index.count / 3;
        } else {
          triangleTotal += position.count / 3;
        }
      }
    }
  });
  return {
    vertices: Math.floor(vertexTotal),
    triangles: Math.floor(triangleTotal)
  };
}

function applyMeshMaterial(object) {
  object.traverse((child) => {
    if (child.isMesh) {
      child.material = new THREE.MeshStandardMaterial({
        color: 0xffb36b,
        roughness: 0.35,
        metalness: 0.1,
        wireframe: state.wireframe
      });
    }
  });
}

function renderImportedObject(object) {
  applyMeshMaterial(object);
  const stats = updateMeshStatsFromObject(object);
  if (stats.vertices > MAX_VERTICES || stats.triangles > MAX_TRIANGLES) {
    handleMeshError('Imported mesh exceeds size limits.');
    addMessage('assistant', 'Imported mesh rejected: size limits exceeded.');
    return;
  }
  setActiveObject(object, stats);
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function exportMesh(format) {
  if (!activeMesh) {
    showToast('No mesh to export.');
    return;
  }

  if (format === 'glb') {
    const exporter = new GLTFExporter();
    exporter.parse(
      activeMesh,
      (result) => {
        const blob = new Blob([result], { type: 'model/gltf-binary' });
        downloadBlob(blob, `mesh-${Date.now()}.glb`);
        showToast('GLB exported.');
      },
      { binary: true }
    );
    return;
  }

  if (format === 'stl') {
    const exporter = new STLExporter();
    const result = exporter.parse(activeMesh, { binary: true });
    const blob = new Blob([result], { type: 'model/stl' });
    downloadBlob(blob, `mesh-${Date.now()}.stl`);
    showToast('STL exported.');
  }
}

async function handleMeshFile(file) {
  if (!file) {
    return;
  }
  const ext = file.name.split('.').pop().toLowerCase();
  setMeshStatus('loading', `Importing ${file.name}...`);

  try {
    if (ext === 'json') {
      const text = await file.text();
      const parsed = JSON.parse(text);
      const payload = extractMeshPayload(text) || parsed.mesh || parsed;
      if (!payload) {
        throw new Error('No mesh data found in JSON.');
      }
      renderMesh(payload);
      showToast('Mesh imported.');
      return;
    }

    if (ext === 'stl') {
      const buffer = await file.arrayBuffer();
      const loader = new STLLoader();
      const geometry = loader.parse(buffer);
      const mesh = new THREE.Mesh(geometry);
      renderImportedObject(mesh);
      showToast('STL imported.');
      return;
    }

    if (ext === 'glb' || ext === 'gltf') {
      const loader = new GLTFLoader();
      if (ext === 'gltf') {
        const text = await file.text();
        loader.parse(text, '', (gltf) => {
          const sceneObject = gltf.scene || gltf.scenes?.[0];
          if (!sceneObject) {
            handleMeshError('GLTF file has no scene.');
            return;
          }
          renderImportedObject(sceneObject);
          showToast('GLTF imported.');
        }, (error) => {
          console.error(error);
          handleMeshError('Failed to import GLTF.');
        });
        return;
      }
      const buffer = await file.arrayBuffer();
      loader.parse(buffer, '', (gltf) => {
        const sceneObject = gltf.scene || gltf.scenes?.[0];
        if (!sceneObject) {
          handleMeshError('GLB file has no scene.');
          return;
        }
        renderImportedObject(sceneObject);
        showToast('GLB imported.');
      }, (error) => {
        console.error(error);
        handleMeshError('Failed to import GLB.');
      });
      return;
    }

    throw new Error('Unsupported file type.');
  } catch (error) {
    handleMeshError(error.message || 'Import failed.');
  }
}

function handleDropEvent(event) {
  event.preventDefault();
  dropOverlay.classList.remove('visible');
  const file = event.dataTransfer?.files?.[0];
  if (file) {
    handleMeshFile(file);
  }
}

function copyMeshStats() {
  if (!state.lastMeshStats) {
    showToast('No mesh stats to copy.');
    return;
  }
  const text = `Vertices: ${state.lastMeshStats.vertices}\nTriangles: ${state.lastMeshStats.triangles}`;
  copyTextToClipboard(text, 'Mesh stats copied.');
}

function copyLastPrompt() {
  if (!state.lastPrompt) {
    showToast('No prompt to copy.');
    return;
  }
  copyTextToClipboard(state.lastPrompt, 'Prompt copied.');
}

async function copyTextToClipboard(text, successMessage) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    } else {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';
      textarea.style.opacity = '0';
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      textarea.remove();
    }
    showToast(successMessage);
  } catch (error) {
    showToast('Copy failed.');
  }
}

function applyGridVisibility(isVisible, options = {}) {
  const { persist = true } = options;
  state.gridVisible = isVisible;
  if (gridHelper) {
    gridHelper.visible = state.gridVisible;
  }
  if (toggleGridBtn) {
    toggleGridBtn.classList.toggle('is-active', state.gridVisible);
    toggleGridBtn.setAttribute('aria-pressed', String(state.gridVisible));
  }
  if (settingsGridToggle) {
    settingsGridToggle.checked = state.gridVisible;
  }
  if (persist) {
    schedulePersist();
  }
}

function applyWireframeState(enabled, options = {}) {
  const { persist = true } = options;
  state.wireframe = enabled;
  if (activeMesh) {
    activeMesh.traverse((child) => {
      if (child.isMesh) {
        child.material.wireframe = state.wireframe;
      }
    });
  }
  if (wireframeBtn) {
    wireframeBtn.classList.toggle('is-active', state.wireframe);
    wireframeBtn.setAttribute('aria-pressed', String(state.wireframe));
  }
  if (settingsWireframeToggle) {
    settingsWireframeToggle.checked = state.wireframe;
  }
  if (persist) {
    schedulePersist();
  }
}

function toggleGrid() {
  applyGridVisibility(!state.gridVisible);
}

if (connectBtn) {
  connectBtn.addEventListener('click', () => {
    connect();
  });
}

if (newSessionBtn) {
  newSessionBtn.addEventListener('click', () => {
    createNewSession();
  });
}

if (settingsOpenBtn) {
  settingsOpenBtn.addEventListener('click', () => {
    openSettings();
  });
}

if (logsOpenBtn) {
  logsOpenBtn.addEventListener('click', () => {
    openLogsPage();
  });
}

if (settingsCloseBtn) {
  settingsCloseBtn.addEventListener('click', () => {
    closeSettings();
  });
}

if (settingsOverlay) {
  settingsOverlay.addEventListener('click', (event) => {
    if (event.target === settingsOverlay) {
      closeSettings();
    }
  });
}

if (settingsForm) {
  settingsForm.addEventListener('submit', (event) => {
    event.preventDefault();
    applySettingsFromForm();
    showToast('Settings saved.');
    closeSettings();
  });
}

if (settingsResetBtn) {
  settingsResetBtn.addEventListener('click', () => {
    resetSettingsForm();
    showToast('Defaults restored. Click save to apply.');
  });
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  if (state.isStreaming) {
    cancelGeneration();
    return;
  }
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }
  messageInput.value = '';
  sendUserMessage(message);
});

messageInput.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
    event.preventDefault();
    if (state.isStreaming) {
      cancelGeneration();
      return;
    }
    const message = messageInput.value.trim();
    if (!message) {
      return;
    }
    messageInput.value = '';
    sendUserMessage(message);
  }
});

resetViewBtn.addEventListener('click', () => {
  controls.reset();
});

wireframeBtn.addEventListener('click', () => {
  applyWireframeState(!state.wireframe);
});

if (toggleGridBtn) {
  toggleGridBtn.addEventListener('click', () => {
    toggleGrid();
  });
}

if (lightingSelect) {
  lightingSelect.addEventListener('change', (event) => {
    applyLightingPreset(event.target.value);
  });
}

if (importBtn && importFileInput) {
  importBtn.addEventListener('click', () => {
    importFileInput.click();
  });
  importFileInput.addEventListener('change', (event) => {
    const file = event.target.files?.[0];
    handleMeshFile(file);
    importFileInput.value = '';
  });
}

if (exportGlbBtn) {
  exportGlbBtn.addEventListener('click', () => exportMesh('glb'));
}

if (exportStlBtn) {
  exportStlBtn.addEventListener('click', () => exportMesh('stl'));
}

if (copyMeshStatsBtn) {
  copyMeshStatsBtn.addEventListener('click', () => copyMeshStats());
}

if (copyPromptBtn) {
  copyPromptBtn.addEventListener('click', () => copyLastPrompt());
}

if (viewerSurface) {
  viewerSurface.addEventListener('dragenter', (event) => {
    event.preventDefault();
    dropOverlay.classList.add('visible');
    setViewerOverlay('Drop a mesh file', 'Accepts JSON, GLB, GLTF, STL');
  });
  viewerSurface.addEventListener('dragover', (event) => {
    event.preventDefault();
  });
  viewerSurface.addEventListener('dragleave', () => {
    dropOverlay.classList.remove('visible');
  });
  viewerSurface.addEventListener('drop', handleDropEvent);
}

if (errorBannerDismiss) {
  errorBannerDismiss.addEventListener('click', () => {
    clearError();
  });
}

window.addEventListener('resize', () => {
  applyLayoutFromRatio(state.layoutRatio ?? 0.55);
});

window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    if (settingsOverlay?.classList.contains('visible')) {
      event.preventDefault();
      closeSettings();
      return;
    }
  }
  const target = event.target;
  if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA')) {
    return;
  }
  const key = event.key.toLowerCase();
  if (event.shiftKey && key === 'r') {
    resetViewBtn.click();
  }
  if (event.shiftKey && key === 'w') {
    wireframeBtn.click();
  }
  if (event.shiftKey && key === 'g' && toggleGridBtn) {
    toggleGridBtn.click();
  }
});

window.addEventListener('error', (event) => {
  addLog('error', 'Window error', {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno
  });
});

window.addEventListener('unhandledrejection', (event) => {
  addLog('error', 'Unhandled promise rejection', {
    reason: event.reason
  });
});

window.addEventListener('storage', (event) => {
  if (event.key === LOGS_STORAGE_KEY) {
    loadLogs({ replace: true });
  }
});

loadLogs();
loadLayout();
loadConfig();
loadState();
setConnectButton('idle');
updateSendButton();
renderPromptTemplates();
renderPromptHistory();
renderSessions();
if (state.sessionId) {
  renderMessages(state.sessionId);
  const session = state.sessions.find((item) => item.id === state.sessionId);
  updateActiveSessionTitle(session);
}
if (lightingSelect) {
  lightingSelect.value = state.lightingPreset;
}
setViewerOverlay('Send a prompt to generate a mesh.', 'Drop a mesh file to import.');
setMeshStatus('idle', 'Waiting for mesh JSON...');
initViewer();
applyGridVisibility(state.gridVisible, { persist: false });
applyWireframeState(state.wireframe, { persist: false });
initResizablePanels();
initNativeMenuListener();
if (settingsLightingSelect) {
  settingsLightingSelect.value = state.lightingPreset;
}
if (state.autoConnect && workspaceInput.value.trim()) {
  connect();
}
