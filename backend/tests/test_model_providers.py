import pytest

from app.core.model_providers import (
    get_provider,
    OllamaProvider,
    VLLMProvider,
    LlamaCppProvider
)


def test_get_provider_known_and_unknown():
    assert isinstance(get_provider('ollama'), OllamaProvider)
    assert isinstance(get_provider('VLLM'), VLLMProvider)
    assert get_provider('unknown') is None


@pytest.mark.asyncio
async def test_ollama_unload_returns_true():
    provider = OllamaProvider()
    result = await provider.unload_model('test', 'http://localhost')
    assert result is True


@pytest.mark.asyncio
async def test_vllm_unload_not_supported():
    provider = VLLMProvider()
    with pytest.raises(NotImplementedError):
        await provider.unload_model('test', 'http://localhost')


@pytest.mark.asyncio
async def test_llamacpp_unload_not_supported():
    provider = LlamaCppProvider()
    with pytest.raises(NotImplementedError):
        await provider.unload_model('test', 'http://localhost')
