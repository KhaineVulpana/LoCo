import pytest

from app.tools.file_tools import ReadFileTool, WriteFileTool, ListFilesTool


@pytest.mark.asyncio
async def test_write_and_read_file(tmp_path):
    writer = WriteFileTool(str(tmp_path))
    write_result = await writer.execute('notes/info.txt', 'hello')
    assert write_result['success'] is True

    reader = ReadFileTool(str(tmp_path))
    read_result = await reader.execute('notes/info.txt')
    assert read_result['success'] is True
    assert read_result['content'] == 'hello'


@pytest.mark.asyncio
async def test_list_files_non_recursive(tmp_path):
    (tmp_path / 'a.txt').write_text('a', encoding='utf-8')
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'b.txt').write_text('b', encoding='utf-8')

    tool = ListFilesTool(str(tmp_path))
    result = await tool.execute('.', recursive=False)

    assert result['success'] is True
    assert 'a.txt' in result['files']
    assert 'dir' in result['directories']
    assert 'dir/b.txt' not in result['files']


@pytest.mark.asyncio
async def test_list_files_recursive(tmp_path):
    (tmp_path / 'dir').mkdir()
    (tmp_path / 'dir' / 'b.txt').write_text('b', encoding='utf-8')

    tool = ListFilesTool(str(tmp_path))
    result = await tool.execute('.', recursive=True)

    assert result['success'] is True
    normalized = [path.replace('\\', '/') for path in result['files']]
    assert 'dir/b.txt' in normalized


@pytest.mark.asyncio
async def test_path_traversal_is_blocked(tmp_path):
    reader = ReadFileTool(str(tmp_path))
    result = await reader.execute('../outside.txt')
    assert result['success'] is False
    assert 'Access denied' in result['error']
