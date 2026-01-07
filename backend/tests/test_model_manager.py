import pytest

from app.core.model_manager import ModelManager, ModelConfig


@pytest.fixture()
def fresh_model_manager():
    ModelManager._instance = None
    return ModelManager()


@pytest.mark.asyncio
async def test_switch_model_sets_state(monkeypatch, fresh_model_manager):
    manager = fresh_model_manager
    old_config = ModelConfig(provider='ollama', model_name='old', url='http://old')
    manager.current_config = old_config
    manager.current_model = object()

    new_config = ModelConfig(provider='ollama', model_name='new', url='http://new')
    new_client = object()
    flags = {'unloaded': False}

    async def fake_unload():
        flags['unloaded'] = True

    async def fake_load(config):
        assert config.provider == new_config.provider
        return new_client

    monkeypatch.setattr(manager, '_unload_current', fake_unload)
    monkeypatch.setattr(manager, '_load_model', fake_load)

    result = await manager.switch_model(
        provider='ollama',
        model_name='new',
        url='http://new'
    )

    assert result is new_client
    assert manager.current_model is new_client
    assert manager.current_config.model_name == 'new'
    assert flags['unloaded'] is True


@pytest.mark.asyncio
async def test_switch_model_short_circuits_when_same(monkeypatch, fresh_model_manager):
    manager = fresh_model_manager
    config = ModelConfig(provider='ollama', model_name='same', url='http://same')
    sentinel = object()
    manager.current_config = config
    manager.current_model = sentinel

    called = {'load': False}

    async def fake_load(config):
        called['load'] = True
        return object()

    monkeypatch.setattr(manager, '_load_model', fake_load)

    result = await manager.switch_model(
        provider='ollama',
        model_name='same',
        url='http://same'
    )

    assert result is sentinel
    assert called['load'] is False


@pytest.mark.asyncio
async def test_ensure_model_loaded_uses_existing(monkeypatch, fresh_model_manager):
    manager = fresh_model_manager
    config = ModelConfig(provider='ollama', model_name='ready', url='http://ready')
    sentinel = object()
    manager.current_config = config
    manager.current_model = sentinel

    result = await manager.ensure_model_loaded(config)
    assert result is sentinel
