# Tools and Approvals

Core tools (server-side)
- read_file, write_file, list_files
- run_command, run_tests
- apply_patch, propose_diff, propose_patch
- report_plan

Approval policy
- The server consults workspace policy for each tool call.
- Commands are gated by allow/deny lists and `command_approval`.
- Network commands can be blocked via policy (`network_enabled`).

Approval flow
1) Server emits tool.request_approval or command.request_approval.
2) Extension shows a modal prompt.
3) User approves or rejects.
4) Server proceeds or cancels.

Auto-approve knobs
- auto_approve_tests: allow running test commands without prompting.
- auto_approve_simple_changes: allow trivial diffs when policy allows.
- auto_approve_tools: allow specific tools without prompting.
