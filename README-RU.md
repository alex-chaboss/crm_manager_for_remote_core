# CRM Remote Core

**Язык:** [English](README.md) · Русский (этот файл)

Десктоп-помощник (**PyQt6**) для соло-разработчика: держать локальный «серверный срез» приложения, выкладывать его на VPS через **git + SSH** и выполнять pre/post-команды (сборка, `.env`, `pm2` и т.п.) без полноценного CI/CD.

---

## Статус / отказ от ответственности (прочитайте сначала)

Проект **свежий, недотестированный и сырой**. Я делал его **под свой рабочий процесс**. Если решите попробовать — **на свой страх и риск**. См. [DISCLAIMER.md](DISCLAIMER.md) и [LICENSE](LICENSE) (**CC BY-NC 4.0**).

Правила Cursor в `.cursor/rules/` настроены **под меня** (в том числе упоминают мои приватные приложения). Если они вам не нужны — **просто удалите эти файлы**: приложение от них не зависит.

Реальные приложения лежат в **`Projects/`** — каталог в **`.gitignore`** и **не публикуется** вместе с этим репозиторием.

---

## Что это и зачем

Типовой поток:

1. Полный исходник в локальном **`project_core/`** (git clone).
2. Только то, что должно оказаться на сервере — в **`remote_server_core/`** (и копия для push в **`boss_server/`**).
3. Одна кнопка **«Деплой»**: опциональный Auto Sync → синхронизация в `boss_server` → **`git push`** → на сервере hook **post-update** (`git pull` в рабочую копию) → SSH-команды **post_deploy** / перезапуск.

**Позиционирование:** лёгкий **локальный** десктоп с фиксированной раскладкой каталогов. Это не Semaphore/Jenkins/Coolify — без обязательного веб-UI и командного RBAC.

