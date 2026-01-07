import pytest

from app.core.qdrant_manager import QdrantManager


@pytest.mark.asyncio
async def test_ensure_running_when_already_healthy(monkeypatch):
    manager = QdrantManager()

    async def healthy():
        return True

    started = {'called': False}

    def start_qdrant():
        started['called'] = True
        return True

    monkeypatch.setattr(manager, 'is_healthy', healthy)
    monkeypatch.setattr(manager, 'start_qdrant', start_qdrant)

    result = await manager.ensure_running()
    assert result is True
    assert started['called'] is False


@pytest.mark.asyncio
async def test_ensure_running_starts_when_unhealthy(monkeypatch):
    manager = QdrantManager()

    async def unhealthy():
        return False

    monkeypatch.setattr(manager, 'is_healthy', unhealthy)
    monkeypatch.setattr(manager, 'start_qdrant', lambda: True)

    async def wait_for_healthy(timeout=30):
        return True

    monkeypatch.setattr(manager, 'wait_for_healthy', wait_for_healthy)

    result = await manager.ensure_running()
    assert result is True


@pytest.mark.asyncio
async def test_wait_for_healthy_returns_true_when_ready(monkeypatch):
    manager = QdrantManager()

    async def healthy():
        return True

    monkeypatch.setattr(manager, 'is_healthy', healthy)

    result = await manager.wait_for_healthy(timeout=1)
    assert result is True


@pytest.mark.asyncio
async def test_ensure_running_fails_when_start_fails(monkeypatch):
    manager = QdrantManager()

    async def unhealthy():
        return False

    monkeypatch.setattr(manager, 'is_healthy', unhealthy)
    monkeypatch.setattr(manager, 'start_qdrant', lambda: False)

    result = await manager.ensure_running()
    assert result is False
