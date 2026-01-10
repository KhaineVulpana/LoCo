"use strict";
/**
 * Server WebSocket Client
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.ServerClient = void 0;
const vscode = __importStar(require("vscode"));
const ws_1 = __importDefault(require("ws"));
const fs = __importStar(require("fs/promises"));
const os = __importStar(require("os"));
const path = __importStar(require("path"));
const stream_1 = require("stream");
class ServerClient {
    constructor(context) {
        this.context = context;
        this.ws = null;
        this.messageHandlers = [];
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.sessionId = null;
        this.workspaceId = null;
        this.indexProgressHandlers = [];
        this.indexStreamController = null;
        this.serverUrl = null;
    }
    async connect() {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const serverUrl = config.get('serverUrl', 'http://localhost:3199');
        const authEnabled = config.get('authEnabled', false);
        const autoIndexWorkspace = config.get('autoIndexWorkspace', false);
        const autoWatchWorkspace = config.get('autoWatchWorkspace', false);
        const usePollingWatcher = config.get('usePollingWatcher', false);
        // Get or create token
        const token = authEnabled ? await this.getOrCreateToken() : undefined;
        this.serverUrl = serverUrl;
        this.authToken = token;
        // Register workspace if needed
        this.workspaceId = await this.registerWorkspace(serverUrl, token, autoIndexWorkspace, autoWatchWorkspace, usePollingWatcher);
        await this.applyWorkspacePolicyOverrides(serverUrl, token);
        if (autoIndexWorkspace || autoWatchWorkspace) {
            const autoStart = autoIndexWorkspace || autoWatchWorkspace;
            this.startIndexStream(serverUrl, token, 'vscode', autoStart, autoWatchWorkspace, usePollingWatcher).catch((error) => {
                console.warn('Index stream failed:', error);
            });
        }
        if (autoWatchWorkspace) {
            this.startWorkspaceWatch(serverUrl, token, 'vscode', usePollingWatcher).catch((error) => {
                console.warn('Workspace watch start failed:', error);
            });
        }
        // Create session
        this.sessionId = await this.createSession(serverUrl, token);
        // Connect WebSocket
        const wsUrl = serverUrl.replace('http', 'ws') + `/v1/sessions/${this.sessionId}/stream`;
        return new Promise((resolve, reject) => {
            const headers = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }
            this.ws = new ws_1.default(wsUrl, { headers });
            this.ws.on('open', () => {
                console.log('WebSocket connected');
                this.reconnectAttempts = 0;
                // Send client hello
                this.send({
                    type: 'client.hello',
                    protocol_version: '1.0.0',
                    client_info: {
                        name: 'vscode-extension',
                        version: '0.1.0',
                        capabilities: ['diff_preview', 'terminal_exec', 'git_integration']
                    }
                });
                resolve();
            });
            this.ws.on('message', (data) => {
                try {
                    const message = JSON.parse(data.toString());
                    this.handleMessage(message);
                }
                catch (error) {
                    console.error('Failed to parse message:', error);
                }
            });
            this.ws.on('error', (error) => {
                console.error('WebSocket error:', error);
                reject(error);
            });
            this.ws.on('close', () => {
                console.log('WebSocket closed');
                this.attemptReconnect();
            });
        });
    }
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
    send(message) {
        if (this.ws && this.ws.readyState === ws_1.default.OPEN) {
            this.ws.send(JSON.stringify(message));
        }
        else {
            console.error('WebSocket not connected');
        }
    }
    sendApprovalResponse(requestId, approved) {
        this.send({
            type: 'client.approval_response',
            request_id: requestId,
            approved
        });
    }
    onMessage(handler) {
        this.messageHandlers.push(handler);
    }
    onIndexProgress(handler) {
        this.indexProgressHandlers.push(handler);
    }
    async syncWorkspacePolicy() {
        if (!this.serverUrl || !this.workspaceId) {
            return;
        }
        await this.applyWorkspacePolicyOverrides(this.serverUrl, this.authToken);
    }
    handleMessage(message) {
        for (const handler of this.messageHandlers) {
            handler(message);
        }
    }
    async attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            vscode.window.showErrorMessage('LoCo Agent: Failed to reconnect to server');
            return;
        }
        this.reconnectAttempts++;
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
        setTimeout(() => {
            this.connect().catch(error => {
                console.error('Reconnection failed:', error);
            });
        }, delay);
    }
    async getOrCreateToken() {
        const tokenPath = path.join(os.homedir(), '.loco-agent', 'token');
        const fileToken = await this.readTokenFile(tokenPath);
        if (fileToken) {
            await this.context.secrets.store('locoAgent.token', fileToken);
            return fileToken;
        }
        const storedToken = await this.context.secrets.get('locoAgent.token');
        if (storedToken) {
            await this.writeTokenFile(tokenPath, storedToken);
            return storedToken;
        }
        const token = this.generateToken();
        await this.context.secrets.store('locoAgent.token', token);
        await this.writeTokenFile(tokenPath, token);
        return token;
    }
    async readTokenFile(tokenPath) {
        try {
            const token = (await fs.readFile(tokenPath, 'utf8')).trim();
            return token ? token : null;
        }
        catch (error) {
            if (error?.code === 'ENOENT' || error?.code === 'ENOTDIR') {
                return null;
            }
            console.warn('Failed to read token file:', error);
            return null;
        }
    }
    async writeTokenFile(tokenPath, token) {
        try {
            await fs.mkdir(path.dirname(tokenPath), { recursive: true });
            await fs.writeFile(tokenPath, token, { encoding: 'utf8', mode: 0o600 });
        }
        catch (error) {
            console.warn('Failed to write token file:', error);
        }
    }
    generateToken() {
        return Array.from({ length: 32 }, () => Math.random().toString(36)[2]).join('');
    }
    async registerWorkspace(serverUrl, token, autoIndexWorkspace = false, autoWatchWorkspace = false, usePollingWatcher = false) {
        if (this.workspaceId) {
            return this.workspaceId;
        }
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }
        const frontendId = 'vscode';
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(`${serverUrl}/v1/workspaces/register`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                path: workspaceFolder.uri.fsPath,
                name: workspaceFolder.name,
                frontend_id: frontendId,
                auto_index: autoIndexWorkspace,
                auto_watch: autoWatchWorkspace,
                use_polling: usePollingWatcher
            })
        });
        if (!response.ok) {
            // Workspace might already exist, try to list
            const listHeaders = {};
            if (token) {
                listHeaders['Authorization'] = `Bearer ${token}`;
            }
            const listResponse = await fetch(`${serverUrl}/v1/workspaces`, {
                headers: listHeaders
            });
            if (listResponse.ok) {
                const workspaces = await listResponse.json();
                const existing = workspaces.find((w) => w.path === workspaceFolder.uri.fsPath);
                if (existing) {
                    this.workspaceId = existing.id;
                    return existing.id;
                }
            }
            throw new Error(`Failed to register workspace: ${response.statusText}`);
        }
        const data = await response.json();
        this.workspaceId = data.id;
        return data.id;
    }
    async createSession(serverUrl, token) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }
        // Get workspace ID
        const workspaceId = await this.registerWorkspace(serverUrl, token);
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        // Let server use its configured defaults
        const response = await fetch(`${serverUrl}/v1/sessions`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                workspace_id: workspaceId
            })
        });
        if (!response.ok) {
            throw new Error(`Failed to create session: ${response.statusText}`);
        }
        const data = await response.json();
        return data.id;
    }
    notifyIndexProgress(payload) {
        for (const handler of this.indexProgressHandlers) {
            handler(payload);
        }
    }
    async startIndexStream(serverUrl, token, frontendId, autoStart, autoWatch, usePollingWatcher) {
        if (!this.workspaceId) {
            return;
        }
        if (this.indexStreamController) {
            this.indexStreamController.abort();
        }
        const url = new URL(`${serverUrl}/v1/workspaces/${this.workspaceId}/index/stream`);
        url.searchParams.set('frontend_id', frontendId);
        url.searchParams.set('auto_start', autoStart ? 'true' : 'false');
        url.searchParams.set('auto_watch', autoWatch ? 'true' : 'false');
        url.searchParams.set('use_polling', usePollingWatcher ? 'true' : 'false');
        const headers = {
            'Accept': 'text/event-stream'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const controller = new AbortController();
        this.indexStreamController = controller;
        const response = await fetch(url.toString(), {
            headers,
            signal: controller.signal
        });
        if (!response.ok || !response.body) {
            throw new Error(`Index stream failed: ${response.statusText}`);
        }
        const decoder = new TextDecoder();
        const stream = stream_1.Readable.fromWeb(response.body);
        let buffer = '';
        for await (const chunk of stream) {
            buffer += decoder.decode(chunk, { stream: true });
            let separator = buffer.indexOf('\n\n');
            while (separator !== -1) {
                const eventBlock = buffer.slice(0, separator);
                buffer = buffer.slice(separator + 2);
                separator = buffer.indexOf('\n\n');
                const lines = eventBlock.split('\n');
                for (const line of lines) {
                    if (!line.startsWith('data:')) {
                        continue;
                    }
                    const data = line.slice(5).trim();
                    if (!data) {
                        continue;
                    }
                    try {
                        const payload = JSON.parse(data);
                        this.notifyIndexProgress(payload);
                    }
                    catch (error) {
                        console.warn('Failed to parse index progress:', error);
                    }
                }
            }
        }
    }
    async startWorkspaceWatch(serverUrl, token, frontendId, usePollingWatcher) {
        if (!this.workspaceId) {
            return;
        }
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(`${serverUrl}/v1/workspaces/${this.workspaceId}/watch/start`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
                frontend_id: frontendId,
                use_polling: usePollingWatcher
            })
        });
        if (!response.ok) {
            throw new Error(`Failed to start workspace watcher: ${response.statusText}`);
        }
    }
    buildPolicyOverrides(config) {
        const overrides = {};
        const commandApproval = this.getExplicitSetting(config, 'policy.commandApproval');
        if (commandApproval) {
            overrides.command_approval = commandApproval;
        }
        const allowedCommands = this.getExplicitSetting(config, 'policy.allowedCommands');
        if (Array.isArray(allowedCommands)) {
            overrides.allowed_commands = allowedCommands;
        }
        const blockedCommands = this.getExplicitSetting(config, 'policy.blockedCommands');
        if (Array.isArray(blockedCommands)) {
            overrides.blocked_commands = blockedCommands;
        }
        const allowedReadGlobs = this.getExplicitSetting(config, 'policy.allowedReadGlobs');
        if (Array.isArray(allowedReadGlobs)) {
            overrides.allowed_read_globs = allowedReadGlobs;
        }
        const allowedWriteGlobs = this.getExplicitSetting(config, 'policy.allowedWriteGlobs');
        if (Array.isArray(allowedWriteGlobs)) {
            overrides.allowed_write_globs = allowedWriteGlobs;
        }
        const blockedGlobs = this.getExplicitSetting(config, 'policy.blockedGlobs');
        if (Array.isArray(blockedGlobs)) {
            overrides.blocked_globs = blockedGlobs;
        }
        const networkEnabled = this.getExplicitSetting(config, 'policy.networkEnabled');
        if (networkEnabled !== undefined) {
            overrides.network_enabled = networkEnabled;
        }
        const autoApproveSimple = this.getExplicitSetting(config, 'policy.autoApproveSimpleChanges');
        if (autoApproveSimple !== undefined) {
            overrides.auto_approve_simple_changes = autoApproveSimple;
        }
        const autoApproveTests = this.getExplicitSetting(config, 'policy.autoApproveTests');
        if (autoApproveTests !== undefined) {
            overrides.auto_approve_tests = autoApproveTests;
        }
        return overrides;
    }
    async applyWorkspacePolicyOverrides(serverUrl, token) {
        if (!this.workspaceId) {
            return;
        }
        const config = vscode.workspace.getConfiguration('locoAgent');
        const overrides = this.buildPolicyOverrides(config);
        if (!Object.keys(overrides).length) {
            return;
        }
        const headers = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }
        const response = await fetch(`${serverUrl}/v1/workspaces/${this.workspaceId}/policy`, {
            method: 'PUT',
            headers,
            body: JSON.stringify(overrides)
        });
        if (!response.ok) {
            console.warn('Failed to update workspace policy:', response.statusText);
        }
    }
    getExplicitSetting(config, key) {
        const inspected = config.inspect(key);
        if (!inspected) {
            return undefined;
        }
        if (inspected.workspaceFolderValue !== undefined) {
            return inspected.workspaceFolderValue;
        }
        if (inspected.workspaceValue !== undefined) {
            return inspected.workspaceValue;
        }
        if (inspected.globalValue !== undefined) {
            return inspected.globalValue;
        }
        return undefined;
    }
}
exports.ServerClient = ServerClient;
//# sourceMappingURL=ServerClient.js.map