# Agent setup guide

This page is for an AI agent asked to set up the `lse-data-mcp` MCP server for a person on their
own computer. People can read it too, to see what the agent will do. The [README][readme] stays the
reference for every command and configuration shape. This page covers which ones to use, in what
order, and how to show that the result works.

Links below go to README sections. If your fetch tool drops the `#section` part of a link, fetch
the [raw README][readme-raw] and find the heading by name.

## Rules that apply throughout

1. **The API key never passes through you.** Do not ask for it. Do not accept it, put it on a
   command line, write it to a file, or print anything that contains it. If the user pastes it into
   the chat anyway, do not use it, and tell them it now sits in the conversation history.
2. **Look before you change anything.** Inspect first (step 2). Reuse a working setup, never add a
   second entry for this server, and leave every unrelated setting as it was.
3. **Never print a configuration file in full.** MCP configuration files often hold other servers'
   secrets. Use the client's list command, or the inspector in step 2.
4. **Ask before changing the machine beyond this server.** That means installing `uv` or Python,
   removing an existing entry, or uninstalling an extension.
5. **Never commit.** If a project-scoped entry ends up inside a repository, leave it uncommitted and
   say so.
6. **Report each verification stage as passed, failed, or pending.** A stage you could not run is
   pending, not passed.

Terms used below:

- **Target client**: the app where the user will use the tools, such as Claude Desktop, Claude
  Code, Cursor, VS Code, Codex or Antigravity. It can be a different app from the one you run in.
- **Launcher**: the exact command the target client runs to start the server, such as
  `uvx lse-data-mcp` or `/absolute/path/to/venv/bin/lse-data-mcp`.
- **Scope**: the configuration the entry goes into. That is either user-wide (every project) or a
  single project.

## 1. Establish the target

| Fact | How to establish it |
| --- | --- |
| Operating system | Your environment, or `uname -s` (on Windows, `$env:OS` in PowerShell) |
| Target client | The user's request. If it names no client, or leaves the README prompt's placeholder unchanged, ask. If you run inside an MCP client, offer that one as the default in the same question |
| Scope | User-wide, unless the user asked for one project. A project scope writes into that repository |
| Whether you run inside the target client | What you know about your own host |

The last row matters because you and the target client are different processes. A command you run
uses *your* shell's `PATH`, environment variables and sandbox, and those can differ from the
process the client starts. So a check you run tells you about your process only. Only the target
client can show that the server works there (stages 2 and 3 in step 7).

Only ask for what you cannot establish yourself, and put all your questions in one message.

## 2. Inspect what is already there

**Prerequisites.**

```bash
command -v uv uvx       # Windows: where.exe uv uvx
uv --version
python3 --version       # only for the virtual-environment route; needs 3.11 or newer
```

**Existing entries.** Look for any entry in the target client, under any name, whose launcher
mentions `lse-data-mcp` or `lse_data_mcp`:

| Client | List with | User-scope file (others) |
| --- | --- | --- |
| Claude Code | `claude mcp list` | `~/.claude.json`, which also holds per-project entries (project: `.mcp.json`) |
| Codex | `codex mcp list` | `~/.codex/config.toml` |
| Claude Desktop | Settings → Extensions, for the bundle | macOS `~/Library/Application Support/Claude/claude_desktop_config.json`, Windows `%APPDATA%\Claude\claude_desktop_config.json` |
| Cursor | **Customize** in the sidebar | `~/.cursor/mcp.json` (project: `.cursor/mcp.json`) |
| VS Code | Command Palette → **MCP: List Servers** | `mcp.json` in the user profile, opened with **MCP: Open User Configuration** (workspace: `.vscode/mcp.json`) |
| Antigravity | **Manage MCP Servers** in the agent panel | `~/.gemini/config/mcp_config.json` (workspace: `.agents/mcp_config.json`) |

Client UIs are only visible to the user, so ask them to look when you cannot. To look inside a
file without printing it, pass the file from the table to this inspector. It prints the name of
every server. For an
`lse-data` entry it also prints the launch command and the *names* of its environment variables,
never their values:

