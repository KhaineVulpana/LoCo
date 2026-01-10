# Security Notes (VS Code)

Workspace trust
- The extension requires a trusted workspace before connecting.

Tokens
- Bearer tokens are optional and stored in VS Code SecretStorage.
- Disable auth with the server flag when running locally.

Policies
- Policies enforce read/write access and command safety.
- Blocked globs should include .git and node_modules by default.
- Blocked commands should include destructive or network operations.

Approvals
- Commands and write operations request approval based on policy.
- Denied tools return a policy violation message to the agent.
