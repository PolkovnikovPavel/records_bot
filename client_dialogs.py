from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters

import auth
import telegram_calendar
import support_functions

import datetime


last_inlines = {}
to_del_messages = {}
calendar_data = {}
selected_record = {}
added_records = {}
records_to_cancel = {}


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


def add_person_to_list(tg_id):
    if tg_id not in to_del_messages:
        to_del_messages[tg_id] = []
    if tg_id not in added_records:
        added_records[tg_id] = []


async def spam_to_admins(context: CallbackContext, message):
    for admin_id in auth.admins:
        await context.bot.send_message(text=message, chat_id=admin_id)


async def send_added_records_to_admins(update: Update, context: CallbackContext, con, cur, person_date):
    if len(added_records[person_date[1]]) == 0 or person_date[7]:
        return
    ids = []
    for id in added_records[person_date[1]]:
        ids.append(f'records.id = {id}')
    ids = ' OR '.join(ids)
    cur.execute(f'''SELECT DISTINCT records.time, days.date FROM records, days
    WHERE days.id = records.day_id AND ({ids}) ''')
    result = cur.fetchall()
    text = []

    for time, date in result:
        date = datetime.datetime.strptime(date, "%d.%m.%Y")
        week = telegram_calendar.week_days[date.weekday()]
        text.append(f'📅 {date.strftime("%d.%m.%Y")} ({week}) - ⏰ {time}')

    text = f'Пользователь {person_date[2]} (+{person_date[3]}) записался на приём:\n' + '\n'.join(text)
    await spam_to_admins(context, text)
    added_records[person_date[1]] = []


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


# ============================================================================================ Персональные данные


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
    # text = "Просмотреть расписание целиком и в красивом оформление можно по ссылке"
    # keyboard = [
    #     [InlineKeyboardButton("Общее расписание ", url='https://github.com/PolkovnikovPavel')]
    # ]
    text = 'В разработке 🛠️'

    # reply_markup = InlineKeyboardMarkup(keyboard)
    # await update.message.reply_text(text, reply_markup=reply_markup)
    await update.message.reply_text(text)

    change_tg_menu(person_date[1], 3, con, cur)
    await menu_3_main_menu(update, context, con, cur, person_date)


# ======================================================================================= Запись на приём

async def menu_21_take(update: Update, context: CallbackContext, con, cur, person_date):
    now = datetime.datetime.now()
    first_day, ignored_days, last_day = support_functions.get_clients_first_ignored_and_last_days(cur, person_date[0])

    calendar_data[person_date[1]] = [first_day, ignored_days, last_day, now]

    await update.message.reply_text(text='Календарь:\n⭘ - есть свободное время\n◉ - есть запись',
                                    reply_markup=telegram_calendar.create_calendar(first_day=first_day,
                                                                                   ignored_days=ignored_days,
                                                                                   last_day=last_day))


async def menu_21_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    (kind, _, _, _, _) = telegram_calendar.separate_callback_data(query.data)
    if kind == 'CALENDAR':
        if person_date[1] in calendar_data:
            selected, date = await telegram_calendar.process_calendar_selection(update, context, *calendar_data[person_date[1]][:3])
        else:
            await support_functions.delete_message(update, context, query.message.message_id)
            await menu_3_main_menu(query, context, con, cur, person_date)
            change_tg_menu(person_date[1], 3, con, cur)
            return
        if selected:
            if date is None:
                await send_added_records_to_admins(update, context, con, cur, person_date)
                await menu_3_main_menu(query, context, con, cur, person_date)
                change_tg_menu(person_date[1], 3, con, cur)
                return
            await menu_22_take(update, context, con, cur, person_date, query.message.message_id)
            change_tg_menu(person_date[1], 22, con, cur)
    else:
        await menu_3_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 3, con, cur)


