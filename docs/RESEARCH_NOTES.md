# Research notes (why these choices)

## VS Code extension UI approach
- VS Code Webview is the standard way to build rich custom UIs; message passing via `acquireVsCodeApi()` and `postMessage`.  
  See VS Code docs on Webviews and message passing. (Cited in the conversation.) 

## Claude Code and Codex-like UI
- Claude Code’s VS Code experience includes a dedicated panel and inline diffs, and it is evolving toward sidebar experiences similar to other AI extensions.  
  (Cited in the conversation.)

## Vector DB choice
- Qdrant is commonly positioned as production-grade with filtering and operational maturity; Chroma is often positioned as simpler for prototyping.  
  (Cited in the conversation.)

This repo keeps the vector store behind an adapter so you can swap Qdrant/Chroma/pgvector later without changing the protocol.
