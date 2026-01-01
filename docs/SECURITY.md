# Security & Sandboxing

## Threat Model

### Threat Actors

1. **Malicious code in workspace** (High priority)
   - User opens untrusted repo containing malicious files
   - Files contain prompt injection attacks in comments/strings
   - Files contain actual malware that agent might execute

2. **Compromised model** (Medium priority)
   - Local model produces malicious code
   - Model attempts to escape sandbox
   - Model generates code that exfiltrates data

3. **Network attacker** (Medium priority)
   - MitM attack on LAN communication
   - Unauthorized access to agent server
   - Session hijacking

4. **Malicious extension** (Low priority)
   - Other VS Code extensions interfering
   - Extension spoofing/impersonation

### Assets to Protect

- User's filesystem (prevent unauthorized writes/deletes)
- User's credentials and secrets
- User's private code and data
- System resources (prevent DoS)
- Command execution environment

---

## Defense Layers

### Layer 1: Authentication & Authorization

#### Bearer Token Authentication (Baseline)
```python
# Server: Generate secure token on first run
import secrets

def generate_token() -> str:
    return secrets.token_urlsafe(32)  # 256 bits of entropy

# Store in server config
with open("~/.loco-agent/token", "w") as f:
    f.write(generate_token())
    os.chmod("~/.loco-agent/token", 0o600)  # user-only

# Extension: Store in VS Code SecretStorage
await context.secrets.store("locoAgent.token", token);
```

#### TLS/HTTPS (LAN deployment)
**Problem**: Self-signed certs cause browser warnings, poor UX

**Solution**: Generate certs with proper SAN, import to system trust store

```bash
# Generate self-signed cert with mkcert (auto-trusted)
mkcert -install  # Install root CA
mkcert localhost 192.168.1.100 desktop.local

# Server: Use generated cert
uvicorn app.main:app \
  --ssl-keyfile=localhost+2-key.pem \
  --ssl-certfile=localhost+2.pem \
  --host 0.0.0.0 \
  --port 3199
```

**Alternative**: Device pairing with TOTP

```python
# Server: Generate pairing code
import pyotp

def generate_pairing_code() -> str:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    return totp.now()  # 6-digit code, valid for 30s

# Extension: User enters code
pairing_code = await vscode.window.showInputBox({
    prompt: "Enter pairing code from server"
});

# Server: Verify and issue token
if totp.verify(pairing_code):
    token = generate_token()
    return {"token": token}
```

#### API Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/v1/sessions/{session_id}/message")
@limiter.limit("100/minute")  # Per IP
async def send_message(session_id: str, request: Request):
    # ...
```

---

### Layer 2: Workspace Trust & Policies

#### VS Code Workspace Trust Integration
```typescript
// Extension: Check workspace trust before connecting
const trustState = vscode.workspace.isTrusted;

if (!trustState) {
  vscode.window.showWarningMessage(
    "Workspace is not trusted. LoCo Agent requires a trusted workspace.",
    "Trust Workspace"
  ).then(selection => {
    if (selection === "Trust Workspace") {
      vscode.commands.executeCommand("workbench.action.manageTrust");
    }
  });
  return;
}
```

#### Policy Enforcement (Server-Side)

**Default Policy** (restrictive):
```json
{
  "allowed_read_globs": ["**/*"],
  "allowed_write_globs": [
    "src/**/*",
    "tests/**/*",
    "docs/**/*"
  ],
  "blocked_globs": [
    ".git/**",
    "node_modules/**",
    ".env",
    "*.key",
    "*.pem",
    "id_rsa*"
  ],
  "command_approval": "prompt",
  "allowed_commands": [
    "npm test",
    "npm run build",
    "npm run lint",
    "pytest",
    "cargo test",
    "go test"
  ],
  "blocked_commands": [
    "rm -rf",
    "sudo",
    "curl",
    "wget",
    "ssh",
    "scp",
    "git push"
  ],
  "network_enabled": false,
  "auto_approve_simple_changes": false,
  "auto_approve_tests": false
}
```

**Policy Validation** (before every tool call):
```python
class PolicyEnforcer:
    def can_read_file(self, workspace_id: str, file_path: str) -> bool:
        policy = get_policy(workspace_id)
        
        # Check blocked globs first
        if self._matches_any_glob(file_path, policy.blocked_globs):
            return False
        
        # Check allowed globs
        return self._matches_any_glob(file_path, policy.allowed_read_globs)
    
    def can_write_file(self, workspace_id: str, file_path: str) -> bool:
        policy = get_policy(workspace_id)
        
        if self._matches_any_glob(file_path, policy.blocked_globs):
            return False
        
        return self._matches_any_glob(file_path, policy.allowed_write_globs)
    
    def can_execute_command(self, workspace_id: str, command: str) -> tuple[bool, str]:
        policy = get_policy(workspace_id)
        
        # Check blocked commands (substring match)
        for blocked in policy.blocked_commands:
            if blocked in command:
                return False, f"Command contains blocked pattern: {blocked}"
        
        # If allowlist is empty, require approval
        if not policy.allowed_commands:
            return False, "No commands are pre-approved"
        
        # Check allowlist (exact match or prefix match)
        for allowed in policy.allowed_commands:
            if command == allowed or command.startswith(allowed + " "):
                return True, "Allowed by policy"
        
        return False, "Command not in allowlist"

