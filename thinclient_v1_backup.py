#!/usr/bin/env python3
import os
import time
import subprocess
import requests
import openai
from datetime import datetime
from dotenv import load_dotenv

# === Инициализация ===
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_TOKEN_POSTER")
CHAT_ID = "1359259211"

openai.api_key = OPENAI_API_KEY

LOG_PATH = "/home/Deltacom/autoposter/thinclient.log"
VM_API = "http://127.0.0.1:5000/api/vm"

# Контроль состояния / recovery
gpt_fail_count = 0
vm_fail_count = 0
total_fail_cycles = 0
MAX_FAILS = 2          # после 2 подряд ошибок — рестарт autoposter
REBOOT_THRESHOLD = 4   # ~2 часа (4 цикла по 30 мин) — перезагрузка VM
CHECK_INTERVAL = 1800  # 30 минут

AUTOSTART_SERVICES = ["vm_api.service", "autoposter.service"]

def log(msg: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{now}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def notify_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        log(f"⚠️ Ошибка Telegram: {e}")

# ---------- Контроль systemd ----------
def run_cmd(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

def is_active(service: str) -> bool:
    res = run_cmd(["systemctl", "is-active", service])
    return res.returncode == 0 and res.stdout.strip() == "active"

def is_enabled(service: str) -> bool:
    res = run_cmd(["systemctl", "is-enabled", service])
    return res.returncode == 0 and res.stdout.strip() == "enabled"

def ensure_service_enabled(service: str):
    if not is_enabled(service):
        run_cmd(["systemctl", "enable", service])
        log(f"🔧 enable {service}")
        notify_telegram(f"🔧 Включил автозапуск `{service}`")

def ensure_service_running(service: str):
    ensure_service_enabled(service)
    if not is_active(service):
        run_cmd(["systemctl", "start", service])
        log(f"▶️ start {service}")
        notify_telegram(f"▶️ Запустил `{service}` (был остановлен)")

def restart_autoposter(reason: str):
    res = run_cmd(["systemctl", "restart", "autoposter.service"])
    if res.returncode == 0:
        msg = f"⚙️ Перезапуск `autoposter.service` выполнен ✅ ({reason})"
    else:
        msg = f"❌ Ошибка перезапуска `autoposter.service`: {res.stdout}"
    log(msg); notify_telegram(msg)

def reboot_vm():
    msg = "⚠️ GPT и VM API недоступны ~2 часа — выполняю *автоматическую перезагрузку VM* 🔄"
    log(msg); notify_telegram(msg)
    try:
        subprocess.run(["sudo", "reboot"], check=True)
    except Exception as e:
        log(f"❌ Ошибка reboot: {e}")
        notify_telegram(f"❌ Ошибка reboot: {e}")

# ---------- Бизнес-проверки ----------
def check_vm_status():
    global vm_fail_count
    try:
        r = requests.get(f"{VM_API}/uptime", timeout=5)
        if r.status_code == 200:
            data = r.json().get("output", "").strip()
            log(f"✅ VM API работает: {data}")
            vm_fail_count = 0
        else:
            vm_fail_count += 1
            msg = f"⚠️ Ошибка VM API (код {r.status_code}) [{vm_fail_count}]"
            log(msg); notify_telegram(msg)
    except Exception as e:
        vm_fail_count += 1
        msg = f"❌ VM API недоступен: {e} [{vm_fail_count}]"
        log(msg); notify_telegram(msg)

def gpt_ping():
    global gpt_fail_count
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Ответь словом OK"}]
        )
        content = resp.choices[0].message["content"].strip()
        log(f"🧠 GPT ответил: {content}")
        gpt_fail_count = 0
    except Exception as e:
        gpt_fail_count += 1
        msg = f"❌ Ошибка GPT: {e} [{gpt_fail_count}]"
        log(msg); notify_telegram(msg)

def recovery_logic():
    global total_fail_cycles
    if gpt_fail_count >= MAX_FAILS or vm_fail_count >= MAX_FAILS:
        total_fail_cycles += 1
        restart_autoposter("Ошибка GPT/VM API")
    else:
        total_fail_cycles = 0

    if total_fail_cycles >= REBOOT_THRESHOLD:
        reboot_vm()

def ensure_stack_after_boot():
    """Гарантируем, что vm_api и autoposter включены и запущены (после перезагрузки VM)"""
    for svc in AUTOSTART_SERVICES:
        ensure_service_running(svc)

def run_loop():
    log("🚀 ThinClient запущен (GPT ↔ VM API ↔ Recovery & Autostart)")
    notify_telegram("🟢 *ThinClient активен* (Recovery + Autostart)")
    # На всякий случай — выравниваем состояние после старта/ребута
    ensure_stack_after_boot()

    while True:
        check_vm_status()
        gpt_ping()
        recovery_logic()
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    log("=== Запуск ThinClient (Recovery + Autostart) ===")
    run_loop()

