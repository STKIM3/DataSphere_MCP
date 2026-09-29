# AGENTS.md

## 1. Project Overview

### Project Name

`datasphere-mcp`

### Objective

Build a dedicated Model Context Protocol (MCP) server for SAP Datasphere.

The MCP server allows AI agents such as Codex, Claude, or other MCP-compatible clients to safely inspect, operate, and eventually modify SAP Datasphere environments.

The server must abstract SAP Datasphere CLI and supported REST/OData APIs behind strongly typed MCP tools.

Primary architecture:

```text
MCP Client
   |
   | MCP
   v
Datasphere MCP Server
   |
   +-- Tool Layer
   |
   +-- Service Layer
   |
   +-- Adapter Layer
   |     |
   |     +-- Datasphere CLI Adapter
   |     +-- REST API Adapter
   |     +-- OData Adapter
   |
   +-- Authentication Layer
         |
         +-- OAuth Provider
         +-- Token Cache
         +-- Environment Configuration
   |
   v
SAP Datasphere
```

This project is ONLY responsible for SAP Datasphere access and control.

The following are explicitly out of scope:

- Ontology
- Knowledge Graph
- RDF
- OWL
- SPARQL
- GraphRAG
- S/4HANA business semantics
- Business-domain reasoning
- SAC automation
- Browser automation

These capabilities may be integrated through separate MCP servers in the future.

---

# 2. Core Design Principles

The project MUST follow these principles.

## 2.1 MCP tools represent business-safe Datasphere operations

Do NOT expose arbitrary shell execution.

Forbidden:

```text
execute_cli(command: string)
run_shell(command: string)
execute_bash(command: string)
```

Preferred:

```text
list_objects()
get_object()
get_dependencies()
get_task_log()
run_task_chain()
create_object()
update_object()
delete_object()
```

The LLM must never construct raw shell commands.

---

## 2.2 Separate MCP tools from SAP implementation

MCP tools MUST NOT directly call subprocess, HTTP APIs, or OAuth endpoints.

Required architecture:

```text
MCP Tool
   |
   v
Service
   |
   v
Adapter
   |
   +-- CLI
   +-- REST
   +-- OData
```

Example:

```text
get_object
    |
    v
ObjectService
    |
    v
DatasphereCLIAdapter
    |
    v
@sap/datasphere-cli
```

This separation is mandatory.

---

## 2.3 Prefer official SAP interfaces

Use interfaces in this priority order:

1. SAP Datasphere supported REST APIs
2. SAP Datasphere supported OData APIs
3. SAP Datasphere CLI
4. Other documented SAP interfaces

Do NOT use undocumented internal browser APIs unless explicitly approved.

Do NOT automate the Datasphere browser UI.

---

# 3. Technology Stack

Primary language:

```text
Python 3.12+
```

MCP framework:

```text
FastMCP
```

Configuration:

```text
pydantic-settings
```

HTTP client:

```text
httpx
```

Data validation:

```text
Pydantic
```

Testing:

```text
pytest
pytest-asyncio
```

CLI integration:

```text
asyncio.create_subprocess_exec
```

Do NOT use:

```text
shell=True
os.system()
subprocess(..., shell=True)
eval()
exec()
```

---

# 4. Project Structure

Use the following structure.

```text
datasphere-mcp/
|
+-- src/
|   +-- datasphere_mcp/
|       |
|       +-- server.py
|       +-- config.py
|       +-- exceptions.py
|       |
|       +-- tools/
|       |   +-- __init__.py
|       |   +-- objects.py
|       |   +-- dependencies.py
|       |   +-- tasks.py
|       |   +-- flows.py
|       |   +-- spaces.py
|       |
|       +-- services/
|       |   +-- __init__.py
|       |   +-- object_service.py
|       |   +-- dependency_service.py
|       |   +-- task_service.py
|       |   +-- flow_service.py
|       |   +-- space_service.py
|       |
|       +-- adapters/
|       |   +-- __init__.py
|       |   +-- cli.py
|       |   +-- rest.py
|       |   +-- odata.py
|       |
|       +-- auth/
|       |   +-- __init__.py
|       |   +-- oauth.py
|       |   +-- token_cache.py
|       |
|       +-- models/
|           +-- __init__.py
|           +-- objects.py
|           +-- dependencies.py
|           +-- tasks.py
|           +-- common.py
|
+-- tests/
|   +-- unit/
|   +-- integration/
|
+-- scripts/
|
+-- .env.example
+-- .gitignore
+-- pyproject.toml
+-- README.md
+-- AGENTS.md
```

Keep files focused.

Avoid large modules containing unrelated responsibilities.

---

# 5. Environment Model

The MCP server must support multiple Datasphere environments.

Initial environments:

```text
DEV
QAS
PRD
```

Environment selection must be explicit.

