import pytest

from app.ace.reflector import Reflector


class FakeLLMClient:
    def __init__(self, content):
        self.content = content

    async def generate_stream(self, messages, temperature=0.7):
        yield {'type': 'content', 'content': self.content}


@pytest.mark.asyncio
async def test_reflector_parses_json():
    payload = '{"reasoning": "ok", "error_identification": "", "root_cause_analysis": "", "correct_approach": "", "key_insight": "", "bullet_feedback": []}'
    reflector = Reflector(llm_client=FakeLLMClient(payload))

    result = await reflector.reflect(
        task='task',
        trajectory='trace',
        outcome={'success': True},
        max_rounds=1
    )

    assert result['reasoning'] == 'ok'
    assert 'key_insight' in result


@pytest.mark.asyncio
async def test_reflector_returns_default_on_invalid_json():
    reflector = Reflector(llm_client=FakeLLMClient('not-json'))

    result = await reflector.reflect(
        task='task',
        trajectory='trace',
        outcome={'success': False},
        max_rounds=1
    )

    assert result['reasoning'] == 'Unable to generate detailed reflection'
