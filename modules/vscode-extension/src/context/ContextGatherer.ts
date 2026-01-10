/**
 * Automatic Context Gathering
 * Collects workspace signals for the agent
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { TextDecoder } from 'util';

export interface WorkspaceContext {
    active_editor?: {
        file_path: string;
        language: string;
        selection?: {
            start: { line: number; character: number };
            end: { line: number; character: number };
        };
        visible_range?: {
            start: number;
            end: number;
        };
        content_hash?: string;
    };
    open_editors?: Array<{
        file_path: string;
        is_dirty: boolean;
        visible: boolean;
    }>;
    diagnostics?: Array<{
        file_path: string;
        severity: string;
        message: string;
        line: number;
        character: number;
        source: string;
    }>;
    terminal_output?: {
        command?: string;
        exit_code?: number;
        stdout?: string;
        stderr?: string;
        timestamp: string;
    };
    git_context?: {
        branch?: string;
        staged_files: string[];
        modified_files: string[];
        recent_commits?: Array<{
            sha: string;
            message: string;
            author: string;
            timestamp: string;
        }>;
    };
    mentions?: Mention[];
    command?: string;
    include_workspace_rag?: boolean;
}

export interface Mention {
    type: string;
    path?: string;
    name?: string;
    line?: number;
    content?: string;
    truncated?: boolean;
}

export class ContextGatherer {
    private lastTerminalOutput: string = '';

    constructor() {
        // Listen for terminal output (if available)
        // Note: VS Code doesn't expose terminal output easily
        // This is a placeholder for future implementation
    }

    async gatherContext(message?: string): Promise<WorkspaceContext> {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const autoContext = config.get<boolean>('autoContext', true);

        const context: WorkspaceContext = {
            include_workspace_rag: config.get<boolean>('includeWorkspaceRag', true)
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

    private gatherDiagnostics(): Array<any> {
        const diagnostics: Array<any> = [];

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

    private async gatherGitContext(): Promise<any> {
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
                .map((change: any) => this.getRelativePath(change.uri.fsPath));

            const staged_files = state.indexChanges
                .map((change: any) => this.getRelativePath(change.uri.fsPath));

            return {
                branch,
                staged_files,
                modified_files
            };
        } catch (error) {
            console.error('Failed to gather git context:', error);
            return { staged_files: [], modified_files: [] };
        }
    }

    private getSeverityString(severity: vscode.DiagnosticSeverity | undefined): string {
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

    private getRelativePath(absolutePath: string): string {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (workspaceFolder) {
            const relative = path.relative(workspaceFolder.uri.fsPath, absolutePath);
            return relative.replace(/\\/g, '/');
        }
        return absolutePath;
    }

    private parseMentions(message: string): string[] {
        const regex = /@([A-Za-z0-9_./-]+)/g;
        const matches = new Set<string>();
        let match: RegExpExecArray | null;
        while ((match = regex.exec(message)) !== null) {
            matches.add(match[1]);
        }
        return Array.from(matches);
    }

    private async resolveMentions(message: string): Promise<Mention[]> {
        const mentions: Mention[] = [];
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

    private async resolveFileMention(
        token: string,
        workspaceFolder: vscode.WorkspaceFolder
    ): Promise<Mention | null> {
        const maxChars = 4000;
        const workspacePath = workspaceFolder.uri.fsPath;
        const directPath = path.join(workspacePath, token);

        const readFileContent = async (uri: vscode.Uri) => {
            const bytes = await vscode.workspace.fs.readFile(uri);
            const content = new TextDecoder('utf-8').decode(bytes);
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
        } catch {
            // Fall back to glob search
        }

        const glob = token.includes('/') ? token : `**/${token}`;
        const matches = await vscode.workspace.findFiles(
            glob,
            '**/{.git,node_modules,dist,build,out,.venv,venv}/**',
            5
        );

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
