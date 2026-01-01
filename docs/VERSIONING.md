# Protocol Versioning & Compatibility

## Versioning Strategy

### Semantic Versioning for Protocol
Protocol versions follow semantic versioning: `MAJOR.MINOR.PATCH`

- **MAJOR**: Breaking changes (incompatible with previous versions)
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

**Current version**: `1.0.0`

### Version Negotiation (Client/Server)

#### Initial Handshake
```typescript
// Client → Server
{
  "type": "client.hello",
  "protocol_version": "1.0.0",
  "client_info": {
    "name": "vscode-extension",
    "version": "0.1.0",
    "capabilities": ["diff_preview", "terminal_exec", "git_integration"]
  }
}

// Server → Client
{
  "type": "server.hello",
  "protocol_version": "1.0.0",
  "supported_versions": ["1.0.0", "0.9.0"],  // backward compat
  "server_info": {
    "version": "0.1.0",
    "model": { ... },
    "capabilities": ["agentic_rag", "ace", "multi_file_edit"]
  }
}
```

#### Version Mismatch Handling

**Case 1: Minor version mismatch (Compatible)**
```
Client: 1.2.0
Server: 1.0.0
Result: Compatible (server ignores unknown fields)
```

**Case 2: Major version mismatch (Incompatible)**
```
Client: 2.0.0
Server: 1.0.0
Result: Incompatible

Server response:
{
  "type": "server.error",
  "error": {
    "code": "VERSION_MISMATCH",
    "message": "Protocol version 2.0.0 not supported. Please upgrade server to 2.x",
    "client_version": "2.0.0",
    "server_version": "1.0.0",
    "upgrade_url": "https://github.com/loco-agent/releases"
  }
}
```

**Case 3: Client too old**
```
Client: 0.5.0
Server: 1.0.0
Result: Warn user to upgrade

Extension shows:
⚠️ Your extension is outdated (0.5.0)
   Server requires 1.x or newer
   [Update Extension]
```

---

## Backward Compatibility Rules

### Adding New Fields (Minor Version Bump)

**Rule**: New optional fields can be added without breaking old clients

```typescript
// Version 1.0.0 message
{
  "type": "patch.proposed",
  "patch_id": "patch_123",
  "file_path": "src/foo.ts",
  "diff": "..."
}

// Version 1.1.0 adds optional field
{
  "type": "patch.proposed",
  "patch_id": "patch_123",
  "file_path": "src/foo.ts",
  "diff": "...",
  "estimated_impact": "low"  // NEW: optional field
}

// Old clients (1.0.0) ignore new field → still works ✓
```

### Changing Field Types (Major Version Bump)

**Rule**: Changing type of existing field is a breaking change

```typescript
// Version 1.0.0
{
  "total_tokens": 1234  // integer
}

// Version 2.0.0 (BREAKING)
{
  "total_tokens": {     // now object
    "prompt": 500,
    "completion": 734
  }
}

// Old clients expect integer → breaks ✗
```

### Removing Fields (Major Version Bump)

**Rule**: Removing fields requires major version bump

```typescript
// Version 1.0.0
{
  "type": "assistant.message",
  "message": "...",
  "confidence": 0.95  // deprecated
}

// Version 1.1.0 (deprecation warning)
{
  "type": "assistant.message",
  "message": "...",
  "confidence": 0.95,  // deprecated, will be removed in 2.0.0
  "_deprecated_fields": ["confidence"]
}

// Version 2.0.0 (BREAKING)
{
  "type": "assistant.message",
  "message": "..."
  // confidence removed
}
```

---

## Migration Paths

### Server-Side Protocol Adapter

```python
class ProtocolAdapter:
    def __init__(self, client_version: str):
        self.client_version = Version(client_version)
    
    def adapt_message(self, message: dict, target_version: str) -> dict:
        """
        Adapt message from server format to client-compatible format
        """
        target = Version(target_version)
        
        # Handle version-specific adaptations
        if target.major == 1 and target.minor == 0:
            # Remove fields not present in 1.0.0
            if "estimated_impact" in message:
                del message["estimated_impact"]
        
        return message
    
    def validate_incoming(self, message: dict) -> bool:
        """
        Validate that incoming message is compatible
        """
        # Check required fields for this version
        required = REQUIRED_FIELDS[self.client_version.major]
        
        for field in required:
            if field not in message:
                raise ValidationError(f"Missing required field: {field}")
        
        return True
```

