# 🤖 Autoposter Telegram Bot

**Autoposter v3.3.2 (Monetized)** — это умный Telegram-бот для автоматического постинга контента с поддержкой OpenAI GPT-5, случайных изображений (Pixabay API), расписания, логов и встроенной системы монетизации.

---

## 🚀 Основные возможности

✅ Автоматическая публикация постов по расписанию  
✅ Генерация текста с GPT-5 (OpenAI API)  
✅ Поддержка Chat-режима (GPT-диалоги прямо в Telegram)  
✅ Автоматическая вставка рекламных постов (`ads.json`)  
✅ Монетизация через Telegram Stars / Patreon  
✅ Автоматическое восстановление после сбоев (cron + systemd)  
✅ Полная интеграция с `.env` конфигурацией  
✅ Проверка состояния сервисов `/status`  
✅ Резервное копирование и очистка логов

---

## ⚙️ Команды Telegram

| Команда | Описание |
|----------|-----------|
| `/start` | Запуск автопостинга |
| `/stop` | Остановка автопостинга |
| `/status` | Проверка статуса и времени активности |
| `/mode <тема>` | Изменить тему постов |
| `/interval <минуты>` | Интервал между публикациями |
| `/time <начало> <конец>` | Настройка активного окна |
| `/confirm on|off` | Подтверждение перед постом |
| `/chatmode on|off` | Включить или выключить **GPT-чат** |
| `/balance` | Проверить баланс |
| `/support` | Поддержать проект (Patreon, TON, USDT и др.) |
| `/health` | Проверка систем: CPU, RAM, IP и аптайм |
| `/logs` | Просмотр логов |
| `/restart` | Перезапуск сервиса Autoposter |
| `/reboot` | Перезагрузка VM |
| `/keycheck` | Проверка OpenAI API-ключей |

---

## 🧩 Установка

```bash
# Клонирование
git clone https://github.com/Olegwzy/autoposter.git
cd autoposter

# Создание виртуального окружения
python3 -m venv venv
source venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Настройка .env
nano .env

# Пример содержимого:
TELEGRAM_TOKEN=...
OPENAI_API_KEY=...
PIXABAY_KEY=...
START_HOUR=0
END_HOUR=23

# Запуск
python autoposter.py
sudo nano /etc/systemd/system/autoposter.service
[Unit]
Description=Telegram Autoposter Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=Deltacom
Group=Deltacom
WorkingDirectory=/home/Deltacom/autoposter
ExecStart=/home/Deltacom/autoposter/venv/bin/python /home/Deltacom/autoposter/autoposter.py
EnvironmentFile=-/home/Deltacom/autoposter/.env
Environment="PYTHONUNBUFFERED=1"
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
sudo systemctl daemon-reload
sudo systemctl enable autoposter.service
sudo systemctl start autoposter.service
sudo systemctl status autoposter.service
journalctl -u autoposter.service -n 20 -f
sudo systemctl daemon-reload
sudo systemctl enable autoposter.service
sudo systemctl start autoposter.service
sudo systemctl status autoposter.service
journalctl -u autoposter.service -n 20 -f
~/autoposter/
├── autoposter.py
├── thinclient.py
├── .env
├── ads.json
├── users.db
├── backup_autoposter.sh
├── autoposter.service
└── README.md
💰 Монетизация

Поддерживает:

Patreon — https://patreon.com/yourpage

Telegram Wallet (TON / USDT / BTC)

Stars API (в будущем)
🧑‍💻 Автор

Deltacom / Olegwzy
📍 Украина, Одесса
🌐 https://github.com/Olegwzy/autoposter

📬 Telegram: @my_ai_autoposter_bot

---

### 💾 3️⃣ Сохрани:
нажми  
`Ctrl + O → Enter → Ctrl + X`

---

### 🚀 4️⃣ Залей на GitHub:
```bash
git add README.md
git commit -m "Добавлен README.md с инструкцией и автозапуском"
git push origin main
