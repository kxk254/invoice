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