py .\manage.py collectstatic 

docker-compose up --build

docker-compose down

docker compose ps

docker compose restart



scp -r ./remanager kenji-konno@100.94.246.4:/home/kenji-konno/

ssh kenji-konno@100.94.246.4

docker build -t remanager:latest .
docker run -d -p 8902:8000 invoice:latest

### with yaml file
docker compose up -d --build

http://100.94.246.4:8902



stop and remove container

docker stop dreamy_gates
docker rm dreamy_gates

docker system prune   stopped container, unused networks build cache
docker image prune
docker volume prune
docker container prune
docker network prune

cp /mnt/nas/develop/invoice/invoice202506dep/db.sqlite3 /var/lib/docker/volumes/invoice202506dep_db_volume/_data


COMPOSE_PROJECT_NAME=invoice202506dep docker compose up -d

### Database Initiation
docker exec -i db-invoice psql -U konno -d postgres -c "DROP DATABASE IF EXISTS invoice;"

docker exec -i db-invoice psql -U konno -d postgres -c "CREATE DATABASE invoice;"

docker exec -i db-invoice psql -U konno -d invoice < ss.sql


# git operation

### Daily workflow
git fetch --prune
git checkout main
git pull --ff-only

### When starting new work
git checkout -b feature/foo

# When switching PCs

### Just push before leaving:

git push origin feature/foo

### Then on the other PC:
git fetch
git checkout feature/foo


1. Delete merged branches locally
git branch --merged main | grep -v main | xargs git branch -d

2. Auto-remove deleted remote branches
git fetch --prune

#### Or permanently:
git config --global fetch.prune true

# Option 3: “Reset to remote” when things get messy

### If your local repo is messy but you don’t want to reclone:
git fetch origin
git reset --hard origin/main
git clean -fd

### - This gives you a fresh state equivalent to re-clone, but faster.
⚠️ This deletes uncommitted work.

# Option 4: Worktrees (advanced but very clean)
#### If you often switch branches:
git worktree add ../repo-feature feature/foo