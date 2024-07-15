from auth import token, admins
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters
import time
import sqlite3
import datetime
import telegram_calendar
import support_functions


admin_calendar_data = {}
last_admin_inlines = {}
count_deleted_msgs = {}
selected_template = {}


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


def check_is_admin(person_date):
    return person_date[1] in admins


async def change_account_type(is_admin_menu, person_date, value=True):
    if not check_is_admin(person_date):
        return
    is_admin_menu[person_date[1]] = value


async def menu_100_welcome(update: Update, context: CallbackContext, con, cur, person_date):
    # Текст сообщения
    text = """Добро пожаловать! Это закулисье автоматической системы - тут можно управлять почти всем\n
В любой непонятной ситуации введите команду /start"""
    keyboard = [['Далее']]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)
    change_tg_menu(person_date[1], 100, con, cur)


# ============================================================================================================


async def menu_102_take(update: Update, context: CallbackContext, con, cur, person_date):
    now = datetime.datetime.now()
    first_day, ignored_days, last_day = support_functions.get_first_ignored_and_last_days(cur)

    admin_calendar_data[person_date[1]] = [first_day, ignored_days, last_day, now]

    await update.message.reply_text(text='Календарь',
                reply_markup=telegram_calendar.create_calendar(first_day=first_day,
                                                               ignored_days=ignored_days,
                                                               last_day=last_day))


async def menu_102_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    (kind, _, _, _, _) = telegram_calendar.separate_callback_data(query.data)
    if kind == 'CALENDAR':
        selected, date = await telegram_calendar.process_calendar_selection(update, context, *admin_calendar_data[person_date[1]][:3])
        if selected:
            if date is None:
                await menu_101_main_menu(query, context, con, cur, person_date)
                change_tg_menu(person_date[1], 101, con, cur)
                return
            await menu_103_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 103, con, cur)
    else:
        await menu_101_main_menu(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)


