from telegram.ext import CommandHandler

def cmd_getid(update, context):
    chat = update.effective_chat
    msg = f"🆔 Chat ID: {chat.id}\n👤 Type: {chat.type}"
    update.message.reply_text(msg)

def register(dp):
    dp.add_handler(CommandHandler("getid", cmd_getid))
