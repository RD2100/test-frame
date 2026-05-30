# -*- coding: utf-8 -*-
"""Canonical TestResult schema for test-frame.

Defines the six-state status model, TypedDict structures for normalized
test results, and the contract between wrappers/normalizers and downstream
consumers (gate, report, evidence, attribution).

Schema version: test-frame.canonical.v1
"""

from typing import Any, Literal, TypedDict

# ---- Canonical Status ----

CanonicalStatus = Literal[
    "passed",     # 测试完成，所有断言通过
    "failed",     # 测试运行完成，至少一个断言失败
    "skipped",    # 主动跳过（配置、标记、feature flag）
    "error",      # 工具或执行链路失败，无法可信评估测试结果
    "blocked",    # 前置条件不满足，测试未能真正启动
    "cancelled",  # 人工取消、CI取消、任务中断
]

VALID_STATUSES: set[str] = {
    "passed",
    "failed",
    "skipped",
    "error",
    "blocked",
    "cancelled",
}

# ---- Evidence Types ----

EvidenceType = Literal[
    "screenshot",
    "video",
    "trace",
    "html_report",
    "json_report",
    "xml_report",
    "log",
    "har",
    "coverage",
    "other",
]

# ---- Error Types ----

ErrorType = Literal[
    "TEST_ASSERTION_FAILED",
    "TOOL_PROCESS_ERROR",
    "TOOL_TIMEOUT",
    "PARSE_ERROR",
    "CONFIG_ERROR",
    "AUTH_ERROR",
    "RESOURCE_UNAVAILABLE",
    "UPSTREAM_API_ERROR",
    "CANCELLED_BY_USER",
    "UNKNOWN_ERROR",
]

# ---- Sub-structures ----

class ToolInfo(TypedDict):
    name: str
    display_name: str
    adapter_type: str
    version: str | None
    contract_ref: str | None


class SuiteInfo(TypedDict):
    name: str
    type: str          # "unit" | "api" | "e2e" | "mobile" | "monitoring" | "unknown"
    status: str        # CanonicalStatus
    started_at: str | None
    ended_at: str | None
    duration_ms: int | None


class Summary(TypedDict, total=False):
    total: int
    passed: int
    failed: int
    skipped: int
    error: int
    blocked: int
    cancelled: int
    test_pass_rate: float | None
    test_pass_rate_basis: str       # "executed_tests" or "all_tests"
    duration_ms: int | None


class ToolStats(TypedDict, total=False):
    status: str        # CanonicalStatus
    total: int
    passed: int
    failed: int
    skipped: int
    error: int
    blocked: int
    cancelled: int
    duration_ms: int | None


class TestCaseResult(TypedDict, total=False):
    test_id: str
    name: str
    full_name: str
    file: str | None
    line: int | None
    status: str        # CanonicalStatus
    raw_status: str | None
    duration_ms: int | None
    started_at: str | None
    ended_at: str | None
    attempt: int
    retry: int
    tags: list[str]
    message: str | None
    trace: str | None
    evidence_refs: list[str]


class QualitySignal(TypedDict, total=False):
    name: str
    type: str           # "count" | "rate" | "duration" | "boolean" | "score"
    value: int | float | bool | str
    unit: str | None
    status: str         # CanonicalStatus
    threshold: dict | None
    source: str
    stage: str


class QualityIssue(TypedDict, total=False):
    issue_id: str
    source: str
    title: str
    severity: str
    status: str
    count: int
    affected_users: int | None
    first_seen: str | None
    last_seen: str | None
    url: str | None
    fingerprint: str | None
    evidence_refs: list[str]
    raw_ref: str | None


class NormalizedError(TypedDict, total=False):
    error_id: str
    type: str           # ErrorType
    severity: str
    message: str
    tool: str
    stage: str
    test_id: str | None
    retryable: bool
    raw_status: str | None
    raw_ref: str | None


class EvidenceFile(TypedDict, total=False):
    evidence_id: str
    type: str           # EvidenceType
    path: str
    name: str | None
    mime_type: str | None
    size_bytes: int | None
    related_test_id: str | None
    related_issue_id: str | None


class QualityEvaluation(TypedDict, total=False):
    gate_profile: str
    gate_passed: bool
    gate_pass_rate: float | None
    gate_pass_rate_basis: str
    blocked_behavior: str
    error_behavior: str
    cancelled_behavior: str
    metrics: dict[str, dict]


class NormalizeContext(TypedDict, total=False):
    run_id: str
    stage: str
    tool_name: str
    suite_name: str | None
    contract_ref: str | None
    adapter_type: str | None
    environment: dict[str, Any] | None


class RawResultSource(TypedDict, total=False):
    kind: str           # "wrapper_dict" | "playwright_json" | "junit_xml" | ...
    payload: Any
    path: str | None


# ---- Top-level CanonicalTestResult ----

class CanonicalTestResult(TypedDict, total=False):
    schema_version: str
    result_id: str
    run_id: str
    stage: str
    tool: ToolInfo
    suite: SuiteInfo
    status: str         # CanonicalStatus
    summary: Summary
    tool_stats: dict[str, ToolStats]
    tests: list[dict[str, Any]]
    signals: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    quality: QualityEvaluation
    errors: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    environment: dict[str, Any]
    source: dict[str, Any]
    metadata: dict[str, Any]
