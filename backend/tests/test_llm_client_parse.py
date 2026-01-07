from app.core.llm_client import parse_xml_tool_calls


def test_parse_xml_tool_calls_extracts_calls():
    content = (
        'Hello\n'
        '<function=read_file>'
        '<parameter=file_path>README.md</parameter>'
        '</function>\n'
        'Bye'
    )

    cleaned, calls = parse_xml_tool_calls(content)

    assert 'function=read_file' not in cleaned
    assert cleaned.strip() == 'Hello\n\nBye'
    assert calls[0]['function']['name'] == 'read_file'
    assert calls[0]['function']['arguments']['file_path'] == 'README.md'


def test_parse_xml_tool_calls_parses_booleans():
    content = (
        '<function=list_files>'
        '<parameter=directory>.</parameter>'
        '<parameter=recursive>true</parameter>'
        '</function>'
    )

    _cleaned, calls = parse_xml_tool_calls(content)
    assert calls[0]['function']['arguments']['recursive'] is True


def test_parse_xml_tool_calls_removes_orphan_tags():
    content = 'Output</tool_call>'
    cleaned, calls = parse_xml_tool_calls(content)
    assert cleaned == 'Output'
    assert calls == []
