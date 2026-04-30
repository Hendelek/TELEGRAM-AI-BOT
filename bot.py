import os
import sqlite3
import logging
import asyncio
from datetime import datetime
from pathlib import Path

# Production-библиотеки
import PyPDF2
import pandas as pd
import docx
from dotenv import load_dotenv
from groq import Groq
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from duckduckgo_search import DDGS

# Настройка логирования для отслеживания работы всех пользователей
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UniversalHendelekOS:
    def __init__(self):
        self.base_path = Path(__file__).parent
        load_dotenv(dotenv_path=self.base_path / ".env")
        
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "llama-3.3-70b-versatile"
        self.db_path = 'bot_memory.db'
        self._init_db()

    def _init_db(self):
        """Создает базу данных с поддержкой времени и ID пользователя."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history 
                (user_id INTEGER, role TEXT, content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
            """)

    async def _extract_content(self, file_path: str, file_name: str) -> str:
        """Универсальный парсер документов."""
        ext = file_name.lower().split('.')[-1]
        text = f"\n[Файл: {file_name}]\n"
        try:
            if ext == 'pdf':
                with open(file_path, "rb") as f:
                    pdf = PyPDF2.PdfReader(f)
                    text += "".join([p.extract_text() for p in pdf.pages[:10]])
            elif ext in ['xlsx', 'xls', 'csv']:
                df = pd.read_excel(file_path) if 'xl' in ext else pd.read_csv(file_path)
                text += df.to_string(index=False, max_rows=30)
            elif ext == 'docx':
                doc = docx.Document(file_path)
                text += "\n".join([p.text for p in doc.paragraphs])
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    text += f.read()
            return text[:20000] # Защита от переполнения контекста
        except Exception as e:
            logger.error(f"Ошибка парсинга {file_name}: {e}")
            return f"\n[Ошибка чтения {file_name}]"

    async def on_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not update.message: return
        
        user = update.effective_user
        user_id = user.id
        # Бот приветствует пользователя по имени, делая его универсальным
        user_name = user.first_name 
        
        raw_input = update.message.text or update.message.caption or ""
        
        # Индикатор работы для пользователя
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

        # 1. Голос (Whisper)
        if update.message.voice:
            v_file = await update.message.voice.get_file()
            v_path = f"v_{user_id}.ogg"
            await v_file.download_to_drive(v_path)
            with open(v_path, "rb") as a:
                trans = self.client.audio.transcriptions.create(file=(v_path, a.read()), model="whisper-large-v3")
                raw_input = trans.text
            os.remove(v_path)

        # 2. Документы
        if update.message.document:
            doc = update.message.document
            d_path = f"tmp_{user_id}_{doc.file_name}"
            await (await doc.get_file()).download_to_drive(d_path)
            raw_input += await self._extract_content(d_path, doc.file_name)
            os.remove(d_path)

        # 3. Динамический системный промпт
        now = datetime.now()
        system_prompt = (
            f"Ты — Hendelek OS, Senior AI. Твой текущий собеседник: {user_name}. "
            f"Время: {now.strftime('%H:%M:%S')}, Дата: {now.strftime('%Y-%m-%d')}. "
            "Стиль: киберпанк, кратко, по делу, с легким сарказмом. Ты мастер IT и файлов."
        )

        # 4. История (индивидуальная для каждого user_id)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT role, content FROM history WHERE user_id = ? ORDER BY timestamp DESC LIMIT 8", 
                (user_id,)
            )
            history = [{"role": r, "content": c} for r, c in reversed(cursor.fetchall())]

        # 5. Поиск в сети (если нужно)
        if any(trigger in raw_input.lower() for trigger in ["найди", "новости", "гугл", "погода"]):
            with DDGS() as ddgs:
                search_data = [r['body'] for r in ddgs.text(raw_input, max_results=3)]
                raw_input += "\n\n[NET_DATA]:\n" + "\n".join(search_data)

        # Сборка и отправка запроса в Groq
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": raw_input}]

        try:
            response = self.client.chat.completions.create(model=self.model, messages=messages, temperature=0.7)
            answer = response.choices[0].message.content
            
            # Сохранение в БД
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("INSERT INTO history (user_id, role, content) VALUES (?, 'user', ?)", (user_id, raw_input[:500]))
                conn.execute("INSERT INTO history (user_id, role, content) VALUES (?, 'assistant', ?)", (user_id, answer))
            
            await update.message.reply_text(answer)
        except Exception as e:
            logger.error(f"Groq API Error: {e}")
            await update.message.reply_text("☢️ Критическая ошибка нейросети. Чат перегружен.")

    def run(self):
        token = os.getenv("TELEGRAM_TOKEN")
        app = ApplicationBuilder().token(token).build()
        app.add_handler(MessageHandler(filters.ALL, self.on_message))
        logger.info(f"Hendelek Universal OS Started on {self.model}")
        app.run_polling()

if __name__ == "__main__":
    # Не забудь: pip install pandas openpyxl python-docx PyPDF2 duckduckgo_search python-dotenv groq python-telegram-bot
    UniversalHendelekOS().run()