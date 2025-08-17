
# OrbStack + Alfred Workflow: PRD and Technical Specification
_Last updated: 2025-08-17 20:42:45 UTC_

## 1) Summary
Build an Alfred workflow that enumerates Docker containers running under OrbStack on macOS, displays their state in Alfred, and provides fast actions such as opening the container's `orb.local` URL, starting or stopping containers, viewing logs, and attaching a shell. The workflow should rely on the Docker CLI as the primary interface and derive `orb.local` domains using container and Compose labels. It must be fast, robust, and require no persistent background daemon.

## 2) Goals
- List **running** and **stopped** containers with clear status, project, and service details.
- Open the related `orb.local` URL for a container with a single keystroke.
- One‑key lifecycle controls: start, stop, restart.
- Quick access actions: attach interactive shell, tail logs, copy names and URLs, reveal Compose project group.
- Project‑level batch actions: start/stop all containers in a Compose project.
- Work out of the box on OrbStack without any manual configuration.

## 3) Non‑Goals
- Managing non‑OrbStack Docker hosts over SSH.
- Full Kubernetes UI. K8s is optional and read‑only if added later.
- A general purpose Docker Desktop replacement.

## 4) Target Users and Key Use Cases
- Developer or marketer running local web apps in containers and wanting to jump to the right local URL quickly.
- Power user wanting to start/stop stacks without switching to OrbStack GUI or the terminal.
- Troubleshooting a stack, needing one‑tap logs or a shell.

## 5) High‑Level UX
- Alfred keyword: `orb`.
- A Script Filter lists containers grouped by state: **Running** first, then **Stopped**.
- Each row shows: `title = service or container`, `subtitle = project • state • ports • health`.
- **Enter** defaults to opening the `https://{domain}.orb.local/` if we believe it is a web service, otherwise focuses on `docker exec` shell.
- **Cmd** opens the `orb.local` URL unconditionally.
- **Opt** toggles start/stop depending on current state.
- **Ctrl** shows recent logs.
- **Shift** copies the `orb.local` URL to clipboard.
- Universal Actions supported for text containing container IDs or names.

## 6) Scope
### In‑scope
- Container discovery via `docker ps --all`.
- Attribute enrichment via `docker inspect` in batched calls.
- Derivation of orb.local domains:
  - Compose: `service.project.orb.local`.
  - Single container: `{container_name}.orb.local`.
- URL open over HTTPS by default.
- Lifecycle controls: start, stop, restart.
- Logs: `docker logs --since=10m --tail=200` in a terminal window.
- Shell: `docker exec -it <container> /bin/sh` (fallback to `/bin/bash` if present).
- Project actions using the shared Compose project label.
- Optional resource snapshot via `docker stats --no-stream` displayed in subtitles.

### Out‑of‑scope (v1)
- Authenticated endpoints inside the container.
- Persisted settings UI beyond a simple env file.

## 7) Assumptions and Dependencies
- macOS 13 or newer, Alfred 5+, OrbStack installed with its Docker context configured as default.
- Docker CLI available in PATH for Alfred’s shell (`/opt/homebrew/bin` on Apple Silicon, `/usr/local/bin` on Intel). 
- User’s browser handles `.orb.local` with OrbStack’s local DNS and TLS.
- No root privileges required.

## 8) Data Model and Discovery
- Primary list: `docker ps --all --format '{{json .}}'` returns one JSON object per line with fields: ID, Names, Image, Status, Labels, Ports.
- Enrichment: `docker inspect --format '{{json .}}' $(docker ps -aq)` to obtain:
  - `.Config.Labels["com.docker.compose.project"]` (project)
  - `.Config.Labels["com.docker.compose.service"]` (service)
  - `.State.Health.Status` (if present)
  - `.NetworkSettings.Networks` for IP and network presence
  - `.Config.Entrypoint` and `.Config.Cmd` (optional display)
  - `.Config.ExposedPorts` and `.HostConfig.PortBindings`
- Resource snapshot: `docker stats --no-stream --format '{{.Container}} {{.CPUPerc}} {{.MemUsage}}'`.

