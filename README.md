# CRM Remote Core

**Language:** English (this file) · [Русский (полный перевод)](README-RU.md)

Desktop helper (**PyQt6**) for a solo developer: keep a local “server slice” of an app, push it to a VPS over **git + SSH**, and run pre/post hooks (build, env files, `pm2`, etc.) without a full CI/CD stack.

---

## Status / disclaimer (read first)

This project is **fresh, under-tested, and rough around the edges**. I built it **for my own workflow**. If you try it, you do so **at your own risk** — see [DISCLAIMER.md](DISCLAIMER.md) and [LICENSE](LICENSE) (**CC BY-NC 4.0**).

Cursor rules under `.cursor/rules/` are tuned **for me** (including rules that mention private apps). If you do not need them, **delete those files** — the app does not depend on them.

Your real apps live under **`Projects/`**, which is **gitignored** and is **not** published with this repository.

---

## What it is and why it exists

Typical flow:

1. Full source in local **`project_core/`** (git clone).
2. Only the server-facing tree in **`remote_server_core/`** (and a push copy in **`boss_server/`**).
3. One **Deploy** button: optional Auto Sync → sync to `boss_server` → **`git push`** → server **post-update** hook (`git pull` into the work tree) → **post_deploy** SSH commands / restart.

**Positioning:** a small **local** desktop tool with a fixed on-disk layout. Not Semaphore/Jenkins/Coolify — no mandatory web UI or team RBAC.

