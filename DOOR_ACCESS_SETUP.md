# Door Access Troubleshooter for Claude

Ask Claude *"Why can't jane@example.com get in the door?"* and get back a checklist like this:

```
Door access check: Jane Doe (Neon #1234, jane@example.com)
Account type: regular member (no special type)

✅ Membership paid and current: Regular membership, paid through 2026-11-06
❌ Access not suspended: AccessSuspended is set in Neon: "Facility Access Suspended"
     → Fix: Find out why it was suspended before clearing it (ask leadership). ...
✅ Waiver signed: WaiverDate 2026-10-07
✅ Orientation completed: FacilityTourDate 2026-08-05
✅ Alta Open account active: Alta Open user 456 is Active
⚠️ Alta Open groups correct: Still in Subscribers, but Neon says they shouldn't be.
     → Fix: The next sync will remove them. That's expected if the Neon checks above fail.
✅ Has a door credential: 1 credential(s): Automatic Mobile Credential

Verdict: Problem found: Access not suspended. Note: Alta Open still has them in access groups,
so the door may keep working until the next sync removes them.
```

The tool is **read only**. It looks things up in Neon and Alta Open but never changes anything.

---

## Setup (about 10 minutes, once per computer)

You need:
- A Mac or Windows computer with the **Claude Desktop app** ([download](https://claude.ai/download)) or **Claude Code** installed and signed in
- The **Neon API user and key** and the **Alta Open API user and key**. Ask the IT lead (it@asmbly.org). They're the same ones in `config.py` on adminbot.

### 1. Open a terminal

- **Mac:** press `Cmd + Space`, type `Terminal`, press Enter.
- **Windows:** press the Windows key, type `PowerShell`, press Enter.

Paste each command below into that window and press Enter. Wait for each to finish before pasting the next.

### 2. Install `uv` (runs the Python code for you)

**Mac:**
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

(If you use Homebrew, `brew install uv` works too.)

**Windows:**
```
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then **close the terminal window and open a new one** so it finds `uv`.

### 3. Download this repo

Skip this step if you already have the `NeonIntegrations` folder.

```
git clone https://github.com/asmbly-makerspace/NeonIntegrations.git
```

On a Mac, if it asks you to install "command line developer tools", click **Install**, wait, then run the command again.

If you get `git: command not found` (common on Windows), go to the [repo on GitHub](https://github.com/asmbly-makerspace/NeonIntegrations), click **Code → Download ZIP**, unzip it into your home folder and rename the folder to `NeonIntegrations`.

### 4. Run the setup

```
cd NeonIntegrations
uv run --group door-access setup_door_access.py
```

It will:
1. Ask for the 4 API values. Key typing is hidden, so nothing appears on screen while you type or paste. That's normal; just press Enter.
2. Test that the keys work. If one fails, it says which one.
3. Ask whether to add the tool to the Claude Desktop app and/or Claude Code, whichever you have. Press Enter for yes.

### 5. Restart Claude

- **Claude Desktop:** fully quit it (Mac: `Cmd + Q`. Windows: right-click the Claude icon in the system tray, then **Quit**) and open it again.
- **Claude Code:** start a new session. Type `/mcp` to confirm `asmbly-door-access` is connected.

### 6. Try it

In a new Claude chat:

> Check door access for jane@example.com

You can also give a name (`Jane Doe`) or a Neon account ID (`1234`). If several people match, Claude shows the list so you can pick one.

The first time, Claude asks permission to use the tool. Click **Allow** (or **Always allow**).

---

## What it checks

| # | Check | Where |
|---|---|---|
| 1 | Membership is **paid** and current (a failed or pending payment fails, even if Neon shows "Active") | Neon memberships |
| 2 | `AccessSuspended` is blank | Neon |
| 3 | `WaiverDate` is set | Neon |
| 4 | `FacilityTourDate` (orientation) is set | Neon |
| 5 | The Alta Open user exists and is Active | Alta Open |
| 6 | The Alta Open groups match what Neon says they should have (e.g. **Subscribers**, which grants General Member Access) | Alta Open |
| 7 | They have a door credential (mobile or card) | Alta Open |

What the icons mean: ✅ good, ❌ problem, ⚠️ worth a look, ➖ not met but not required for this account.

**Staff and other special accounts.** The top of the report shows the person's Neon account type. Some types get door access without meeting the member requirements, so those lines show ➖ and "That's OK" in place of ❌:

| Neon account type | What isn't required |
|---|---|
| Paid Staff, Space Lead, Leader, Super Steward | Membership, waiver and orientation. A suspension shows as ⚠️ because the door sync ignores it for these accounts. |
| CoWorking Tenant | Membership only. They still need the waiver and orientation, and must not be suspended. |

These follow the same rules the door sync uses (`neonUtil.accountHasFacilityAccess` and `openPathUtil.getOpGroups`).

If everything passes, the problem is most likely the phone (Bluetooth or location off, not logged in to the Avigilon Alta app) or the door reader.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Close the terminal, open a new one, and try again. If it still fails, redo step 2. |
| Setup says a key doesn't work | Open `config.py` in the `NeonIntegrations` folder with any text editor and fix the value, then run step 4 again. |
| Claude doesn't seem to have the tool | Fully quit and reopen Claude Desktop. In Claude, open **Settings → Developer**: `asmbly-door-access` should be listed as **running**. If it shows an error, click it to see the log. |
| "API key ... wrong or lacks permission" in the chat | The key in `config.py` changed or expired. Get the new one and edit `config.py`. |
| Claude Code doesn't have the tool | Start a new session and type `/mcp`. If `asmbly-door-access` isn't listed, run the setup again and press Enter at the Claude Code question. |
| Run a check without Claude | `uv run doorAccessCheck.py jane@example.com` from the `NeonIntegrations` folder |

**Keep `config.py` private.** It holds the keys that control door access. Git already ignores it, but don't email or paste it anywhere.

---

## For developers

- `doorAccessCheck.py`: the checks. Uses `neonUtil` / `openPathUtil`, so it always matches the real sync logic (`openPathUtil.getOpGroups`).
- `doorAccessMcp.py`: the MCP server (stdio) that exposes `check_door_access` and `find_member`.
- `setup_door_access.py`: guided setup. It merges into `claude_desktop_config.json` and saves a `.bak` copy first.
- Tests: `tests/test_doorAccessCheck.py`
- The `mcp` package lives in the `door-access` dependency group, so it isn't installed into the Lambda image.
- Team-wide claude.ai connector (no local install): not built yet. It would need the server hosted remotely with authentication in front of it, plus read-only Neon and Alta Open API users.