```bash
python3 - "$HOME/.cursor/mcp.json" <<'PY'
import json, pathlib, sys
path = pathlib.Path(sys.argv[1]).expanduser()
if path.suffix == ".toml":
    import tomllib  # Python 3.11+; for Codex, `codex mcp list` is usually enough
    data = tomllib.loads(path.read_text(encoding="utf-8"))
else:
    data = json.loads(path.read_text(encoding="utf-8"))  # fails on comments: stop, do not print the file
groups = [(key, data[key]) for key in ("mcpServers", "servers", "mcp_servers") if isinstance(data.get(key), dict)]
groups += [(f"projects[{name}].mcpServers", entry["mcpServers"]) for name, entry in data.get("projects", {}).items()
           if isinstance(entry, dict) and isinstance(entry.get("mcpServers"), dict)]
for where, servers in groups:
    for name, entry in servers.items():
        launch = " ".join(str(part) for part in [entry.get("command", ""), *entry.get("args", [])])
        if "lse-data" in name or "lse-data-mcp" in launch or "lse_data_mcp" in launch:
            print(f"{where}.{name}: {launch}")
            print(f"    env names: {sorted(entry.get('env', {}))}  env_vars: {entry.get('env_vars', [])}")
        else:
            print(f"{where}.{name}")
PY
```

On Windows, save the script to a temporary file and run `python <script> <config file>`.

**Credential state.** Run `status` with the launcher of the existing entry, or with the launcher
you are about to configure. For example:

```bash
uvx lse-data-mcp status
```

It prints four lines (`API key source`, `Credential store`, `Key stored there`, `LSE_API_KEY set`)
and never prints the key itself. It exits 0 when the process that ran it can find a key. It does
not contact the API, so it cannot tell a valid key from an invalid one. Skip it for the Claude
Desktop bundle or a VS Code input: there the client holds the key, and `status` cannot see it.

On macOS, a program other than the one that stored the key raises a Keychain dialog the first time
it reads the key ([README › The macOS Keychain prompt][r-keychain]). Before you run `status`, warn
the user that the dialog may appear. It asks for their Mac login password, not the API key.

**Decide what to do next.**

- **An entry exists and has a key**, found by `status` or held by the client. Change nothing yet
  and go to step 7. Fix only the
  stage that fails, if any.
- **An entry exists but is broken**, for example a wrong path, switched off, or failing to start.
  Repair that entry rather than adding another one.
- **Two entries exist**, such as the bundle and a manual entry in Claude Desktop. The client would
  start two copies of the same 15 tools. Ask the user which one to keep before you remove either.
- **No entry exists.** Continue to step 3.

## 3. Choose the route

| Target client | Route | Register with |
| --- | --- | --- |
| Claude Desktop | The bundle, if `uv` is installed or the user agrees to install it. Otherwise a manual entry | Bundle: [README › Claude Desktop][r-desktop]. Manual: the `mcpServers` object in [README › MCP client configuration examples][r-clients] |
| Claude Code | `uvx` | `claude mcp add -s user lse-data -- uvx lse-data-mcp` |
| Codex | `uvx` | `codex mcp add lse-data -- uvx lse-data-mcp` |
| VS Code | `uvx` | `code --add-mcp '{"name":"lse-data","command":"uvx","args":["lse-data-mcp"]}'` (user profile), or the README's install button |
| Cursor | `uvx` | The README's **Add to Cursor** button, or add the entry to `~/.cursor/mcp.json` |
| Antigravity | `uvx` | Add the entry to `~/.gemini/config/mcp_config.json` ([README][r-clients]) |
| Any other | `uvx` | The README's `mcpServers` object, translated into that client's own format |

