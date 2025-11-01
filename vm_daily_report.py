#!/usr/bin/env python3
import os
import requests
import subprocess
from datetime import datetime
import pytz
import telegram

# === Настройки ===
CHAT_ID = "1359259211"
BOT_TOKEN = os.getenv("TELEGRAM_TOKEN_POSTER", "8291273565:AAHkz3Txr-_j-gwtAoSbBgd2S7TGBcILFgU")
TZ = pytz.timezone("Europe/Kiev")

bot = telegram.Bot(token=BOT_TOKEN)

def run_cmd(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode().strip()
    except Exception as e:
        return f"Error: {e}"

def get_vm_status():
    uptime = run_cmd(["uptime", "-p"]).replace("up ", "")
    disk = run_cmd(["df", "-h", "--output=pcent", "/"]).splitlines()[-1].strip()
    mem = run_cmd(["free", "-h"]).splitlines()[1].split()
    mem_used = mem[2]
    mem_total = mem[1]
    mem_info = f"{mem_used}/{mem_total}"
    return uptime, disk, mem_info

def get_service_status(service):
    try:
        output = run_cmd(["systemctl", "is-active", service])
        return "🟢 active" if output.strip() == "active" else "🔴 inactive"
    except:
        return "⚠️ unknown"

def main():
    now = datetime.now(TZ).strftime("%d.%m.%Y %H:%M")
    uptime, disk, memory = get_vm_status()

    services = {
        "autoposter": get_service_status("autoposter.service"),
        "vm_api": get_service_status("vm_api.service"),
        "thinclient": get_service_status("thinclient.service")
    }

    report = (
        f"📊 <b>VM Daily Report — {now}</b>\n"
        f"🕒 Uptime: {uptime}\n"
        f"💾 Disk used: {disk}\n"
        f"💡 Memory: {memory}\n\n"
        f"🤖 Autoposter: {services['autoposter']}\n"
        f"🌐 VM API: {services['vm_api']}\n"
        f"🧩 ThinClient: {services['thinclient']}\n"
    )

    bot.send_message(chat_id=CHAT_ID, text=report, parse_mode="HTML")

if __name__ == "__main__":
    main()
