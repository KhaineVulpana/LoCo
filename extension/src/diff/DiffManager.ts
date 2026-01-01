/**
 * Diff Management and Patch Application
 */

import * as vscode from 'vscode';

interface PatchInfo {
    patchId: string;
    filePath: string;
    diff: string;
    baseHash: string;
}

export class DiffManager {
    private pendingPatches: Map<string, PatchInfo> = new Map();

    constructor(private context: vscode.ExtensionContext) {}

    addPatch(patchId: string, filePath: string, diff: string, baseHash: string): void {
        this.pendingPatches.set(patchId, {
            patchId,
            filePath,
            diff,
            baseHash
        });
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
            vscode.window.showInformationMessage(`Applied changes to ${patch.filePath}`);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to apply patch: ${error}`);
        }
    }

    async rejectPatch(patchId: string): Promise<void> {
        const patch = this.pendingPatches.get(patchId);
        if (patch) {
            this.pendingPatches.delete(patchId);
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

    private async applyPatch(patch: PatchInfo): Promise<void> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            throw new Error('No workspace folder');
        }

        const fileUri = vscode.Uri.file(
            `${workspaceFolder.uri.fsPath}/${patch.filePath}`
        );

        // Read current content
        const currentContent = await vscode.workspace.fs.readFile(fileUri);
        const currentText = currentContent.toString();

        // Apply diff
        const newText = this.applyDiffToContent(currentText, patch.diff);

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
    }

    private applyDiffToContent(content: string, diff: string): string {
        // Simplified diff application
        // In production, use a proper diff library like diff-match-patch

        // For now, just extract the new content from the diff
        // This is a placeholder implementation
        const lines = diff.split('\n');
        const newLines: string[] = [];

        for (const line of lines) {
            if (line.startsWith('+') && !line.startsWith('+++')) {
                newLines.push(line.substring(1));
            } else if (!line.startsWith('-') && !line.startsWith('@@') && !line.startsWith('---')) {
                newLines.push(line);
            }
        }

        return newLines.join('\n');
    }
}
