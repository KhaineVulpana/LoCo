# VS Code Extension Settings

Connection
- locoAgent.serverUrl: server endpoint (default http://localhost:3199).
- locoAgent.authEnabled: enable bearer token.

Context
- locoAgent.autoContext: gather context automatically.
- locoAgent.includeWorkspaceRag: include indexed workspace results.

Indexing
- locoAgent.autoIndexWorkspace: index on connect.
- locoAgent.autoWatchWorkspace: watch files after indexing.
- locoAgent.usePollingWatcher: polling instead of filesystem events.

Model
- locoAgent.modelProvider: ollama | vllm | llamacpp.
- locoAgent.modelName: model identifier.

Diff behavior
- locoAgent.autoApproveSimple: auto-approve small diffs.
- locoAgent.showInlineDiffs: inline and gutter decorations.

Policy overrides (syncs to server policy)
- locoAgent.policy.commandApproval: always | never | prompt.
- locoAgent.policy.allowedCommands: allow list.
- locoAgent.policy.blockedCommands: deny list.
- locoAgent.policy.allowedReadGlobs: read access rules.
- locoAgent.policy.allowedWriteGlobs: write access rules.
- locoAgent.policy.blockedGlobs: blocked paths.
- locoAgent.policy.networkEnabled: allow network commands.
- locoAgent.policy.autoApproveSimpleChanges: auto-approve simple changes.
- locoAgent.policy.autoApproveTests: auto-approve test commands.
