###############################################################################
# One-time guided setup for the Claude door access tool.
#
#   uv run --group door-access setup_door_access.py
#
# It will:
#   1. Ask for your Neon and Alta Open API keys (only if config.py lacks them)
#   2. Test that both keys actually work
#   3. Add the tool to Claude Desktop (and/or show the Claude Code command)
# Safe to run again any time - it won't overwrite keys that already work.
###############################################################################

import base64
import getpass
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parent
CONFIG = REPO / "config.py"
SERVER_NAME = "asmbly-door-access"

NEEDED = {
    "N_APIuser": "Neon API user (your Neon org ID, e.g. 'asmbly')",
    "N_APIkey": "Neon API key",
    "O_APIuser": "Alta Open API user (usually an email address)",
    "O_APIkey": "Alta Open API key / password",
}


def say(msg=""):
    print(msg, flush=True)


def ok(msg):
    say(f"  ✅ {msg}")


def bad(msg):
    say(f"  ❌ {msg}")


def ask_yes(question, default=True):
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {hint} ").strip().lower()
    if not answer:
        return default
    return answer.startswith("y")


def load_config():
    if not CONFIG.exists():
        return {}
    spec = importlib.util.spec_from_file_location("config", CONFIG)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as err:
        bad(f"config.py exists but has an error in it: {err}")
        bad("Fix or delete config.py, then run this again.")
        sys.exit(1)
    return {k: getattr(module, k, None) for k in NEEDED}


def step_keys():
    say("\nStep 1 of 3: API keys")
    values = load_config()
    missing = [k for k in NEEDED if not values.get(k)]
    if not missing:
        ok("config.py already has Neon and Alta Open keys")
        return values

    say("  Ask your IT lead for these if you don't have them. Typing is hidden for keys.")
    lines = []
    for key in missing:
        prompt = f"  {NEEDED[key]}: "
        while True:
            value = (getpass.getpass(prompt) if "key" in key.lower() else input(prompt)).strip()
            if value:
                break
            say("    (can't be blank)")
        values[key] = value
        lines.append(f"{key} = {value!r}")

    new = not CONFIG.exists()
    with open(CONFIG, "a") as f:
        if new:
            f.write("# API keys - this file is ignored by git. Never commit or share it.\n")
        f.write("\n# Added by setup_door_access.py\n" + "\n".join(lines) + "\n")
    os.chmod(CONFIG, 0o600)
    ok(f"Saved to {CONFIG}")
    return values


def basic_auth(user, key):
    return "Basic " + base64.b64encode(f"{user}:{key}".encode()).decode()


def step_test(values):
    say("\nStep 2 of 3: Testing the keys")
    allGood = True

    try:
        r = requests.get(
            "https://api.neoncrm.com/v2/accounts/search/searchFields",
            headers={"Authorization": basic_auth(values["N_APIuser"], values["N_APIkey"])},
            timeout=30,
        )
        if r.status_code == 200:
            ok("Neon key works")
        else:
            bad(f"Neon said {r.status_code}. Double-check N_APIuser / N_APIkey in config.py.")
            allGood = False
    except requests.RequestException as err:
        bad(f"Couldn't reach Neon: {err}")
        allGood = False

    try:
        r = requests.get(
            "https://api.openpath.com/orgs/5231/users?limit=1",
            headers={"Authorization": basic_auth(values["O_APIuser"], values["O_APIkey"])},
            timeout=30,
        )
        if r.status_code == 200:
            ok("Alta Open key works")
        else:
            bad(f"Alta Open said {r.status_code}. Double-check O_APIuser / O_APIkey in config.py.")
            allGood = False
    except requests.RequestException as err:
        bad(f"Couldn't reach Alta Open: {err}")
        allGood = False

    if not allGood:
        say("\n  Fix the keys in config.py (open it in any text editor), then run this again.")
        sys.exit(1)


def desktop_config_path():
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if system == "Windows":
        return Path(os.environ.get("APPDATA", Path.home())) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/Claude/claude_desktop_config.json"


def server_command():
    # Claude Desktop doesn't see your shell's PATH, so use the full path to uv
    uv = shutil.which("uv")
    if not uv:
        bad("Can't find 'uv'. Install it (see DOOR_ACCESS_SETUP.md) and run this again.")
        sys.exit(1)
    return uv, ["--directory", str(REPO), "run", "--group", "door-access", "doorAccessMcp.py"]


def step_install():
    say("\nStep 3 of 3: Connect to Claude")
    uv, args = server_command()
    installed = False

    path = desktop_config_path()
    if path.parent.exists() and ask_yes("  Add the tool to the Claude Desktop app?"):
        data = {}
        if path.exists():
            try:
                data = json.loads(path.read_text() or "{}")
            except json.JSONDecodeError:
                bad(f"{path} isn't valid JSON, so I won't touch it. Fix it or add the entry by hand.")
                data = None
            if data is not None:
                shutil.copy(path, path.with_suffix(".json.bak"))
        if data is not None:
            data.setdefault("mcpServers", {})[SERVER_NAME] = {"command": uv, "args": args}
            path.write_text(json.dumps(data, indent=2) + "\n")
            ok("Added to Claude Desktop")
            say("     → Fully QUIT Claude Desktop (Cmd+Q on Mac, not just close the window) and reopen it.")
            installed = True
    elif not path.parent.exists():
        say("  Claude Desktop isn't installed on this computer (skipping).")

    claude = shutil.which("claude")
    if claude and ask_yes("  Add the tool to Claude Code (the terminal app) too?", default=False):
        result = subprocess.run(
            [claude, "mcp", "add", "--scope", "user", SERVER_NAME, "--", uv, *args],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            ok("Added to Claude Code")
            installed = True
        else:
            bad(f"Claude Code said: {(result.stderr or result.stdout).strip()}")

    if not installed:
        say("\n  To add it by hand, put this in your Claude Desktop config under \"mcpServers\":")
        say(json.dumps({SERVER_NAME: {"command": uv, "args": args}}, indent=2))


def main():
    say("Asmbly door access tool setup")
    say("=" * 30)
    values = step_keys()
    step_test(values)
    step_install()
    say("\nAll done! In Claude, try:")
    say('  "Check door access for jane@example.com"')
    say("\nYou can also run a check without Claude:")
    say("  uv run doorAccessCheck.py jane@example.com")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        say("\nCancelled. Nothing else was changed.")