# Use in every tool
@tool("write_file")
async def write_file(workspace_id: str, file_path: str, content: str):
    if not enforcer.can_write_file(workspace_id, file_path):
        raise PolicyViolation(f"Cannot write to {file_path}")
    
    # Log to audit trail
    log_tool_event(workspace_id, "write_file", {"path": file_path})
    
    # Perform write
    ...
```

---

### Layer 3: Prompt Injection Defense

#### Input Sanitization
```python
def sanitize_file_content(content: str, file_path: str) -> str:
    """
    Prevent prompt injection from malicious file contents
    """
    # Detect and neutralize prompt injection patterns
    dangerous_patterns = [
        r"(?i)ignore previous instructions",
        r"(?i)disregard all previous",
        r"(?i)system:\s*you are now",
        r"(?i)<\|endoftext\|>",
        r"(?i)<\|im_start\|>",
        # Add model-specific tokens
    ]
    
    for pattern in dangerous_patterns:
        if re.search(pattern, content):
            logger.warning(f"Potential prompt injection in {file_path}")
            # Option 1: Strip dangerous patterns
            content = re.sub(pattern, "[REDACTED]", content)
            # Option 2: Refuse to include file
            # return f"[File {file_path} contains suspicious content]"
    
    return content
```

#### Context Sandboxing
```python
def build_context_pack(workspace_id: str, user_message: str, context: dict):
    """
    Wrap untrusted content in clear delimiters
    """
    return {
        "system": SYSTEM_PROMPT,  # Trusted
        "user_message": user_message,  # Semi-trusted (from user)
        "file_contents": [
            {
                "path": file.path,
                "content": f"<file_content>\n{sanitize(file.content)}\n</file_content>",
                "source": "workspace"  # Mark as untrusted
            }
            for file in context.files
        ],
        "diagnostics": context.diagnostics,  # Trusted (from VS Code)
        "terminal_output": f"<terminal>\n{context.terminal}\n</terminal>",  # Semi-trusted
    }
```

#### Output Validation
```python
def validate_proposed_patch(patch: str, file_path: str) -> bool:
    """
    Validate that proposed patch doesn't contain suspicious patterns
    """
    # Check for attempts to modify .env, secrets, etc.
    if file_path in [".env", ".env.local", "id_rsa", "secrets.yaml"]:
        logger.error(f"Attempted to modify sensitive file: {file_path}")
        return False
    
    # Check diff for suspicious additions
    dangerous_additions = [
        r"eval\(",
        r"exec\(",
        r"__import__\(",
        r"os\.system\(",
        r"subprocess\.call\(",
        r"curl\s+http",
        r"wget\s+http",
    ]
    
    for pattern in dangerous_additions:
        if re.search(pattern, patch):
            logger.warning(f"Suspicious code in patch: {pattern}")
            return False
    
    return True
```

---

### Layer 4: Command Execution Sandbox

#### Local Terminal (Default, User-Visible)
```typescript
// Extension: Run in VS Code terminal (user sees it)
async function executeCommand(command: string): Promise<CommandResult> {
  // Create or reuse terminal
  const terminal = vscode.window.terminals.find(t => t.name === "LoCo Agent")
    || vscode.window.createTerminal("LoCo Agent");
  
  terminal.show();
  
  // Execute command
  terminal.sendText(command);
  
  // Capture output (requires terminal output API)
  // Note: This is a limitation - VS Code doesn't expose terminal output easily
  // Workaround: Use child_process in extension host
  
  return new Promise((resolve) => {
    const child = exec(command, {
      cwd: vscode.workspace.workspaceFolders[0].uri.fsPath,
      timeout: 60000,  // 60s max
      maxBuffer: 10 * 1024 * 1024  // 10MB max output
    });
    
    let stdout = "";
    let stderr = "";
    
    child.stdout.on('data', (data) => stdout += data);
    child.stderr.on('data', (data) => stderr += data);
    
    child.on('close', (code) => {
      resolve({ exit_code: code, stdout, stderr });
    });
  });
}
```

#### Server-Side Runner (Optional, Sandboxed)
```python
import subprocess
import shlex

async def run_command_sandboxed(
    command: str,
    workspace_path: str,
    timeout: int = 60
) -> CommandResult:
    """
    Run command in sandboxed environment
    """
    # Parse command safely
    args = shlex.split(command)
    
    # Whitelist-based validation
    if args[0] not in ALLOWED_EXECUTABLES:
        raise PolicyViolation(f"Executable not allowed: {args[0]}")
    
    # Run in subprocess with limits
    try:
        result = subprocess.run(
            args,
            cwd=workspace_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            # Security: Drop privileges, no shell
            shell=False,
            check=False
        )
        
        return CommandResult(
            exit_code=result.returncode,
            stdout=result.stdout[:100_000],  # Truncate
            stderr=result.stderr[:100_000]
        )
    
    except subprocess.TimeoutExpired:
        raise CommandTimeout(f"Command exceeded {timeout}s")
