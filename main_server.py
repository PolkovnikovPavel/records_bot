#!/usr/bin/python3

import logging, datetime
import auth

from telegram.ext import Updater, CallbackQueryHandler, CommandHandler, CallbackContext, Application
from telegram import ReplyKeyboardRemove, Update

import telegram_calendar

# Go to botfather and create a bot and copy the token and paste it here in token
TOKEN = auth.token  # token of the bot

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

logger = logging.getLogger(__name__)

first_day = datetime.datetime.strptime("11.07.2024", '%d.%m.%Y')
last_day = datetime.datetime.strptime("11.08.2024", '%d.%m.%Y')
ignored_days = [(datetime.datetime.strptime("15.07.2024", '%d.%m.%Y'), '✓', True),
                (datetime.datetime.strptime("16.07.2024", '%d.%m.%Y'), '✓', True),
                (datetime.datetime.strptime("17.07.2024", '%d.%m.%Y'), '✓', True)]


async def start(update, context):
    await update.message.reply_text(text="старт")


def separate_callback_data(data):
    """ Separate the callback data"""
    return data.split(";")


# A simple command to display the calender
async def calendar_handler(update, context):
    await update.message.reply_text(text='календарь',
        reply_markup=telegram_calendar.create_calendar(first_day=first_day, last_day=last_day, ignored_days=ignored_days))


async def inline_handler(update, context):
    query = update.callback_query
    (kind, _, _, _, _) = separate_callback_data(query.data)
    if kind == 'CALENDAR':
        await inline_calendar_handler(update, context)


async def inline_calendar_handler(update, context):
    selected, date = await telegram_calendar.process_calendar_selection(update, context, first_day=first_day, last_day=last_day, ignored_days=ignored_days)
    if selected:
        await update.message.reply_text(chat_id=update.callback_query.from_user.id,
                                 text='You selected %s' % (date.strftime("%d/%m/%Y")),
                                 reply_markup=ReplyKeyboardRemove())


if TOKEN == "":
    print("Please write TOKEN into file")
else:
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("calendar", calendar_handler))
    application.add_handler(CallbackQueryHandler(inline_handler))

    # Запускаем бота
    application.run_polling()
