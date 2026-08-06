# project-widget: установка, структура и remote git

## Структура каталога проекта

Для каждого проекта `Projects/<id>/` создаётся подкаталог **`project-widget/`** с зарезервированным файлом **`base_project_widget.py`**. Загрузчик [`crm/project_widget_loader.py`](../crm/project_widget_loader.py) подставляет результат в **всю область выбранного проекта** (см. [project_widget_contract.md](project_widget_contract.md)). При ошибке загрузки показывается **fallback**: подсказка про ⚙ и вкладки **Метрики** / **Health** (заглушки).

При создании нового скелета через кнопку «+» в GUI или при первом запуске (пустой `Projects/`) каталог **`project-widget/`** копируется из шаблона в репозитории:

- по умолчанию: `crm/templates/project_widget/default/`;
- для примеров `simple_game_example`, `simple_service_example`, `simple_site_example`: `crm/templates/project_widget/examples/<id>/`, если такая папка существует.

## Уже существующий локальный `Projects/`

Если проекты были созданы до появления `project-widget/`, скопируйте вручную содержимое `crm/templates/project_widget/default/` в `Projects/<id>/project-widget/` (или соответствующий пример из `examples/`), сохранив имя **`base_project_widget.py`**. После обновления репозитория перезапишите `Projects/<id>/project-widget/` из шаблонов при необходимости.

Если устарел **`create_git_repo.sh`** в проекте:

```bash
.venv/bin/python3 -c "from crm.maintenance import refresh_create_git_repo_scripts; print(refresh_create_git_repo_scripts())"
```

## PYTHONPATH и импорты

Приложение предполагается запускать **из корня репозитория** (`python main.py` или `python -m …`), чтобы пакет `crm` был доступен импорту. Внутри `base_project_widget.py` допускается `from crm... import ...` — при переносе на другую машину нужно воспроизвести тот же способ запуска и структуру каталогов.

Соседние модули в той же папке `project-widget/` (например `game_ui.py`) подключаются обычным **`import game_ui`** на время загрузки: загрузчик временно добавляет каталог `project-widget` в начало `sys.path`, затем очищает загруженные оттуда записи в `sys.modules`, чтобы не смешивать модули разных проектов.

## Пример: `build` и класс `CRMProjectTab`

- **`simple_game_example`** — функция **`build`**: вкладки **CRM** (подсказка про ⚙) и **«График и таблица (demo)»**.
- **`simple_site_example`** — класс **`CRMProjectTab`** (без `build`).

Деплой, Clone, Init на сервере — только через **⚙** на вкладке проекта, не внутри кастомного виджета.

## Remote git (чеклист)

1. В ⚙ или глобальных настройках задайте **`server_base_path`** (`MY_MAIN_PATH`) и **`server_project_name`** (`PROJECT_NAME`).
2. **Инициализация на сервере** из CRM (pre/post init, скрипт по SSH) **или** вручную:

   ```bash
   export MY_MAIN_PATH=/path/on/server
   export PROJECT_NAME=your_project
   export GIT_BRANCH=master   # опционально
   ssh user@host 'bash -s' < Projects/<id>/create_git_repo.sh
   ```

3. Локально **`boss_server/`** привязывается к `ssh://user@host$MY_MAIN_PATH/$PROJECT_NAME.git` (кнопка Init в CRM или вручную).
4. **Деплой:** `remote_server_core` → `boss_server` → `git push` → на VPS срабатывает **hook post-update** (`git pull` в `$MY_MAIN_PATH/$PROJECT_NAME`) → **post_deploy** и перезапуск по SSH.

Подробнее: [README.md](../README.md), [deploy_roadmap.md](deploy_roadmap.md).