```

**Future**: Container-based sandbox (Docker/Podman)
```python
# Run in container (isolated filesystem, network, resources)
docker_client.containers.run(
    image="loco-agent-sandbox:latest",
    command=command,
    volumes={workspace_path: {"bind": "/workspace", "mode": "rw"}},
    working_dir="/workspace",
    network_mode="none",  # No network access
    mem_limit="512m",
    cpu_quota=50000,  # 50% of one core
    remove=True,
    timeout=60
)
```

---

### Layer 5: Audit Logging (Detection & Response)

#### Comprehensive Logging
```python
import structlog

audit_logger = structlog.get_logger("audit")

class AuditLogger:
    def log_tool_call(self, workspace_id: str, tool_name: str, args: dict, result: dict):
        audit_logger.info(
            "tool_executed",
            workspace_id=workspace_id,
            tool_name=tool_name,
            args=args,
            result=result,
            timestamp=datetime.utcnow().isoformat()
        )
        
        # Also store in SQLite for long-term audit
        db.execute(
            "INSERT INTO tool_events (workspace_id, tool_name, args_json, result_json) VALUES (?, ?, ?, ?)",
            workspace_id, tool_name, json.dumps(args), json.dumps(result)
        )
    
    def log_policy_violation(self, workspace_id: str, violation: str, details: dict):
        audit_logger.warning(
            "policy_violation",
            workspace_id=workspace_id,
            violation=violation,
            details=details
        )
        
        # Alert user in extension
        notify_user(f"Policy violation: {violation}")
```

#### Audit Log Viewer (Extension)
```typescript
// Command: View audit logs
vscode.commands.registerCommand("locoAgent.viewAuditLogs", async () => {
  const logs = await serverClient.getAuditLogs({
    workspace_id: currentWorkspace.id,
    limit: 100
  });
  
  const panel = vscode.window.createWebviewPanel(
    "auditLogs",
    "Audit Logs",
    vscode.ViewColumn.One,
    {}
  );
  
  panel.webview.html = renderAuditLogs(logs);
});
```

---

## Security Checklist (Pre-Deployment)

### Server
- [ ] HTTPS enabled with valid certificate
- [ ] Bearer token authentication implemented
- [ ] Token stored securely (chmod 600)
- [ ] Rate limiting configured
- [ ] Policy enforcement on all file/command operations
- [ ] Audit logging enabled
- [ ] Input sanitization for file contents
- [ ] Output validation for patches
- [ ] Command execution timeouts
- [ ] Resource limits (memory, CPU)

### Extension
- [ ] Token stored in SecretStorage (not settings.json)
- [ ] Workspace trust checked before connection
- [ ] Patches applied via WorkspaceEdit (not fs.writeFile)
- [ ] User approval required for destructive operations
- [ ] Undo stack implemented
- [ ] Audit log viewer available
- [ ] Clear error messages for policy violations
- [ ] No sensitive data in logs

### Deployment
- [ ] Firewall configured (allow only LAN)
- [ ] Server runs as non-root user
- [ ] Workspace directories have proper permissions
- [ ] Secrets excluded from indexing
- [ ] Regular security updates planned

---

## Security Best Practices (User Education)

### Documentation for Users
1. **Only open trusted workspaces** - Don't use LoCo Agent on untrusted repos
2. **Review all patches before accepting** - Especially for files you didn't ask to modify
3. **Use restrictive policies** - Start with defaults, relax as needed
4. **Monitor audit logs** - Periodically review what agent has done
5. **Limit command allowlist** - Only allow commands you understand
6. **Disable network if not needed** - Most coding tasks don't need network
7. **Update regularly** - Apply security patches promptly

### Red Flags (Warn Users)
- Agent proposes changes to .env, secrets, or credential files
- Agent suggests running commands with `sudo`, `curl`, `wget`
- Agent proposes excessive file deletions
- Agent modifies files outside src/tests directories unexpectedly
- Agent proposes adding `eval()`, `exec()`, or similar dynamic code execution

---

## Incident Response Plan

### If Malicious Activity Detected

1. **Immediate**:
   - Kill server process
   - Disconnect extension
   - Review audit logs

2. **Investigation**:
   - Identify what files were modified
   - Check command execution history
   - Review patches that were applied

3. **Remediation**:
   - Restore files from git (if in version control)
   - Or restore from undo stack
   - Or restore from backup

4. **Prevention**:
   - Tighten policies
   - Update blocklists
   - Report incident (if bug in product)

### Security Contact
- Report security issues: security@loco-agent.local
- PGP key: [placeholder]
- Response time: 48 hours

---

## Future Security Enhancements

1. **mTLS** (mutual TLS) for device authentication
2. **HSM/TPM** integration for credential storage
3. **Code signing** for patches (verify agent signatures)
4. **Anomaly detection** (detect unusual behavior patterns)
5. **RBAC** (role-based access control for multi-user setups)
6. **Encrypted storage** for audit logs and ACE artifacts
7. **SIEM integration** (send logs to external security tools)
8. **Penetration testing** (hire security firm to audit)
