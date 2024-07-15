from client_dialogs import *
from admin_dialogs import admin_button_handler, admin_text_message_handler, admin_contact_handler, check_is_admin, menu_100_welcome

con = sqlite3.connect('data/db.db')
cur = con.cursor()
timer_con = time.time()
last_inlines = {}
to_del_message = {}

is_admin_menu = {}
for id in admins:
    is_admin_menu[id] = True



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
        await menu_1_welcome(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 5, con, cur)
    else:
        change_tg_menu(person_date[1], 2, con, cur)
        await menu_2_main_menu(update, context, con, cur, person_date)


# Обработчик нажатия кнопок
async def button_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.callback_query.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_button_handler(update, context, con, cur, person_date)
            return

    query = update.callback_query
    await query.answer()

    if query.data == 'cancel':
        change_tg_menu(person_date[1], 2, con, cur)
        await menu_2_main_menu(update.callback_query, context, con, cur, person_date)
        await query.edit_message_text(text='Действие отменено')

    if query.data == 'user_name':
        text = "Как вас подписать в расписании, чтоб было понятно кто вы?"

        keyboard = [
            [InlineKeyboardButton("Назад", callback_data='back_to_7')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        change_tg_menu(person_date[1], 3, con, cur)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    if query.data == 'phone_number':
        text = "Укажите ваш номер телефона, чтобы мы могли перезвонить для уточнения записи"
        keyboard = [
            [InlineKeyboardButton("Назад", callback_data='back_to_7')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        change_tg_menu(person_date[1], 4, con, cur)
        await query.edit_message_text(text=text, reply_markup=reply_markup)

        keyboard = [[KeyboardButton("Отправить номер телефона", request_contact=True)]]
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        message = await query.message.reply_text('📞', reply_markup=reply_markup)
        to_del_message[person_date[1]] = message.message_id

    if query.data == 'back_to_7' and (person_date[4] == 3 or person_date[4] == 4):
        await delete_message(update, context, person_date, to_del_message)

        change_tg_menu(person_date[1], 2, con, cur)
        await menu_7(update, context, con, cur, person_date, 0)


# Обработчик получения контакта
async def contact_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_contact_handler(update, context, con, cur, person_date)
            return

    if person_date[4] == 6:
        await menu_6_get_phone_number(update, context, con, cur, person_date)
    elif person_date[4] == 4:
        await menu_4_get_phone_number(update, context, con, cur, person_date, last_inlines=last_inlines, to_del_message=to_del_message)


# Обработчик текстовых сообщений
async def text_message_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)
    if check_is_admin(person_date):
        if is_admin_menu[person_date[1]]:
            await admin_text_message_handler(update, context, con, cur, person_date)
            return

    if person_date[4] == 5:
        await menu_5_get_name(update, context, con, cur, person_date)
    elif person_date[4] == 6:
        await menu_6_get_phone_number(update, context, con, cur, person_date)
    elif person_date[4] == 2:
        if update.message.text == 'Обновить контактную информацию':
            await menu_7(update, context, con, cur, person_date, last_inlines=last_inlines)
        elif update.message.text == 'Общее расписание':
            await menu_8_general_timetable(update, context, con, cur, person_date)
        else:
            await menu_2_main_menu(update, context, con, cur, person_date)
    elif person_date[4] == 3:
        await menu_3_get_name(update, context, con, cur, person_date, last_inlines=last_inlines)

def main():
    # Создание подключения к базе данных
    create_con()

    application = Application.builder().token(token).build()

    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

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
