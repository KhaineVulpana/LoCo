import pytest

from app.tools.base import Tool, ToolRegistry


class DummyTool(Tool):
    name = 'dummy'
    description = 'dummy tool'
    parameters = {
        'type': 'object',
        'properties': {},
        'required': []
    }

    async def execute(self, **kwargs):
        return {'success': True, 'payload': kwargs}


@pytest.mark.asyncio
async def test_tool_registry_execute_success():
    registry = ToolRegistry()
    registry.register(DummyTool())

    result = await registry.execute_tool('dummy', {'value': 42})
    assert result['success'] is True
    assert result['payload']['value'] == 42


@pytest.mark.asyncio
async def test_tool_registry_execute_missing_tool():
    registry = ToolRegistry()
    result = await registry.execute_tool('missing', {})

    assert result['success'] is False
    assert 'not found' in result['error']
