/**
 * Diff Management and Patch Application
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { createHash } from 'crypto';
import { applyPatch, parsePatch, ParsedDiff } from 'diff';

interface PatchInfo {
    patchId: string;
    filePath: string;
    diff: string;
    baseHash: string;
}

interface AppliedPatchInfo {
    patchId: string;
    filePath: string;
    beforeText: string;
    afterText: string;
    beforeHash: string;
    afterHash: string;
    appliedAt: string;
}

interface DiffDecorations {
    added: vscode.DecorationOptions[];
    removed: vscode.Range[];
    modified: vscode.Range[];
    inlineAdditions: vscode.DecorationOptions[];
}

class PatchConflictError extends Error {
    constructor(message: string) {
        super(message);
        this.name = 'PatchConflictError';
    }
}

export class DiffManager {
    private pendingPatches: Map<string, PatchInfo> = new Map();
    private appliedPatches: Map<string, AppliedPatchInfo> = new Map();
    private appliedStack: string[] = [];
    private addDecoration: vscode.TextEditorDecorationType;
    private removeDecoration: vscode.TextEditorDecorationType;
    private modifyDecoration: vscode.TextEditorDecorationType;
    private inlineAddDecoration: vscode.TextEditorDecorationType;
    private workspaceRoot: string | null = null;

    constructor(private context: vscode.ExtensionContext) {
        const addIcon = vscode.Uri.joinPath(this.context.extensionUri, 'media', 'diff-added.svg');
        const removeIcon = vscode.Uri.joinPath(this.context.extensionUri, 'media', 'diff-removed.svg');
        const modifyIcon = vscode.Uri.joinPath(this.context.extensionUri, 'media', 'diff-modified.svg');

        this.addDecoration = vscode.window.createTextEditorDecorationType({
            isWholeLine: true,
            gutterIconPath: addIcon,
            gutterIconSize: 'contain',
            backgroundColor: new vscode.ThemeColor('diffEditor.insertedLineBackground'),
            overviewRulerColor: new vscode.ThemeColor('diffEditor.insertedLineBackground'),
            overviewRulerLane: vscode.OverviewRulerLane.Left
        });

        this.removeDecoration = vscode.window.createTextEditorDecorationType({
            isWholeLine: true,
            gutterIconPath: removeIcon,
            gutterIconSize: 'contain',
            backgroundColor: new vscode.ThemeColor('diffEditor.removedLineBackground'),
            overviewRulerColor: new vscode.ThemeColor('diffEditor.removedLineBackground'),
            overviewRulerLane: vscode.OverviewRulerLane.Left
        });

        this.modifyDecoration = vscode.window.createTextEditorDecorationType({
            isWholeLine: true,
            gutterIconPath: modifyIcon,
            gutterIconSize: 'contain',
            backgroundColor: new vscode.ThemeColor('diffEditor.modifiedLineBackground'),
            overviewRulerColor: new vscode.ThemeColor('diffEditor.modifiedLineBackground'),
            overviewRulerLane: vscode.OverviewRulerLane.Left
        });

        this.inlineAddDecoration = vscode.window.createTextEditorDecorationType({});

        this.context.subscriptions.push(
            this.addDecoration,
            this.removeDecoration,
            this.modifyDecoration,
            this.inlineAddDecoration,
            vscode.window.onDidChangeActiveTextEditor((editor) => {
                if (editor) {
                    this.updateEditorDecorations(editor);
                }
            }),
            vscode.workspace.onDidChangeTextDocument((event) => {
                const editors = vscode.window.visibleTextEditors.filter(
                    (editor) => editor.document.uri.toString() === event.document.uri.toString()
                );
                for (const editor of editors) {
                    this.updateEditorDecorations(editor);
                }
            }),
            vscode.workspace.onDidChangeConfiguration((event) => {
                if (event.affectsConfiguration('locoAgent.showInlineDiffs')) {
                    this.refreshAllDecorations();
                }
            })
        );

        this.refreshAllDecorations();
    }

    addPatch(patchId: string, filePath: string, diff: string, baseHash: string): void {
        this.pendingPatches.set(patchId, {
            patchId,
            filePath: this.normalizePath(filePath),
            diff,
            baseHash
        });
        this.refreshDecorationsForFile(filePath);
    }

    async acceptPatch(patchId: string): Promise<void> {
        const patch = this.pendingPatches.get(patchId);
        if (!patch) {
            vscode.window.showErrorMessage(`Patch ${patchId} not found`);
            return;
        }

        try {
            await this.applyPatch(patch);
            this.pendingPatches.delete(patchId);
            this.refreshDecorationsForFile(patch.filePath);
            vscode.window.showInformationMessage(`Applied changes to ${patch.filePath}`);
        } catch (error: any) {
            if (error instanceof PatchConflictError) {
                vscode.window.showErrorMessage(`Patch conflict: ${error.message}`);
            } else {
                vscode.window.showErrorMessage(`Failed to apply patch: ${error}`);
            }
        }
    }

    async rejectPatch(patchId: string): Promise<void> {
        const patch = this.pendingPatches.get(patchId);
        if (patch) {
            this.pendingPatches.delete(patchId);
            this.refreshDecorationsForFile(patch.filePath);
            vscode.window.showInformationMessage(`Rejected changes to ${patch.filePath}`);
        }
    }

    async viewDiff(patchId: string): Promise<void> {
        const patch = this.pendingPatches.get(patchId);
        if (!patch) {
            vscode.window.showErrorMessage(`Patch ${patchId} not found`);
            return;
        }

        // Create temporary file with proposed changes
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return;
        }

        const originalUri = vscode.Uri.file(
            `${workspaceFolder.uri.fsPath}/${patch.filePath}`
        );

        try {
            const originalContent = await vscode.workspace.fs.readFile(originalUri);
            const proposedContent = this.applyDiffToContent(
                originalContent.toString(),
                patch.diff
            );

            // Create temporary URI for proposed content
            const proposedUri = originalUri.with({
                scheme: 'untitled',
                path: originalUri.path + '.proposed'
            });

            const proposedDoc = await vscode.workspace.openTextDocument(proposedUri);
            const edit = new vscode.WorkspaceEdit();
            edit.insert(proposedUri, new vscode.Position(0, 0), proposedContent);
            await vscode.workspace.applyEdit(edit);

            // Show diff
            await vscode.commands.executeCommand(
                'vscode.diff',
                originalUri,
                proposedUri,
                `${patch.filePath}: Current ↔ Proposed`
            );
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to show diff: ${error}`);
        }
    }

    async undoPatch(patchId?: string): Promise<void> {
        const targetId = patchId || this.appliedStack.pop();
        if (!targetId) {
            vscode.window.showInformationMessage('No applied patches to undo');
            return;
        }

        const patch = this.appliedPatches.get(targetId);
        if (!patch) {
            vscode.window.showErrorMessage(`Patch ${targetId} not found in undo stack`);
            return;
        }

        const fileUri = this.getFileUri(patch.filePath);
        if (!fileUri) {
            vscode.window.showErrorMessage('No workspace folder');
            return;
        }

        const currentContent = await vscode.workspace.fs.readFile(fileUri);
        const currentText = currentContent.toString();
        const currentHash = this.hashContent(currentText);
        if (currentHash !== patch.afterHash) {
            vscode.window.showErrorMessage(
                `Cannot undo ${patch.filePath}: file has changed since apply`
            );
            return;
        }

        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(
            new vscode.Position(0, 0),
            new vscode.Position(currentText.split('\n').length, 0)
        );
        edit.replace(fileUri, fullRange, patch.beforeText);

        const success = await vscode.workspace.applyEdit(edit);
        if (!success) {
            vscode.window.showErrorMessage(`Failed to undo changes for ${patch.filePath}`);
            return;
        }

        this.appliedPatches.delete(targetId);
        vscode.window.showInformationMessage(`Undid changes in ${patch.filePath}`);
    }

    private async applyPatch(patch: PatchInfo): Promise<void> {
        const fileUri = this.getFileUri(patch.filePath);
        if (!fileUri) {
            throw new Error('No workspace folder');
        }

        // Read current content
        const currentContent = await vscode.workspace.fs.readFile(fileUri);
        const currentText = currentContent.toString();
        const currentHash = this.hashContent(currentText);

        if (patch.baseHash && patch.baseHash !== currentHash) {
            throw new PatchConflictError('File has changed since patch was generated');
        }

        // Apply diff
        const newText = this.applyDiffToContent(currentText, patch.diff);
        const newHash = this.hashContent(newText);

        // Create workspace edit
        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(
            new vscode.Position(0, 0),
            new vscode.Position(currentText.split('\n').length, 0)
        );

        edit.replace(fileUri, fullRange, newText);

        // Apply edit
        const success = await vscode.workspace.applyEdit(edit);

        if (!success) {
            throw new Error('Failed to apply edit');
        }

        this.appliedPatches.set(patch.patchId, {
            patchId: patch.patchId,
            filePath: patch.filePath,
            beforeText: currentText,
            afterText: newText,
            beforeHash: currentHash,
            afterHash: newHash,
            appliedAt: new Date().toISOString()
        });
        this.appliedStack.push(patch.patchId);
    }

    private applyDiffToContent(content: string, diff: string): string {
        const patched = applyPatch(content, diff);
        if (patched === false) {
            throw new PatchConflictError('Patch did not apply cleanly');
        }
        return patched;
    }

    private normalizePath(filePath: string): string {
        return filePath.replace(/\\/g, '/').replace(/^\.\//, '');
    }

    private getFileUri(filePath: string): vscode.Uri | null {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return null;
        }
        return vscode.Uri.file(path.join(workspaceFolder.uri.fsPath, filePath));
    }

    private hashContent(content: string): string {
        return createHash('sha256').update(content, 'utf8').digest('hex');
    }

    private getWorkspaceRoot(): string | null {
        if (this.workspaceRoot) {
            return this.workspaceRoot;
        }
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return null;
        }
        this.workspaceRoot = workspaceFolder.uri.fsPath;
        return this.workspaceRoot;
    }

    private shouldShowInlineDiffs(): boolean {
        return vscode.workspace.getConfiguration('locoAgent').get<boolean>('showInlineDiffs', true);
    }

    private refreshDecorationsForFile(filePath: string): void {
        const normalized = this.normalizePath(filePath);
        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot) {
            return;
        }

        const absolutePath = path.join(workspaceRoot, normalized);
        const editors = vscode.window.visibleTextEditors.filter(
            (editor) => editor.document.uri.fsPath === absolutePath
        );

        for (const editor of editors) {
            this.updateEditorDecorations(editor);
        }
    }

    private refreshAllDecorations(): void {
        for (const editor of vscode.window.visibleTextEditors) {
            this.updateEditorDecorations(editor);
        }
    }

    private getPendingPatchesForDocument(document: vscode.TextDocument): PatchInfo[] {
        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot) {
            return [];
        }
        const relative = this.normalizePath(path.relative(workspaceRoot, document.uri.fsPath));
        return Array.from(this.pendingPatches.values()).filter((patch) => patch.filePath === relative);
    }

    private updateEditorDecorations(editor: vscode.TextEditor): void {
        if (!this.shouldShowInlineDiffs()) {
            editor.setDecorations(this.addDecoration, []);
            editor.setDecorations(this.removeDecoration, []);
            editor.setDecorations(this.modifyDecoration, []);
            editor.setDecorations(this.inlineAddDecoration, []);
            return;
        }

        const patches = this.getPendingPatchesForDocument(editor.document);
        if (!patches.length) {
            editor.setDecorations(this.addDecoration, []);
            editor.setDecorations(this.removeDecoration, []);
            editor.setDecorations(this.modifyDecoration, []);
            editor.setDecorations(this.inlineAddDecoration, []);
            return;
        }

        const combined: DiffDecorations = {
            added: [],
            removed: [],
            modified: [],
            inlineAdditions: []
        };

        for (const patch of patches) {
            const next = this.buildDecorations(editor.document, patch.diff);
            combined.added.push(...next.added);
            combined.removed.push(...next.removed);
            combined.modified.push(...next.modified);
            combined.inlineAdditions.push(...next.inlineAdditions);
        }

        editor.setDecorations(this.addDecoration, combined.added);
        editor.setDecorations(this.removeDecoration, combined.removed);
        editor.setDecorations(this.modifyDecoration, combined.modified);
        editor.setDecorations(this.inlineAddDecoration, combined.inlineAdditions);
    }

    private buildDecorations(document: vscode.TextDocument, diff: string): DiffDecorations {
        const parsed = parsePatch(diff);
        const filePatch: ParsedDiff | undefined = parsed[0];
        const hunks = filePatch?.hunks || [];
        const added: vscode.DecorationOptions[] = [];
        const removed: vscode.Range[] = [];
        const modified: vscode.Range[] = [];
        const inlineAdditions: vscode.DecorationOptions[] = [];

        for (const hunk of hunks) {
            let oldLine = hunk.oldStart;
            let newLine = hunk.newStart;
            let pendingRemoved: number[] = [];
            let pendingAdded: string[] = [];

            const flush = (anchorLine: number) => {
                if (!pendingRemoved.length && !pendingAdded.length) {
                    return;
                }

                if (pendingRemoved.length && pendingAdded.length) {
                    for (const removedLine of pendingRemoved) {
                        const range = this.lineRange(document, removedLine - 1);
                        if (range) {
                            modified.push(range);
                        }
                    }
                    const inline = this.buildInlineAdditionDecoration(document, anchorLine, pendingAdded);
                    if (inline) {
                        inlineAdditions.push(inline);
                    }
                } else if (pendingRemoved.length) {
                    for (const removedLine of pendingRemoved) {
                        const range = this.lineRange(document, removedLine - 1);
                        if (range) {
                            removed.push(range);
                        }
                    }
                } else if (pendingAdded.length) {
                    const inline = this.buildInlineAdditionDecoration(document, anchorLine, pendingAdded);
                    if (inline) {
                        inlineAdditions.push(inline);
                        const anchorRange = this.lineRange(document, anchorLine);
                        if (anchorRange) {
                            added.push({ range: anchorRange });
                        }
                    }
                }

                pendingRemoved = [];
                pendingAdded = [];
            };

            for (const line of hunk.lines) {
                if (line.startsWith('-')) {
                    pendingRemoved.push(oldLine);
                    oldLine += 1;
                } else if (line.startsWith('+')) {
                    pendingAdded.push(line.slice(1));
                    newLine += 1;
                } else if (line.startsWith(' ')) {
                    flush(Math.max(oldLine - 1, 0));
                    oldLine += 1;
                    newLine += 1;
                }
            }

            flush(Math.max(oldLine - 1, 0));
        }

        return { added, removed, modified, inlineAdditions };
    }

    private lineRange(document: vscode.TextDocument, lineIndex: number): vscode.Range | null {
        if (lineIndex < 0 || lineIndex >= document.lineCount) {
            return null;
        }
        const line = document.lineAt(lineIndex);
        return new vscode.Range(lineIndex, 0, lineIndex, line.text.length);
    }

    private buildInlineAdditionDecoration(
        document: vscode.TextDocument,
        anchorLine: number,
        addedLines: string[]
    ): vscode.DecorationOptions | null {
        const safeLine = Math.min(Math.max(anchorLine, 0), Math.max(document.lineCount - 1, 0));
        const range = this.lineRange(document, safeLine);
        if (!range) {
            return null;
        }

        const preview = this.buildInlinePreview(addedLines);
        return {
            range,
            renderOptions: {
                after: {
                    contentText: preview,
                    color: new vscode.ThemeColor('gitDecoration.addedResourceForeground'),
                    margin: '0 0 0 1rem',
                    fontStyle: 'italic'
                }
            }
        };
    }

    private buildInlinePreview(lines: string[]): string {
        if (!lines.length) {
            return '';
        }
        const trimmed = lines.map((line) => line.trim());
        const head = trimmed.slice(0, 2).join(' | ');
        const suffix = trimmed.length > 2 ? ` (+${trimmed.length - 2} more)` : '';
        return `+ ${head}${suffix}`;
    }
}
