import telegram.error

from tabulate import tabulate
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, filters

import os
import logging
import sqlite3
import datetime
import telegram_calendar
import support_functions


admins_id = os.getenv("ADMINS_ID", "")
admins = list(map(int, admins_id.split(";")))

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

admin_calendar_data = {}
last_admin_inlines = {}
count_deleted_msgs = {}
selected_template = {}
selected_account = {}
selected_admin_data = {}
is_active_account = {}
new_name_for_user = {}
selected_record = {}


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


async def spam_to_user(context: CallbackContext, message, chat_id):
    await context.bot.send_message(text=message, chat_id=chat_id)


def check_is_admin(person_date):
    return person_date[1] in admins


async def change_account_type(is_admin_menu, person_date, value=True):
    if not check_is_admin(person_date):
        return
    is_admin_menu[person_date[1]] = value


async def menu_100_welcome(update: Update, context: CallbackContext, con, cur, person_date):
    # Текст сообщения
    text = """Добро пожаловать! Это закулисье автоматической системы - тут можно управлять почти всем\n
В любой непонятной ситуации введите команду /start
Для переключения управления как клиент и обратно в админа команда /switch"""
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
        logger.warning(f'Введено время "{update.message.text}", которое не удалось обработать')
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
    keyboard.append([InlineKeyboardButton('❌ Закрыть', callback_data='close')])

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
        keyboard.append([InlineKeyboardButton('🗑️' + time, callback_data=time)])

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


# ====================================================================================================== Пациенты


async def menu_121_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None, is_active=False):
    if is_active:
        text = 'Активные пациенты:'
    else:
        text = 'Все пациенты:'
    is_active_account[person_date[1]] = is_active

    keyboard = [[InlineKeyboardButton("❌ Закрыть", callback_data='close')]]
    if is_active:
        active_id = support_functions.get_active_accounts(cur)
        inquiry = []
        for id in active_id:
            inquiry.append(f'id = {id}')
        inquiry = 'SELECT * FROM accounts WHERE is_deleted = 0 AND (' + ' OR '.join(inquiry) + ')'
        cur.execute(inquiry)
    else:
        cur.execute(f'''SELECT * FROM accounts WHERE is_deleted = 0''')
    result = cur.fetchall()
    if is_active:
        result.sort(key=lambda x: x[2])
    else:
        result = result[::-1]

    for account in result:
        name = str(account[2])
        if str(account[3]).isdigit():
            name += f' ({account[3]})'
        if account[7]:
            name = '✔ ' + name
        keyboard.append([InlineKeyboardButton(name, callback_data=f'account_{account[0]}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    if message_id is not None:
        await context.bot.edit_message_text(text=text,
            chat_id=person_date[1],
            reply_markup=reply_markup,
            message_id=message_id)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)


async def menu_121_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    last_admin_inlines[person_date[1]] = query.message.message_id

    if query.data == 'close':
        await context.bot.edit_message_text(text=query.message.text,
            chat_id=person_date[1],
            message_id=query.message.message_id)

        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
    else:
        account_id = int(query.data.split('_')[1])
        selected_account[person_date[1]] = account_id
        await menu_122_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 122, con, cur)


async def menu_122_take(update: Update, context: CallbackContext, con, cur, person_date):
    if person_date[1] not in selected_account:
        return

    cur.execute(f'''SELECT * FROM accounts
        WHERE id = {selected_account[person_date[1]]}''')
    account = cur.fetchall()[0]

    cur.execute(f'''SELECT id FROM records
        WHERE patient_id = {selected_account[person_date[1]]} AND is_cancel = 0''')
    result = cur.fetchall()

    cur.execute(f'''SELECT * FROM complaints
        WHERE user_id = {selected_account[person_date[1]]}''')
    all_complaints = cur.fetchall()
    complaints = []
    for i in range(len(all_complaints)):
        grad_1, grad_2 = all_complaints[i][4], all_complaints[i][5]
        if grad_1 is None:
            grad_1 = '—'
        if grad_2 is None:
            grad_2 = '—'
        complaints.append(f'📌 {all_complaints[i][2]} - {all_complaints[i][3]}\nОценка до: {grad_1}\nПосле: {grad_2}')
    complaints = '\n'.join(complaints)

    text = f'''{account[2]}\n
📞 +{account[3]}
всего записей: {len(result)}
====================
📃 Жалобы:
{complaints}

====================
📃 Описание:
{account[9]}
'''
    verify = ["✔ подтвердить аккаунт", 'verify']
    if account[7]:
        verify = ['✔ Доверенный аккаунт', 'null']

    # TODO сделать кнопку "Завершить курс" чтоб по её нажатии отправлялись все не отправленные опросы

    keyboard = [[],
                [InlineKeyboardButton("✅ Завершить курс", callback_data='close_course')],
                [InlineKeyboardButton("✏ Добавить описание", callback_data='add_description'),
                 InlineKeyboardButton("📃 Заменить описание", callback_data='set_description')],
                [InlineKeyboardButton("📅 Расписание", callback_data='timetable'),
                 InlineKeyboardButton("Изменить имя", callback_data='new_name')],
                [InlineKeyboardButton(verify[0], callback_data=verify[1]),
                 InlineKeyboardButton("🚫 забанить", callback_data='ban')],
                [InlineKeyboardButton("Назад", callback_data='back')]
                ]
    if account[6] == 'None':
        keyboard[0].append(InlineKeyboardButton('Нет ссылки', callback_data='none'))
    else:
        keyboard[0].append(InlineKeyboardButton('Написать', url=account[6]))

    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        reply_markup=reply_markup,
                                        message_id=last_admin_inlines[person_date[1]])