**Launcher.** `uvx` is preferred. It needs only `uv`, which brings its own Python. If `uv` is
missing, ask before installing it, then follow [uv's installation guide][uv-install].

When `uv` is unavailable or unwanted, use a virtual environment instead (a self-contained Python
install). It needs Python 3.11 or newer, and macOS's own `python3` is often 3.9
([README › Installation][r-install]). Create it in a stable per-user directory outside any
repository, and register its script by absolute path (README, *Pointing at a virtual environment
instead*):

```bash
python3.13 -m venv ~/.local/share/lse-data-mcp/venv
~/.local/share/lse-data-mcp/venv/bin/python -m pip install lse-data-mcp
~/.local/share/lse-data-mcp/venv/bin/lse-data-mcp --help    # shows usage when the launcher works
```

On Windows, run `py -3.13 -m venv "$env:LOCALAPPDATA\lse-data-mcp\venv"`. The script is then at
`...\venv\Scripts\lse-data-mcp.exe`.

**Keep the launcher consistent.** Run `login` and `status` as the client's exact launcher with the
subcommand added:

| The client runs | Store and check the key with |
| --- | --- |
| `uvx lse-data-mcp` | `uvx lse-data-mcp login`, `uvx lse-data-mcp status` |
| `/abs/path/venv/bin/lse-data-mcp` | `/abs/path/venv/bin/lse-data-mcp login`, `... status` |

On macOS, a mismatched launcher brings back the Keychain prompt. Keep any existing version pin, and
add one only if the user asks for it.

**GUI clients and `PATH`.** An app started from the Dock, the Start menu or a desktop launcher does
not read your shell profile. It may therefore not find a `uvx` installed in `~/.local/bin` or
Homebrew's `bin`. For a manual Claude Desktop entry, set `command` to the absolute path from
`command -v uvx` (on Windows, `where.exe uvx`). For other GUI clients, keep the bare `uvx` and
switch to the absolute path only if the server fails with a "command not found" or `ENOENT` error.
After installing `uv`, restart any GUI client that was already running so it can find the new
program.

## 4. Register the server

- Prefer the client's own command from the table above, because it changes only its own entry.
  `claude mcp add` defaults to the `local` scope (this project only), so pass `-s user` for
  user-wide.
- Name the entry `lse-data`, as the README does. If an entry for this server already exists under
  another name, keep that name.
- If you have to edit a file by hand:
  1. Copy it next to the original first, as `<file>.bak-lse-data`, and list the copy in your
     report. It contains everything the original does, including any other servers' secrets.
  2. Parse the file and add or update only the one entry under the client's server key:
     `mcpServers` for most clients, `servers` for VS Code, `[mcp_servers.<name>]` for Codex. Write
     it back without reordering anything else.
  3. Parse the result again to confirm it is still valid.
  4. Never write a key value into an `env` block. The environment route (step 5C) adds a reference
     by name only.

## 5. Supply the key

Use the first option below that fits.

### A. The operating system's credential store (the default on a desktop)

Give the user one exact command to run **in their own terminal window**: the launcher plus
`login`. For example:

```bash
uvx lse-data-mcp login
```

It prompts `London Strategic Edge API key (input is hidden):` and stores the key in Keychain,
Credential Locker or Secret Service ([README › Supplying the API key][r-key]).

Do not run it through your own command tool, or through any shell passthrough in the chat. Without
a real terminal the prompt cannot hide what is typed, and the typed key can end up in the session
transcript. Wait for the user to confirm they have done it, then run `status` yourself.

### B. The client's own secure key field

- **Claude Desktop bundle.** The install dialog asks for the key, and Claude Desktop stores it
  encrypted, so no `login` is needed. Point the user to the
  [bundle download][bundle], which they open with Claude Desktop. Then follow the steps in
  [README › Claude Desktop][r-desktop]: switch the extension on under Settings → Extensions, and
  check again after saving the key, because saving can switch it off.
- **VS Code.** Use this when the user wants VS Code to hold the key, or when VS Code cannot reach
  the credential store. Declare an `inputs` entry of type `promptString` with `"password": true`.
  Then set the server's `"env": {"LSE_API_KEY": "${input:<id>}"}`, where `<id>` is the input's
  `id`. VS Code prompts for the key on the server's first start and stores it for later starts
  ([VS Code MCP configuration reference][vscode-mcp]).

### C. An environment variable (headless hosts, or a store the client cannot reach)

`LSE_API_KEY` takes precedence over a stored key. The user puts the value into the environment of
the process that starts the client, not you. They can use the host's own secret mechanism, such as
a container secret, a CI secret, or a service manager credential. For a single interactive shell
session on macOS or Linux, they can type it into a hidden prompt and then start the client from
that same shell:

```bash
read -rs LSE_API_KEY && export LSE_API_KEY    # type the key and press Enter; nothing is shown
```

Do not put the value in a shell profile, a `.env` file, or a configuration file. The server never
reads `.env` files, and plain text on disk is exactly what the credential store exists to avoid.

Your part is to make sure the client passes the variable on to the server *by name*:

- **Codex** passes local stdio servers only a fixed list of variables, such as `HOME` and `PATH`.
  Add `env_vars = ["LSE_API_KEY"]` under `[mcp_servers.lse-data]`
  ([Codex MCP docs][codex-mcp]).
- **Cursor:** `"env": {"LSE_API_KEY": "${env:LSE_API_KEY}"}` ([Cursor MCP docs][cursor-mcp]).
- **Claude Code:** `"env": {"LSE_API_KEY": "${LSE_API_KEY}"}` ([Claude Code MCP docs][claude-mcp]).
  If the variable is unset when Claude Code starts, the literal text `${LSE_API_KEY}` reaches the
  server and the API rejects it with a 401 error. Use this only on hosts where the variable is
  always set.
- **Any other client:** use its documented way to reference a variable by name. Never use
  `--env LSE_API_KEY=<value>` with `claude mcp add` or `codex mcp add`. That puts the key in shell
  history, in the process list and in the configuration file.

To check whether the variable is set without revealing it, read the `LSE_API_KEY set:` line of
`status`. Never run `env`, `printenv` or `set`, or `echo` the variable.

### When `status` cannot find a key

`status` gives one of three answers on its `Key stored there:` line
([README › When the server cannot find your key][r-cannot-find]):

| `Key stored there:` | Meaning | Do |
| --- | --- | --- |
| `no` | The store answered, and it holds no key | 5A: the user runs `login` |
| `unknown - there is no credential store to ask` | This host has no store, which is usual on headless Linux | 5C. `login` cannot work on this host |
| `unknown - this process cannot reach the credential store` | A key may well be stored, but this process is not allowed to read it | **Do not suggest `login` again.** Follow the steps below |

For "cannot reach":

1. **Find out whose process is blocked.** If you run in a sandbox, the store may refuse your shell
   while still answering the user's terminal and the client. Ask the user to run the same `status`
   command in their own terminal.
2. **If their terminal reports `yes`**, the key exists. Continue to step 6 and step 7, because the
   client may read it without trouble.
3. **If the client's server reports the same error at stage 3**, that process needs access. The
   user can unlock their keychain or keyring, answer the Keychain prompt, or run the client outside
   its sandbox. Otherwise, switch that client to option B or C.

Running `login` again cannot fix this. From a blocked process it fails, and from an unblocked one it
overwrites a key that was already stored.

## 6. Restart or reload

A server process looks up the key once and keeps the result until it exits, and most clients start
servers only when they launch. So after registering the server, or after storing or changing the
key, the client must start a fresh server process:

| Client | What is needed |
| --- | --- |
| Claude Code | A new session. `/mcp` shows server status and can reconnect |
| Codex | A new session. `/mcp` lists active servers |
| Claude Desktop, manual entry | Quit the app completely (closing the window is not enough) and reopen it |
| Claude Desktop, bundle | Switch the extension on under Settings → Extensions, and check again after saving the key |
| VS Code | **MCP: List Servers** → start or restart the server, and accept the trust prompt on its first start |
| Cursor | Switch the server off and on under **Customize** in the sidebar |
| Antigravity | Refresh in **Manage MCP Servers** |

Tell the user exactly which of these they need to do themselves, and wait until they have done it.
If you run inside the target client, its new tools usually do not appear in your current
conversation. Stage 3 then falls to the user, or to you in a new session.

## 7. Verify in three stages

Each stage proves something the one before cannot. Stop at the first stage that fails and fix it.

### Stage 1: credential availability

- **Credential-store or environment route.** `<launcher> status` exits 0, and `API key source:`
  names either the credential store or `LSE_API_KEY`. If it names `LSE_API_KEY` but the user meant
  to use the stored key, the variable is overriding it. Find out where the variable is set.
- **Bundle or VS Code input.** There is nothing for you to run. The user confirms that the key field
  is filled in.

A pass shows that the process that ran the check can find a key. It does not show that the key is
valid, that the client's own process can read it, or that the API answers.

### Stage 2: connection and tool discovery in the target client

- **Claude Code:** `claude mcp list` health-checks each server and should show `lse-data` as
  connected. In a session, `/mcp` lists its tools.
- **Codex:** `codex mcp list` shows the entry. In a new session, `/mcp` shows whether it started.
- **Other clients:** the client's MCP settings or server list shows `lse-data` running. Ask the user
  to look if you cannot.

It passes when the server is connected and lists 15 tools, all named `get_…`. The server can start
and list its tools without any key, because it reads the key only when a tool is called. So a pass
here says nothing about the key.

If the server fails to start, run the launcher with `--help` in a terminal to check that it
resolves, and check the `PATH` rule in step 3. Then look at the client's MCP log, for example
`~/Library/Logs/Claude/mcp*.log` for Claude Desktop on macOS, or **MCP Logs** in Cursor's Output
panel. Show only the lines about `lse-data`.

### Stage 3: one small read-only request

Make this call through the target client:

> `get_candles` with `symbol: "IBM"`, `timeframe: "1d"`, `limit: 1`, `order: "desc"`

That fetches the most recent daily bar: one request against the user's allowance, and one row in
reply. Do not use `get_reference("catalog")` for this check, because it lists 22,000+ instruments.
Avoid option chains and large `limit` values for the same reason.

It passes when `row_count` is 1 and there is no error. If you cannot call tools in the target
client, give the user this message to paste there. Mark stage 3 as pending until they report back:

> Use the lse-data get_candles tool with symbol IBM, timeframe 1d, limit 1 and order desc. Tell me
> the row_count, or the exact error message.

A failure carries one of the server's own messages
([README › Errors and retries][r-errors]):

| The error contains | Meaning | Next step |
| --- | --- | --- |
| `No London Strategic Edge API key is configured` | The client's server process found no key at all | If stage 1 passed for you, your process and the client's differ. Either the variable did not reach the server (5C), or the key was stored for another user or host. If `login` ran after the server started, restart it (step 6) |
| `cannot reach` | The client's process is blocked from the credential store | Step 5, "cannot reach". Not `login` |
| `no credential store` | This host has no store | 5C |
| `authentication failed` (status 401) | The API rejected the key | First rule out a `${LSE_API_KEY}` reference that reached the server unexpanded (5C). Otherwise the key is wrong or expired, and this is the one case where the user should run `login` again with a correct key |
| `does not permit this request` (status 402 or 403) | The API accepted the key, but the account cannot access this data | Setup works. Report that the account's plan does not cover this request |
| `rate limit` (status 429) | Too many requests | Wait, then retry once |
| `timed out`, `could not be reached`, `temporarily unavailable` | A network or upstream problem | Retry later. This is not a setup fault |

## 8. Report

Finish with a short report in this shape:

```text
lse-data-mcp setup: <client>, <scope>, <OS>
Route: <bundle | uvx | virtual environment>, launcher <command>
Changed: <each command run and file edited, with any backup made>, or "nothing; reused the existing setup"
Stage 1, credential:  <passed | failed | pending>, <evidence, e.g. "status: key in macOS Keychain">
Stage 2, connection:  <passed | failed | pending>, <evidence>
Stage 3, API request: <passed | failed | pending>, <evidence>
Left for you: <each remaining action>, or "nothing"
```

While any stage is pending, do not call the setup complete. Say what will complete it.

## Scenario map

| Situation | Path through this guide |
| --- | --- |
| Fresh install | Steps 1 to 8 in order |
| Existing working setup | 1, then 2 (entry found and key available), then 7 and 8. Change nothing unless a stage fails |
| Missing key (`Key stored there: no`) | 5A, then 6, 7 and 8 |
| Credential store unreachable | Step 5, "cannot reach", then 6, 7 and 8. Never a repeated `login` |
| Client needs a restart | 6, then stages 2 and 3, which stay pending until the user has restarted |

[readme]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md
[readme-raw]: https://raw.githubusercontent.com/OlegDyukel/lse-data-mcp/main/README.md
[r-install]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#installation
[r-desktop]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#claude-desktop
[r-key]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#supplying-the-api-key
[r-cannot-find]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#when-the-server-cannot-find-your-key
[r-keychain]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#the-macos-keychain-prompt
[r-clients]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#mcp-client-configuration-examples
[r-errors]: https://github.com/OlegDyukel/lse-data-mcp/blob/main/README.md#errors-and-retries
[bundle]: https://github.com/OlegDyukel/lse-data-mcp/releases/latest/download/lse-data-mcp.mcpb
[uv-install]: https://docs.astral.sh/uv/getting-started/installation/
[claude-mcp]: https://code.claude.com/docs/en/mcp
[codex-mcp]: https://learn.chatgpt.com/docs/extend/mcp
[cursor-mcp]: https://cursor.com/docs/mcp
[vscode-mcp]: https://code.visualstudio.com/docs/agents/reference/mcp-configuration
