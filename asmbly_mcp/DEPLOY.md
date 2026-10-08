# Hosting for the whole org: not ready yet

**Status: parked.** The hosted server has no sign-in, so it must not be deployed. To use the tool today, set it up on your own computer: [LOCAL_SETUP.md](LOCAL_SETUP.md).

## Why it's parked

The hosted server would sit at a public address and can look up any member's door access. It needs sign-in that lets in only the people who should have that. The right way to do that is being built separately: the **Asmbly Login Service**, which lets Asmbly apps sign people in with their Neon account.

## The plan

1. A person clicks **Connect** in claude.ai and signs in with their Neon account, through the Asmbly Login Service.
2. The login service tells this server who they are. It does not decide what they may do.
3. This server looks up that person's Neon account and checks its **account type**. Only the allowed types get in.

Access is then managed where roles are already managed. Remove the account type in Neon and the person loses access.

## What has to happen first

- [ ] The Asmbly Login Service is live in production.
- [ ] This server is registered with it as an app.
- [ ] Decide which Neon account types may use this server.
- [ ] Build the sign-in and the account type check in `auth.py`, and wire them up in `hosted.py`.
- [ ] Give the server an address on asmbly.org, for example `mcp.asmbly.org`.
- [ ] Create read-only API users for this server in Neon and Alta Open, and store their keys in Parameter Store under the names in [infra/template.yaml](infra/template.yaml). The server must not use the door sync's keys, because those can change door access.
- [ ] Add a small "signed out" page.
- [ ] Remove the three blocks listed below.

## What's already built

These carry over as they are:

| Piece | Where |
|---|---|
| The tools and the door access checks | `tools.py`, `door_access.py` |
| The web server, minus sign-in | `hosted.py` |
| Reading keys from Parameter Store by name | `aws_keys.py` |
| Storage for sign-in state, encrypted | `auth.py`, and the table in the template |
| The container image for AWS Lambda | `Dockerfile` |
| The AWS resources: function, public address, table, logs, permissions | `infra/template.yaml` |
| The deploy workflow | `.github/workflows/mcp_deploy.yml` |

## What stops an accidental deploy

Three separate blocks, each with a message pointing here:

1. **The server refuses to start.** `createApp()` in `hosted.py` raises an error.
2. **The AWS template refuses to deploy.** The `Rules` section at the top of `infra/template.yaml` fails every deploy.
3. **The GitHub deploy button stops at its first step.**

There is also a guard that stays for good: `buildApp()` in `hosted.py` will not build the server without sign-in.

## When it's ready

The deploy itself will be `sam build` and `sam deploy` from `asmbly_mcp/infra`, or the **Deploy Asmbly MCP server** button in GitHub Actions. A claude.ai Owner then adds the server's address under **Organization settings > Connectors > Add > Custom**, and each person clicks **Connect** and signs in.

This page gets rewritten as a step-by-step guide when the sign-in is built.
