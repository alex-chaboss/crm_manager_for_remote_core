# Roadmap: деплой и инициализация проекта

Реализованный объём — [implementation_plan_deploy_settings_ui.md](implementation_plan_deploy_settings_ui.md). Контракт виджета — [project_widget_contract.md](project_widget_contract.md).

## Реализовано

- `create_git_repo.sh` (`MY_MAIN_PATH`, `PROJECT_NAME`, hook post-update), [`crm/maintenance.py`](../crm/maintenance.py).
- ⚙ **ProjectSettingsDialog**: Clone, Init, Деплой, тест **pre_deploy**, дерево `project_core`, Auto Sync.
- **Файл секретов** (после кнопки Clone): локальный `.txt`/`.env` с строками `<$name>=значение` (по одной на строку; `#` — комментарий). Путь хранится в профиле проекта (`secrets_file_path`), значения только в RAM. При Init/Deploy сначала подстановка из файла, недостающие маркеры — прежние password-алерты. Кнопка «обновить» (иконка) перечитывает файл.
- **OperationLogDialog** + **OperationRunner**: копирование лога, экспорт в файл, отмена subprocess, overlay на главном окне.
- Списки команд с **`local-sh:`** (bash на ПК), **`local:`**, **`server:`**, ↑↓, merge global→project.
- Проверка рабочей копии на сервере после push (`git status` по SSH).

## Идеи на будущее

| Направление | Описание |
|-------------|----------|
| Явное ожидание hook | Poll / retry вместо одного `git status` |
| CI / уведомления | Webhook после push |
| i18n в кастомных `project-widget` | По запросу |

При реализации — строка в [development_process_log.md](development_process_log.md).
