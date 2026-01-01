/**
 * Server WebSocket Client
 */

import * as vscode from 'vscode';
import WebSocket from 'ws';
import * as fs from 'fs/promises';
import * as os from 'os';
import * as path from 'path';

export interface ServerMessage {
    type: string;
    [key: string]: any;
}

export type MessageHandler = (message: ServerMessage) => void;

export class ServerClient {
    private ws: WebSocket | null = null;
    private messageHandlers: MessageHandler[] = [];
    private reconnectAttempts = 0;
    private maxReconnectAttempts = 5;
    private reconnectDelay = 1000;
    private sessionId: string | null = null;

    constructor(private context: vscode.ExtensionContext) {}

    async connect(): Promise<void> {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const serverUrl = config.get<string>('serverUrl', 'http://localhost:3199');

        // Get or create token
        const token = await this.getOrCreateToken();

        // Register workspace if needed
        await this.registerWorkspace(serverUrl, token);

        // Create session
        this.sessionId = await this.createSession(serverUrl, token);

        // Connect WebSocket
        const wsUrl = serverUrl.replace('http', 'ws') + `/v1/sessions/${this.sessionId}/stream`;

        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(wsUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

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

    onMessage(handler: MessageHandler): void {
        this.messageHandlers.push(handler);
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

    private async registerWorkspace(serverUrl: string, token: string): Promise<string> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }

        const response = await fetch(`${serverUrl}/v1/workspaces/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                path: workspaceFolder.uri.fsPath,
                name: workspaceFolder.name
            })
        });

        if (!response.ok) {
            // Workspace might already exist, try to list
            const listResponse = await fetch(`${serverUrl}/v1/workspaces`, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (listResponse.ok) {
                const workspaces: any = await listResponse.json();
                const existing = workspaces.find((w: any) => w.path === workspaceFolder.uri.fsPath);
                if (existing) {
                    return existing.id;
                }
            }

            throw new Error(`Failed to register workspace: ${response.statusText}`);
        }

        const data: any = await response.json();
        return data.id;
    }

    private async createSession(serverUrl: string, token: string): Promise<string> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder open');
        }

        // Get workspace ID
        const workspaceId = await this.registerWorkspace(serverUrl, token);

        // Let server use its configured defaults
        const response = await fetch(`${serverUrl}/v1/sessions`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
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
