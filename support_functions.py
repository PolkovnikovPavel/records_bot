import json
import datetime


def get_template_from_json(string):
    return json.loads(string)


def get_json_from_template(template):
    return json.dumps(template)


def get_count_minutes(time):
    hour, minut = map(int, time.split(':'))
    return hour * 60 + minut


async def delete_message(update, context, to_del_message):
    if to_del_message is not None:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=to_del_message
        )


def get_first_ignored_and_last_days(cur):
    now = datetime.datetime.now()
    first_day = datetime.datetime(now.year, now.month, now.day)
    last_day = first_day + datetime.timedelta(days=31)

    cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 31''')
    result = cur.fetchall()
    ignored_days = []
    for i in range(len(result)):
        date = datetime.datetime.strptime(result[i][1], '%d.%m.%Y')
        if date == first_day:
            ignored_days.append((date, '*', True))
            continue
        cur.execute(f'''SELECT DISTINCT patient_id FROM records
                            WHERE day_id = {result[i][0]}''')
        records = cur.fetchall()
        if any(map(lambda x: x[0] is None, records)):
            ignored_days.append((date, '⭘', True))
        else:
            ignored_days.append((date, '◉', True))

    if first_day not in ignored_days:
        ignored_days.append((first_day, '*', True))
    return first_day, ignored_days, last_day
