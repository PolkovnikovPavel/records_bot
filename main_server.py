from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, CallbackContext
from auth import token


# Обработчик команды /start
async def start(update: Update, context: CallbackContext) -> None:
    # Текст сообщения
    text = "Нажмите на кнопку ниже:"

    # Определяем инлайн-кнопки
    inline_keyboard = [
        [InlineKeyboardButton("Показать уведомление", callback_data='show_alert')],
        [InlineKeyboardButton("Показать сообщение", callback_data='show_message')]
    ]

    # Создаем инлайн-клавиатуру
    inline_reply_markup = InlineKeyboardMarkup(inline_keyboard)

    # Отправляем сообщение с инлайн-кнопками
    await update.message.reply_text(text, reply_markup=inline_reply_markup)


# Обработчик нажатия инлайн-кнопок
async def button_handler(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == 'show_alert':
        # Отправляем всплывающее уведомление (alert)
        await query.answer(text="Это всплывающее уведомление!", show_alert=True)
    elif query.data == 'show_message':
        # Отправляем сообщение в чат
        await query.edit_message_text(text="Вы нажали кнопку показать сообщение.")


def main() -> None:
    # Создаем Application и передаем ему токен вашего бота.
    application = Application.builder().token(token).build()

    # Регистрируем обработчик команды /start
    application.add_handler(CommandHandler("start", start))

    # Регистрируем обработчик нажатия инлайн-кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    # Запускаем бота
    application.run_polling()


if __name__ == '__main__':
    main()