Example MCP call:

```text
get_object(
    environment="DEV",
    space="SALES",
    object_type="analytic-models",
    technical_name="AM_SALES"
)
```

Never silently default write operations to PRD.

---

# 6. Authentication

## 6.1 Authentication model

Authentication must be isolated from MCP tools.

Preferred production authentication:

```text
OAuth 2.0
Technical User / Service Credential
```

Development may support user-based OAuth when required.

Architecture:

```text
Datasphere MCP
     |
     v
AuthProvider
     |
     +-- obtain token
     +-- cache token
     +-- refresh token when required
     |
     v
Datasphere
```

---

## 6.2 Secrets

Secrets MUST NOT appear in:

- MCP tool parameters
- MCP responses
- logs
- exception messages
- source code
- Git commits

Forbidden tool design:

```text
get_object(
    client_id,
    client_secret,
    space,
    object
)
```

Correct design:

```text
get_object(
    environment,
    space,
    object_type,
    technical_name
)
```

Credentials are resolved internally from environment configuration.

---

## 6.3 Environment configuration

Example:

```text
DSP_DEV_BASE_URL=
DSP_DEV_TOKEN_URL=
DSP_DEV_CLIENT_ID=
DSP_DEV_CLIENT_SECRET=

DSP_QAS_BASE_URL=
DSP_QAS_TOKEN_URL=
DSP_QAS_CLIENT_ID=
DSP_QAS_CLIENT_SECRET=

DSP_PRD_BASE_URL=
DSP_PRD_TOKEN_URL=
DSP_PRD_CLIENT_ID=
DSP_PRD_CLIENT_SECRET=
```

`.env` MUST be excluded from Git.

Provide `.env.example` without real credentials.

---

# 7. Authorization Policy

Authentication and authorization are separate concerns.

Even when SAP credentials permit an operation, the MCP server may reject it.

Initial policy:

| Environment | Read | Execute | Create/Update | Delete |
|---|---|---|---|---|
| DEV | Allow | Allow | Allow | Guarded |
| QAS | Allow | Allow | Guarded | Deny |
| PRD | Allow | Guarded | Deny | Deny |

"Guarded" means the operation requires an explicit confirmation mechanism or policy approval.

Never bypass this policy.

---

# 8. Tool Risk Levels

Every MCP tool must have a risk classification.

## READ

No state change.

Examples:

```text
list_spaces
list_objects
get_object
get_dependencies
get_task_status
get_task_log
```

## EXECUTE

Starts or controls an existing process.

Examples:

```text
run_task_chain
run_replication_flow
retry_task
cancel_task
```

## WRITE

Changes Datasphere metadata.

Examples:

```text
create_object
update_object
```

## DESTRUCTIVE

Deletes or irreversibly modifies resources.

Examples:

```text
delete_object
```

Tool risk metadata should be represented internally whenever practical.

---

# 9. MVP Scope

Implement READ capabilities first.

MVP tools:

```text
list_spaces
list_objects
get_object
get_dependencies
get_task_status
get_task_log
```

Do NOT implement write operations until READ functionality is stable and tested.

---

# 10. Phase 2 Scope

After MVP validation, implement operational tools.

```text
run_task_chain
run_replication_flow
retry_task
cancel_task
```

These tools must validate:

```text
environment
space
technical_name
operation
```

before execution.

---

# 11. Phase 3 Scope

Only after Phase 2 is stable, implement:

```text
create_object
update_object
delete_object
```

Requirements:

- strict Pydantic validation
- environment policy enforcement
- structured audit logging
- no arbitrary file paths
- no arbitrary CLI options
- no arbitrary command execution
- destructive operations guarded
- PRD mutation denied by default

---

# 12. Object Model

Create an enum for supported Datasphere object types.

Example:

```python
class DatasphereObjectType(str, Enum):
    LOCAL_TABLE = "local-tables"
    REMOTE_TABLE = "remote-tables"
    VIEW = "views"
    DATA_FLOW = "data-flows"
    REPLICATION_FLOW = "replication-flows"
    TRANSFORMATION_FLOW = "transformation-flows"
    TASK_CHAIN = "task-chains"
    ANALYTIC_MODEL = "analytic-models"
    BUSINESS_ENTITY = "business-entities"
    FACT_MODEL = "fact-models"
    CONSUMPTION_MODEL = "consumption-models"
    DATA_ACCESS_CONTROL = "data-access-controls"
    PACKAGE = "packages"
```

Do not accept arbitrary object type strings when a known enum can be used.

Verify actual support against the installed/current Datasphere CLI before implementation.

---

# 13. CLI Adapter

The CLI adapter is the only layer allowed to invoke the Datasphere CLI.

Example responsibility:

