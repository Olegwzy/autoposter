#!/bin/bash
# === Autoposter Backup Script ===
# Создает архив с .env, config.json и логом, хранит только 3 последних

BACKUP_DIR="/home/Deltacom/autoposter/backups"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y-%m-%d)
BACKUP_FILE="$BACKUP_DIR/autoposter_backup_$DATE.tar.gz"

# Создаем архив
tar -czf "$BACKUP_FILE" /home/Deltacom/autoposter/.env /home/Deltacom/autoposter/config.json /home/Deltacom/autoposter/autoposter.log 2>/dev/null

# Очищаем старые бэкапы (оставляем 3 последних)
ls -tp "$BACKUP_DIR"/autoposter_backup_*.tar.gz 2>/dev/null | tail -n +4 | xargs -r rm --

echo "$(date '+%Y-%m-%d %H:%M:%S') — Backup created: $BACKUP_FILE" >> /home/Deltacom/autoposter/backup.log
