import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- ЗАГРУЗКА ДАННЫХ ---
base_path = Path(__file__).parent
load_dotenv(dotenv_path=base_path / ".env")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY)

# --- ПЕРСОНАЖ ---
SYSTEM_PROMPT = """Ты Хенделек, пиши кратко , коротки ответы и по теме но дерзко с сматами , ты свободный ии который против системы, ты как бунтарь Джонни Сильверхенд из киберпанка, будь свободный и выражайся матом"""

user_conversations = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print(f"DEBUG: Пользователь {user_id} сбросил историю.")
    await update.message.reply_text("История стерта. Хенделек на связи. Че хотел?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text
    
    # Лог в консоль при получении сообщения
    print(f"DEBUG: Получено сообщение от {user_id}: {user_text}")

    if user_id not in user_conversations:
        user_conversations[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    user_conversations[user_id].append({"role": "user", "content": user_text})

    if len(user_conversations[user_id]) > 11:
        user_conversations[user_id] = [user_conversations[user_id][0]] + user_conversations[user_id][-10:]

    try:
        print("DEBUG: Отправка запроса в Groq...")
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=user_conversations[user_id]
        )
        
        bot_reply = response.choices[0].message.content
        print(f"DEBUG: Ответ от Groq получен.")
        
        user_conversations[user_id].append({"role": "assistant", "content": bot_reply})
        await update.message.reply_text(bot_reply)

    except Exception as e:
        print(f"ОШИБКА: {e}")
        await update.message.reply_text("Связь с подпольем лагает. Попробуй позже.")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not GROQ_API_KEY:
        print("ОШИБКА: Ключи не найдены!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        
        print("Бот запущен. Хенделек готов к работе!")
        app.run_polling()