# Roadmap: деплой и инициализация проекта

Краткий ориентир по развитию сценария «скелет → сервер → один клик деплой». Детали `project-widget` — в [project_widget_contract.md](project_widget_contract.md).

## Уже есть

- Скелет каталогов и **`create_git_repo.sh`** при создании проекта ([`crm/project_init.py`](../crm/project_init.py)).
- Копирование **`remote_server_core` → `boss_server`**, `git commit` / `git push` и SSH pull + restart из формы настроек ([`crm/sync_deploy.py`](../crm/sync_deploy.py), [`crm/gui/project_settings_core.py`](../crm/gui/project_settings_core.py)).

## Частично / в планах

| Направление | Описание |
|-------------|----------|
| SSH + bare + clone в `boss_server` одной кнопкой | Автоматический вызов шаблона `create_git_repo.sh` на сервере и привязка рабочей копии — отдельная задача (UX + безопасность + логирование). |
| Манифест путей `project_core` → `remote_server_core` | Конфиг списка файлов/папок на проект, UI выбора, копирование только из списка перед sync (сейчас копирование в `remote_server_core` вручную или вне CRM). |
| Кнопка «Деплой» | Объединённый сценарий: условное копирование по манифесту → sync/push → ожидание (таймер 10–20 с или сигнал по успеху push) → команда перезапуска (nginx, pm2, unit, кастом). |
| Связка с `project-widget` | Опциональный хост-API или встраивание `ProjectSettingsCore` в кастом, чтобы не дублировать пути и SSH. |

Этот файл не задаёт сроков; при реализации фич добавляйте строки в [development_process_log.md](development_process_log.md).