async def menu_22_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None, date=None):
    query = update.callback_query
    if date is None:
        (_, action, year, month, day) = telegram_calendar.separate_callback_data(query.data)
        date = datetime.datetime(int(year), int(month), int(day))
        calendar_data[person_date[1]][3] = date

    text = f"Выберите свободное время на {date.strftime('%d.%m.%Y')} ({telegram_calendar.week_days[date.weekday()]})"

    cur.execute(f'''SELECT DISTINCT * FROM days
            WHERE date = "{date.strftime('%d.%m.%Y')}"''')
    result = cur.fetchall()
    if result:
        cur.execute(f'''SELECT DISTINCT * FROM records
            WHERE day_id = {result[0][0]} AND (patient_id IS NULL OR patient_id = {person_date[0]}) AND is_cancel = 0''')
        result = cur.fetchall()
        keyboard = []
        result.sort(key=lambda x: support_functions.get_count_minutes(x[3]))
        for record in result:
            if record[5]:
                keyboard.append([InlineKeyboardButton(f"✖ {record[3]}", callback_data='null')])
            elif record[2] is None:
                keyboard.append([InlineKeyboardButton(f"⭘ {record[3]}", callback_data=f'record_{record[0]}')])
            elif record[4]:
                keyboard.append([InlineKeyboardButton(f"✓ {record[3]}", callback_data='null')])
            else:
                keyboard.append([InlineKeyboardButton(f"◉ {record[3]}", callback_data='null')])
    else:
        keyboard = []

    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=message_id,
                                        reply_markup=reply_markup)
    else:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id,
                                            reply_markup=reply_markup)


async def menu_22_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        first_day, ignored_days, last_day = support_functions.get_clients_first_ignored_and_last_days(cur, person_date[0])
        calendar_data[person_date[1]][:3] = first_day, ignored_days, last_day
        await telegram_calendar.redraw_calendar(update, context, None, None, *calendar_data[person_date[1]][:3])
        change_tg_menu(person_date[1], 21, con, cur)
        return
    elif 'record_' in query.data:
        record_id = query.data.split('_')[1]
        selected_record[person_date[1]] = record_id
        await menu_23_take(update, context, con, cur, person_date, query.message.message_id)
        change_tg_menu(person_date[1], 23, con, cur)


async def menu_23_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    cur.execute(f'''SELECT DISTINCT records.time, days.date FROM records, days
                WHERE days.id = records.day_id AND records.id = {selected_record[person_date[1]]}''')
    result = cur.fetchall()[0]

    text = f'Подтвердите бронь записи на {result[1]} в {result[0]}'
    keyboard = [
        [InlineKeyboardButton(f"Да", callback_data=f'yes'),
         InlineKeyboardButton(f"Нет", callback_data=f'no')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=message_id,
                                            reply_markup=reply_markup)
    else:
        query = update.callback_query
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id,
                                            reply_markup=reply_markup)


