import aiogram
import os
import pickle
import shelve
import sys
import time
from aiogram import types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import Dispatcher, FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import exceptions, executor
from collections import deque
from datetime import date

import local_database.fb_sql as db
from parser.fb_parser import CHECK


__version__ = '1.0'

clf_ex, clf_in = pickle.load(
    open('data_define\\categorizer.data', 'rb'))
ct_ex_list, ct_in_list, subct_ex_dict, subct_in_dict = \
    pickle.load(open('local_database\\cts_lists.data', 'rb'))
# store = shelve.open('local_database\\backup_data.data')


bot = aiogram.Bot(os.getenv('TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())


class FSMAdmin(StatesGroup):
    qr = State()
    heqr = State()
    hand_enter = State()

    oper_type = State()
    choice1 = State()
    category = State()
    set_subcat = State()
    add_operation = State()

    gsd_for = State()
    gsd_current = State()
    gsd_other = State()
    set_graphs = State()
    set_dgm = State()

    date_for = State()
    date_current = State()
    date_other = State()
    amount = State()
    ppu = State()
    total = State()
    catfilt = State()
    subcatfilt = State()
    sort_it = State()
    search = State()

    delete_it_all = State()
    delop = State()
    del_select = State()


# Обычные функции
async def setup_on(_):
    print('Bot https://t.me/fin_man_bot is online!')


# Обработчики команд
@dp.message_handler(commands=['start'], state='*')
async def start_bot(message: types.Message, state: FSMContext):
    if state is not None:
        await state.finish()

    b = db.show_balance(message.from_user.id)

    buttons = [
        types.InlineKeyboardButton('Добавить QR-код',
                                   callback_data='qr'),
        types.InlineKeyboardButton('Добавить самостоятельно',
                                   callback_data='hand_enter'),
        types.InlineKeyboardButton('Посмотреть операции',
                                   callback_data='show_what'),
        types.InlineKeyboardButton('Удаление',
                                   callback_data='delete')
    ]

    kb1 = types.InlineKeyboardMarkup()
    kb1.add(buttons[0]).add(buttons[1]).add(buttons[2])
    kb1.add(buttons[3])

    msg = f"Доброго времени суток, {message.from_user.full_name}.\n\n" \
          f"\tВаш баланс: {b}\n\nВыберите одно из следующих действий."
    await bot.send_message(message.from_user.id, msg, reply_markup=kb1)


@dp.message_handler(commands=['help'])
async def user_help(message: types.Message):
    msg = "Добавить QR-код - вставка текста отсканированного QR-кода " \
          "и обработка каждой строки из чека отдельно.\n" \
          "Добавить самостоятельно - ручной ввод информации " \
          "об операции/ях с датой равной дате отправки сообщения " \
          "и обработка каждой введённой строки отдельно.\n" \
          "Посмотреть операции - поиск и вывод списка всех найденных " \
          "операций в одном сообщении, либо просмотр графиков" \
          " расходов и доходов\n" \
          "Удаление - поиск и удаление выбранных операций, либо" \
          " восстановление всех последних удалённых операций.\n"
    await bot.send_message(message.from_user.id, msg)


# Обработчики состояний
@dp.message_handler(state=FSMAdmin.qr)
async def load_qr(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        ul = data.get('items_' + str(message.from_user.id))
        if ul is None:
            data['qr_' + str(message.from_user.id)] = message.text
            t = CHECK(message.text)
            data['date_' + str(message.from_user.id)] = t.date()
            print(data['date_' + str(message.from_user.id)])
            try:
                li = t.get_list()
            except Exception as e:
                li = []
                await bot.send_message(
                    message.from_user.id,
                    'Похоже, произошла непредвиденная ошибка:\n'
                    + ' '.join(map(str, e.args))
                    + "\n\nПопробуйте повторить то же самое "
                      "через пару-тройку дней. Обычно за это время "
                      "данные чеков успевают появиться.")

            data['items_' + str(message.from_user.id)] = deque(li)

            if not li:
                bt1 = types.InlineKeyboardButton(
                    'Ввести самостоятельно',
                    callback_data='hand_enter_qr')
                bt2 = types.InlineKeyboardButton('Пропустить',
                                                 callback_data='pass1')

                kb2 = types.InlineKeyboardMarkup()
                kb2.add(bt1).add(bt2)
                await message.answer('Информация с этого чека не была '
                                     'загружена.',
                                     reply_markup=kb2)
            else:
                for i, item in enumerate(li):
                    li[i] = [item[0], *map(float, item[1:])]

                data['items_' + str(message.from_user.id)] = deque(li)

        elif len(ul) == 0:
            await state.finish()
            await bot.send_message(
                message.from_user.id,
                'Вся информация по чеку была успешно введена!',
                reply_markup=types.ReplyKeyboardRemove())

        if state is not None \
                and data['items_' + str(message.from_user.id)]:
            data['oper_' + str(message.from_user.id)] = \
                data['items_' + str(message.from_user.id)].popleft()
            oper = data['oper_' + str(message.from_user.id)]
            print(oper)

            bt1 = types.KeyboardButton('Расход')
            bt2 = types.KeyboardButton('Доход')

            kb3 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                            one_time_keyboard=True)
            kb3.row(bt1, bt2)
            await FSMAdmin.oper_type.set()
            await bot.send_message(message.from_user.id,
                                   'Выберите тип для операции:'
                                   f'\n{oper[0]}',
                                   reply_markup=kb3)


@dp.message_handler(state=FSMAdmin.heqr)
async def hand_enter_qr_post(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        d = data.get('date_' + str(message.from_user.id))
        if d is None:
            data['date_' + str(message.from_user.id)] = \
                date.today().isoformat() \
                + f'-{str(time.localtime().tm_hour):0>2s}' \
                  f'-{str(time.localtime().tm_min):0>2s}'

        ul = data.get('items_' + str(message.from_user.id))
        if ul is None:
            s = message.text
            oper_list = []
            if '\n' in s:
                items = s.split('\n')
                for item in items:
                    if item:
                        item = item.split('   ')
                        oper_list.append(
                            [item[0], *map(float, item[1:])])
            else:
                item = s.split('   ')
                oper_list.append([item[0], *map(float, item[1:])])

            data['items_' + str(message.from_user.id)] = \
                deque(oper_list)
        elif len(ul) == 0:
            await state.finish()
            await bot.send_message(
                message.from_user.id,
                'Вся информация по чеку была успешно введена!',
                reply_markup=types.ReplyKeyboardRemove())

        if state is not None:
            data['oper_' + str(message.from_user.id)] = \
                data['items_' + str(message.from_user.id)].popleft()
            oper = data['oper_' + str(message.from_user.id)]

            bt1 = types.KeyboardButton('Расход')
            bt2 = types.KeyboardButton('Доход')

            kb4 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                            one_time_keyboard=True)
            kb4.add(bt1).add(bt2)
            await FSMAdmin.oper_type.set()
            await bot.send_message(message.from_user.id,
                                   'Выберите тип для операции:'
                                   f'\n{oper[0]}',
                                   reply_markup=kb4)


@dp.message_handler(state=FSMAdmin.hand_enter)
async def add_operation(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        d = data.get('date_' + str(message.from_user.id))
        if d is None:
            data['date_' + str(message.from_user.id)] = \
                date.today().isoformat() \
                + f'-{str(time.localtime().tm_hour):0>2s}' \
                  f'-{str(time.localtime().tm_min):0>2s}'

        ul = data.get('items_' + str(message.from_user.id))
        if ul is None:
            s = message.text
            oper_list = []
            if '\n' in s:
                items = s.split('\n')
                for item in items:
                    if item:
                        item = item.split('   ')
                        oper_list.append(
                            [item[0], *map(float, item[1:])])
            else:
                item = s.split('   ')
                oper_list.append([item[0], *map(float, item[1:])])

            data['items_' + str(message.from_user.id)] = \
                deque(oper_list)
        elif len(ul) == 0:
            await state.finish()
            await bot.send_message(
                message.from_user.id,
                'Вся введённая информация была успешно введена!',
                reply_markup=types.ReplyKeyboardRemove())

        if state is not None:
            data['oper_' + str(message.from_user.id)] = \
                data['items_' + str(message.from_user.id)].popleft()
            oper = data['oper_' + str(message.from_user.id)]

            bt1 = types.KeyboardButton('Расход')
            bt2 = types.KeyboardButton('Доход')

            kb5 = types.ReplyKeyboardMarkup(resize_keyboard=True)
            kb5.add(bt1).add(bt2)
            await FSMAdmin.oper_type.set()
            await bot.send_message(message.from_user.id,
                                   'Выберите тип для операции:'
                                   f'\n{oper[0]}',
                                   reply_markup=kb5)


@dp.message_handler(state=FSMAdmin.oper_type)
async def oper_type(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if data.get('oper_type_' + str(message.from_user.id)) is None:
            data['oper_type_' + str(message.from_user.id)] = \
                message.text

        msg = "Текущие введённые данные:\n" \
              f"{data['oper_' + str(message.from_user.id)][0]}"

        if data['oper_type_' + str(message.from_user.id)] == 'Доход':
            if data.get('ct_' + str(message.from_user.id)) is None:
                ct = clf_in.predict(
                    [data['oper_' + str(message.from_user.id)][0]])[0]
                data['ct_' + str(message.from_user.id)] = ct
                msg = "Для операции " \
                    f"{data['oper_' + str(message.from_user.id)][0]} " \
                    f"определена категория {ct}.\nЕсли категория " \
                    "бала определена верно, нажмите " \
                    "Установить подкатегорию.\nЕсли хотите изменить " \
                    "её изменить, нажмите Изменить категорию или Далее."

            if message.text.isdigit():
                try:
                    data['ct_' + str(message.from_user.id)] = \
                        ct_in_list[int(message.text) - 1]
                except IndexError:
                    await bot.send_message(message.from_user.id,
                                           "Неверно введена цифра, "
                                           "попробуйте снова.")

            msg += f"{data['ct_' + str(message.from_user.id)]}"

            bt1 = types.InlineKeyboardButton('Изменить категорию',
                                             callback_data='change_cat')
            bt3 = types.InlineKeyboardButton('Далее',
                                             callback_data='add_item')

            kb6 = types.InlineKeyboardMarkup()
            kb6.add(bt1)

            ct = data.get('ct_' + str(message.from_user.id))
            if ct is not None:
                msg += f"   {ct}."

            subct = data.get('subct_' + str(message.from_user.id))
            if subct is not None:
                msg += f"   {subct}."
                bt2 = types.InlineKeyboardButton(
                    'Установить подкатегорию',
                    callback_data='set_subcat')
                kb6.add(bt2)
            elif subct is None \
                    and data['ct_' + str(message.from_user.id)] \
                    in subct_in_dict.keys():
                bt2 = types.InlineKeyboardButton(
                    'Установить подкатегорию',
                    callback_data='set_subcat')
                kb6.add(bt2)

            kb6.add(bt3)
            await bot.send_message(message.from_user.id, msg,
                                   reply_markup=kb6)

        if data['oper_type_' + str(message.from_user.id)] == 'Расход':
            if data.get('ct_' + str(message.from_user.id)) is None:
                ct = clf_ex.predict(
                    [data['oper_' + str(message.from_user.id)][0]])[0]
                data['ct_' + str(message.from_user.id)] = ct

                item = data['oper_' + str(message.from_user.id)]
                if item[1] >= 0:
                    item = [item[0], item[1] * -1,
                            item[2], item[3] * -1]
                data['oper_' + str(message.from_user.id)] = item

                msg = "Для операции " \
                    f"{data['oper_' + str(message.from_user.id)][0]} " \
                    f"определена категория \"{ct}\".\nЕсли категория " \
                    "бала определена верно, нажмите " \
                    "Установить подкатегорию.\nЕсли хотите изменить " \
                    "её, нажмите Изменить категорию."

            if message.text.isdigit():
                try:
                    data['ct_' + str(message.from_user.id)] = \
                        ct_ex_list[int(message.text) - 1]
                except IndexError:
                    await bot.send_message(message.from_user.id,
                                           "Неверно введена цифра, "
                                           "попробуйте снова.")

            ct = data.get('ct_' + str(message.from_user.id))
            if ct is not None:
                msg += f"   {ct}"

            subct = data.get('subct_' + str(message.from_user.id))
            if subct is not None:
                msg += f"   {subct}"

            bt1 = types.InlineKeyboardButton('Изменить категорию',
                                             callback_data='change_cat')
            bt2 = types.InlineKeyboardButton('Установить подкатегорию',
                                             callback_data='set_subcat')
            bt3 = types.InlineKeyboardButton('Далее',
                                             callback_data='add_item')

            kb7 = types.InlineKeyboardMarkup()
            kb7.add(bt1).add(bt2).add(bt3)
            await bot.send_message(message.from_user.id, msg,
                                   reply_markup=kb7)


@dp.message_handler(state=FSMAdmin.set_subcat)
async def set_subcategory(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        o_t = data['oper_type_' + str(message.from_user.id)]
        item = data['oper_' + str(message.from_user.id)]
        ct = data['ct_' + str(message.from_user.id)]
        if message.text.isdigit():
            if o_t == 'Доход':
                data['subct_' + str(message.from_user.id)] = \
                    subct_in_dict[ct][int(message.text) - 1]

            if o_t == 'Расход':
                data['subct_' + str(message.from_user.id)] = \
                    subct_ex_dict[ct][int(message.text) - 1]

        if message.text.replace(' ', '').isalpha():
            if o_t == 'Доход':
                data['subct_' + str(message.from_user.id)] = \
                    message.text

            if o_t == 'Расход':
                data['subct_' + str(message.from_user.id)] = \
                    message.text

    if o_t == 'Доход':
        msg = "Текущие введённые данные:\n" \
              f"{item[0]}   {item[1]}   {item[2]}   {item[3]}   {ct}" \
              f"   {data['subct_' + str(message.from_user.id)]}"

    if o_t == 'Расход':
        msg = "Текущие введённые данные:\n" \
            f"{item[0]}   {item[1] * -1}   {item[2]}   {item[3] * -1}" \
            f"   {ct}   {data['subct_' + str(message.from_user.id)]}"

    bt1 = types.InlineKeyboardButton('Изменить категорию',
                                     callback_data='change_cat')
    bt2 = types.InlineKeyboardButton('Установить подкатегорию',
                                     callback_data='set_subcat')
    bt3 = types.InlineKeyboardButton('Далее',
                                     callback_data='add_item')

    kb8 = types.InlineKeyboardMarkup()
    kb8.add(bt1).add(bt2).add(bt3)
    await FSMAdmin.oper_type.set()
    await bot.send_message(message.from_user.id, msg,
                           reply_markup=kb8)


@dp.message_handler(state=FSMAdmin.add_operation)
async def add_operation(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if message.text == 'Добавить операцию':
            ui = message.from_user.id
            date = data['date_' + str(message.from_user.id)]
            name = data['oper_' + str(message.from_user.id)][0]
            price = data['oper_' + str(message.from_user.id)][1:]
            if data['oper_type_' + str(message.from_user.id)] \
                    == 'Расход' and price[0] >= 0:
                price[0] = price[0] * -1
                price[2] = price[2] * -1

            ct = data['ct_' + str(message.from_user.id)]
            subct = data.get('subct_' + str(message.from_user.id))
            operation = (ui, date, name, *price, ct, subct)
            try:
                added = db.add_operation(operation)
            except Exception as e:
                await bot.send_message(
                    message.from_user.id,
                    "Похоже, произошла непредвиденная ошибка:\n"
                    f"{' '.join(map(str, e.args))}\n\n"
                    "Попробуйте повторить все действия заново, "
                    "вдруг сработает.")

                added = None
                del data['ct_' + str(message.from_user.id)]
                if data.get('subct_' + str(message.from_user.id)) \
                        is not None:
                    del data['subct_' + str(message.from_user.id)]

                if data.get('qr_' + str(message.from_user.id)) is None:
                    await FSMAdmin.hand_enter.set()
                else:
                    await FSMAdmin.qr.set()

            if not added and added is not None:
                bt1 = types.InlineKeyboardButton(
                    'Прибавить',
                    callback_data='update_yes')
                bt2 = types.InlineKeyboardButton(
                    'Пропустить',
                    callback_data='update_no')

                kb9 = types.InlineKeyboardMarkup()
                kb9.row(bt1, bt2)
                await bot.send_message(
                    message.from_user.id,
                    f'Такая операция ({date}   {name}   '
                    f'{price[0]}) уже существует.\n'
                    'Вы хотите прибавить введённые данные '
                    'к уже существующим?\n'
                    'Если нет, то нажмите Пропустить '
                    'и отправьте любое сообщение.', reply_markup=kb9)
            elif added is not None:
                qr = data.get('qr_' + str(message.from_user.id))
                if data['oper_type_' + str(message.from_user.id)] \
                   == 'Доход':
                    with open('data_define/data_set_in.txt',
                              'a', encoding='utf-8') as f:
                        f.write(name + ' @ ' + ct + '\n')

                if data['oper_type_' + str(message.from_user.id)] \
                   == 'Расход':
                    with open('data_define/data_set_ex.txt',
                              'a', encoding='utf-8') as f:
                        f.write(name + ' @ ' + ct + '\n')

                await bot.send_message(
                    message.from_user.id,
                    f'Операция {date}   {name}   '
                    f'{price[0]} успешно добавлена!\n'
                    'Отправьте любое сообщение, чтобы продолжить.',
                    reply_markup=types.ReplyKeyboardRemove())

                del data['ct_' + str(message.from_user.id)]
                if data.get('subct_' + str(message.from_user.id)) \
                        is not None:
                    del data['subct_' + str(message.from_user.id)]

                if qr is None:
                    await FSMAdmin.hand_enter.set()
                else:
                    await FSMAdmin.heqr.set()

        if message.text == 'Назад к вводу данных':
            qr = data.get('qr_' + str(message.from_user.id))

            del data['ct_' + str(message.from_user.id)]
            if data.get('subct_' + str(message.from_user.id)) \
                    is not None:
                del data['subct_' + str(message.from_user.id)]

            if qr is None:
                await FSMAdmin.hand_enter.set()
            else:
                await FSMAdmin.qr.set()


@dp.message_handler(state=FSMAdmin.gsd_for)
async def graphs_date_for(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        args = {"День": "day", "Неделя": "week",
                "Месяц": "month", "Год": "year"}
        date = db.date_for(args[message.text])
        data['graphs_data'] = db.select_operations(
            date, 'date', ui=message.from_user.id, sort_by='date')

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='graphs_period')

        kb10 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            "Установлен следующий промежуток времени: "
            f"{date[0]} до {date[1]}.",
            reply_markup=kb10)


@dp.message_handler(state=FSMAdmin.gsd_current)
async def graphs_date_current(message: types.Message,
                              state: FSMContext):
    async with state.proxy() as data:
        args = {"День": "day", "Неделя": "week",
                "Месяц": "month", "Год": "year"}
        date = db.date_current(args[message.text])
        data['graphs_data'] = db.select_operations(
            date, 'date', ui=message.from_user.id, sort_by='date')

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='graphs_period')

        kb10 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            "Установлен следующий промежуток времени: "
            f"{date[0]} до {date[1]}.",
            reply_markup=kb10)


@dp.message_handler(state=FSMAdmin.gsd_other)
async def graphs_date_other(message: types.Message,
                            state: FSMContext):
    try:
        l1, l2 = message.text.split('   ')
    except ValueError:
        await FSMAdmin.gsd_other.set()
        await bot.send_message(message.from_user.id,
                               "Вы ввели неправильные данные. "
                               "Попробуйте ещё раз")

    async with state.proxy() as data:
        date = (l1, l2)
        data['graphs_data'] = db.select_operations(
            date, 'date', ui=message.from_user.id, sort_by='date')

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='graphs_period')

        kb10 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            "Установлен следующий промедуток времени: "
            f"{l1} до {l2}.",
            reply_markup=kb10)


@dp.message_handler(state=FSMAdmin.set_graphs)
async def set_all_graphs(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if message.text == 'По дням':
            data['summary'] = 'day'
        if message.text == 'По месяцам':
            data['summary'] = 'month'
        if message.text == 'По годам':
            data['summary'] = 'year'

    bt1 = types.InlineKeyboardButton('Далее',
                                     callback_data='set_ct_dgm')

    kb11 = types.InlineKeyboardMarkup().add(bt1)
    await bot.send_message(message.from_user.id,
                           'Установлено суммирование '
                           f'{message.text.lower()}.',
                           reply_markup=kb11)


@dp.message_handler(state=FSMAdmin.set_dgm)
async def set_diagrams(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        cs = data['dgm_cts']
        if message.text[0].isdigit():
            try:
                if message.text.isdigit():
                    cs = [cs[int(message.text) - 1]]
                else:
                    cs = [cs[int(i) - 1]
                          for i in message.text.split(', ')]
            except IndexError:
                await bot.send_message(message.from_user.id,
                                       'Извините, но вы неправильно '
                                       'ввели номера категорий, '
                                       'Попробуйте ещё раз.')
            data['dgm_cts'] = cs
        if message.text == '_':
            data['dgm_cts'] = cs
        if message.text == '-':
            data['dgm_cts'] = None

    if sys.exc_info()[0] is not IndexError:
        bt1 = types.InlineKeyboardButton('Паказать',
                                         callback_data='graph_show')

        kb12 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(message.from_user.id,
                               'Настройки графиков завершены!',
                               reply_markup=kb12)


@dp.message_handler(state=FSMAdmin.date_for)
async def choose_date_for(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        args = {"День": "day", "Неделя": "week",
                "Месяц": "month", "Год": "year"}
        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = db.date_for(args[message.text])
            filargs['cols'] = ['date']

        elif 'date' not in filargs['cols']:
            filargs['points'].extend(db.date_for(args[message.text]))
            filargs['cols'].append('date')

        elif 'date' in filargs['cols']:
            i = [i for i, a in enumerate(filargs['points']) if '-' in a]
            filargs['points'][i[0]:i[1] + 1] = \
                db.date_for(args[message.text])

        data['filter_args_' + str(message.from_user.id)] = filargs
        l1, l2 = db.date_for(args[message.text])

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb10 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по дате от {l1} до {l2} установлен.",
            reply_markup=kb10)


@dp.message_handler(state=FSMAdmin.date_current)
async def choose_date_current(message: types.Message,
                              state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        args = {"День": "day", "Неделя": "week",
                "Месяц": "month", "Год": "year"}
        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = db.date_current(args[message.text])
            filargs['cols'] = ['date']

        elif 'date' not in filargs['cols']:
            filargs['points'].extend(
                db.date_current(args[message.text]))
            filargs['cols'].append('date')

        elif 'date' in filargs['cols']:
            i = [i for i, a in enumerate(filargs['points']) if '-' in a]
            filargs['points'][i[0]:i[1] + 1] = \
                db.date_current(args[message.text])

        data['filter_args_' + str(message.from_user.id)] = filargs
        l1, l2 = db.date_current(args[message.text])

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb11 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по дате от {l1} до {l2} установлен.",
            reply_markup=kb11)


@dp.message_handler(state=FSMAdmin.date_other)
async def choose_date_other(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        try:
            l1, l2 = message.text.split('   ')
        except ValueError:
            await FSMAdmin.date_other.set()
            await bot.send_message(message.from_user.id,
                                   "Вы ввели неправильные данные. "
                                   "Попробуйте ещё раз")

        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = [l1, l2]
            filargs['cols'] = ['date']

        elif 'date' not in filargs['cols']:
            filargs['points'].extend([l1, l2])
            filargs['cols'].append('date')

        elif 'date' in filargs['cols']:
            i = [i for i, a in enumerate(filargs['points']) if '-' in a]
            filargs['points'][i[0]:i[1] + 1] = [l1, l2]

        data['filter_args_' + str(message.from_user.id)] = filargs

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb12 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по дате от {l1} до {l2} установлен.",
            reply_markup=kb12)


@dp.message_handler(state=FSMAdmin.amount)
async def choose_amount(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        try:
            l1, l2 = message.text.split('   ')
            l1, l2 = float(l1), float(l2)
        except ValueError:
            await FSMAdmin.amount.set()
            await bot.send_message(message.from_user.id,
                                   "Вы ввели неправильные данные. "
                                   "Попробуйте ещё раз")

        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = [l1, l2]
            filargs['cols'] = ['amount']

        elif 'amount' not in filargs['cols']:
            filargs['points'].extend([l1, l2])
            filargs['cols'].append('amount')

        elif 'amount' in filargs['cols']:
            i = filargs['cols'].index('amount')
            filargs['points'][i*2:i*2 + 1] = [l1, l2]

        data['filter_args_' + str(message.from_user.id)] = filargs

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb13 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по количеству от {l1} до {l2} установлен.",
            reply_markup=kb13)


@dp.message_handler(state=FSMAdmin.ppu)
async def choose_ppu(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        try:
            l1, l2 = message.text.split('   ')
            l1, l2 = float(l1), float(l2)
        except ValueError:
            await FSMAdmin.amount.set()
            await bot.send_message(message.from_user.id,
                                   "Вы ввели неправильные данные. "
                                   "Попробуйте ещё раз")

        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = [l1, l2]
            filargs['cols'] = ['price_per_unit']

        elif 'price_per_unit' not in filargs['cols']:
            filargs['points'].extend([l1, l2])
            filargs['cols'].append('price_per_unit')

        elif 'price_per_unit' in filargs['cols']:
            i = filargs['cols'].index('price_per_unit')
            filargs['points'][i * 2:i * 2 + 1] = [l1, l2]

        data['filter_args_' + str(message.from_user.id)] = filargs

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb14 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по цене за единицу от {l1} до {l2} установлен.",
            reply_markup=kb14)


@dp.message_handler(state=FSMAdmin.total)
async def choose_total(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        try:
            l1, l2 = message.text.split('   ')
            l1, l2 = float(l1), float(l2)
        except ValueError:
            await FSMAdmin.total.set()
            await bot.send_message(message.from_user.id,
                                   "Вы ввели неправильные данные. "
                                   "Попробуйте ещё раз")

        if filargs['points'] is None and filargs['cols'] is None:
            filargs['points'] = [l1, l2]
            filargs['cols'] = ['total']

        elif 'total' not in filargs['cols']:
            filargs['points'].extend([l1, l2])
            filargs['cols'].append('total')

        elif 'total' in filargs['cols']:
            i = filargs['cols'].index('total')
            filargs['points'][i * 2:i * 2 + 1] = [l1, l2]

        data['filter_args_' + str(message.from_user.id)] = filargs

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='select')

        kb15 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(
            message.from_user.id,
            f"Фильтр по общей стоимости от {l1} до {l2} установлен.",
            reply_markup=kb15)


@dp.message_handler(state=FSMAdmin.catfilt)
async def ct_flt(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        if ', ' in message.text:
            cts = [db.catgs[int(i) - 1]
                   for i in message.text.split(', ')]
        else:
            cts = [db.catgs[int(message.text) - 1]]

        if filargs['eqs'] is None:
            filargs['eqs'] = cts
        else:
            filargs['eqs'] = list(set(filargs['eqs']) | set(cts))

        data['filter_args_' + str(message.from_user.id)] = filargs
        cts = ', '.join(cts)

        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='ct_filters')

        kb16 = types.InlineKeyboardMarkup()
        kb16.add(bt1)
        await bot.send_message(message.from_user.id,
                               "Вы добавили фильтры по категориям:\n"
                               f"{cts}",
                               reply_markup=kb16)


@dp.message_handler(state=FSMAdmin.subcatfilt)
async def subct_flt(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data['filter_args_' + str(message.from_user.id)]
        scs_dict = data['scs_dict_' + str(message.from_user.id)]

        if ', ' in message.text:
            numbers = message.text.split(', ')
            numbers.sort()
        else:
            numbers = [message.text]

        cs = []
        scs = []
        for n in numbers:
            if len(n) < 4:
                ci, sci = int(n[0]) - 1, int(n[1:]) - 1
            else:
                ci, sci = int(n[:2]) - 1, int(n[2:]) - 1

            sct = scs_dict[ci][1][sci]
            scs.append(sct)
            cs.append(ci)

            filargs['eqs'] = list(set(filargs['eqs']) | set(sct))

        no_cs = [c for c in range(len(scs_dict)) if c not in cs]
        if no_cs:
            for i in no_cs:
                filargs['eqs'] = list(set(filargs['eqs'])
                                      | set(scs_dict[i][1]))
                scs.extend(scs_dict[i][1])

        data['filter_args_' + str(message.from_user.id)] = filargs

        scs = ', '.join(scs)
        bt1 = types.InlineKeyboardButton('Вернуться назад',
                                         callback_data='ct_filters')

        kb17 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(message.from_user.id,
                               "Вы добавили фильтры по подкатегориям:\n"
                               f"{scs}",
                               reply_markup=kb17)


@dp.message_handler(state=FSMAdmin.sort_it)
async def sort_it(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        filargs = data.get('filter_args_' + str(message.from_user.id))
        if filargs is None:
            data['filter_args_' + str(message.from_user.id)] = \
                dict.fromkeys(
                    ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                    None)
            data['filter_args_' + str(message.from_user.id)]['ui'] = \
                message.from_user.id
            filargs = data['filter_args_' + str(message.from_user.id)]

        params = list({'Дата': 'date', "Название": 'operation_name',
                       "Цена за единицу": 'price_per_unit',
                       "Количество": 'amount',
                       "Общая стоимость": 'total',
                       "Категории": 'category',
                       "Подкатегории": 'subcategory'}.items())

        sorters = [params[int(i) - 1][1]
                   for i in message.text.split(', ')]
        filargs['sort_by'] = sorters
        data['filter_args_' + str(message.from_user.id)] = filargs

    params = {'Дата': 'date', "Название": 'operation_name',
              "Цена за единицу": 'price_per_unit',
              "Количество": 'amount',
              "Общая стоимость": 'total',
              "Категории": 'category',
              "Подкатегории": 'subcategory'}
    sorters = [list(params.items())
               [list(params.values()).index(s)][0]
               for s in filargs['sort_by']]

    bt1 = types.InlineKeyboardButton('Назад',
                                     callback_data='is_sorting')

    kb18 = types.InlineKeyboardMarkup().add(bt1)
    await bot.send_message(message.from_user.id,
                           "Добавлена сотрировка:\n"
                           f"{', '.join(sorters)}",
                           reply_markup=kb18)


@dp.message_handler(state=FSMAdmin.search)
async def search_all(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['search_' + str(message.from_user.id)] = message.text
        query = data['search_' + str(message.from_user.id)]

        bt1 = types.InlineKeyboardButton('Назад',
                                         callback_data='search')

        kb19 = types.InlineKeyboardMarkup().add(bt1)
        await bot.send_message(message.from_user.id,
                               f"Добавлен поисковой запрос: {query}",
                               reply_markup=kb19)


@dp.message_handler(state=FSMAdmin.delete_it_all)
async def del_it_all(message: types.Message, state: FSMContext):
    items = db.select_operations(ui=message.from_user.id,
                                 sort_by='date')

    save = []
    indexes = map(int, message.text.split()) if message.text != '_' \
        else range(len(items))

    for i in indexes:
        try:
            save.append(items[i-1])
            db.delete_operation(items[i-1])
        except IndexError:
            continue

    store = shelve.open('local_database\\backup_data.data')
    first_key = [k for k in store
                 if k.startswith(str(message.from_user.id))]
    key = str(message.from_user.id) + '_' \
        + date.today().isoformat() \
        + f'-{str(time.localtime().tm_hour):0>2s}' \
        f'-{str(time.localtime().tm_min):0>2s}'
    store[key] = save
    if first_key:
        del store[first_key[0]]

    await state.finish()
    await bot.send_message(message.from_user.id,
                           f"{len(save)} выбранных вами операций "
                           "были успешно удалены. Если вы что-то "
                           "удалили по ошибке, воспользуйтесь кнопкой"
                           " \"Восстановить удалённое\" "
                           "в главном меню, чтобы вернуть всё, "
                           "что вы удаляли в последний раз.")


@dp.message_handler(state=FSMAdmin.del_select)
async def del_selected(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        items = data['del_items_' + str(message.from_user.id)]

    save = []
    indexes = map(int, message.text.split()) if message.text != '_' \
        else range(len(items))

    for i in indexes:
        try:
            save.append(items[i - 1])
            db.delete_operation(items[i - 1])
        except IndexError:
            continue

    store = shelve.open('local_database\\backup_data.data')
    first_key = [k for k in store
                 if k.startswith(str(message.from_user.id))]
    key = str(message.from_user.id) + '_' \
        + date.today().isoformat() \
        + f'-{str(time.localtime().tm_hour):0>2s}' \
        f'-{str(time.localtime().tm_min):0>2s}'
    store[key] = save
    if first_key:
        del store[first_key[0]]

    await state.finish()
    await bot.send_message(message.from_user.id,
                           f"{len(save)} выбранных вами операций "
                           "были успешно удалены. Если вы что-то "
                           "удалили по ошибке, воспользуйтесь кнопкой"
                           " \"Восстановить удалённое\" "
                           "в главном меню, чтобы вернуть всё, "
                           "что вы удаляли в последний раз.")


# Обработчики колбэков от инлайнровых кнопок
@dp.callback_query_handler(lambda call: call.data == 'qr')
async def add_qr_code(call: types.CallbackQuery):
    await FSMAdmin.qr.set()
    await bot.send_message(call.from_user.id,
                           'Вставьте текст отсканированного QR-кода '
                           'и ждите чуда:')


@dp.callback_query_handler(lambda call: call.data == 'hand_enter')
async def add_qr_code(call: types.CallbackQuery):
    await bot.send_message(call.from_user.id,
                           'Введите информацию по шаблону ниже:\n'
                           'название операции, '
                           'цена за единицу измерения, количество, '
                           'общая стоимость (отделяя каждый параметр '
                           'тремя пробелами, как показано ниже \/).\n'
                           'Мука Белиевская в/с 2кг 1/   82.00   1   '
                           '82.00\nСалфетки комфорт бум б/рис   '
                           '21.00   2   42.00\nЯблоки   159.90   '
                           '0.866   138.47\n   100   1   100 '
                           '(можно пропустить имя таким способом)\n\n'
                           'Вводите каждую такую операцию '
                           'с новой строки')
    await FSMAdmin.hand_enter.set()


@dp.callback_query_handler(lambda call: call.data == 'hand_enter_qr',
                           state=FSMAdmin.qr)
async def hand_enter_qr(call: types.CallbackQuery, state: FSMContext):
    await bot.send_message(call.from_user.id,
                           'Введите информацию по шаблону ниже:\n'
                           'название операции, '
                           'цена за единицу измерения, количество, '
                           'общая стоимость (отделяя каждый параметр '
                           'тремя пробелами, как показано ниже \/).\n'
                           'Мука Белиевская в/с 2кг 1/   82.00   1   '
                           '82.00\nСалфетки комфорт бум б/рис   '
                           '21.00   2   42.00\nЯблоки   159.90   '
                           '0.866   138.47\n   100   1   100 '
                           '(можно пропустить имя таким способом)\n\n'
                           'Вводите каждую такую операцию '
                           'с новой строки')
    await FSMAdmin.heqr.set()


@dp.callback_query_handler(lambda call: call.data == 'change_cat',
                           state=[FSMAdmin.oper_type,
                                  FSMAdmin.set_subcat])
async def change_category(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        o_t = data['oper_type_' + str(call.from_user.id)]

    await FSMAdmin.oper_type.set()

    if o_t == 'Расход':
        t_ex = ''.join([f'\n{i + 1}. {c}'
                        for i, c in enumerate(ct_ex_list)])

    if o_t == 'Доход':
        t_ex = ''.join([f'\n{i + 1}. {c}'
                        for i, c in enumerate(ct_in_list)])
    await bot.send_message(call.from_user.id,
                           "Введите цифру одной "
                           f"из следующих категорий:\n{t_ex}",
                           reply_markup=types.ReplyKeyboardRemove())


@dp.callback_query_handler(lambda call: call.data == 'set_subcat',
                           state=[FSMAdmin.oper_type,
                                  FSMAdmin.set_subcat])
async def set_subcat(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        o_t = data['oper_type_' + str(call.from_user.id)]
        await FSMAdmin.set_subcat.set()

        ct = data['ct_' + str(call.from_user.id)]
        if o_t == 'Расход':
            t_ex = ''.join([f'\n{i + 1}. {c}'
                            for i, c in enumerate(subct_ex_dict[ct])])

        if o_t == 'Доход':
            t_ex = ''.join([f'\n{i + 1}. {c}'
                            for i, c in enumerate(subct_in_dict[ct])])
        await bot.send_message(call.from_user.id,
                               "Выберите номер одной из подкатегорий "
                               "в соответствии с выбранной категорией:"
                               + t_ex + "\n\nИли введите свою "
                                        "собственную подкатегорию.",
                               reply_markup=types.ReplyKeyboardRemove())


@dp.callback_query_handler(lambda call: call.data == 'add_item',
                           state=[FSMAdmin.set_subcat,
                                  FSMAdmin.oper_type])
async def add_item(call: types.CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        o_t = data['oper_type_' + str(call.from_user.id)]
        date = data['date_' + str(call.from_user.id)]
        name = data['oper_' + str(call.from_user.id)][0]
        price = data['oper_' + str(call.from_user.id)][1:]
        ct = data['ct_' + str(call.from_user.id)]
        subct = data.get('subct_' + str(call.from_user.id))
        if o_t == 'Доход':
            msg = "Информация об операции была введена со следующими " \
                  f"данными:\n{date}   {name}   {price[0]}   " \
                  f"{price[1]}   {price[2]}   {ct}   {subct}"

        if o_t == 'Расход':
            msg = "Информация об операции была введена со следующими " \
                  f"данными:\n{date}   {name}   {price[0] * -1}   " \
                  f"{price[1]}   {price[2] * -1}   {ct}   {subct}"

        bt1 = types.KeyboardButton('Добавить операцию')
        bt2 = types.KeyboardButton('Назад к вводу данных')

        kb20 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb20.add(bt1).add(bt2)
        await bot.send_message(call.from_user.id, msg,
                               reply_markup=kb20)
        await FSMAdmin.add_operation.set()


@dp.callback_query_handler(lambda call: call.data.startswith('update'),
                           state=FSMAdmin.add_operation)
async def update_operation(call: types.CallbackQuery,
                           state: FSMContext):
    async with state.proxy() as data:
        if call.data.endswith('yes'):
            ui = call.from_user.id
            date = data['date_' + str(call.from_user.id)]
            name = data['oper_' + str(call.from_user.id)][0]
            price = data['oper_' + str(call.from_user.id)][1:]
            operation = (ui, date, name, *price)
            db.update_operation(operation)
            await bot.send_message(
                call.from_user.id,
                'Информация об операции была успешно обновлена!',
                reply_markup=types.ReplyKeyboardRemove())

            del data['ct_' + str(call.from_user.id)]
            if data.get('subct_' + str(call.from_user.id)) \
                    is not None:
                del data['subct_' + str(call.from_user.id)]

            qr = data.get('qr_' + str(call.from_user.id))
            if qr is None:
                await FSMAdmin.hand_enter.set()
            else:
                await FSMAdmin.heqr.set()

        if call.data.endswith('no'):
            del data['ct_' + str(call.from_user.id)]
            if data.get('subct_' + str(call.from_user.id)) \
                    is not None:
                del data['subct_' + str(call.from_user.id)]

            qr = data.get('qr_' + str(call.from_user.id))
            if qr is None:
                await FSMAdmin.hand_enter.set()
            else:
                await FSMAdmin.qr.set()


@dp.callback_query_handler(lambda call: call.data == 'show_what')
async def what_to_show(call: types.CallbackQuery):
    if db.select_operations(ui=call.from_user.id):
        msg = "Выберите: показать графики или список операций."

        bt1 = types.InlineKeyboardButton('Показать графики',
                                         callback_data='show_graphs')
        bt2 = types.InlineKeyboardButton(
            'Показать список', callback_data='show_operations')

        kb21 = types.InlineKeyboardMarkup()
        kb21.row(bt1, bt2)
        await bot.send_message(call.from_user.id, msg,
                               reply_markup=kb21)
    else:
        msg = "Я, конечно, извиняюсь, но у вас ничего нет.\n" \
              "Вы либо ничего не добавляли, либо всё удалили."
        await bot.send_message(call.from_user.id, msg)


@dp.callback_query_handler(lambda call: call.data == 'show_graphs')
async def show_graphs(call: types.CallbackQuery):
    msg = "Выберите: показать на графике все операции " \
          "или настроить параметры."

    bt1 = types.InlineKeyboardButton('Настроить',
                                     callback_data='graphs_period')
    bt2 = types.InlineKeyboardButton(
        'Показать всё', callback_data='show_all_graphs')

    kb21 = types.InlineKeyboardMarkup()
    kb21.row(bt1, bt2)
    await bot.send_message(call.from_user.id, msg,
                           reply_markup=kb21)


@dp.callback_query_handler(lambda call: call.data == 'show_operations')
async def show_opertations(call: types.CallbackQuery):
    msg = "Выберите: посмотреть всё (если данных много, " \
          "то сообщение сократиться до первых 45 строк) " \
          "или найти операции по определённым " \
          "значениям параметров."

    bt1 = types.InlineKeyboardButton('Поиск по фильтрам',
                                     callback_data='select')
    bt2 = types.InlineKeyboardButton('Показать всё',
                                     callback_data='show_all')

    kb21 = types.InlineKeyboardMarkup()
    kb21.row(bt1, bt2)
    await bot.send_message(call.from_user.id, msg,
                           reply_markup=kb21)


@dp.callback_query_handler(lambda call:
                           call.data.startswith('show_all'))
async def show_all_operations(call: types.CallbackQuery):
    items = db.select_operations(ui=call.from_user.id, sort_by='date')
    if call.data.endswith('graphs') and items:
        data = db.data_summary(items)
        file = db.make_main_report(data, call.from_user.id)
        await bot.send_photo(call.from_user.id, open(file, 'rb'))

    elif items:
        if len(items) > 100:
            items = items[:100]

        bt1 = types.InlineKeyboardButton('Завершить поиск',
                                         callback_data='pass')

        kb22 = types.InlineKeyboardMarkup().add(bt1)
        try:
            await bot.send_message(call.from_user.id,
                                   db.show_table(items),
                                   reply_markup=kb22)
        except exceptions.MessageIsTooLong:
            await bot.send_message(call.from_user.id,
                                   db.show_table(items[:45]),
                                   reply_markup=kb22)
    else:
        await bot.send_message(call.from_user.id,
                               "Извините, ничего не найдено. "
                               "Скорее всего вы ничего не добавляли.")


@dp.callback_query_handler(lambda call: call.data == 'graphs_period',
                           state='*')
async def set_graphs_period(call: types.CallbackQuery,
                            state: FSMContext):
    bt1 = types.InlineKeyboardButton('В течение периода',
                                     callback_data='gsd_for')
    bt2 = types.InlineKeyboardButton('За текущий период',
                                     callback_data='gsd_current')
    bt3 = types.InlineKeyboardButton(
        'Выбрать другой период времени',
        callback_data='gsd_other')

    kb24 = types.InlineKeyboardMarkup()
    kb24.row(bt1, bt2).add(bt3)
    if state is not None:
        bt5 = types.InlineKeyboardButton('Далее',
                                         callback_data='set_graphs')
        kb24.add(bt5)

    await bot.send_message(call.from_user.id,
                           "Выберите период времени, которым хотите"
                           " ограничить выбор операций",
                           reply_markup=kb24)


@dp.callback_query_handler(lambda call: call.data.startswith('gsd'),
                           state='*')
async def graphs_date(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'for':
        bt1 = types.KeyboardButton('День')
        bt2 = types.KeyboardButton('Неделя')
        bt3 = types.KeyboardButton('Месяц')
        bt4 = types.KeyboardButton('Год')

        kb25 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb25.row(bt1, bt2, bt3, bt4)
        await FSMAdmin.gsd_for.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от сегодняшнего дня до дня, который "
            "был неделю назад.",
            reply_markup=kb25)

    if aim == 'current':
        bt1 = types.KeyboardButton('День')
        bt2 = types.KeyboardButton('Неделя')
        bt3 = types.KeyboardButton('Месяц')
        bt4 = types.KeyboardButton('Год')

        kb26 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb26.row(bt1, bt2, bt3, bt4)
        await FSMAdmin.gsd_current.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от настоящего момента до дня, который "
            "был или есть началом недели.",
            reply_markup=kb26)

    if aim == 'other':
        await FSMAdmin.gsd_other.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции по следующему шаблону.\n\n"
            "2022-08-01-00-01   2022-08-31-12-03\n\n"
            "(год-месяц-день-час-минута, "
            "разделяя ограничители тремя пробелами)")


@dp.callback_query_handler(lambda call: call.data == 'set_graphs',
                           state='*')
async def graphs_settings(call: types.CallbackQuery):
    if __version__ != '1.0':
        await bot.send_message(call.from_user.id,
                               'This feature is still developing,'
                               ' sorry :(')
    else:
        await FSMAdmin.set_graphs.set()
        bt1 = types.KeyboardButton('По дням')
        bt2 = types.KeyboardButton('По месяцам')
        bt3 = types.KeyboardButton('По годам')

        kb23 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb23.row(bt1, bt2, bt3)
        await bot.send_message(call.from_user.id,
                               'Выберите периоды времени, '
                               'по которым на графиках будут '
                               'отображаться расходы и доходы:',
                               reply_markup=kb23)


@dp.callback_query_handler(lambda call: call.data == 'set_ct_dgm',
                           state='*')
async def categories_diagrams(call: types.CallbackQuery,
                              state: FSMContext):
    async with state.proxy() as data:
        d = data['graphs_data']
        cs = list(set(it[6] for it in d))
        data['dgm_cts'] = cs
        t_ct = '\n'.join([f'{i+1}. {c}' for i, c in enumerate(cs)])
        await FSMAdmin.set_dgm.set()
        await bot.send_message(
            call.from_user.id,
            'Введите через запятую цифры категорий, по которым '
            'вы хотите увидеть соотношения подкатегорий\nили\n'
            'Введите символ нижнего подчёркивания, чтобы выбрать '
            'все категории\nили\nВведите тире (-), чтобы провустить:\n'
            f'{t_ct}')


@dp.callback_query_handler(lambda call: call.data == 'graph_show',
                           state=FSMAdmin.set_dgm)
async def show_graphs_and_diagrams(call: types.CallbackQuery,
                                   state: FSMContext):
    async with state.proxy() as data:
        d = data['graphs_data']
        cs = data['dgm_cts']
        summ = data['summary']

        d_main = db.data_summary(d, summ)
        file = db.make_main_report(d_main, call.from_user.id)
        await bot.send_photo(call.from_user.id, open(file, 'rb'))

        if cs is not None:
            d_ct = [db.category_summary(d, c) for c in cs]
            file = db.make_categories_report(
                d_ct, cs, call.from_user.id)
            await bot.send_photo(call.from_user.id, open(file, 'rb'))


@dp.callback_query_handler(lambda call: call.data.startswith('select'),
                           state='*')
async def select_operations(call: types.CallbackQuery,
                            state: FSMContext):
    msg = "Выберите параметр, по которому вы хотите " \
          "ограничить поиск операций."

    if call.data.endswith('dal'):
        await FSMAdmin.delop.set()
        async with state.proxy() as data:
            data['del'] = True

    if state is not None:
        async with state.proxy() as data:
            filargs = data.get('filter_args_' + str(call.from_user.id))
            if filargs is not None:
                msg += "\nВаши текущие фильтры:\n"
                args = {'date': 'Дата',
                        'price_per_unit': 'Цена за единицу',
                        'amount': 'Количество',
                        'total': 'Общая стоимость'}
                if filargs['cols'] is not None:
                    for i in range(0, len(filargs['points']), 2):
                        msg += f"{args[filargs['cols'][i//2]]}:" \
                               f" от {filargs['points'][i]} " \
                               f"до {filargs['points'][i+1]};\n"

    bt1 = types.InlineKeyboardButton('Дата',
                                     callback_data='choose_date')
    bt2 = types.InlineKeyboardButton('Количество',
                                     callback_data='choose_amount')
    bt3 = types.InlineKeyboardButton('Цена за единицу',
                                     callback_data='choose_ppu')
    bt4 = types.InlineKeyboardButton('Общая стоимость',
                                     callback_data='choose_total')
    bt5 = types.InlineKeyboardButton('Далее', callback_data='ct_filters')

    kb23 = types.InlineKeyboardMarkup()
    kb23.row(bt1, bt2).row(bt3, bt4).add(bt5)
    await bot.send_message(call.from_user.id,
                           msg,
                           reply_markup=kb23)


@dp.callback_query_handler(lambda call: call.data.startswith('choose'),
                           state='*')
async def choose_limits(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'date':
        bt1 = types.InlineKeyboardButton('В течение периода',
                                         callback_data='period_for')
        bt2 = types.InlineKeyboardButton('За текущий период',
                                         callback_data='period_current')
        bt3 = types.InlineKeyboardButton(
            'Выбрать другой период времени',
            callback_data='period_other')

        kb24 = types.InlineKeyboardMarkup()
        kb24.row(bt1, bt2).add(bt3)
        await bot.send_message(call.from_user.id,
                               "Выберите период времени, которым хотите"
                               " ограничить поиск операций",
                               reply_markup=kb24)

    if aim == 'amount':
        await FSMAdmin.amount.set()
        await bot.send_message(call.from_user.id,
                               "Введите значения количества, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "0.001   1.999 (разделяя ограничители "
                               "тремя пробелами)")

    if aim == 'ppu':
        await FSMAdmin.ppu.set()
        await bot.send_message(call.from_user.id,
                               "Введите значения цены за единицу, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "-99.99   9999.99 (разделяя "
                               "ограничители тремя пробелами "
                               "(значения со знаком \"-\" - расходы, "
                               "без - доходы))")

    if aim == 'total':
        await FSMAdmin.total.set()
        await bot.send_message(call.from_user.id,
                               "Введите значения общей стоимости, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "-1000.00   10000.00 (разделяя "
                               "ограничители тремя пробелами "
                               "(значения со знаком \"-\" - расходы, "
                               "без - доходы))")


@dp.callback_query_handler(lambda call: call.data.startswith('period'),
                           state='*')
async def choose_time(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'for':
        bt1 = types.KeyboardButton('День')
        bt2 = types.KeyboardButton('Неделя')
        bt3 = types.KeyboardButton('Месяц')
        bt4 = types.KeyboardButton('Год')

        kb25 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb25.row(bt1, bt2, bt3, bt4)
        await FSMAdmin.date_for.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от сегодняшнего дня до дня, который "
            "был неделю назад.",
            reply_markup=kb25)

    if aim == 'current':
        bt1 = types.KeyboardButton('День')
        bt2 = types.KeyboardButton('Неделя')
        bt3 = types.KeyboardButton('Месяц')
        bt4 = types.KeyboardButton('Год')

        kb26 = types.ReplyKeyboardMarkup(resize_keyboard=True,
                                         one_time_keyboard=True)
        kb26.row(bt1, bt2, bt3, bt4)
        await FSMAdmin.date_current.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от настоящего момента до дня, который "
            "был или есть началом недели.",
            reply_markup=kb26)

    if aim == 'other':
        await FSMAdmin.date_other.set()
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций "
            "по следующему шаблону.\n\n"
            "2022-08-01-00-01   2022-08-31-12-03\n\n"
            "(год-месяц-день-час-минута, "
            "разделяя ограничители тремя пробелами)")


@dp.callback_query_handler(lambda call: call.data == 'ct_filters',
                           state='*')
async def category_filter(call: types.CallbackQuery, state: FSMContext):
    msg = ""
    if state is not None:
        async with state.proxy() as data:
            filargs = data.get('filter_args_' + str(call.from_user.id))
            if filargs is None:
                data['filter_args_' + str(call.from_user.id)] = \
                    dict.fromkeys(
                        ['points', 'cols', 'eqs', 'ui', 'sort_by'],
                        None)
                data['filter_args_' + str(call.from_user.id)]['ui'] = \
                    call.from_user.id
                filargs = data['filter_args_' + str(call.from_user.id)]

            if filargs['eqs'] is not None:
                cs = [c for c in filargs['eqs'] if c in db.catgs]
                scs = [c for c in filargs['eqs'] if c in db.subcatgs]
                msg += "Уже выбраны:\n" if cs else ""
            else:
                cs, scs = None, None

            if cs:
                msg += 'Категории:\n\t'
                for c in cs:
                    msg += (c + ", ")
                else:
                    msg = msg[:-2]
                    msg += '\n'

            if scs:
                msg += 'Подкатегории:\n\t'
                for sc in scs:
                    msg += (sc + ', ')
                else:
                    msg = msg[:-2]
                    msg += '\n'

    bt1 = types.InlineKeyboardButton("Выбрать категории",
                                     callback_data='cat_filt')
    bt3 = types.InlineKeyboardButton("Далее",
                                     callback_data='is_sorting')

    kb27 = types.InlineKeyboardMarkup()
    if msg:
        bt2 = types.InlineKeyboardButton(
            "Выбрать подкатегории", callback_data='subcat_filt')
        kb27.row(bt1, bt2).add(bt3)
    else:
        kb27.row(bt1, bt3)

    await bot.send_message(call.from_user.id,
                           f"Выбрать фильтр по категориям?\n{msg}"
                           "Если нет, то фильтр по подкатегориям "
                           "пропуститься автоматически.",
                           reply_markup=kb27)


@dp.callback_query_handler(lambda call: call.data == 'cat_filt',
                           state='*')
async def cat_filt(call: types.CallbackQuery, state: FSMContext):
    t_ex = ''.join([f'{i + 1}. {c}\n'
                    for i, c in enumerate(db.catgs)])
    await FSMAdmin.catfilt.set()
    await bot.send_message(call.from_user.id,
                           "Введите номера одной или нескольких "
                           "категорий из существующих через запятую "
                           f"(например: 1, 6, 4 ):\n{t_ex}")


@dp.callback_query_handler(lambda call: call.data == 'subcat_filt',
                           state='*')
async def subcat_filt(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        async with state.proxy() as data:
            ex_sc = list(subct_ex_dict.keys())
            filargs = data['filter_args_' + str(call.from_user.id)]

            cs = [c for c in filargs['eqs'] if c in db.catgs]
            scs_dict = {c: subct_ex_dict[c] if c in ex_sc
                        else subct_in_dict[c] for c in cs}
            data['scs_dict_' + str(call.from_user.id)] = \
                list(scs_dict.items())

            scs_l = ""
            j = 0
            for c in scs_dict:
                scs_l += (c + ":\n")
                j += 1
                for i, sc in enumerate(scs_dict[c]):
                    scs_l += f'\t{j}{i + 1}. {sc}\n'

    await FSMAdmin.subcatfilt.set()
    await bot.send_message(call.from_user.id,
                           "Введите номера одной или нескольких "
                           "подкатегорий из существующих выбранных "
                           "категорий через запятую "
                           f"(например: 15, 211, 36 ):\n{scs_l}")


@dp.callback_query_handler(lambda call: call.data == 'is_sorting',
                           state='*')
async def is_sorting(call: types.CallbackQuery, state: FSMContext):
    msg = ""
    if state is not None:
        async with state.proxy() as data:
            filargs = data['filter_args_' + str(call.from_user.id)]
            if filargs['sort_by'] is not None:
                params = {'Дата': 'date', "Название": 'operation_name',
                          "Цена за единицу": 'price_per_unit',
                          "Количество": 'amount',
                          "Общая стоимость": 'total',
                          "Категории": 'category',
                          "Подкатегории": 'subcategory'}
                sorters = [list(params.items())
                           [list(params.values()).index(s)][0]
                           for s in filargs['sort_by']]
                msg += "\nУже добавлена следующая сортировка:\n"
                msg += f"{', '.join(sorters)}"

    bt1 = types.InlineKeyboardButton('Сортировать',
                                     callback_data='yes_sort')
    bt2 = types.InlineKeyboardButton('Пропустить',
                                     callback_data='search')

    kb28 = types.InlineKeyboardMarkup()
    kb28.row(bt1, bt2)
    await bot.send_message(call.from_user.id,
                           f"Сортировать операции по параметрам?{msg}",
                           reply_markup=kb28)


@dp.callback_query_handler(lambda call: call.data == 'yes_sort',
                           state='*')
async def sort_it_all(call: types.CallbackQuery, state: FSMContext):
    await FSMAdmin.sort_it.set()
    params = ['Дата', "Название", "Цена за единицу", "Количество",
              "Общая стоимость", "Категории", "Подкатегории"]
    ps = ''.join([f'{i+1}. {p}\n' for i, p in enumerate(params)])
    await bot.send_message(call.from_user.id,
                           "Введите через запятую номера параметров, "
                           "по которым вы хотите "
                           "отсортировать операции. Например: 1, 3, 2 "
                           "(порядок расположения имеет значение):"
                           f"\n{ps}")


@dp.callback_query_handler(lambda call: call.data == 'search',
                           state='*')
async def search_operations(call: types.CallbackQuery,
                            state: FSMContext):
    msg = ""
    if state is not None:
        async with state.proxy() as data:
            query = data.get('search_' + str(call.from_user.id))
            if query is not None:
                msg += f"\nУже добавлен поисковой запрос: {query}\n"

    bt1 = types.InlineKeyboardButton('Искать', callback_data='yes_find')
    bt2 = types.InlineKeyboardButton("Показать результат",
                                     callback_data='show_res')

    kb29 = types.InlineKeyboardMarkup()
    kb29.row(bt1, bt2)
    await bot.send_message(call.from_user.id,
                           "Вы хотите добавить фильтр "
                           f"по имени операции?{msg}"
                           "(будут найдены все операции, "
                           "в которых есть введённая подстрока)",
                           reply_markup=kb29)


@dp.callback_query_handler(lambda call: call.data == 'yes_find',
                           state='*')
async def find_operations(call: types.CallbackQuery, state: FSMContext):
    await FSMAdmin.search.set()
    await bot.send_message(call.from_user.id,
                           "Введите поисковой запрос:")


@dp.callback_query_handler(lambda call: call.data == 'show_res',
                           state='*')
async def show_results(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        async with state.proxy() as data:
            filargs = data.get('filter_args_' + str(call.from_user.id))
            query = data.get('search_' + str(call.from_user.id))

            if filargs is not None:
                p = tuple(filargs['points']) \
                    if filargs['points'] is not None else None
                c = tuple(filargs['cols']) \
                    if filargs['cols'] is not None else None
                e = tuple(filargs['eqs']) \
                    if filargs['eqs'] is not None else None
                sb = tuple(filargs['sort_by']) \
                    if filargs['sort_by'] is not None else None
                items = db.select_operations(p, c, e, filargs['ui'],
                                             sort_by=sb)
            else:
                items = db.select_operations(ui=call.from_user.id,
                                             sort_by='date')

            if query is not None:
                items = db.search_in_list(items, query)

            if items and not data.get('del', False):
                if len(items) > 100:
                    items = items[:100]

                bt1 = types.InlineKeyboardButton('Завершить поиск',
                                                 callback_data='pass')

                kb30 = types.InlineKeyboardMarkup().add(bt1)
                await bot.send_message(call.from_user.id,
                                       "Найдено следующее:\n"
                                       f"{db.show_table(items)}",
                                       reply_markup=kb30)
            elif items and data.get('del', False):
                data['del_items_' + str(call.from_user.id)] = items
                await FSMAdmin.del_select.set()
                await bot.send_message(call.from_user.id,
                                       f"{db.show_table(items)}\n"
                                       f"Введите номера операций, "
                                       f"которые хотите удалить\nИЛИ\n"
                                       f"Отправьте нижнее "
                                       f"подчёркивание (_), "
                                       f"если хотите удалить "
                                       f"всё найденное.")
            else:
                bt1 = types.InlineKeyboardButton('Повторить поиск',
                                                 callback_data='search')
                bt2 = types.InlineKeyboardButton('Завершить поиск',
                                                 callback_data='pass')

                kb31 = types.InlineKeyboardMarkup().row(bt1, bt2)
                await bot.send_message(call.from_user.id,
                                       "По вашему запросу ничего "
                                       "не найдено.",
                                       reply_markup=kb31)
    else:
        items = db.select_operations(ui=call.from_user.id,
                                     sort_by='date')
        if items:
            if len(items) > 100:
                items = items[:100]

            bt1 = types.InlineKeyboardButton('Завершить поиск',
                                             callback_data='pass')

            kb32 = types.InlineKeyboardMarkup().add(bt1)
            await bot.send_message(call.from_user.id,
                                   "Найдено следующее:\n"
                                   f"{db.show_table(items)}",
                                   reply_markup=kb32)
        else:
            await bot.send_message(call.from_user.id,
                                   "Извините, ничего не найдено. "
                                   "Скорее всего вы ничего "
                                   "не добавляли.")


@dp.callback_query_handler(lambda call: call.data == 'delete')
async def delete_operations(call: types.CallbackQuery):
    bt1 = types.InlineKeyboardButton('Удалить всё',
                                     callback_data='delete_all')
    bt2 = types.InlineKeyboardButton('Выбрать для удаления',
                                     callback_data='select_del')
    bt3 = types.InlineKeyboardButton('Восстановить удалённое',
                                     callback_data='restore')

    kb33 = types.InlineKeyboardMarkup()
    kb33.row(bt1, bt2).add(bt3)
    await bot.send_message(call.from_user.id,
                           "Выберите, какие операции "
                           "вы хотите удалить (или восстановить)",
                           reply_markup=kb33)


@dp.callback_query_handler(lambda call: call.data == 'delete_all')
async def show_all_operations(call: types.CallbackQuery):
    items = db.select_operations(ui=call.from_user.id, sort_by='date')
    if items:
        if len(items) > 100:
            items = items[:100]

        msg = "\nВыберите номера операций для удаления " \
              "(через один пробел, например: 1 4 5 6 7 8 9 34)\n" \
              "ИЛИ\nОтправьте подчёркивание (_), чтобы удалить " \
              "всё выданное."
        await FSMAdmin.delete_it_all.set()
        await bot.send_message(call.from_user.id,
                               db.show_table(items) + msg)
    else:
        await bot.send_message(call.from_user.id,
                               "Извините, ничего не найдено. "
                               "Скорее всего вы ничего не добавляли.")


@dp.callback_query_handler(lambda call: call.data == 'restore')
async def restore_data(call: types.CallbackQuery):
    store = shelve.open('local_database\\backup_data.data')
    key = [k for k in store if k.startswith(str(call.from_user.id))]
    if len(key) == 0:
        await bot.send_message(call.from_user.id,
                               'Данных для восстановления '
                               'не нашлось :(\nВозможно вы '
                               'ничего не удаляли.')
    else:
        key = key[0]
        _, d = key.split('_')
        dat = store[key]
        store.close()
        if len(dat) > 2:
            example = f"{' | '.join(map(str, dat[0][1:]))}\n" \
                      f"{' | '.join(map(str, dat[1][1:]))}\n"
            msg = f"Найдено резервное сохранение от {d}:" \
                  f"\n\n{example}...\nВы хотите его восстановить?"
        if 0 < len(dat) <= 2:
            example = f"{' | '.join(map(str, dat[0][1:]))}\n"
            example += "" if len(dat) == 1 \
                else f"{' | '.join(map(str, dat[1][1:]))}\n"
            msg = f"Найдено резервное сохранение от {d}:" \
                  f"\n\n{example}Вы хотите его восстановить?"

        bt1 = types.InlineKeyboardButton('Восстановить',
                                         callback_data='backup_yes')
        bt2 = types.InlineKeyboardButton('Не восстанавливать',
                                         callback_data='pass1')

        kb34 = types.InlineKeyboardMarkup()
        kb34.add(bt1).add(bt2)
        await bot.send_message(call.from_user.id, msg,
                               reply_markup=kb34)


@dp.callback_query_handler(lambda call: call.data == 'backup')
async def restore_backup(call: types.CallbackQuery):
    store = shelve.open('local_database\\backup_data.data')
    key = [k for k in store if k.startswith(str(call.from_user.id))]
    key = key[0]
    dat = store[key]
    for item in dat:
        db.add_operation(item)
        await bot.send_message(call.from_user.id,
                               f"Добавлено: {item[2]}")
    else:
        await bot.send_message(call.from_user.id,
                               "Все данные успешно восстановлены!")


@dp.callback_query_handler(lambda call: call.data.startswith('pass'),
                           state='*')
async def pass_action(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        await state.finish()

    b = db.show_balance(call.from_user.id)

    buttons = [
        types.InlineKeyboardButton('Добавить QR-код',
                                   callback_data='qr'),
        types.InlineKeyboardButton('Добавить самостоятельно',
                                   callback_data='hand_enter'),
        types.InlineKeyboardButton('Посмотреть операции',
                                   callback_data='show_what'),
        types.InlineKeyboardButton('Удаление',
                                   callback_data='delete')
    ]

    kb1 = types.InlineKeyboardMarkup()
    kb1.add(buttons[0]).add(buttons[1]).add(buttons[2])
    kb1.add(buttons[3])

    msg = f"Доброго времени суток, {call.from_user.full_name}.\n\n" \
          f"\tВаш баланс: {b}\n\nВыберите одно из следующих действий."
    await bot.send_message(call.from_user.id, msg, reply_markup=kb1)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=setup_on)