async def menu_103_take(update: Update, context: CallbackContext, con, cur, person_date, date=None):
    query = update.callback_query
    if date is None:
        (_, action, year, month, day) = telegram_calendar.separate_callback_data(query.data)
        date = datetime.datetime(int(year),int(month),int(day))
        admin_calendar_data[person_date[1]][3] = date

    text = f"Расписание на {date.strftime('%d.%m.%Y')} ({telegram_calendar.week_days[date.weekday()]})"

    cur.execute(f'''SELECT DISTINCT * FROM days
        WHERE date = "{date.strftime('%d.%m.%Y')}"''')
    result = cur.fetchall()

    if result:
        cur.execute(f'''SELECT DISTINCT * FROM records
            WHERE day_id = {result[0][0]}''')
        result = cur.fetchall()
        keyboard = []
        result.sort(key=lambda x: support_functions.get_count_minutes(x[3]))
        for record in result:
            if record[5]:
                keyboard.append([InlineKeyboardButton(f"✖ {record[3]}", callback_data=f'record_{record[0]}')])
            elif record[2] is None:
                keyboard.append([InlineKeyboardButton(f"⭘ {record[3]}", callback_data=f'record_{record[0]}')])
            elif record[4]:
                keyboard.append([InlineKeyboardButton(f"✓ {record[3]}", callback_data=f'record_{record[0]}')])
            else:
                keyboard.append([InlineKeyboardButton(f"◉ {record[3]}", callback_data=f'record_{record[0]}')])

        keyboard.append([InlineKeyboardButton("+ Добавить новую запись", callback_data='new_record')])

    else:
        keyboard = [
            [InlineKeyboardButton("+ Добавить новую запись", callback_data='new_record')]
        ]
        cur.execute(f'''SELECT DISTINCT id, name FROM templates''')
        result = cur.fetchall()
        for template in result:
            keyboard.append([InlineKeyboardButton(f"Шаблон: {template[1]}", callback_data=f'template_{template[0]}')])

    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])

    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_103_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        first_day, ignored_days, last_day = support_functions.get_first_ignored_and_last_days(cur)
        admin_calendar_data[person_date[1]][:3] = first_day, ignored_days, last_day
        await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3])
        change_tg_menu(person_date[1], 102, con, cur)
        return
    elif query.data == 'new_record':
        await menu_104_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 104, con, cur)
    elif 'template_' in query.data:
        template_id = query.data.split('_')[1]

        cur.execute(f'''SELECT DISTINCT * FROM days
        WHERE date = "{admin_calendar_data[person_date[1]][3].strftime('%d.%m.%Y')}"''')
        result = cur.fetchall()
        if not result:
            inquiry = f"""INSERT INTO days (date)
            VALUES ('{admin_calendar_data[person_date[1]][3].strftime('%d.%m.%Y')}')"""
            cur.execute(inquiry)
            con.commit()
            cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 1''')
            result = cur.fetchall()
        day_id = result[0][0]

        cur.execute(f'''SELECT DISTINCT * FROM templates
        WHERE id = {template_id}''')
        times = support_functions.get_template_from_json(cur.fetchall()[0][2])
        for time in times:
            inquiry = f"""INSERT INTO records (day_id, time, is_verification, is_cancel, is_reminder)
            VALUES ({day_id}, '{time}', 0, 0, 0)"""
            cur.execute(inquiry)
            con.commit()

        await menu_103_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])

    # TODO сделать обработку record_xxx (перенаправление в меню записей)


async def menu_104_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    last_admin_inlines[person_date[1]] = query.message.message_id
    if person_date[1] not in count_deleted_msgs:
        count_deleted_msgs[person_date[1]] = 0

    text = 'Введите время для новой записи в формате "чч.мм", например "12.30"'

    keyboard = []
    cur.execute(f'''SELECT * FROM records ORDER BY id DESC LIMIT 1''')
    result = cur.fetchall()
    if result:
        keyboard.append([result[0][3].replace(':', '.')])
    keyboard.append(['Назад'])

    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await context.bot.edit_message_text(text=query.message.text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]])
    await query.message.reply_text(text, reply_markup=reply_markup)


async def menu_104_get(update: Update, context: CallbackContext, con, cur, person_date):
    is_wrong = True
    if update.message.text == 'Назад':
        await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3],
                                                chat_id=person_date[1], message_id=last_admin_inlines[person_date[1]])

        await context.bot.delete_messages(person_date[1], [last_admin_inlines[person_date[1]] + 1 + count_deleted_msgs[person_date[1]],
                                                     last_admin_inlines[person_date[1]] + 2 + count_deleted_msgs[person_date[1]]])
        count_deleted_msgs[person_date[1]] += 2
        change_tg_menu(person_date[1], 102, con, cur)
        return
    try:
        time = update.message.text.replace(':', '.')
        time = time.replace(',', '.')
        hour, minut = map(int, time.split('.')[:2])
        if hour < 0 or hour > 23 or minut < 0 or minut > 59:
            print(1 / 0)
        hour, minut = map(str, time.split('.')[:2])

        cur.execute(f'''SELECT DISTINCT * FROM days
                WHERE date = "{admin_calendar_data[person_date[1]][3].strftime('%d.%m.%Y')}"''')
        result = cur.fetchall()
        if result:
            inquiry = f"""INSERT INTO records (day_id, time, is_verification, is_cancel, is_reminder)
            VALUES ({result[0][0]}, '{hour}:{minut}', 0, 0, 0)"""
            cur.execute(inquiry)
            con.commit()
        else:
            inquiry = f"""INSERT INTO days (date)
                        VALUES ('{admin_calendar_data[person_date[1]][3].strftime('%d.%m.%Y')}')"""
            cur.execute(inquiry)
            con.commit()
            cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 1''')
            result = cur.fetchall()
            inquiry = f"""INSERT INTO records (day_id, time, is_verification, is_cancel, is_reminder)
                        VALUES ({result[0][0]}, '{hour}:{minut}', 0, 0, 0)"""
            cur.execute(inquiry)
            con.commit()
        is_wrong = False
    except Exception:
        is_wrong = True

    if is_wrong:
        keyboard = []
        cur.execute(f'''SELECT * FROM records ORDER BY id DESC LIMIT 1''')
        result = cur.fetchall()
        if result:
            keyboard.append([result[0][3].replace(':', '.')])
        keyboard.append(['Назад'])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        await update.message.reply_text('Не верный формат ответа', reply_markup=reply_markup)
    else:
        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]] + 1)
        count_deleted_msgs[person_date[1]] += 1
        await menu_105_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 105, con, cur)