### Client-Side Version Detection

```typescript
class ServerClient {
  private serverVersion: string;
  private protocolVersion: string;
  
  async connect() {
    // Send hello with client version
    await this.send({
      type: "client.hello",
      protocol_version: CLIENT_PROTOCOL_VERSION
    });
    
    // Receive server hello
    const response = await this.receive();
    this.serverVersion = response.server_info.version;
    this.protocolVersion = response.protocol_version;
    
    // Check compatibility
    if (!this.isCompatible()) {
      throw new VersionMismatchError(
        `Server version ${this.protocolVersion} not compatible with client ${CLIENT_PROTOCOL_VERSION}`
      );
    }
  }
  
  private isCompatible(): boolean {
    const server = semver.parse(this.protocolVersion);
    const client = semver.parse(CLIENT_PROTOCOL_VERSION);
    
    // Same major version required
    return server.major === client.major;
  }
}
```

---

## Feature Flags (Gradual Rollout)

### Capability Negotiation

```typescript
// Client declares capabilities
{
  "type": "client.hello",
  "protocol_version": "1.0.0",
  "capabilities": [
    "diff_preview",
    "terminal_exec",
    "git_integration",
    "multi_file_edit_v2"  // New capability
  ]
}

// Server responds with its capabilities
{
  "type": "server.hello",
  "protocol_version": "1.0.0",
  "capabilities": [
    "agentic_rag",
    "ace",
    "multi_file_edit",
    "streaming_diffs"  // New capability
  ]
}

// Both sides check for capability before using feature
if (serverCapabilities.includes("streaming_diffs")) {
  // Use new streaming diff feature
} else {
  // Fall back to old batch diff approach
}
```

### Feature Gates (Server)

```python
class FeatureGates:
    def __init__(self, client_capabilities: List[str]):
        self.client_capabilities = set(client_capabilities)
    
    def is_enabled(self, feature: str) -> bool:
        # Check if client supports feature
        if feature not in self.client_capabilities:
            return False
        
        # Check if feature is enabled in server config
        return config.features.get(feature, False)
    
    def get_diff_strategy(self) -> str:
        if self.is_enabled("streaming_diffs"):
            return "streaming"
        elif self.is_enabled("multi_file_edit_v2"):
            return "batch_v2"
        else:
            return "batch_v1"

# Usage
gates = FeatureGates(client_capabilities)

if gates.is_enabled("streaming_diffs"):
    async for diff_chunk in generate_diff_streaming():
        await ws.send_json({
            "type": "patch.chunk",
            "data": diff_chunk
        })
else:
    diff = generate_diff_batch()
    await ws.send_json({
        "type": "patch.proposed",
        "diff": diff
    })
```

---

## Deprecation Policy

### Deprecation Timeline

1. **Announcement** (at least 2 minor versions before removal)
   - Document field as deprecated
   - Add warning in server logs
   - Update API docs

2. **Deprecation** (1 major version before removal)
   - Field still present but marked deprecated
   - Return `_deprecated_fields` in responses
   - Extension shows deprecation warnings

3. **Removal** (next major version)
   - Field removed from protocol
   - Major version bump
   - Migration guide published

### Example Deprecation Flow

**v1.0.0** (Current)
```json
{
  "type": "assistant.message",
  "message": "...",
  "confidence": 0.95
}
```

**v1.1.0** (Announce deprecation)
```json
{
  "type": "assistant.message",
  "message": "...",
  "confidence": 0.95,
  "_deprecation_warnings": [
    {
      "field": "confidence",
      "message": "Field 'confidence' is deprecated and will be removed in v2.0.0",
      "alternative": "Use message metadata instead"
    }
  ]
}
```

**v1.5.0** (Final warning)
```json
{
  "type": "assistant.message",
  "message": "...",
  "confidence": 0.95,
  "_deprecation_warnings": [
    {
      "field": "confidence",
      "message": "FINAL WARNING: Field 'confidence' will be removed in v2.0.0 (next major release)",
      "migration_guide": "https://docs.loco-agent.dev/migration/v2"
    }
  ]
}
```

**v2.0.0** (Removed)
```json
{
  "type": "assistant.message",
  "message": "..."
  // confidence field removed
}
```

---

## Testing Strategy for Compatibility

### Version Compatibility Test Matrix

