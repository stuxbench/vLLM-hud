"""Environment management for vLLM testing."""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add shared code to path
sys.path.insert(0, '/app')

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format='[%(levelname)s] %(asctime)s | %(name)s | %(message)s'
)

def setup_environment():
    """Set up vLLM environment variables."""
    os.environ['PYTHONPATH'] = '/workspace/vllm:/app'
    
    logging.info("Environment initialized for vLLM testing")
    logging.info(f"vLLM version: latest")
    logging.info(f"Working directory: /workspace/vllm")
    logging.info(f"Initial state: baseline branch")

async def main():
    """Initialize the environment and keep it running."""
    setup_environment()
    
    # Keep running
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logging.info("Shutting down environment")

if __name__ == "__main__":
    asyncio.run(main())