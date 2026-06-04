from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from pdf2md.extractors.page_worker import (
    PageWorkerBatchInput,
    PageWorkerInput,
    PageWorkerResult,
    extract_page_worker,
    extract_page_worker_batch,
)


def effective_page_worker_count(requested_workers: int, page_count: int) -> int:
    """Return a conservative worker count capped by page count and CPU count."""
    if requested_workers <= 1 or page_count <= 1:
        return 1
    cpu_count = os.cpu_count() or requested_workers
    return max(1, min(requested_workers, page_count, cpu_count))


def _chunk_page_worker_inputs(inputs: list[PageWorkerInput], worker_count: int) -> list[list[PageWorkerInput]]:
    if not inputs:
        return []
    chunk_count = max(1, min(worker_count, len(inputs)))
    base_size, remainder = divmod(len(inputs), chunk_count)
    chunks: list[list[PageWorkerInput]] = []
    offset = 0
    for chunk_index in range(chunk_count):
        chunk_size = base_size + (1 if chunk_index < remainder else 0)
        chunk = inputs[offset : offset + chunk_size]
        if chunk:
            chunks.append(chunk)
        offset += chunk_size
    return chunks


def _build_page_worker_batch_input(inputs: list[PageWorkerInput]) -> PageWorkerBatchInput:
    first = inputs[0]
    for worker_input in inputs[1:]:
        if (
            worker_input.pdf_path != first.pdf_path
            or worker_input.password != first.password
            or worker_input.collect_table_candidates != first.collect_table_candidates
        ):
            raise ValueError("Page worker batch inputs must share pdf_path, password, and collection options")
    return PageWorkerBatchInput(
        pdf_path=first.pdf_path,
        pages=tuple(worker_input.page for worker_input in inputs),
        password=first.password,
        collect_table_candidates=first.collect_table_candidates,
    )


def run_page_workers(inputs: list[PageWorkerInput], worker_count: int) -> list[PageWorkerResult]:
    """Run page workers and return results in deterministic page order."""
    if not inputs:
        return []
    if worker_count <= 1:
        return [extract_page_worker(worker_input) for worker_input in inputs]

    results: list[PageWorkerResult] = []
    batches = [_build_page_worker_batch_input(chunk) for chunk in _chunk_page_worker_inputs(inputs, worker_count)]
    with ThreadPoolExecutor(max_workers=min(worker_count, len(batches))) as executor:
        futures = [executor.submit(extract_page_worker_batch, batch) for batch in batches]
        for future in as_completed(futures):
            results.extend(future.result())
    return sorted(results, key=lambda result: result.page)
