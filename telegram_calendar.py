
from telegram import InlineKeyboardButton, InlineKeyboardMarkup,ReplyKeyboardRemove
import datetime
import calendar

month_name = ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']
week_days = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']


def separate_callback_data(data):
    """ Separate the callback data"""
    return data.split(";")


def create_callback_data(action,year,month,day):
    """ Create the callback data associated to each button"""
    return "CALENDAR" + ";" + ";".join([action,str(year),str(month),str(day)])


def create_calendar(year=None,month=None, first_day: datetime=None, ignored_days=[], last_day: datetime=None):
    """
    Create an inline keyboard with the provided year and month
    :param int year: Year to use in the calendar, if None the current year is used.
    :param int month: Month to use in the calendar, if None the current month is used.
    :return: Returns the InlineKeyboardMarkup object with the calendar.
    """
    now = datetime.datetime.now()
    if year == None: year = now.year
    if month == None: month = now.month
    data_ignore = create_callback_data("IGNORE", year, month, 0)
    keyboard = []
    #First row - Month and Year
    row=[]
    row.append(InlineKeyboardButton(month_name[month]+" "+str(year),callback_data=data_ignore))
    keyboard.append(row)
    #Second row - Week Days
    row=[]
    for day in ["Пн","Вт","Ср","Чт","Пт","Сб","Вс"]:
        row.append(InlineKeyboardButton(day,callback_data=data_ignore))
    keyboard.append(row)

    my_calendar = calendar.monthcalendar(year, month)
    for week in my_calendar:
        row=[]
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ",callback_data=data_ignore))
            else:
                d = datetime.datetime(year, month, day)
                if first_day is not None and last_day is not None:
                    if d < first_day or d > last_day:
                        row.append(InlineKeyboardButton(" ", callback_data=data_ignore))
                        continue
                    is_continue = False
                    for ignored_day, s, is_data in ignored_days:
                        if ignored_day == d:
                            is_continue = True
                            if is_data:
                                row.append(InlineKeyboardButton(s + ' ' + str(day), callback_data=create_callback_data("DAY", year, month, day)))
                                break
                            row.append(InlineKeyboardButton(s + ' ' + str(day), callback_data=data_ignore))
                            break
                    if is_continue:
                        continue

                row.append(InlineKeyboardButton(str(day), callback_data=create_callback_data("DAY", year, month, day)))
        keyboard.append(row)

    #Last row - Buttons
    row=[]
    row.append(InlineKeyboardButton("<",callback_data=create_callback_data("PREV-MONTH",year,month,day)))
    row.append(InlineKeyboardButton("отмена",callback_data=create_callback_data("BACK", year, month, 0)))
    row.append(InlineKeyboardButton(">",callback_data=create_callback_data("NEXT-MONTH",year,month,day)))
    keyboard.append(row)

    return InlineKeyboardMarkup(keyboard)


async def process_calendar_selection(update, context, first_day: datetime=None, ignored_days=[], last_day: datetime=None, is_redraw=False):
    """
    Process the callback_query. This method generates a new calendar if forward or
    backward is pressed. This method should be called inside a CallbackQueryHandler.
    :param telegram.Bot bot: The bot, as provided by the CallbackQueryHandler
    :param telegram.Update update: The update, as provided by the CallbackQueryHandler
    :return: Returns a tuple (Boolean,datetime.datetime), indicating if a date is selected
                and returning the date if so.
    """
    ret_data = (False,None)
    query = update.callback_query
    # print(query)
    (_,action,year,month,day) = separate_callback_data(query.data)
    curr = datetime.datetime(int(year), int(month), 1)
    if action == "IGNORE":
        await context.bot.answer_callback_query(callback_query_id=query.id)
    elif action == "DAY":
        # await context.bot.edit_message_text(text=query.message.text,
        #     chat_id=query.message.chat_id,
        #     message_id=query.message.message_id
        #     )
        ret_data = True,datetime.datetime(int(year),int(month),int(day))
    elif action == "PREV-MONTH":
        pre = curr - datetime.timedelta(days=1)
        await context.bot.edit_message_text(text=query.message.text,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_calendar(int(pre.year),int(pre.month), first_day, ignored_days, last_day))
    elif action == "NEXT-MONTH":
        ne = curr + datetime.timedelta(days=31)
        await context.bot.edit_message_text(text=query.message.text,
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_calendar(int(ne.year),int(ne.month), first_day, ignored_days, last_day))
    elif action == "BACK":
        await context.bot.edit_message_text(text='Действие отменено',
                                            chat_id=query.message.chat_id,
                                            message_id=query.message.message_id
                                            )
        ret_data = True, None
    else:
        await context.bot.answer_callback_query(callback_query_id= query.id,text="Something went wrong!")
        # UNKNOWN
    return ret_data


async def redraw_calendar(update, context, month, year, first_day: datetime=None, ignored_days=[], last_day: datetime=None, chat_id=None, message_id=None):
    if chat_id is None or message_id is None:
        query = update.callback_query
        await context.bot.edit_message_text(text='Календарь',
            chat_id=query.message.chat_id,
            message_id=query.message.message_id,
            reply_markup=create_calendar(year, month, first_day, ignored_days, last_day))
    else:
        if chat_id is not None and message_id is not None:
            await context.bot.edit_message_text(text='Календарь',
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=create_calendar(year, month, first_day, ignored_days, last_day))

