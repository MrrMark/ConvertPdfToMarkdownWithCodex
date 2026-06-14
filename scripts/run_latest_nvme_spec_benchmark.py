#!/usr/bin/env python3
from __future__ import annotations

try:
    from scripts.run_latest_nvme_base_benchmark import main
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from run_latest_nvme_base_benchmark import main  # type: ignore[no-redef]


if __name__ == "__main__":
    raise SystemExit(main())
