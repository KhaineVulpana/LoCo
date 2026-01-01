# Error Handling and Resilience

## Critical Failure Modes and Mitigation

### 1. Indexing Failures

#### Tree-sitter Parse Failures
**Scenario**: File has syntax errors or unsupported language constructs

**Mitigation**:
1. Catch parse exceptions, log with file path
2. Fall back to heuristic chunking (sliding window)
3. Mark file as "partially indexed" in SQLite
4. Retry parse after file is modified (might be fixed)
5. Continue indexing other files (don't fail entire job)

**Degraded Mode**:
- File still searchable via text search (ripgrep)
- File still has vector embeddings (from text chunks)
- Symbol extraction skipped (mark as unavailable)

```python
try:
    tree = parser.parse(source_code)
    chunks = ast_chunk(tree)
except ParseError as e:
    logger.warning(f"Parse failed for {file_path}: {e}")
    chunks = heuristic_chunk(source_code)  # fallback
    mark_partially_indexed(file_id)
```

#### Embedding Model Failures
**Scenario**: Embedding model crashes, OOM, or unavailable

**Mitigation**:
1. Retry with exponential backoff (3 attempts)
2. If model persistently fails:
   - Mark workspace as "text-only mode"
   - Disable vector search (still have symbol + text search)
   - Alert user with clear error message
3. Queue failed chunks for later retry (after model restart)
4. Allow user to swap embedding model in settings

**Degraded Mode**:
- Symbol search still works (SQLite FTS)
- Text search still works (ripgrep)
- Agent quality degrades but remains functional

```python
@retry(max_attempts=3, backoff=exponential)
async def embed_chunks(chunks: List[str]) -> List[np.ndarray]:
    try:
        return await embedding_model.encode(chunks)
    except (OOMError, ModelUnavailable) as e:
        logger.error(f"Embedding failed: {e}")
        workspace.set_mode("text_only")
        raise EmbeddingUnavailable()
```

#### Qdrant Unavailable
**Scenario**: Qdrant container stopped, crashed, or unreachable

**Mitigation**:
1. Health check on startup and every 60s
2. If Qdrant down:
   - Workspace enters "text-only mode"
   - Vector search disabled
   - Extension shows warning banner
3. Auto-reconnect when Qdrant comes back
4. Catch up indexing (queue unflushed vectors)

**Degraded Mode**:
- Symbol + text search only
- Agent still functional for simple tasks
- User notified with actionable error

```python
class VectorStore:
    async def health_check(self):
        try:
            await self.qdrant_client.get_collections()
            self.available = True
        except Exception:
            self.available = False
            workspace.set_mode("text_only")
            notify_user("Vector search unavailable")
```

---

### 2. Context Size Management

#### WebSocket Message Size Limits
**Problem**: Large context structures exceed WS frame limits (default 1MB)

**Solution**: Chunked context protocol

```typescript
// Instead of single large message
{
  "type": "client.user_message",
  "message": "...",
  "context": { /* 5MB of data */ }
}

// Send in chunks
{
  "type": "client.context_start",
  "message": "...",
  "context_id": "ctx_abc123",
  "total_chunks": 5
}

{
  "type": "client.context_chunk",
  "context_id": "ctx_abc123",
  "chunk_index": 0,
  "data": { "diagnostics": [...] }
}

// ... more chunks ...

{
  "type": "client.context_end",
  "context_id": "ctx_abc123"
}
```

**Limits**:
- Max single chunk: 256KB
- Max total context: 10MB
- Max chunks: 100

#### Context Truncation Strategy
**Problem**: Context exceeds model's context window

**Solution**: Priority-based truncation

```python
class ContextBudget:
    def __init__(self, max_tokens: int):
        self.max_tokens = max_tokens
        self.reserved_response = 4096  # reserve for output
        self.available = max_tokens - self.reserved_response
    
    def allocate(self):
        # Priority order (never drop these)
        required = {
            "task_spec": 500,
            "current_file": min(2000, file_tokens),
            "diagnostics": min(1000, diag_tokens),
            "constitution": 500
        }
        
        remaining = self.available - sum(required.values())
        
        # Optional context (drop from bottom up if needed)
        optional = [
            ("retrieved_evidence", 0.6 * remaining),  # 60%
            ("history", 0.2 * remaining),              # 20%
            ("terminal_output", 0.1 * remaining),      # 10%
            ("git_context", 0.1 * remaining)           # 10%
        ]
        
        return required | dict(optional)
```

**Truncation Rules**:
1. Never truncate: task spec, current file, diagnostics, constitution
2. Truncate first: history (keep last N messages)
3. Truncate second: terminal output (keep last 500 lines)
4. Truncate third: retrieved evidence (keep top-ranked chunks)
5. Alert user if critical context dropped

#### Terminal Output Truncation
**Problem**: `npm test` output can be 100k+ lines

**Solution**: Smart truncation

```python
def truncate_terminal_output(output: str, max_lines: int = 500) -> str:
    lines = output.split('\n')
    
    if len(lines) <= max_lines:
        return output
    
    # Keep first 100 lines (command, initial output)
    # Keep last 400 lines (failures, summary)
    return '\n'.join(
        lines[:100] + 
        [f"... ({len(lines) - 500} lines truncated) ..."] +
        lines[-400:]
    )
```

**Additional filters**:
- Remove ANSI color codes
- Collapse repeated lines (e.g., 1000x "Loading...")
- Extract only failure sections for tests

---

### 3. Model Context Window Detection

**Problem**: Architecture assumes 16k+ context, many local models are 4k-8k

**Solution**: Dynamic context budget

```python
class ModelAdapter:
    def get_context_window(self) -> int:
        """Return model's actual context window size"""
        if self.provider == "ollama":
            # Query Ollama API for model info
            info = requests.get(f"{ollama_url}/api/show", 
                              json={"name": self.model_name})
            return info.json().get("context_length", 4096)
        
        elif self.provider == "vllm":
            # vLLM exposes this in /v1/models
            return self.vllm_client.get_model_info()["max_model_len"]
        
        elif self.provider == "llamacpp":
            # Read from model metadata
            return self.llamacpp_context_size
        
        return 4096  # safe default

class ContextManager:
    def __init__(self, model: ModelAdapter):
        self.context_window = model.get_context_window()
        
        # Adjust strategy based on window size
        if self.context_window < 8192:
            # Aggressive truncation for small models
            self.strategy = "minimal"
            self.max_retrieved_chunks = 5
            self.max_history_messages = 2
        
        elif self.context_window < 16384:
            # Moderate context
            self.strategy = "balanced"
            self.max_retrieved_chunks = 10
            self.max_history_messages = 5
        
        else:
            # Full context
            self.strategy = "full"
            self.max_retrieved_chunks = 20
            self.max_history_messages = 10
```

**User notification**:
```
⚠️ Model 'codellama:7b' has 4k context window
   Using minimal context strategy
   Consider using a larger model for complex tasks
```

---

### 4. Diff Conflict Resolution

#### File Modified During Agent Response
**Problem**: User edits file while agent generates diff

**Solution**: Content hash validation

```typescript
interface PatchProposal {
  file_path: string;
  base_hash: string;  // SHA-256 of file when diff generated
  diff: string;
}

async function applyPatch(patch: PatchProposal): Promise<ApplyResult> {
  const currentHash = await getFileHash(patch.file_path);
  
  if (currentHash !== patch.base_hash) {
    return {
      success: false,
      error: "FILE_MODIFIED",
      message: "File changed since diff was generated",
      resolution_options: [
        "regenerate",  // Ask agent to regenerate diff
        "force",       // Apply anyway (might conflict)
        "cancel"       // Skip this file
      ]
    };
  }
  
  // Hash matches, safe to apply
  return applyWorkspaceEdit(patch.diff);
}
```

**UI Flow**:
```
⚠️ Conflict detected in login.ts
   File was modified since AI generated this diff
   
   [Regenerate Diff] [Show Changes] [Skip File]
```

#### Three-Way Merge for Conflicts
**Problem**: Patch applies but creates conflicts

**Solution**: Use VS Code merge conflict UI

```typescript
async function applyPatchWithMerge(patch: PatchProposal) {
  try {
    await applyWorkspaceEdit(patch.diff);
  } catch (ConflictError) {
    // Create merge conflict markers
    const conflictMarkers = createMergeConflict(
      patch.base_content,
      patch.proposed_content,
      getCurrentContent()
    );
    
    // Write to file with conflict markers
    await writeFile(patch.file_path, conflictMarkers);
    
    // Open in VS Code merge editor
    await vscode.commands.executeCommand(
      'merge-conflict.accept.both',
      vscode.Uri.file(patch.file_path)
    );
  }
}
```

#### Undo Stack
**Problem**: User wants to undo AI changes

**Solution**: Maintain undo history per session

```typescript
class DiffManager {
  private undoStack: Array<{
    file_path: string;
    before_hash: string;
    after_hash: string;
    before_content: string;  // stored in memory
    timestamp: Date;
  }> = [];
  
  async applyPatch(patch: PatchProposal) {
    const beforeContent = await readFile(patch.file_path);
    const beforeHash = hash(beforeContent);
    
    await applyWorkspaceEdit(patch.diff);
    
    const afterHash = await getFileHash(patch.file_path);
    
    // Push to undo stack
    this.undoStack.push({
      file_path: patch.file_path,
      before_hash: beforeHash,
      after_hash: afterHash,
      before_content: beforeContent,
      timestamp: new Date()
    });
  }
  
  async undo(file_path: string) {
    const entry = this.undoStack
      .reverse()
      .find(e => e.file_path === file_path);
    
    if (!entry) return;
    
    await writeFile(file_path, entry.before_content);
    this.undoStack = this.undoStack.filter(e => e !== entry);
  }
  
  async undoAll() {
    for (const entry of this.undoStack.reverse()) {
      await writeFile(entry.file_path, entry.before_content);
    }
    this.undoStack = [];
  }
}
```

---

### 5. Resource Limits and Scaling

#### Memory Management (Embedding Model)
**Problem**: Embedding model consumes excessive memory

**Solution**: Batch size limits and memory monitoring

```python
class EmbeddingManager:
    def __init__(self):
        self.max_batch_size = 100
        self.memory_threshold = 0.8  # 80% of available RAM
    
    async def embed_chunks(self, chunks: List[str]) -> List[np.ndarray]:
        # Monitor memory before batch
        if psutil.virtual_memory().percent > 80:
            # Reduce batch size
            self.max_batch_size = max(10, self.max_batch_size // 2)
            logger.warning(f"Reduced batch size to {self.max_batch_size}")
        
        # Process in smaller batches
        results = []
        for i in range(0, len(chunks), self.max_batch_size):
            batch = chunks[i:i + self.max_batch_size]
            embeddings = await self.model.encode(batch)
            results.extend(embeddings)
            
            # Allow garbage collection between batches
            gc.collect()
        
        return results
```

#### Qdrant Scaling Limits
**Problem**: 1M+ chunks cause slow queries

**Solution**: Collection partitioning and archival

```python
class VectorStoreManager:
    def __init__(self):
        self.max_chunks_per_collection = 500_000
    
    async def should_partition(self, workspace_id: str) -> bool:
        count = await self.get_chunk_count(workspace_id)
        return count > self.max_chunks_per_collection
    
    async def partition_collection(self, workspace_id: str):
        # Create hot/warm/cold collections
        collections = {
            "hot": "recently accessed (< 7 days)",
            "warm": "moderately accessed (< 30 days)",
            "cold": "rarely accessed (> 30 days)"
        }
        
        for tier, description in collections.items():
            await self.qdrant.create_collection(
                f"{workspace_id}_{tier}",
                vectors_config=self.vector_config
            )
        
        # Migrate chunks based on access patterns
        await self.migrate_by_access_time(workspace_id)
    
    async def search_tiered(self, query: str, workspace_id: str):
        # Search hot first (90% of queries satisfied here)
        results = await self.search(f"{workspace_id}_hot", query, limit=20)
        
        if len(results) < 10:
            # Search warm if insufficient results
            warm_results = await self.search(f"{workspace_id}_warm", query, limit=10)
            results.extend(warm_results)
        
        return results[:20]  # Top 20 combined
```

#### SQLite Scaling
**Problem**: Large workspaces (100k+ files) slow down SQLite

**Solution**: Proper indexing and archival

```sql
-- Critical indexes
CREATE INDEX idx_files_path ON files(path);
CREATE INDEX idx_files_hash ON files(content_hash);
CREATE INDEX idx_chunks_file_id ON chunks(file_id);
CREATE INDEX idx_symbols_name ON symbols(name);
CREATE INDEX idx_symbols_file_id ON symbols(file_id);

-- Full-text search for symbols
CREATE VIRTUAL TABLE symbols_fts USING fts5(
  name,
  signature,
  content='symbols',
  content_rowid='id'
);

-- Archive old sessions (> 30 days)
CREATE TABLE sessions_archive (
  -- same schema as sessions
);

-- Periodically move old sessions
INSERT INTO sessions_archive 
SELECT * FROM sessions 
WHERE updated_at < datetime('now', '-30 days');

DELETE FROM sessions 
WHERE updated_at < datetime('now', '-30 days');
```

**Query optimization**:
```python
# BAD: Loads entire table into memory
files = session.query(File).all()

# GOOD: Paginate and stream
files = session.query(File).yield_per(1000)
for file in files:
    process(file)
```

---

### 6. Observability and Debugging

#### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Every operation logs structured data
logger.info(
    "indexing_started",
    workspace_id=workspace.id,
    file_count=len(files),
    mode="incremental"
)

logger.info(
    "retrieval_completed",
    workspace_id=workspace.id,
    query=query,
    symbol_results=len(symbol_results),
    vector_results=len(vector_results),
    latency_ms=elapsed_ms
)

logger.error(
    "patch_apply_failed",
    workspace_id=workspace.id,
    file_path=file_path,
    error_type="conflict",
    base_hash=base_hash,
    current_hash=current_hash
)
```

#### Metrics Collection
```python
from prometheus_client import Counter, Histogram, Gauge

# Counters
requests_total = Counter('requests_total', 'Total requests', ['endpoint'])
errors_total = Counter('errors_total', 'Total errors', ['error_type'])
patches_applied = Counter('patches_applied_total', 'Patches applied', ['result'])

# Histograms (latency)
indexing_duration = Histogram('indexing_duration_seconds', 'Indexing time')
retrieval_duration = Histogram('retrieval_duration_seconds', 'Retrieval time')
model_inference_duration = Histogram('model_inference_seconds', 'Model inference')

# Gauges (state)
active_sessions = Gauge('active_sessions', 'Active sessions')
indexed_files = Gauge('indexed_files', 'Total indexed files', ['workspace_id'])
```

#### Debug Mode (Extension)
```typescript
// Settings
"locoAgent.debug": true

// When enabled
- Log all WS messages to Output channel
- Show context pack in debug panel
- Show retrieval results before sending to model
- Show token usage and context breakdown
- Enable slow-motion mode (delay between steps)
```

#### Performance Profiling
```python
import cProfile
import pstats

class ProfilingMiddleware:
    async def __call__(self, request, call_next):
        if request.headers.get("X-Profile"):
            profiler = cProfile.Profile()
            profiler.enable()
            
            response = await call_next(request)
            
            profiler.disable()
            stats = pstats.Stats(profiler)
            stats.sort_stats('cumulative')
            
            # Write to file
            stats.dump_stats(f"profile_{request.url.path}.prof")
            
            return response
        else:
            return await call_next(request)
```

---

### 7. Graceful Degradation Strategy

| Component Failure | Impact | Degraded Mode | User Experience |
|------------------|--------|---------------|-----------------|
| Qdrant down | No vector search | Symbol + text search only | Warning banner: "Vector search unavailable" |
| Embedding model crash | No new embeddings | Use cached embeddings + text search | Warning: "Semantic search disabled" |
| Tree-sitter parse fail | No AST chunks | Heuristic chunking | Transparent (no user notification) |
| Model timeout | No response | Retry with smaller context | "Retrying with reduced context..." |
| SQLite lock | Writes blocked | Queue writes, reads still work | Transparent (retry automatically) |
| Network partition | Server unreachable | Extension shows cached history | "Reconnecting..." indicator |

**Principle**: Never fail completely. Always provide reduced functionality.

---

### 8. Testing Strategy (From Day One)

#### Unit Tests (Phase 1)
```python
# tests/test_chunking.py
def test_ast_chunking_with_valid_code():
    code = "def foo(): pass"
    chunks = ast_chunk(code)
    assert len(chunks) == 1
    assert "def foo()" in chunks[0]

def test_ast_chunking_falls_back_on_parse_error():
    code = "def foo( invalid syntax"
    chunks = ast_chunk(code)  # Should not raise
    assert len(chunks) > 0  # Heuristic fallback

# tests/test_context_budget.py
def test_context_truncation_preserves_required():
    budget = ContextBudget(max_tokens=8192)
    context = budget.allocate(large_context)
    
    assert "task_spec" in context
    assert "current_file" in context
    assert "diagnostics" in context

# tests/test_diff_apply.py
async def test_apply_patch_detects_file_modified():
    patch = create_test_patch(base_hash="abc123")
    modify_file_externally()  # Simulate user edit
    
    result = await apply_patch(patch)
    assert result.success == False
    assert result.error == "FILE_MODIFIED"
```

#### Integration Tests (Phase 2-3)
```python
# tests/integration/test_retrieval.py
async def test_symbol_search_finds_function():
    workspace = await create_test_workspace()
    await index_workspace(workspace)
    
    results = await search_symbols("login", workspace.id)
    assert any("login" in r.name for r in results)

# tests/integration/test_websocket.py
async def test_client_server_message_flow():
    async with websocket_client() as ws:
        await ws.send_json({"type": "client.hello"})
        response = await ws.receive_json()
        assert response["type"] == "server.hello"
```

#### E2E Tests (Phase 4-5)
```typescript
// tests/e2e/test_fix_command.spec.ts
test('fix command proposes and applies patch', async () => {
  await extension.activate();
  await openFile('src/bug.ts');
  
  await chatInput.type('/fix the bug');
  await chatInput.pressEnter();
  
  await waitForProposedPatch();
  await clickAcceptPatch();
  
  const content = await readFile('src/bug.ts');
  expect(content).toContain('fixed code');
});
```

#### Regression Tests (Continuous)
```python
# tests/regression/test_retrieval_quality.py
def test_retrieval_regression():
    """Ensure retrieval quality doesn't degrade"""
    test_cases = load_golden_queries()
    
    for query, expected_files in test_cases:
        results = search(query)
        actual_files = [r.file_path for r in results[:5]]
        
        # At least 3 of top 5 should match expected
        overlap = len(set(actual_files) & set(expected_files))
        assert overlap >= 3, f"Retrieval degraded for: {query}"
```

**Test Coverage Goals**:
- Unit tests: 80% coverage
- Integration tests: Critical paths covered
- E2E tests: All user flows covered
- Regression tests: All bugs become test cases
