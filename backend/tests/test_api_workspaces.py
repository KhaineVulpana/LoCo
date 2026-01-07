import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api import workspaces
from app.core.database import get_db


async def create_app(async_session_maker):
    app = FastAPI()
    app.include_router(workspaces.router, prefix='/v1/workspaces')

    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_register_and_list_workspaces(async_session_maker):
    app = await create_app(async_session_maker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post('/v1/workspaces/register', json={
            'path': 'C:/Projects/LoCo',
            'name': 'LoCo'
        })
        assert response.status_code == 200
        workspace = response.json()

        list_response = await client.get('/v1/workspaces')
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = await client.get(f"/v1/workspaces/{workspace['id']}")
        assert get_response.status_code == 200
        assert get_response.json()['path'] == 'C:/Projects/LoCo'


@pytest.mark.asyncio
async def test_register_workspace_returns_existing(async_session_maker):
    app = await create_app(async_session_maker)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        first = await client.post('/v1/workspaces/register', json={
            'path': 'C:/Projects/LoCo',
            'name': 'LoCo'
        })
        second = await client.post('/v1/workspaces/register', json={
            'path': 'C:/Projects/LoCo'
        })

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()['id'] == second.json()['id']
