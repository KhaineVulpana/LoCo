# API Quick Reference (VS Code)

Workspaces
- POST /v1/workspaces/register
- GET /v1/workspaces
- GET /v1/workspaces/{id}
- POST /v1/workspaces/{id}/index
- POST /v1/workspaces/{id}/watch/start
- POST /v1/workspaces/{id}/watch/stop
- GET /v1/workspaces/{id}/policy
- PUT /v1/workspaces/{id}/policy

Sessions
- POST /v1/sessions
- GET /v1/sessions?workspace_id=...
- GET /v1/sessions/{id}

Models
- GET /v1/models
- GET /v1/models/current
- PUT /v1/models/current

Knowledge
- POST /v1/knowledge/{module_id}/index-docs
- POST /v1/knowledge/{module_id}/index-training
- GET /v1/knowledge/{module_id}/stats
- POST /v1/knowledge/{module_id}/retrieve
- POST /v1/knowledge/{module_id}/clear
