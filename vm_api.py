#!/usr/bin/env python3
from flask import Flask, jsonify
import subprocess

app = Flask(__name__)

# Разрешённые команды
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


if __name__ == "__main__":
    print("✅ Flask VM API запущен на порту 5000")
    app.run(host="0.0.0.0", port=5000)
