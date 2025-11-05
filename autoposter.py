# autoposter.py — v3.3.2 Monetized (auto ads)
# Базируется на V3.3.1 Clean+ (твоя текущая baseline-версия), без сокращений.
# Новое в 3.3.2:
# 1) Монетизация через ads.json (создаётся автоматически при отсутствии)
# 2) Случайная вставка рекламного поста ≈ 1 из 10 (AD_FREQUENCY)
# 3) Рекламный пост отправляется сразу (без confirm), с inline-кнопкой
# 4) Лог: "💰 Отправлен рекламный пост."

import os
import sys#!/usr/bin/env python3

import json
import time
import glob
import random
import socket
import logging
import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import subprocess
from datetime import datetime, time as dtime
from typing import Optional, Tuple

import requests
import psutil

import os
import json
import requests

from telegram.ext import CallbackQueryHandler
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext
from telegram.ext import MessageHandler, Filters
from vm_daily_report import main as vm_daily_main

# === MONETIZATION BLOCK ===
import random

PARTNER_LINKS = [
    "http://bit.ly/4oMIsWN",
    "https://bit.ly/3LeQN7s"
    
]


def add_monetization(text):
    """Добавляет случайную партнёрскую ссылку в пост"""
    link = random.choice(PARTNER_LINKS)
    return f"{text}\n\n🔗 Поддержи проект: {link}"

import requests
import random
import os

def get_pixabay_image(query: str) -> str:
    """Возвращает URL случайного изображения по теме из Pixabay"""
    key = os.getenv("PIXABAY_KEY")
    url = f"https://pixabay.com/api/?key={key}&q={query}&image_type=photo&orientation=horizontal&per_page=50"
    resp = requests.get(url)
    data = resp.json()
    if data.get("hits"):
        image = random.choice(data["hits"])
        return image["webformatURL"]
    return None

# =========================
# Логирование
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger("autoposter")

# =========================
# Пути и сервис
# =========================
APP_DIR = os.path.expanduser("~/autoposter")
IMG_DIR = os.path.join(APP_DIR, "images")
CFG_PATH = os.path.join(APP_DIR, "config.json")
ADS_PATH = os.path.join(APP_DIR, "ads.json")  # NEW
SERVICE_NAME = "autoposter.service"

# Монетизация: частота рекламы (примерно 1 из 10)
AD_FREQUENCY = 10

# =========================
# Среда
# =========================
load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN_POSTER") or os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")


# =========================
# Конфиг по умолчанию
# =========================
DEFAULT_CFG = {
    "autoposting": False,
    "confirm": False,
    "chatmode": True,
    "topic": "мотивация",
    "interval": 60,           # минуты
    "start_time": "00:01",   # HH:MM
    "end_time": "23:59"      # HH:MM
}

state = DEFAULT_CFG.copy()
pending_posts = {}

# === GPT fallback state ===
GPT_FAIL_THRESHOLD = 3
_gpt_fail_count = 0
_gpt_offline = False

# === JobQueue link ===
autopost_job = None

# =========================
# Утилиты
# =========================

def ensure_dirs():
    os.makedirs(APP_DIR, exist_ok=True)
    os.makedirs(IMG_DIR, exist_ok=True)


def ensure_ads_file():  # NEW
    """Создаёт ads.json с демо-данными, если отсутствует."""
    if os.path.isfile(ADS_PATH):
        return
    demo = [
        {
            "text": "📢 Поддержи проект Autoposter — небольшое пожертвование помогает развивать бота ❤️",
            "button_text": "💰 Поддержать",
            "button_url": "https://t.me/yourbot?start=donate"
        },
        {
            "text": "🔥 Попробуй Binance P2P — обмен USDT без комиссии!",
            "button_text": "👉 Перейти",
            "button_url": "https://accounts.binance.com/register?ref=1011259426"
        }
    ]
    try:
        with open(ADS_PATH, "w", encoding="utf-8") as f:
            json.dump(demo, f, ensure_ascii=False, indent=2)
        log.info("Создан ads.json с демо-записями.")
    except Exception as e:
        log.warning(f"Не удалось создать ads.json: {e}")


