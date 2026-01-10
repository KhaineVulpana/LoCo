import * as THREE from 'https://unpkg.com/three@0.161.0/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.161.0/examples/jsm/controls/OrbitControls.js';
import { extractMeshPayload } from './mesh_parser.js';

const statusPill = document.getElementById('status-pill');
const statusPillDup = document.getElementById('status-pill-dup');
const viewerStatus = document.getElementById('viewer-status');
const viewerOverlay = document.getElementById('viewer-overlay');
const vertexCount = document.getElementById('vertex-count');
const triangleCount = document.getElementById('triangle-count');
const meshStatus = document.getElementById('mesh-status');

const serverInput = document.getElementById('server-url');
const workspaceInput = document.getElementById('workspace-path');
const tokenInput = document.getElementById('auth-token');
const connectBtn = document.getElementById('connect-btn');
const composer = document.getElementById('composer');
const messageInput = document.getElementById('message-input');
const messagesEl = document.getElementById('messages');
const sessionListEl = document.getElementById('session-list');
const newSessionBtn = document.getElementById('new-session-btn');
const activeSessionTitle = document.getElementById('active-session-title');
const resetViewBtn = document.getElementById('reset-view');
const wireframeBtn = document.getElementById('toggle-wireframe');

const DEFAULT_SERVER = 'http://localhost:3199';
const FRONTEND_ID = '3d-gen';

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
  mesh: null
};

function setStatus(online, label) {
  statusPill.textContent = label;
  statusPill.classList.toggle('online', online);
  statusPill.classList.toggle('offline', !online);
  if (statusPillDup) {
    statusPillDup.textContent = label;
    statusPillDup.classList.toggle('online', online);
    statusPillDup.classList.toggle('offline', !online);
  }
}

function saveConfig() {
  localStorage.setItem('loco-3d-gen-config', JSON.stringify({
    serverUrl: serverInput.value.trim(),
    workspacePath: workspaceInput.value.trim(),
    token: tokenInput.value.trim()
  }));
}

function loadConfig() {
  const raw = localStorage.getItem('loco-3d-gen-config');
  if (!raw) {
    serverInput.value = DEFAULT_SERVER;
    return;
  }

  try {
    const config = JSON.parse(raw);
    serverInput.value = config.serverUrl || DEFAULT_SERVER;
    workspaceInput.value = config.workspacePath || '';
    tokenInput.value = config.token || '';
  } catch {
    serverInput.value = DEFAULT_SERVER;
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

function renderMessages(sessionId) {
  messagesEl.innerHTML = '';
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
  return renderMessage(role, content);
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

  const meshPayload = extractMeshPayload(message);
  if (meshPayload) {
    renderMesh(meshPayload);
  }

  state.currentAssistantEl = null;
  state.currentAssistantIndex = null;
  state.assistantBuffer = '';
}

async function registerWorkspace(serverUrl, token, workspacePath) {
  const response = await fetch(`${serverUrl}/v1/workspaces/register`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({
      path: workspacePath,
      name: '3d-gen'
    })
  });

  if (!response.ok) {
    throw new Error(`Workspace registration failed: ${response.statusText}`);
  }

  return response.json();
}

async function createSession(serverUrl, token, workspaceId) {
  const response = await fetch(`${serverUrl}/v1/sessions`, {
    method: 'POST',
    headers: buildHeaders(token),
    body: JSON.stringify({
      workspace_id: workspaceId
    })
  });

  if (!response.ok) {
    throw new Error(`Session creation failed: ${response.statusText}`);
  }

  return response.json();
}

function buildHeaders(token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
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

  if (!state.serverUrl || !state.workspaceId) {
    return;
  }

  if (state.ws) {
    state.ws.close();
    state.ws = null;
  }

  try {
    setStatus(false, 'connecting');
    await openWebSocket(state.serverUrl, state.token);
    setStatus(true, 'online');
  } catch (error) {
    console.error(error);
    addMessage('assistant', 'Failed to switch session.');
    setStatus(false, 'offline');
  }
}

async function connect() {
  const serverUrl = serverInput.value.trim() || DEFAULT_SERVER;
  const workspacePath = workspaceInput.value.trim();
  const token = tokenInput.value.trim();

  if (!workspacePath) {
    addMessage('assistant', 'Please provide a workspace path before connecting.');
    return;
  }

  saveConfig();
  setStatus(false, 'connecting');

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

    await openWebSocket(serverUrl, token);
    setStatus(true, 'online');
  } catch (error) {
    console.error(error);
    addMessage('assistant', `Connection failed: ${error.message}`);
    setStatus(false, 'offline');
  }
}

