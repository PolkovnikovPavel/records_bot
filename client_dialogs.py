from auth import token
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import time
import sqlite3


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


async def delete_message(update, context, person_date, to_del_message):
    if to_del_message is not None and person_date[1] in to_del_message:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=to_del_message[person_date[1]]
        )


async def menu_1_welcome(update: Update, context: CallbackContext, con, cur, person_date):
    # Текст сообщения
    text = "Добро пожаловать! Это система автоматической записи на массаж.\nКак вас можно записывать в расписании?\nЭту информацию можно будет поменять в любой момент"

    keyboard = [
        [person_date[2]],
        ['О проекте']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)

    # Отправляем сообщение
    await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_5_get_name(update: Update, context: CallbackContext, con, cur, person_date):
    answer = update.message.text

    if answer == 'О проекте':
        text = "Тут небольшое описание о том, что это электронный дневник (расписание). Укажите как вас подписывать."
        keyboard = [
            [person_date[2]],
            ['О проекте']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
        await update.message.reply_text(text, reply_markup=reply_markup)
        return
    new_name = answer
    new_name.replace('"', '')
    new_name.replace("'", '')

    # Обновляем информацию о пользователе
    inquiry = f"""UPDATE accounts
        SET name = '{new_name}'
            WHERE tg_id = {person_date[1]}"""
    cur.execute(inquiry)
    con.commit()

    text = 'Укажите пожалуйста ваш номер телефона, чтоб мы могли перезвонить'
    keyboard = [
        [KeyboardButton("Отправить номер телефона", request_contact=True)],
        ['Пока без номера']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(text, reply_markup=reply_markup)
    change_tg_menu(person_date[1], 6, con, cur)


async def menu_6_get_phone_number(update: Update, context: CallbackContext, con, cur, person_date):
    # Текст сообщения
    text = "Спасибо, на этом регистрация завершена. Вы в главном меню"

    if update.message.contact:
        # Обновляем информацию о пользователе
        inquiry = f"""UPDATE accounts
                SET phone_number = '{update.message.contact.phone_number}'
                    WHERE tg_id = {person_date[1]}"""
        cur.execute(inquiry)
        con.commit()
    else:
        text = "Добавить номер телефона всегда можно из меню обновления контактной информации. Вы в главном меню..."
    # Отправляем сообщение
    await update.message.reply_text(text)
    change_tg_menu(person_date[1], 2, con, cur)
    await menu_2_main_menu(update, context, con, cur, person_date)


async def menu_2_main_menu(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Главное меню"

    keyboard = [
        ['Записаться на приём'],
        ['мои записи'],
        ['Общее расписание', 'Описание'],
        ['Обновить контактную информацию']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    # Отправляем сообщение
    await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_7(update: Update, context: CallbackContext, con, cur, person_date, mode=1, last_inlines=None):
    text = "Что именно хотите поменять?"

    keyboard = [
        [InlineKeyboardButton("Имя", callback_data='user_name')],
        [InlineKeyboardButton("Номер телефона", callback_data='phone_number')],
        [InlineKeyboardButton("Отмена", callback_data='cancel')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if mode == 1:   # отправка нового сообщения
        await update.message.reply_text(text, reply_markup=reply_markup)
        if last_inlines is not None:
            last_inlines[person_date[1]] = update.message.message_id
    else:           # изменение старого сообщения
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)


async def menu_3_get_name(update: Update, context: CallbackContext, con, cur, person_date, last_inlines=None):
    answer = update.message.text

    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        change_tg_menu(person_date[1], 2, con, cur)
        await menu_2_main_menu(update, context, con, cur, person_date)
        return

    new_name = answer

    # Обновляем информацию о пользователе
    try:
        inquiry = f"""UPDATE accounts
            SET name = '{new_name}'
                WHERE tg_id = {person_date[1]}"""
        cur.execute(inquiry)
        con.commit()
    except Exception:
        new_name = person_date[2]

    if last_inlines is not None and person_date[1] in last_inlines:
            await context.bot.edit_message_text(
                text=f'Теперь вы подписаны как "{new_name}"',
                chat_id=update.effective_chat.id,
                message_id=last_inlines[person_date[1]] + 1
            )
    else:
        text=f'Теперь вы подписаны как "{new_name}"',
        await update.message.reply_text(text)

    change_tg_menu(person_date[1], 2, con, cur)
    await menu_2_main_menu(update, context, con, cur, person_date)


async def menu_4_get_phone_number(update: Update, context: CallbackContext, con, cur, person_date, last_inlines=None, to_del_message=None):
    if update.message.contact:
        try:
            inquiry = f"""UPDATE accounts
                SET phone_number = '{update.message.contact.phone_number}'
                    WHERE tg_id = {person_date[1]}"""
            cur.execute(inquiry)
            con.commit()
            text = 'Ваш номер телефона записан.'

        except Exception:
            await update.message.reply_text('Ошибка записи номера телефона, вы в главном меню.')
            change_tg_menu(person_date[1], 2, con, cur)
            await menu_2_main_menu(update, context, con, cur, person_date)
            return
    else:
        if update.message.text == 'Отмена':
            text = 'Телефон не записан.'
        else:
            return

    if last_inlines is not None and person_date[1] in last_inlines:
        await context.bot.edit_message_text(
            text=text,
            chat_id=update.effective_chat.id,
            message_id=last_inlines[person_date[1]] + 1
        )
    await delete_message(update, context, person_date, to_del_message)

    change_tg_menu(person_date[1], 2, con, cur)
    await menu_2_main_menu(update, context, con, cur, person_date)


async def menu_8_general_timetable(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Просмотреть расписание целиком и в красивом оформление можно по ссылке"
    keyboard = [
        [InlineKeyboardButton("Общее расписание ", url='https://github.com/PolkovnikovPavel')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

    change_tg_menu(person_date[1], 2, con, cur)
    await menu_2_main_menu(update, context, con, cur, person_date)
