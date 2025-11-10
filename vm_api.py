#!/usr/bin/env python3
from flask import Flask, jsonify
import subprocess
import psutil
import datetime
import os
import json

app = Flask(__name__)

# === Разрешённые системные команды ===
COMMANDS = {
    "uptime": ["uptime"],
    "disk": ["df", "-h"],
    "memory": ["free", "-h"],
    "autoposter": ["systemctl", "status", "autoposter.service"]
}


@app.route("/api/vm/<action>", methods=["GET"])
def vm_action(action):
    """Безопасное выполнение только разрешённых команд"""
    if action not in COMMANDS:
        return jsonify({"error": f"Invalid action '{action}'"}), 400

    try:
        output = subprocess.check_output(
            COMMANDS[action], stderr=subprocess.STDOUT
        ).decode("utf-8")
        return jsonify({"output": output})
    except subprocess.CalledProcessError as e:
        return jsonify({"error": e.output.decode("utf-8")}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === Новый универсальный статус ===
@app.route("/status")
def status():
    """Объединённый статус VM + Autoposter"""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
    cpu_load = psutil.cpu_percent(interval=1)

    # Проверяем статус systemd-сервиса autoposter
    try:
        svc = subprocess.check_output(
            ["systemctl", "is-active", "autoposter.service"],
            stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        autoposter_status = "🟢 активно" if svc == "active" else f"🔴 {svc}"
    except Exception:
        autoposter_status = "❌ неизвестно"

    data = {
        "cpu": cpu_load,
        "memory": mem.percent,
        "disk": disk.percent,
        "uptime": str(uptime).split('.')[0],
        "autoposter": autoposter_status
    }
    return jsonify(data)


# === Новый API для Dashboard ===
@app.route("/api/system")
def api_system():
    """Живые данные о системе (для Dashboard)"""
    try:
        disk = psutil.disk_usage("/")
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.5)

        data = {
            "cpu": round(cpu, 1),
            "ram_used_pct": round(mem.percent, 1),
            "disk_used_pct": round(disk.percent, 1),
            "hostname": subprocess.getoutput("hostname"),
            "mem_used_mb": int(mem.used / 1024 / 1024),
            "mem_total_mb": int(mem.total / 1024 / 1024),
            "disk_path": "/"
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/autoposter")
def api_autoposter():
    """Статус автопостера и GPT"""
    try:
        cfg_path = "/home/Deltacom/autoposter/config.json"
        active = False
        topic = "не указана"
        interval = 0
        gpt_mode = "Offline 💭"

        if os.path.isfile(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            active = cfg.get("autoposting", False)
            topic = cfg.get("topic", "unknown")
            interval = cfg.get("interval", 0)

        if os.getenv("OPENAI_API_KEY"):
            gpt_mode = "Online ✅"

        data = {
            "active": active,
            "topic": topic,
            "interval": interval,
            "gpt_mode": gpt_mode
        }
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def home():
    return "🟢 VM API is running. Endpoints: /status, /api/system, /api/autoposter, /api/vm/<action>"


if __name__ == "__main__":
    print("✅ Flask VM API запущен на порту 5000")
    app.run(host="0.0.0.0", port=5000)
