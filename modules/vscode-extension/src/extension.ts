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

export async function activate(context: vscode.ExtensionContext) {
    console.log('LoCo Agent is activating...');

    // Initialize components
    serverClient = new ServerClient(context);
    contextGatherer = new ContextGatherer();
    diffManager = new DiffManager(context);

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

export function deactivate() {
    if (serverClient) {
        serverClient.disconnect();
    }
}
