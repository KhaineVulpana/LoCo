"use strict";
/**
 * Automatic Context Gathering
 * Collects workspace signals for the agent
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
exports.ContextGatherer = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const util_1 = require("util");
class ContextGatherer {
    constructor() {
        this.lastTerminalOutput = '';
        // Listen for terminal output (if available)
        // Note: VS Code doesn't expose terminal output easily
        // This is a placeholder for future implementation
    }
    async gatherContext(message) {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const autoContext = config.get('autoContext', true);
        const context = {
            include_workspace_rag: config.get('includeWorkspaceRag', true)
        };
        if (message) {
            context.mentions = await this.resolveMentions(message);
        }
        if (!autoContext) {
            return context;
        }
        // Get active editor
        const editor = vscode.window.activeTextEditor;
        if (editor) {
            const document = editor.document;
            const selection = editor.selection;
            const visibleRanges = editor.visibleRanges;
            context.active_editor = {
                file_path: this.getRelativePath(document.uri.fsPath),
                language: document.languageId
            };
            // Add selection if non-empty
            if (!selection.isEmpty) {
                context.active_editor.selection = {
                    start: {
                        line: selection.start.line,
                        character: selection.start.character
                    },
                    end: {
                        line: selection.end.line,
                        character: selection.end.character
                    }
                };
            }
            // Add visible range
            if (visibleRanges.length > 0) {
                context.active_editor.visible_range = {
                    start: visibleRanges[0].start.line,
                    end: visibleRanges[0].end.line
                };
            }
        }
        // Get open editors
        context.open_editors = vscode.window.visibleTextEditors.map(editor => ({
            file_path: this.getRelativePath(editor.document.uri.fsPath),
            is_dirty: editor.document.isDirty,
            visible: true
        }));
        // Get diagnostics
        context.diagnostics = this.gatherDiagnostics();
        // Get git context
        context.git_context = await this.gatherGitContext();
        return context;
    }
    gatherDiagnostics() {
        const diagnostics = [];
        for (const [uri, fileDiagnostics] of vscode.languages.getDiagnostics()) {
            for (const diagnostic of fileDiagnostics) {
                diagnostics.push({
                    file_path: this.getRelativePath(uri.fsPath),
                    severity: this.getSeverityString(diagnostic.severity),
                    message: diagnostic.message,
                    line: diagnostic.range.start.line,
                    character: diagnostic.range.start.character,
                    source: diagnostic.source || 'unknown'
                });
            }
        }
        return diagnostics;
    }
    async gatherGitContext() {
        try {
            const gitExtension = vscode.extensions.getExtension('vscode.git');
            if (!gitExtension) {
                return { staged_files: [], modified_files: [] };
            }
            const git = gitExtension.exports.getAPI(1);
            const repo = git.repositories[0];
            if (!repo) {
                return { staged_files: [], modified_files: [] };
            }
            const state = repo.state;
            const branch = state.HEAD?.name;
            const modified_files = state.workingTreeChanges
                .map((change) => this.getRelativePath(change.uri.fsPath));
            const staged_files = state.indexChanges
                .map((change) => this.getRelativePath(change.uri.fsPath));
            return {
                branch,
                staged_files,
                modified_files
            };
        }
        catch (error) {
            console.error('Failed to gather git context:', error);
            return { staged_files: [], modified_files: [] };
        }
    }
    getSeverityString(severity) {
        switch (severity) {
            case vscode.DiagnosticSeverity.Error:
                return 'error';
            case vscode.DiagnosticSeverity.Warning:
                return 'warning';
            case vscode.DiagnosticSeverity.Information:
                return 'info';
            case vscode.DiagnosticSeverity.Hint:
                return 'hint';
            default:
                return 'unknown';
        }
    }
    getRelativePath(absolutePath) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
            const relative = path.relative(workspaceFolder.uri.fsPath, absolutePath);
            return relative.replace(/\\/g, '/');
        }
        return absolutePath;
    }
    parseMentions(message) {
        const regex = /@([A-Za-z0-9_./-]+)/g;
        const matches = new Set();
        let match;
        while ((match = regex.exec(message)) !== null) {
            matches.add(match[1]);
        }
        return Array.from(matches);
    }
    async resolveMentions(message) {
        const mentions = [];
        const tokens = this.parseMentions(message);
        if (!tokens.length) {
            return mentions;
        }
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return mentions;
        }
        const maxMentions = 5;
        for (const token of tokens.slice(0, maxMentions)) {
            const resolved = await this.resolveFileMention(token, workspaceFolder);
            if (resolved) {
                mentions.push(resolved);
            }
        }
        return mentions;
    }
    async resolveFileMention(token, workspaceFolder) {
        const maxChars = 4000;
        const workspacePath = workspaceFolder.uri.fsPath;
        const directPath = path.join(workspacePath, token);
        const readFileContent = async (uri) => {
            const bytes = await vscode.workspace.fs.readFile(uri);
            const content = new util_1.TextDecoder('utf-8').decode(bytes);
            const truncated = content.length > maxChars;
            return {
                content: truncated ? content.slice(0, maxChars) : content,
                truncated
            };
        };
        try {
            const stat = await vscode.workspace.fs.stat(vscode.Uri.file(directPath));
            if (stat.type === vscode.FileType.File) {
                const fileUri = vscode.Uri.file(directPath);
                const relative = this.getRelativePath(directPath);
                const { content, truncated } = await readFileContent(fileUri);
                return {
                    type: 'file',
                    path: relative,
                    content,
                    truncated
                };
            }
        }
        catch {
            // Fall back to glob search
        }
        const glob = token.includes('/') ? token : `**/${token}`;
        const matches = await vscode.workspace.findFiles(glob, '**/{.git,node_modules,dist,build,out,.venv,venv}/**', 5);
        if (!matches.length) {
            return {
                type: 'unknown',
                name: token
            };
        }
        const target = matches[0];
        const relative = this.getRelativePath(target.fsPath);
        const { content, truncated } = await readFileContent(target);
        return {
            type: 'file',
            path: relative,
            content,
            truncated
        };
    }
}
exports.ContextGatherer = ContextGatherer;
//# sourceMappingURL=ContextGatherer.js.map