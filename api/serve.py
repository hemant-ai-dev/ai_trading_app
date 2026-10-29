"""Run the internal API: python -m api.serve"""

from __future__ import annotations

import os
import threading

import uvicorn

_started = False


def start_background_server() -> None:
    """Optional local FastAPI next to Streamlit. Bind failures are ignored (Cloud has one port)."""
    global _started
    if _started or os.getenv("ANGAD_API_AUTOSTART", "1") != "1":
        return
    _started = True

    try:
        from config.loader import load_settings
        from workers.prediction_scheduler import start as start_scheduler

        start_scheduler(load_settings())
    except Exception:
        # Scheduler failure must never block the UI process.
        pass

    def _run() -> None:
        try:
            uvicorn.run(
                "api.app:app",
                host=os.getenv("ANGAD_API_HOST", "127.0.0.1"),
                port=int(os.getenv("ANGAD_API_PORT", "8765")),
                log_level="warning",
            )
        except Exception:
            return

    threading.Thread(target=_run, daemon=True, name="angad-api").start()


def main() -> None:
    host = os.getenv("ANGAD_API_HOST", "127.0.0.1")
    port = int(os.getenv("ANGAD_API_PORT", "8765"))
    uvicorn.run("api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
