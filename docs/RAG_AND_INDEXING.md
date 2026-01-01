# Indexing & Agentic RAG

## Indexing pipeline (incremental, file-watcher based)

### Initial indexing (workspace registration)
1. **Discover files**:
   - Respect .gitignore, .agenticcodexignore
   - Configurable ignores (node_modules, .git, build artifacts)
   - Prioritize source files over generated files
   
2. **Detect language + file type**:
   - tree-sitter grammar detection
   - Fallback to extension-based detection
   - Binary file exclusion (with configurable overrides)

3. **Chunk intelligently**:
   - **For code** (tree-sitter AST chunking):
     - Functions/methods as primary chunks
     - Classes as secondary chunks (with method sub-chunks)
     - Top-level statements as fallback chunks
     - Preserve full context (imports, class definition, function signature)
   - **For text** (Markdown, docs):
     - Section-based chunking (by headers)
     - Fallback to sliding window (1000 tokens, 200 token overlap)
   - **For config** (JSON, YAML, TOML):
     - Top-level keys as chunks
     - Nested objects as sub-chunks if large

4. **Embed each chunk**:
   - Local embedding model (e.g., all-MiniLM-L6-v2, nomic-embed-text)
   - Batch embedding (100 chunks at a time)
   - Cache embeddings by content hash
   - Store embedding metadata (model version, dimensions)

5. **Store vectors + metadata**:
   - **Vector DB** (Qdrant):
     - Vectors with payload: file_path, chunk_id, offsets, language, tags
     - Collections per workspace (isolation)
     - Filtered search by language, module, recency
   - **SQLite** (metadata):
     - files: path, hash, language, size, last_modified
     - chunks: file_id, offsets, token_count, vector_id
     - symbols: name, kind (function/class/var), file_id, line, signature
     - file_summaries: file_id, summary_text, dependencies

6. **Extract symbol map**:
   - Function/class/method names with signatures
   - Imports and exports
   - Test file associations (src/foo.ts → tests/foo.test.ts)
   - Call relationships (optional, for callgraph-aware retrieval)

### Incremental indexing (file watcher events)

Extension sends file changes to server in real-time:
```typescript
{
  "type": "created" | "modified" | "deleted",
  "file_path": "src/utils/helper.ts",
  "content_hash": "sha256:abc123...",
  "timestamp": "2025-12-30T10:35:12Z"
}
```

Server processing:
1. **Created**: Full indexing (chunk, embed, store)
2. **Modified**: 
   - Compare content hash
   - If changed: re-chunk, re-embed changed chunks only
   - Update symbol map
   - Update file summary
3. **Deleted**: Remove vectors, chunks, symbols, file record

