# SevaCRM — Деплой и администрирование

## Сервер

- **IP:** `109.172.114.197`
- **Пользователь:** `root`
- **SSH-ключ:** `~/.ssh/id_ed25519_seva`
- **Директория приложения:** `/opt/sevacrm`
- **URL:** https://sevacrm.ru
- **Compose-файл:** `docker-compose.prod.yml`

---

## Как деплоить обновления

На сервере **нет git-репозитория** — файлы копируются через `scp`, затем пересобирается контейнер.

### 1. Закоммитить и запушить в git (для истории)

```bash
git add <файлы>
git commit -m "описание изменений"
git push origin main
```

### 2. Скопировать изменённые файлы на сервер

```bash
scp -i ~/.ssh/id_ed25519_seva <локальный_путь> root@109.172.114.197:/opt/sevacrm/<путь_на_сервере>
```

Примеры:

```bash
# Python-файл
scp -i ~/.ssh/id_ed25519_seva app/routers/orders.py root@109.172.114.197:/opt/sevacrm/app/routers/orders.py

# Шаблон
scp -i ~/.ssh/id_ed25519_seva app/templates/dashboard.html root@109.172.114.197:/opt/sevacrm/app/templates/dashboard.html

# Несколько файлов — по одному через scp или через rsync:
rsync -avz -e "ssh -i ~/.ssh/id_ed25519_seva" \
  --exclude='.venv/' --exclude='node_modules/' --exclude='.git/' \
  --exclude='sevacrm.db' --exclude='uploads/' --exclude='__pycache__/' \
  app/ root@109.172.114.197:/opt/sevacrm/app/
```

### 3. Пересобрать и перезапустить контейнер

```bash
ssh -i ~/.ssh/id_ed25519_seva root@109.172.114.197 \
  "cd /opt/sevacrm && docker compose -f docker-compose.prod.yml up --build -d"
```

---

## Полезные SSH-команды

```bash
# Войти на сервер
ssh -i ~/.ssh/id_ed25519_seva root@109.172.114.197

# Посмотреть логи приложения
ssh -i ~/.ssh/id_ed25519_seva root@109.172.114.197 \
  "docker logs sevacrm_app --tail=50 -f"

# Статус контейнера
ssh -i ~/.ssh/id_ed25519_seva root@109.172.114.197 \
  "docker ps"

# Перезапустить без пересборки
ssh -i ~/.ssh/id_ed25519_seva root@109.172.114.197 \
  "cd /opt/sevacrm && docker compose -f docker-compose.prod.yml restart"
```

---

## Важно

- **Не трогать** `/etc/nginx/sites-available/sevacrm.ru` — там SSL-конфиг
- **Не трогать** SSL-сертификаты в `/etc/letsencrypt/live/sevacrm.ru/`
- **Не запускать** `deploy.sh` — он перезаписывает nginx-конфиг
- База данных хранится в `/opt/sevacrm/sevacrm.db` — монтируется как volume, при пересборке не удаляется
- Загрузки хранятся в `/opt/sevacrm/uploads/` — тоже volume, не удаляются
