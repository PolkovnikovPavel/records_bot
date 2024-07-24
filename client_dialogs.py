from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters

import telegram_calendar
import support_functions


last_inlines = {}
to_del_messages = {}


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


def add_person_to_list(tg_id):
    if tg_id not in to_del_messages:
        to_del_messages[tg_id] = []


async def check_is_baned(update: Update, context: CallbackContext, con, cur, person_date):
    if person_date[8]:
        text = "Ваш аккаунт был заблокирован, вы не можете пользоваться ботом"
        await update.message.reply_text(text)
        return True
    return False


async def menu_0_get(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Добро пожаловать! Это система автоматической записи на массаж."

    await update.message.reply_text(text)


async def menu_1_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = """Добро пожаловать! Это система автоматической записи на массаж.
Как вас можно записывать в расписании?\nЭту информацию можно будет поменять в любой момент"""

    keyboard = [
        [person_date[2]],
        ['О проекте']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=False, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)
    change_tg_menu(person_date[1], 1, con, cur)


async def menu_1_get(update: Update, context: CallbackContext, con, cur, person_date):
    answer = update.message.text

    if answer == 'О проекте':
        text = "Тут небольшое описание о том, что это электронный дневник (расписание).\n\nУкажите как вас подписать."
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
    await menu_2_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 2, con, cur)


async def menu_2_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = 'Укажите пожалуйста ваш номер телефона, чтоб мы могли перезвонить'
    keyboard = [
        [KeyboardButton("Отправить номер телефона", request_contact=True)],
        ['Пока без номера']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)

    await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_2_get(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Спасибо, на этом регистрация завершена. Вы в главном меню"

    if update.message.contact or update.message.text.isdigit():
        if update.message.contact:
            phone_number = update.message.contact.phone_number
        else:
            phone_number = update.message.text
        # Обновляем информацию о пользователе
        inquiry = f"""UPDATE accounts
                    SET phone_number = '{phone_number}'
                        WHERE tg_id = {person_date[1]}"""
        cur.execute(inquiry)
        con.commit()
    else:
        text = "Добавить номер телефона всегда можно из меню обновления контактной информации. Вы в главном меню..."

    await update.message.reply_text(text)
    change_tg_menu(person_date[1], 3, con, cur)
    await menu_3_main_menu(update, context, con, cur, person_date)


# ============================================================================================================


async def menu_11_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = "Какие персональные данных вы хотите поменять?"

    keyboard = [
        [InlineKeyboardButton("Имя", callback_data='user_name')],
        [InlineKeyboardButton("Номер телефона", callback_data='phone_number')],
        [InlineKeyboardButton("Отмена", callback_data='cancel')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            reply_markup=reply_markup,
                                            message_id=message_id)
        last_inlines[person_date[1]] = message_id
    else:
        message = await update.message.reply_text(text, reply_markup=reply_markup)
        last_inlines[person_date[1]] = message.message_id


async def menu_11_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'cancel':
        change_tg_menu(person_date[1], 3, con, cur)
        await menu_3_main_menu(update.callback_query, context, con, cur, person_date)
        await query.edit_message_text(text='Действие отменено')

    if query.data == 'user_name':
        await menu_12_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 12, con, cur)

    if query.data == 'phone_number':
        await menu_13_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 13, con, cur)


