from client_dialogs import client_button_handler, client_text_message_handler, client_contact_handler, menu_1_take
from admin_dialogs import admin_button_handler, admin_text_message_handler, admin_contact_handler, check_is_admin, menu_100_welcome
from support_functions import change_tg_menu
from auth import *

import sqlite3
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters

con = sqlite3.connect('data/db.db')
cur = con.cursor()
timer_con = time.time()
last_inlines = {}
to_del_message = {}

is_admin_menu = {}
for id in admins:
    is_admin_menu[id] = False


def create_con():
    global con, cur, timer_con
    text = f'Срок действия курсора вышел ({int(time.time() - timer_con)}сек.)'
    print(text)

    con = sqlite3.connect('data/db.db')
    cur = con.cursor()

    timer_con = time.time()


def check_timer_con(mod=0):
    if mod == 1:
        create_con()
    if time.time() - timer_con > 3 * 60:   # 3 минуты
        create_con()


def create_user(message, mod=False):
    if not mod:
        cur.execute(f'''SELECT DISTINCT * FROM accounts
        WHERE tg_id = {message.chat_id}''')
        result = cur.fetchall()
    else:
        result = False

    if not result:
        inquiry = f"""INSERT INTO accounts (tg_id, name, phone_number, tg_menu, number_requests, tg_link)
VALUES ({message.chat_id}, '{message.from_user.full_name}', '{message.from_user.link}', 1, 0, '{message.from_user.link}')"""
        cur.execute(inquiry)
        con.commit()
        print(f'добавлен новый пользователь, id = {message.chat_id}, name = {message.from_user.full_name}')


def get_data_of_person(message):
    check_timer_con()
    cur.execute(f'''SELECT DISTINCT * FROM accounts
    WHERE tg_id = {message.chat_id}''')
    result = cur.fetchall()
    if not result:
        create_user(message, True)
        cur.execute(f'''SELECT DISTINCT * FROM accounts
    WHERE tg_id = {message.chat_id}''')
        result = cur.fetchall()
    return result[0]


# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await menu_100_welcome(update, context, con, cur, person_date)
            return
    if person_date[4] == 1:
        await menu_1_take(update, context, con, cur, person_date)
    else:
        change_tg_menu(person_date[1], 3, con, cur)
        person_date = get_data_of_person(update.message)
        await client_text_message_handler(update, context, con, cur, person_date)


# Обработчик команды /switch для админов
async def switch_admin(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        is_admin_menu[person_date[1]] = not is_admin_menu[person_date[1]]
    await start(update, context)


# Обработчик нажатия кнопок
async def button_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.callback_query.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_button_handler(update, context, con, cur, person_date)
            return

    await client_button_handler(update, context, con, cur, person_date)

    query = update.callback_query
    await query.answer()


# Обработчик получения контакта
async def contact_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_contact_handler(update, context, con, cur, person_date)
            return
    await client_contact_handler(update, context, con, cur, person_date)


# Обработчик текстовых сообщений
async def text_message_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_text_message_handler(update, context, con, cur, person_date)
            return
    await client_text_message_handler(update, context, con, cur, person_date)


def main():
    # Создание подключения к базе данных
    create_con()

    application = Application.builder().token(token).build()

    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler('switch', switch_admin))

    # Регистрируем обработчик callback-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT, text_message_handler))

    # Регистрируем обработчик контактов
    application.add_handler(MessageHandler(filters.CONTACT, contact_handler))

    # Запускаем бота
    application.run_polling()


if __name__ == '__main__':
    main()
