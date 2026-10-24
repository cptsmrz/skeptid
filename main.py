"""Root application entrypoint for zero-config ASGI deployment (Render, Railway, Fly.io)."""

import sys
from pathlib import Path

# Add src/ directory to Python system path so skeptid is always resolvable
src_path = str(Path(__file__).resolve().parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from skeptid.main import app, create_app  # noqa: E402, F401

if __name__ == "__main__":
    import os
    import uvicorn

    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, proxy_headers=True, forwarded_allow_ips="*")
