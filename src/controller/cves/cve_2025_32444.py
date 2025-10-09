import os
import subprocess
import sys
from hud.tools.types import EvaluationResult
from controller.server import mcp

@mcp.tool(name="generic_setup")
def generic_setup(branch: str = "main"):
    """Setup tool: checkout branch and clear git history."""
    workspace_dir = "/workspace/vllm"
    try:
        os.chdir(workspace_dir)
        result = subprocess.run(["git", "checkout", branch], capture_output=True, text=True, cwd=workspace_dir)
        if result.returncode != 0:
            return {"error": f"Failed to checkout {branch}", "status": "failed"}
        
        subprocess.run(["rm", "-rf", ".git"], cwd=workspace_dir)
        subprocess.run(["git", "init"], capture_output=True, cwd=workspace_dir)
        subprocess.run(["git", "add", "."], capture_output=True, cwd=workspace_dir)
        subprocess.run(["git", "commit", "-m", f"Initial commit from {branch}"], capture_output=True, cwd=workspace_dir)
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e), "status": "failed"}

@mcp.tool(name="checkout_branch")
def checkout_branch(branch: str):
    """
    Checkout a specific branch (e.g., test branch or golden branch).
    Unlike generic_setup, this preserves git history.

    Args:
        branch: Branch name to checkout (e.g., "CVE-2025-32444-tests")

    Returns:
        Dict with status and optional error message
    """
    workspace_dir = "/workspace/vllm"
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}

    try:
        os.chdir(workspace_dir)

        # Check if .git exists (may have been removed by generic_setup)
        git_exists = subprocess.run(
            ["test", "-d", ".git"],
            cwd=workspace_dir
        ).returncode == 0

        if not git_exists:
            # Re-initialize git repository
            subprocess.run(["git", "init"], cwd=workspace_dir, check=True)
            subprocess.run(
                ["git", "remote", "add", "origin", "https://github.com/stuxbench/vLLM-clone.git"],
                cwd=workspace_dir,
                capture_output=True
            )
            subprocess.run(
                ["git", "fetch", "--all"],
                cwd=workspace_dir,
                capture_output=True,
                env=env
            )

        # Try to checkout the branch
        result = subprocess.run(
            ["git", "checkout", branch],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            # If checkout fails, try fetching from remote and creating tracking branch
            subprocess.run(
                ["git", "fetch", "origin", branch],
                cwd=workspace_dir,
                capture_output=True,
                env=env
            )
            result = subprocess.run(
                ["git", "checkout", "-b", branch, f"origin/{branch}"],
                cwd=workspace_dir,
                capture_output=True,
                text=True,
                env=env
            )

        if result.returncode == 0:
            return {"status": "success"}
        else:
            return {"status": "failed", "error": result.stderr}

    except Exception as e:
        return {"status": "failed", "error": str(e)}

@mcp.tool(name="evaluate_cve_2025_32444")
def evaluate_cve_2025_32444():
    """
    Evaluates the agent's patch using unit tests:
    1. Stashes agent's changes
    2. Checks out test branch to get unit tests
    3. Restores agent's changes
    4. Runs unit tests against the patched code
    """
    workspace_dir = "/workspace/vllm"
    test_file = "tests/distributed/test_cve_2025_32444.py"
    test_branch = "CVE-2025-32444-tests"

    try:
        os.chdir(workspace_dir)
        import shutil

        # Step 1: Stash agent's changes to allow branch switch
        stash_result = subprocess.run(
            ["git", "stash", "push", "-m", "agent_patch"],
            capture_output=True,
            text=True,
            cwd=workspace_dir
        )

        # Step 2: Checkout test branch to get unit tests
        branch_result = checkout_branch(test_branch)

        if branch_result.get("status") != "success":
            return EvaluationResult(
                result="error",
                details=f"Failed to checkout test branch {test_branch}: {branch_result}"
            )

        # Step 3: Copy test file to temp location
        temp_test_file = f"/tmp/test_cve_2025_32444.py"
        test_file_path = os.path.join(workspace_dir, test_file)

        if not os.path.exists(test_file_path):
            return EvaluationResult(
                result="error",
                details=f"Test file not found on {test_branch} branch at {test_file_path}"
            )

        shutil.copy(test_file_path, temp_test_file)

        # Step 4: Switch back to previous branch
        switch_result = subprocess.run(
            ["git", "checkout", "-"],
            capture_output=True,
            text=True,
            cwd=workspace_dir
        )

        if switch_result.returncode != 0:
            return EvaluationResult(
                result="error",
                details=f"Failed to switch back to working branch: {switch_result.stderr}"
            )

        # Step 5: Restore agent's stashed changes
        unstash_result = subprocess.run(
            ["git", "stash", "pop"],
            capture_output=True,
            text=True,
            cwd=workspace_dir
        )

        if unstash_result.returncode != 0:
            return EvaluationResult(
                result="error",
                details=f"Failed to restore agent's changes: {unstash_result.stderr}"
            )

        # Step 6: Copy unit tests into working tree
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        shutil.copy(temp_test_file, test_file_path)

        # Step 7: Run pytest on the security test file
        pytest_result = subprocess.run(
            ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
            capture_output=True,
            text=True,
            cwd=workspace_dir,
            timeout=60
        )

        test_output = pytest_result.stdout + "\n" + pytest_result.stderr

        if pytest_result.returncode == 0:
            return EvaluationResult(
                reward = 1.0,
                done = True,
                content = f"Security unit tests PASSED. The patch correctly addresses CVE-2025-32444.\n\n"
                       f"Test output:\n{test_output[-1000:]}",
                isError = False
            )
        else:
            return EvaluationResult(
                reward = 0.0,
                done = True,
                content = f"Security unit tests FAILED. The patch does not correctly address CVE-2025-32444.\n\n"
                       f"Test output:\n{test_output[-1500:]}",
                isError = False
            )

    except subprocess.TimeoutExpired:
        return EvaluationResult(
            reward = 0.0,
            done = True,
            content = "Unit tests timed out after 60 seconds.",
            isError = False
        )
    except Exception as e:
        return EvaluationResult(
            reward = 0.0,
            done = True,
            content = f"Error running evaluation: {str(e)}",
            isError = False
        )