| Аналог | Роль |
|--------|------|
| [Semaphore UI](https://semaphoreui.com/) | Веб-UI для Ansible/Terraform |
| Jenkins / GitLab CI / GitHub Actions | Pipeline-ориентированный CI/CD |
| Capistrano / Deployer | Классический push-to-deploy по SSH из CLI |
| [Coolify](https://coolify.io/) | Self-hosted PaaS с UI |

---

## Требования

- Python **3.10+**
- **`ssh`** в `PATH`, доступ к хосту по ключу
- По желанию: `bash` для строк `local-sh:` / `server-sh:`

```bash
cd /path/to/crm_manager_for_remote_core
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
.venv/bin/python3 main.py
```

Язык UI: **ru** / **en** в глобальной панели (`ui_locale` в `.cache/global_settings.json`).

---

## Быстрый старт (GUI)

### 1. Первый запуск

- Если `Projects/` нет или он пуст, CRM создаёт примеры: `simple_game_example`, `simple_service_example`, `simple_site_example`.
- **Слева:** глобальный SSH и глобальные списки pre/post (автосохранение в `.cache/global_settings.json`).
- **Справа:** вкладки проектов. **`+`** — новый скелет.
- **`⚙`** на вкладке проекта — **настройки проекта** (клон, init, деплой, пути, секреты). Кастомный виджет **не** содержит форму деплоя.

### 2. Глобальный SSH (слева)

Минимум:

- **SSH хост** — `user@hostname` или `user@IP`
- **Базовый путь на сервере** — каталог на VPS, где будут `$PROJECT_NAME` и `$PROJECT_NAME.git` (это `MY_MAIN_PATH`)
- По желанию: порт, команда перезапуска, таймаут, глобальные списки команд

### 3. Настройки проекта (`⚙`)

1. **URL исходного git** → **Клонировать в project_core** (или положите дерево вручную в `Projects/<id>/project_core/`).
2. Задайте **базовый путь** / **имя проекта на сервере** (базовый путь можно взять из глобальных).
3. Вкладка **«Из ядра на remote»**: отметьте файлы/папки из `project_core`, которые должны жить на сервере → **Применить выбранные пути** (копия в `remote_server_core` и `boss_server`). Включите **Auto Sync**, если это нужно перед каждым Деплоем.
4. При необходимости укажите **файл секретов** (см. ниже) — лучше **вне** `Projects/` и вне любого git-репозитория.
5. Заполните списки **pre_init / post_init / pre_deploy / post_deploy**.
6. Один раз нажмите **«Инициализация на сервере»** (bare + рабочая копия + hook, привязка локального `boss_server`).
7. Дальше — **«Деплой»**.

Долгие операции открывают **модальный лог** (копировать, Стоп, экспорт). Закрытие — только после завершения/отмены. **Стоп не откатывает** уже выполненные шаги на VPS.

### 4. Перенос на другую машину

Скопируйте каталог приложения **и вручную** папку **`Projects/`** (её нет в git).

---

## Структура каталогов

| Путь | Назначение |
|------|------------|
| `crm/` | Пакет приложения (GUI, sync, SSH, конфиг) |
| `Projects/<id>/` | **Ваша** рабочая зона (в gitignore) |
| `Projects/<id>/project_core/` | Полный исходник |
| `Projects/<id>/remote_server_core/` | Серверный срез (канон) |
| `Projects/<id>/boss_server/` | Рабочая копия git для **push** |
| `Projects/<id>/project-widget/` | Опциональный UI вкладки проекта |
| `Projects/<id>/create_git_repo.sh` | Скрипт init на сервере (из шаблона) |
| `scripts/create_git_repo.sh` | Канонический шаблон в этом репозитории |
| `.cache/` | Глобальные настройки (gitignore) |

---

## Описание полей настроек (простыми словами)

### Глобальные (левая панель)

| Поле | Зачем |
|------|--------|
| **SSH хост** | Общий `user@host` для проектов |
| **SSH порт** | Пусто = 22 |
| **Рабочая папка на сервере** | Куда по умолчанию делать `cd` (рабочая копия). Часто пусто — тогда берётся `$base/$project_name` |
| **Git remote / branch** | Значения по умолчанию для привязки `boss_server` / контекста hook |
| **Команда перезапуска** | SSH после деплоя; `true` — пропустить |
| **Таймаут SSH** | Секунды для SSH **и** длинных локальных команд (`local-sh:`) |
| **Базовый путь на сервере по умолчанию** | Дефолтный `MY_MAIN_PATH` |
| **Глобальные pre_init / post_init / pre_deploy / post_deploy** | Общие списки команд (см. правила мержа ниже) |

Файл: `.cache/global_settings.json`.

### Проект (`⚙` → настройки)

| Поле | Зачем |
|------|--------|
| **URL исходного git** | Откуда клонировать в **project_core** |
| **Файл секретов** | Путь к файлу со строками `<$name>=значение` (в профиле хранится только **путь**) |
| **Базовый путь (`MY_MAIN_PATH`)** | Родительский каталог на VPS |
| **Имя проекта на сервере (`PROJECT_NAME`)** | Имя папки / bare (по умолчанию — id локального проекта) |
| **Ветка на сервере (`GIT_BRANCH`)** | Ветка из скрипта init (часто `master`) |
| **Имя remote (`REMOTE_ALIAS`)** | Имя remote в рабочей копии на сервере (пусто = имя проекта) |
| **Auto Sync перед деплоем** | Перед push копировать отмеченные `core_sync_paths` из `project_core` |
| **remote_server_core / boss_server (абс. путь)** | Если каталоги не лежат под `Projects/<id>/` |
| **SSH host / port / work dir / restart / timeout (override)** | Пусто → из глобальных; timeout `0` → глобальный таймаут |
| **Мерж с Global commands** | Выкл (по умолчанию): если список проекта непустой — только он, иначе глобальный. Вкл: сначала **global, затем project** |
| **pre_init / post_init / pre_deploy / post_deploy** | Списки команд проекта |
| **«Из ядра на remote»** | Дерево `project_core` с чекбоксами → `core_sync_paths` |

Профиль: `Projects/<id>/.cache/project_profile.json` (автосохранение и кнопка «Сохранить»).

### Префиксы строк в списках команд

Каждая **строка** — отдельный шаг.

| Префикс | Где | Поведение |
|---------|-----|-----------|
| `local-sh:` | Ваш ПК | `bash -lc` — можно `cd`, `&&`, пайпы |
| `local:` | Ваш ПК | Одна программа + аргументы (**без** shell); не пишите `cd && …` |
| `server-sh:` | VPS | SSH + `bash -s` (скрипт на stdin, как heredoc) |
| `server:` или без префикса | VPS | Одна SSH-команда |

Примеры:

```text
local-sh:cd project_core/front && npm i --legacy-peer-deps && npm run build
local:npm i --prefix project_core/front
server-sh:export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
cd /var/www/html/my_app
pm2 restart my_app
server:mkdir -p /var/www/html/my_app/logs
```

Каталог для `local:` / `local-sh:` — корень проекта `Projects/<id>/`. Между строками **нет** общего shell: цепочку делайте в **одной** строке `local-sh:` или через `--prefix`.

Кнопка **«Тест: pre_deploy»** прогоняет объединённый pre_deploy без полного деплоя (удобно отладить сборку и секреты).

---

## Скрипт `create_git_repo.sh` — что и зачем

Одноразовая **инициализация remote git** на VPS:

1. Создаёт bare `$MY_MAIN_PATH/$PROJECT_NAME.git`
2. Создаёт рабочую копию `$MY_MAIN_PATH/$PROJECT_NAME`
3. Делает начальный commit и push в bare
4. Ставит hook **`post-update`**: при каждом push в bare выполняется `git pull` в рабочую копию

Дальше **Деплой** с локального `boss_server` сводится к **`git push`**: файлы на сервере обновляет hook.

Кнопка CRM **«Инициализация на сервере»** гоняет скрипт по SSH (с переменными окружения), затем привязывает локальный `boss_server` (`fetch` / `checkout` / **`pull`** / upstream). Без этого `pull` первый Деплой часто падает с **non-fast-forward**.

Вручную:

```bash
export MY_MAIN_PATH=/var/www/html/crm_projects
export PROJECT_NAME=my_app
export GIT_BRANCH=master   # опционально
ssh user@host 'bash -s' < Projects/my_app/create_git_repo.sh
```

Обновить устаревшие копии скрипта в существующих проектах:

```bash
.venv/bin/python3 -c "from crm.maintenance import refresh_create_git_repo_scripts; print(refresh_create_git_repo_scripts())"
```

**Замечание:** в историческом шаблоне есть `chmod 777` — на проде при необходимости ужесточите права. Отмена в UI **не откатывает** уже созданный bare/hook.

---

## Pre/post init и deploy + файл секретов

### Когда выполняются списки

| Фаза | Когда |
|------|--------|
| **pre_init** | Перед `create_git_repo.sh` при **«Инициализация на сервере»** |
| **post_init** | После скрипта и привязки `boss_server` |
| **pre_deploy** | Перед sync/push при **«Деплой»** |
| **post_deploy** | После успешного push (затем опциональная команда перезапуска) |

Типичные задачи: поставить пакеты, записать `.env` на сервере, собрать фронт локально, `pm2 restart`, миграции и т.д.

### Зачем нужен файл секретов?

Списки команд и `project_profile.json` удобны — и легко утекают в git, бэкапы или в чаты «вайб-кодинга», если туда вписать живые пароли.

В тексте команд остаются **маркеры** вида `<$db_password>`. Значения подставляются:

1. из **файла секретов**, указанного в `⚙` (чтение в **RAM** на время операции), и/или  
2. из диалога ввода, если маркера в файле нет.

В логе операции известные **значения** секретов заменяются на `***`. В профиле хранится только **путь** к файлу, не содержимое.

### Куда класть файл

- Лучше **вне** `Projects/` и **вне** любого репозитория (например `~/secrets/my_app_crm_secrets.txt`).
- **Не коммитьте** его. Желательно не держать там, где Cursor/агенты индексируют дерево проекта.
- Если копия всё же рядом — добавьте локальные ignore-правила (в этом репо уже игнорируются `.env` и `Projects/`).

### Формат файла

```text
# Комментарии и пустые строки допустимы
<$db_password>=замените_меня
<$pm2_user>=deploy
<$api_token>=tok_xxx
# В значении может быть символ '='
<$dsn>=user=x password=y host=z
```

Правила: одна строка `<$name>=значение`; `name` — из `\w+`; пустые значения пропускаются; при дубликатах имён побеждает последняя строка.

### Примеры с секретами

**post_init — создать `.env` на сервере (пароли не писать в список команд):**

```text
server-sh:cat > "$HOME/apps/my_app/.env" <<EOF
DATABASE_URL=postgres://app:<$db_password>@127.0.0.1:5432/app
API_TOKEN=<$api_token>
EOF
chmod 600 "$HOME/apps/my_app/.env"
```

**pre_deploy — локальная сборка фронта (без секрета):**

```text
local-sh:cd project_core/front && npm ci && npm run build
```

**post_deploy — перезапуск с токеном в env (в логе будет `***`):**

```text
server-sh:export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
cd /var/www/html/my_app
GAME_ADMIN_TOKEN=<$api_token> pm2 restart my_app --update-env
```

Укажите файл через **«Обзор…»** в `⚙`, после правок нажмите **перезагрузку**. Если путь битый в момент Деплоя — CRM предупредит и запросит недостающие маркеры вручную.

---

## Короткая инструкция: виджет отдельного проекта

Кастомный UI — в `Projects/<id>/project-widget/`.

1. Зарезервированный файл: **`base_project_widget.py`**.
2. Точка входа: функция **`build(parent, project_id, main_window) -> QWidget`** или класс **`CRMProjectTab(project_id, main_window, parent=None)`** (если есть оба — побеждает **`build`**).
3. Шаблон: `crm/templates/project_widget/default/` или примеры в `crm/templates/project_widget/examples/`.
4. Соседние модули: обычный `import game_ui` — загрузчик временно добавляет `project-widget/` в `sys.path`.
5. Деплой / Clone / Init — только через **`⚙`**; в виджете достаточно подсказки (`ProjectSettingsHint`).
6. Не блокируйте GUI в `build` / `__init__`; длинные операции — через API CRM.

Подробнее: [docs/project_widget_contract.md](docs/project_widget_contract.md), [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md).

---

## Пайплайн деплоя (одна кнопка)

1. `pre_deploy_commands` (с учётом мержа)
2. Auto Sync (если включён)
3. Подготовка рабочей копии на VPS (`git stash` при грязном дереве, затем `git pull`)
4. `remote_server_core` → `boss_server`, commit, **`git push`** → **post-update** на VPS
5. `post_deploy_commands` + команда перезапуска (если не `true`)

Дорожная карта: [docs/deploy_roadmap.md](docs/deploy_roadmap.md).

---

## Лицензия

[LICENSE](LICENSE) — **CC BY-NC 4.0**. Риски: [DISCLAIMER.md](DISCLAIMER.md). Коммерческое использование / платные доработки: **alex.chaboss@gmail.com**.

---

## Дополнительные документы

- [docs/project_widget_contract.md](docs/project_widget_contract.md)
- [docs/project_widget_setup_and_git.md](docs/project_widget_setup_and_git.md)
- [docs/deploy_roadmap.md](docs/deploy_roadmap.md)
- [README.md](README.md) — английская базовая версия