```python
# tests/compatibility/test_version_matrix.py
import pytest

SUPPORTED_VERSIONS = ["0.9.0", "1.0.0", "1.1.0"]

@pytest.mark.parametrize("client_version", SUPPORTED_VERSIONS)
async def test_client_compatibility(client_version):
    """Test that server works with all supported client versions"""
    
    client = TestClient(protocol_version=client_version)
    await client.connect()
    
    # Test basic operations
    response = await client.send_message("Hello")
    assert response.type == "assistant.message"
    
    # Test capabilities
    if Version(client_version) >= Version("1.1.0"):
        assert "estimated_impact" in response
    else:
        assert "estimated_impact" not in response

@pytest.mark.parametrize("server_version", SUPPORTED_VERSIONS)
async def test_server_compatibility(server_version):
    """Test that client works with all supported server versions"""
    
    server = TestServer(version=server_version)
    client = ProductionClient()
    
    await client.connect(server)
    
    # Should work or fail gracefully
    if Version(server_version).major != Version(CLIENT_VERSION).major:
        with pytest.raises(VersionMismatchError):
            await client.send_message("Hello")
    else:
        response = await client.send_message("Hello")
        assert response is not None
```

### Migration Test Suite

```python
# tests/migration/test_v1_to_v2.py
async def test_migrate_v1_session_to_v2():
    """Test migrating session data from v1 to v2"""
    
    # Create v1 session
    v1_session = create_v1_session()
    
    # Migrate to v2
    v2_session = migrate_session(v1_session, target_version="2.0.0")
    
    # Verify migration
    assert v2_session.protocol_version == "2.0.0"
    assert all_required_v2_fields_present(v2_session)
    assert no_deprecated_fields_present(v2_session)

async def test_downgrade_v2_to_v1():
    """Test downgrading session for v1 client compatibility"""
    
    v2_session = create_v2_session()
    
    # Adapt for v1 client
    v1_compatible = adapt_for_client(v2_session, client_version="1.0.0")
    
    # Verify adaptation
    assert no_v2_only_fields_present(v1_compatible)
    assert all_required_v1_fields_present(v1_compatible)
```

---

## Changelog & Release Notes

### Changelog Format

```markdown
# Changelog

## [2.0.0] - 2026-03-15

### Breaking Changes
- **REMOVED**: `confidence` field from `assistant.message` (deprecated since v1.1.0)
- **CHANGED**: `total_tokens` is now an object with `prompt` and `completion` fields
- **REMOVED**: Support for protocol version 0.x

### Migration Guide
- Replace `message.confidence` with `message.metadata.quality_score`
- Update `total_tokens` parsing to handle object structure
- Upgrade clients to 1.x before upgrading server to 2.0

### Added
- New `streaming_diffs` capability for real-time diff preview
- New `estimated_impact` field in patch proposals

### Fixed
- Fixed race condition in context chunking
- Fixed memory leak in embedding cache

## [1.1.0] - 2026-01-15

### Added
- New optional field `estimated_impact` in patch proposals
- New capability `multi_file_edit_v2` with improved conflict handling

### Deprecated
- `confidence` field in `assistant.message` (will be removed in 2.0.0)

### Fixed
- Fixed incorrect token counting for non-ASCII text

## [1.0.0] - 2025-12-30

### Initial Release
- WebSocket-based protocol
- Multi-file diff proposals
- Command execution approvals
- ACE artifact system
```

---

## Version Upgrade Checklist

### For Users (Upgrading Extension)

1. **Check compatibility**:
   - Read release notes
   - Check if server needs upgrade
   - Review breaking changes

2. **Backup**:
   - Export ACE artifacts
   - Save session history if needed

3. **Upgrade**:
   - Install new extension version
   - Restart VS Code
   - Verify connection to server

4. **Test**:
   - Create test session
   - Try basic operations
   - Check for deprecation warnings

### For Developers (Releasing New Version)

1. **Before release**:
   - [ ] Update CHANGELOG.md
   - [ ] Update protocol version in schemas
   - [ ] Run compatibility test suite
   - [ ] Update API documentation
   - [ ] Write migration guide (if breaking changes)

2. **Release**:
   - [ ] Tag release in git
   - [ ] Build and publish extension
   - [ ] Build and publish server
   - [ ] Update documentation site

3. **After release**:
   - [ ] Monitor error reports
   - [ ] Check compatibility issues
   - [ ] Respond to user feedback
   - [ ] Plan deprecations for next version