def load_config():
    global state
    ensure_dirs()
    if os.path.isfile(CFG_PATH):
        try:
            with open(CFG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            merged = DEFAULT_CFG.copy()
            merged.update({k: v for k, v in cfg.items() if k in DEFAULT_CFG})
            state = merged
        except Exception as e:
            log.warning("Не удалось прочитать config.json: %s", e)
            state = DEFAULT_CFG.copy()
    else:
        save_config()


def save_config():
    ensure_dirs()
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log.warning("Не удалось сохранить config.json: %s", e)

# === GitHub API ===
GITHUB_OWNER = "Olegwzy"
GITHUB_REPO  = "autoposter"
GITHUB_API   = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/contents"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

def github_list_root():
    """Список файлов в корне репозитория через GitHub API."""
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    r = requests.get(GITHUB_API, headers=headers, timeout=15)
    if not r.ok:
        raise RuntimeError(f"GitHub API error {r.status_code}: {r.text[:200]}")
    return r.json()

def _cfg_get_repo_shas() -> dict:
    """Достаём из config.json последнюю «память» SHA, чтобы отмечать, что изменилось."""
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg.get("_repo_shas", {})
    except Exception:
        return {}

def _cfg_set_repo_shas(shas: dict) -> None:
    """Сохраняем «память» SHA обратно в config.json."""
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg["_repo_shas"] = shas
    with open(CFG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

from datetime import datetime, time as dtime
import pytz

def in_active_window(now: Optional[datetime] = None) -> bool:
    kyiv_tz = pytz.timezone("Europe/Kiev")
    if now is None:
        now = datetime.now(kyiv_tz)
    try:
        sh = datetime.strptime(state["start_time"], "%H:%M").time()
        eh = datetime.strptime(state["end_time"], "%H:%M").time()
    except Exception:
        sh, eh = dtime(0, 1), dtime(23, 59)
    cur = now.time()
    if sh <= eh:
        return sh <= cur <= eh
    else:
        return cur >= sh or cur <= eh


def local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "unknown"


def external_ip(timeout=5) -> str:
    try:
        r = requests.get("https://api.ipify.org", timeout=timeout)
        if r.ok:
            return r.text.strip()
    except Exception:
        pass
    return "unknown"


def sys_health() -> Tuple[str, str]:
    try:
        disk = psutil.disk_usage("/")
        mem = psutil.virtual_memory()
        disk_str = f"{disk.percent:.1f}%"
        mem_str = f"{int((mem.total - mem.available)/1024/1024)}/{int(mem.total/1024/1024)}Mi"
        return disk_str, mem_str
    except Exception as e:
        log.warning("sys_health error: %s", e)
        return "n/a", "n/a"


def tail_logs(unit: str = SERVICE_NAME, lines: int = 20) -> str:
    try:
        cmd = ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=5)
        return "\n".join(out.strip().splitlines()[-lines:])
    except Exception as e:
        return f"Не удалось получить логи: {e}"


def pick_local_image() -> Optional[str]:
    ensure_dirs()
    patterns = ["*.jpg", "*.jpeg", "*.png", "*.webp"]
    files = []
    for p in patterns:
        files.extend(glob.glob(os.path.join(IMG_DIR, p)))
    files = [p for p in files if os.path.isfile(p) and os.path.getsize(p) > 0]
    return random.choice(files) if files else None

# =========================
# GPT генерация (с офлайн-фолбеком)
# =========================

def _weekday_ru(i: int) -> str:
    return ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][i]

GPT_FAIL_THRESHOLD = 3
_gpt_fail_count = 0
_gpt_offline = False

def _mark_gpt_fail(e_msg: str = ""):
    global _gpt_fail_count, _gpt_offline
    _gpt_fail_count += 1
    if _gpt_fail_count >= GPT_FAIL_THRESHOLD:
        _gpt_offline = True
        log.warning("[OpenAI] квота/лимит — переключаемся в офлайн до перезапуска.")
    else:
        log.info(f"[OpenAI] временно недоступно ({_gpt_fail_count}/{GPT_FAIL_THRESHOLD}).")


def _mark_gpt_ok():
    global _gpt_fail_count, _gpt_offline
    _gpt_fail_count = 0
    _gpt_offline = False


def _offline_samples(topic: str) -> list:
    base = topic.strip() or "мотивация"
    return [
        f"{base.capitalize()}: каждый день — шанс стать лучше. Маленький шаг тоже шаг!",
        f"{base.capitalize()}: начни с 5 минут — дальше легче.",
        f"{base.capitalize()}: сконцентрируйся на одном простом действии и сделай его сейчас.",
    ]


