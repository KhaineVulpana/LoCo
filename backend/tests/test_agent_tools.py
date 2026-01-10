import pytest
from pathlib import Path

from app.tools.agent_tools import ProposeDiffTool


@pytest.mark.asyncio
async def test_propose_diff_tool_generates_patch(tmp_path):
    (tmp_path / "example.txt").write_text("alpha\nbeta\n", encoding="utf-8")

    tool = ProposeDiffTool(str(tmp_path))
    result = await tool.execute(
        file_path="example.txt",
        new_content="alpha\ngamma\n"
    )

    assert result["success"] is True
    assert result["diff"]
    assert "example.txt" in result["diff"]
