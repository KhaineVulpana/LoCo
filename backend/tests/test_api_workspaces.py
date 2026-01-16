import pytest
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.api import workspaces
from app.core.database import get_db
from app.core.runtime import get_embedding_manager, get_vector_store


async def create_app(async_session_maker, fake_embedding_manager=None, fake_vector_store=None):
    app = FastAPI()
    app.include_router(workspaces.router, prefix='/v1/workspaces')

    async def override_get_db():
        async with async_session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    if fake_embedding_manager:
        app.dependency_overrides[get_embedding_manager] = lambda: fake_embedding_manager
    if fake_vector_store:
        app.dependency_overrides[get_vector_store] = lambda: fake_vector_store
    return app


@pytest.mark.asyncio
async def test_register_and_list_workspaces(async_session_maker, tmp_path):
    app = await create_app(async_session_maker)
    workspace_dir = tmp_path / "LoCo"
    workspace_dir.mkdir()
    workspace_path = str(workspace_dir)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.post('/v1/workspaces/register', json={
            'path': workspace_path,
            'name': 'LoCo'
        })
        assert response.status_code == 200
        workspace = response.json()

        list_response = await client.get('/v1/workspaces')
        assert list_response.status_code == 200
        assert len(list_response.json()) == 1

        get_response = await client.get(f"/v1/workspaces/{workspace['id']}")
        assert get_response.status_code == 200
        assert get_response.json()['path'] == workspace_path


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


@pytest.mark.asyncio
async def test_index_workspace_updates_status(
    async_session_maker,
    tmp_path,
    fake_embedding_manager,
    fake_vector_store
):
    (tmp_path / 'main.py').write_text('print("hi")\n', encoding='utf-8')

    app = await create_app(async_session_maker, fake_embedding_manager, fake_vector_store)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url='http://test') as client:
        register = await client.post('/v1/workspaces/register', json={
            'path': str(tmp_path),
            'name': 'TempWorkspace'
        })
        assert register.status_code == 200
        workspace_id = register.json()['id']

        index_response = await client.post(f'/v1/workspaces/{workspace_id}/index', json={
            'module_id': 'vscode'
        })
        assert index_response.status_code == 200
        stats = index_response.json()['stats']
        assert stats['total_files'] == 1
        assert stats['indexed'] == 1

        get_response = await client.get(f"/v1/workspaces/{workspace_id}")
        assert get_response.status_code == 200
        workspace = get_response.json()
        assert workspace['index_status'] in ('complete', 'partial')
        assert workspace['indexed_files'] == 1


@pytest.mark.asyncio
async def test_workspace_policy_round_trip(async_session_maker):
    app = await create_app(async_session_maker)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url='http://test') as client:
        register = await client.post('/v1/workspaces/register', json={
            'path': 'C:/Projects/LoCo',
            'name': 'LoCo'
        })
        assert register.status_code == 200
        workspace_id = register.json()['id']

        get_policy = await client.get(f'/v1/workspaces/{workspace_id}/policy')
        assert get_policy.status_code == 200
        policy = get_policy.json()
        assert policy['allowed_read_globs'] == ['**/*']
        assert policy['allowed_write_globs'] == ['**/*']
        assert policy['blocked_globs'] == ['.git/**', 'node_modules/**']
        assert policy['command_approval'] == 'prompt'
        assert policy['auto_approve_tools'] == []

        update_payload = {
            'allowed_write_globs': ['src/**', 'tests/**'],
            'blocked_commands': ['rm -rf', 'curl'],
            'network_enabled': True,
            'auto_approve_tests': True,
            'auto_approve_tools': ['read_file', 'list_files']
        }

        update_policy = await client.put(
            f'/v1/workspaces/{workspace_id}/policy',
            json=update_payload
        )
        assert update_policy.status_code == 200
        updated = update_policy.json()
        assert updated['allowed_write_globs'] == ['src/**', 'tests/**']
        assert updated['blocked_commands'] == ['rm -rf', 'curl']
        assert updated['network_enabled'] is True
        assert updated['auto_approve_tests'] is True
        assert updated['auto_approve_tools'] == ['read_file', 'list_files']

        get_policy_again = await client.get(f'/v1/workspaces/{workspace_id}/policy')
        assert get_policy_again.status_code == 200
        policy_again = get_policy_again.json()
        assert policy_again['allowed_write_globs'] == ['src/**', 'tests/**']
        assert policy_again['auto_approve_tools'] == ['read_file', 'list_files']
