"""Шаблон create_git_repo.sh (логика как scripts/create_git_repo.sh)."""


def render_create_git_repo_sh(project_id: str) -> str:
  """Параметры при запуске: MY_MAIN_PATH, PROJECT_NAME, опционально GIT_BRANCH, REMOTE_ALIAS."""
  return f'''#!/bin/sh
# CRM: инициализация bare remote git для проекта «{project_id}» на сервере.
# Запуск с машины разработчика:
#   export MY_MAIN_PATH=/var/www/html/crm_projects
#   export PROJECT_NAME={project_id}
#   ssh user@host 'bash -s' < Projects/{project_id}/create_git_repo.sh
#
# MY_MAIN_PATH — базовый каталог; bare: $MY_MAIN_PATH/$PROJECT_NAME.git; рабочая копия: $MY_MAIN_PATH/$PROJECT_NAME

set -e
MY_MAIN_PATH="${{MY_MAIN_PATH:?Задайте MY_MAIN_PATH}}"
PROJECT_NAME="${{PROJECT_NAME:-{project_id}}}"
GIT_BRANCH="${{GIT_BRANCH:-master}}"
REMOTE_ALIAS="${{REMOTE_ALIAS:-$PROJECT_NAME}}"

cd "$MY_MAIN_PATH"
echo ">>>>>>>>>>>>> cd to path : $MY_MAIN_PATH"
mkdir "$PROJECT_NAME.git"
chmod 777 -R "$PROJECT_NAME.git"
echo ">>>>>>>>>>>>> create folder $PROJECT_NAME.git"
cd "$PROJECT_NAME.git"
echo ">>>>>>>>>>>>> cd to: $PROJECT_NAME.git"
git init
sleep 1
git --bare init
sleep 1

echo "#!/bin/sh" > '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "echo" >> '.git/hooks/post-update'
echo "echo '**** Вытягиваем изменения в рабочую копию [post-update hook]'" >> '.git/hooks/post-update'
echo "echo" >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "cd $MY_MAIN_PATH/$PROJECT_NAME" >> '.git/hooks/post-update'
echo "unset GIT_DIR" >> '.git/hooks/post-update'
echo "git pull $REMOTE_ALIAS $GIT_BRANCH" >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "exec git update-server-info" >> '.git/hooks/post-update'

git config --bool core.bare true

echo ">>>>>>>>>>>>> post-update created !!!"
cd '..'
chmod 777 -R "$PROJECT_NAME.git"

mkdir "$PROJECT_NAME"
chmod 777 -R "$PROJECT_NAME"
echo ">>>>>>>>>>>>> create folder $PROJECT_NAME"
cd "$PROJECT_NAME"
echo ">>>>>>>>>>>>> cd to: $PROJECT_NAME"
git init
git remote add "$REMOTE_ALIAS" "../$PROJECT_NAME.git"
git remote show "$REMOTE_ALIAS"
git checkout -b "$GIT_BRANCH"
echo "$PROJECT_NAME" >> readme
git add .
git commit -m "init new remote repo !"
git push "$REMOTE_ALIAS" "$GIT_BRANCH"
cd '..'
chmod 777 -R "$PROJECT_NAME"

echo ">>>>>>>>>>>>> bare: $MY_MAIN_PATH/$PROJECT_NAME.git work: $MY_MAIN_PATH/$PROJECT_NAME"
echo ">>>>>>>>>>>>> clone example: git clone ssh://user@host$MY_MAIN_PATH/$PROJECT_NAME.git boss_server"
'''
