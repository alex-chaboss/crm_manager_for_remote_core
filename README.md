## CRM Remote Core (summary)

Desktop helper (PyQt6) for the workflow **sync server payload → local git repo → push → SSH pull + restart**. Each **project** under `Projects/` includes `project_core` (full tree), `remote_server_core` (files that belong on the VPS), `boss_server` (working copy for `git push`), **`project-widget/`** (optional **full replacement** of the project panel via `base_project_widget.py`: `build` or class `CRMProjectTab`; on failure — standard three tabs), and `create_git_repo.sh` (server-side bare + clone template). The `Projects/` tree is **gitignored** in this repo; on first launch, if `Projects/` is missing or empty, three example skeletons are created. **License:** [LICENSE](LICENSE) — **CC BY-NC 4.0** (non-commercial use only); **software use / liability:** [DISCLAIMER.md](DISCLAIMER.md). **Run:** from this directory, create `.venv` if needed (`python3 -m venv .venv`), then `.venv/bin/python3 -m pip install -r requirements.txt`, then `.venv/bin/python3 main.py` (ensure `ssh` is on `PATH`). **Custom project UI:** [docs/project_widget_contract.md](docs/project_widget_contract.md), [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md), roadmap [docs/deploy_roadmap.md](docs/deploy_roadmap.md).

### Market analogs (short)

| Product | Role |
|--------|------|
| [Semaphore UI](https://semaphoreui.com/) | Web UI for Ansible/Terraform, teams, RBAC |
| Jenkins / GitLab CI / GitHub Actions | Pipeline-centric CI/CD, not a small PyQt desktop |
| [Ansible AWX](https://github.com/ansible/awx) | Enterprise web UI over Ansible |
| Capistrano / Deployer | Classic push-to-deploy over SSH from CLI |
| [Coolify](https://coolify.io/) | Self-hosted PaaS with UI, container-centric |

**CRM positioning:** lightweight **local** desktop, fixed on-disk layout (`project_core` / `remote_server_core` / `boss_server`), no mandatory web stack; you edit server slice locally, push, then refresh the service over SSH.

---

## CRM Remote Core (полное описание на русском)

### Назначение

Отдельное десктоп-приложение для сценария: **канон серверных файлов** (`remote_server_core`) копируется в репозиторий **`boss_server`**, затем **`git push`**, затем по **SSH** на VPS выполняется **`git pull`** (и при необходимости stash) и **команда перезапуска** (например `systemctl restart …`). Подходит как основа «квикстарта» для выкладки произвольных проектов, не только торговых систем.

### Архитектура каталогов

- **`crm/`** — Python-пакет: конфиг, sync/push, SSH, инициализация скелетов, GUI.
- **`Projects/`** — рабочая зона проектов; **не коммитится** в git (см. `.gitignore`). При **первом запуске**, если каталога нет или он пуст, создаются проекты-шаблоны: `simple_game_example`, `simple_service_example`, `simple_site_example`.
- У **каждого** проекта пять элементов:
  1. **`project_core/`** — полный исходник приложения (клон сюда вручную).
  2. **`remote_server_core/`** — только то, что должно оказаться на сервере.
  3. **`boss_server/`** — рабочая копия для push (содержимое как у `remote_server_core`, плюс `.git` после настройки remotes).
  4. **`project-widget/`** — опционально **полностью подменяет** панель выбранного проекта (`base_project_widget.py`: функция **`build`** или класс **`CRMProjectTab`**; при ошибке — три вкладки CRM по умолчанию). См. [docs/project_widget_contract.md](docs/project_widget_contract.md), [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md). Долгосрочный деплой: [docs/deploy_roadmap.md](docs/deploy_roadmap.md).
  5. **`create_git_repo.sh`** — шаблон скрипта для создания bare-репозитория и рабочей копии **на сервере**; ориентир на запуск в одну SSH-сессию (`ssh user@host 'bash -s' < …/create_git_repo.sh`). Перед запуском задайте на сервере переменную **`CRM_SERVER_BASE`** (см. комментарии в скрипте). Не используйте `chmod 777` из старых примеров без необходимости.

### GUI

- **Слева:** глобальные параметры SSH (хост, **порт** — пусто = 22, нестандартный через поле), рабочая директория на сервере для `cd`, remote, ветка, команда после `git pull`, таймаут. Изменения **автоматически** пишутся в `.cache/global_settings.json` (с небольшой задержкой); кнопка «Сохранить» — немедленная запись и подтверждение.
- **Справа:** в шапке — **язык интерфейса** (ru/en) и вкладки **по одному на проекту**; кнопка **«+»** — новый скелет. **Область выбранного проекта** целиком задаётся `Projects/<id>/project-widget/` (см. контракт); при сбое загрузки — стандартные **Настройки** (форма путей, Sync, SSH, лог), **Метрики** и **Health** (заглушки). Контракт: [docs/project_widget_contract.md](docs/project_widget_contract.md).

### Конфигурация

- Глобальные настройки: `.cache/global_settings.json` (в т.ч. `ui_locale`: `ru` | `en`, `ssh_port` — строка, пусто = порт 22). Файл создаётся/обновляется при работе GUI (автосохранение и по кнопке).
- Профиль проекта: `Projects/<id>/project_profile.json` (override путей, SSH **хост** `user@host`, **порт**, `ssh_work_dir`, git и т.д.; пустые строки = взять из глобальных). Только в каталоге соответствующего проекта.

### Лицензия

См. файл **[LICENSE](LICENSE)** — **CC BY-NC 4.0** (некоммерческое использование; ссылка на полный юридический текст Creative Commons). Риски использования ПО и ограничение ответственности — в **[DISCLAIMER.md](DISCLAIMER.md)**.

### Требования

- Python **3.10+**
- **`ssh`** в `PATH`, доступ по ключу к хосту
- Зависимости: рекомендуется виртуальное окружение `.venv/`:  
  `python3 -m venv .venv && .venv/bin/python3 -m pip install -r requirements.txt`

### Запуск

```bash
cd to_project_path
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
.venv/bin/python3 main.py
```

### Перенос на другую машину

Скопируйте каталог приложения и **вручную** папку **`Projects/`** (она не в git).

### Проверка после установки

```bash
.venv/bin/python3 -m py_compile crm/*.py crm/gui/*.py crm/project_widget_loader.py main.py
```

GUI smoke: вручную после `.venv/bin/python3 main.py`.