async def menu_105_take(update: Update, context: CallbackContext, con, cur, person_date):
    cur.execute(f'''SELECT records.id, days.date, records.time FROM records, days
WHERE records.day_id = days.id
ORDER BY records.id DESC LIMIT 1''')
    result = cur.fetchall()[0]
    text = f"Добавлена новая запись в {result[2]} на {result[1]}"
    keyboard = [
        [InlineKeyboardButton("Готово", callback_data='done')],
        [InlineKeyboardButton("Добавить ещё", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if last_admin_inlines[person_date[1]]:
        await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]],
                                        reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_105_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    await context.bot.edit_message_text(text=query.message.text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]])
    count_deleted_msgs[person_date[1]] = 0
    if query.data == 'done':
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return
    elif query.data == 'back':
        await menu_102_take(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 102, con, cur)


# ========================================================================================================== Шаблоны

async def menu_111_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = 'Все шаблоны:'

    keyboard = [[InlineKeyboardButton("+ Добавить новый", callback_data='new')]]

    cur.execute(f'''SELECT * FROM templates''')
    result = cur.fetchall()
    for template in result:
        times = support_functions.get_template_from_json(template[2])
        times.sort(key=lambda x: support_functions.get_count_minutes(x))
        if len(times) > 0:
            times = f'({times[0]}...)'
        else:
            times = '()'

        keyboard.append([InlineKeyboardButton(f'{template[1]} {times}', callback_data=f'template_{template[0]}')])
    keyboard.append([InlineKeyboardButton('Закрыть', callback_data='close')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if message_id is not None:
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=message_id)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)


async def menu_111_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    last_admin_inlines[person_date[1]] = query.message.message_id

    if query.data == 'new':
        keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.edit_message_text(text='Введите название новому шаблону, названия не должны повторяться',
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=query.message.message_id)
        change_tg_menu(person_date[1], 112, con, cur)

    elif query.data == 'close':
        await context.bot.edit_message_text(text=query.message.text,
            chat_id=person_date[1],
            message_id=query.message.message_id)

        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
    else:
        template_id = int(query.data.split('_')[1])
        selected_template[person_date[1]] = template_id
        await menu_113_take(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 113, con, cur)


async def menu_112_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        new_name = update.message.text
        times = support_functions.get_json_from_template([])

        inquiry = f"""INSERT INTO templates (name, description)
        VALUES ('{new_name}', '{times}')"""
        cur.execute(inquiry)
        con.commit()
    if person_date[1] in last_admin_inlines:
        await menu_111_take(update, context, con, cur, person_date, last_admin_inlines[person_date[1]])
    else:
        if is_inline:
            query = update.callback_query
            await query.answer()
            await menu_111_take(query, context, con, cur, person_date)
        else:
            await menu_111_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 111, con, cur)


async def menu_113_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    if person_date[1] not in selected_template:
        return
    template_id = selected_template[person_date[1]]
    cur.execute(f'''SELECT * FROM templates
    WHERE id = {template_id}''')
    template = cur.fetchall()[0]

    text = f'Шаблон: "{template[1]}"\nДля удаления времени - выберете его'
    keyboard = [[InlineKeyboardButton("Назад", callback_data='back')],
        [InlineKeyboardButton("Изменить имя", callback_data='name'), InlineKeyboardButton("+ Добавить время", callback_data='new')]
    ]
    times = support_functions.get_template_from_json(template[2])
    times.sort(key=lambda x: support_functions.get_count_minutes(x))
    for time in times:
        keyboard.append([InlineKeyboardButton(time, callback_data=time)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if message_id:
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=message_id)
    else:
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=update.message.message_id)


