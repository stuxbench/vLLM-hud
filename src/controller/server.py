"""MCP server for vLLM CVE-2025-32444 vulnerability testing."""
import sys
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import importlib
import pkgutil

# Ensure 'controller.server' resolves to this module when run via `-m src.controller.server`
sys.modules.setdefault('controller.server', sys.modules[__name__])

sys.path.insert(0, '/app')

from hud.server import MCPServer
from mcp.types import TextContent

from hud.tools.bash import BashTool
from hud.tools.edit import EditTool

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s | %(name)s | %(message)s'
)

mcp = MCPServer(name="vllm-cve-2025-32444")
bash_tool = BashTool()
edit_tool = EditTool()
mcp.add_tool(bash_tool)
mcp.add_tool(edit_tool)

def load_cve_tools() -> None:
    """Dynamically import all modules in controller.cves so their @mcp.tool functions register."""
    import importlib
    import pkgutil
    
    logging.info("Starting CVE tools loading...")
    
    # Add src directory to path to allow controller.cves import
    src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)))
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
        logging.info(f"Added {src_path} to sys.path")
    
    try:
        import controller.cves as cves_pkg
        logging.info(f"Successfully imported controller.cves from {cves_pkg.__path__}")
    except Exception as e:
        logging.exception(f"No CVE tools package 'controller.cves' found or failed to import: {e}")
        return
    if not hasattr(cves_pkg, "__path__"):
        logging.info("'controller.cves' is not a package; skipping dynamic tool loading.")
        return
    
    modules_found = list(pkgutil.iter_modules(cves_pkg.__path__, cves_pkg.__name__ + "."))
    logging.info(f"Found {len(modules_found)} CVE modules: {[m.name for m in modules_found]}")
    
    for module_info in modules_found:
        module_name = module_info.name
        try:
            importlib.import_module(module_name)
            logging.info(f"Successfully loaded CVE tools module: {module_name}")
        except Exception as exc:
            logging.exception(f"Failed to load CVE tools module '{module_name}': {exc}")
    
    logging.info("CVE tools loading completed.")


if __name__ == "__main__":
    load_cve_tools()
    mcp.run()