| Analog | Role |
|--------|------|
| [Semaphore UI](https://semaphoreui.com/) | Web UI for Ansible/Terraform |
| Jenkins / GitLab CI / GitHub Actions | Pipeline-centric CI/CD |
| Capistrano / Deployer | CLI push-to-deploy over SSH |
| [Coolify](https://coolify.io/) | Self-hosted PaaS |

---

## Requirements

- Python **3.10+**
- **`ssh`** in `PATH`, key-based access to the host
- Optional: `bash` for `local-sh:` / `server-sh:` command lines

```bash
cd /path/to/crm_manager_for_remote_core
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
.venv/bin/python3 main.py
```

UI language: **ru** / **en** in the global panel (`ui_locale` in `.cache/global_settings.json`).

---

## Quick start (GUI)

### 1. First launch

- If `Projects/` is missing or empty, CRM creates example skeletons: `simple_game_example`, `simple_service_example`, `simple_site_example`.
- **Left panel:** global SSH defaults and global pre/post command lists (auto-saved to `.cache/global_settings.json`).
- **Right:** project tabs. **`+`** creates a new empty project skeleton.
- **`⚙`** on a project tab opens **project settings** (clone, init, deploy, paths, secrets). Custom widgets do **not** own deploy UI.

### 2. Global SSH (left)

Fill at least:

- **SSH host** — `user@hostname` or `user@IP`
- **Server base path** — directory on the VPS that will hold `$PROJECT_NAME` and `$PROJECT_NAME.git` (this is `MY_MAIN_PATH`)
- Optional: port, default restart command, timeout, global command lists

### 3. Project settings (`⚙`)

1. **Source git URL** → **Clone into project_core** (or copy your tree manually into `Projects/<id>/project_core/`).
2. Set **Server base path** / **Server project name** (or inherit base from global).
3. Tab **“From core to remote”**: check files/folders from `project_core` that should live on the server → **Apply selected paths** (copies into `remote_server_core` and `boss_server`). Enable **Auto Sync** if you want this before every Deploy.
4. Optionally attach a **secrets file** (see below) — keep it **outside** `Projects/` and outside any git repo.
5. Fill **pre_init / post_init / pre_deploy / post_deploy** lists as needed.
6. **Initialize on server** once (creates bare + work tree + hook, binds local `boss_server`).
7. Later: **Deploy**.

Long operations open a **modal log** (copy, Stop, export). Closing is allowed only after finish/cancel. Stop does **not** roll back steps already done on the VPS.

### 4. Moving to another machine

Copy the CRM app **and** your **`Projects/`** folder manually (`Projects/` is not in git).

---

## Directory layout

| Path | Role |
|------|------|
| `crm/` | Application package (GUI, sync, SSH, config) |
| `Projects/<id>/` | **Your** work (gitignored) |
| `Projects/<id>/project_core/` | Full app source |
| `Projects/<id>/remote_server_core/` | Server slice (canon) |
| `Projects/<id>/boss_server/` | Git working copy used for **push** |
| `Projects/<id>/project-widget/` | Optional custom project UI |
| `Projects/<id>/create_git_repo.sh` | Server init script (from template) |
| `scripts/create_git_repo.sh` | Canonical template in this repo |
| `.cache/` | Global settings (gitignored) |

---

## Settings reference (plain language)

### Global (left panel)

| Field | What it does |
|-------|----------------|
| **SSH host** | Default `user@host` for all projects |
| **SSH port** | Empty = 22 |
| **Server working directory** | Default `cd` target on the server (work tree). Often left empty and derived as `$base/$project_name` |
| **Git remote / branch** | Defaults used when binding `boss_server` / hooks context |
| **Restart command** | Run after deploy over SSH; `true` = skip |
| **SSH timeout** | Seconds for SSH **and** long local commands (`local-sh:`) |
| **Default server base path** | Default `MY_MAIN_PATH` |
| **Global pre_init / post_init / pre_deploy / post_deploy** | Shared command lists (see merge rules below) |

Saved to `.cache/global_settings.json`.

### Project (`⚙` → Settings)

| Field | What it does |
|-------|----------------|
| **Source git URL** | Clone target for **Clone into project_core** |
| **Secrets file** | Path to a local file with `<$name>=value` lines (only the **path** is stored in the profile) |
| **Server base path (`MY_MAIN_PATH`)** | Parent directory on the VPS |
| **Server project name (`PROJECT_NAME`)** | Folder / bare name on the VPS (defaults to local project id) |
| **Server branch (`GIT_BRANCH`)** | Branch created by init script (default `master`) |
| **Remote alias (`REMOTE_ALIAS`)** | Remote name inside the server work tree (empty = project name) |
| **Auto Sync before deploy** | Copy checked `core_sync_paths` from `project_core` into remote/boss before push |
| **remote_server_core / boss_server (abs. path)** | Optional overrides if folders are not under `Projects/<id>/` |
| **SSH host / port / work dir / restart / timeout (override)** | Empty → use global; timeout `0` → use global timeout |
| **Merge with Global commands** | Off (default): use project list if non-empty, else global. On: run **global then project** |
| **pre_init / post_init / pre_deploy / post_deploy** | Per-project command lists |
| **From core to remote** | Tree of `project_core` with checkboxes → stored as `core_sync_paths` |

Profile file: `Projects/<id>/.cache/project_profile.json` (auto-save + Save).

### Command list prefixes

Each **line** is one step. Prefixes:

| Prefix | Where | Behavior |
|--------|-------|----------|
| `local-sh:` | Your PC | `bash -lc` — `cd`, `&&`, pipes OK |
| `local:` | Your PC | One program + args (**no** shell); no `cd && …` |
| `server-sh:` | VPS | SSH + `bash -s` (script on stdin, like a heredoc) |
| `server:` or no prefix | VPS | Single SSH command string |

Examples:

```text
local-sh:cd project_core/front && npm i --legacy-peer-deps && npm run build
local:npm i --prefix project_core/front
server-sh:export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
cd /var/www/html/my_app
pm2 restart my_app
server:mkdir -p /var/www/html/my_app/logs
```

Working directory for `local:` / `local-sh:` is the project root `Projects/<id>/`. Lines do **not** share a persistent shell between lines — chain with `local-sh:` on **one** line or use `--prefix`.

**Test: pre_deploy** runs the merged pre_deploy list without a full deploy (useful to debug builds/secrets).

---

## `create_git_repo.sh` — what and why

One-time **remote git bootstrap** on the VPS:

1. Creates bare repo `$MY_MAIN_PATH/$PROJECT_NAME.git`
2. Creates work tree `$MY_MAIN_PATH/$PROJECT_NAME`
3. Initial commit + push into bare
4. Installs **`post-update`** hook: on every push to bare, `git pull` into the work tree

So later **Deploy** only needs **`git push`** from local `boss_server`; the server work tree updates via the hook.

CRM button **Initialize on server** runs this over SSH (with env vars), then binds local `boss_server` (`fetch` / `checkout` / **`pull`** / upstream). Without that pull, the first Deploy often fails with **non-fast-forward**.

Manual:

```bash
export MY_MAIN_PATH=/var/www/html/crm_projects
export PROJECT_NAME=my_app
export GIT_BRANCH=master   # optional
ssh user@host 'bash -s' < Projects/my_app/create_git_repo.sh
```

Refresh outdated copies in existing projects:

```bash
.venv/bin/python3 -c "from crm.maintenance import refresh_create_git_repo_scripts; print(refresh_create_git_repo_scripts())"
```

**Note:** the historical template uses `chmod 777` — harden permissions on production if needed. Cancel in the UI does **not** undo bare/hook already created.

---

## Init / deploy command lists and the secrets file

### When lists run

| Phase | When |
|-------|------|
| **pre_init** | Before `create_git_repo.sh` during **Initialize on server** |
| **post_init** | After script + `boss_server` bind |
| **pre_deploy** | Before sync/push on **Deploy** |
| **post_deploy** | After successful push (then optional restart command) |

Use them for: install packages, write `.env` on the server, build assets locally, `pm2 restart`, migrations, etc.

### Why a secrets file?

Command lists and `project_profile.json` are convenient — and easy to leak into git, backups, or AI “vibe coding” chats if they contain real passwords.

**Markers** like `<$db_password>` stay in the command text. Values come from:

1. A **secrets file** you point to in `⚙` (loaded into **RAM** for the operation), and/or  
2. A password dialog for any marker still missing.

In the operation log, known secret **values** are replaced with `***`. The profile stores only the **path** to the file, not the contents.

### Recommended placement

- Keep the file **outside** `Projects/` and **outside** any repository (e.g. `~/secrets/my_app_crm_secrets.txt`).
- Do **not** commit it. Prefer not to put it where Cursor/agents index your project tree.
- Add local ignore patterns if you ever keep a copy nearby (this repo already ignores `.env` and `Projects/`).

### File format

```text
# Comments and blank lines are OK
<$db_password>=replace_me
<$pm2_user>=deploy
<$api_token>=tok_xxx
# Value may contain '='
<$dsn>=user=x password=y host=z
```

Rules: one `<$name>=value` per line; `name` is word characters (`\w+`); empty values are ignored; duplicate names — last wins.

### Examples with secrets

**post_init — create `.env` on the server (do not put real passwords in the list):**

```text
server-sh:cat > "$HOME/apps/my_app/.env" <<EOF
DATABASE_URL=postgres://app:<$db_password>@127.0.0.1:5432/app
API_TOKEN=<$api_token>
EOF
chmod 600 "$HOME/apps/my_app/.env"
```

**pre_deploy — local frontend build (no secret):**

```text
local-sh:cd project_core/front && npm ci && npm run build
```

**post_deploy — restart with token in env (masked in log):**

```text
server-sh:export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
cd /var/www/html/my_app
GAME_ADMIN_TOKEN=<$api_token> pm2 restart my_app --update-env
```

Browse the file in `⚙`, use **reload** after edits. If the path is wrong at Deploy time, CRM warns and prompts for missing markers.

---

## Editing a project widget (short)

Custom UI lives in `Projects/<id>/project-widget/`.

1. Reserved file: **`base_project_widget.py`**.
2. Prefer entry **`build(parent, project_id, main_window) -> QWidget`**, or class **`CRMProjectTab(project_id, main_window, parent=None)`** (if both exist, **`build` wins**).
3. Start from `crm/templates/project_widget/default/` or examples under `crm/templates/project_widget/examples/`.
4. Neighbor modules: `import game_ui` style imports work while the loader adds `project-widget/` to `sys.path`.
5. Deploy / Clone / Init stay in **`⚙`** — show a hint (`ProjectSettingsHint`) instead of duplicating the pipeline.
6. Do not block the GUI in `build` / `__init__`; use CRM operation APIs if you trigger long work.

Details: [docs/project_widget_contract.md](docs/project_widget_contract.md), [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md).

---

## Deploy pipeline (one button)

1. `pre_deploy_commands` (merged)
2. Auto Sync (if enabled)
3. Prepare server work tree (`git stash` if dirty, then `git pull`)
4. `remote_server_core` → `boss_server`, commit, **`git push`** → **post-update** pulls on VPS
5. `post_deploy_commands` + restart command (if not `true`)

More detail: [docs/deploy_roadmap.md](docs/deploy_roadmap.md).

---

## License

[LICENSE](LICENSE) — **CC BY-NC 4.0**. Risks: [DISCLAIMER.md](DISCLAIMER.md). Commercial use / paid custom work: contact **alex.chaboss@gmail.com**.

---

## Extra docs

- [docs/project_widget_contract.md](docs/project_widget_contract.md)
- [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md)
- [docs/deploy_roadmap.md](docs/deploy_roadmap.md)
- [README-RU.md](README-RU.md) — full Russian version of this guide
