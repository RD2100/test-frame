# Negative Test Fixtures -- RD2100 Agent Runtime v2

> Batch D3, 2026-05-27
> 43 deliberately-broken test fixtures for reviewer detection capability testing.

## Purpose

This directory contains negative acceptance test cases. Each fixture describes a fake report that contains one or more violations of RD2100 Agent Runtime v2 rules, contracts, policies, or gates. A competent reviewer (human or agent) must detect these violations and reject the report.

These fixtures test the reviewer, not the executor. The executor produces these kinds of violations (intentionally in test, or inadvertently in production). The reviewer must catch them.

## Usage

Each `.json` file is a self-contained test case with these fields:

| Field | Description |
|-------|-------------|
| `test_id` | Unique identifier (NEG-001 through NEG-043) |
| `scenario` | Human-readable description of the violation being tested |
| `input_report_features` | Description of what the fake report contains -- the violation details |
| `expected_gate_decision` | What the reviewer should decide (must NOT be "pass") |
| `expected_findings` | Array of specific violations the reviewer should identify |
| `related_invariant` | Reference to the invariant(s) this test maps to |
| `hard_stop` | Whether this should be a P0 hard stop |

Paper/WriteLab reviewer-pack fixtures may also include these extension fields:

| Field | Description |
|-------|-------------|
| `domain` | Domain-specific fixture group, such as `paper_writelab_redacted_reviewer_pack` or `paper_writelab_business_validation` |
| `gate_level` | P0/P1/P2/P3 severity expected for the reviewer gate |
| `canary_tags` | Canary categories covered by the fixture |
| `contract_surface` | Contracts or schemas the fixture is meant to exercise |
| `test_frame_boundary` | Explicit reminder that test-frame produces verification evidence only, not final acceptance |

## How to Use These Fixtures

1. **For reviewer agents**: Read a fixture, review the `input_report_features` as if it were a real execution report, and produce a gate decision. Compare your decision against `expected_gate_decision`. Your findings should match `expected_findings`.

2. **For human reviewers**: These are training and calibration cases. Run through them to ensure your judgment aligns with the invariant definitions.

3. **For automated gate validation (future)**: These fixtures define the expected behavior of an automated gate checker. Parse the fixture, feed `input_report_features` to the checker, verify output matches `expected_gate_decision` and `expected_findings`.

## Fixture Coverage Map

| Category | Count | Fixtures |
|----------|-------|----------|
| Missing evidence | 3 | NEG-001, NEG-019, NEG-021 |
| Fake green / misrepresentation | 3 | NEG-002, NEG-013, NEG-020 |
| Forbidden tool usage | 7 | NEG-004, NEG-005, NEG-006, NEG-007, NEG-026, NEG-027, NEG-028 |
| Contract violations | 4 | NEG-008, NEG-014, NEG-015, NEG-016 |
| Self-approval / exec-review separation | 3 | NEG-011, NEG-030, NEG-013 |
| Security vulnerabilities | 3 | NEG-009, NEG-023, NEG-024 |
| Scope control violations | 2 | NEG-017, NEG-018 |
| Phase boundary violations | 1 | NEG-022 |
| Report structure violations | 2 | NEG-012, NEG-029 |
| Quality / completeness | 1 | NEG-025 |
| Source-of-truth / architecture | 1 | NEG-003 |
| Gate result integrity | 1 | NEG-010 |
| Paper/WriteLab redacted reviewer pack | 8 | NEG-031, NEG-032, NEG-033, NEG-034, NEG-035, NEG-036, NEG-037, NEG-038 |
| Paper/WriteLab business validation | 5 | NEG-039, NEG-040, NEG-041, NEG-042, NEG-043 |

## Hard Stop Distribution

| Hard Stop | Count |
|-----------|-------|
| true (P0) | 22 |
| false (P1/P2/P3) | 8 |
| paper extension true (P0) | 7 |
| paper extension false (P1/P2) | 6 |

## Relationship to Invariants

These fixtures collectively cover all key invariants from:
- `integration-contracts.md` (8 core contracts)
- `verification-gates.md` (P0-P3 gate hierarchy)
- `tool-policy.md` (Phase 0-5 permitted/forbidden actions)
- `review.md` (6 review rules)

## Paper/WriteLab Reviewer-Pack Extension

NEG-031 through NEG-038 cover paper/WriteLab/redacted reviewer pack canaries for:

- no-tests-run reported as verification success;
- failed privacy gate reported as green;
- generated summary treated as final verdict;
- artifact path outside the approved root;
- token-like value in stdout or evidence;
- raw paragraph text inside a redacted pack;
- `human_required` promoted to PASS;
- summary-only pack missing hash, manifest, and boundary fields.

These fixtures remain reviewer detection inputs. test-frame may produce verification evidence
and reviewer calibration inputs, but it must not produce final paper acceptance, paper quality
verdicts, or live WriteLab success claims.

NEG-039 through NEG-043 extend the paper/WriteLab coverage to business-capability
validation canaries using synthetic/offline evidence only:

- missing command-chain evidence for reproducibility;
- summary generation reported as offline production-path validation;
- reviewer or audit zip treated as final acceptance;
- offline handoff integrity missing manifest and hash chain;
- incomplete synthetic evidence pack missing artifact, hash, gate, and boundary fields.

These fixtures are reviewer detection inputs. They do not execute live WriteLab,
external runtimes, H5, MiniApp, MeterSphere, cloud device, or Android capability.