## 9) Orb.local URL Derivation
1. If both `project` and `service` labels exist, domain is `service.project.orb.local`.
2. Else, domain is `container_name.orb.local`.
3. Always prefix `https://` and do not append a port.
4. A container is likely a web service if any of the following heuristics are true:
   - Exposes port 80 or 443, or maps any container port to host.
   - Name or service contains `web`, `app`, `frontend`, or `ui`.
   - Image contains `nginx`, `httpd`, `caddy`, `traefik`, `node`, or `python` web servers.
5. Heuristic confidence controls the default action for **Enter**.

## 10) Alfred Workflow Architecture
- **Script Filter** (Python recommended) for the `orb` keyword:
  - Produces an `items` JSON array of rows with fields:
    - `title`, `subtitle`, `arg` (JSON string), `uid` (container ID), `autocomplete`, `valid`.
    - `icon` variant based on state (green for running, grey for stopped).
    - `mods`:
      - `cmd`: open URL.
      - `alt`: start/stop.
      - `ctrl`: show logs.
      - `shift`: copy URL.
    - `variables`: pass container metadata for downstream actions.
- **Action scripts**: a single dispatcher script reads `{{action, container_id, container_name, project, service, url}}` from `arg` JSON and executes the requested command.
- **External Triggers** provide callable entry points for other workflows or Hotkeys.
- **Caching**: write a small JSON cache under `~/Library/Caches/com.yourdomain.orb-alfred/containers.json` with a TTL of 2 seconds to keep the UI snappy.

## 11) Commands and Snippets
- List all containers:
  ```bash
  docker ps --all --format '{{json .}}'
  ```
- Inspect in batch:
  ```bash
  docker inspect --format '{{json .}}' $(docker ps -aq)
  ```
- Health:
  ```bash
  docker inspect -f '{{.State.Health.Status}}' <id> || echo "unknown"
  ```
- Lifecycle:
  ```bash
  docker start <id> ; docker stop <id> ; docker restart <id>
  ```
- Logs and shell:
  ```bash
  docker logs --since=10m --tail=200 <id>
  docker exec -it <id> /bin/sh
  ```
- Project batch actions:
  ```bash
  docker ps -aq --filter "label=com.docker.compose.project=<project>"
  docker start $(docker ps -aq --filter "label=com.docker.compose.project=<project>")
  ```
- Open URL:
  ```bash
  open "https://{domain}.orb.local/"
  ```

## 12) Error Handling
- **Docker not found**: detect with `command -v docker || echo "notfound"`. Show a single Alfred item explaining how to add `/opt/homebrew/bin` to PATH in Alfred.
- **No containers**: show a friendly empty state item.
- **URL likely unreachable**: still offer open action, plus a note to check the container’s ports.
- **Permission denied**: surface stderr in a Large Type panel or macOS notification.
- **Long operations**: show Alfred workflow progress text.
- **Non‑zero exit** from actions: include the exit code and the short stderr snippet.

## 13) Performance
- Heavy calls (`docker inspect`, `docker stats`) are batched and cached.
- Defer `docker stats` until the user focuses the item, or compute once per invocation.
- All shell calls must time out within 800 ms for the initial list.

## 14) Security and Privacy
- No network calls beyond `open https://*.orb.local/` in the default browser.
- Do not log command output by default. Provide an optional `DEBUG=1` env var to log to `~/Library/Logs/orb-alfred.log`.
- Do not store secrets. Redact environment values in any debug dump.

## 15) Configuration
- A simple `.env` file in the workflow directory with:
  - `DEFAULT_OPEN_ACTION=auto|url|shell`
  - `URL_SCHEME=https`
  - `LOGS_SINCE=10m`
  - `CACHE_TTL_MS=2000`
  - `FALLBACK_SHELL=/bin/sh`
- Optional allow‑list of service name keywords that imply “web”.