def generate_text(topic: str) -> str:
    if _gpt_offline or not OPENAI_KEY:
        return random.choice(_offline_samples(topic))
    try:
        import openai
        for key_var in ("OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"):
            api_key = os.getenv(key_var)
            if not api_key:
                continue
            openai.api_key = api_key
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": f"Короткий пост (1–2 строки). Тема: {topic.strip() or 'мотивация'}."}],
                    max_tokens=60,
                    temperature=0.8
                )
                txt = response["choices"][0]["message"]["content"].strip()
                if txt:
                    _mark_gpt_ok()
                    return txt[:1024]
                raise RuntimeError("Empty OpenAI text")
            except Exception as e:
                es = str(e).lower()
                if "rate" in es or "quota" in es or "insufficient_quota" in es:
                    _mark_gpt_fail()
                    continue
                _mark_gpt_fail()
                continue
        return random.choice(_offline_samples(topic))
    except Exception:
        _mark_gpt_fail()
        return random.choice(_offline_samples(topic))

# =========================
# Отправка
# =========================

def safe_send_photo(bot, chat_id: str, img_path: str, caption: str) -> None:
    if not img_path or not os.path.isfile(img_path):
        raise FileNotFoundError(f"Image path invalid: {img_path}")
    if os.path.getsize(img_path) <= 0:
        raise IOError("Image file is empty")
    cap = (caption or "").strip()
    if len(cap) > 1024:
        cap = cap[:1021] + "…"
    last_err = None
    for attempt in range(1, 4):
        try:
            with open(img_path, "rb") as f:
                bot.send_photo(chat_id=chat_id, photo=f, caption=cap)
            return
        except Exception as e:
            last_err = e
            log.warning("[send_photo] attempt %d/3: %s", attempt, e)
            time.sleep(1.5 * attempt)
    raise last_err if last_err else RuntimeError("send_photo failed")


def send_preview_with_buttons(bot, chat_id: str, text: str, img_path: Optional[str] = None) -> int:
    # === MONETIZATION HOOK ===
    if os.getenv("MONETIZATION", "True").lower() == "true":
        text = add_monetization(text)

    token = str(int(time.time() * 1000))
    pending_posts[token] = {"text": text, "img": img_path, "chat_id": str(chat_id)}

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Отправить", callback_data=f"confirm:yes:{token}"),
            InlineKeyboardButton("❌ Отмена", callback_data=f"confirm:no:{token}")
        ]
    ])

    if img_path:
        with open(img_path, "rb") as f:
            msg = bot.send_photo(chat_id, photo=f, caption=text, reply_markup=kb)
    else:
        msg = bot.send_message(chat_id, text, reply_markup=kb)

    return msg.message_id


def confirm_callback(update: Update, context: CallbackContext):
    q = update.callback_query
    q.answer()
    try:
        _, action, token = q.data.split(":")
    except Exception:
        q.edit_message_reply_markup(None)
        return
    payload = pending_posts.pop(token, None)
    if not payload:
        q.edit_message_reply_markup(None)
        q.message.reply_text("⛔ Истёк срок подтверждения.")
        return
    chat_id = payload["chat_id"]
    text    = payload["text"]
    img     = payload["img"]
    try:
        q.edit_message_reply_markup(None)
    except Exception:
        pass
    if action == "yes":
        try:
            if img:
                safe_send_photo(context.bot, chat_id, img, text)
            else:
                context.bot.send_message(chat_id, text)
            q.message.reply_text("✅ Отправлено.")
        except Exception as e:
            q.message.reply_text(f"⚠️ Ошибка отправки: {e}")
    else:
        q.message.reply_text("❌ Отменено.")

# =========================
# Команды
# =========================
HELP_TEXT = (
    "📘 Команды управления:\n\n"
    "/start — запустить автопостинг\n"
    "/stop — остановить автопостинг\n"
    "/status — статус и настройки\n"
    "/mode <тема> — сменить тему постов\n"
    "/interval <минуты> — задать интервал\n"
    "/time <начало> <конец> — активное время\n"
    "/test — тестовый пост\n"
    "/confirm on|off — подтверждение постов\n"
    "/keycheck — проверить OpenAI ключи\n"
    "/chatmode on|off — чат GPT\n"
    "/health — состояние сервисов\n"
    "/logs — последние строки логов\n"
    "/daily — краткий отчёт о VM\n"
    "/restart <autoposter|vm_api|thinclient>\n"
    "/reboot — перезагрузка VM\n"
)

