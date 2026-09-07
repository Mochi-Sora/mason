# Mason CLI Reference

Live sources when anything looks stale: `mason --help`, `mason <command> --help`,
https://mason-agent.nousresearch.com/docs/reference/cli-commands

### Global Flags

```
mason [flags] [command]        (no subcommand = interactive chat)

  --version, -V             Show version
  -z, --oneshot PROMPT      One-shot: print ONLY the final response (for scripts/pipes)
  -m MODEL  --provider P    Model/provider override for this invocation
  -t, --toolsets LIST       Comma-separated toolsets for this invocation
  --resume, -r SESSION      Resume session by ID or title
  --continue, -c [NAME]     Resume by name, or most recent session
  --worktree, -w            Isolated git worktree mode (parallel agents)
  --skills, -s SKILL        Preload skills (comma-separate or repeat)
  --profile, -p NAME        Use a named profile
  --yolo                    Skip dangerous command approval
  --tui / --cli             Force the Ink TUI / classic REPL
  --ignore-rules            Skip AGENTS.md/SOUL.md/memory/skill injection
  --safe-mode               Disable ALL customizations (troubleshooting)
  --pass-session-id         Include session ID in system prompt
```

### Chat

```
mason chat [flags]
  -q, --query TEXT          Single query, non-interactive
  --image PATH              Attach a local image to a single query
  -Q, --quiet               Suppress banner, spinner, tool previews
  --checkpoints             Enable filesystem checkpoints (/rollback)
  --max-turns N             Cap tool-calling iterations
  --source TAG              Session source tag (default: cli)
```
(plus the global flags above)

### Configuration

```
mason setup [section]      Wizard (model|tts|terminal|gateway|tools|agent)
mason model                Interactive model/provider picker
mason fallback [add|remove|list]  Fallback provider chain
mason config [show|edit|get|set|unset|path|env-path|check|migrate]
mason login / logout       OAuth sign-in / clear stored auth
mason doctor [--fix]       Check dependencies and config
mason status [--all]       Component status
```

### Tools & Skills

```
mason tools [list|enable NAME|disable NAME]   Per-platform toolsets (curses UI with no args)

mason skills list|browse|search QUERY|inspect ID
mason skills install ID    Hub identifier OR a direct https://…/SKILL.md URL
mason skills config        Enable/disable skills per platform
mason skills check|update|uninstall|publish PATH
mason skills tap add REPO  Add a GitHub repo as a skill source
mason bundles              Skill bundles (one /<name> alias loads several skills)
```

### MCP Servers

```
mason mcp add NAME (--url or --command) | remove | list | test NAME
mason mcp catalog | install NAME     Curated catalog install
mason mcp configure NAME             Toggle tool selection
mason mcp serve                      Run Mason as an MCP server
```
Details (transport, tool discovery, catalog): `references/native-mcp.md`.

### Gateway (Messaging Platforms)

```
mason gateway run|install|start|stop|restart|status|setup
```

20+ platforms: Telegram, Discord, Slack, WhatsApp (Baileys + Business Cloud API), iMessage (Photon — `mason photon setup`), Signal, Email, SMS, Matrix, Mattermost, Teams, LINE, SimpleX, ntfy, Google Chat, Home Assistant, DingTalk, Feishu, WeCom, Weixin, API Server, Webhooks. Open WebUI connects via the API Server adapter. Most adapters ship under `plugins/platforms/`.
Docs: https://mason-agent.nousresearch.com/docs/user-guide/messaging/

### Sessions

```
mason sessions list|browse|rename ID TITLE|delete ID|export OUT|prune|stats
```

### Cron / Webhooks

```
mason cron list|create SCHED|edit ID|pause|resume|run ID|remove|status
    Schedules: '30m', 'every 2h', '0 9 * * *', ISO timestamp
mason webhook subscribe NAME|list|remove NAME|test NAME
```
Webhook payloads/routes: `references/webhooks.md`.

### Profiles

```
mason profile list|create NAME (--clone|--clone-all|--clone-from)|use|show|delete
mason profile rename A B | alias NAME | export NAME | import FILE
```

### Credentials & Pools

```
mason auth                 Interactive credential manager
mason auth add [PROVIDER]  Add OAuth or API-key credential (nous, openai-codex, qwen-oauth, …)
mason auth list|remove P IDX|reset PROVIDER|status
```
Multiple credentials per provider form a pool that rotates automatically and skips exhausted keys.

### Other

```
mason desktop / gui        Native desktop app
mason dashboard            Web admin panel + embedded chat (--stop / --status)
mason proxy                OpenAI-compatible local proxy backed by an OAuth provider
mason portal               Quick setup / sign in via Nous Portal
mason kanban <verb>        Multi-agent work-queue board
mason project              Named multi-folder workspaces
mason skin list|use|set    Switch/tweak skins (see references/themes.md)
mason pets <verb>          Pet mascots (see references/petdex.md)
mason memory setup|status|off|reset   Memory provider
mason secrets bitwarden|onepassword   External secret stores
mason moa                  Mixture-of-Agents slots
mason hooks / security / backup / import / checkpoints / console
mason logs [-f] [errors]   View agent/error logs
mason send                 One-off message through a gateway platform
mason pairing / plugins / insights / journey / computer-use
mason acp                  ACP server (IDE integration)
mason completion bash|zsh|fish
mason update / uninstall / claw migrate
```

Plugin- and provider-supplied subcommands (e.g. `mason photon setup`) only appear once their plugin is installed/active.

### Where to Find Things

| Looking for... | Location |
|---|---|
| Config options | `mason config edit` · [Configuration docs](https://mason-agent.nousresearch.com/docs/user-guide/configuration) |
| Tools / toolsets | `mason tools list` · [Tools reference](https://mason-agent.nousresearch.com/docs/reference/tools-reference) |
| Skills catalog | `mason skills browse` · [Skills catalog](https://mason-agent.nousresearch.com/docs/reference/skills-catalog) |
| Provider setup | `mason model` · [Providers guide](https://mason-agent.nousresearch.com/docs/integrations/providers) |
| Env variables | `mason config env-path` · [Env vars reference](https://mason-agent.nousresearch.com/docs/reference/environment-variables) |
| Gateway logs | `~/.mason/logs/gateway.log` (or `mason logs`) |
| Sessions | `mason sessions browse` (reads state.db) |