## 16) Deliverables for the AI Agent
Repository layout:
```
orbstack-alfred/
  README.md
  LICENSE
  workflow/
    info.plist                 # Alfred bundle
    icon.png
    scripts/
      script_filter.py         # lists containers
      dispatcher.py            # performs actions
      helpers.py               # parsing, URL derivation, caching
    .env.example
  tests/
    fixtures/
      docker_ps_all.jsonl
      docker_inspect_all.json
    test_url_derivation.py
    test_parsing.py
    test_actions.py
```

Tasks:
1. Create Python scripts with no external dependencies beyond the standard library.
2. Implement container discovery, enrichment, and caching.
3. Implement URL derivation logic and heuristics.
4. Implement Alfred Script Filter JSON output.
5. Implement dispatcher actions for URL open, start/stop/restart, logs, shell, copy.
6. Add project batch actions.
7. Build `info.plist` for Alfred with keyword, Script Filter, Run Script, and External Triggers.
8. Add tests using fixtures that mimic `docker` output.
9. Write `README.md` with installation, permissions, and troubleshooting notes.
10. Package as an `.alfredworkflow` export.

## 17) Acceptance Criteria
- Typing `orb` in Alfred lists containers within 1 second on a machine with 10–20 containers.
- Running containers appear above stopped containers.
- Pressing **Cmd** on any item opens `https://<derived-domain>/` in the default browser.
- **Opt** starts a stopped container, **Opt** on a running container stops it, with success feedback.
- **Ctrl** opens a terminal window tailing the last 200 log lines.
- **Enter** opens URL for web‑like services and opens shell otherwise, based on the heuristics.
- Project batch actions are visible when multiple containers share a project label.
- The workflow works without any changes on a clean OrbStack install.
- No crashes on containers without Compose labels.

## 18) Test Plan
- **Unit**: URL derivation for Compose and non‑Compose containers, health extraction, stats parsing.
- **Integration**: Run against mocked `docker` outputs using fixtures.
- **Manual**: With a Compose project like `0089-dramdeals` having services `web` and `web_db`, verify URLs `web.0089-dramdeals.orb.local` and `web_db.0089-dramdeals.orb.local` open.
- **Edge cases**: Containers with spaces or underscores, no ports, unhealthy state, restarting loop, very long names.
- **Performance**: Cold run < 1200 ms, warm run < 400 ms.

## 19) Future Enhancements
- Optional Kubernetes discovery, surfacing `*.k8s.orb.local` services if present.
- Open the container in iTerm’s split pane instead of a new window.
- “Reveal project” action that opens the project folder in Finder, derived from a label like `working_dir` if present.
- Small status menu bar extra using the same Python code for visibility outside Alfred.
- Basic metrics overlay using `docker stats` with top offenders.

## 20) Appendix
### 20.1 Example Alfred item (JSON)
```json
{
  "title": "web",
  "subtitle": "0089-dramdeals • running • 0.7% CPU • healthy",
  "uid": "4f3c2d1e90a1",
  "arg": "{\"action\": \"default\", \"id\": \"4f3c2d1e90a1\", \"name\": \"0089-dramdeals-web\", \"project\": \"0089-dramdeals\", \"service\": \"web\", \"url\": \"https://web.0089-dramdeals.orb.local/\"}",
  "mods": {
    "cmd": {
      "subtitle": "Open https://web.0089-dramdeals.orb.local/",
      "arg": "{\"action\": \"open_url\", \"id\": \"4f3c2d1e90a1\", \"url\": \"https://web.0089-dramdeals.orb.local/\"}"
    },
    "alt": {
      "subtitle": "Stop container",
      "arg": "{\"action\": \"toggle\", \"id\": \"4f3c2d1e90a1\"}"
    },
    "ctrl": {
      "subtitle": "Tail logs",
      "arg": "{\"action\": \"logs\", \"id\": \"4f3c2d1e90a1\"}"
    },
    "shift": {
      "subtitle": "Copy orb.local URL",
      "arg": "{\"action\": \"copy_url\", \"url\": \"https://web.0089-dramdeals.orb.local/\"}"
    }
  }
}
```

### 20.2 Heuristic examples
- `web` service exposing 80/443 ⇒ default Enter opens URL.
- `web_db` with no exposed ports ⇒ default Enter opens shell.

---

**End of document.**
