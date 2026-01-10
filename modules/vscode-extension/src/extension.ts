/**
 * LoCo Agent VS Code Extension
 * Main entry point
 */

import * as vscode from 'vscode';
import { SidebarProvider } from './sidebar/SidebarProvider';
import { ServerClient } from './api/ServerClient';
import { ContextGatherer } from './context/ContextGatherer';
import { DiffManager } from './diff/DiffManager';

let sidebarProvider: SidebarProvider;
let serverClient: ServerClient;
let contextGatherer: ContextGatherer;
let diffManager: DiffManager;
let indexStatusBar: vscode.StatusBarItem;

export async function activate(context: vscode.ExtensionContext) {
    console.log('LoCo Agent is activating...');

    // Initialize components
    serverClient = new ServerClient(context);
    contextGatherer = new ContextGatherer();
    diffManager = new DiffManager(context);
    indexStatusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    indexStatusBar.hide();
    context.subscriptions.push(indexStatusBar);

    serverClient.onMessage((message) => {
        if (message.type === 'patch.proposed') {
            const patchId = message.id || message.patch_id || message.patchId;
            if (!patchId) {
                return;
            }
            diffManager.addPatch(
                patchId,
                message.file_path,
                message.diff,
                message.base_hash || ''
            );
            return;
        }

        if (message.type === 'tool.request_approval' || message.type === 'command.request_approval') {
            void handleApprovalRequest(message);
        }
    });

    serverClient.onIndexProgress((progress) => {
        if (progress?.error) {
            indexStatusBar.hide();
            return;
        }

        const percent = Math.round((progress.index_progress || 0) * 100);
        const total = progress.total_files || 0;
        const indexed = progress.indexed_files || 0;
        indexStatusBar.text = `LoCo Indexing: ${percent}%`;
        indexStatusBar.tooltip = `Indexed ${indexed}/${total} files`;
        indexStatusBar.show();

        if (['complete', 'partial', 'failed'].includes(progress.index_status)) {
            indexStatusBar.hide();
        }
    });

    // Register sidebar provider
    sidebarProvider = new SidebarProvider(context, serverClient, contextGatherer);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            'locoAgent.chatView',
            sidebarProvider,
            {
                webviewOptions: {
                    retainContextWhenHidden: true
                }
            }
        )
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.openChat', () => {
            vscode.commands.executeCommand('locoAgent.chatView.focus');
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.sendMessage', async () => {
            const editor = vscode.window.activeTextEditor;
            if (editor) {
                const selection = editor.selection;
                const text = editor.document.getText(selection);

                if (text) {
                    sidebarProvider.sendMessage(`Explain this code:\n\`\`\`\n${text}\n\`\`\``);
                }
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.acceptPatch', async (patchId: string) => {
            await diffManager.acceptPatch(patchId);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.rejectPatch', async (patchId: string) => {
            await diffManager.rejectPatch(patchId);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.viewDiff', async (patchId: string) => {
            await diffManager.viewDiff(patchId);
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('locoAgent.undoPatch', async (patchId?: string) => {
            await diffManager.undoPatch(patchId);
        })
    );

    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration('locoAgent.policy')) {
                serverClient.syncWorkspacePolicy().catch((error) => {
                    console.warn('Failed to sync workspace policy:', error);
                });
            }
        })
    );

    // Check workspace trust
    if (!vscode.workspace.isTrusted) {
        vscode.window.showWarningMessage(
            'LoCo Agent requires a trusted workspace. Please trust this workspace to use the extension.',
            'Trust Workspace'
        ).then(selection => {
            if (selection === 'Trust Workspace') {
                vscode.commands.executeCommand('workbench.action.manageTrust');
            }
        });
        return;
    }

    // Connect to server
    try {
        await serverClient.connect();
        vscode.window.showInformationMessage('LoCo Agent: Connected to server');
    } catch (error) {
        vscode.window.showErrorMessage(
            `LoCo Agent: Failed to connect to server. ${error}`
        );
    }

    console.log('LoCo Agent is now active');
}

async function handleApprovalRequest(message: any): Promise<void> {
    const tool = message.tool || 'tool';
    const requestId = message.request_id;
    if (!requestId) {
        return;
    }

    const details = message.message || `Approve ${tool} with args: ${JSON.stringify(message.arguments || {})}`;
    const choice = await vscode.window.showWarningMessage(
        details,
        { modal: true },
        'Approve',
        'Reject'
    );

    const approved = choice === 'Approve';
    serverClient.sendApprovalResponse(requestId, approved);
}

export function deactivate() {
    if (serverClient) {
        serverClient.disconnect();
    }
}
