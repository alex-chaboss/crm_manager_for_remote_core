#!/bin/sh 

my_main_path='/root/arbitrage/'

# create repo for arbitrage backend

cd $my_main_path
echo ">>>>>>>>>>>>> cd to path : $my_main_path"
mkdir arbitrage.git
chmod 777 -R arbitrage.git
echo ">>>>>>>>>>>>> create folder arbitrage.git"
cd "arbitrage.git"
echo ">>>>>>>>>>>>> cd to: arbitrage.git"
git init
sleep 1
git --bare init
sleep 1

echo "#!/bin/sh" > '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "echo" >> '.git/hooks/post-update'
echo "echo '**** Вытягиваем изменения в Prime [post-update hook]'" >> '.git/hooks/post-update'
echo "echo" >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "cd $my_main_path/arbitrage" >> '.git/hooks/post-update'
echo "unset GIT_DIR" >> '.git/hooks/post-update'
echo "git pull arbitrage master" >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo " " >> '.git/hooks/post-update'
echo "exec git update-server-info" >> '.git/hooks/post-update'

git config --bool core.bare true

echo ">>>>>>>>>>>>> post-update created !!!"
cd '..'
chmod 777 -R 'arbitrage.git'

mkdir arbitrage
chmod 777 -R 'arbitrage'
echo ">>>>>>>>>>>>> create folder arbitrage"
cd arbitrage
echo ">>>>>>>>>>>>> cd to: arbitrage"
git init
git remote add arbitrage ../arbitrage.git
git remote show arbitrage
git checkout -b master
echo 'arbitrage' >> readme
git add .
git commit -m "init new remote repo !"
git push arbitrage master
cd '..'
chmod 777 -R 'arbitrage'


echo ">>>>>>>>>>>>> you can do something like this: git clone ssh://root@176.9.139.200/root/arbitrage/arbitrage.git boss_server"

# to start this script use: ssh root@176.9.139.200 'bash -s' < /home/chaba/work/python/neuro/server/arbitrage/scripts/create_git_repo