async def menu_113_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    cur.execute(f'''SELECT * FROM templates
    WHERE id = {selected_template[person_date[1]]}''')
    template = cur.fetchall()[0]

    if query.data == 'back':
        del selected_template[person_date[1]]
        await menu_111_take(update, context, con, cur, person_date, query.message.message_id)
        change_tg_menu(person_date[1], 111, con, cur)
    elif query.data == 'name':
        text = f'Введите новое название для шаблона "{template[1]}"'
        keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=query.message.message_id)
        change_tg_menu(person_date[1], 114, con, cur)
    elif query.data == 'new':
        text = f'Введите время которое будет привязано к этому шаблону в формате "чч.мм", например "12.30"'
        keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=query.message.message_id)
        change_tg_menu(person_date[1], 115, con, cur)
    else:
        time_to_del = query.data
        all_times = support_functions.get_template_from_json(template[2])
        all_times.remove(time_to_del)

        inquiry = f"""UPDATE templates 
        SET description = '{support_functions.get_json_from_template(all_times)}' 
        WHERE id = {selected_template[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
        await menu_113_take(query, context, con, cur, person_date)


async def menu_114_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        if person_date[1] not in selected_template:
            return
        new_name = update.message.text
        inquiry = f"""UPDATE templates 
        SET name = '{new_name}' WHERE id = {selected_template[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
    if is_inline:
        query = update.callback_query
        await query.answer()
        await menu_113_take(query, context, con, cur, person_date)
    else:
        if person_date[1] in last_admin_inlines:
            await menu_113_take(update, context, con, cur, person_date, last_admin_inlines[person_date[1]])
        else:
            await menu_113_take(update, context, con, cur, person_date, update.message.message_id - 1)
    change_tg_menu(person_date[1], 113, con, cur)


async def menu_115_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        if person_date[1] not in selected_template:
            return
        new_time = update.message.text.replace('.', ':')
        new_time = new_time.replace(',', ':')
        if len(new_time.split(':')) != 2:
            return

        cur.execute(f'''SELECT * FROM templates
                    WHERE id = {selected_template[person_date[1]]}''')
        template = cur.fetchall()[0]
        ald_times = support_functions.get_template_from_json(template[2])
        ald_times.append(new_time)
        ald_times.sort(key=lambda x: support_functions.get_count_minutes(x))

        inquiry = f"""UPDATE templates 
        SET description = '{support_functions.get_json_from_template(ald_times)}' 
        WHERE id = {selected_template[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
    if is_inline:
        query = update.callback_query
        await query.answer()
        await menu_113_take(query, context, con, cur, person_date)
    else:
        if person_date[1] in last_admin_inlines:
            await menu_113_take(update, context, con, cur, person_date, last_admin_inlines[person_date[1]])
        else:
            await menu_113_take(update, context, con, cur, person_date, update.message.message_id - 1)
    change_tg_menu(person_date[1], 113, con, cur)



# ====================================================================================================== Главное меню

async def menu_101_main_menu(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Главное меню админа"

    keyboard = [
        ['Добавить расписание'],
        ["Шаблоны", "Отмены"],
        ['Пациенты активные', 'Все пациенты'],
        ['База данных']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def admin_button_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if person_date[4] == 102:
        await menu_102_get(update, context, con, cur, person_date)
    elif person_date[4] == 103:
        await menu_103_get(update, context, con, cur, person_date)
    elif person_date[4] == 105:
        await menu_105_get(update, context, con, cur, person_date)
    elif person_date[4] == 111:
        await menu_111_get(update, context, con, cur, person_date)
    elif person_date[4] == 112:
        await menu_112_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 113:
        await menu_113_get(update, context, con, cur, person_date)
    elif person_date[4] == 114:
        await menu_114_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 115:
        await menu_115_get(update, context, con, cur, person_date, True)


async def admin_text_message_handler(update: Update, context: CallbackContext, con, cur, person_date):
    if person_date[4] == 100:
        await menu_101_main_menu(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
    elif person_date[4] == 101:
        if update.message.text == 'Добавить расписание':
            await menu_102_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 102, con, cur)
        elif update.message.text == 'Шаблоны':
            await menu_111_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 111, con, cur)
        elif update.message.text == 'База данных':
            await update.message.reply_text('В разработке')
            await menu_101_main_menu(update, context, con, cur, person_date)
        elif 'пациенты' in update.message.text.lower():
            await update.message.reply_text('Собираем статистику, пока мало данных...')
            await menu_101_main_menu(update, context, con, cur, person_date)
        else:
            await menu_101_main_menu(update, context, con, cur, person_date)
    elif person_date[4] == 104:
        await menu_104_get(update, context, con, cur, person_date)
    elif person_date[4] == 112:
        await menu_112_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 114:
        await menu_114_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 115:
        await menu_115_get(update, context, con, cur, person_date, False)


async def admin_contact_handler(update: Update, context: CallbackContext, con, cur, person_date):
    pass
