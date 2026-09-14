"""Public report contract for isolated conversion benchmarks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BenchmarkSample(BaseModel):
    model_config = ConfigDict(extra="allow")
    phase: Literal["cold", "warm"]
    index: int = Field(ge=0, le=5)
    status: Literal["success", "partial_success", "failed"]
    convert_export_write_seconds: float = Field(ge=0)


class BenchmarkEngine(BaseModel):
    model_config = ConfigDict(extra="allow")
    engine: Literal["native", "docling", "pymupdf", "marker"]
    status: Literal["success", "incomplete", "unavailable", "failed"]
    runs: list[BenchmarkSample] = Field(default_factory=list)
    input_identity_verified: bool
    process_wall_seconds: float = Field(ge=0)


class FairBenchmarkReport(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["fair_conversion_benchmark"] = "fair_conversion_benchmark"
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    slice_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_pages: list[int]
    input_preparation_seconds: float = Field(ge=0)
    method: dict
    engines: list[BenchmarkEngine]
    timing_samples_complete: bool
    feature_parity_assumed: Literal[False] = False
