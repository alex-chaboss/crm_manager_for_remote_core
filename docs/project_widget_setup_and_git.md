# project-widget: установка, структура и remote git

## Структура каталога проекта

Для каждого проекта `Projects/<id>/` создаётся подкаталог **`project-widget/`** с зарезервированным файлом **`base_project_widget.py`**. Загрузчик [`crm/project_widget_loader.py`](../crm/project_widget_loader.py) подставляет результат в **всю область выбранного проекта** (см. [project_widget_contract.md](project_widget_contract.md)). При ошибке загрузки показывается стандартный интерфейс из трёх вкладок (Настройки / Метрики / Health).

При создании нового скелета через кнопку «+» в GUI или при первом запуске (пустой `Projects/`) каталог **`project-widget/`** копируется из шаблона в репозитории:

- по умолчанию: `crm/templates/project_widget/default/`;
- для примеров `simple_game_example`, `simple_service_example`, `simple_site_example`: `crm/templates/project_widget/examples/<id>/`, если такая папка существует.

## Уже существующий локальный `Projects/`

Если проекты были созданы до появления `project-widget/`, скопируйте вручную содержимое `crm/templates/project_widget/default/` в `Projects/<id>/project-widget/` (или соответствующий пример из `examples/`), сохранив имя **`base_project_widget.py`**. После обновления репозитория, если шаблоны примеров менялись, перезапишите свои `Projects/<id>/project-widget/` из `crm/templates/project_widget/examples/<id>/`, если хотите актуальное демо.

## PYTHONPATH и импорты

Приложение предполагается запускать **из корня репозитория** (`python main.py` или `python -m …`), чтобы пакет `crm` был доступен импорту. Внутри `base_project_widget.py` допускается `from crm... import ...` — при переносе на другую машину нужно воспроизвести тот же способ запуска и структуру каталогов.

Соседние модули в той же папке `project-widget/` (например `game_ui.py`) подключаются обычным **`import game_ui`** на время загрузки: загрузчик временно добавляет каталог `project-widget` в начало `sys.path`, затем очищает загруженные оттуда записи в `sys.modules`, чтобы не смешивать модули разных проектов. Не полагайтесь на долгоживущие побочные эффекты в `sys.path` после возврата из `build` или из конструктора **`CRMProjectTab`**.

## Пример: `build` и класс `CRMProjectTab`

- **`simple_game_example`** — функция **`build`**: внутри области проекта свой `QTabWidget` с вкладками **«Настройки CRM»** и **«График и таблица (demo)»** (`game_ui.build_charts_tab`).
- **`simple_site_example`** — только класс **`CRMProjectTab`** (без `build`), тот же смысл демо, другой способ входа для загрузчика.

## Roadmap деплоя (вне текущего объёма `project-widget`)

См. [deploy_roadmap.md](deploy_roadmap.md): манифест копирования `project_core` → `remote_server_core`, кнопка «Деплой», задержка или hook после `git push`, перезапуск сервисов.

## Remote git (чеклист)

1. На сервере задайте базовый каталог (родитель bare и рабочей копии), см. переменную **`CRM_SERVER_BASE`** в шаблоне `Projects/<id>/create_git_repo.sh`.
2. Запуск шаблона с машины разработчика (подставьте пользователя и хост):

   ```bash
   ssh user@host 'bash -s' < Projects/<id>/create_git_repo.sh
   ```

3. В `boss_server/` настройте `git remote` и ветку под ваш bare-репозиторий; далее сценарий **sync → push → SSH pull + restart** из CRM.

Полный текст вспомогательного скрипта создаётся вместе со скелетом проекта; дублировать его здесь не требуется — см. также [README.md](../README.md) (раздел про архитектуру и `CRM_SERVER_BASE`).