async def menu_122_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=True):
    if person_date[1] not in selected_account:
        return

    cur.execute(f'''SELECT * FROM accounts
    WHERE id = {selected_account[person_date[1]]}''')
    account = cur.fetchall()[0]

    if is_inline:
        query = update.callback_query
        await query.answer()

        if query.data == 'back':
            del selected_account[person_date[1]]
            await menu_121_take(update, context, con, cur, person_date, query.message.message_id, is_active=is_active_account[person_date[1]])
            change_tg_menu(person_date[1], 121, con, cur)
        elif query.data == 'add_description':
            text = f'Дополнение описания с новой строки:'
            keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.edit_message_text(text=text,
                                                chat_id=person_date[1],
                                                reply_markup=reply_markup,
                                                message_id=query.message.message_id)
            change_tg_menu(person_date[1], 123, con, cur)
        elif query.data == 'set_description':
            text = f'Новое описание с ЧИСТОГО листа:'
            keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.edit_message_text(text=text,
                                                chat_id=person_date[1],
                                                reply_markup=reply_markup,
                                                message_id=query.message.message_id)
            change_tg_menu(person_date[1], 124, con, cur)
        elif query.data == 'new_name':
            text = f'Введите новое имя для этого пользователя:'
            keyboard = [[InlineKeyboardButton("Назад", callback_data='back')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await context.bot.edit_message_text(text=text,
                                                chat_id=person_date[1],
                                                reply_markup=reply_markup,
                                                message_id=query.message.message_id)
            change_tg_menu(person_date[1], 125, con, cur)
        elif query.data == 'timetable':
            timetable = list(map(lambda x: f'* {x[1].strftime("%d.%m.%Y")} в {x[0]}', support_functions.get_timetable_by_user(cur, account[0])))
            text = 'Расписание ближайших процедур:\n' + '\n'.join(timetable)
            await query.message.reply_text(text)
        elif query.data == 'ban':
            text = f'!Для БЕЗВОЗРАТНОГО удаления и БЛОКИРОВКИ аккаунта "{account[2]} (tg_id = {account[1]})" \nОтправьте сообщение "УдАлИтЬ {account[0]}"'
            await query.message.reply_text(text)
        elif query.data == 'verify':
            inquiry = f"""UPDATE accounts 
            SET is_verification = 1 WHERE id = {selected_account[person_date[1]]}"""
            cur.execute(inquiry)
            con.commit()
            await menu_122_take(update, context, con, cur, person_date)
    else:
        if update.message.text == f'УдАлИтЬ {account[0]}':
            inquiry = f"""UPDATE accounts 
            SET is_deleted = 1 WHERE id = {selected_account[person_date[1]]}"""
            cur.execute(inquiry)
            con.commit()


async def menu_123_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        if person_date[1] not in selected_account:
            return
        cur.execute(f'''SELECT * FROM accounts
            WHERE id = {selected_account[person_date[1]]}''')
        account = cur.fetchall()[0]

        new_description = account[9] + '\n' + update.message.text
        inquiry = f"""UPDATE accounts 
        SET description = '{new_description}' WHERE id = {selected_account[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
    if is_inline:
        query = update.callback_query
        await query.answer()
        await menu_122_take(query, context, con, cur, person_date)
    else:
        await menu_122_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 122, con, cur)


async def menu_124_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        if person_date[1] not in selected_account:
            return

        new_description = update.message.text
        inquiry = f"""UPDATE accounts 
        SET description = '{new_description}' WHERE id = {selected_account[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
    if is_inline:
        query = update.callback_query
        await query.answer()
        await menu_122_take(query, context, con, cur, person_date)
    else:
        await menu_122_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 122, con, cur)


async def menu_125_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if not is_inline:
        if person_date[1] not in selected_account:
            return

        new_name = update.message.text
        inquiry = f"""UPDATE accounts 
        SET name = '{new_name}' WHERE id = {selected_account[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
    if is_inline:
        query = update.callback_query
        await query.answer()
        await menu_122_take(query, context, con, cur, person_date)
    else:
        await menu_122_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 122, con, cur)


# ============================================================================================== Системная информация


async def menu_131_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    cur.execute(f'''SELECT DISTINCT * FROM admin_data''')
    result = cur.fetchall()

    text = []
    keyboard = []
    for i in range(len(result)):
        text.append(f'{i + 1}) {result[i][1]} = "{result[i][2]}"')
        keyboard.append([InlineKeyboardButton(f"{i + 1}) {result[i][1]}", callback_data=result[i][1])])
    text = 'Изменяемые системные поля:\n' + '\n'.join(text)
    keyboard.append([InlineKeyboardButton("❌ Назад", callback_data='back')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=message_id,
                                            reply_markup=reply_markup)
        last_admin_inlines[person_date[1]] = message_id
    else:
        massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
        last_admin_inlines[person_date[1]] = massage.message_id


async def menu_131_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        await context.bot.edit_message_text(text=query.message.text,
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    await menu_132_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 132, con, cur)


async def menu_132_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    name = query.data
    cur.execute(f'''SELECT DISTINCT * FROM admin_data
        WHERE name = "{name}"''')
    logger.debug(f'''SELECT DISTINCT * FROM admin_data
        WHERE name = "{name}"''')
    result = cur.fetchall()[0]

    selected_admin_data[person_date[1]] = result[0]

    text = f'Введите новое значение для параметра "{name}"\nТекущее значение = "{result[2]}"'
    keyboard = [[InlineKeyboardButton("❌ Назад", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        reply_markup=reply_markup,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id)


async def menu_132_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        await menu_131_take(update, context, con, cur, person_date, last_admin_inlines[person_date[1]])
        change_tg_menu(person_date[1], 131, con, cur)
        return
    answer = update.message.text

    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        change_tg_menu(person_date[1], 101, con, cur)
        await menu_101_main_menu(update, context, con, cur, person_date)
        return

    inquiry = f"""UPDATE admin_data 
                SET data = '{update.message.text}' WHERE id = {selected_admin_data[person_date[1]]}"""
    try:
        cur.execute(inquiry)
        con.commit()
    except Exception as e:
        logger.error(f'Ошибка при изменении системной информации, старое значение {selected_admin_data[person_date[1]]}, новое {update.message.text}, запрос "{inquiry}".\n\nОшибка "{e}"')
        await update.message.reply_text(f'Произошла ошибка запроса изменения данных: {e}')

    logger.info(f'Изменение системной информации, старое значение {selected_admin_data[person_date[1]]}, новое {update.message.text}')
    await support_functions.delete_message(update, context, update.message.message_id)
    await menu_131_take(update, context, con, cur, person_date, last_admin_inlines[person_date[1]])
    change_tg_menu(person_date[1], 131, con, cur)


# ===================================================================================================== Новый пациент


async def menu_141_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = 'Введите как будут звать нового пациента'
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='close')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if message_id:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=message_id,
                                            reply_markup=reply_markup)
        last_admin_inlines[person_date[1]] = message_id
    else:
        massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
        last_admin_inlines[person_date[1]] = massage.message_id


async def menu_141_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        query = update.callback_query
        await query.answer()

        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]])
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    answer = update.message.text
    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        id = last_admin_inlines[person_date[1]]
        await support_functions.delete_messages(update, context, [id, id + 1])
        change_tg_menu(person_date[1], 101, con, cur)
        await menu_101_main_menu(update, context, con, cur, person_date)
        return

    new_name_for_user[person_date[1]] = [update.message.text]

    await menu_142_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 142, con, cur)


async def menu_142_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = 'Теперь укажите номер телефона в удобном формате без "+" в начале'
    keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data='close')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]],
                                        reply_markup=reply_markup)


async def menu_142_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        query = update.callback_query
        await query.answer()

        id = last_admin_inlines[person_date[1]]
        await support_functions.delete_messages(update, context, [id, id + 1])
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    answer = update.message.text
    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        id = last_admin_inlines[person_date[1]]
        await support_functions.delete_messages(update, context, [id, id + 1, id + 2])
        change_tg_menu(person_date[1], 101, con, cur)
        await menu_101_main_menu(update, context, con, cur, person_date)
        return

    new_name_for_user[person_date[1]].append(update.message.text)

    await menu_143_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 143, con, cur)


async def menu_143_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = f'''Подтвердите введённые данные перед добавлением нового пациента:
👤 {new_name_for_user[person_date[1]][0]}
📞 +{new_name_for_user[person_date[1]][1]}
'''
    keyboard = [[InlineKeyboardButton("✅ Верно", callback_data='true'),
                 InlineKeyboardButton("❌ Отмена", callback_data='close')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]],
                                        reply_markup=reply_markup)


async def menu_143_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'true':
        cur.execute(f'SELECT id FROM accounts ORDER BY id DESC LIMIT 1')
        result = cur.fetchall()[0]
        user_id = result[0] + 1

        inquiry = f"""INSERT INTO accounts (id, tg_id, name, phone_number, tg_menu, number_requests, tg_link)
        VALUES ({user_id}, {-1 * user_id}, '{new_name_for_user[person_date[1]][0]}', '{new_name_for_user[person_date[1]][1]}', 1, 0, 'None')"""
        cur.execute(inquiry)
        con.commit()
        logger.info(f'добавлен новый пользователь, id = {user_id}, name = {new_name_for_user[person_date[1]][0]}')
        text = f'''Добавлен новый пациент:
👤 {new_name_for_user[person_date[1]][0]}
📞 +{new_name_for_user[person_date[1]][1]}
'''
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            message_id=last_admin_inlines[person_date[1]])

        id = last_admin_inlines[person_date[1]]
        await support_functions.delete_messages(update, context, [id + 1, id + 2])
        change_tg_menu(person_date[1], 101, con, cur)
        await menu_101_main_menu(query, context, con, cur, person_date)

    elif query.data == 'close':
        id = last_admin_inlines[person_date[1]]
        await support_functions.delete_messages(update, context, [id, id + 1, id + 2])
        change_tg_menu(person_date[1], 101, con, cur)
        await menu_101_main_menu(query, context, con, cur, person_date)
        return


# ====================================================================================================== Меню Отмены


async def menu_151_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    now = datetime.datetime.now()
    first_day, ignored_days, last_day = support_functions.get_first_ignored_and_last_days_for_canceled(cur)

    admin_calendar_data[person_date[1]] = [first_day, ignored_days, last_day, now]

    message = await update.message.reply_text(text='Выберите день отмены',
                                    reply_markup=telegram_calendar.create_calendar(first_day=first_day,
                                                                                   ignored_days=ignored_days,
                                                                                   last_day=last_day))
    last_admin_inlines[person_date[1]] = message.message_id


async def menu_151_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    (kind, _, _, _, _) = telegram_calendar.separate_callback_data(query.data)
    if kind == 'CALENDAR':
        if person_date[1] in admin_calendar_data:
            selected, date = await telegram_calendar.process_calendar_selection(update, context,
                                                                                *admin_calendar_data[person_date[1]][:3])
        else:
            await support_functions.delete_message(update, context, query.message.message_id)
            await menu_101_main_menu(query, context, con, cur, person_date)
            change_tg_menu(person_date[1], 101, con, cur)
            return
        if selected:
            if date is None:
                await menu_101_main_menu(query, context, con, cur, person_date)
                change_tg_menu(person_date[1], 101, con, cur)
                return
            await menu_152_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 152, con, cur)
    else:
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)


async def menu_152_take(update: Update, context: CallbackContext, con, cur, person_date, date=None):
    query = update.callback_query
    if date is None:
        (_, action, year, month, day) = telegram_calendar.separate_callback_data(query.data)
        date = datetime.datetime(int(year), int(month), int(day))
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

    else:
        keyboard = []
    keyboard.append([InlineKeyboardButton("🚫 удалить день", callback_data='block_day')])
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_152_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'block_day':
        await menu_154_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 154, con, cur)
        return
    if query.data == 'back':
        first_day, ignored_days, last_day = support_functions.get_first_ignored_and_last_days(cur)
        admin_calendar_data[person_date[1]][:3] = first_day, ignored_days, last_day
        await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3],
                                                text='Выберите день отмены')
        change_tg_menu(person_date[1], 151, con, cur)
        return
    if 'record_' in query.data:
        record_id = query.data.split('_')[1]
        selected_record[person_date[1]] = record_id
        await menu_153_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 153, con, cur)


async def menu_153_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query

    cur.execute(f'''SELECT * FROM records
    WHERE records.id = {selected_record[person_date[1]]}''')
    result = cur.fetchall()[0]

    keyboard = [[InlineKeyboardButton("🚫 отменить процедуру", callback_data='del')],
                [InlineKeyboardButton("Назад", callback_data='back')]]
    if result[2]:
        keyboard[0].append(InlineKeyboardButton("Отменить пациента", callback_data='close'))

        cur.execute(f'''SELECT records.id, records.time, days.date, accounts.name, accounts.phone_number FROM records, accounts, days
        WHERE records.patient_id = accounts.id AND records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
        record = cur.fetchall()[0]
        text = f'''Процедура №{record[0]} 📅 {record[2]} ⏰ {record[1]}
Записан:
👤 {record[3]} (+{record[4]})'''
    else:
        cur.execute(f'''SELECT records.id, records.time, days.date FROM records, days
        WHERE records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
        record = cur.fetchall()[0]
        text = f'''Процедура №{record[0]} 📅 {record[2]} ⏰ {record[1]}
Никто не записан'''
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_153_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        await menu_152_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])
        change_tg_menu(person_date[1], 152, con, cur)
        return
    elif query.data == 'del':
        await menu_155_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 155, con, cur)
        return
    elif query.data == 'close':
        await menu_156_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 156, con, cur)
        return


async def menu_154_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    text = f'Вы точно хотите удалить весь день {admin_calendar_data[person_date[1]][3].strftime("%d.%m.%Y")} целиком?'
    keyboard = [[InlineKeyboardButton("Да", callback_data='yes'),
                 InlineKeyboardButton("нет", callback_data='no')
                 ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_154_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'yes':
        cur.execute(f'''SELECT DISTINCT * FROM days
                        WHERE date = "{admin_calendar_data[person_date[1]][3].strftime('%d.%m.%Y')}"''')
        result = cur.fetchall()
        if result:
            users = []
            cur.execute(f'''SELECT DISTINCT * FROM records
                    WHERE day_id = {result[0][0]}''')
            result = cur.fetchall()
            inquiry = []
            for i in range(len(result)):
                inquiry.append(f'id = {result[i][0]}')
                if result[i][2]:
                    users.append(result[i][2])
            inquiry = ' OR '.join(inquiry)
            inquiry = f"""UPDATE records
            SET is_cancel = 1
            WHERE {inquiry}"""
            cur.execute(inquiry)
            con.commit()
            if len(users) > 0:
                users = ' OR '.join(list(map(lambda x: f'id = {x}', users)))
                cur.execute(f'''SELECT DISTINCT * FROM accounts
                WHERE {users}''')
                result = cur.fetchall()
                text = f'К сожалению, все ваши записи 📅 {admin_calendar_data[person_date[1]][3].strftime("%d.%m.%Y")} были отменены\nРасписание обновлено'
                for i in range(len(result)):
                    if result[i][1] > 0:
                        await spam_to_user(context, text, result[i][1])

    await menu_152_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])
    change_tg_menu(person_date[1], 152, con, cur)


async def menu_155_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    cur.execute(f'''SELECT records.id, records.time, days.date FROM records, days
            WHERE records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
    record = cur.fetchall()[0]
    text = f'Вы точно хотите удалить процедуру №{record[0]} 📅 {record[2]} ⏰ {record[1]} ?'
    keyboard = [[InlineKeyboardButton("Да", callback_data='yes'),
                 InlineKeyboardButton("нет", callback_data='no')
                 ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_155_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'yes':
        cur.execute(f'''SELECT records.id, records.time, days.date, records.patient_id FROM records, days
                WHERE records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
        record = cur.fetchall()[0]

        inquiry = f"""UPDATE records
                    SET is_cancel = 1
                    WHERE id = {selected_record[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
        if record[3]:
            cur.execute(f'''SELECT DISTINCT * FROM accounts
                        WHERE id = {record[3]}''')
            result = cur.fetchall()[0]
            if result[1] > 0:
                text = f'К сожалению, процедура 📅 {record[2]} ⏰ {record[1]} была отменена\nРасписание обновлено'
                await spam_to_user(context, text, result[1])

    await menu_152_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])
    change_tg_menu(person_date[1], 152, con, cur)


async def menu_156_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    cur.execute(f'''SELECT records.id, records.time, days.date, accounts.name, accounts.phone_number FROM records, accounts, days
            WHERE records.patient_id = accounts.id AND records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
    record = cur.fetchall()[0]
    text = f'Вы точно хотите убрать пациента 👤 {record[3]} (+{record[4]}) от записи №{record[0]} 📅 {record[2]} ⏰ {record[1]} ?'
    keyboard = [[InlineKeyboardButton("Да", callback_data='yes'),
                 InlineKeyboardButton("нет", callback_data='no')
                 ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_156_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'yes':
        cur.execute(f'''SELECT records.id, records.time, days.date, records.patient_id FROM records, days
        WHERE records.day_id = days.id AND records.id = {selected_record[person_date[1]]}''')
        record = cur.fetchall()[0]
        inquiry = f"""UPDATE records
                    SET patient_id = NULL, is_verification = 0, is_reminder = 0, is_ended = 0
                    WHERE id = {selected_record[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()
        if record[3]:
            cur.execute(f'''SELECT DISTINCT * FROM accounts
                WHERE id = {record[3]}''')
            result = cur.fetchall()[0]
            if result[1] > 0:
                text = f'К сожалению, вам отменили процедуру 📅 {record[2]} ⏰ {record[1]}\nРасписание обновлено'
                await spam_to_user(context, text, result[1])

    await menu_152_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])
    change_tg_menu(person_date[1], 152, con, cur)


# ============================================================================================== Расписание на неделю


async def menu_171_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = 'Расписание на неделю\n'
    now = datetime.datetime.now()
    for i in range(7):
        text += f'==== {now.strftime("%d.%m.%Y")} ({telegram_calendar.week_days[now.weekday()]}) ====\n'
        cur.execute(f'''SELECT DISTINCT * FROM days
        WHERE date = "{now.strftime("%d.%m.%Y")}"''')
        date = cur.fetchall()
        if date:
            cur.execute(f'''SELECT DISTINCT * FROM records
            WHERE day_id = {date[0][0]} AND is_cancel = 0''')
            records = cur.fetchall()
            if records:
                records.sort(key=lambda x: support_functions.get_count_minutes(x[3]))
                for record in records:
                    if record[2]:
                        cur.execute(f'''SELECT DISTINCT name, phone_number FROM accounts
                        WHERE id = {record[2]}''')
                        user = cur.fetchall()[0]
                        if record[4]:
                            text += f'✓ {record[3]} - {user[0]} (+{user[1]})\n'
                        else:
                            text += f'◉ {record[3]} - {user[0]} (+{user[1]})\n'
                    else:
                        text += f'⭘ {record[3]}\n'
            else:
                text += '⭘ Выходной\n'
        else:
            text += '⭘ Выходной\n'
        text += '\n'
        now += datetime.timedelta(days=1)
    await update.message.reply_text(text)
    await menu_101_main_menu(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 101, con, cur)


# ================================================================================================== Запись пациентов


async def menu_161_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = 'Выберете кого записать'
    active_id = set(support_functions.get_active_accounts(cur))
    simple_id = set(support_functions.get_simple_account(cur))
    cur.execute('SELECT id FROM accounts WHERE tg_id > 0 AND is_deleted = 0')
    other_id = set(map(lambda x: x[0], cur.fetchall()))
    other_id = other_id - simple_id - active_id
    users = []
    for ids in [active_id, simple_id, other_id]:
        if len(ids) == 0:
            continue
        inquiry = ' OR '.join(list(map(lambda x: f'id = {x}', ids)))
        logger.debug(f'SELECT name, phone_number, id FROM accounts WHERE {inquiry}')
        cur.execute(f'SELECT name, phone_number, id FROM accounts WHERE {inquiry}')
        result = cur.fetchall()
        result.sort(key=lambda x: x[0])
        users.extend(result)
    keyboard = [[InlineKeyboardButton("❌ Назад", callback_data='back')]]

    for user in users:
        keyboard.append([InlineKeyboardButton(f'{user[0]} (+{user[1]})', callback_data=f'user_{user[2]}')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)


async def menu_161_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        await context.bot.edit_message_text(text='Действие отменено',
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
    elif 'user_' in query.data:
        user_id = query.data.split('_')[1]
        selected_account[person_date[1]] = user_id
        await menu_162_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 162, con, cur)


async def menu_162_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    cur.execute(f'SELECT name, phone_number FROM accounts WHERE id = {selected_account[person_date[1]]}')
    result = cur.fetchall()[0]
    text = f'Выбран {result[0]} (+{result[1]})\nДата для записи:'
    now = datetime.datetime.now()
    first_day, ignored_days, last_day = support_functions.get_clients_first_ignored_and_last_days(cur, int(selected_account[person_date[1]]))

    admin_calendar_data[person_date[1]] = [first_day, ignored_days, last_day, now]
    await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3],
                                            text=text)


async def menu_162_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()
    (kind, _, _, _, _) = telegram_calendar.separate_callback_data(query.data)
    if kind == 'CALENDAR':
        if person_date[1] in admin_calendar_data:
            selected, date = await telegram_calendar.process_calendar_selection(update, context, *admin_calendar_data[person_date[1]][:3])
        else:
            await support_functions.delete_message(update, context, query.message.message_id)
            await menu_101_main_menu(query, context, con, cur, person_date)
            change_tg_menu(person_date[1], 101, con, cur)
            return
        if selected:
            if date is None:
                await menu_101_main_menu(query, context, con, cur, person_date)
                change_tg_menu(person_date[1], 101, con, cur)
                return
            await menu_163_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 163, con, cur)
    else:
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)


async def menu_163_take(update: Update, context: CallbackContext, con, cur, person_date, date=None):
    query = update.callback_query
    if date is None:
        (_, action, year, month, day) = telegram_calendar.separate_callback_data(query.data)
        date = datetime.datetime(int(year), int(month), int(day))
    admin_calendar_data[person_date[1]][3] = date
    cur.execute(f'SELECT name, phone_number FROM accounts WHERE id = {selected_account[person_date[1]]}')
    result = cur.fetchall()[0]
    text = f"Выбран {result[0]} (+{result[1]})\nРасписание на {date.strftime('%d.%m.%Y')} ({telegram_calendar.week_days[date.weekday()]})"

    cur.execute(f'''SELECT DISTINCT * FROM days
                    WHERE date = "{date.strftime('%d.%m.%Y')}"''')
    result = cur.fetchall()
    if result:
        cur.execute(f'''SELECT DISTINCT * FROM records
                WHERE day_id = {result[0][0]} AND (patient_id IS NULL OR patient_id = {selected_account[person_date[1]]}) AND is_cancel = 0''')
        result = cur.fetchall()
        keyboard = []
        result.sort(key=lambda x: support_functions.get_count_minutes(x[3]))
        for record in result:
            if record[2] is None:
                keyboard.append([InlineKeyboardButton(f"⭘ {record[3]}", callback_data=f'record_{record[0]}')])
            elif record[4]:
                keyboard.append([InlineKeyboardButton(f"✓ {record[3]}", callback_data=f'-')])
            else:
                keyboard.append([InlineKeyboardButton(f"◉ {record[3]}", callback_data=f'-')])

    else:
        keyboard = []
    keyboard.append([InlineKeyboardButton("Назад", callback_data='back')])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_163_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'back':
        first_day, ignored_days, last_day = support_functions.get_clients_first_ignored_and_last_days(cur, int(selected_account[person_date[1]]))
        admin_calendar_data[person_date[1]][:3] = first_day, ignored_days, last_day
        cur.execute(f'SELECT name, phone_number FROM accounts WHERE id = {selected_account[person_date[1]]}')
        result = cur.fetchall()[0]
        text = f'Выбран {result[0]} (+{result[1]})\nДата для записи:'
        await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3],
                                                text=text)
        change_tg_menu(person_date[1], 162, con, cur)
        return
    if 'record_' in query.data:
        record_id = query.data.split('_')[1]
        selected_record[person_date[1]] = record_id
        await menu_164_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 164, con, cur)


async def menu_164_take(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query

    cur.execute(f'''SELECT days.date, records.time FROM records, days
        WHERE records.id = {selected_record[person_date[1]]} AND records.day_id = days.id''')
    time = cur.fetchall()[0]
    cur.execute(f'SELECT name, phone_number FROM accounts WHERE id = {selected_account[person_date[1]]}')
    user = cur.fetchall()[0]
    text = f'Записать?\n👤 {user[0]} (+{user[1]})\n📅 {time[0]} ⏰ {time[1]}'

    keyboard = [[InlineKeyboardButton("✅ Да", callback_data='yes'),
                InlineKeyboardButton("❌ Нет", callback_data='no')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_164_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'yes':
        inquiry = f"""UPDATE records
            SET patient_id = {selected_account[person_date[1]]}
                WHERE id = {selected_record[person_date[1]]}"""
        cur.execute(inquiry)
        con.commit()

        cur.execute(f'''SELECT days.date, records.time FROM records, days
            WHERE records.id = {selected_record[person_date[1]]} AND records.day_id = days.id''')
        time = cur.fetchall()[0]
        cur.execute(f'SELECT name, phone_number, tg_id FROM accounts WHERE id = {selected_account[person_date[1]]}')
        user = cur.fetchall()[0]
        text = f'Пользователь 👤 {user[0]} (+{user[1]})\n Записан 📅 {time[0]} ⏰ {time[1]}'
        await query.message.reply_text(text)

        if user[2] > 0:
            cur.execute(f'''SELECT DISTINCT * FROM admin_data''')
            result = cur.fetchall()
            address = list(filter(lambda x: x[1] == 'address', result))[0][2]
            name_specialist = list(filter(lambda x: x[1] == 'master_name', result))[0][2]
            week = telegram_calendar.week_days[admin_calendar_data[person_date[1]][3].weekday()]

            text = f'Вас записали: {name_specialist}\n📅 {time[0]} ({week})\n⏰ {time[1]}\n🗺️ {address}.\n🔔 За сутки вам придёт напоминание.'
            await spam_to_user(context, text, user[2])
        await menu_165_take(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 165, con, cur)

    elif query.data == 'no':
        await menu_163_take(update, context, con, cur, person_date, admin_calendar_data[person_date[1]][3])
        change_tg_menu(person_date[1], 163, con, cur)


async def menu_165_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    query = update.callback_query
    text = f'Готово'
    keyboard = [
        [InlineKeyboardButton(f"Записаться ещё", callback_data=f'continue'),
         InlineKeyboardButton(f"Готово", callback_data=f'done')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=query.message.message_id,
                                        reply_markup=reply_markup)


async def menu_165_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'done':
        await context.bot.edit_message_text(text='Готово',
                                            chat_id=person_date[1],
                                            message_id=query.message.message_id)
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
    elif query.data == 'continue':
        first_day, ignored_days, last_day = support_functions.get_clients_first_ignored_and_last_days(cur, int(selected_account[person_date[1]]))
        admin_calendar_data[person_date[1]][:3] = first_day, ignored_days, last_day
        cur.execute(f'SELECT name, phone_number FROM accounts WHERE id = {selected_account[person_date[1]]}')
        result = cur.fetchall()[0]
        text = f'Выбран {result[0]} (+{result[1]})\nДата для записи:'
        await telegram_calendar.redraw_calendar(update, context, None, None, *admin_calendar_data[person_date[1]][:3], text=text)
        change_tg_menu(person_date[1], 162, con, cur)


# ====================================================================================================== Рассылка


async def menu_181_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = 'Введите сообщение для рассылке ВСЕМ активным клиентам:'
    keyboard = [[InlineKeyboardButton("❌ Назад", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
    last_admin_inlines[person_date[1]] = massage.message_id


async def menu_181_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        query = update.callback_query
        await query.answer()

        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]])
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    answer = update.message.text
    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]])
        await menu_101_main_menu(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    active_id = support_functions.get_active_accounts(cur)
    inquiry = []
    for id in active_id:
        inquiry.append(f'id = {id}')
    inquiry = 'SELECT * FROM accounts WHERE is_deleted = 0 AND (' + ' OR '.join(inquiry) + ')'
    cur.execute(inquiry)
    result = cur.fetchall()
    for account in result:
        await spam_to_user(context, answer, account[1])

    text = f'Сообщение "{answer}"\nУспешно доставлено до {len(result)} пользователей'
    await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]] + 1)

    await context.bot.edit_message_text(text=text,
                                        chat_id=person_date[1],
                                        message_id=last_admin_inlines[person_date[1]])
    await menu_101_main_menu(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 101, con, cur)


# ====================================================================================================== Меню Статистики

async def menu_191_take(update: Update, context: CallbackContext, con, cur, person_date, message_id=None):
    text = f"Чтобы сгенерировать команду для запуска можно воспользоваться deepseek https://chat.deepseek.com/\n\nНо перед этим сгенерируйте промт и вставьте вместо <...> свой запрос"

    keyboard = [
        [InlineKeyboardButton("получить промт", callback_data='get_promt'), InlineKeyboardButton("выполнить команду", callback_data='run_command')],
        [InlineKeyboardButton("Назад", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if message_id is not None:
        await context.bot.edit_message_text(text=text,
                                            chat_id=person_date[1],
                                            reply_markup=InlineKeyboardMarkup([]),
                                            message_id=message_id)
    else:
        massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
        last_admin_inlines[person_date[1]] = massage.message_id


async def menu_191_get(update: Update, context: CallbackContext, con, cur, person_date):
    query = update.callback_query
    await query.answer()

    if query.data == 'get_promt':
        structure_description = support_functions.get_database_structure(cur)
        text = f'Напиши SLQ Lite запрос для <...>\n{structure_description}'

        await query.message.reply_text(text)
        return
    elif query.data == 'run_command':
        await menu_191_take(query, context, con, cur, person_date, message_id=last_admin_inlines[person_date[1]])
        await menu_192_take(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 192, con, cur)
        return
    elif query.data == 'back':
        await menu_191_take(query, context, con, cur, person_date, message_id=last_admin_inlines[person_date[1]])
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return


async def menu_192_take(update: Update, context: CallbackContext, con, cur, person_date):
    text = f"Введите sql запрос для выполнения его:"

    keyboard = [
        [InlineKeyboardButton("Отмена", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    massage = await update.message.reply_text(text=text, reply_markup=reply_markup)
    last_admin_inlines[person_date[1]] = massage.message_id


async def menu_192_get(update: Update, context: CallbackContext, con, cur, person_date, is_inline=False):
    if is_inline:
        query = update.callback_query
        await query.answer()

        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]])
        await menu_101_main_menu(query, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    answer = update.message.text

    if answer.lower() == 'отмена' or answer.lower() == 'назад' or answer.lower() == 'стоп':
        await menu_101_main_menu(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 101, con, cur)
        return

    temp_cur = support_functions.get_cur('ro')
    result = 'error'
    try:
        temp_cur.execute(answer)
        result = temp_cur.fetchall()  # Получаем все строки результата
        headers = [description[0] for description in cur.description]  # Заголовки столбцов

        # Преобразуем Unicode-последовательности в читаемый текст
        e = '\n'
        result = [
            [f'{cell.replace(e, "")}' if isinstance(cell, str) else cell for cell in row]
            for row in result
        ]
        headers = [f'{header}' if isinstance(header, str) else header for header in headers]

        # Форматируем таблицу с ограничением ширины столбцов
        formatted_table = tabulate(
            result,
            headers=headers,
            tablefmt="mixed_outline" # Ограничение ширины столбцов
        )

    except sqlite3.Error as e:
        formatted_table = f" Ошибка выполнения SQL-запроса: {e}"
        logger.error(f"Ошибка выполнения кастомного SQL-запроса: {e}\nSQL: {answer}")

    logger.info(f'SQL: {answer}\n=============\nResult: {result}')
    if person_date[1] in last_admin_inlines:
        await support_functions.delete_message(update, context, last_admin_inlines[person_date[1]])
    try:
        await update.message.reply_text(text=formatted_table[1:])   # первый символ - всегда пробел
    except telegram.error.BadRequest as e:
        try:
            await update.message.reply_text(text=f'Ответ слишком большой, пришлось сократить его:\n\n{result}')
        except telegram.error.BadRequest as e:
            await update.message.reply_text(text=e.message)
    await menu_191_take(update, context, con, cur, person_date)
    change_tg_menu(person_date[1], 191, con, cur)


# ====================================================================================================== Главное меню


async def menu_101_main_menu(update: Update, context: CallbackContext, con, cur, person_date):
    text = "Главное меню админа"

    keyboard = [
        ['Добавить расписание'],
        ['📅 расписание', '📊 Статистика'],
        ["Шаблоны", "Отмены", 'Запись'],
        ['Пациенты активные', 'Все пациенты', 'Новый пациент'],
        ['Системная информация', 'Рассылка']
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
    elif person_date[4] == 121:
        await menu_121_get(update, context, con, cur, person_date)
    elif person_date[4] == 122:
        await menu_122_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 123:
        await menu_123_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 124:
        await menu_124_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 125:
        await menu_125_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 131:
        await menu_131_get(update, context, con, cur, person_date)
    elif person_date[4] == 132:
        await menu_132_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 141:
        await menu_141_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 142:
        await menu_142_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 143:
        await menu_143_get(update, context, con, cur, person_date)
    elif person_date[4] == 151:
        await menu_151_get(update, context, con, cur, person_date)
    elif person_date[4] == 152:
        await menu_152_get(update, context, con, cur, person_date)
    elif person_date[4] == 153:
        await menu_153_get(update, context, con, cur, person_date)
    elif person_date[4] == 154:
        await menu_154_get(update, context, con, cur, person_date)
    elif person_date[4] == 155:
        await menu_155_get(update, context, con, cur, person_date)
    elif person_date[4] == 156:
        await menu_156_get(update, context, con, cur, person_date)
    elif person_date[4] == 161:
        await menu_161_get(update, context, con, cur, person_date)
    elif person_date[4] == 162:
        await menu_162_get(update, context, con, cur, person_date)
    elif person_date[4] == 163:
        await menu_163_get(update, context, con, cur, person_date)
    elif person_date[4] == 164:
        await menu_164_get(update, context, con, cur, person_date)
    elif person_date[4] == 165:
        await menu_165_get(update, context, con, cur, person_date)
    elif person_date[4] == 181:
        await menu_181_get(update, context, con, cur, person_date, True)
    elif person_date[4] == 191:
        await menu_191_get(update, context, con, cur, person_date)
    elif person_date[4] == 192:
        await menu_192_get(update, context, con, cur, person_date, True)



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
        elif update.message.text == 'Системная информация':
            await menu_131_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 131, con, cur)
        elif update.message.text == 'Все пациенты':
            await menu_121_take(update, context, con, cur, person_date, is_active=False)
            change_tg_menu(person_date[1], 121, con, cur)
        elif update.message.text == 'Пациенты активные':
            await menu_121_take(update, context, con, cur, person_date, is_active=True)
            change_tg_menu(person_date[1], 121, con, cur)
        elif update.message.text == 'Новый пациент':
            await menu_141_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 141, con, cur)
        elif update.message.text == 'Отмены':
            await menu_151_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 151, con, cur)
        elif update.message.text == 'Запись':
            await menu_161_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 161, con, cur)
        elif update.message.text == '📅 расписание':
            await menu_171_take(update, context, con, cur, person_date)
        elif update.message.text == 'Рассылка':
            await menu_181_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 181, con, cur)
        elif update.message.text == '📊 Статистика':
            await menu_191_take(update, context, con, cur, person_date)
            change_tg_menu(person_date[1], 191, con, cur)
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
    elif person_date[4] == 122:
        await menu_122_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 123:
        await menu_123_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 124:
        await menu_124_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 125:
        await menu_125_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 132:
        await menu_132_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 141:
        await menu_141_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 142:
        await menu_142_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 181:
        await menu_181_get(update, context, con, cur, person_date, False)
    elif person_date[4] == 192:
        await menu_192_get(update, context, con, cur, person_date, False)


async def admin_contact_handler(update: Update, context: CallbackContext, con, cur, person_date):
    pass
