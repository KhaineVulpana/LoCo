/**
 * Automatic Context Gathering
 * Collects workspace signals for the agent
 */

import * as vscode from 'vscode';

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
    mentions?: Array<{
        type: string;
        path?: string;
        name?: string;
        line?: number;
    }>;
    command?: string;
}

export class ContextGatherer {
    private lastTerminalOutput: string = '';

    constructor() {
        // Listen for terminal output (if available)
        // Note: VS Code doesn't expose terminal output easily
        // This is a placeholder for future implementation
    }

    async gatherContext(): Promise<WorkspaceContext> {
        const config = vscode.workspace.getConfiguration('locoAgent');
        const autoContext = config.get<boolean>('autoContext', true);

        if (!autoContext) {
            return {};
        }

        const context: WorkspaceContext = {};

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
            return absolutePath.replace(workspaceFolder.uri.fsPath + '/', '');
        }
        return absolutePath;
    }
}