async function createNewSession() {
  if (!state.serverUrl || !state.workspaceId) {
    addMessage('assistant', 'Connect to a workspace before creating a new chat.');
    return;
  }

  setStatus(false, 'connecting');
  try {
    const session = await createSession(state.serverUrl, state.token, state.workspaceId);
    const entry = addSession(session);
    await switchSession(entry.id);
  } catch (error) {
    console.error(error);
    addMessage('assistant', `Failed to create session: ${error.message}`);
    setStatus(false, 'offline');
  }
}

function openWebSocket(serverUrl, token) {
  return new Promise((resolve, reject) => {
    const wsUrl = serverUrl.replace('http', 'ws') + `/v1/sessions/${state.sessionId}/stream`;
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
      resolve();
    });

    ws.addEventListener('message', (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerEvent(data);
      } catch (error) {
        console.warn('Failed to parse server message', error);
      }
    });

    ws.addEventListener('close', () => {
      setStatus(false, 'offline');
    });

    ws.addEventListener('error', (error) => {
      reject(error);
    });

    state.ws = ws;
  });
}

function sendUserMessage(message) {
  if (!state.ws || state.ws.readyState !== WebSocket.OPEN) {
    addMessage('assistant', 'Not connected. Please connect first.');
    return;
  }

  addMessage('user', message);
  updateSessionTitleFromMessage(message);

  state.ws.send(JSON.stringify({
    type: 'client.user_message',
    message,
    context: {
      frontend_id: FRONTEND_ID
    }
  }));
}

function handleServerEvent(event) {
  switch (event.type) {
    case 'assistant.message_delta':
      appendAssistantDelta(event.delta || '');
      break;
    case 'assistant.message_final':
      finalizeAssistantMessage(event.message || '');
      break;
    case 'assistant.thinking':
      addMessage('assistant', event.message || 'Thinking...');
      break;
    case 'assistant.tool_use':
      addMessage('assistant', `Tool: ${event.tool}`);
      break;
    case 'assistant.tool_result':
      addMessage('assistant', `Tool result: ${JSON.stringify(event.result)}`);
      break;
    case 'server.error':
      addMessage('assistant', `Error: ${event.error?.message || 'Unknown error'}`);
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

function initViewer() {
  const canvas = document.getElementById('viewer');
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(window.devicePixelRatio || 1);

  scene = new THREE.Scene();
  scene.background = new THREE.Color('#0d1018');

  camera = new THREE.PerspectiveCamera(45, 1, 0.1, 200);
  camera.position.set(2.5, 1.8, 2.8);

  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;

  const ambient = new THREE.AmbientLight(0xffffff, 0.8);
  scene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0xffffff, 0.9);
  keyLight.position.set(4, 6, 4);
  scene.add(keyLight);

  const grid = new THREE.GridHelper(10, 20, 0x1c2a3b, 0x111822);
  grid.position.y = -0.01;
  scene.add(grid);

  const axes = new THREE.AxesHelper(0.5);
  scene.add(axes);

  resizeRenderer();
  animate();
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

function renderMesh(mesh) {
  if (!mesh || !mesh.vertices || !mesh.triangles) {
    return;
  }

  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(mesh.vertices.flat());

  let indices = mesh.triangles.flat();
  if (mesh.triangles.length && typeof mesh.triangles[0] === 'number') {
    indices = mesh.triangles;
  }

  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setIndex(indices);

  if (mesh.normals && mesh.normals.length === mesh.vertices.length) {
    const normals = new Float32Array(mesh.normals.flat());
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
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

  if (activeMesh) {
    scene.remove(activeMesh);
  }

  activeMesh = newMesh;
  scene.add(newMesh);

  geometry.computeBoundingSphere();
  if (geometry.boundingSphere) {
    const radius = geometry.boundingSphere.radius;
    controls.target.copy(geometry.boundingSphere.center);
    camera.position.set(radius * 2.2, radius * 1.6, radius * 2.4);
    controls.update();
  }

  viewerOverlay.style.display = 'none';
  viewerStatus.textContent = 'Mesh loaded';
  meshStatus.textContent = 'ready';
  vertexCount.textContent = mesh.vertices.length;
  triangleCount.textContent = Math.floor(indices.length / 3);
}

connectBtn.addEventListener('click', () => {
  connect();
});

if (newSessionBtn) {
  newSessionBtn.addEventListener('click', () => {
    createNewSession();
  });
}

composer.addEventListener('submit', (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  if (!message) {
    return;
  }
  messageInput.value = '';
  sendUserMessage(message);
});

resetViewBtn.addEventListener('click', () => {
  controls.reset();
});

wireframeBtn.addEventListener('click', () => {
  state.wireframe = !state.wireframe;
  if (activeMesh) {
    activeMesh.material.wireframe = state.wireframe;
  }
});

window.addEventListener('resize', () => {
  resizeRenderer();
});

loadConfig();
renderSessions();
initViewer();
