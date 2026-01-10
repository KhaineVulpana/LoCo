/**
 * Server WebSocket Client
 */

import * as vscode from 'vscode';
import WebSocket from 'ws';
import * as fs from 'fs/promises';
import * as os from 'os';
import * as path from 'path';
import { Readable } from 'stream';

export interface ServerMessage {
    type: string;
    [key: string]: any;
}

export type MessageHandler = (message: ServerMessage) => void;
export type IndexProgressHandler = (progress: any) => void;

export class ServerClient {
    private ws: WebSocket | null = null;
    private messageHandlers: MessageHandler[] = [];
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private sessionId: string | null = null;
    private workspaceId: string | null = null;
    private indexProgressHandlers: IndexProgressHandler[] = [];
    private indexStreamController: AbortController | null = null;
    private serverUrl: string | null = null;
    private authToken: string | undefined;

    constructor(private context: vscode.ExtensionContext) {}

    async connect(): Promise<void> {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const serverUrl = config.get<string>('serverUrl', 'http://localhost:3199');
        const authEnabled = config.get<boolean>('authEnabled', false);
        const autoIndexWorkspace = config.get<boolean>('autoIndexWorkspace', false);
        const autoWatchWorkspace = config.get<boolean>('autoWatchWorkspace', false);
        const usePollingWatcher = config.get<boolean>('usePollingWatcher', false);

        // Get or create token
        const token = authEnabled ? await this.getOrCreateToken() : undefined;
        this.serverUrl = serverUrl;
        this.authToken = token;
        // Register workspace if needed
        this.workspaceId = await this.registerWorkspace(
            serverUrl,
            token,
            autoIndexWorkspace,
            autoWatchWorkspace,
            usePollingWatcher
        );

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
            const headers: Record<string, string> = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            this.ws = new WebSocket(wsUrl, { headers });

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

            this.ws.on('message', (data: WebSocket.Data) => {
                try {
                    const message = JSON.parse(data.toString());
                    this.handleMessage(message);
                } catch (error) {
                    console.error('Failed to parse message:', error);
                }
            });

            this.ws.on('error', (error: Error) => {
                console.error('WebSocket error:', error);
                reject(error);
            });

            this.ws.on('close', () => {
                console.log('WebSocket closed');
                this.attemptReconnect();
            });
        });
    }

    disconnect(): void {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    send(message: any): void {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.error('WebSocket not connected');
        }
    }

    sendApprovalResponse(requestId: string, approved: boolean): void {
        this.send({
            type: 'client.approval_response',
            request_id: requestId,
            approved
        });
    }

    onMessage(handler: MessageHandler): void {
        this.messageHandlers.push(handler);
    }

    onIndexProgress(handler: IndexProgressHandler): void {
        this.indexProgressHandlers.push(handler);
    }

    async syncWorkspacePolicy(): Promise<void> {
        if (!this.serverUrl || !this.workspaceId) {
            return;
        }
        await this.applyWorkspacePolicyOverrides(this.serverUrl, this.authToken);
    }

    private handleMessage(message: ServerMessage): void {
        for (const handler of this.messageHandlers) {
            handler(message);
        }
    }

    private async attemptReconnect(): Promise<void> {
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

    private async getOrCreateToken(): Promise<string> {
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

    private async readTokenFile(tokenPath: string): Promise<string | null> {
        try {
            const token = (await fs.readFile(tokenPath, 'utf8')).trim();
            return token ? token : null;
        } catch (error: any) {
            if (error?.code === 'ENOENT' || error?.code === 'ENOTDIR') {
                return null;
            }
            console.warn('Failed to read token file:', error);
            return null;
        }
    }

    private async writeTokenFile(tokenPath: string, token: string): Promise<void> {
        try {
            await fs.mkdir(path.dirname(tokenPath), { recursive: true });
            await fs.writeFile(tokenPath, token, { encoding: 'utf8', mode: 0o600 });
        } catch (error) {
            console.warn('Failed to write token file:', error);
        }
    }

    private generateToken(): string {
        return Array.from({ length: 32 }, () =>
            Math.random().toString(36)[2]
        ).join('');
    }

    private async registerWorkspace(
        serverUrl: string,
        token?: string,
        autoIndexWorkspace: boolean = false,
        autoWatchWorkspace: boolean = false,
        usePollingWatcher: boolean = false
    ): Promise<string> {
        if (this.workspaceId) {
            return this.workspaceId;
        }

        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }

        const frontendId = 'vscode';
        const headers: Record<string, string> = {
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
            const listHeaders: Record<string, string> = {};
            if (token) {
                listHeaders['Authorization'] = `Bearer ${token}`;
            }
            const listResponse = await fetch(`${serverUrl}/v1/workspaces`, {
                headers: listHeaders
            });

            if (listResponse.ok) {
                const workspaces: any = await listResponse.json();
                const existing = workspaces.find((w: any) => w.path === workspaceFolder.uri.fsPath);
                if (existing) {
                    this.workspaceId = existing.id;
                    return existing.id;
                }
            }

            throw new Error(`Failed to register workspace: ${response.statusText}`);
        }

        const data: any = await response.json();
        this.workspaceId = data.id;
        return data.id;
    }

    private async createSession(serverUrl: string, token?: string): Promise<string> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }

        // Get workspace ID
        const workspaceId = await this.registerWorkspace(serverUrl, token);

        const headers: Record<string, string> = {
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

        const data: any = await response.json();
        return data.id;
    }

    private notifyIndexProgress(payload: any): void {
        for (const handler of this.indexProgressHandlers) {
            handler(payload);
        }
    }

    private async startIndexStream(
        serverUrl: string,
        token: string | undefined,
        frontendId: string,
        autoStart: boolean,
        autoWatch: boolean,
        usePollingWatcher: boolean
    ): Promise<void> {
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

        const headers: Record<string, string> = {
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
        const stream = Readable.fromWeb(response.body as any);
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
                    } catch (error) {
                        console.warn('Failed to parse index progress:', error);
                    }
                }
            }
        }
    }

    private async startWorkspaceWatch(
        serverUrl: string,
        token: string | undefined,
        frontendId: string,
        usePollingWatcher: boolean
    ): Promise<void> {
        if (!this.workspaceId) {
            return;
        }

        const headers: Record<string, string> = {
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

    private buildPolicyOverrides(config: vscode.WorkspaceConfiguration): Record<string, any> {
        const overrides: Record<string, any> = {};

        const commandApproval = this.getExplicitSetting<string>(config, 'policy.commandApproval');
        if (commandApproval) {
            overrides.command_approval = commandApproval;
        }

        const allowedCommands = this.getExplicitSetting<string[]>(config, 'policy.allowedCommands');
        if (Array.isArray(allowedCommands)) {
            overrides.allowed_commands = allowedCommands;
        }

        const blockedCommands = this.getExplicitSetting<string[]>(config, 'policy.blockedCommands');
        if (Array.isArray(blockedCommands)) {
            overrides.blocked_commands = blockedCommands;
        }

        const allowedReadGlobs = this.getExplicitSetting<string[]>(config, 'policy.allowedReadGlobs');
        if (Array.isArray(allowedReadGlobs)) {
            overrides.allowed_read_globs = allowedReadGlobs;
        }

        const allowedWriteGlobs = this.getExplicitSetting<string[]>(config, 'policy.allowedWriteGlobs');
        if (Array.isArray(allowedWriteGlobs)) {
            overrides.allowed_write_globs = allowedWriteGlobs;
        }

        const blockedGlobs = this.getExplicitSetting<string[]>(config, 'policy.blockedGlobs');
        if (Array.isArray(blockedGlobs)) {
            overrides.blocked_globs = blockedGlobs;
        }

        const networkEnabled = this.getExplicitSetting<boolean>(config, 'policy.networkEnabled');
        if (networkEnabled !== undefined) {
            overrides.network_enabled = networkEnabled;
        }

        const autoApproveSimple = this.getExplicitSetting<boolean>(config, 'policy.autoApproveSimpleChanges');
        if (autoApproveSimple !== undefined) {
            overrides.auto_approve_simple_changes = autoApproveSimple;
        }

        const autoApproveTests = this.getExplicitSetting<boolean>(config, 'policy.autoApproveTests');
        if (autoApproveTests !== undefined) {
            overrides.auto_approve_tests = autoApproveTests;
        }

        return overrides;
    }

    private async applyWorkspacePolicyOverrides(
        serverUrl: string,
        token: string | undefined
    ): Promise<void> {
        if (!this.workspaceId) {
            return;
        }

        const config = vscode.workspace.getConfiguration('locoAgent');
        const overrides = this.buildPolicyOverrides(config);
        if (!Object.keys(overrides).length) {
            return;
        }

        const headers: Record<string, string> = {
            'Content-Type': 'application/json'
        };
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(
            `${serverUrl}/v1/workspaces/${this.workspaceId}/policy`,
            {
                method: 'PUT',
                headers,
                body: JSON.stringify(overrides)
            }
        );

        if (!response.ok) {
            console.warn('Failed to update workspace policy:', response.statusText);
        }
    }

    private getExplicitSetting<T>(config: vscode.WorkspaceConfiguration, key: string): T | undefined {
        const inspected = config.inspect<T>(key);
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