```python
class DatasphereCLIAdapter:

    async def list_objects(...):
        ...

    async def read_object(...):
        ...

    async def get_dependencies(...):
        ...

    async def run_task_chain(...):
        ...
```

Never expose a generic:

```python
execute(command: str)
```

to MCP tools.

An internal low-level executor may exist but must accept a list of validated arguments.

Example:

```python
async def _execute(args: list[str]):
    process = await asyncio.create_subprocess_exec(
        "datasphere",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
```

Never concatenate user-controlled values into shell strings.

---

# 14. REST Adapter

Create a separate REST adapter.

Example:

```python
class DatasphereRESTAdapter:

    async def get(...):
        ...

    async def post(...):
        ...
```

Responsibilities:

- OAuth token handling
- HTTP timeout
- retry policy
- SAP error normalization
- response parsing

Do not put business logic into the REST adapter.

---

# 15. OData Adapter

OData access must be isolated.

Responsibilities:

```text
metadata retrieval
entity retrieval
query parameters
pagination
```

Prevent unrestricted OData queries from becoming an arbitrary query execution interface.

Apply limits to:

```text
$top
pagination
response size
```

where appropriate.

---

# 16. Service Layer

Services decide HOW an operation should be performed.

Example:

```text
ObjectService
     |
     +-- REST Adapter
     |
     +-- CLI Adapter
```

The MCP tool should not care whether SAP CLI or REST was used.

Example:

```python
result = await object_service.get_object(...)
```

not:

```python
result = await cli.execute(...)
```

This allows future migration from CLI to REST without changing MCP contracts.

---

# 17. MCP Tool Contract

Tools must use explicit typed parameters.

Example:

```python
@mcp.tool()
async def get_object(
    environment: Environment,
    space: str,
    object_type: DatasphereObjectType,
    technical_name: str,
) -> DatasphereObject:
    ...
```

Avoid generic dictionary inputs unless SAP payloads require them.

Responses should also use structured models.

---

# 18. Standard Response Model

Prefer structured results.

Example:

```json
{
  "success": true,
  "environment": "DEV",
  "space": "SALES",
  "object_type": "analytic-models",
  "technical_name": "AM_SALES",
  "data": {},
  "warnings": []
}
```

Errors should be normalized.

Example:

```json
{
  "success": false,
  "error": {
    "code": "OBJECT_NOT_FOUND",
    "message": "Datasphere object was not found."
  }
}
```

Never return raw OAuth errors containing secrets.

---

# 19. Dependency Analysis

`get_dependencies` is a first-class MCP capability.

It should eventually support:

```text
UPSTREAM
DOWNSTREAM
BOTH
```

Example:

```text
get_dependencies(
    environment="DEV",
    space="SALES",
    object_type="analytic-models",
    technical_name="AM_SALES",
    direction="UPSTREAM"
)
```

Return a normalized dependency graph rather than raw CLI text whenever possible.

Example:

```text
AM_SALES
   |
   +-- V_SALES_FACT
   |      |
   |      +-- LT_BILLING
   |
   +-- D_CUSTOMER
   |
   +-- D_PRODUCT
```

The MCP server retrieves and normalizes metadata.

It does NOT perform ontology reasoning.

---

# 20. Object Inspection

`get_object` should preserve enough original SAP metadata for AI-assisted analysis.

Where available preserve:

```text
technical name
business name
object type
space
columns
measures
dimensions
associations
sources
filters
calculated columns
semantic usage
CSN / JSON metadata
```

Do not unnecessarily transform or discard SAP metadata.

---

# 21. Logging

Use structured logging.

Log:

```text
timestamp
environment
tool
operation
space
object_type
technical_name
duration
success/failure
```

Never log:

```text
access_token
refresh_token
client_secret
password
authorization header
full credential payload
```

Write operations must produce audit events.

---

# 22. Error Handling

Define project-specific exceptions.

Examples:

```text
DatasphereError
AuthenticationError
AuthorizationError
ObjectNotFoundError
CLIExecutionError
APIError
ValidationError
PolicyViolationError
```

Adapters translate SAP-specific errors.

Services translate adapter errors into domain errors.

MCP tools return safe structured errors.

---

# 23. Timeout and Retry

All external operations require timeouts.

HTTP:

```text
connect timeout
read timeout
total operation timeout
```

CLI:

```text
process timeout
```

Retries are allowed only for appropriate transient failures.

Do NOT blindly retry state-changing operations.

---

# 24. Input Validation

Validate identifiers before passing them to adapters.

Examples:

```text
environment
space
technical_name
object_type
```

Reject suspicious input containing shell-control patterns where applicable.

Validation is defense-in-depth and does not replace safe subprocess invocation.

---

# 25. File Handling

Datasphere CLI may require temporary JSON/CSN files.

Rules:

