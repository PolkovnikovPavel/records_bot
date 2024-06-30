from client_dialogs import *

con = sqlite3.connect('data/db.db')
cur = con.cursor()
timer_con = time.time()


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
        inquiry = f"""INSERT INTO accounts (tg_id, name, phone_number, tg_menu, number_requests)
VALUES ({message.chat_id}, '{message.from_user.full_name}', '{message.from_user.link}', 1, 0)"""
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

    if person_date[4] == 1:
        await menu_1_welcome(update, context, con, cur, person_date)
        change_tg_menu(person_date[1], 5, con, cur)
    else:
        change_tg_menu(person_date[1], 2, con, cur)


# Обработчик нажатия кнопок
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'button1':
        # Текст сообщения
        text = "Вы нажали Кнопку 1! Пожалуйста, выберите следующую опцию:"

        # Определяем кнопки для нового сообщения
        keyboard = [
            [InlineKeyboardButton("Подкнопка 1.1 (неактивная)", callback_data='subbutton1.1_disabled')],
            [InlineKeyboardButton("Подкнопка 1.2", callback_data='subbutton1.2')],
            [InlineKeyboardButton("Назад", callback_data='back')]
        ]

        # Создаем клавиатуру
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Обновляем сообщение с новой клавиатурой
        await query.edit_message_text(text=text, reply_markup=reply_markup)

    elif query.data == 'subbutton1.1_disabled':
        # Игнорируем нажатие на неактивную кнопку
        await query.answer("Эта кнопка неактивна", show_alert=True)

    elif query.data == 'subbutton1.1':
        await query.edit_message_text(text="Вы выбрали Подкнопку 1.1")
    elif query.data == 'subbutton1.2':
        await query.edit_message_text(text="Вы выбрали Подкнопку 1.2")
    elif query.data == 'back':
        await start(update, context)


# Обработчик получения контакта
async def contact_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)

    if person_date[4] == 6:
        await menu_6_get_phone_number(update, context, con, cur, person_date)
    else:
        # TODO удалить этот блок
        contact = update.message.contact
        user = update.message.from_user

        # Получение информации о пользователе
        user_name = user.full_name
        phone_number = contact.phone_number

        # Отправка информации пользователю
        await update.message.reply_text(f"Спасибо, {user_name}! Ваш номер телефона: {phone_number}")


# Обработчик текстовых сообщений
async def text_message_handler(update: Update, context: CallbackContext) -> None:
    check_timer_con()
    person_date = get_data_of_person(update.message)

    if person_date[4] == 5:
        await menu_5_get_name(update, context, con, cur, person_date)
    elif person_date[4] == 6:
        await menu_6_get_phone_number(update, context, con, cur, person_date)
    else:
        # TODO удалить этот блок
        text = update.message.text

        if text == 'Кнопка 1':
            text = "Вы нажали Кнопку 1! Пожалуйста, выберите следующую опцию:"

            # Определяем кнопки для нового сообщения
            keyboard = []
            for i in range(1, 21):
                keyboard.append([InlineKeyboardButton(f"Подкнопка 1.{i}", callback_data=f'subbutton1.{i}')])

            # Создаем клавиатуру
            reply_markup = InlineKeyboardMarkup(keyboard)

            # Обновляем сообщение с новой клавиатурой
            await update.message.reply_text(text, reply_markup=reply_markup)
            return

        await update.message.reply_text(f"Вы отправили сообщение: {text}")


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