async def menu_12_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Как вас подписать в расписании, чтоб было понятно кто вы?"

    keyboard = [
        [InlineKeyboardButton("Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        reply_markup=reply_markup,
                                        message_id=last_inlines[person_date[1]])


async def menu_12_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        change_tg_menu(person_date[1], 11, con, cur)
        await menu_11_take(update, context, con, cur, person_date, last_inlines[person_date[1]])
        return
    answer = update.message.text

    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        change_tg_menu(person_date[1], 3, con, cur)
        await menu_3_main_menu(update, context, con, cur, person_date)
        return
    new_name = answer

    try:
        inquiry = f"""UPDATE accounts
                SET name = '{new_name}'
                    WHERE tg_id = {person_date[1]}"""
        cur.execute(inquiry)
        con.commit()
    except Exception:
        new_name = person_date[2]

    if person_date[1] in last_inlines:
        await context.bot.edit_message_text(
            text=f'Теперь вы подписаны как "{new_name}"',
            chat_id=person_date[1],
            message_id=last_inlines[person_date[1]]
        )
    else:
        text = f'Теперь вы подписаны как "{new_name}"',
        await update.message.reply_text(text)

    change_tg_menu(person_date[1], 3, con, cur)
    await menu_3_main_menu(update, context, con, cur, person_date)


async def menu_13_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query

    text = "Укажите ваш номер телефона, чтобы мы могли перезвонить для уточнения записи"
    keyboard = [
        [InlineKeyboardButton("Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)

    keyboard = [[KeyboardButton("Отправить номер телефона", request_contact=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    message = await query.message.reply_text('📞', reply_markup=reply_markup)
    to_del_messages[person_date[1]].append(message.message_id)


async def menu_13_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        await support_functions.delete_messages(update, context, to_del_messages[person_date[1]])
        change_tg_menu(person_date[1], 11, con, cur)
        await menu_11_take(update, context, con, cur, person_date, last_inlines[person_date[1]])
        return
    if update.message.contact or update.message.text.isdigit():
        try:
            if update.message.contact:
                phone_number = update.message.contact.phone_number
            else:
                phone_number = update.message.text
            inquiry = f"""UPDATE accounts
                SET phone_number = '{phone_number}'
                    WHERE tg_id = {person_date[1]}"""
            cur.execute(inquiry)
            con.commit()
            text = f'Ваш номер телефона записан, как "{phone_number}"'

        except Exception:
            await update.message.reply_text('Ошибка записи номера телефона, вы в главном меню.')
            change_tg_menu(person_date[1], 3, con, cur)
            await menu_3_main_menu(update, context, con, cur, person_date)
            return
    else:
        if update.message.text == 'Отмена':
            text = 'Телефон не записан.'
        else:
            return
    to_del_messages[person_date[1]].append(update.message.message_id)
    await support_functions.delete_messages(update, context, to_del_messages[person_date[1]])

    if person_date[1] in last_inlines:
        await context.bot.edit_message_text(
            text=text,
            chat_id=update.effective_chat.id,
            message_id=last_inlines[person_date[1]]
        )

    change_tg_menu(person_date[1], 3, con, cur)
    await menu_3_main_menu(update, context, con, cur, person_date)


async def menu_14_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Просмотреть расписание целиком и в красивом оформление можно по ссылке"
    keyboard = [
        [InlineKeyboardButton("Общее расписание ", url='https://github.com/PolkovnikovPavel')]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)

    change_tg_menu(person_date[1], 3, con, cur)
    await menu_3_main_menu(update, context, con, cur, person_date)


# ====================================================================================================


async def menu_3_main_menu(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Главное меню."

    keyboard = [
        ['Записаться на приём'],
        ['Моё расписание'],
        ['Общее расписание', 'Описание'],
        ['Обновить контактную информацию']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def client_button_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 11:
        await menu_11_get(update, context, con, cur, person_date)
    elif person_date[4] == 12:
        await menu_12_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, True)


async def client_text_message_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 1:
        await menu_1_get(update, context, con, cur, person_date)
    if person_date[4] == 2:
        await menu_2_get(update, context, con, cur, person_date)
    elif person_date[4] == 3:   # Главное меню
        if update.message.text == 'Обновить контактную информацию':
            await menu_11_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 11, con, cur)
        elif update.message.text == 'Общее расписание':
            await menu_14_take(update, context, con, cur, person_date)
        else:
            await menu_3_main_menu(update, context, con, cur, person_date)

    elif person_date[4] == 12:
        await menu_12_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, False)


async def client_contact_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 2:
        await menu_2_get(update, context, con, cur, person_date)
    if person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, False)

