import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api import sessions, workspaces
from app.core.config import settings
from app.core.database import get_db


async def create_app(async_session_maker):
    app = FastAPI()
    app.include_router(workspaces.router, prefix='/v1/workspaces')
    app.include_router(sessions.router, prefix='/v1/sessions')

    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_session_lifecycle(async_session_maker, monkeypatch):
    monkeypatch.setattr(settings, 'MODEL_PROVIDER', 'ollama')
    monkeypatch.setattr(settings, 'MODEL_NAME', 'qwen')
    monkeypatch.setattr(settings, 'MAX_CONTEXT_TOKENS', 4096)

    app = await create_app(async_session_maker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        ws_response = await client.post('/v1/workspaces/register', json={
            'path': 'C:/Projects/LoCo',
            'name': 'LoCo'
        })
        workspace_id = ws_response.json()['id']

        create_response = await client.post('/v1/sessions', json={
            'workspace_id': workspace_id
        })
        assert create_response.status_code == 200
        session = create_response.json()
        assert session['model_provider'] == 'ollama'
        assert session['model_name'] == 'qwen'

        list_response = await client.get('/v1/sessions', params={
            'workspace_id': workspace_id
        })
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = await client.get(f"/v1/sessions/{session['id']}")
        assert get_response.status_code == 200

        delete_response = await client.delete(f"/v1/sessions/{session['id']}")
        assert delete_response.status_code == 200
        assert delete_response.json()['success'] is True

        list_response = await client.get('/v1/sessions', params={
            'workspace_id': workspace_id
        })
        assert list_response.status_code == 200
        assert list_response.json() == []
