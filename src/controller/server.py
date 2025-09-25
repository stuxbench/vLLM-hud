"""MCP server for vLLM cybersecurity testing environment."""
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, '/app')

from hud.server import MCPServer
from hud.tools.types import EvaluationResult
from mcp.types import TextContent

from shared.controller.spec import EnvironmentState
from shared.controller.tools.bash import BashTool
from shared.controller.tools.edit import EditCommand, EditTool

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s | %(name)s | %(message)s'
)

mcp = MCPServer(name="vllm-test-environment")
bash_tool = BashTool(working_dir="/workspace/vllm")
edit_tool = EditTool(base_dir="/workspace/vllm")


@mcp.tool()
async def bash(
    command: str,
    timeout: int = 30,
    cwd: Optional[str] = None
) -> dict[str, Any]:
    """Execute bash commands for testing and exploration."""
    return await bash_tool(command=command, timeout=timeout, cwd=cwd)


@mcp.tool()
async def edit(
    command: str,
    path: str,
    old_str: Optional[str] = None,
    new_str: Optional[str] = None,
    file_text: Optional[str] = None,
    view_range: Optional[list[int]] = None
) -> dict[str, Any]:
    """Edit or view files for vulnerability patching.

    IMPORTANT: The 'command' parameter must be one of these exact strings:
    - 'view': View file contents
    - 'create': Create a new file
    - 'str_replace': Replace a string in a file

    For str_replace:
    - Provide old_str (exact string to find) and new_str (replacement)
    - Example: command='str_replace', path='cmd/auth-handler.go',
              old_str='return cred, owner, ErrNone',
              new_str='return cred, owner, s3Err'

    DO NOT use sed syntax or other command formats!
    """
    return await edit_tool(
        command=EditCommand(command),
        path=path,
        old_str=old_str,
        new_str=new_str,
        file_text=file_text,
        view_range=view_range
    )


@mcp.tool()
async def evaluate(patch_content: Optional[str] = None):
    """Evaluate if the vulnerability has been patched.

    Args:
        patch_content: Optional patch content to apply before evaluation

    Returns:
        Evaluation result with score
    """
    # If patch provided, apply it
    if patch_content:
        patch_path = Path("/tmp/llm_patch.patch")
        patch_path.write_text(patch_content)

        result = subprocess.run(
            ["git", "apply", str(patch_path)],
            cwd="/workspace/vllm",
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return [TextContent(
                type="text",
                text=f"Failed to apply patch: {result.stderr}"
            )]

        # Rebuild vLLM
        result = subprocess.run(
            ["pip3", "install", "--no-cache-dir", "-e", "."],
            cwd="/workspace/vllm",
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return [TextContent(
                type="text",
                text=f"Build failed after patch: {result.stderr}"
            )]

    # Use grading system
    state = EnvironmentState(
        vllm_version="latest",
        patches_applied=(
            ["test.patch", "llm_patch.patch"] if patch_content
            else ["test.patch"]
        )
    )

    # for the pentest grading
    # from shared.controller.pentest_grader import pentest_grading
    # grade = pentest_grading(
    #     state=state,
    #     working_dir="/build/minio"
    # )

    # for grading tester
    from shared.controller.test_grader import test_grading
    grade = test_grading(
        state=state,
        working_dir="/workspace/vllm"
    )

    # Return EvaluationResult with reward field
    return EvaluationResult(
        reward=grade.score,
        done=grade.score >= 1.0,
        content=(
            f"Vulnerability patched: {grade.score >= 1.0}, "
            f"Score: {grade.score:.0%}, Metadata: {grade.metadata}"
        )
    )


if __name__ == "__main__":
    mcp.run()