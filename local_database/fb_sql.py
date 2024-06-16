import datetime
import hashlib
import pickle
import sqlite3
import time
from itertools import chain
from matplotlib import pyplot as plt


if __name__ == '__main__':
    f1 = 'transactions.db'
    f2 = 'cts_lists.data'
    f3 = 'plots/'
else:
    f1 = 'local_database/transactions.db'
    f2 = 'local_database/cts_lists.data'
    f3 = 'local_database/plots/'

db1 = sqlite3.connect(f1)
crs1 = db1.cursor()

crs1.execute("""CREATE TABLE IF NOT EXISTS operations(
        user_id TEXT NOT NULL DEFAULT '1',
        date VARCHAR(16) NOT NULL,
        operation_name TEXT,
        price_per_unit REAL NOT NULL,
        amount REAL NOT NULL DEFAULT 1.0,
        total REAL NOT NULL,
        category VARCHAR NOT NULL,
        subcategory VARCHAR
    )""")
db1.commit()

ct_ex_list, ct_in_list, subct_ex_dict, subct_in_dict = \
    pickle.load(open(f2, 'rb'))

catgs = ct_ex_list + ct_in_list
subcatgs = list(chain.from_iterable(list(subct_in_dict.values()) +
                                    list(subct_ex_dict.values())))


def _md5id(value):
    """Функция для простой шифровки данных."""
    return hashlib.md5(str(value).encode()).hexdigest()


db1.create_function('md5', 1, _md5id)


def add_operation(oper_info: tuple):
    """
    Функция добавляет операцию в таблицу.

    :param oper_info: Информация об операции - это кортеж
    из 8-ми элементов, каждый из которых соответствует столбцу таблицы
    (идентификатор пользователя, дата, название операции,
    цена за единицу, количество, общая стоимость,
    категория, подкатегория).
    """
    assert len(oper_info) == 8, 'Кортеж всегда должен быть длины 8, ' \
                                'все элементы должны быть заполнены.'

    db = sqlite3.connect(f1)
    crs = db.cursor()
    db.create_function('md5', 1, _md5id)  # создание функции шифрования

    # Поиск введённой операции в таблице
    crs.execute("SELECT * FROM operations "
                f"WHERE user_id = md5({oper_info[0]}) AND "
                f"date = '{oper_info[1]}' AND "
                f"operation_name = '{oper_info[2]}' AND "
                f"price_per_unit = {oper_info[3]}")

    if crs.fetchone() is None:  # Если таковой нет, то добавляем её
        crs.execute("INSERT INTO operations "
                    "VALUES(md5(?), ?, ?, ?, ?, ?, ?, ?)",
                    oper_info)
        db.commit()

        crs.close()
        db.close()
        return True
    else:
        return False


def update_operation(oper_info: tuple):
    """
    Функция обновляет количество и общую сумму у операции
    с такими же датой, названием и ценой за единицу.

    :param oper_info: Информация об операции - это кортеж
    из 8-ми элементов, каждый из которых соответствует столбцу таблицы
    (идентификатор пользователя, дата, название операции,
    цена за единицу, количество, общая стоимость,
    категория, подкатегория).
    """
    with sqlite3.connect(f1) as db:
        crs = db.cursor()
        # создание функции шифрования
        db.create_function('md5', 1, _md5id)

        crs.execute("UPDATE operations SET "
                    f'amount = amount + {oper_info[4]}, '
                    f'total = amount + {oper_info[5]} '
                    f'WHERE user_id = md5({oper_info[0]}) AND '
                    f"date = '{oper_info[1]}' AND "
                    f"operation_name = '{oper_info[2]}'AND "
                    f"price_per_unit = {oper_info[3]}")


def delete_operation(oper_info: tuple):
    """
    Функция удаляет операцию из таблицы по её первым четырём полям.

    :param oper_info: Информация об операции - это кортеж
    из 8-ми элементов, каждый из которых соответствует столбцу таблицы
    (идентификатор пользователя, дата, название операции,
    цена за единицу, количество, общая стоимость,
    категория, подкатегория).
    """
    assert len(oper_info) >= 4, 'Поиск операции происходит ' \
                                'по её первым четырём полям.'

    with sqlite3.connect(f1) as db:
        crs = db.cursor()
        # создание функции шифрования
        db.create_function('md5', 1, _md5id)

        crs.execute("DELETE FROM operations WHERE user_id = md5(?) AND "
                    "date = ? AND operation_name = ? AND "
                    "price_per_unit = ?", oper_info[:4])
        print(f'Operation: {"   ".join(map(str, oper_info[1:4]))}'
              ' - deleted successfully')