def repo_command(update, context):
    chat_id = update.effective_chat.id
    try:
        items = github_list_root()
        last = _cfg_get_repo_shas()
        seen = {}

        # Покажем ключевые файлы первыми
        priority = {"autoposter.py", "README.md", "vm_daily_report.py", "vm_api.py",
                    "requirements.txt", "config.json", "posts.txt", "ads.json"}
        # Сортируем: приоритетные вверх, затем по имени
        items = sorted(items, key=lambda x: (x["name"] not in priority, x["name"].lower()))

        lines = ["📂 <b>autoposter — содержимое репозитория</b>"]
        for it in items:
            if it.get("type") not in ("file", "dir"):
                continue
            name = it["name"]
            sha  = it.get("sha", "")[:7]
            mark = ""
            if it["type"] == "file":
                if name in last and last[name] != sha:
                    mark = " 🆕"
                elif name not in last:
                    mark = " 🆕"
                seen[name] = sha
                size = it.get("size", 0)
                lines.append(f"• {name} — <code>{sha}</code> ({size} B){mark}")
            else:
                lines.append(f"• {name}/")

        # Сохраняем «память» увиденных SHA (только файлы)
        if seen:
            _cfg_set_repo_shas(seen)

        context.bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML")
    except Exception as e:
        context.bot.send_message(chat_id, f"❌ Ошибка GitHub: {e}")

def _weekday_ru(i: int) -> str:
    return ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"][i]

def _status_time_block() -> str:
    now = datetime.now()
    dn = now.strftime("%d.%m.%Y")
    wd = _weekday_ru(now.weekday())
    hhmm = now.strftime("%H:%M")
    st = state.get("start_time", "00:01")
    et = state.get("end_time", "23:59")
    active = in_active_window(now)
    return (
        f"📅 Сегодня: {dn} ({wd})\n"
        f"🕓 Активное окно: {st}–{et}\n"
        f"🕒 Сейчас: {hhmm} → {'активно ✅' if active else 'неактивно 💤'}"
    )

def cmd_help(update: Update, context: CallbackContext):
    update.message.reply_text(HELP_TEXT)

def cmd_start(update: Update, context: CallbackContext):
    state["autoposting"] = True
    save_config()
    update.message.reply_text("🚀 Автопостинг включён.")
    try:
        schedule_autopost_job(context.bot_data.get("updater"))
    except Exception as e:
        log.warning(f"Не удалось запланировать job при /start: {e}")

def cmd_stop(update: Update, context: CallbackContext):
    global autopost_job
    state["autoposting"] = False
    save_config()
    try:
        if autopost_job:
            autopost_job.schedule_removal()
            autopost_job = None
            log.info("⏸️ Автопостинг: job остановлен")
    except Exception as e:
        log.warning(f"Не удалось остановить job: {e}")
    update.message.reply_text("⏸️ Автопостинг остановлен.")

def cmd_status(update: Update, context: CallbackContext):
    disk, mem = sys_health()
    gpt_line = "💭 GPT Mode: Online ✅" if not _gpt_offline and OPENAI_KEY else "💤 GPT Mode: Offline fallback"
    msg = (
        "📊 Статус Autoposter\n\n"
        f"🟢 Активен: {state['autoposting']}\n"
        f"🔔 Подтверждение: {state['confirm']}\n"
        f"🎯 Тема: {state['topic']}\n"
        f"⏱️ Интервал: {state['interval']} мин\n"
        f"💬 ChatMode: {'ON' if state['chatmode'] else 'OFF'}\n"
        f"{gpt_line}\n\n"
        f"{_status_time_block()}\n\n"
        f"💾 Disk: {disk} | 💡 Mem: {mem}\n"
        f"🌐 Local IP: {local_ip()}\n"
        f"🌍 External IP: {external_ip()}\n"
    )
    update.message.reply_text(msg)

def cmd_mode(update: Update, context: CallbackContext):
    if context.args:
        state["topic"] = " ".join(context.args)
        save_config()
        update.message.reply_text(f"🎯 Тема изменена на: {state['topic']}")
    else:
        update.message.reply_text("Укажи тему: /mode <тема>")

def cmd_interval(update: Update, context: CallbackContext):
    if not context.args:
        update.message.reply_text(f"Текущий интервал: {state['interval']} мин")
        return
    try:
        val = int(context.args[0])
        if val < 1:
            raise ValueError("interval < 1")
        state["interval"] = val
        save_config()
        update.message.reply_text(f"⏱️ Интервал установлен: {val} мин")
        if state.get("autoposting", False):
            schedule_autopost_job(context.bot_data.get("updater"))
    except Exception:
        update.message.reply_text("Укажи число минут: /interval 60")

