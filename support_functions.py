import json
import datetime


def get_template_from_json(string):
    return json.loads(string)


def get_json_from_template(template):
    return json.dumps(template)


def get_count_minutes(time):
    hour, minut = map(int, time.split(':'))
    return hour * 60 + minut


def change_tg_menu(tg_id, new_type, con, cur):
    inquiry = f"""UPDATE accounts
    SET tg_menu = {new_type}
        WHERE tg_id = '{tg_id}'"""
    cur.execute(inquiry)
    con.commit()


async def delete_message(update, context, to_del_message):
    if to_del_message is not None:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=to_del_message
        )


async def delete_messages(update, context, to_del_messages):
    for id in to_del_messages:
        if id is not None:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=id
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
            ignored_days.append((date, '📌', True))
            continue
        cur.execute(f'''SELECT DISTINCT patient_id FROM records
                            WHERE day_id = {result[i][0]}''')
        records = cur.fetchall()
        if any(map(lambda x: x[0] is None, records)):
            ignored_days.append((date, '⭘', True))
        else:
            ignored_days.append((date, '◉', True))

    if first_day not in ignored_days:
        ignored_days.append((first_day, '📌', True))
    return first_day, ignored_days, last_day


def get_first_ignored_and_last_days_for_canceled(cur):
    now = datetime.datetime.now()
    first_day = datetime.datetime(now.year, now.month, now.day)
    last_day = first_day + datetime.timedelta(days=31)

    cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 31''')
    result = cur.fetchall()
    ignored_days = []
    for i in range(len(result)):
        date = datetime.datetime.strptime(result[i][1], '%d.%m.%Y')
        if date == first_day:
            ignored_days.append((date, '📌', True))
            continue
        cur.execute(f'''SELECT DISTINCT patient_id FROM records
                            WHERE day_id = {result[i][0]}''')
        records = cur.fetchall()
        if any(map(lambda x: x[0] is not None, records)):
            ignored_days.append((date, '◉', True))
        else:
            ignored_days.append((date, '⭘', True))

    if first_day not in ignored_days:
        ignored_days.append((first_day, '📌', True))
    return first_day, ignored_days, last_day


def get_clients_first_ignored_and_last_days(cur, user_id):
    now = datetime.datetime.now()
    first_day = datetime.datetime(now.year, now.month, now.day)
    last_day = first_day + datetime.timedelta(days=31)

    cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 31''')
    result = cur.fetchall()

    data_date = []
    for i in range(len(result)):
        date = datetime.datetime.strptime(result[i][1], '%d.%m.%Y')
        data_date.append((result[i][0], date))

    ignored_days = []
    data = datetime.datetime(now.year, now.month, now.day) - datetime.timedelta(days=1)
    while data <= last_day:
        data += datetime.timedelta(days=1)
        this_date = list(filter(lambda x: x[1] == data, data_date))
        if this_date:
            cur.execute(f'''SELECT DISTINCT patient_id FROM records
            WHERE day_id = {this_date[0][0]} AND is_cancel = 0 AND (patient_id = {user_id} OR patient_id IS NULL)''')
            records = cur.fetchall()
            if data == first_day:
                if any(map(lambda x: x[0] is None, records)):
                    ignored_days.append((data, '📌', True))
                else:
                    ignored_days.append((data, '📌', False))
                continue
            if records:
                if any(map(lambda x: x[0] == user_id, records)):
                    ignored_days.append((data, '◉', True))
                else:
                    ignored_days.append((data, '⭘', True))
            else:
                ignored_days.append((data, '', False))
        else:
            ignored_days.append((data, '', False))
    return first_day, ignored_days, last_day


def get_active_accounts(cur):
    now = datetime.datetime.now() - datetime.timedelta(days=1)

    cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 31''')
    result = cur.fetchall()
    days_id = []
    for day in result:
        date = datetime.datetime.strptime(day[1], '%d.%m.%Y')
        if date >= now:
            days_id.append(day[0])

    inquiry = []
    for id in days_id:
        inquiry.append(f'day_id = {id}')
    inquiry = 'SELECT patient_id FROM records WHERE patient_id AND (' + ' OR '.join(inquiry) + ')'
    cur.execute(inquiry)
    result = list(map(lambda x: x[0], cur.fetchall()))
    result = set(result)
    return list(result)


def get_simple_account(cur):
    inquiry = 'SELECT id FROM accounts WHERE tg_id < 0 AND is_deleted = 0'
    cur.execute(inquiry)
    result = list(map(lambda x: x[0], cur.fetchall()))
    return result


def get_timetable_by_user(cur, patient_id):
    now = datetime.datetime.now() - datetime.timedelta(days=1)

    cur.execute(f'''SELECT * FROM days ORDER BY id DESC LIMIT 31''')
    result = cur.fetchall()
    days_id = []
    for day in result:
        date = datetime.datetime.strptime(day[1], '%d.%m.%Y')
        if date >= now:
            days_id.append(day[0])
    inquiry = []
    for id in days_id:
        inquiry.append(f'records.day_id = {id}')
    inquiry = f'SELECT records.time, days.date FROM records, days WHERE records.is_cancel = 0 AND days.id = records.day_id AND patient_id = {patient_id} AND (' + ' OR '.join(inquiry) + ')'
    cur.execute(inquiry)
    result = cur.fetchall()
    res = []
    for time, date in result:
        res.append((time, datetime.datetime.strptime(date, '%d.%m.%Y')))
    res.sort(key=lambda x: x[1])
    return res


def get_future_records(cur, patient_id):
    cur.execute(f'''SELECT DISTINCT records.time, days.date, records.id FROM records, days
    WHERE days.id = records.day_id AND records.is_cancel = 0 AND records.patient_id = {patient_id}''')
    result = cur.fetchall()

    now = datetime.datetime.now() - datetime.timedelta(days=1)
    records_data = []
    for i in range(len(result)):
        date = datetime.datetime.strptime(result[i][1], '%d.%m.%Y')
        if date < now:
            continue
        records_data.append((result[i][0], date, result[i][2]))
    records_data.sort(key=lambda x: x[1])
    return records_data


def get_records_for_reminder(cur):
    now = datetime.datetime.now() + datetime.timedelta(days=1)
    cur.execute(f'''SELECT DISTINCT records.id, records.time, days.date, accounts.tg_id FROM records, days, accounts
    WHERE records.patient_id = accounts.id AND days.date = "{now.strftime("%d.%m.%Y")}" AND records.day_id = days.id AND records.is_cancel = 0 AND records.is_reminder = 0''')
    result = cur.fetchall()
    return result


if __name__ == '__main__':
    import sqlite3
    con = sqlite3.connect('data/db.db')
    cur = con.cursor()
    x = get_simple_account(cur)
    print(x)