def select_operations(points: tuple or list = None,
                      cols: str or tuple or list = None,
                      eqs: str or tuple or list = None, ui='1',
                      *, sort_by: str or tuple or list = None):
    """
    Функция выбирает все операции, соответствующие указанным
    ограничителям (points) определённых полей (cols),
    и, при необходимости, сортирует эти данные
    по указанным полям (sort_by).

    :param points: Пары значений, по которым определяются ограничения
    выборки (на одно поле == два ограничителя, сначала наименьший,
    потом наибольший и никак иначе).
    :param cols: Параметры (столбцы), по которым устанавливаются
    ограничения выборки
    (одно поле == два ограничителя из кортежа points).
    :param eqs: Поля, по которым будет происходить фильтр операций.
    Допустимы категории и подкатегории.
    :param ui: Идентификатор пользователя.
    :param sort_by: Параметры, по которым происходит сортировка
    выбранных данных.
    :return: Список операций исходя из указанных ограничений.
    """
    # Список полей, доступных для параметра cols
    accessible = ['date', 'price_per_unit', 'amount', 'total']
    # Список всех существующих для сортировки полей, кроме user_id
    existing = accessible + ['operation_name', 'category',
                             'subcategory']

    db = sqlite3.connect(f1)
    crs = db.cursor()
    db.create_function('md5', 1, _md5id)  # создание функции шифрования
    # Инициализация sql-запроса
    sql_str = "SELECT * FROM operations " \
              f"WHERE user_id = md5({ui}) AND "

    def add_filters(sql_string, categories: str or tuple):
        """
        Функция, которая добавляет к sql-запросу поля для фильтрации
        операций по определённым категориям или подкатегориям.

        :param sql_string: Строка sql-запроса.
        :param categories: Поля для фильтрации.
        :return: Строка обновлённого sql-запроса.
        """
        if not sql_string.endswith(' AND '):
            sql_string += ' AND '

        if categories is not None:
            if isinstance(categories, str):
                if categories in catgs:
                    sql_string += f"category = '{categories}'"

                if categories in subcatgs:
                    sql_string += f"subcategory = '{categories}'"

            if isinstance(categories, tuple):
                # категории из кортежа
                cs = [c for c in categories if c in catgs]
                # подкатегории из картежа
                scs = [c for c in categories if c in subcatgs]
                if len(cs) == 1:  # Если категория одна,
                    # то добавляем как единичный фильтр
                    sql_string += f"category = '{cs[0]}' AND "
                else:  # Если несколько категорий,
                    sql_string += '('  # то открываем скобки
                    for c1 in cs:  # и добавляем каждую категорию
                        # по отдельности чере операнд OR
                        sql_string += f"category = '{c1}' OR "
                    else:
                        sql_string = sql_string[:-4]  # убираем " OR "

                    sql_string += ') AND '  # закрываем скобки

                if len(scs) == 1:
                    sql_string += f"subcategory = '{scs[0]}' AND "
                else:
                    sql_string += '('
                    for c1 in scs:
                        sql_string += f"subcategory = '{c1}' OR "
                    else:
                        sql_string = sql_string[:-4]

                    sql_string += ') AND '

        sql_string = sql_string if not sql_string.endswith(' AND ') \
            else sql_string[:-5]

        return sql_string

    def add_sort(sql_string, sort_by_tags):
        """
        Функция, которая добавляет поля сортировки к sql-запросу,
        если таковые указаны.

        :param sql_string: Строка sql-запроса.
        :param sort_by_tags: Поля сортировки
        :return: Строка завершённого sql-запроса.
        """
        if sort_by_tags is not None:
            sql_string += ' ORDER BY '
            if isinstance(sort_by_tags, str) \
                    and sort_by_tags in existing:
                sql_string += f'{sort_by_tags} DESC'

            if isinstance(sort_by_tags, tuple) \
                    and all(s in existing for s in sort_by_tags):
                for s in sort_by_tags:
                    sql_string += f'{s} DESC, '

                sql_string = sql_string[:-2]

        return sql_string

    if cols is not None and isinstance(cols, str) \
            and cols in accessible:
        assert len(points) == 2, 'Если параметр ограничения один, ' \
                                 'то ограничителей должно быть два'

        if cols == 'date':  # Если указано поле date,
            # то тип данных - текст
            sql_str += f"'{points[0]}' <= {cols} " \
                       f"AND {cols} <= '{points[1]}'"
        else:  # иначе тип данных - число
            sql_str += f"{points[0]} <= {cols} " \
                       f"AND {cols} <= {points[1]}"

        sql_str = add_filters(sql_str, eqs)  # Добавление фильтров,
        # если они указаны
        sql_str = add_sort(sql_str, sort_by)  # Добавление сортировки,
        # если она указана

        crs.execute(sql_str)
        return crs.fetchall()

    if cols is not None and isinstance(cols, tuple) \
            and all(c in accessible for c in cols):
        assert len(points) // 2 == len(cols), \
            'Ограничителей должно быть в два раз больше, ' \
            'чем параметров ограничения'

        for i in range(0, len(points), 2):
            if cols[i // 2] == 'date':
                sql_str += f"'{points[i]}' <= {cols[i // 2]} " \
                           f"AND {cols[i // 2]} <= '{points[i + 1]}'" \
                           f" AND "
            else:
                sql_str += f"{points[i]} <= {cols[i // 2]} " \
                           f"AND {cols[i // 2]} <= {points[i + 1]} AND "

        # Добавление фильтров, если они указаны, к строке sql-запроса,
        # за исключением последних пяти символов,
        # если те появляются (" AND ")
        sql_str = add_filters(sql_str, eqs)
        # Добавление сортировки, если она указана, к строке sql-запроса,
        # за исключением последних пяти символов в конце (" AND ")
        sql_str = add_sort(sql_str, sort_by)

        sql_str = sql_str if not sql_str.endswith(' AND ') \
            else sql_str[:-5]

        crs.execute(sql_str)
        return crs.fetchall()

    if points is None and cols is None:
        sql_str = sql_str if not sql_str.endswith(' AND ') \
            else sql_str[:-5]
        sql_str = add_filters(sql_str, eqs)
        sql_str = add_sort(sql_str, sort_by)

        sql_str = sql_str if not sql_str.endswith(' AND ') \
            else sql_str[:-5]

        crs.execute(sql_str)
        return crs.fetchall()

    crs.close()
    db.close()
    raise ValueError('Some of entered values are wrong '
                     f'(points = {points}, cols = {cols}, '
                     f'sort_by = {sort_by})')


def date_for(period: str = 'day'):
    """
    Функция возвращает один из четырёх промежутков времени
    от сегодняшнего дня.

    :param period: Период времени. Принимает одно из четырёх значений:
     'day', 'week', 'month' и 'year' - что означает соответственно день,
      неделя, месяц, год.
    :return: Указанный промежуток времени в виде кортежа.
    """
    assert period in ('day', 'week', 'month', 'year'), ''

    if period == 'day':
        now = datetime.date.today().isoformat()
        return [now + '-00-00', now + '-23-59']

    if period == 'week':
        now = datetime.date.today()
        opposite = str(now - datetime.timedelta(7))
        return [opposite + '-00-00', str(now) + '-23-59']

    if period == 'month':
        now = datetime.date.today()
        opposite = str(now - datetime.timedelta(30))
        return [opposite + '-00-00', str(now) + '-23-59']

    if period == 'year':
        now = datetime.date.today()
        opposite = str(now - datetime.timedelta(365))
        return [opposite + '-00-00', str(now) + '-23-59']


def date_current(period: str = 'day'):
    """
    Функция возвращает один из четырёх промежутков времени
    от настоящего момента до начала периода.

    :param period: Период времени. Принимает одно из четырёх значений:
    'day', 'week', 'month' и 'year' - что означает соответственно
    текущие день, неделя, месяц, год.
    :return: Текущий промежуток времени в виде кортежа.
    """
    assert period in ('day', 'week', 'month', 'year'), ''

    if period == 'day':
        now = datetime.date.today().isoformat()
        return [now + '-00-00',
                now + f'-{str(time.localtime().tm_hour):0>2s}'
                      f'-{str(time.localtime().tm_min):0>2s}']
    if period == 'week':
        now = datetime.date.today()
        opposite = str(now - datetime.timedelta(now.weekday()))
        return [opposite + '-00-00',
                str(now) + f'-{str(time.localtime().tm_hour):0>2s}'
                           f'-{str(time.localtime().tm_min):0>2s}']

    if period == 'month':
        now = datetime.date.today()
        opposite = str(now - datetime.timedelta(now.day - 1))
        return [opposite + '-00-00',
                str(now) + f'-{str(time.localtime().tm_hour):0>2s}'
                           f'-{str(time.localtime().tm_min):0>2s}']

    if period == 'year':
        now = datetime.date.today()
        opposite = str(datetime.date(now.year, 1, 1))
        return [opposite + '-00-00',
                str(now) + f'-{str(time.localtime().tm_hour):0>2s}'
                           f'-{str(time.localtime().tm_min):0>2s}']


def search_in_list(oper_list: list, search: str):
    """
    Функция ищет все операции из списка oper_list, в которых существует
    вхождение search в названии операции.

    :param oper_list: Список кортежей с информацией об операциях.
    :param search: Поисковой запрос.
    :return: Список операций, в которых найдено хотя бы
    одно вхождение search.
    """
    return [op for op in oper_list if search in op[2].lower()]


def show_table(oper_list: list) -> str:
    """
    Функция конструирует строку вывода списка операций
    из введённого списка кортежей (oper_list).

    :param oper_list: Список кортежей с информацией об операциях.
    :return: Отформатированная строка вывода информации
    из списка oper_list
    """
    assert len(oper_list[0]) == 8

    s = ""
    j = 0
    ex_list = [op for op in oper_list if op[5] < 0.0]
    if len(ex_list) > 0:
        s += "\tРасходы:\n"
        for op in ex_list:
            op = list(op)
            j += 1
            s += "{index}. {date} | ".format(date=op[1][:10], index=j)
            s += "{0: <35.35} | {1: <8.2f} | {2} | {3}\n".format(
                op[2], op[5] * -1, *op[6:])

    in_list = [op for op in oper_list if op[5] > 0.0]
    if len(in_list) > 0:
        s += "\tДоходы:\n"
        for op in in_list:
            op = list(op)
            j += 1
            s += "{index}. {date} | ".format(date=op[1][:10], index=j)
            s += "{0: <35.35} | {1: <8.2f} | {2} | {3}\n".format(
                op[2], *op[5:])

    return s


def show_balance(ui: str or int):
    """
    Функция суммирует доходы и расходы, показывая глобальный баланс
    пользователя.

    :param ui: Идентификатор пользователя.
    :return: Сумму доходов и расходов.
    """
    b_l = select_operations(ui=ui)
    return round(sum(op[5] for op in b_l), 2) \
        if b_l else 'ещё не создан'


def data_summary(oper_list: list, summary: str = 'day'):
    """
    Функция суммирует все стоимости операций из списка oper_list
    по четырём словарям: расходы по дате, доходы по дате,
    баланс и категории.

    :param oper_list: Список кортежей с информацией об операциях.
    :param summary: Периоды времени, по которым будут суммироваться
    стоимости операций. Может принимать 3 значения: 'day', 'month',
     'year'. Например, при значении day все операции для первых трёх
     словарей будут суммироваться по дням.
    :return: Пять словарей: первые три - с датами в качестве ключей,
    два последних - с категориями. Первый - расходы, второй - доходы,
    третий - изменение баланса, четвёртый - соотношение трат
    по категориям, пятый - соотношение доходов по категории.
    """
    assert len(oper_list[0]) == 8

    sd = []
    if summary == 'day':
        sd = set(it[1][:10] for it in oper_list)

    if summary == 'month':
        sd = set(it[1][:7] for it in oper_list)

    if summary == 'year':
        sd = set(it[1][:4] for it in oper_list)

    sd = sorted(sd)

    def make_dates(summary_dates, data, is_expences: bool = True):
        """
        Функция конструирует словарь расходов за периоды времени,
        указанные в summary_dates.

        :param summary_dates: Список дат.
        :param data: Список кортежей с информацией об операциях.
        :param is_expences: Являются ли данные рвсходами, если да,
        то все стоимости и цены будут умножены на -1
        :return: Словарь с дотами из summary_dates в качестве ключей
        и с суммами по этим периодом времени в качестве значений.
        """
        if is_expences:
            data = [(*it[:3], it[3] * -1, it[4], it[5] * -1, *it[6:])
                    for it in data if it[5] < 0]

        dates = {}
        for i, period in enumerate(summary_dates):
            if summary != 'year':
                p = period
                if len(period) < 10:
                    p = period + '-01'

                new_period = datetime.date(*map(int, p.split('-')))
            else:
                new_period = int(period)

            dates[new_period] = sum(it[5] for it in data
                                    if it[1].startswith(period))

        return dates

    dates_ex = dict(sorted(
        make_dates(
            sd, filter(lambda x: x[5] < 0, oper_list)
        ).items()
    )) if list(filter(lambda x: x[5] < 0, oper_list)) else None

    dates_in = dict(sorted(
        make_dates(
            sd, filter(lambda x: x[5] > 0, oper_list), False
        ).items()
    )) if list(filter(lambda x: x[5] > 0, oper_list)) else None

    sb = {}
    nd = lambda p: datetime.date(*map(int, p.split('-')))
    for j, period in enumerate(sd):
        if summary != 'year':
            p = period[:]
            if len(period) != 10:
                p = period + '-01'

            new_period = nd(p)

            sb[new_period] = sum(it[5] for it in oper_list
                                 if it[1].startswith(period))

            if j > 0:
                sb[new_period] += sb[nd(list(sd)[j - 1])]
        else:
            new_period = int(period)

            sb[new_period] = sum(it[5] for it in oper_list
                                 if it[1].startswith(period))

            if j > 0:
                sb[new_period] += sb[int(list(sd)[j - 1])]

    ctex = set(it[6] for it in oper_list if it[6] in ct_ex_list)
    ctin = set(it[6] for it in oper_list if it[6] in ct_in_list)
    if ctex:
        ct_ex = {}
        for ct in ctex:
            ct_ex[ct] = sum(it[5] * -1 for it in oper_list
                            if it[6] == ct)

        ct_ex = dict(sorted(ct_ex.items(), key=lambda x: x[1],
                            reverse=True))
    else:
        ct_ex = None

    if ctin:
        ct_in = {}
        for ct in ctin:
            ct_in[ct] = sum(it[5] for it in oper_list if it[6] == ct)

        ct_in = dict(sorted(ct_in.items(), key=lambda x: x[1],
                            reverse=True))
    else:
        ct_in = None

    return dates_ex, dates_in, dict(sorted(sb.items())), ct_ex, ct_in


def category_summary(oper_list: list, category: str):
    """
    Функция суммирует все стоимости операций из списка oper_list
    в словарь по подкатегориям указанной категории.

    :param oper_list:
    :param category: Категория, подкатегории которой будут представлены
    в словаре в качестве ключей.
    :return: Словарь стоимостей подкатегорий из указанной категории.
    """
    assert category in catgs \
           and category in list(subct_in_dict.keys())\
           + list(subct_ex_dict.keys())

    ssc = {}
    if category in ct_ex_list:
        increment = -1
        subcategories = set(it[7] for it in oper_list
                            if it[7] in subct_ex_dict[category])
    else:
        increment = 1
        subcategories = set(it[7] for it in oper_list
                            if it[7] in subct_in_dict[category])

    for sct in subcategories:
        ssc[sct] = sum(it[5] for it in oper_list if it[7] == sct) \
                   * increment

    return dict(sorted(ssc.items(), key=lambda x: x[1], reverse=True))


def make_main_report(data: list[dict, ] or tuple[dict, ], ui):
    """
    Функция создаёт две столбчатые диаграммы, показывающие доходы
    и расходы, две круговые диаграммы, показвыающие соотношение
    категорий доходов и расходов, и график изменения баланса
    пользователя.

    :param data: Список из пяти элементов, отвечающих за данные
    вышеописанных графиков. Если словаря нет или его невозможно создать,
     следует укащывать None.
    :param ui: Идентификатор пользователя.
    :return: Путь к изображению графиков.
    """
    assert data

    dates_ex, dates_in, summ_bal, cts_ex, cts_in = data

    plt.figure(1, figsize=(12, 12))

    if dates_ex is not None:
        plt.subplot(321)
        plt.bar(dates_ex.keys(), dates_ex.values())
        plt.title('Расходы')

    if dates_in is not None:
        plt.subplot(323)
        plt.bar(dates_in.keys(), dates_in.values())
        plt.title('Доходы')

    if cts_ex is not None:
        plt.subplot(322)
        plt.pie(cts_ex.values(), labels=cts_ex.keys(),
                autopct='%2.2f%%', shadow=True)
        plt.title('Структура расходов')

    if cts_in is not None:
        plt.subplot(324)
        plt.pie(cts_in.values(), labels=cts_in.keys(),
                autopct='%2.2f%%', shadow=True)
        plt.title('Структура доходов')

    ax = plt.subplot(3, 2, (5, 6))
    plt.plot(summ_bal.keys(), summ_bal.values())
    ax.axhline(0, color='r')
    plt.title('Изменение баланса')

    plt.savefig(f3 + str(ui) + '_main_report.png', dpi=320)
    plt.close()
    return f3 + str(ui) + '_main_report.png'


def make_categories_report(data, categories, ui):
    """
    Функция создаёт круговые диаграммы, отображающие соотношение
    подкатегорий в указанных категориях.

    :param data: Список словарей с данными по каждой категории.
    :param categories: Назвария категрий, соответствующие списку data.
    :param ui: Идентификатор пользователя.
    :return: Путь к изображению диаграмм.
    """
    assert data and categories

    rows = round(len(categories)**0.5)
    cols = len(categories) // rows
    if cols * rows < len(categories):
        cols += 1

    if len(categories) < 9:
        plt.figure(figsize=(cols * 5, rows * 5))
    else:
        plt.figure(figsize=(cols * 3, rows * 3))

    for i, category in enumerate(categories):
        plt.subplot(rows, cols, i+1)
        plt.pie(data[i].values(), labels=data[i].keys(),
                autopct='%2.2f%%', shadow=True)
        plt.title(category)

    plt.savefig(f3 + str(ui) + '_categories_report.png', dpi=320)
    plt.close()
    return f3 + str(ui) + '_categories_report.png'


if __name__ == '__main__':
    print(show_balance('1548032094'))
    print([(t[2], t[1]) for t in select_operations(
        ui=1548032094, sort_by='date')])

    crs1.execute("SELECT * FROM operations WHERE "
                 "user_id = md5(1548032094) AND 0.0 <= amount "
                 "AND amount <= 10000.0 ORDER BY total DESC")
    db1.commit()

    """
    crs1.execute("UPDATE operations SET date='2022-09-11-17-11' "
                 "WHERE user_id=md5(1548032094) "
                 "and date='00020002020-'")
    db1.commit()
    """

    so = select_operations(('2022-08-01-00-00', '2022-08-31-23-59'),
                           'date',
                           ('Еда', 'Хлебобулочные', 'Развлечения',
                            *subct_ex_dict['Развлечения']),
                           sort_by=('category', 'date'))
    print("Хлебобулочные = ",
          sum([op[5] for op in so if op[7] == 'Хлебобулочные']))

    print(*data_summary(select_operations(date_for('month'), "date",
                                          ui=1548032094),
                        'day'), sep='\n\n')
    make_main_report(data_summary(
        select_operations(date_for('month'), "date", ui=1548032094),
                     'day'), (True, True, True), 1548032094)

    d = []
    for c in ['Товары', "Еда"]:
        d.append(category_summary(
            select_operations(date_for('month'), "date", ui=1548032094),
            c))

    make_categories_report(d, ['Товары', "Еда"], ui=1548032094)