def cmd_time(update: Update, context: CallbackContext):
    if len(context.args) != 2:
        update.message.reply_text("Формат: /time HH:MM HH:MM (например, /time 08:00 22:00)")
        return
    st, et = context.args
    try:
        datetime.strptime(st, "%H:%M")
        datetime.strptime(et, "%H:%M")
        state["start_time"] = st
        state["end_time"] = et
        save_config()
        update.message.reply_text(f"🕒 Активное время: {st}–{et}")
    except Exception:
        update.message.reply_text("Неверный формат. Пример: /time 08:00 22:00")

def cmd_confirm(update: Update, context: CallbackContext):
    if not context.args or context.args[0].lower() not in ("on", "off"):
        update.message.reply_text(f"Текущая настройка: {'on' if state['confirm'] else 'off'}")
        return
    state["confirm"] = (context.args[0].lower() == "on")
    save_config()
    update.message.reply_text(f"Подтверждение: {'on' if state['confirm'] else 'off'}")

def cmd_chatmode(update: Update, context: CallbackContext):
    if not context.args or context.args[0].lower() not in ("on", "off"):
        update.message.reply_text(f"ChatMode сейчас: {'on' if state['chatmode'] else 'off'}")
        return
    state["chatmode"] = (context.args[0].lower() == "on")
    save_config()
    update.message.reply_text(f"ChatMode: {'on' if state['chatmode'] else 'off'}")

def cmd_health(update: Update, context: CallbackContext):
    disk, mem = sys_health()
    msg = (
        "🩺 Health\n"
        f"💾 Disk: {disk}\n"
        f"💡 Memory: {mem}\n"
        f"🌐 Local IP: {local_ip()}\n"
        f"🌍 External IP: {external_ip()}\n"
    )
    update.message.reply_text(msg)

def cmd_logs(update: Update, context: CallbackContext):
    txt = tail_logs(SERVICE_NAME, 20)
    if len(txt) > 3500:
        txt = txt[-3500:]
    update.message.reply_text(f"```\n{txt}\n```", parse_mode=None)

def cmd_daily(update: Update, context: CallbackContext):
    disk, mem = sys_health()
    now = datetime.now().strftime("%d.%m.%Y %H:%M")
    msg = (
        f"🗓️ Ежедневный отчёт {now}\n"
        f"💾 Disk: {disk} | 💡 Mem: {mem}\n"
        f"🌐 Local IP: {local_ip()} | 🌍 External IP: {external_ip()}\n"
        f"🔧 Services: autoposter — {'active' if state['autoposting'] else 'stopped'}\n"
    )
    update.message.reply_text(msg)

def cmd_restart(update: Update, context: CallbackContext):
    # Заглушка. Чтобы сделать restart без пароля:
    # 1) sudo loginctl enable-linger Deltacom
    # 2) sudo visudo → добавить:
    #    Deltacom ALL=(ALL) NOPASSWD: /bin/systemctl restart autoposter.service
    if not context.args:
        update.message.reply_text("Формат: /restart <autoposter|vm_api|thinclient>")
        return
    svc = context.args[0].lower()
    update.message.reply_text(f"⏳ Запрос на рестарт сервиса '{svc}' принят (заглушка).")

def cmd_reboot(update: Update, context: CallbackContext):
    update.message.reply_text("⚠️ Перезагрузка не выполняется из бота (заглушка для безопасности).")

def cmd_test(update: Update, context: CallbackContext):
    bot = context.bot
    chat_id = str(update.effective_chat.id or CHAT_ID or "").strip()
    if not chat_id:
        update.message.reply_text("⚠️ Chat_id пуст. Напиши боту сюда команду ещё раз, чтобы бот получил chat_id.")
        return
    text = generate_text(state["topic"])
    img  = pick_local_image()
    try:
        if state.get("confirm", False):
            send_preview_with_buttons(bot, chat_id, text, img)
        else:
            if img:
                safe_send_photo(bot, chat_id, img, text)
            else:
                bot.send_message(chat_id, text)
        update.message.reply_text("🧪 Тест выполнен.")
    except Exception as e:
        update.message.reply_text(f"⚠️ Ошибка отправки поста: {e}")

def report_command(update, context):
    """Выполнить ежедневный отчёт о состоянии VM."""
    chat_id = update.effective_chat.id
    try:
        vm_daily_main()  # вызывает существующий отчёт
        context.bot.send_message(chat_id, "✅ Отчёт отправлен администратору.")
    except Exception as e:
        context.bot.send_message(chat_id, f"⚠️ Ошибка при создании отчёта: {e}")

# =========================
# Монетизация — реклама
# =========================