async def menu_23_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    if person_date[1] not in selected_record:
        print('Ошибка: в момент перед фиксацией пользователя была потеряна информация о records.id')
        await menu_3_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 3, con, cur)
        return

    if query.data == 'yes':
        added_records[person_date[1]].append(selected_record[person_date[1]])
        inquiry = f"""UPDATE records
            SET patient_id = {person_date[0]}
                WHERE id = {selected_record[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
        await menu_24_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 24, con, cur)
    else:
        await menu_22_take(update, context, con, cur, person_date, query.message.message_id, calendar_data[person_date[1]][3])
        change_tg_menu(person_date[1], 22, con, cur)


async def menu_24_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query

    cur.execute(f'''SELECT DISTINCT * FROM admin_data''')
    result = cur.fetchall()
    address = list(filter(lambda x: x[1] == 'address', result))[0][2]
    name_specialist = list(filter(lambda x: x[1] == 'master_name', result))[0][2]

    cur.execute(f'''SELECT DISTINCT records.time, days.date FROM records, days
                            WHERE days.id = records.day_id AND records.id = {selected_record[person_date[1]]} ''')
    result = cur.fetchall()[0]
    week = telegram_calendar.week_days[calendar_data[person_date[1]][3].weekday()]

    text = f'Вы записаны: {name_specialist}\n📅 {result[1]} ({week})\n⏰ {result[0]}\n🗺️ {address}.\n🔔 За сутки вам придёт напоминание.'
    keyboard = [
        [InlineKeyboardButton(f"Записаться ещё", callback_data=f'continue'),
         InlineKeyboardButton(f"Готово", callback_data=f'done')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        reply_markup=reply_markup,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id)


async def menu_24_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'done':
        await context.bot.edit_message_text(text=query.message.text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)

        await send_added_records_to_admins(update, context, con, cur, person_date)

        await menu_3_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 3, con, cur)
    elif query.data == 'continue':
        await context.bot.edit_message_text(text=query.message.text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_21_take(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 21, con, cur)


# ======================================================================================= Моё расписание


async def menu_31_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    records_data = support_functions.get_future_records(cur, person_date[0])
    records_text = []
    num = 0
    for time, date, record_id in records_data:
        num += 1
        records_text.append(f'{num}) 📅 {date.strftime("%d.%m.%Y")} ({telegram_calendar.week_days[date.weekday()]}) - ⏰ {time}')

    cur.execute(f'''SELECT DISTINCT * FROM admin_data''')
    result = cur.fetchall()
    address = list(filter(lambda x: x[1] == 'address', result))[0][2]
    name_specialist = list(filter(lambda x: x[1] == 'master_name', result))[0][2]

    temp = '\n'.join(records_text)
    text = f'Ваше ближайшее расписание {name_specialist} по адресу "{address}":\n{temp}'
    keyboard = [
        [InlineKeyboardButton(f"Отменить запись", callback_data=f'cancel_recording'),
         InlineKeyboardButton(f"В меню", callback_data=f'exit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=message_id,
                                            reply_markup=reply_markup)
        last_inlines[person_date[1]] = message_id
    else:
        massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
        last_inlines[person_date[1]] = massage.message_id


async def menu_31_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'exit':
        await context.bot.edit_message_text(text=query.message.text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_3_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 3, con, cur)
        return

    records_to_cancel[person_date[1]] = []
    await menu_32_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 32, con, cur)


async def menu_32_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query

    records_data = support_functions.get_future_records(cur, person_date[0])
    records_text = []
    keyboard = []
    num = 0
    for time, date, record_id in records_data:
        num += 1
        t = f'{num}) {date.strftime("%d.%m.%Y")} ({telegram_calendar.week_days[date.weekday()]}) в {time}'
        records_text.append(t)
        if record_id in records_to_cancel[person_date[1]]:
            keyboard.append([InlineKeyboardButton(f"❌ {t}", callback_data=f'cancel_{record_id}')])
        else:
            keyboard.append([InlineKeyboardButton(f"✅ {t}", callback_data=f'cancel_{record_id}')])

    keyboard.append([InlineKeyboardButton(f"Сохранить", callback_data=f'save')])

    temp = '\n'.join(records_text)
    text = f'''Укажите, какие записи вы хотите отменить (нажимайте на кнопки ниже), в конце обязательно сохраните.\n
Ваши записи, для удобства пронумерованы:\n{temp}'''
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        reply_markup=reply_markup,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id)


async def menu_32_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'save':
        if len(records_to_cancel[person_date[1]]) == 0:
            await menu_31_take(update, context, con, cur, person_date, query.message.message_id)
            change_tg_menu(person_date[1], 31, con, cur)
            return

        del_list = []
        for id in records_to_cancel[person_date[1]]:
            del_list.append(f'id = {id}')
        del_list = ' OR '.join(del_list)

        inquiry = f"""UPDATE records
                    SET patient_id = NULL, is_verification = 0, is_reminder = 0, is_ended = 0
                        WHERE {del_list}"""
        cur.execute(inquiry)
        con.commit()

        del_list = []
        for id in records_to_cancel[person_date[1]]:
            del_list.append(f'records.id = {id}')
        del_list = ' OR '.join(del_list)
        cur.execute(f'''SELECT DISTINCT records.time, days.date FROM records, days
        WHERE days.id = records.day_id AND records.is_cancel = 0 AND ({del_list})''')
        result = cur.fetchall()

        text = f'Пользователь "{person_date[2]}" (+{person_date[3]}) Отменил следующие записи:\n'
        for time, date in result:
            date = datetime.datetime.strptime(date, '%d.%m.%Y')
            week = telegram_calendar.week_days[date.weekday()]
            text += f'📅 {date.strftime("%d.%m.%Y")} ({week}) ⏰ {time}\n'

        await spam_to_admins(context, text)

        await menu_31_take(update, context, con, cur, person_date, query.message.message_id)
        change_tg_menu(person_date[1], 31, con, cur)
    elif 'cancel_' in query.data:
        record_id = int(query.data.split('_')[1])
        if record_id in records_to_cancel[person_date[1]]:
            records_to_cancel[person_date[1]].remove(record_id)
        else:
            records_to_cancel[person_date[1]].append(record_id)

        await menu_32_take(update, context, con, cur, person_date)


# =========================================================================================== Мои жалобы

# TODO обязать написание жалобы, если нет активных (активная - это нет хотя бы одной оценки из двух)
async def menu_41_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    cur.execute(f'''SELECT DISTINCT * FROM complaints 
    WHERE user_id = {person_date[0]}''')
    result = cur.fetchall()

    if len(result) == 0:
        text = f'''В этом разделе будут отображаться ваши жалобы, когда вы их добавите, это нужно, чтоб специалист мог понимать с чем предстоит работать и оценить эффективность работы.
    \n❗ Для каждой жалобы будет 2 опросника после процедур'''
        keyboard = [
            [InlineKeyboardButton(f"Добавить жалобу", callback_data=f'add'),
             InlineKeyboardButton(f"Назад", callback_data=f'back')]
        ]
    else:
        text = []
        for i in range(len(result)):
            grad_1, grad_2 = result[i][4], result[i][5]
            if grad_1 is None:
                grad_1 = '—'
            if grad_2 is None:
                grad_2 = '—'
            text.append(f'📌 {result[i][2]} - {result[i][3]}\nОценка до: {grad_1}\nПосле: {grad_2}')
        text = 'Все ваши жалобы:\n' + '\n'.join(text)
        keyboard = [
            [InlineKeyboardButton(f"Добавить жалобу", callback_data=f'add'),
             InlineKeyboardButton(f"Готово", callback_data=f'back')]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=message_id,
                                            reply_markup=reply_markup)
        last_inlines[person_date[1]] = message_id
    else:
        massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
        last_inlines[person_date[1]] = massage.message_id


async def menu_41_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        cur.execute(f'''SELECT DISTINCT * FROM complaints 
        WHERE user_id = {person_date[0]}''')
        result = cur.fetchall()
        if len(result) == 0:
            await support_functions.delete_message(update, context, query.message.message_id)
            await menu_3_main_menu(query, context, con, cur, person_date)
            change_tg_menu(person_date[1], 3, con, cur)
            return
        await context.bot.edit_message_text(text=query.message.text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_3_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 3, con, cur)
        return
    elif query.data == 'add':
        await menu_42_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 42, con, cur)


async def menu_42_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    text = 'Кратко опишите на что жалуетесь'
    keyboard = [
        [InlineKeyboardButton(f"Назад", callback_data=f'back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(text=text,
                                        reply_markup=reply_markup,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id)


async def menu_42_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        change_tg_menu(person_date[1], 41, con, cur)
        await menu_41_take(update, context, con, cur, person_date, last_inlines[person_date[1]])
        return
    answer = update.message.text

    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        change_tg_menu(person_date[1], 3, con, cur)
        await menu_3_main_menu(update, context, con, cur, person_date)
        return
    new_complaint = answer
    now = datetime.datetime.now()

    inquiry = f"""INSERT INTO complaints (user_id, date, text)
    VALUES ({person_date[0]}, '{now.strftime("%d.%m.%Y")}', '{new_complaint}')"""
    cur.execute(inquiry)
    con.commit()

    await support_functions.delete_message(update, context, update.message.message_id)
    await menu_41_take(update, context, con, cur, person_date, last_inlines[person_date[1]])
    change_tg_menu(person_date[1], 41, con, cur)


# =========================================================================================== Оповещения


async def notification_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    if 'remeber_yes_' in query.data:
        record_id = query.data.split('_')[-1]
        inquiry = f"""UPDATE records
        SET is_verification = 1
        WHERE id = {record_id}"""
        cur.execute(inquiry)
        con.commit()
        await context.bot.edit_message_text(text="Спасибо за ответ!",
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        return True
    elif 'remeber_no_' in query.data:
        record_id = query.data.split('_')[-1]
        inquiry = f"""UPDATE records
        SET patient_id = NULL, is_verification = 0, is_reminder = 0, is_ended = 0
            WHERE id = {record_id}"""
        cur.execute(inquiry)
        con.commit()

        cur.execute(f'''SELECT DISTINCT records.time, days.date FROM records, days
        WHERE days.id = records.day_id AND records.is_cancel = 0 AND records.id = {record_id}''')
        result = cur.fetchall()[0]

        text = f'Пользователь "{person_date[2]}" (+{person_date[3]}) не придёт завтра:\n'
        date = datetime.datetime.strptime(result[1], '%d.%m.%Y')
        week = telegram_calendar.week_days[date.weekday()]
        text += f'📅 {date.strftime("%d.%m.%Y")} ({week}) ⏰ {result[0]}\nЗапись открыта.'
        await context.bot.edit_message_text(text="Ничего страшного, запись отменена.",
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)

        await spam_to_admins(context, text)
        return True
    return False


# =========================================================================================== Главное меню


async def menu_3_main_menu(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Главное меню."

    keyboard = [
        ['Записаться на приём'],
        ['Моё расписание'],
        ['Общее расписание', 'Мои жалобы'],
        ['🏠', 'Обновить контактную информацию']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def client_button_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    if await notification_get(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 11:
        await menu_11_get(update, context, con, cur, person_date)
    elif person_date[4] == 12:
        await menu_12_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 21:
        await menu_21_get(update, context, con, cur, person_date)
    elif person_date[4] == 22:
        await menu_22_get(update, context, con, cur, person_date)
    elif person_date[4] == 23:
        await menu_23_get(update, context, con, cur, person_date)
    elif person_date[4] == 24:
        await menu_24_get(update, context, con, cur, person_date)
    elif person_date[4] == 31:
        await menu_31_get(update, context, con, cur, person_date)
    elif person_date[4] == 32:
        await menu_32_get(update, context, con, cur, person_date)
    elif person_date[4] == 41:
        await menu_41_get(update, context, con, cur, person_date)
    elif person_date[4] == 42:
        await menu_42_get(update, context, con, cur, person_date, True)


async def client_text_message_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 1:
        await menu_1_get(update, context, con, cur, person_date)
    elif person_date[4] == 2:
        await menu_2_get(update, context, con, cur, person_date)
    else:
        if update.message.text == '🏠':
            change_tg_menu(person_date[1], 3, con, cur)
            await menu_3_main_menu(update, context, con, cur, person_date)
            return
    if person_date[4] == 3:   # Главное меню
        if update.message.text == 'Обновить контактную информацию':
            await menu_11_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 11, con, cur)
        elif update.message.text == 'Общее расписание':
            await menu_14_take(update, context, con, cur, person_date)
        elif update.message.text == 'Записаться на приём':
            await menu_21_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 21, con, cur)
        elif update.message.text == 'Моё расписание':
            await menu_31_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 31, con, cur)
        elif update.message.text == 'Мои жалобы':
            await menu_41_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 41, con, cur)
        else:
            await menu_3_main_menu(update, context, con, cur, person_date)

    elif person_date[4] == 12:
        await menu_12_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 42:
        await menu_42_get(update, context, con, cur, person_date, False)


async def client_contact_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if await check_is_baned(update, context, con, cur, person_date):
        return
    add_person_to_list(person_date[1])
    if person_date[4] == 2:
        await menu_2_get(update, context, con, cur, person_date)
    if person_date[4] == 13:
        await menu_13_get(update, context, con, cur, person_date, False)

