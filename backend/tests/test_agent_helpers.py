from app.agent.agent import Agent


def test_format_user_message_with_context(tmp_path):
    agent = Agent(workspace_path=str(tmp_path), module_id='vscode', enable_ace=False)
    context = {
        'active_editor': {
            'file_path': 'main.py',
            'selection': {
                'start': {'line': 1, 'character': 0},
                'end': {'line': 3, 'character': 0}
            }
        },
        'diagnostics': [
            {'file_path': 'main.py', 'line': 10, 'message': 'Syntax error'}
        ],
        'open_editors': [
            {'file_path': 'main.py', 'is_dirty': False, 'visible': True},
            {'file_path': 'utils.py', 'is_dirty': False, 'visible': True}
        ]
    }

    formatted = agent._format_user_message('Fix this', context)
    assert 'Active file: main.py' in formatted
    assert 'Selected lines 1-3' in formatted
    assert 'main.py:10' in formatted
    assert 'Open files: main.py, utils.py' in formatted


def test_build_messages_includes_system_prompt_and_playbook(tmp_path):
    agent = Agent(workspace_path=str(tmp_path), module_id='3d-gen', enable_ace=True)
    bullet_id = agent.playbook.add_bullet('domain_knowledge', 'Meshes are in meters.')

    messages = agent._build_messages()

    assert messages[0]['role'] == 'system'
    assert 'LoCo 3D-Gen assistant' in messages[0]['content']
    assert bullet_id in messages[0]['content']


def test_get_display_result_truncates_read_file(tmp_path):
    agent = Agent(workspace_path=str(tmp_path), module_id='vscode', enable_ace=False)
    content = '\n'.join([f'line{i}' for i in range(60)])
    result = agent._get_display_result('read_file', {
        'success': True,
        'file_path': 'file.txt',
        'content': content,
        'size': len(content)
    })

    assert result['truncated'] is True
    assert result['total_lines'] == 60
    assert result['preview'].startswith('line0')


def test_summarize_tool_result_truncates_large_payloads(tmp_path):
    agent = Agent(workspace_path=str(tmp_path), module_id='vscode', enable_ace=False)

    files = [f'file_{i}.txt' for i in range(25)]
    summary = agent._summarize_tool_result('list_files', {
        'success': True,
        'directory': '.',
        'files': files,
        'directories': []
    })
    assert 'Showing first 20 of 25 files' in summary

    content = 'a' * 10001
    summary = agent._summarize_tool_result('read_file', {
        'success': True,
        'file_path': 'big.txt',
        'content': content,
        'size': len(content)
    })
    assert 'Content truncated' in summary
