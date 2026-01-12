"use strict";
/**
 * LoCo Agent VS Code Extension
 * Main entry point
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
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
const SidebarProvider_1 = require("./sidebar/SidebarProvider");
const ServerClient_1 = require("./api/ServerClient");
const ContextGatherer_1 = require("./context/ContextGatherer");
const DiffManager_1 = require("./diff/DiffManager");
let sidebarProvider;
let serverClient;
let contextGatherer;
let diffManager;
let indexStatusBar;
async function activate(context) {
    console.log('LoCo Agent is activating...');
    // Disconnect old client if it exists (prevent duplicate connections)
    if (serverClient) {
        console.log('Disconnecting old server client...');
        serverClient.disconnect();
    }
    // Initialize components
    serverClient = new ServerClient_1.ServerClient(context);
    contextGatherer = new ContextGatherer_1.ContextGatherer();
    diffManager = new DiffManager_1.DiffManager(context);
    indexStatusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    indexStatusBar.hide();
    context.subscriptions.push(indexStatusBar);
    serverClient.onMessage((message) => {
        if (message.type === 'patch.proposed') {
            const patchId = message.id || message.patch_id || message.patchId;
            if (!patchId) {
                return;
            }
            diffManager.addPatch(patchId, message.file_path, message.diff, message.base_hash || '');
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
    sidebarProvider = new SidebarProvider_1.SidebarProvider(context, serverClient, contextGatherer);
    context.subscriptions.push(vscode.window.registerWebviewViewProvider('locoAgent.chatView', sidebarProvider, {
        webviewOptions: {
            retainContextWhenHidden: true
        }
    }));
    // Register commands
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.openChat', () => {
        vscode.commands.executeCommand('locoAgent.chatView.focus');
    }));
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.sendMessage', async () => {
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const selection = editor.selection;
            const text = editor.document.getText(selection);
            if (text) {
                sidebarProvider.sendMessage(`Explain this code:\n\`\`\`\n${text}\n\`\`\``);
            }
        }
    }));
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.acceptPatch', async (patchId) => {
        await diffManager.acceptPatch(patchId);
    }));
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.rejectPatch', async (patchId) => {
        await diffManager.rejectPatch(patchId);
    }));
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.viewDiff', async (patchId) => {
        await diffManager.viewDiff(patchId);
    }));
    context.subscriptions.push(vscode.commands.registerCommand('locoAgent.undoPatch', async (patchId) => {
        await diffManager.undoPatch(patchId);
    }));
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
        if (event.affectsConfiguration('locoAgent.policy')) {
            serverClient.syncWorkspacePolicy().catch((error) => {
                console.warn('Failed to sync workspace policy:', error);
            });
        }
    }));
    // Check workspace trust
    if (!vscode.workspace.isTrusted) {
        vscode.window.showWarningMessage('LoCo Agent requires a trusted workspace. Please trust this workspace to use the extension.', 'Trust Workspace').then(selection => {
            if (selection === 'Trust Workspace') {
                vscode.commands.executeCommand('workbench.action.manageTrust');
            }
        });
        return;
    }
    // Connect to server
    try {
        console.log('Attempting to connect to server...');
        await serverClient.connect();
        console.log('Successfully connected to server');
        vscode.window.showInformationMessage('LoCo Agent: Connected to server');
    }
    catch (error) {
        console.error('Failed to connect to server:', error);
        vscode.window.showErrorMessage(`LoCo Agent: Failed to connect to server. Will retry automatically. ${error}`);
        // Note: ServerClient.attemptReconnect() will handle retries if WebSocket was created
    }
    console.log('LoCo Agent is now active');
}
async function handleApprovalRequest(message) {
    const tool = message.tool || 'tool';
    const requestId = message.request_id;
    if (!requestId) {
        return;
    }
    const details = message.message || `Approve ${tool} with args: ${JSON.stringify(message.arguments || {})}`;
    const choice = await vscode.window.showWarningMessage(details, { modal: true }, 'Approve', 'Reject');
    const approved = choice === 'Approve';
    serverClient.sendApprovalResponse(requestId, approved);
}
function deactivate() {
    if (serverClient) {
        serverClient.disconnect();
    }
}
//# sourceMappingURL=extension.js.map