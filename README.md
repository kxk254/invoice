DATABASE Settings (settings.py)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'your_db',
        'USER': 'your_user',
        'PASSWORD': 'your_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
📤 DUMP SQL Data
python manage.py dumpdata --natural-primary --natural-foreign --indent 2 > data.json
🧱 MIGRATE SQL SCHEMA
python manage.py migrate
📥 LOAD DATA INTO POSTGRES
python manage.py loaddata data.json
💾 BACKUP DUMP DATA
python manage.py dumpdata --indent 2 > /mnt/nas/remanager/db/db_backups/db_backup_$(date +%F_%H-%M-%S).json
♻️ RESTORE DATA
python manage.py loaddata /mnt/nas/remanager/db/db_backups/db_backup_2025-09-24_15-12-30.json
NAS MOUNT
sudo umount /mnt/nas
mount | grep cifs
ls -ld /mnt/nas


getent group | grep media
sudo groupadd -g 1010 mediausers
sudo usermod -aG mediausers www-data
