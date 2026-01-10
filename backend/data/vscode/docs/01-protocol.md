# Protocol Quick Guide (VS Code)

Important message types
- client.hello: client capability handshake.
- client.user_message: user prompt + context payload.
- assistant.thinking: streaming phase hints.
- assistant.message_delta: incremental tokens.
- assistant.message_final: final response message.
- agent.plan: optional plan steps with rationale.
- patch.proposed: unified diff proposal with metadata.
- tool.request_approval: approval gate for risky tool usage.
- command.request_approval: approval gate for command execution.
- client.approval_response: user decision on approvals.
- client.patch_apply_result: report patch application outcome.
- client.command_result: return stdout/stderr for executed commands.
- server.error: structured error with code + details.

Patch proposal expectations
- diff: unified diff (git style, UTF-8).
- file_path: path relative to workspace root.
- rationale: short explanation.
- acceptance_criteria: list of expected outcomes.
- hunks: line ranges for UI preview.

Approval flow
1) Server emits tool or command approval request.
2) Extension prompts user and replies with approval or reject.
3) Server proceeds or aborts the tool call.

Error handling
- server.error is non-fatal when possible; client should surface it and allow retry.
- patch_apply_result should include a conflict type if the diff failed to apply.
