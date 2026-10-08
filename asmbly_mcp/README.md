# Asmbly MCP server

Lets Claude answer Asmbly questions. Today it does one thing: troubleshoot why a member can't get in the door. Ask Claude *"Check door access for jane@example.com"* and it returns a checklist covering Neon (membership, suspension, waiver, orientation) and Alta Open (account, groups, credential).

It is **read only**. It looks things up in Neon and Alta Open and never changes them.

Everything for the server lives in this folder: code, dependencies, tests, container image and AWS infrastructure. It is separate from the door sync in the rest of the repo, apart from one deliberate link (see [Shared code](#shared-code)).

## Two ways to run it

| | On your own computer | Hosted for the whole org |
|---|---|---|
| Status | **Works today** | **Not ready. Do not deploy.** |
| Who can use it | You, in Claude Code or Claude Desktop | People in the Asmbly org on claude.ai whose Neon account type allows it |
| Sign-in | None (it's your machine) | Not built yet. It waits on the Asmbly Login Service. |
| Where the API keys come from | `config.py` at the repo root (ignored by git) | AWS Parameter Store |
| Guide | [LOCAL_SETUP.md](LOCAL_SETUP.md) | [DEPLOY.md](DEPLOY.md) (status and plan) |

## Keys

**No key values are stored in this repo, which is public.** The code and the infrastructure files only ever name where a key lives.

| Key | Used for | Local | Hosted (Parameter Store name) |
|---|---|---|---|
| Neon API user and key | Looking up members | `N_APIuser`, `N_APIkey` in `config.py` | `/asmbly-mcp/neon_api_user`, `/asmbly-mcp/neon_api_key` |
| Alta Open API user and key | Looking up door access | `O_APIuser`, `O_APIkey` in `config.py` | `/asmbly-mcp/altaopen_api_user`, `/asmbly-mcp/altaopen_api_key` |

The hosted names are settings at the top of [infra/template.yaml](infra/template.yaml). They are meant to be read-only keys made for this server, not the door sync's keys, which can change door access. That file is also where the server's AWS permissions are spelled out: it can read those four parameters and nothing else. Sign-in settings get added there when sign-in is built.

## What's in this folder

| File | What it is |
|---|---|
| `door_access.py` | The door access checks. Also runs from the command line. |
| `tools.py` | The tools Claude can call. Shared by both ways of running. |
| `local.py` | Starts the server on your own computer. |
| `setup_local.py` | Guided one-time setup for your own computer. |
| `hosted.py` | The server for AWS. Parked: it refuses to start until sign-in is built. |
| `auth.py` | Sign-in for the hosted server. Not built yet; holds the parts that carry over. |
| `aws_keys.py` | Reads the keys from Parameter Store when hosted. |
| `Dockerfile` | The container image that runs on AWS Lambda. |
| `infra/template.yaml` | The AWS resources (infrastructure as code, AWS SAM). Parked: it refuses to deploy. |
| `infra/samconfig.toml` | Deploy settings: stack name and region. |
| `pyproject.toml`, `uv.lock` | This folder's own dependencies. |
| `tests/` | Tests. |

The GitHub workflows are in the repo's `.github/workflows/`: `mcp_test.yml` runs the tests, and `mcp_deploy.yml` is the deploy, which is parked too.

## Shared code

`door_access.py` calls the same functions the door sync uses (`neonUtil.accountHasFacilityAccess`, `openPathUtil.getOpGroups` and friends), so its answers match what the sync will do. That is the one link to the rest of the repo, and it is on purpose.

Two things keep that link safe:

- **Separate dependencies.** This folder has its own `pyproject.toml` and `uv.lock`. Nothing installed here changes what the door sync installs.
- **A test that catches drift.** `tests/test_door_access.py` checks the report against the real sync rules for every account type. If someone changes the rules in `neonUtil.py`, that test fails until the report is updated to match.

## Working on it

Run commands from the repo root unless noted.

```
# run the tests
cd asmbly_mcp && uv run pytest

# run one check from the command line (needs config.py)
uv run --project asmbly_mcp python -m asmbly_mcp.door_access jane@example.com

# check the AWS template and build the container image (no AWS changes)
cd asmbly_mcp/infra && sam validate --lint && sam build
```

**Adding a tool:** add a function inside `buildServer()` in `tools.py`. Both the local and hosted servers pick it up. Keep tools read-only unless the name makes a write obvious.

**Upgrading libraries:** the sign-in storage library marks its DynamoDB support as subject to change. `uv.lock` pins exact versions, so nothing changes until someone runs `uv lock --upgrade`. After an upgrade, run the tests and try a sign-in before relying on it.
