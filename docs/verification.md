# Verification record — 2026-09-29

## Local result

- Python 3.14 / Node 24.18.1 / SAP CLI 2026.19.0 / FastMCP 4.0.10.
- `python -m pytest -q`: **50 passed, 1 skipped**.
- `python -m pip check`: no broken requirements.
- Four MCP schemas and calls exercised with an in-memory MCP client.
- MCP handshake, list_spaces and shutdown exercised over a real stdio subprocess.
- Tests cover OAuth refresh rotation and concurrent caching, secret redaction, environment
  isolation, policy denial, CLI argument generation, process timeout/cleanup, response limits,
  OData pagination/retry, and CSN extraction including cycles and unsupported directions.

## SAP interface verification

- Installed official npm package and verified its version, Node requirements, environment
  option handling, OAuth token request logic, cache precedence and session export format.
- Used SAP Help's documented `spaces list`, `objects <type> list/read` syntax.
- Current package uses `config secrets show` (not the older README's `secrets show`),
  exporting an array of tenant sessions. Server selects the exact configured tenant.
- Actual DEV tenant discovery and payload parsing were verified for the four acceptance
  calls below. Other object types and tenants remain unverified.
- Live testing found that fresh profiles do not register tenant-specific commands until
  `config cache init` completes. The adapter now initializes the temporary profile through
  the official CLI before each read, sharing one timeout budget across both processes.
  Error-level diagnostics are captured for safe classification only, never emitted.

## DEV acceptance — passed

Target: `DEV / BSG_BI / local-tables / T_TEST`, user-based OAuth.

| Step | Status |
|---|---|
| Authenticate as configured DEV user | Passed; OAuth refresh succeeded |
| Find BSG_BI with list_spaces | Passed |
| Find T_TEST with list_objects | Passed |
| Read T_TEST definition with get_object | Passed |
| Extract T_TEST upstream CSN references | Passed; 1 node, 0 edges, not truncated |

Live smoke run started at **2026-09-29 06:48:04 UTC (15:48:04 KST)** and completed with
`success=true`, `mock_mode=false`. It exercised all four tools through the MCP protocol,
using the user's configured DEV OAuth session. No SAP mutation was performed.
The result was saved to the Git-ignored `dev-smoke-result.json`.

The dependency result has `complete=false`: no source/association relationships were found
by the supported CSN extractor. This is not a claim that every possible SAP dependency was
examined. Multi-hop view/model lineage is outside this local-table acceptance result.

To repeat explicitly after completing the README's OAuth setup:

```powershell
# Set DSP_RUN_DEV_INTEGRATION=true in .env first.
.venv\Scripts\python.exe scripts/dev_smoke.py --space BSG_BI --object-type local-tables --technical-name T_TEST --output dev-smoke-result.json
```

The ignored report contains safe statuses, not original definitions or credentials.
An additional real view/analytic-model fixture with known sources is needed to verify
multi-hop dependency behavior beyond a local table's potentially empty upstream set.
