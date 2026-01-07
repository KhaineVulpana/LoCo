import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import models
from app.core.model_manager import ModelConfig


class FakeModelManager:
    def __init__(self):
        self.config = None
        self.loaded = False

    def is_model_loaded(self):
        return self.loaded

    def get_current_config(self):
        return self.config

    async def switch_model(self, provider, model_name, url, context_window, temperature):
        self.config = ModelConfig(
            provider=provider,
            model_name=model_name,
            url=url,
            context_window=context_window,
            temperature=temperature
        )
        self.loaded = True
        return object()

    async def _unload_current(self):
        self.config = None
        self.loaded = False


def create_app(fake_manager):
    app = FastAPI()
    app.include_router(models.router, prefix='/v1/models')
    app.dependency_overrides[models.get_model_manager] = lambda: fake_manager
    return app


def test_model_status_when_unloaded():
    manager = FakeModelManager()
    client = TestClient(create_app(manager))

    response = client.get('/v1/models/status')
    assert response.status_code == 200
    assert response.json()['is_loaded'] is False


def test_model_switch_and_current():
    manager = FakeModelManager()
    client = TestClient(create_app(manager))

    switch_resp = client.post('/v1/models/switch', json={
        'provider': 'ollama',
        'model_name': 'qwen',
        'url': 'http://localhost:11434',
        'context_window': 8192,
        'temperature': 0.6
    })
    assert switch_resp.status_code == 200
    assert switch_resp.json()['success'] is True

    current_resp = client.get('/v1/models/current')
    assert current_resp.status_code == 200
    assert current_resp.json()['model_name'] == 'qwen'


def test_unload_when_not_loaded():
    manager = FakeModelManager()
    client = TestClient(create_app(manager))

    response = client.post('/v1/models/unload')
    assert response.status_code == 400


def test_unload_loaded_model():
    manager = FakeModelManager()
    manager.loaded = True
    manager.config = ModelConfig(
        provider='ollama',
        model_name='qwen',
        url='http://localhost:11434'
    )

    client = TestClient(create_app(manager))
    response = client.post('/v1/models/unload')
    assert response.status_code == 200
    assert response.json()['success'] is True