### Background indexing strategy
- Index in background (don't block user interactions)
- Prioritize open files and recently accessed files
- Batch updates (every 5 seconds or 100 files)
- Report progress to extension (file count, percentage)

---

## Retrieval (multi-source, automatic)

### Retrieval sources (hybrid)

1. **Symbol index** (fast, precise):
   - SQLite full-text search on symbol names
   - Signature matching (fuzzy)
   - Use case: "Find the validatePassword function"
   - Latency: <50ms
   
2. **Text search** (ripgrep):
   - Full-text search with regex support
   - Case-insensitive, multi-line
   - Use case: "Find all TODO comments"
   - Latency: <200ms for 10k files
   
3. **Vector search** (semantic):
   - Qdrant vector similarity search
   - Filtered by language, module, recency
   - Use case: "Find code that handles authentication"
   - Latency: <500ms for 100k chunks
   
4. **Dependency expansion**:
   - Follow imports/exports
   - Include callees and callers (if callgraph enabled)
   - Include associated test files
   - Use case: "Get all files related to login.ts"

### Retrieval strategy (automatic, task-aware)

Extension gathers context automatically based on task type:

#### For `/fix` command:
1. **Immediate context** (no retrieval needed):
   - Current file with diagnostics
   - Terminal output (test failures, build errors)
   - Git diff (if relevant)
   
2. **Symbol retrieval** (if needed):
   - Functions mentioned in error messages
   - Imported modules from current file
   - Related test files
   
3. **Vector retrieval** (if symbol retrieval insufficient):
   - "How to handle [error type]"
   - "Examples of [pattern] in this codebase"

#### For `/test` command:
1. **Immediate context**:
   - Current file or selection
   - Existing test files for this file
   
2. **Symbol retrieval**:
   - Test utilities and helpers
   - Similar test files in workspace
   
3. **Vector retrieval**:
   - "Test examples for [function type]"
   - "Mocking patterns in this codebase"

#### For `/refactor` command:
1. **Immediate context**:
   - Current file or selection
   
2. **Dependency expansion**:
   - All imports from current file
   - All files that import current file
   - Call graph (callers and callees)
   
3. **Vector retrieval**:
   - "Similar refactoring patterns"
   - "Best practices for [code pattern]"

#### For `/explain` command:
1. **Immediate context**:
   - Selection or current function
   
2. **Symbol retrieval**:
   - Called functions from selection
   - Type definitions referenced
   
3. **Vector retrieval** (minimal):
   - Only if selection references obscure patterns

### Reranker (optional, quality improvement)

After initial retrieval (symbol + text + vector), optionally rerank:
1. **Cross-encoder reranking**:
   - Model: ms-marco-MiniLM-L-6-v2 (or similar)
   - Input: (query, retrieved_chunk) pairs
   - Output: relevance score (0-1)
   
2. **Rerank top 50 candidates** → **Keep top 10-20**

3. **Reranking criteria**:
   - Semantic relevance to task
   - Recency (newer code prioritized)
   - Proximity to current file (same module > different module)
   - Test files deprioritized unless explicitly needed

---

## Agentic RAG loop (iterative retrieval)

For complex tasks (implement/fix/refactor), agent retrieves iteratively:

### Pass 1: Initial retrieval (before planning)
1. **Automatic context** from extension (always):
   - Current file, selection, diagnostics
   - Open editors, recent terminal output
   
2. **Symbol search** based on task intent:
   - Extract key terms from user message
   - Search symbol index (functions, classes)
   - Retrieve top 10 symbols with full context
   
3. **Text search** for patterns:
   - Error messages from diagnostics
   - Stack traces from terminal output
   - Grep for TODOs, FIXMEs if relevant
   
4. **Vector search** for semantic context:
   - Query: task description + key terms
   - Filter: same language, same module preferred
   - Top 10 semantic matches

**Result**: 20-30 chunks (symbol + text + vector)

### Rerank and prune
1. **Rerank** using cross-encoder (optional)
2. **Prune** to context budget (e.g., 8k tokens):
   - Keep high-relevance chunks
   - Keep current file (always)
   - Keep diagnostic-related chunks (always)
3. **Organize by file** (group chunks from same file)

### Pass 2: Post-plan retrieval (targeted)
After generating plan, retrieve additional context for each step:

Example plan:
```
1. Add input validation to login.ts
2. Add TypeScript types to auth interfaces
3. Update tests
```

For step 1:
- Retrieve validator utilities from codebase
- Retrieve examples of input validation in other files

For step 2:
- Retrieve type definitions from @types or interfaces/
- Retrieve similar type patterns

For step 3:
- Retrieve test utilities
- Retrieve similar test patterns

### Pass 3: Failure retrieval (after test/build failures)
If patch application succeeds but verification fails:
1. **Extract failure details**:
   - Parse test output (Jest, pytest, etc.)
   - Parse build errors (TypeScript, ESLint)
   - Extract stack traces
   
2. **Targeted retrieval**:
   - Retrieve files mentioned in stack trace
   - Retrieve failing test file and source file
   - Vector search: "How to fix [error type]"
   
3. **Iterate** with focused context

---

## Context pack structure (bounded, structured)

Every agent invocation receives a context pack with these sections:

### 1. Task specification
```yaml
goal: "Fix SQL injection vulnerability in login.ts"
slash_command: "/fix"
acceptance_criteria:
  - Tests pass
  - No SQL injection vulnerabilities
  - Type safety maintained
constraints:
  - Do not change API contract
  - Maintain backward compatibility
```

### 2. Workspace context (automatic from extension)
```yaml
current_file: "src/auth/login.ts"
selection: lines 23-45
diagnostics:
  - file: src/auth/login.ts
    line: 23
    message: "Potential SQL injection"
terminal_output: |
  $ npm test
  FAIL src/auth/login.test.ts
    ✕ should validate input (23ms)
git_status:
  branch: feature/auth-fix
  modified_files: [src/auth/login.ts]
```

### 3. ACE artifacts (constitution, gotchas, runbook)
```yaml
constitution:
  - Always use parameterized queries for SQL
  - Validate all user input before database operations
  - Use TypeScript strict mode
gotchas:
  - Database connection requires environment variable DB_URL
  - Tests must run with NODE_ENV=test
runbook:
  test: npm test
  build: npm run build
  lint: npm run lint
```

### 4. Retrieved evidence (with citations)
```yaml
evidence:
  - file: src/auth/login.ts
    lines: 23-45
    content: |
      function login(username, password) {
        return db.query('SELECT * FROM users WHERE name = ' + username);
      }
    
  - file: src/utils/validator.ts
    lines: 12-20
    content: |
      export function validateInput(input: string): boolean {
        return input && input.length > 0;
      }
    
  - file: src/db/connection.ts
    lines: 5-10
    content: |
      export function query(sql: string, params?: any[]): Promise<any> {
        return pool.query(sql, params);
      }
```

### 5. Conversation history (recent messages only)
```yaml
history:
  - role: user
    content: "Fix the authentication bug"
  
  - role: assistant
    content: "I'll analyze the authentication flow..."
```

### Token budget discipline
- **Total budget**: 16k tokens (for models with 32k context)
- **Reserved for response**: 4k tokens
- **Available for context**: 12k tokens

**Allocation**:
- Task spec: ~500 tokens
- Workspace context: ~1k tokens
- ACE artifacts: ~1k tokens (prefer ACE over raw logs)
- Retrieved evidence: ~8k tokens
- History: ~1.5k tokens (last 5 messages)

**Overflow strategy**:
- Drop oldest history messages first
- Then reduce retrieved evidence (keep highest-ranked chunks)
- Never drop task spec, current file, or diagnostics
- Never drop ACE constitution

---

## Caching strategy

### Embedding cache
- Key: content_hash (SHA-256)
- Value: embedding vector
- Rationale: Same code chunk → same embedding (no need to re-embed)
- Storage: SQLite table `embedding_cache`

### Retrieval cache
- Key: (query_hash, filters)
- Value: retrieved chunk IDs + scores
- TTL: 5 minutes (short, since codebase changes frequently)
- Rationale: Same query in quick succession → same results
- Storage: In-memory LRU cache (max 1000 entries)

### Symbol index cache
- Key: symbol_name
- Value: list of (file_path, line, signature)
- Update: on file change events
- Rationale: Symbol lookups are frequent and fast
- Storage: SQLite with full-text index

---

## Quality metrics (track and improve)

### Retrieval quality
- **Precision@10**: Of top 10 chunks, how many are relevant?
- **Recall**: Did we retrieve the chunks that led to successful fix?
- **MRR (Mean Reciprocal Rank)**: How highly ranked was the most relevant chunk?

### Context pack quality
- **Task success rate**: Did agent complete task successfully?
- **Iteration count**: How many fix → test cycles needed?
- **Context utilization**: Did agent use retrieved chunks in response?

### ACE artifact quality
- **Artifact reuse**: How often are artifacts retrieved and applied?
- **Artifact accuracy**: Do artifacts prevent repeated failures?
- **Artifact coverage**: Do we have constitution/gotchas for all modules?

---

## Optimization strategies

### For large workspaces (>10k files)
1. **Tiered indexing**:
   - Hot tier: Recently accessed files (index immediately)
   - Warm tier: Modified in last week (index in background)
   - Cold tier: Rarely accessed (index on-demand)

2. **Partitioned search**:
   - Search current module first (90% of queries)
   - Expand to workspace if needed
   - Use file-path prefix filtering in vector DB

3. **Incremental embeddings**:
   - Only re-embed changed chunks (not entire file)
   - Use content-addressable storage (chunks by hash)

### For slow embedding models
1. **Batch embedding** (100 chunks at a time)
2. **Prioritize visible files** (index open editors first)
3. **Background indexing** (low-priority thread)
4. **Embedding queue** (FIFO with priority override)

### For large context windows (>32k tokens)
1. **Dynamic budget allocation**:
   - Simple tasks: 8k context, 8k response
   - Complex tasks: 24k context, 8k response
   
2. **Hierarchical summarization**:
   - Full file content for current file
   - Function summaries for related files
   - File-level summaries for distant dependencies

3. **Streaming context**:
   - Send ACE + current file first
   - Stream retrieved chunks as agent requests them
   - Agent can request "more context" mid-response