- use OS temporary directories
- generate filenames internally
- do not accept arbitrary filesystem paths from MCP clients
- remove temporary files after operation
- never allow directory traversal
- validate JSON before passing it to CLI

Forbidden:

```text
create_object(file_path="/etc/...")
```

Preferred:

```text
create_object(
    environment,
    space,
    object_type,
    technical_name,
    definition
)
```

The server creates the temporary file itself.

---

# 26. Testing Strategy

Every service and adapter must have tests.

## Unit tests

Mock:

```text
CLI process
HTTP requests
OAuth provider
```

Test:

```text
parameter validation
command generation
policy enforcement
response parsing
error normalization
```

## Integration tests

Integration tests may connect only to a designated Datasphere DEV environment.

Never run destructive integration tests against QAS or PRD.

---

# 27. Mock Mode

Provide a mock mode for local development.

Example:

```text
DSP_MOCK_MODE=true
```

Mock mode should allow MCP tools to operate without a real Datasphere tenant.

Provide representative fixture data for:

```text
spaces
views
analytic models
dependencies
task logs
```

This is important for automated tests and agent development.

---

# 28. Security Requirements

Treat all MCP input as untrusted.

Never:

```text
execute arbitrary commands
execute arbitrary SQL
expose secrets
return OAuth tokens
accept arbitrary file paths
disable TLS verification
bypass environment policies
allow unrestricted PRD mutation
```

Security restrictions take precedence over convenience.

---

# 29. Production Safety

PRD must default to read-only.

A configuration such as:

```text
DSP_PRD_ALLOW_EXECUTE=false
DSP_PRD_ALLOW_WRITE=false
DSP_PRD_ALLOW_DELETE=false
```

should be supported.

Changing these defaults must require explicit server-side configuration.

An MCP client cannot override them.

---

# 30. Development Workflow

Implement features in this order.

### Phase 0 — Foundation

Implement:

```text
FastMCP server
configuration
environment model
logging
exceptions
mock mode
```

### Phase 1 — Authentication

Implement:

```text
OAuth provider
token acquisition
token cache
secret masking
```

### Phase 2 — Read Adapter

Implement:

```text
CLI adapter
REST adapter
```

Start with only required operations.

### Phase 3 — Read Tools

Implement:

```text
list_spaces
list_objects
get_object
get_dependencies
get_task_status
get_task_log
```

### Phase 4 — Operational Tools

Implement:

```text
run_task_chain
run_replication_flow
retry_task
cancel_task
```

### Phase 5 — Write Tools

Implement:

```text
create_object
update_object
```

### Phase 6 — Destructive Tools

Implement only after explicit approval:

```text
delete_object
```

---

# 31. First Milestone

The first usable milestone is complete when an MCP client can perform:

```text
"DEV Datasphere의 SALES Space 객체를 보여줘."

"AM_SALES Analytic Model 정의를 가져와."

"AM_SALES의 upstream dependency를 보여줘."

"이 모델이 어떤 View와 Local Table에 의존하는지 확인해줘."

"최근 Task 실행 상태를 확인해줘."
```

without exposing credentials or allowing arbitrary command execution.

---

# 32. Definition of Done

A feature is complete only when:

- MCP tool schema is typed
- input validation exists
- authorization policy is applied
- service layer is used
- adapter is isolated
- errors are normalized
- secrets are masked
- unit tests exist
- README usage is updated

Do not consider an MCP tool complete merely because it successfully calls the Datasphere CLI.

---

# 33. Coding Rules for AI Agents

When modifying this repository:

1. Read this `AGENTS.md` first.
2. Inspect existing architecture before adding files.
3. Preserve Tool → Service → Adapter separation.
4. Prefer small focused changes.
5. Do not introduce new dependencies without justification.
6. Do not expose generic shell execution.
7. Do not place authentication logic inside MCP tools.
8. Do not hardcode SAP tenant information.
9. Do not hardcode credentials.
10. Do not weaken PRD protection.
11. Add or update tests with every behavior change.
12. Verify SAP CLI syntax against the installed/current CLI instead of guessing.
13. Prefer documented SAP interfaces.
14. Preserve backward compatibility of MCP tool contracts where practical.
15. If an SAP capability is uncertain, mark it unsupported or TODO rather than inventing behavior.

---

# 34. Architectural Boundary

The responsibility of this server ends at SAP Datasphere control.

```text
                    AI Agent
                        |
                        v
                Datasphere MCP
                        |
             +----------+----------+
             |          |          |
            CLI        REST       OData
             |          |          |
             +----------+----------+
                        |
                        v
                 SAP Datasphere
```

Future systems may consume this MCP server, including ontology, semantic reasoning, BI engineering, or agent orchestration systems.

Those concerns must NOT be implemented inside this repository.

The goal of this project is:

> Provide a secure, predictable, typed, and automation-friendly MCP interface to SAP Datasphere.