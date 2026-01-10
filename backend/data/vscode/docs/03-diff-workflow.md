# Diff Workflow (VS Code)

Proposal
- The agent uses `propose_diff` to create a unified diff.
- The extension shows a diff card with Accept / Reject / View Diff.

Inline UX
- Inline decorations highlight pending changes in the editor.
- Gutter indicators show added, removed, and modified lines.

Conflict detection
- The extension checks the base hash before applying a patch.
- If the file changed, it reports a conflict and refuses to apply.

Undo flow
- Applied patches are tracked in an undo stack.
- Users can undo a patch as long as the file hash matches the post-apply hash.

Best practices for patches
- Keep diffs small and focused.
- Include clear acceptance criteria.
- Avoid bundling unrelated changes.
