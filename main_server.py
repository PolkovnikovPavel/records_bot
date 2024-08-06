import asyncio
import threading
import sqlite3
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
from auth import *


# Асинхронная функция для отправки сообщения
async def send_message(application, text, chat_id, reply_markup=None):
    await application.bot.send_message(text=text, chat_id=chat_id, reply_markup=reply_markup)


# Функция для выполнения периодической рассылки
def spam_every_30_minutes(application: Application, loop: asyncio.AbstractEventLoop):
    con = sqlite3.connect('data/db.db')
    cur = con.cursor()
    while True:
        for i in range(5):
            # Используем run_coroutine_threadsafe для безопасного выполнения асинхронной функции из другого потока
            asyncio.run_coroutine_threadsafe(
                send_message(application, str(i), admins[0]),
                loop
            )
            threading.Event().wait(1)
        threading.Event().wait(5)


async def start_post_init(application):
    await application.bot.send_message(text='bot started', chat_id=admins[0])
    # Передаем текущий событийный цикл
    loop = asyncio.get_running_loop()
    independent_thread = threading.Thread(target=spam_every_30_minutes, args=(application, loop))
    independent_thread.start()
    print('bot')

if __name__ == '__main__':
    # Настройка и запуск бота
    application = Application.builder().token(token).post_init(start_post_init).build()
    application.run_polling()