def pick_ad() -> Optional[dict]:  # NEW
    if not os.path.isfile(ADS_PATH):
        return None
    try:
        with open(ADS_PATH, "r", encoding="utf-8") as f:
            ads = json.load(f)
        if not isinstance(ads, list):
            return None
        ads = [a for a in ads if isinstance(a, dict) and a.get("text") and a.get("button_text") and a.get("button_url")]
        return random.choice(ads) if ads else None
    except Exception as e:
        log.warning("Не удалось прочитать ads.json: %s", e)
        return None

# =========================
# Автопостинг (обновлённый)
# =========================
last_post_ts = 0.0

def autopost_tick(bot):
    """Автоматическая публикация контента с изображением и монетизацией"""
    global last_post_ts

    # --- Проверка включения автопостинга и расписания ---
    if not state["autoposting"]:
        return
    if not in_active_window():
        return

    now = time.time()
    if now - last_post_ts < state["interval"] * 60:
        return

    chat_id = (CHAT_ID or "").strip()
    if not chat_id:
        log.info("CHAT_ID не задан — автоматический пост пропущен.")
        return

    # === Случайный рекламный пост (≈1 из AD_FREQUENCY) ===
    try:
        if random.randint(1, AD_FREQUENCY) == 1:
            # Генерация рекламного текста
            theme = state.get("theme", "автоматизация")
            text = f"🤖 Автоматизация — ключ к свободе времени.\n\n#{theme}"

            # Добавляем партнёрскую ссылку (если включена)
            if os.getenv("MONETIZATION", "True").lower() == "true":
                text = add_monetization(text)

            # Получаем изображение с Pixabay
            img_url = get_pixabay_image(theme)

            # Отправляем рекламный пост
            if img_url:
                bot.send_photo(chat_id=chat_id, photo=img_url, caption=text)
                log.info(f"💰 Отправлен рекламный пост с фото ({theme}).")
            else:
                bot.send_message(chat_id, text, parse_mode="HTML")
                log.info(f"💰 Отправлен рекламный пост без фото ({theme}).")

            last_post_ts = now
            return
    except Exception as e:
        log.warning(f"Рекламный пост не отправлен: {e}")
        # не прерываем — попробуем обычный контент

    # === Обычный GPT-контент ===
    text = generate_text(state["topic"])
    img  = pick_local_image()
    try:
        if state.get("confirm", False):
            send_preview_with_buttons(bot, chat_id, text, img)
        else:
            if img:
                safe_send_photo(bot, chat_id, img, text)
            else:
                bot.send_message(chat_id, text)
            last_post_ts = now
    except Exception as e:
        log.warning("Автопостинг: ошибка отправки: %s", e)

# =========================
# ChatMode: GPT диалог без /ask
# =========================

def chatmode_handler(update, context):
    msg = update.message.text
    if not msg or msg.startswith("/"):
        return
    if not state.get("chatmode", False):
        return
    if _gpt_offline or not OPENAI_KEY:
        update.message.reply_text(random.choice(_offline_samples("chat")))
        return
    try:
        import openai
        for key_var in ("OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"):
            api_key = os.getenv(key_var)
            if not api_key:
                continue
            openai.api_key = api_key
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": msg}]
                )
                reply = response["choices"][0]["message"]["content"].strip()
                if reply:
                    _mark_gpt_ok()
                    update.message.reply_text(reply)
                    return
                raise RuntimeError("Empty GPT reply")
            except Exception as e:
                es = str(e).lower()
                if "rate" in es or "quota" in es or "insufficient_quota" in es:
                    _mark_gpt_fail()
                    continue
                _mark_gpt_fail()
                continue
        update.message.reply_text(random.choice(_offline_samples("chat")))
    except Exception:
        _mark_gpt_fail()
        update.message.reply_text(random.choice(_offline_samples("chat")))

# =========================
# Планирование через JobQueue (v13)
# =========================

def schedule_autopost_job(updater: Optional[Updater]):
    global autopost_job
    if updater is None:
        log.warning("schedule_autopost_job: updater is None")
        return
    jq = updater.job_queue
    try:
        if autopost_job:
            autopost_job.schedule_removal()
            autopost_job = None
        if not state.get("autoposting", False):
            log.info("Автопостинг выключен — job не создаётся")
            return
        seconds = max(60, int(state.get("interval", 60)) * 60)
        autopost_job = jq.run_repeating(lambda ctx: autopost_tick(updater.bot), interval=seconds, first=10, name="autopost")
        log.info(f"📆 Автопостинг активирован: каждые {seconds//60} мин (JobQueue)")
    except Exception as e:
        log.warning(f"Не удалось создать repeating job: {e}")

