"use strict";
/**
 * Diff Management and Patch Application
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
exports.DiffManager = void 0;
const vscode = __importStar(require("vscode"));
const path = __importStar(require("path"));
const crypto_1 = require("crypto");
const diff_1 = require("diff");
class PatchConflictError extends Error {
    constructor(message) {
        super(message);
        this.name = 'PatchConflictError';
    }
}
class DiffManager {
    constructor(context) {
        this.context = context;
        this.pendingPatches = new Map();
        this.appliedPatches = new Map();
        this.appliedStack = [];
        this.workspaceRoot = null;
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
        this.context.subscriptions.push(this.addDecoration, this.removeDecoration, this.modifyDecoration, this.inlineAddDecoration, vscode.window.onDidChangeActiveTextEditor((editor) => {
            if (editor) {
                this.updateEditorDecorations(editor);
            }
        }), vscode.workspace.onDidChangeTextDocument((event) => {
            const editors = vscode.window.visibleTextEditors.filter((editor) => editor.document.uri.toString() === event.document.uri.toString());
            for (const editor of editors) {
                this.updateEditorDecorations(editor);
            }
        }), vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration('locoAgent.showInlineDiffs')) {
                this.refreshAllDecorations();
            }
        }));
        this.refreshAllDecorations();
    }
    addPatch(patchId, filePath, diff, baseHash) {
        this.pendingPatches.set(patchId, {
            patchId,
            filePath: this.normalizePath(filePath),
            diff,
            baseHash
        });
        this.refreshDecorationsForFile(filePath);
    }
    async acceptPatch(patchId) {
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
        }
        catch (error) {
            if (error instanceof PatchConflictError) {
                vscode.window.showErrorMessage(`Patch conflict: ${error.message}`);
            }
            else {
                vscode.window.showErrorMessage(`Failed to apply patch: ${error}`);
            }
        }
    }
    async rejectPatch(patchId) {
        const patch = this.pendingPatches.get(patchId);
        if (patch) {
            this.pendingPatches.delete(patchId);
            this.refreshDecorationsForFile(patch.filePath);
            vscode.window.showInformationMessage(`Rejected changes to ${patch.filePath}`);
        }
    }
    async viewDiff(patchId) {
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
        const originalUri = vscode.Uri.file(`${workspaceFolder.uri.fsPath}/${patch.filePath}`);
        try {
            const originalContent = await vscode.workspace.fs.readFile(originalUri);
            const proposedContent = this.applyDiffToContent(originalContent.toString(), patch.diff);
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
            await vscode.commands.executeCommand('vscode.diff', originalUri, proposedUri, `${patch.filePath}: Current ↔ Proposed`);
        }
        catch (error) {
            vscode.window.showErrorMessage(`Failed to show diff: ${error}`);
        }
    }
    async undoPatch(patchId) {
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
            vscode.window.showErrorMessage(`Cannot undo ${patch.filePath}: file has changed since apply`);
            return;
        }
        const edit = new vscode.WorkspaceEdit();
        const fullRange = new vscode.Range(new vscode.Position(0, 0), new vscode.Position(currentText.split('\n').length, 0));
        edit.replace(fileUri, fullRange, patch.beforeText);
        const success = await vscode.workspace.applyEdit(edit);
        if (!success) {
            vscode.window.showErrorMessage(`Failed to undo changes for ${patch.filePath}`);
            return;
        }
        this.appliedPatches.delete(targetId);
        vscode.window.showInformationMessage(`Undid changes in ${patch.filePath}`);
    }
    async applyPatch(patch) {
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
        const fullRange = new vscode.Range(new vscode.Position(0, 0), new vscode.Position(currentText.split('\n').length, 0));
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
    applyDiffToContent(content, diff) {
        const patched = (0, diff_1.applyPatch)(content, diff);
        if (patched === false) {
            throw new PatchConflictError('Patch did not apply cleanly');
        }
        return patched;
    }
    normalizePath(filePath) {
        return filePath.replace(/\\/g, '/').replace(/^\.\//, '');
    }
    getFileUri(filePath) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return null;
        }
        return vscode.Uri.file(path.join(workspaceFolder.uri.fsPath, filePath));
    }
    hashContent(content) {
        return (0, crypto_1.createHash)('sha256').update(content, 'utf8').digest('hex');
    }
    getWorkspaceRoot() {
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
    shouldShowInlineDiffs() {
        return vscode.workspace.getConfiguration('locoAgent').get('showInlineDiffs', true);
    }
    refreshDecorationsForFile(filePath) {
        const normalized = this.normalizePath(filePath);
        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot) {
            return;
        }
        const absolutePath = path.join(workspaceRoot, normalized);
        const editors = vscode.window.visibleTextEditors.filter((editor) => editor.document.uri.fsPath === absolutePath);
        for (const editor of editors) {
            this.updateEditorDecorations(editor);
        }
    }
    refreshAllDecorations() {
        for (const editor of vscode.window.visibleTextEditors) {
            this.updateEditorDecorations(editor);
        }
    }
    getPendingPatchesForDocument(document) {
        const workspaceRoot = this.getWorkspaceRoot();
        if (!workspaceRoot) {
            return [];
        }
        const relative = this.normalizePath(path.relative(workspaceRoot, document.uri.fsPath));
        return Array.from(this.pendingPatches.values()).filter((patch) => patch.filePath === relative);
    }
    updateEditorDecorations(editor) {
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
        const combined = {
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
    buildDecorations(document, diff) {
        const parsed = (0, diff_1.parsePatch)(diff);
        const filePatch = parsed[0];
        const hunks = filePatch?.hunks || [];
        const added = [];
        const removed = [];
        const modified = [];
        const inlineAdditions = [];
        for (const hunk of hunks) {
            let oldLine = hunk.oldStart;
            let newLine = hunk.newStart;
            let pendingRemoved = [];
            let pendingAdded = [];
            const flush = (anchorLine) => {
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
                }
                else if (pendingRemoved.length) {
                    for (const removedLine of pendingRemoved) {
                        const range = this.lineRange(document, removedLine - 1);
                        if (range) {
                            removed.push(range);
                        }
                    }
                }
                else if (pendingAdded.length) {
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
                }
                else if (line.startsWith('+')) {
                    pendingAdded.push(line.slice(1));
                    newLine += 1;
                }
                else if (line.startsWith(' ')) {
                    flush(Math.max(oldLine - 1, 0));
                    oldLine += 1;
                    newLine += 1;
                }
            }
            flush(Math.max(oldLine - 1, 0));
        }
        return { added, removed, modified, inlineAdditions };
    }
    lineRange(document, lineIndex) {
        if (lineIndex < 0 || lineIndex >= document.lineCount) {
            return null;
        }
        const line = document.lineAt(lineIndex);
        return new vscode.Range(lineIndex, 0, lineIndex, line.text.length);
    }
    buildInlineAdditionDecoration(document, anchorLine, addedLines) {
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
    buildInlinePreview(lines) {
        if (!lines.length) {
            return '';
        }
        const trimmed = lines.map((line) => line.trim());
        const head = trimmed.slice(0, 2).join(' | ');
        const suffix = trimmed.length > 2 ? ` (+${trimmed.length - 2} more)` : '';
        return `+ ${head}${suffix}`;
    }
}
exports.DiffManager = DiffManager;
//# sourceMappingURL=DiffManager.js.map