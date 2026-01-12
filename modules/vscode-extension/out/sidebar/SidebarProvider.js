"use strict";
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
exports.SidebarProvider = void 0;
const vscode = __importStar(require("vscode"));
const marked = __importStar(require("marked"));
const path = __importStar(require("path"));
class SidebarProvider {
    constructor(context, serverClient, contextGatherer) {
        this.context = context;
        this.serverClient = serverClient;
        this.contextGatherer = contextGatherer;
        this.messages = [];
        this.serverClient.onMessage((message) => this.handleServerMessage(message));
    }
    resolveWebviewView(webviewView) {
        this.view = webviewView;
        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this.context.extensionUri]
        };
        webviewView.webview.html = this.getHtmlContent(webviewView.webview);
        webviewView.webview.onDidReceiveMessage(async (data) => {
            switch (data.type) {
                case 'sendMessage':
                    await this.sendMessage(data.message);
                    break;
                case 'acceptPatch':
                    vscode.commands.executeCommand('locoAgent.acceptPatch', data.patchId);
                    break;
                case 'rejectPatch':
                    vscode.commands.executeCommand('locoAgent.rejectPatch', data.patchId);
                    break;
                case 'viewDiff':
                    vscode.commands.executeCommand('locoAgent.viewDiff', data.patchId);
                    break;
                case 'undoPatch':
                    vscode.commands.executeCommand('locoAgent.undoPatch', data.patchId);
                    break;
                case 'openMentionPicker':
                    await this.openMentionPicker();
                    break;
            }
        });
    }
    async sendMessage(message) {
        // Add user message to UI
        this.addMessage('user', message);
        const parsed = this.parseSlashCommand(message);
        // Gather context
        const context = await this.contextGatherer.gatherContext(message);
        if (parsed.command) {
            context.command = parsed.command;
        }
        // Send to server
        this.serverClient.send({
            type: 'client.user_message',
            message: parsed.message || message,
            context: context
        });
    }
    parseSlashCommand(message) {
        const match = message.match(/^\/([a-z]+)\s*(.*)$/is);
        if (!match) {
            return { message };
        }
        const command = match[1].toLowerCase();
        const rest = match[2]?.trim() || '';
        return { command, message: rest };
    }
    async openMentionPicker() {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return;
        }
        const files = await vscode.workspace.findFiles('**/*', '**/{.git,node_modules,dist,build,out,.venv,venv}/**', 200);
        const picks = files.map(file => {
            const relative = path
                .relative(workspaceFolder.uri.fsPath, file.fsPath)
                .replace(/\\/g, '/');
            return {
                label: relative,
                description: file.fsPath
            };
        });
        const selection = await vscode.window.showQuickPick(picks, {
            placeHolder: 'Select a file to mention'
        });
        if (!selection || !this.view) {
            return;
        }
        this.view.webview.postMessage({
            type: 'insertMention',
            text: `@${selection.label} `
        });
    }
    handleServerMessage(message) {
        switch (message.type) {
            case 'server.hello':
                console.log('Server hello:', message.server_info);
                break;
            case 'assistant.thinking':
                this.updateThinking(message.phase, message.message);
                break;
            case 'assistant.message_delta':
                this.appendMessageDelta(message.delta);
                break;
            case 'assistant.message_final':
                this.addMessage('assistant', message.message);
                this.clearThinking();
                break;
            case 'assistant.tool_use':
                this.showToolUse(message.tool, message.arguments);
                break;
            case 'assistant.tool_result':
                this.showToolResult(message.tool, message.result);
                break;
            case 'agent.plan':
                this.showPlan(message.steps, message.rationale);
                break;
            case 'patch.proposed':
                this.showPatch(message);
                break;
            case 'server.error':
                this.showError(message.error.message);
                break;
        }
    }
    addMessage(role, content) {
        this.messages.push({ role, content });
        if (this.view) {
            this.view.webview.postMessage({
                type: 'addMessage',
                role,
                content: this.renderMarkdown(content)
            });
        }
    }
    appendMessageDelta(delta) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'appendDelta',
                delta
            });
        }
    }
    updateThinking(phase, message) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'updateThinking',
                phase,
                message
            });
        }
    }
    clearThinking() {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'clearThinking'
            });
        }
    }
    showToolUse(tool, args) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'showToolUse',
                tool,
                args
            });
        }
    }
    showToolResult(tool, result) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'showToolResult',
                tool,
                result
            });
        }
    }
    showPlan(steps, rationale) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'showPlan',
                steps,
                rationale
            });
        }
    }
    showPatch(patch) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'showPatch',
                patch
            });
        }
    }
    showError(message) {
        if (this.view) {
            this.view.webview.postMessage({
                type: 'showError',
                message
            });
        }
    }
    renderMarkdown(content) {
        return marked.parse(content);
    }
    getHtmlContent(webview) {
        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LoCo Agent</title>
            <style>
                * {
                    box-sizing: border-box;
                    margin: 0;
                    padding: 0;
                }

                body {
                    font-family: var(--vscode-font-family);
                    font-size: 13px;
                    color: var(--vscode-foreground);
                    background-color: var(--vscode-sideBar-background);
                    display: flex;
                    flex-direction: column;
                    height: 100vh;
                }

                #messages-container {
                    flex: 1;
                    overflow-y: auto;
                    padding: 16px;
                    padding-bottom: 8px;
                }

                #messages-container::-webkit-scrollbar {
                    width: 10px;
                }

                #messages-container::-webkit-scrollbar-track {
                    background: transparent;
                }

                #messages-container::-webkit-scrollbar-thumb {
                    background: var(--vscode-scrollbarSlider-background);
                    border-radius: 5px;
                }

                #messages-container::-webkit-scrollbar-thumb:hover {
                    background: var(--vscode-scrollbarSlider-hoverBackground);
                }

                .message {
                    margin-bottom: 20px;
                    animation: slideIn 0.2s ease-out;
                }

                @keyframes slideIn {
                    from {
                        opacity: 0;
                        transform: translateY(10px);
                    }
                    to {
                        opacity: 1;
                        transform: translateY(0);
                    }
                }

                .message-header {
                    display: flex;
                    align-items: center;
                    margin-bottom: 8px;
                    gap: 8px;
                }

                .message-avatar {
                    width: 24px;
                    height: 24px;
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-weight: 600;
                    font-size: 11px;
                }

                .message.user .message-avatar {
                    background-color: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                }

                .message.assistant .message-avatar {
                    background: linear-gradient(135deg, #FF6B35 0%, #F7931E 100%);
                    color: white;
                }

                .message-role {
                    font-weight: 600;
                    font-size: 12px;
                    color: var(--vscode-foreground);
                }

                .message-content {
                    margin-left: 32px;
                    line-height: 1.6;
                    color: var(--vscode-foreground);
                }

                .message-content p {
                    margin: 0 0 12px 0;
                }

                .message-content p:last-child {
                    margin-bottom: 0;
                }

                .message-content code {
                    background-color: var(--vscode-textCodeBlock-background);
                    padding: 2px 6px;
                    border-radius: 3px;
                    font-family: var(--vscode-editor-font-family);
                    font-size: 12px;
                    border: 1px solid var(--vscode-panel-border);
                }

                .message-content pre {
                    background-color: var(--vscode-textCodeBlock-background);
                    padding: 12px;
                    border-radius: 6px;
                    overflow-x: auto;
                    margin: 12px 0;
                    border: 1px solid var(--vscode-panel-border);
                }

                .message-content pre code {
                    background: none;
                    padding: 0;
                    border: none;
                }

                .message-content ul, .message-content ol {
                    margin: 8px 0;
                    padding-left: 24px;
                }

                .message-content li {
                    margin: 4px 0;
                }

                .thinking-indicator {
                    margin-bottom: 20px;
                    padding: 12px;
                    background-color: var(--vscode-inputValidation-infoBackground);
                    border-left: 3px solid var(--vscode-inputValidation-infoBorder);
                    border-radius: 4px;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                    animation: pulse 2s ease-in-out infinite;
                }

                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.7; }
                }

                .thinking-spinner {
                    width: 16px;
                    height: 16px;
                    border: 2px solid var(--vscode-inputValidation-infoBorder);
                    border-top-color: transparent;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                }

                @keyframes spin {
                    to { transform: rotate(360deg); }
                }

                .thinking-text {
                    font-size: 12px;
                    color: var(--vscode-foreground);
                }

                .tool-use {
                    margin: 12px 0 12px 32px;
                    padding: 10px;
                    background-color: var(--vscode-editor-background);
                    border-left: 2px solid var(--vscode-textLink-foreground);
                    border-radius: 4px;
                    font-size: 12px;
                }

                .tool-result {
                    margin: 12px 0 12px 32px;
                    padding: 10px;
                    background-color: var(--vscode-editor-background);
                    border-left: 2px solid var(--vscode-inputValidation-infoBorder);
                    border-radius: 4px;
                    font-size: 12px;
                }

                .tool-name {
                    font-weight: 600;
                    color: var(--vscode-textLink-foreground);
                    margin-bottom: 6px;
                }

                .tool-args {
                    font-family: var(--vscode-editor-font-family);
                    font-size: 11px;
                    color: var(--vscode-descriptionForeground);
                    white-space: pre-wrap;
                    word-break: break-word;
                }

                .plan {
                    margin: 12px 0 12px 32px;
                    padding: 12px;
                    background-color: var(--vscode-editor-background);
                    border-left: 3px solid var(--vscode-charts-blue);
                    border-radius: 4px;
                }

                .plan-title {
                    font-weight: 600;
                    margin-bottom: 10px;
                    color: var(--vscode-charts-blue);
                }

                .plan-step {
                    padding: 6px 0;
                    font-size: 12px;
                    line-height: 1.5;
                }

                .patch {
                    margin: 12px 0 12px 32px;
                    padding: 12px;
                    background-color: var(--vscode-editor-background);
                    border: 1px solid var(--vscode-panel-border);
                    border-radius: 6px;
                }

                .patch-header {
                    font-weight: 600;
                    margin-bottom: 10px;
                    color: var(--vscode-charts-orange);
                }

                .patch-actions {
                    margin-top: 12px;
                    display: flex;
                    gap: 8px;
                }

                .patch-actions button {
                    padding: 6px 12px;
                    background-color: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 500;
                    transition: background-color 0.2s;
                }

                .patch-actions button:hover {
                    background-color: var(--vscode-button-hoverBackground);
                }

                .patch-actions button.secondary {
                    background-color: var(--vscode-button-secondaryBackground);
                    color: var(--vscode-button-secondaryForeground);
                }

                .patch-actions button.secondary:hover {
                    background-color: var(--vscode-button-secondaryHoverBackground);
                }

                .error-message {
                    margin: 12px 0 12px 32px;
                    padding: 10px;
                    background-color: var(--vscode-inputValidation-errorBackground);
                    border-left: 3px solid var(--vscode-inputValidation-errorBorder);
                    border-radius: 4px;
                    color: var(--vscode-errorForeground);
                    font-size: 12px;
                }

                #input-container {
                    border-top: 1px solid var(--vscode-panel-border);
                    padding: 12px 16px;
                    background-color: var(--vscode-sideBar-background);
                }

                #input-wrapper {
                    display: flex;
                    gap: 8px;
                    align-items: flex-end;
                }

                #message-input {
                    flex: 1;
                    padding: 10px 12px;
                    border: 1px solid var(--vscode-input-border);
                    background-color: var(--vscode-input-background);
                    color: var(--vscode-input-foreground);
                    border-radius: 6px;
                    font-family: var(--vscode-font-family);
                    font-size: 13px;
                    resize: none;
                    min-height: 40px;
                    max-height: 200px;
                    line-height: 1.4;
                }

                #message-input:focus {
                    outline: none;
                    border-color: var(--vscode-focusBorder);
                }

                #send-button {
                    padding: 10px 16px;
                    background-color: var(--vscode-button-background);
                    color: var(--vscode-button-foreground);
                    border: none;
                    border-radius: 6px;
                    cursor: pointer;
                    font-weight: 600;
                    font-size: 13px;
                    transition: background-color 0.2s;
                    white-space: nowrap;
                    height: 40px;
                }

                #send-button:hover:not(:disabled) {
                    background-color: var(--vscode-button-hoverBackground);
                }

                #send-button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .empty-state {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                    text-align: center;
                    padding: 40px 20px;
                    color: var(--vscode-descriptionForeground);
                }

                .empty-state-icon {
                    font-size: 48px;
                    margin-bottom: 16px;
                    opacity: 0.6;
                }

                .empty-state-title {
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 8px;
                    color: var(--vscode-foreground);
                }

                .empty-state-description {
                    font-size: 13px;
                    line-height: 1.5;
                    max-width: 300px;
                }

                /* Parity styling */
                html {
                    display: flex;
                    flex: 1;
                    height: 100%;
                    overscroll-behavior: none;
                    position: relative;
                    color-scheme: dark;
                    --app-brand: #f3a15e;
                    --app-brand-strong: #e0894b;
                    --app-brand-soft: rgba(243, 161, 94, 0.18);
                    --app-spacing-small: 4px;
                    --app-spacing-medium: 8px;
                    --app-spacing-large: 12px;
                    --app-spacing-xlarge: 16px;
                    --corner-radius-small: 6px;
                    --corner-radius-medium: 10px;
                    --corner-radius-large: 14px;
                    --app-monospace-font-family: var(--vscode-editor-font-family, monospace);
                    --app-monospace-font-size: var(--vscode-editor-font-size, 12px);
                    --app-monospace-font-size-small: calc(var(--vscode-editor-font-size, 12px) - 2px);
                    --app-text-font-family: var(--vscode-chat-font-family, var(--vscode-font-family, sans-serif));
                    --app-text-font-size: var(--vscode-chat-font-size, var(--vscode-font-size, 13px));
                    --app-primary-foreground: #f5f6f8;
                    --app-primary-background: #0f1115;
                    --app-primary-border-color: #1f2532;
                    --app-secondary-foreground: #9aa3b2;
                    --app-input-foreground: #f5f6f8;
                    --app-input-background: #151a24;
                    --app-input-border: #242b3a;
                    --app-input-active-border: #f3a15e;
                    --app-input-placeholder-foreground: #697388;
                    --app-input-secondary-foreground: #cbd0d8;
                    --app-input-secondary-background: #121621;
                    --app-tool-background: #141922;
                    --app-list-padding: 0px;
                    --app-list-item-padding: 6px 10px;
                    --app-list-border-color: transparent;
                    --app-list-border-radius: 8px;
                    --app-list-hover-background: rgba(255, 255, 255, 0.06);
                    --app-list-active-background: rgba(243, 161, 94, 0.16);
                    --app-list-active-foreground: #f5f6f8;
                    --app-list-gap: 4px;
                    --app-menu-background: #121621;
                    --app-menu-border: #252c3a;
                    --app-menu-foreground: #f5f6f8;
                    --app-menu-selection-background: rgba(243, 161, 94, 0.2);
                    --app-menu-selection-foreground: #f5f6f8;
                    --app-warning-foreground: #f5f6f8;
                    --app-warning-background: #1a1f2c;
                    --app-badge-foreground: #0f1115;
                    --app-badge-background: #f3a15e;
                    --app-header-background: #0f1115;
                    --app-splitter-background: #1f2532;
                    --app-splitter-hover-background: #2b3342;
                    --app-progressbar-background: #f3a15e;
                    --app-progressbar-border: #2b3342;
                    --app-widget-border: #1f2532;
                    --app-editor-highlight-background: rgba(255, 255, 255, 0.04);
                    --app-ghost-button-hover-background: rgba(255, 255, 255, 0.06);
                    --app-button-foreground: #1a120c;
                    --app-button-background: #f3a15e;
                    --app-button-hover-background: #ffb675;
                    --app-transparent-inner-border: rgba(255, 255, 255, 0.08);
                    --app-spinner-foreground: #f3a15e;
                    --app-error-foreground: #ff7a7a;
                    --app-modal-background: rgba(15, 17, 21, 0.75);
                    --app-message-user-bg: rgba(243, 161, 94, 0.18);
                    --app-message-user-border: rgba(243, 161, 94, 0.35);
                    --app-message-assistant-bg: #151a24;
                    --app-message-assistant-border: #212838;
                }

                .vscode-light {
                    --app-transparent-inner-border: rgba(255, 255, 255, 0.12);
                    --app-spinner-foreground: var(--app-brand-strong);
                }

                body {
                    margin: 0;
                    display: flex;
                    flex: 1;
                    padding: 0;
                    overscroll-behavior: none;
                    max-width: 100%;
                    font-size: var(--app-text-font-size);
                    font-family: var(--app-text-font-family);
                    color: var(--app-primary-foreground);
                    background-color: var(--app-primary-background);
                }

                #root {
                    display: flex;
                    flex: 1;
                    flex-direction: column;
                    overflow: hidden;
                    color: var(--app-primary-foreground);
                    background-color: var(--app-primary-background);
                    user-select: none;
                }

                #header {
                    display: flex;
                    border-bottom: 1px solid var(--app-primary-border-color);
                    padding: 10px 12px;
                    gap: 6px;
                    background-color: var(--app-header-background);
                    justify-content: flex-start;
                    user-select: none;
                }

                #session-button {
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    padding: 4px 10px;
                    background: transparent;
                    border: none;
                    border-radius: 8px;
                    cursor: pointer;
                    outline: none;
                    min-width: 0;
                    max-width: 300px;
                    overflow: hidden;
                    font-size: var(--app-text-font-size);
                    font-family: var(--app-text-font-family);
                    color: var(--app-primary-foreground);
                }

                #session-button:focus,
                #session-button:hover {
                    background: var(--app-ghost-button-hover-background);
                }

                .session-button-content {
                    display: flex;
                    align-items: center;
                    gap: 4px;
                    max-width: 300px;
                    overflow: hidden;
                }

                .session-button-text {
                    overflow: hidden;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                    font-weight: 500;
                }

                .session-button-icon {
                    flex-shrink: 0;
                    width: 16px;
                    height: 16px;
                    min-width: 16px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    font-size: 10px;
                    opacity: 0.8;
                }

                .header-spacer {
                    flex: 1;
                }

                #new-session-button {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 28px;
                    height: 28px;
                    border-radius: 8px;
                    border: 1px solid transparent;
                    background: transparent;
                    color: var(--app-primary-foreground);
                    cursor: pointer;
                    font-size: 16px;
                }

                #new-session-button:hover {
                    background: var(--app-ghost-button-hover-background);
                }

                #chat-container {
                    display: flex;
                    flex-direction: column;
                    flex: 1;
                    overflow: hidden;
                    position: relative;
                    line-height: 1.5;
                }

                #messages-container {
                    flex: 1;
                    overflow-y: auto;
                    overflow-x: hidden;
                    padding: 24px 20px 140px;
                    display: flex;
                    flex-direction: column;
                    gap: 0;
                    background: linear-gradient(180deg, rgba(15, 17, 21, 0.98) 0%, rgba(15, 17, 21, 1) 100%);
                    position: relative;
                    min-width: 0;
                }

                #messages-container:focus {
                    outline: none;
                }

                #message-gradient {
                    position: absolute;
                    bottom: 0;
                    left: 0;
                    right: 0;
                    height: 160px;
                    background: linear-gradient(to bottom, rgba(15, 17, 21, 0) 0%, var(--app-primary-background) 100%);
                    pointer-events: none;
                    z-index: 2;
                }

                .message {
                    color: var(--app-primary-foreground);
                    display: flex;
                    gap: 0;
                    align-items: flex-start;
                    padding: 12px 0 16px;
                    flex-direction: column;
                    position: relative;
                    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
                }

                .message.user {
                    align-items: flex-end;
                }

                .message.assistant {
                    align-items: flex-start;
                }

                .message.user .message-content {
                    align-self: flex-end;
                    max-width: 92%;
                }

                .message.assistant .message-content {
                    max-width: 92%;
                }

                .message-content {
                    line-height: 1.5;
                    white-space: pre-wrap;
                    word-break: break-word;
                    user-select: text;
                }

                .message-bubble {
                    border: 1px solid var(--app-input-border);
                    border-radius: var(--corner-radius-medium);
                    background-color: var(--app-input-background);
                    padding: 8px 10px;
                    display: inline-block;
                    max-width: 100%;
                    overflow-x: hidden;
                    overflow-y: hidden;
                    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
                }

                .message.user .message-bubble {
                    background-color: var(--app-message-user-bg);
                    border-color: var(--app-message-user-border);
                }

                .message-content p {
                    margin: 0 0 12px 0;
                }

                .message-content p:last-child {
                    margin-bottom: 0;
                }

                .message-content code {
                    font-family: var(--app-monospace-font-family);
                    font-size: 0.9em;
                }

                .message-content pre {
                    background-color: var(--app-tool-background);
                    padding: 8px;
                    border-radius: var(--corner-radius-small);
                    overflow-x: auto;
                    margin: 8px 0;
                    border: 1px solid var(--app-input-border);
                    font-family: var(--app-monospace-font-family);
                    font-size: 0.9em;
                }

                .message-content pre code {
                    background: none;
                    padding: 0;
                    border: none;
                }

                .message-content ul,
                .message-content ol {
                    margin: 8px 0;
                    padding-left: 24px;
                }

                .message-content li {
                    margin: 4px 0;
                }

                .thinking-indicator {
                    display: flex;
                    align-items: center;
                    margin-top: 4px;
                    margin-left: 0;
                    animation: fadeIn 0.3s ease-in-out;
                    height: 1.85em;
                    color: var(--app-secondary-foreground);
                }

                .thinking-spinner {
                    width: 14px;
                    height: 14px;
                    border: 2px solid var(--app-spinner-foreground);
                    border-top-color: transparent;
                    border-radius: 50%;
                    animation: spin 0.8s linear infinite;
                    margin-right: 6px;
                }

                .thinking-text {
                    font-size: 12px;
                }

                .timeline-message {
                    position: relative;
                    align-items: flex-start;
                    padding-left: 30px;
                    user-select: text;
                }

                .timeline-message:before {
                    content: "*";
                    position: absolute;
                    left: 8px;
                    padding-top: 2px;
                    font-size: 10px;
                    color: var(--app-secondary-foreground);
                    z-index: 1;
                }

                .timeline-message:after {
                    content: "";
                    position: absolute;
                    left: 12px;
                    top: 0;
                    bottom: 0;
                    width: 1px;
                    background-color: var(--app-primary-border-color);
                }

                .timeline-message.progress:before {
                    color: var(--app-spinner-foreground);
                }

                .tool-name {
                    font-weight: 500;
                    color: var(--app-primary-foreground);
                    margin-bottom: 4px;
                }

                .tool-args {
                    font-family: var(--app-monospace-font-family);
                    font-size: 0.85em;
                    color: var(--app-secondary-foreground);
                    white-space: pre-wrap;
                    word-break: break-word;
                    margin: 0;
                }

                .tool-card {
                    border: 0.5px solid var(--app-input-border);
                    border-radius: 10px;
                    background: var(--app-tool-background);
                    margin: 8px 0;
                    max-width: 100%;
                    font-size: 1em;
                    align-items: start;
                }

                .tool-card-header {
                    padding: 8px;
                    font-weight: 600;
                    color: var(--app-primary-foreground);
                }

                .tool-card-body {
                    margin: 0;
                    padding: 8px;
                    white-space: pre-wrap;
                    word-break: break-word;
                    font-family: var(--app-monospace-font-family);
                    font-size: 0.85em;
                    color: var(--app-primary-foreground);
                    border-top: 0.5px solid var(--app-input-border);
                }

                .plan-steps {
                    padding: 0 8px 8px 8px;
                }

                .plan-step {
                    padding: 4px 0;
                    font-size: 12px;
                    line-height: 1.5;
                }

                .plan-rationale {
                    margin: 6px 8px 8px;
                    font-style: italic;
                    font-size: 11px;
                    opacity: 0.8;
                }

                .patch-actions {
                    margin: 8px;
                    display: flex;
                    gap: 8px;
                }

                .patch-actions button {
                    padding: 6px 12px;
                    background-color: var(--app-button-background);
                    color: var(--app-button-foreground);
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                    font-size: 12px;
                    font-weight: 500;
                    transition: background-color 0.2s;
                }

                .patch-actions button:hover {
                    background-color: var(--app-button-hover-background);
                }

                .patch-actions button.secondary {
                    background-color: transparent;
                    color: var(--app-primary-foreground);
                    box-shadow: inset 0 0 0 1px var(--app-transparent-inner-border);
                }

                .patch-actions button.secondary:hover {
                    background-color: var(--app-ghost-button-hover-background);
                }

                .error-banner {
                    background-color: color-mix(in srgb, var(--app-primary-background) 96%, var(--app-error-foreground) 4%);
                    color: var(--app-error-foreground);
                    border-bottom: 1px solid var(--app-error-foreground);
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    font-size: 13px;
                }

                .error-message {
                    flex: 1;
                    margin-top: 2px;
                    word-wrap: break-word;
                    padding: 10px 12px;
                    user-select: text;
                }

                .error-dismiss {
                    background: none;
                    border: none;
                    color: var(--app-error-foreground);
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    width: 44px;
                    height: 44px;
                    font-size: 20px;
                    line-height: 1;
                }

                #composer-container {
                    position: absolute;
                    bottom: 16px;
                    left: 16px;
                    right: 16px;
                    display: flex;
                    flex-direction: column;
                    z-index: 20;
                }

                #composer {
                    display: flex;
                    flex-direction: column;
                    padding: 10px;
                    background-color: var(--app-input-secondary-background);
                    border: 1px solid var(--app-input-border);
                    border-radius: var(--corner-radius-large);
                    box-shadow: 0 24px 40px rgba(0, 0, 0, 0.38);
                }

                #composer:focus-within {
                    border-color: color-mix(in srgb, var(--app-input-active-border) 65%, transparent);
                }

                #message-input {
                    width: 100%;
                    border: none;
                    background: transparent;
                    color: var(--app-input-foreground);
                    font-family: var(--app-text-font-family);
                    font-size: var(--app-text-font-size);
                    resize: none;
                    line-height: 1.4;
                    min-height: 32px;
                    max-height: 200px;
                }

                #message-input:focus {
                    outline: none;
                }

                #message-input::placeholder {
                    color: var(--app-input-placeholder-foreground);
                }

                #composer-actions {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-top: 8px;
                    gap: 8px;
                }

                #attach-button,
                #send-button {
                    padding: 6px 8px;
                    border-radius: 4px;
                    border: none;
                    background: transparent;
                    color: var(--app-primary-foreground);
                    font-family: var(--app-text-font-family);
                    font-size: var(--app-text-font-size);
                    box-shadow: inset 0 0 0 1px var(--app-transparent-inner-border);
                    cursor: pointer;
                }

                #attach-button:hover,
                #send-button:hover:not(:disabled) {
                    background-color: var(--app-ghost-button-hover-background);
                }

                #send-button.primary {
                    background-color: var(--app-button-background);
                    color: var(--app-button-foreground);
                    box-shadow: none;
                }

                #send-button.primary:hover:not(:disabled) {
                    background-color: var(--app-button-hover-background);
                }

                #send-button:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .empty-state {
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    flex: 1;
                    animation: fadeIn 0.3s ease-in-out;
                    user-select: none;
                    color: var(--app-secondary-foreground);
                }

                .empty-state-content {
                    text-align: center;
                    max-width: 480px;
                    position: relative;
                    top: -30px;
                }

                .empty-state-title {
                    font-size: 14px;
                    font-weight: 600;
                    color: var(--app-primary-foreground);
                    margin-bottom: 6px;
                }

                .empty-state-description {
                    font-size: 12px;
                    line-height: 1.6;
                }

                @keyframes fadeIn {
                    0% {
                        opacity: 0;
                    }
                    100% {
                        opacity: 1;
                    }
                }

                @keyframes spin {
                    to {
                        transform: rotate(360deg);
                    }
                }
            </style>
        </head>
                <body>
            <div id="root">
                <div id="header">
                    <button id="session-button" type="button" title="Sessions">
                        <span class="session-button-content">
                            <span class="session-button-text">Sessions</span>
                            <span class="session-button-icon">v</span>
                        </span>
                    </button>
                    <div class="header-spacer"></div>
                    <button id="new-session-button" type="button" title="New chat">+</button>
                </div>
                <div id="chat-container">
                    <div id="messages-container" tabindex="0">
                        <div class="empty-state" id="empty-state">
                            <div class="empty-state-content">
                                <div class="empty-state-title">LoCo Agent</div>
                                <div class="empty-state-description">
                                    Your AI coding assistant with self-improving capabilities powered by ACE
                                </div>
                            </div>
                        </div>
                    </div>
                    <div id="message-gradient"></div>
                    <div id="composer-container">
                        <div id="composer">
                            <textarea id="message-input" placeholder="Ask a question or type / for commands..." rows="1"></textarea>
                            <div id="composer-actions">
                                <button id="attach-button" type="button">Attach</button>
                                <button id="send-button" type="button" class="primary">Send</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <script>
                const vscode = acquireVsCodeApi();
                const messagesContainer = document.getElementById('messages-container');
                const messageInput = document.getElementById('message-input');
                const sendButton = document.getElementById('send-button');
                const attachButton = document.getElementById('attach-button');
                const sessionButton = document.getElementById('session-button');
                const newSessionButton = document.getElementById('new-session-button');
                const emptyState = document.getElementById('empty-state');

                let currentAssistantMessage = null;
                let hasMessages = false;

                function updateSendButtonState() {
                    const hasText = Boolean(messageInput.value.trim());
                    sendButton.disabled = !hasText;
                    sendButton.classList.toggle('primary', hasText);
                }

                // Auto-resize textarea
                messageInput.addEventListener('input', () => {
                    messageInput.style.height = 'auto';
                    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + 'px';
                    updateSendButtonState();
                });

                // Send message
                function sendMessage() {
                    const message = messageInput.value.trim();
                    if (message) {
                        vscode.postMessage({
                            type: 'sendMessage',
                            message: message
                        });
                        messageInput.value = '';
                        messageInput.style.height = 'auto';
                        updateSendButtonState();
                    }
                }

                sendButton.addEventListener('click', sendMessage);

                messageInput.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                    }
                });

                updateSendButtonState();

                if (attachButton) {
                    attachButton.addEventListener('click', () => {
                        vscode.postMessage({ type: 'openMentionPicker' });
                    });
                }

                if (sessionButton) {
                    sessionButton.addEventListener('click', () => {
                        messageInput.focus();
                    });
                }

                if (newSessionButton) {
                    newSessionButton.addEventListener('click', () => {
                        messageInput.focus();
                    });
                }

                // Handle messages from extension
                window.addEventListener('message', event => {
                    const message = event.data;

                    // Hide empty state on first message
                    if (!hasMessages && emptyState) {
                        emptyState.style.display = 'none';
                        hasMessages = true;
                    }

                    switch (message.type) {
                        case 'addMessage':
                            addMessage(message.role, message.content);
                            updateSendButtonState();
                            currentAssistantMessage = null;
                            break;
                        case 'appendDelta':
                            appendDelta(message.delta);
                            break;
                        case 'updateThinking':
                            updateThinking(message.phase, message.message);
                            break;
                        case 'clearThinking':
                            clearThinking();
                            break;
                        case 'showToolUse':
                            showToolUse(message.tool, message.args);
                            break;
                        case 'showToolResult':
                            showToolResult(message.tool, message.result);
                            break;
                        case 'showPlan':
                            showPlan(message.steps, message.rationale);
                            break;
                        case 'showPatch':
                            showPatch(message.patch);
                            break;
                        case 'showError':
                            showError(message.message);
                            updateSendButtonState();
                            break;
                        case 'insertMention':
                            insertMention(message.text);
                            break;
                    }
                });

                function insertMention(text) {
                    if (!text) {
                        return;
                    }
                    const start = messageInput.selectionStart || 0;
                    const end = messageInput.selectionEnd || 0;
                    const before = messageInput.value.slice(0, start);
                    const after = messageInput.value.slice(end);
                    messageInput.value = before + text + after;
                    const cursor = start + text.length;
                    messageInput.setSelectionRange(cursor, cursor);
                    messageInput.focus();
                    messageInput.dispatchEvent(new Event('input'));
                }

                function addMessage(role, content) {
                    if (role === 'assistant' && currentAssistantMessage) {
                        currentAssistantMessage.innerHTML = content;
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        return;
                    }

                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'message ' + role;

                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content';

                    if (role === 'user') {
                        const bubbleDiv = document.createElement('div');
                        bubbleDiv.className = 'message-bubble';
                        bubbleDiv.innerHTML = content;
                        contentDiv.appendChild(bubbleDiv);
                    } else {
                        contentDiv.innerHTML = content;
                    }

                    messageDiv.appendChild(contentDiv);
                    messagesContainer.appendChild(messageDiv);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function appendDelta(delta) {
                    if (!currentAssistantMessage) {
                        const messageDiv = document.createElement('div');
                        messageDiv.className = 'message assistant';

                        const contentDiv = document.createElement('div');
                        contentDiv.className = 'message-content';

                        messageDiv.appendChild(contentDiv);
                        messagesContainer.appendChild(messageDiv);
                        currentAssistantMessage = contentDiv;
                    }

                    currentAssistantMessage.textContent += delta;
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                let thinkingDiv = null;

                function updateThinking(phase, message) {
                    if (!thinkingDiv) {
                        thinkingDiv = document.createElement('div');
                        thinkingDiv.className = 'thinking-indicator';
                        thinkingDiv.innerHTML = \`
                            <div class="thinking-spinner"></div>
                            <div class="thinking-text"></div>
                        \`;
                        messagesContainer.appendChild(thinkingDiv);
                    }

                    thinkingDiv.querySelector('.thinking-text').textContent = message || \`\${phase}...\`;
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function clearThinking() {
                    if (thinkingDiv) {
                        thinkingDiv.remove();
                        thinkingDiv = null;
                    }
                }

                function showToolUse(tool, args) {
                    currentAssistantMessage = null;
                    const toolCard = document.createElement('div');
                    toolCard.className = 'tool-card';

                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'tool-card-header';
                    headerDiv.textContent = 'Tool: ' + tool;

                    const bodyPre = document.createElement('pre');
                    bodyPre.className = 'tool-card-body';
                    bodyPre.textContent = JSON.stringify(args, null, 2);

                    toolCard.appendChild(headerDiv);
                    toolCard.appendChild(bodyPre);

                    messagesContainer.appendChild(toolCard);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function showToolResult(tool, result) {
                    currentAssistantMessage = null;
                    const resultCard = document.createElement('div');
                    resultCard.className = 'tool-card';

                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'tool-card-header';
                    headerDiv.textContent = 'Result: ' + tool;

                    const bodyPre = document.createElement('pre');
                    bodyPre.className = 'tool-card-body';
                    bodyPre.textContent = JSON.stringify(result, null, 2);

                    resultCard.appendChild(headerDiv);
                    resultCard.appendChild(bodyPre);

                    messagesContainer.appendChild(resultCard);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function showPlan(steps, rationale) {
                    const planCard = document.createElement('div');
                    planCard.className = 'tool-card';

                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'tool-card-header';
                    headerDiv.textContent = 'Plan';

                    const stepsDiv = document.createElement('div');
                    stepsDiv.className = 'plan-steps';

                    const planSteps = Array.isArray(steps) ? steps : [];
                    planSteps.forEach((step, index) => {
                        const stepDiv = document.createElement('div');
                        stepDiv.className = 'plan-step';
                        stepDiv.textContent = (index + 1) + '. ' + (step.description || step);
                        stepsDiv.appendChild(stepDiv);
                    });

                    planCard.appendChild(headerDiv);
                    planCard.appendChild(stepsDiv);

                    if (rationale) {
                        const rationaleDiv = document.createElement('div');
                        rationaleDiv.className = 'plan-rationale';
                        rationaleDiv.textContent = rationale;
                        planCard.appendChild(rationaleDiv);
                    }

                    messagesContainer.appendChild(planCard);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function showPatch(patch) {
                    const patchCard = document.createElement('div');
                    patchCard.className = 'tool-card';

                    const headerDiv = document.createElement('div');
                    headerDiv.className = 'tool-card-header';
                    headerDiv.textContent = 'Proposed changes: ' + patch.file_path;

                    const bodyPre = document.createElement('pre');
                    bodyPre.className = 'tool-card-body';
                    bodyPre.textContent = patch.diff || patch.content || 'No diff available';

                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'patch-actions';

                    const acceptButton = document.createElement('button');
                    acceptButton.textContent = 'Accept';
                    acceptButton.addEventListener('click', () => acceptPatch(patch.id));

                    const viewButton = document.createElement('button');
                    viewButton.className = 'secondary';
                    viewButton.textContent = 'View Diff';
                    viewButton.addEventListener('click', () => viewDiff(patch.id));

                    const rejectButton = document.createElement('button');
                    rejectButton.className = 'secondary';
                    rejectButton.textContent = 'Reject';
                    rejectButton.addEventListener('click', () => rejectPatch(patch.id));

                    const undoButton = document.createElement('button');
                    undoButton.className = 'secondary';
                    undoButton.textContent = 'Undo';
                    undoButton.addEventListener('click', () => undoPatch(patch.id));

                    actionsDiv.appendChild(acceptButton);
                    actionsDiv.appendChild(viewButton);
                    actionsDiv.appendChild(rejectButton);
                    actionsDiv.appendChild(undoButton);

                    patchCard.appendChild(headerDiv);
                    patchCard.appendChild(bodyPre);
                    patchCard.appendChild(actionsDiv);

                    messagesContainer.appendChild(patchCard);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function showError(message) {
                    const errorBanner = document.createElement('div');
                    errorBanner.className = 'error-banner';

                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'error-message';
                    messageDiv.textContent = message;

                    const dismissButton = document.createElement('button');
                    dismissButton.className = 'error-dismiss';
                    dismissButton.textContent = 'x';
                    dismissButton.addEventListener('click', () => {
                        errorBanner.remove();
                    });

                    errorBanner.appendChild(messageDiv);
                    errorBanner.appendChild(dismissButton);

                    messagesContainer.appendChild(errorBanner);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                }

                function acceptPatch(patchId) {
                    vscode.postMessage({ type: 'acceptPatch', patchId });
                }

                function rejectPatch(patchId) {
                    vscode.postMessage({ type: 'rejectPatch', patchId });
                }

                function viewDiff(patchId) {
                    vscode.postMessage({ type: 'viewDiff', patchId });
                }

                function undoPatch(patchId) {
                    vscode.postMessage({ type: 'undoPatch', patchId });
                }

                // Focus input on load
                messageInput.focus();
            </script>
        </body>
        </html>`;
    }
}
exports.SidebarProvider = SidebarProvider;
//# sourceMappingURL=SidebarProvider.js.map