# Hosting for the whole org: not ready yet

**Status: parked.** The hosted server has no sign-in, so it must not be deployed. To use the tool today, set it up on your own computer: [LOCAL_SETUP.md](LOCAL_SETUP.md).

## Why it's parked

The hosted server would sit at a public address and can look up any member's door access. It needs sign-in that lets in only the people who should have that. The right way to do that is being built separately: the **Asmbly Login Service**, which lets Asmbly apps sign people in with their Neon account.

## What's decided

| | |
|---|---|
| **Address** | `https://mcp.asmbly.org`. claude.ai connects to `https://mcp.asmbly.org/mcp`. |
| **Sign-in** | With a Neon account, through the Asmbly Login Service. |
| **Who gets in** | People whose Neon member account has the **Paid Staff** account type. Nobody else. |
| **Keys** | Read-only Neon and Alta Open keys made for this server, never the door sync's keys. |

## The plan

1. A person clicks **Connect** in claude.ai and signs in with their Neon account, through the Asmbly Login Service.
2. The login service tells this server who they are. It does not decide what they may do.
3. This server looks up that person's Neon member account and checks its account type. Anyone who isn't Paid Staff is refused.

Access is then managed in Neon, where the Paid Staff type is already kept up to date because it controls door access.

### Who gets in, in more detail

- **The rule is a setting.** `AllowedNeonAccountTypes` in [infra/template.yaml](infra/template.yaml) lists the allowed account types, and defaults to `Paid Staff`. Adding another type later, such as `Leader`, is a change to that one line. The check itself is `mayUseServer()` in `auth.py`.
- **Never give someone a type just to let them use this server.** These account types also control door access. Paid Staff gets into every area at any hour, without a membership or waiver. If someone needs the lookup but shouldn't be Paid Staff, create a separate account type for that and add it to the setting.
- **Why not Neon's user groups?** Groups such as Administrator belong to Neon staff logins. Sign-in goes through member accounts, which are a separate thing, and Neon's API doesn't expose user groups at all.

## Open questions

1. **Can every Paid Staff person sign in to their member account?** Sign-in goes through the member account that carries the Paid Staff type, not a Neon staff login. Someone who has never used their member login will need to set a password first.
2. **How long may someone stay signed in?** The login service suggests 30 minutes idle and 8 hours at most for member apps. A connector in claude.ai that signs people out that often may be annoying; one that never does is a risk for a tool that reads member data.
3. **Should the logs record who was looked up?** Today they record who used which tool, and leave out who they looked up, to keep member details out of the logs. Recording the looked-up Neon ID would make misuse traceable.
4. **Can Neon and Alta Open issue read-only API keys?** The server should hold keys that can't change anything. Whether each system can restrict a key that far needs checking with whoever administers it.

## What has to happen first

- [ ] The Asmbly Login Service is live in production.
- [ ] Answer the open questions above.
- [ ] Register this server with the login service as an app:
  - callback `https://mcp.asmbly.org/auth/callback`
  - signed-out page `https://mcp.asmbly.org/signed-out`
- [ ] Build the sign-in in `auth.py` and wire it up in `hosted.py`. The "is this person allowed" rule is already there.
- [ ] Point `mcp.asmbly.org` at the server: a certificate and a DNS record, added to `infra/template.yaml`. asmbly.org's DNS is in the same AWS account, so both can be infrastructure as code.
- [ ] Create the read-only API users in Neon and Alta Open, and store their keys in Parameter Store under the names in [infra/template.yaml](infra/template.yaml).
- [ ] Add the small "signed out" page.
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
| The AWS resources: function, table, logs, permissions | `infra/template.yaml` |
| The deploy workflow | `.github/workflows/mcp_deploy.yml` |

## What stops an accidental deploy

Three separate blocks, each with a message pointing here:

1. **The server refuses to start.** `createApp()` in `hosted.py` raises an error.
2. **The AWS template refuses to deploy.** The `Rules` section at the top of `infra/template.yaml` fails every deploy.
3. **The GitHub deploy button stops at its first step.**

There is also a guard that stays for good: `buildApp()` in `hosted.py` will not build the server without sign-in.

## When it's ready

The deploy itself will be `sam build` and `sam deploy` from `asmbly_mcp/infra`, or the **Deploy Asmbly MCP server** button in GitHub Actions. A claude.ai Owner then adds `https://mcp.asmbly.org/mcp` under **Organization settings > Connectors > Add > Custom**, and each person clicks **Connect** and signs in.

This page gets rewritten as a step-by-step guide when the sign-in is built.
