from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from pdf2md.extractors.page_worker import PageWorkerInput, PageWorkerResult, extract_page_worker


def effective_page_worker_count(requested_workers: int, page_count: int) -> int:
    """Return a conservative worker count capped by page count and CPU count."""
    if requested_workers <= 1 or page_count <= 1:
        return 1
    cpu_count = os.cpu_count() or requested_workers
    return max(1, min(requested_workers, page_count, cpu_count))


def run_page_workers(inputs: list[PageWorkerInput], worker_count: int) -> list[PageWorkerResult]:
    """Run page workers and return results in deterministic page order."""
    if worker_count <= 1:
        return [extract_page_worker(worker_input) for worker_input in inputs]

    results: list[PageWorkerResult] = []
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        future_to_page = {executor.submit(extract_page_worker, worker_input): worker_input.page for worker_input in inputs}
        for future in as_completed(future_to_page):
            results.append(future.result())
    return sorted(results, key=lambda result: result.page)