# === БАЗА ДАННЫХ ДЛЯ БАЛАНСОВ ===

DB_PATH = "/home/Deltacom/autoposter/users.db"

import sqlite3
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_user_balance(telegram_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT balance FROM users WHERE telegram_id=?", (telegram_id,))
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO users (telegram_id, balance) VALUES (?, 0)", (telegram_id,))
        conn.commit()
        balance = 0
    else:
        balance = row[0]
    conn.close()
    return balance

def update_balance(telegram_id, delta):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO users (telegram_id, balance) VALUES (?, 0)", (telegram_id,))
    cur.execute("UPDATE users SET balance = balance + ? WHERE telegram_id=?", (delta, telegram_id))
    conn.commit()
    conn.close()

def balance_command(update, context):
    user_id = update.message.from_user.id
    balance = get_user_balance(user_id)
    update.message.reply_text(f"💰 Ваш баланс: {balance} ⭐")


# === 💎 Блок поддержки и донатов через Telegram Wallet ===

def support_command(update, context):
    """Общее меню поддержки проекта"""
    keyboard = [
        [InlineKeyboardButton("💎 Донат (TON / USDT)", callback_data="open_donate")],
        [InlineKeyboardButton("☕ Patreon / BuyMeACoffee", url="https://buymeacoffee.com/yourpage")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        "🙏 Спасибо за поддержку проекта!\n\n"
        "Вы можете поддержать развитие Autoposter любым способом:",
        reply_markup=reply_markup
    )


def donate_command(update, context):
    """Кнопки для перевода TON или USDT (в сети TON)"""
    ton_addr = "UQDuL6UOsy-91L8ZPkvc-8ni2PLCh91W-_hXteJ3Z-h4CI17"
    usdt_addr = "UQCA_YSamy2IWt9HHezCAGYAM8YsE6rOUasfNklijiG7Wblx"

    ton_link = f"https://tonhub.com/transfer/{ton_addr}?amount=1&text=Support+Autoposter"
    usdt_link = f"https://tonhub.com/transfer/{usdt_addr}?amount=5&text=USDT+Support"

    keyboard = [
        [InlineKeyboardButton("💎 Отправить TON", url=ton_link)],
        [InlineKeyboardButton("💵 Отправить USDT (TON)", url=usdt_link)],
        [InlineKeyboardButton("✅ Я оплатил", callback_data="paid_confirm")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text(
        f"🙏 Спасибо за поддержку проекта!\n\n"
        f"💎 TON адрес:\n`{ton_addr}`\n"
        f"💵 USDT (TON):\n`{usdt_addr}`\n\n"
        "Нажмите на кнопку, чтобы открыть Wallet (Tonkeeper, Telegram Wallet и т.п.), "
        "или скопируйте адрес вручную.\n"
        "После перевода нажмите «✅ Я оплатил».",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


def payment_confirm_callback(update, context):
    """Подтверждение перевода (тестовое начисление)"""
    query = update.callback_query
    user_id = query.from_user.id
    query.answer("Проверяем перевод...")
    update_balance(user_id, 10)  # тестовое начисление 10⭐
    query.edit_message_text("💰 Спасибо! Баланс пополнен на 10 ⭐ (тестовое начисление).")

def cmd_keycheck(update, context):
    """Проверяет все OpenAI API ключи"""
    keys = ["OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3"]
    msg_lines = ["🔍 Проверка OpenAI ключей:\n"]

    for key_var in keys:
        api_key = os.getenv(key_var)
        if not api_key:
            msg_lines.append(f"⚠️ {key_var}: отсутствует")
            continue

        try:
            import requests
            r = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10
            )
            if r.status_code == 200 and '"id"' in r.text:
                msg_lines.append(f"✅ {key_var}: работает")
            elif "insufficient_quota" in r.text:
                msg_lines.append(f"⚠️ {key_var}: лимит исчерпан")
            elif "invalid_api_key" in r.text or r.status_code == 401:
                msg_lines.append(f"❌ {key_var}: неверный ключ")
            else:
                msg_lines.append(f"❓ {key_var}: {r.status_code} / неизвестный ответ")
        except Exception as e:
            msg_lines.append(f"❌ {key_var}: ошибка {e}")

    update.message.reply_text("\n".join(msg_lines))

# =========================
# Запуск
# =========================
def main():
    if not TOKEN:
        log.error("TELEGRAM_BOT_TOKEN пуст — выход")
        sys.exit(1)
    ensure_dirs()
    ensure_ads_file()  # NEW
    load_config()

    request_kwargs = {"con_pool_size": 8, "read_timeout": 30, "connect_timeout": 15}
    updater = Updater(token=TOKEN, use_context=True, request_kwargs=request_kwargs)
    dp = updater.dispatcher

    dp.bot_data["updater"] = updater

    # Команды
    dp.add_handler(CommandHandler("help", cmd_help))
    dp.add_handler(CommandHandler("start", cmd_start))
    dp.add_handler(CommandHandler("stop", cmd_stop))
    dp.add_handler(CommandHandler("status", cmd_status))
    dp.add_handler(CommandHandler("balance", balance_command))
    dp.add_handler(CommandHandler("support", support_command))
    dp.add_handler(CommandHandler("mode", cmd_mode))
    dp.add_handler(CommandHandler("interval", cmd_interval))
    dp.add_handler(CommandHandler("time", cmd_time))
    dp.add_handler(CommandHandler("confirm", cmd_confirm))
    dp.add_handler(CommandHandler("chatmode", cmd_chatmode))
    dp.add_handler(CommandHandler("health", cmd_health))
    dp.add_handler(CommandHandler("logs", cmd_logs))
    dp.add_handler(CommandHandler(["daily", "daily_report"], cmd_daily))
    dp.add_handler(CommandHandler("restart", cmd_restart))
    dp.add_handler(CommandHandler("reboot", cmd_reboot))
    dp.add_handler(CommandHandler("test", cmd_test))

    # 🔹 GitHub репозиторий (новая команда)
    dp.add_handler(CommandHandler("repo", repo_command))
    dp.add_handler(CommandHandler("report", report_command))

    # Донаты
    dp.add_handler(CommandHandler("donate", donate_command))

    dp.add_handler(CallbackQueryHandler(payment_confirm_callback, pattern="^paid_confirm$"))
    dp.add_handler(CallbackQueryHandler(lambda update, context: donate_command(update, context), pattern="^open_donate$"))

    # Callback & ChatMode
    dp.add_handler(CallbackQueryHandler(confirm_callback, pattern=r"^confirm:(yes|no):"))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, chatmode_handler))

    # Проверяет работу OPENAI_API_KEY, OPENAI_API_KEY_2, OPENAI_API_KEY_3
    dp.add_handler(CommandHandler("keycheck", cmd_keycheck))
    
    # Первый пост (best-effort)
    try:
        autopost_tick(updater.bot)
    except Exception as e:
        log.warning(f"Первый пост не удался: {e}")

    # JobQueue
    try:
        schedule_autopost_job(updater)
    except Exception as e:
        log.warning(f"Не удалось запустить автопостинг (job): {e}")

    # Polling
    while True:
        try:
            updater.start_polling(drop_pending_updates=True)
            log.info("🤖 Autoposter активен и слушает команды...")
            updater.idle()
            break
        except Exception as e:
            log.warning(f"🔁 Ошибка polling: {e}, повтор через 5 секунд...")
            time.sleep(5)

# === Flask Web Admin ===
from flask import Flask, jsonify
import psutil

app = Flask(__name__)

@app.route("/")
def home():
    return "🟢 Autoposter Flask API is running. Try /status"

@app.route("/status")
def status():
    mem = psutil.virtual_memory()
    uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
    data = {
        "autoposter": "✅ активен",
        "uptime": str(uptime).split('.')[0],
        "memory_used": f"{mem.percent}%",
        "interval": f"{INTERVAL_MINUTES} мин",
        "theme": CURRENT_TOPIC,
        "confirm": CONFIRMATION_MODE,
        "status": "online"
    }
    return jsonify(data)


if __name__ == "__main__":
    from threading import Thread
    import logging

    def run_flask():
        print("🌐 Flask server starting on port 5000...")
        try:
            app.run(host="0.0.0.0", port=5000)
        except Exception as e:
            logging.error(f"Flask failed to start: {e}")

    # 🔹 Запуск Flask в отдельном потоке (демон)
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # 🔹 Запуск основного Telegram-бота
    try:
        print("🤖 Starting Telegram Autoposter...")
        main()  # ← это твоя основная функция (где запускается бот, scheduler и т.д.)
    except KeyboardInterrupt:
        print("🛑 Autoposter stopped manually.")
    except Exception as e:
        logging.error(f"Autoposter crashed: {e}")



