import asyncio

import pytest

from app.tools.shell_tools import RunCommandTool


class FakeProcess:
    def __init__(self, stdout=b'', stderr=b'', returncode=0):
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode
        self.killed = False

    async def communicate(self):
        return self._stdout, self._stderr

    def kill(self):
        self.killed = True


@pytest.mark.asyncio
async def test_run_command_success(monkeypatch, tmp_path):
    async def fake_create_subprocess_shell(command, stdout, stderr, cwd):
        return FakeProcess(stdout=b'ok\n', stderr=b'', returncode=0)

    async def passthrough(coro, timeout):
        return await coro

    monkeypatch.setattr(asyncio, 'create_subprocess_shell', fake_create_subprocess_shell)
    monkeypatch.setattr(asyncio, 'wait_for', passthrough)

    tool = RunCommandTool(str(tmp_path))
    result = await tool.execute('echo ok')

    assert result['success'] is True
    assert 'ok' in result['stdout']


@pytest.mark.asyncio
async def test_run_command_timeout(monkeypatch, tmp_path):
    process = FakeProcess()

    async def fake_create_subprocess_shell(command, stdout, stderr, cwd):
        return process

    async def raise_timeout(coro, timeout):
        coro.close()
        raise asyncio.TimeoutError()

    monkeypatch.setattr(asyncio, 'create_subprocess_shell', fake_create_subprocess_shell)
    monkeypatch.setattr(asyncio, 'wait_for', raise_timeout)

    tool = RunCommandTool(str(tmp_path))
    result = await tool.execute('sleep 5', timeout=0.01)

    assert result['success'] is False
    assert 'timed out' in result['error']
    assert process.killed is True
