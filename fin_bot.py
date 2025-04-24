import os
import pickle
import shelve
import sys
import time
from collections import deque
from datetime import date

from aiogram import Bot, Dispatcher, exceptions, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import (InlineKeyboardButton, InlineKeyboardMarkup, 
                                    KeyboardButton, ReplyKeyboardMarkup)

import local_database.fb_sql as db
from parser.fb_parser import CHECK


__version__ = '1.1'

clf_ex, clf_in = pickle.load(open('data_define/categorizer.data', 'rb'))
ct_ex_list, ct_in_list, subct_ex_dict, subct_in_dict = pickle.load(
    open('local_database/cts_lists.data', 'rb'))
# store = shelve.open('local_database/backup_data.data')


bot = Bot(os.getenv('TOKEN'))
dp = Dispatcher(storage=MemoryStorage())


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
@dp.message(commands=['start'])
async def start_bot(message: types.Message, state: FSMContext):
    if state is not None:
        await state.clear()

    b = db.show_balance(message.from_user.id)

    buttons = [
        [InlineKeyboardButton(text='Добавить QR-код', callback_data='qr')],
        [InlineKeyboardButton(text='Добавить самостоятельно', 
                              callback_data='hand_enter')],
        [InlineKeyboardButton(text='Посмотреть операции', callback_data='show_what')],
        [InlineKeyboardButton(text='Удаление', callback_data='delete')]
    ]
    kb1 = InlineKeyboardMarkup(inline_keyboard=buttons)

    msg = f"Доброго времени суток, {message.from_user.full_name}.\n\n" \
          f"\tВаш баланс: {b}\n\nВыберите одно из следующих действий."
    await bot.send_message(message.from_user.id, msg, reply_markup=kb1)


@dp.message(commands=['help'])
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
@dp.message(state=FSMAdmin.qr)
async def load_qr(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ul = data.get(f'items_{message.from_user.id}')
    if ul is None:
        t = CHECK(message.text)
        await state.set_data({f'qr_{message.from_user.id}': message.text,
                              f'date_{message.from_user.id}': t.date()})
        print((await state.get_data())[f'date_{message.from_user.id}'])
        
        li = []
        try:
            li = t.get_list()
        except Exception as e:
            await bot.send_message(
                message.from_user.id,
                'Похоже, произошла непредвиденная ошибка:\n'
                + ' '.join(map(str, e.args))
                + "\n\nПопробуйте повторить то же самое через пару-тройку дней. "
                  "Обычно за это время данные чеков успевают появиться.")

        if not li:
            bt1 = InlineKeyboardButton(text='Ввести самостоятельно',
                                       callback_data='hand_enter_qr')
            bt2 = InlineKeyboardButton(text='Пропустить', callback_data='pass1')
            kb2 = InlineKeyboardMarkup(inline_keyboard=[[bt1], [bt2]])
            await message.answer('Информация с этого чека не была загружена.',
                                 reply_markup=kb2)
        else:
            for i, item in enumerate(li):
                li[i] = [item[0], *map(float, item[1:])]

            await state.set_data({f'items_{message.from_user.id}': deque(li)})

    elif len(ul) == 0:
        await state.clear()
        await bot.send_message(
                message.from_user.id,
                'Вся информация по чеку была успешно введена!',
                reply_markup=types.ReplyKeyboardRemove())

    if state is not None and (await state.get_data())[
       f'items_{message.from_user.id}']:
        oper = (await state.get_data())[f'items_{message.from_user.id}'].popleft()
        await state.set_data({f'oper_{message.from_user.id}': oper})
        print(oper)

        bt1 = KeyboardButton(text='Расход')
        bt2 = KeyboardButton(text='Доход')
        kb3 = ReplyKeyboardMarkup(keyboard=[[bt1], [bt2]],
                                  resize_keyboard=True,
                                  one_time_keyboard=True)

        await state.set_state(FSMAdmin.oper_type)
        await bot.send_message(message.from_user.id,
                                   f'Выберите тип для операции:\n{oper[0]}',
                                   reply_markup=kb3)


@dp.message(state=FSMAdmin.heqr)
async def hand_enter_qr_post(message: types.Message, state: FSMContext):
    data = await state.get_data()
    d = data.get(f'date_{message.from_user.id}')
    if d is None:
        await state.set_data({
            f'date_{message.from_user.id}': 
                date.today().isoformat() 
                + f'-{time.localtime().tm_hour:0>2s}' 
                + f'-{time.localtime().tm_min:0>2s}'
        })
        
    ul = data.get(f'items_{message.from_user.id}')
    if ul is None:
        s = message.text
        oper_list = []
        if '\n' in s:
            items = s.split('\n')
            for item in items:
                if item:
                    item = item.split('   ')
                    oper_list.append([item[0], *map(float, item[1:])])
        else:
            item = s.split('   ')
            oper_list.append([item[0], *map(float, item[1:])])
            await state.set_data({f'items_{message.from_user.id}': deque(oper_list)})
            
    elif len(ul) == 0:
        await state.clear()
        await bot.send_message(
            message.from_user.id,
            'Вся информация по чеку была успешно введена!',
            reply_markup=types.ReplyKeyboardRemove()
        )

    if state is not None:
        oper = (await state.get_data())[f'items_{message.from_user.id}'].popleft()
        await state.set_data({f'oper_{message.from_user.id}': oper})

        bt1 = KeyboardButton(text='Расход')
        bt2 = KeyboardButton(text='Доход')
        kb4 = ReplyKeyboardMarkup(keyboard=[[bt1], [bt2]], 
                                  resize_keyboard=True,
                                  one_time_keyboard=True)
        await state.set_state(FSMAdmin.oper_type)
        await bot.send_message(message.from_user.id,
                               f'Выберите тип для операции:\n{oper[0]}',
                               reply_markup=kb4)


@dp.message(state=FSMAdmin.hand_enter)
async def add_operation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    d = data.get(f'date_{message.from_user.id}')
    if d is None:
        await state.set_data({
            f'date_{message.from_user.id}':
                date.today().isoformat()
                + f'-{time.localtime().tm_hour:0>2s}'
                + f'-{time.localtime().tm_min:0>2s}'
        })

    ul = data.get(f'items_{message.from_user.id}')
    if ul is None:
        s = message.text
        oper_list = []
        if '\n' in s:
            items = s.split('\n')
            for item in items:
                if item:
                    item = item.split('   ')
                    oper_list.append([item[0], *map(float, item[1:])])
        else:
            item = s.split('   ')
            oper_list.append([item[0], *map(float, item[1:])])

        await state.set_data({f'items_{message.from_user.id}': deque(oper_list)})
    elif len(ul) == 0:
        await state.clear()
        await bot.send_message(
                message.from_user.id,
                'Вся введённая информация была успешно введена!',
                reply_markup=types.ReplyKeyboardRemove())

    if state is not None:
        oper = (await state.get_data())[f'items_{message.from_user.id}'].popleft()
        await state.set_data({f'oper_{message.from_user.id}': oper})

        bt1 = KeyboardButton(text='Расход')
        bt2 = KeyboardButton(text='Доход')
        kb5 = ReplyKeyboardMarkup(keyboard=[[bt1], [bt2]], resize_keyboard=True)
        await state.set_state(FSMAdmin.oper_type)
        await bot.send_message(message.from_user.id,
                                   f'Выберите тип для операции:\n{oper[0]}',
                                   reply_markup=kb5)


@dp.message(state=FSMAdmin.oper_type)
async def oper_type(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if data.get(f'oper_type_{message.from_user.id}') is None:
        await state.set_data({f'oper_type_{message.from_user.id}': message.text})
        data = await state.get_data()

    msg = f"Текущие введённые данные:\n{data[f'oper_{message.from_user.id}'][0]}"
    if data[f'oper_type_{message.from_user.id}'] == 'Доход':
        if data.get(f'ct_{message.from_user.id}') is None:
            ct = clf_in.predict([data[f'oper_{message.from_user.id}'][0]])[0]
            await state.set_data({f'ct_{message.from_user.id}': ct})
            msg = (f"Для операции {data[f'oper_{message.from_user.id}'][0]} "
                   f"определена категория {ct}.\nЕсли категория бала "
                   f"определена верно, нажмите Установить подкатегорию.\n"
                   f"Если хотите изменить её изменить, "
                   f"нажмите Изменить категорию или Далее.")

        if message.text.isdigit():
            try:
                await state.set_data({
                    f'ct_{message.from_user.id}': ct_in_list[int(message.text) - 1]
                })
            except IndexError:
                await bot.send_message(message.from_user.id,
                                       "Неверно введена цифра, попробуйте снова.")

        msg += f"{data[f'ct_{message.from_user.id}']}"

        bt1 = InlineKeyboardButton(text='Изменить категорию',
                                   callback_data='change_cat')
        buttons = [[bt1]]

        ct = data.get(f'ct_{message.from_user.id}')
        if ct is not None:
            msg += f"   {ct}."

        subct = data.get(f'subct_{message.from_user.id}')
        if subct is not None:
            msg += f"   {subct}."
            bt2 = InlineKeyboardButton(text='Установить подкатегорию',
                                       callback_data='set_subcat')
            buttons.append([bt2])
        elif subct is None \
                and data[f'ct_{message.from_user.id}'] \
                in subct_in_dict.keys():
            bt2 = InlineKeyboardButton(text='Установить подкатегорию',
                                       callback_data='set_subcat')
            buttons.append([bt2])
        
        bt3 = InlineKeyboardButton(text='Далее', callback_data='add_item')
        buttons.append([bt3])
        kb6 = InlineKeyboardMarkup(inline_keyboard=buttons)
        await bot.send_message(message.from_user.id, msg, reply_markup=kb6)

    if data[f'oper_type_{message.from_user.id}'] == 'Расход':
        if data.get(f'ct_{message.from_user.id}') is None:
            ct = clf_ex.predict([data[f'oper_{message.from_user.id}'][0]])[0]
            await state.set_data({f'ct_{message.from_user.id}': ct})

            item = data[f'oper_{message.from_user.id}']
            if item[1] >= 0:
                item = [item[0], item[1] * -1,
                        item[2], item[3] * -1]
            await state.set_data({f'oper_{message.from_user.id}': item})

            msg = "Для операции " \
                f"{data[f'oper_{message.from_user.id}'][0]} " \
                f"определена категория \"{ct}\".\nЕсли категория " \
                "бала определена верно, нажмите " \
                "Установить подкатегорию.\nЕсли хотите изменить " \
                "её, нажмите Изменить категорию."

        if message.text.isdigit():
            try:
                await state.set_data({f'ct_{message.from_user.id}':
                                          ct_ex_list[int(message.text) - 1]})
            except IndexError:
                await bot.send_message(message.from_user.id,
                                       "Неверно введена цифра, попробуйте снова.")

        ct = data.get(f'ct_{message.from_user.id}')
        if ct is not None:
            msg += f"   {ct}"

        subct = data.get(f'subct_{message.from_user.id}')
        if subct is not None:
            msg += f"   {subct}"

        bt1 = InlineKeyboardButton(text='Изменить категорию',
                                   callback_data='change_cat')
        bt2 = InlineKeyboardButton(text='Установить подкатегорию',
                                   callback_data='set_subcat')
        bt3 = InlineKeyboardButton(text='Далее', callback_data='add_item')
        kb7 = InlineKeyboardMarkup(inline_keyboard=[[bt1], [bt2], [bt3]])
        await bot.send_message(message.from_user.id, msg, reply_markup=kb7)


@dp.message(state=FSMAdmin.set_subcat)
async def set_subcategory(message: types.Message, state: FSMContext):
    data = await state.get_data()
    o_t = data[f'oper_type_{message.from_user.id}']
    item = data[f'oper_{message.from_user.id}']
    ct = data[f'ct_{message.from_user.id}']
    if message.text.isdigit():
        if o_t == 'Доход':
            await state.set_data({f'subct_{message.from_user.id}':
                                      subct_in_dict[ct][int(message.text) - 1]})

        if o_t == 'Расход':
            await state.set_data({f'subct_{message.from_user.id}':
                                      subct_ex_dict[ct][int(message.text) - 1]})

    if message.text.replace(' ', '').isalpha():
        await state.set_data({f'subct_{message.from_user.id}': message.text})

    if o_t == 'Доход':
        msg = (f"Текущие введённые данные:\n"
               f"{item[0]}   {item[1]}   {item[2]}   {item[3]}   {ct}   "
               f"{data[f'subct_{message.from_user.id}']}")

    if o_t == 'Расход':
        msg = (f"Текущие введённые данные:\n{item[0]}   {item[1] * -1}   "
               f"{item[2]}   {item[3] * -1}   {ct}   "
               f"{data[f'subct_{message.from_user.id}']}")

    bt1 = InlineKeyboardButton(text='Изменить категорию',
                               callback_data='change_cat')
    bt2 = InlineKeyboardButton(text='Установить подкатегорию',
                               callback_data='set_subcat')
    bt3 = InlineKeyboardButton(text='Далее', callback_data='add_item')

    kb8 = InlineKeyboardMarkup(inline_keyboard=[[bt1], [bt2], [bt3]])
    await state.set_state(FSMAdmin.oper_type)
    await bot.send_message(message.from_user.id, msg, reply_markup=kb8)


@dp.message(state=FSMAdmin.add_operation)
async def add_operation(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text == 'Добавить операцию':
        ui = message.from_user.id
        date_ = data[f'date_{message.from_user.id}']
        name = data[f'oper_{message.from_user.id}'][0]
        price = data[f'oper_{message.from_user.id}'][1:]
        if data[f'oper_type_{message.from_user.id}']  == 'Расход' and price[0] >= 0:
            price[0] = price[0] * -1
            price[2] = price[2] * -1

        ct = data[f'ct_{message.from_user.id}']
        subct = data.get(f'subct_{message.from_user.id}')
        operation = (ui, date_, name, *price, ct, subct)
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
            await state.update_data({f'ct_{message.from_user.id}': None})
            # del data[f'ct_{message.from_user.id}']
            if data.get(f'subct_{message.from_user.id}') is not None:
                await state.update_data({f'subct_{message.from_user.id}': None})
                # del data[f'subct_{message.from_user.id}']

            if data.get(f'qr_{message.from_user.id}') is None:
                await state.set_state(FSMAdmin.hand_enter)
            else:
                await state.set_state(FSMAdmin.qr)

        if not added and added is not None:
            bt1 = InlineKeyboardButton(text='Прибавить',
                                       callback_data='update_yes')
            bt2 = InlineKeyboardButton(text='Пропустить',
                                       callback_data='update_no')
            kb9 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
            await bot.send_message(
                message.from_user.id,
                f'Такая операция ({date_}   {name}   '
                f'{price[0]}) уже существует.\n'
                'Вы хотите прибавить введённые данные '
                'к уже существующим?\n'
                'Если нет, то нажмите Пропустить '
                'и отправьте любое сообщение.', reply_markup=kb9)
        elif added is not None:
            qr = data.get(f'qr_{message.from_user.id}')
            with open('data_define/data_set_in.txt', 'a', encoding='utf-8') as f:
                f.write(name + ' @ ' + ct + '\n')

            await bot.send_message(
                message.from_user.id,
                f'Операция {date_}   {name}   '
                f'{price[0]} успешно добавлена!\n'
                'Отправьте любое сообщение, чтобы продолжить.',
                reply_markup=types.ReplyKeyboardRemove()
            )
            
            await state.update_data({f'ct_{message.from_user.id}': None})
            # del data[f'ct_{message.from_user.id}']
            if data.get(f'subct_{message.from_user.id}') is not None:
                await state.update_data({f'subct_{message.from_user.id}': None})
                # del data[f'subct_{message.from_user.id}']

            if qr is None:
                await state.set_state(FSMAdmin.hand_enter)
            else:
                await state.set_state(FSMAdmin.heqr)

    if message.text == 'Назад к вводу данных':
        qr = data.get(f'qr_{message.from_user.id}')
        
        await state.update_data({f'ct_{message.from_user.id}': None})
        # del data[f'ct_{message.from_user.id}']
        if data.get(f'subct_{message.from_user.id}') is not None:
            await state.update_data({f'subct_{message.from_user.id}': None})
            # del data[f'subct_{message.from_user.id}']

        if qr is None:
            await state.set_state(FSMAdmin.hand_enter)
        else:
            await state.set_state(FSMAdmin.qr)


@dp.message(state=FSMAdmin.gsd_for)
async def graphs_date_for(message: types.Message, state: FSMContext):
    args = {"День": "day", "Неделя": "week", "Месяц": "month", "Год": "year"}
    
    date_ = db.date_for(args[message.text])
    await state.set_data({'graphs_data': db.select_operations(
        date_, 'date', ui=message.from_user.id, sort_by='date')})

    bt1 = InlineKeyboardButton(text='Вернуться назад',
                               callback_data='graphs_period')
    kb10 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           "Установлен следующий промежуток времени: "
                           f"{date_[0]} до {date_[1]}.",
                           reply_markup=kb10)


@dp.message(state=FSMAdmin.gsd_current)
async def graphs_date_current(message: types.Message,
                              state: FSMContext):
    args = {"День": "day", "Неделя": "week", "Месяц": "month", "Год": "year"}
    
    date_ = db.date_current(args[message.text])
    await state.set_data({'graphs_data': db.select_operations(
        date_, 'date', ui=message.from_user.id, sort_by='date')})

    bt1 = InlineKeyboardButton(text='Вернуться назад',
                               callback_data='graphs_period')
    kb10 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           "Установлен следующий промежуток времени: "
                           f"{date_[0]} до {date_[1]}.",
                           reply_markup=kb10)


@dp.message(state=FSMAdmin.gsd_other)
async def graphs_date_other(message: types.Message, state: FSMContext):
    try:
        l1, l2 = message.text.split('   ')
    except ValueError:
        await state.set_state(FSMAdmin.gsd_other)
        await bot.send_message(message.from_user.id,
                          "Вы ввели неправильные данные. Попробуйте ещё раз")

    date_ = (l1, l2)
    await state.set_data({'graphs_data': db.select_operations(
        date_, 'date', ui=message.from_user.id, sort_by='date')})

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='graphs_period')
    kb10 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           "Установлен следующий промежуток времени: "
                           f"{l1} до {l2}.",
                           reply_markup=kb10)


@dp.message(state=FSMAdmin.set_graphs)
async def set_all_graphs(message: types.Message, state: FSMContext):
    if message.text == 'По дням':
        await state.set_data({'summary': 'day'})
    elif message.text == 'По месяцам':
        await state.set_data({'summary': 'month'})
    elif message.text == 'По годам':
        await state.set_data({'summary': 'year'})

    bt1 = InlineKeyboardButton(text='Далее', callback_data='set_ct_dgm')
    kb11 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f'Установлено суммирование {message.text.lower()}.',
                           reply_markup=kb11)


@dp.message(state=FSMAdmin.set_dgm)
async def set_diagrams(message: types.Message, state: FSMContext):
    cs = (await state.get_data())['dgm_cts']
    if message.text[0].isdigit():
        try:
            if message.text.isdigit():
                cs = [cs[int(message.text) - 1]]
            else:
                cs = [cs[int(i) - 1] for i in message.text.split(', ')]
        except IndexError:
            await bot.send_message(message.from_user.id,
                                   'Извините, но вы неправильно '
                                   'ввели номера категорий, '
                                   'Попробуйте ещё раз.')
        await state.set_data({'dgm_cts': cs})
        
    if message.text == '_':
        await state.set_data({'dgm_cts': cs})
    if message.text == '-':
        await state.set_data({'dgm_cts': None})

    if sys.exc_info()[0] is not IndexError:
        bt1 = InlineKeyboardButton(text='Показать', callback_data='graph_show')
        kb12 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
        await bot.send_message(message.from_user.id,
                               'Настройки графиков завершены!',
                               reply_markup=kb12)


@dp.message(state=FSMAdmin.date_for)
async def choose_date_for(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs =  dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    args = {"День": "day", "Неделя": "week", "Месяц": "month", "Год": "year"}
    if filargs['points'] is None and filargs['cols'] is None:
        filargs['points'] = db.date_for(args[message.text])
        filargs['cols'] = ['date']
    elif 'date' not in filargs['cols']:
        filargs['points'].extend(db.date_for(args[message.text]))
        filargs['cols'].append('date')

    elif 'date' in filargs['cols']:
        i = [i for i, a in enumerate(filargs['points']) if '-' in a]
        filargs['points'][i[0]:i[1] + 1] = db.date_for(args[message.text])

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})
    l1, l2 = db.date_for(args[message.text])

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb10 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f"Фильтр по дате от {l1} до {l2} установлен.",
                           reply_markup=kb10)


@dp.message(state=FSMAdmin.date_current)
async def choose_date_current(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    args = {"День": "day", "Неделя": "week", "Месяц": "month", "Год": "year"}
    if filargs['points'] is None and filargs['cols'] is None:
        filargs['points'] = db.date_current(args[message.text])
        filargs['cols'] = ['date']

    elif 'date' not in filargs['cols']:
        filargs['points'].extend(db.date_current(args[message.text]))
        filargs['cols'].append('date')

    elif 'date' in filargs['cols']:
        i = [i for i, a in enumerate(filargs['points']) if '-' in a]
        filargs['points'][i[0]:i[1] + 1] = db.date_current(args[message.text])

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})
    l1, l2 = db.date_current(args[message.text])

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb11 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(
        message.from_user.id,
        f"Фильтр по дате от {l1} до {l2} установлен.",
        reply_markup=kb11)


@dp.message(state=FSMAdmin.date_other)
async def choose_date_other(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    try:
        l1, l2 = message.text.split('   ')
    except ValueError:
        await state.set_state(FSMAdmin.date_other)
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

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb12 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f"Фильтр по дате от {l1} до {l2} установлен.",
                           reply_markup=kb12)


@dp.message(state=FSMAdmin.amount)
async def choose_amount(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    try:
        l1, l2 = message.text.split('   ')
        l1, l2 = float(l1), float(l2)
    except ValueError:
        await state.set_state(FSMAdmin.amount)
        await bot.send_message(message.from_user.id,
                               "Вы ввели неправильные данные. Попробуйте ещё раз")

    if filargs['points'] is None and filargs['cols'] is None:
        filargs['points'] = [l1, l2]
        filargs['cols'] = ['amount']

    elif 'amount' not in filargs['cols']:
        filargs['points'].extend([l1, l2])
        filargs['cols'].append('amount')

    elif 'amount' in filargs['cols']:
        i = filargs['cols'].index('amount')
        filargs['points'][i*2:i*2 + 1] = [l1, l2]

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb13 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(
        message.from_user.id,
        f"Фильтр по количеству от {l1} до {l2} установлен.",
        reply_markup=kb13)


@dp.message(state=FSMAdmin.ppu)
async def choose_ppu(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    try:
        l1, l2 = message.text.split('   ')
        l1, l2 = float(l1), float(l2)
    except ValueError:
        await state.set_state(FSMAdmin.amount)
        await bot.send_message(message.from_user.id,
                               "Вы ввели неправильные данные. Попробуйте ещё раз")

    if filargs['points'] is None and filargs['cols'] is None:
        filargs['points'] = [l1, l2]
        filargs['cols'] = ['price_per_unit']

    elif 'price_per_unit' not in filargs['cols']:
        filargs['points'].extend([l1, l2])
        filargs['cols'].append('price_per_unit')

    elif 'price_per_unit' in filargs['cols']:
        i = filargs['cols'].index('price_per_unit')
        filargs['points'][i * 2:i * 2 + 1] = [l1, l2]

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb14 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(
        message.from_user.id,
        f"Фильтр по цене за единицу от {l1} до {l2} установлен.",
        reply_markup=kb14)


@dp.message(state=FSMAdmin.total)
async def choose_total(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    try:
        l1, l2 = message.text.split('   ')
        l1, l2 = float(l1), float(l2)
    except ValueError:
        await state.set_state(FSMAdmin.total)
        await bot.send_message(message.from_user.id,
                               "Вы ввели неправильные данные. Попробуйте ещё раз")

    if filargs['points'] is None and filargs['cols'] is None:
        filargs['points'] = [l1, l2]
        filargs['cols'] = ['total']

    elif 'total' not in filargs['cols']:
        filargs['points'].extend([l1, l2])
        filargs['cols'].append('total')

    elif 'total' in filargs['cols']:
        i = filargs['cols'].index('total')
        filargs['points'][i * 2:i * 2 + 1] = [l1, l2]

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='select')
    kb15 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f"Фильтр по общей стоимости от {l1} до {l2} установлен.",
                           reply_markup=kb15)


@dp.message(state=FSMAdmin.catfilt)
async def ct_flt(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'], None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    if ', ' in message.text:
        cts = [db.catgs[int(i) - 1] for i in message.text.split(', ')]
    else:
        cts = [db.catgs[int(message.text) - 1]]

    if filargs['eqs'] is None:
        filargs['eqs'] = cts
    else:
        filargs['eqs'] = list(set(filargs['eqs']) | set(cts))

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})
    cts = ', '.join(cts)

    bt1 = InlineKeyboardButton(text='Вернуться назад',
                                     callback_data='ct_filters')
    kb16 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           "Вы добавили фильтры по категориям:\n"
                           f"{cts}",
                           reply_markup=kb16)


@dp.message(state=FSMAdmin.subcatfilt)
async def subct_flt(message: types.Message, state: FSMContext):
    data = await state.get_data()
    filargs = data[f'filter_args_{message.from_user.id}']
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

    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    scs = ', '.join(scs)
    bt1 = InlineKeyboardButton(text='Вернуться назад', callback_data='ct_filters')
    kb17 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           "Вы добавили фильтры по подкатегориям:\n"
                           f"{scs}",
                           reply_markup=kb17)


@dp.message(state=FSMAdmin.sort_it)
async def sort_it(message: types.Message, state: FSMContext):
    filargs = (await state.get_data()).get(f'filter_args_{message.from_user.id}')
    if filargs is None:
        filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'],
                                None)
        filargs['ui'] = message.from_user.id
        await state.set_data({f'filter_args_{message.from_user.id}': filargs})
    
    params = {'Дата': 'date',
              "Название": 'operation_name',
              "Цена за единицу": 'price_per_unit',
              "Количество": 'amount',
              "Общая стоимость": 'total',
              "Категории": 'category',
              "Подкатегории": 'subcategory'}
    param_items = list(params.items())

    sorters = [param_items[int(i) - 1][1] for i in message.text.split(', ')]
    filargs['sort_by'] = sorters
    await state.set_data({f'filter_args_{message.from_user.id}': filargs})

    sorters = [list(params.items())[list(params.values()).index(s)][0]
               for s in filargs['sort_by']]

    bt1 = InlineKeyboardButton(text='Назад', callback_data='is_sorting')
    kb18 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f"Добавлена сортировка:\n{', '.join(sorters)}",
                           reply_markup=kb18)


@dp.message(state=FSMAdmin.search)
async def search_all(message: types.Message, state: FSMContext):
    query = message.text
    await state.set_data({f'search_{message.from_user.id}': query})

    bt1 = InlineKeyboardButton(text='Назад', callback_data='search')
    kb19 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
    await bot.send_message(message.from_user.id,
                           f"Добавлен поисковой запрос: {query}",
                           reply_markup=kb19)


@dp.message(state=FSMAdmin.delete_it_all)
async def del_it_all(message: types.Message, state: FSMContext):
    items = db.select_operations(ui=message.from_user.id, sort_by='date')

    save = []
    indexes = map(int, message.text.split()) if message.text != '_' \
        else range(len(items))

    for i in indexes:
        try:
            save.append(items[i-1])
            db.delete_operation(items[i-1])
        except IndexError:
            continue

    store = shelve.open('local_database/backup_data.data')
    first_key = [k for k in store if k.startswith(str(message.from_user.id))]
    key = (f'{message.from_user.id}_' + date.today().isoformat() 
           + f'-{time.localtime().tm_hour:0>2s}'
           + f'-{time.localtime().tm_min:0>2s}')
    store[key] = save
    if first_key:
        del store[first_key[0]]

    await state.clear()
    await bot.send_message(message.from_user.id,
                           f"{len(save)} выбранных вами операций "
                           "были успешно удалены. Если вы что-то "
                           "удалили по ошибке, воспользуйтесь кнопкой"
                           " \"Восстановить удалённое\" "
                           "в главном меню, чтобы вернуть всё, "
                           "что вы удаляли в последний раз.")


@dp.message(state=FSMAdmin.del_select)
async def del_selected(message: types.Message, state: FSMContext):
    items = (await state.get_data())[f'del_items_{message.from_user.id}']
    save = []
    indexes = map(int, message.text.split()) if message.text != '_' \
        else range(len(items))

    for i in indexes:
        try:
            save.append(items[i - 1])
            db.delete_operation(items[i - 1])
        except IndexError:
            continue

    store = shelve.open('local_database/backup_data.data')
    first_key = [k for k in store if k.startswith(str(message.from_user.id))]
    key = (f'{message.from_user.id}_' + date.today().isoformat() 
           + f'-{time.localtime().tm_hour:0>2s}'
           + f'-{time.localtime().tm_min:0>2s}')
    store[key] = save
    if first_key:
        del store[first_key[0]]

    await state.clear()
    await bot.send_message(message.from_user.id,
                           f"{len(save)} выбранных вами операций "
                           "были успешно удалены. Если вы что-то "
                           "удалили по ошибке, воспользуйтесь кнопкой"
                           " \"Восстановить удалённое\" "
                           "в главном меню, чтобы вернуть всё, "
                           "что вы удаляли в последний раз.")


# Обработчики колбэков от инлайнровых кнопок
@dp.callback_query(lambda call: call.data == 'qr')
async def add_qr_code(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.qr)
    await bot.send_message(call.from_user.id,
                           'Вставьте текст отсканированного QR-кода и ждите чуда:')


@dp.callback_query(lambda call: call.data == 'hand_enter')
async def add_qr_code(call: types.CallbackQuery, state: FSMContext):
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
    await state.set_state(FSMAdmin.hand_enter)


@dp.callback_query(lambda call: call.data == 'hand_enter_qr', state=FSMAdmin.qr)
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
    await state.set_state(FSMAdmin.heqr)


@dp.callback_query(lambda call: call.data == 'change_cat',
                   state=[FSMAdmin.oper_type, FSMAdmin.set_subcat])
async def change_category(call: types.CallbackQuery, state: FSMContext):
    # async with state.proxy() as data:
    o_t = (await state.get_data())[f'oper_type_{call.from_user.id}']

    await state.set_state(FSMAdmin.oper_type)

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


@dp.callback_query(lambda call: call.data == 'set_subcat',
                   state=[FSMAdmin.oper_type, FSMAdmin.set_subcat])
async def set_subcat(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    o_t = data[f'oper_type_{call.from_user.id}']
    await state.set_state(FSMAdmin.set_subcat)

    ct = data[f'ct_{call.from_user.id}']
    if o_t == 'Расход':
        t_ex = ''.join([f'\n{i + 1}. {c}' for i, c in enumerate(subct_ex_dict[ct])])

    if o_t == 'Доход':
        t_ex = ''.join([f'\n{i + 1}. {c}' for i, c in enumerate(subct_in_dict[ct])])
    await bot.send_message(call.from_user.id,
                           "Выберите номер одной из подкатегорий "
                           "в соответствии с выбранной категорией:"
                           + t_ex + "\n\nИли введите свою "
                                    "собственную подкатегорию.",
                           reply_markup=types.ReplyKeyboardRemove())


@dp.callback_query(lambda call: call.data == 'add_item',
                   state=[FSMAdmin.set_subcat, FSMAdmin.oper_type])
async def add_item(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    o_t = data[f'oper_type_{call.from_user.id}']
    date_ = data[f'date_{call.from_user.id}']
    name = data[f'oper_{call.from_user.id}'][0]
    price = data[f'oper_{call.from_user.id}'][1:]
    ct = data['ct_' + str(call.from_user.id)]
    subct = data.get(f'subct_{call.from_user.id}')
    if o_t == 'Расход':
        price[0] *= -1
        price[2] *= -1
        
    msg = "Информация об операции была введена со следующими " \
          f"данными:\n{date_}   {name}   {price[0] * -1}   " \
          f"{price[1]}   {price[2] * -1}   {ct}   {subct}"

    bt1 = KeyboardButton(text='Добавить операцию')
    bt2 = KeyboardButton(text='Назад к вводу данных')
    kb20 = ReplyKeyboardMarkup(keyboard=[[bt1], [bt2]],
                               resize_keyboard=True, one_time_keyboard=True)
    await bot.send_message(call.from_user.id, msg, reply_markup=kb20)
    await state.set_state(FSMAdmin.add_operation)


@dp.callback_query(lambda call: call.data.startswith('update'),
                   state=FSMAdmin.add_operation)
async def update_operation(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if call.data.endswith('yes'):
        ui = call.from_user.id
        date_ = data[f'date_{call.from_user.id}']
        name = data[f'oper_{call.from_user.id}'][0]
        price = data[f'oper_{call.from_user.id}'][1:]
        operation = (ui, date_, name, *price)
        db.update_operation(operation)
        await bot.send_message(call.from_user.id,
                               'Информация об операции была успешно обновлена!',
                               reply_markup=types.ReplyKeyboardRemove())

        await state.update_data({f'ct_{call.from_user.id}': None})
        if data.get(f'subct_{call.from_user.id}') is not None:
            await state.update_data({f'subct_{call.from_user.id}': None})

        qr = data.get(f'qr_{call.from_user.id}')
        if qr is None:
            await state.set_state(FSMAdmin.hand_enter)
        else:
            await state.set_state(FSMAdmin.heqr)

    elif call.data.endswith('no'):
        await state.update_data({f'ct_{call.from_user.id}': None})
        if data.get(f'subct_{call.from_user.id}') is not None:
            await state.update_data({f'subct_{call.from_user.id}': None})

        qr = data.get(f'qr_{call.from_user.id}')
        if qr is None:
            await state.set_state(FSMAdmin.hand_enter)
        else:
            await state.set_state(FSMAdmin.qr)


@dp.callback_query(lambda call: call.data == 'show_what')
async def what_to_show(call: types.CallbackQuery):
    if db.select_operations(ui=call.from_user.id):
        msg = "Выберите: показать графики или список операций."

        bt1 = InlineKeyboardButton(text='Показать графики',
                                   callback_data='show_graphs')
        bt2 = InlineKeyboardButton(text='Показать список',
                                   callback_data='show_operations')
        kb21 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
        await bot.send_message(call.from_user.id, msg, reply_markup=kb21)
    else:
        msg = ("Я, конечно, извиняюсь, но у вас ничего нет.\n"
               "Вы либо ничего не добавляли, либо всё удалили.")
        await bot.send_message(call.from_user.id, msg)


@dp.callback_query(lambda call: call.data == 'show_graphs')
async def show_graphs(call: types.CallbackQuery):
    msg = "Выберите: показать на графике все операции или настроить параметры."

    bt1 = InlineKeyboardButton(text='Настроить', callback_data='graphs_period')
    bt2 = InlineKeyboardButton(text='Показать всё', callback_data='show_all_graphs')
    kb21 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
    await bot.send_message(call.from_user.id, msg, reply_markup=kb21)


@dp.callback_query(lambda call: call.data == 'show_operations')
async def show_opertations(call: types.CallbackQuery):
    msg = ("Выберите: посмотреть всё (если данных много, "
           "то сообщение сократиться до первых 45 строк) "
           "или найти операции по определённым "
           "значениям параметров.")

    bt1 = InlineKeyboardButton(text='Поиск по фильтрам', callback_data='select')
    bt2 = InlineKeyboardButton(text='Показать всё', callback_data='show_all')
    kb21 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
    await bot.send_message(call.from_user.id, msg, reply_markup=kb21)


@dp.callback_query(lambda call: call.data.startswith('show_all'))
async def show_all_operations(call: types.CallbackQuery):
    items = db.select_operations(ui=call.from_user.id, sort_by='date')
    if call.data.endswith('graphs') and items:
        data = db.data_summary(items)
        file = db.make_main_report(data, call.from_user.id)
        await bot.send_photo(call.from_user.id, types.InputFile(file))

    elif items:
        if len(items) > 100:
            items = items[:100]

        bt1 = InlineKeyboardButton(text='Завершить поиск', callback_data='pass')
        kb22 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
        try:
            await bot.send_message(call.from_user.id,
                                   db.show_table(items),
                                   reply_markup=kb22)
        except exceptions.TelegramEntityTooLarge:
            await bot.send_message(call.from_user.id,
                                   db.show_table(items[:45]),
                                   reply_markup=kb22)
    else:
        await bot.send_message(call.from_user.id,
                               "Извините, ничего не найдено. "
                               "Скорее всего вы ничего не добавляли.")


@dp.callback_query(lambda call: call.data == 'graphs_period')
async def set_graphs_period(call: types.CallbackQuery, state: FSMContext):
    bt1 = InlineKeyboardButton(text='В течение периода', callback_data='gsd_for')
    bt2 = InlineKeyboardButton(text='За текущий период',
                               callback_data='gsd_current')
    bt3 = InlineKeyboardButton(text='Выбрать другой период времени',
                               callback_data='gsd_other')
    buttons = [[bt1, bt2], [bt3]]
    if state is not None:
        bt5 = InlineKeyboardButton(text='Далее', callback_data='set_graphs')
        buttons.append([bt5])
    
    kb24 = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(call.from_user.id,
                           "Выберите период времени, которым хотите"
                           " ограничить выбор операций",
                           reply_markup=kb24)


@dp.callback_query(lambda call: call.data.startswith('gsd'))
async def graphs_date(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'for':
        bt1 = KeyboardButton(text='День')
        bt2 = KeyboardButton(text='Неделя')
        bt3 = KeyboardButton(text='Месяц')
        bt4 = KeyboardButton(text='Год')
        kb25 = ReplyKeyboardMarkup(keyboard=[[bt1, bt2, bt3, bt4]],
                                   resize_keyboard=True, one_time_keyboard=True)
        await state.set_state(FSMAdmin.gsd_for)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от сегодняшнего дня до дня, который "
            "был неделю назад.",
            reply_markup=kb25
        )

    elif aim == 'current':
        bt1 = KeyboardButton(text='День')
        bt2 = KeyboardButton(text='Неделя')
        bt3 = KeyboardButton(text='Месяц')
        bt4 = KeyboardButton(text='Год')
        kb26 = ReplyKeyboardMarkup(keyboard=[[bt1, bt2, bt3, bt4]],
                                   resize_keyboard=True, one_time_keyboard=True)
        await state.set_state(FSMAdmin.gsd_current)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от настоящего момента до дня, который "
            "был или есть началом недели.",
            reply_markup=kb26
        )

    elif aim == 'other':
        await state.set_state(FSMAdmin.gsd_other)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "выбрать операции по следующему шаблону.\n\n"
            "2022-08-01-00-01   2022-08-31-12-03\n\n"
            "(год-месяц-день-час-минута, "
            "разделяя ограничители тремя пробелами)")


@dp.callback_query(lambda call: call.data == 'set_graphs')
async def graphs_settings(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.set_graphs)
    bt1 = KeyboardButton(text='По дням')
    bt2 = KeyboardButton(text='По месяцам')
    bt3 = KeyboardButton(text='По годам')
    kb23 = ReplyKeyboardMarkup(keyboard=[[bt1, bt2, bt3]],
                               resize_keyboard=True, one_time_keyboard=True)
    await bot.send_message(call.from_user.id,
                           'Выберите периоды времени, '
                           'по которым на графиках будут '
                           'отображаться расходы и доходы:',
                           reply_markup=kb23)


@dp.callback_query(lambda call: call.data == 'set_ct_dgm')
async def categories_diagrams(call: types.CallbackQuery, state: FSMContext):
    d = (await state.get_data())['graphs_data']
    cs = list(set(it[6] for it in d))
    await state.set_data({'dgm_cts': cs})
    
    t_ct = '\n'.join([f'{i+1}. {c}' for i, c in enumerate(cs)])
    await state.set_state(FSMAdmin.set_dgm)
    await bot.send_message(
        call.from_user.id,
        'Введите через запятую цифры категорий, по которым '
        'вы хотите увидеть соотношения подкатегорий\nили\n'
        'Введите символ нижнего подчёркивания, чтобы выбрать '
        'все категории\nили\nВведите тире (-), чтобы пропустить:\n'
        f'{t_ct}')


@dp.callback_query(lambda call: call.data == 'graph_show', state=FSMAdmin.set_dgm)
async def show_graphs_and_diagrams(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    d = data['graphs_data']
    cs = data['dgm_cts']
    summ = data['summary']

    d_main = db.data_summary(d, summ)
    file = db.make_main_report(d_main, call.from_user.id)
    await bot.send_photo(call.from_user.id, types.InputFile(file))

    if cs is not None:
        d_ct = [db.category_summary(d, c) for c in cs]
        file = db.make_categories_report(d_ct, cs, call.from_user.id)
        await bot.send_photo(call.from_user.id, types.InputFile(file))


@dp.callback_query(lambda call: call.data.startswith('select'))
async def select_operations(call: types.CallbackQuery, state: FSMContext):
    msg = "Выберите параметр, по которому вы хотите ограничить поиск операций."
    
    if call.data.endswith('dal'):
        await state.set_state(FSMAdmin.delop)
        await state.set_data({'del': True})

    if state is not None:
        filargs = (await state.get_data()).get(f'filter_args_{call.from_user.id}')
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

    bt1 = InlineKeyboardButton(text='Дата', callback_data='choose_date')
    bt2 = InlineKeyboardButton(text='Количество', callback_data='choose_amount')
    bt3 = InlineKeyboardButton(text='Цена за единицу', callback_data='choose_ppu')
    bt4 = InlineKeyboardButton(text='Общая стоимость', callback_data='choose_total')
    bt5 = InlineKeyboardButton(text='Далее', callback_data='ct_filters')
    kb23 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2], [bt3, bt4], [bt5]])
    await bot.send_message(call.from_user.id, msg, reply_markup=kb23)


@dp.callback_query(lambda call: call.data.startswith('choose'))
async def choose_limits(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'date':
        bt1 = InlineKeyboardButton(text='В течение периода',
                                   callback_data='period_for')
        bt2 = InlineKeyboardButton(text='За текущий период',
                                   callback_data='period_current')
        bt3 = InlineKeyboardButton(text='Выбрать другой период времени',
                                   callback_data='period_other')
        kb24 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2], [bt3]])
        await bot.send_message(call.from_user.id,
                               "Выберите период времени, которым хотите"
                               " ограничить поиск операций",
                               reply_markup=kb24)

    if aim == 'amount':
        await state.set_state(FSMAdmin.amount)
        await bot.send_message(call.from_user.id,
                               "Введите значения количества, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "0.001   1.999 (разделяя ограничители "
                               "тремя пробелами)")

    if aim == 'ppu':
        await state.set_state(FSMAdmin.ppu)
        await bot.send_message(call.from_user.id,
                               "Введите значения цены за единицу, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "-99.99   9999.99 (разделяя "
                               "ограничители тремя пробелами "
                               "(значения со знаком \"-\" - расходы, "
                               "без - доходы))")

    if aim == 'total':
        await state.set_state(FSMAdmin.total)
        await bot.send_message(call.from_user.id,
                               "Введите значения общей стоимости, "
                               "которыми хотите ограничить выбор "
                               "операций, по примеру ниже.\n"
                               "-1000.00   10000.00 (разделяя "
                               "ограничители тремя пробелами "
                               "(значения со знаком \"-\" - расходы, "
                               "без - доходы))")


@dp.callback_query(lambda call: call.data.startswith('period'))
async def choose_time(call: types.CallbackQuery, state: FSMContext):
    _, aim = call.data.split('_')
    if aim == 'for':
        bt1 = KeyboardButton(text='День')
        bt2 = KeyboardButton(text='Неделя')
        bt3 = KeyboardButton(text='Месяц')
        bt4 = KeyboardButton(text='Год')
        kb25 = ReplyKeyboardMarkup(keyboard=[[bt1, bt2, bt3, bt4]],
                                   resize_keyboard=True, one_time_keyboard=True)
        await state.set_state(FSMAdmin.date_for)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от сегодняшнего дня до дня, который "
            "был неделю назад.",
            reply_markup=kb25)

    if aim == 'current':
        bt1 = KeyboardButton(text='День')
        bt2 = KeyboardButton(text='Неделя')
        bt3 = KeyboardButton(text='Месяц')
        bt4 = KeyboardButton(text='Год')
        kb26 = ReplyKeyboardMarkup(keyboard=[[bt1, bt2, bt3, bt4]],
                                   resize_keyboard=True, one_time_keyboard=True)
        await state.set_state(FSMAdmin.date_current)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций.\n"
            "Например, \"Неделя\" означает, что будут найдены все "
            "операции от настоящего момента до дня, который "
            "был или есть началом недели.",
            reply_markup=kb26)

    if aim == 'other':
        await state.set_state(FSMAdmin.date_other)
        await bot.send_message(
            call.from_user.id,
            "Выберите промежуток времени, за который вы хотите "
            "поставить ограничение по времени при выборе операций "
            "по следующему шаблону.\n\n"
            "2022-08-01-00-01   2022-08-31-12-03\n\n"
            "(год-месяц-день-час-минута, "
            "разделяя ограничители тремя пробелами)")


@dp.callback_query(lambda call: call.data == 'ct_filters')
async def category_filter(call: types.CallbackQuery, state: FSMContext):
    msg = ""
    if state is not None:
        filargs = (await state.get_data()).get(f'filter_args_{call.from_user.id}')
        if filargs is None:
            filargs = dict.fromkeys(['points', 'cols', 'eqs', 'ui', 'sort_by'],
                                    None)
            filargs['ui'] = call.from_user.id
            await state.set_data({f'filter_args_{call.from_user.id}': filargs})

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

    bt1 = InlineKeyboardButton(text="Выбрать категории", callback_data='cat_filt')
    bt3 = InlineKeyboardButton(text="Далее", callback_data='is_sorting')
    buttons = [[bt1, bt3]]
    if msg:
        bt2 = InlineKeyboardButton(text="Выбрать подкатегории",
                                   callback_data='subcat_filt')
        buttons = [[bt1, bt2], [bt3]]
    
    kb27 = InlineKeyboardMarkup(inline_keyboard=buttons)
    await bot.send_message(call.from_user.id,
                           f"Выбрать фильтр по категориям?\n{msg}"
                           "Если нет, то фильтр по подкатегориям "
                           "пропускается автоматически.",
                           reply_markup=kb27)


@dp.callback_query(lambda call: call.data == 'cat_filt')
async def cat_filt(call: types.CallbackQuery, state: FSMContext):
    t_ex = ''.join([f'{i + 1}. {c}\n' for i, c in enumerate(db.catgs)])
    await state.set_state(FSMAdmin.catfilt)
    await bot.send_message(call.from_user.id,
                           "Введите номера одной или нескольких "
                           "категорий из существующих через запятую "
                           f"(например: 1, 6, 4 ):\n{t_ex}")


@dp.callback_query(lambda call: call.data == 'subcat_filt')
async def subcat_filt(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        ex_sc = list(subct_ex_dict.keys())
        filargs = (await state.get_data())[f'filter_args_{call.from_user.id}']

        cs = [c for c in filargs['eqs'] if c in db.catgs]
        scs_dict = {c: subct_ex_dict[c] if c in ex_sc
                    else subct_in_dict[c] for c in cs}
        await state.set_data({f'scs_dict_{call.from_user.id}':
                                  list(scs_dict.items())})
        
        scs_l = ""
        j = 0
        for c in scs_dict:
            scs_l += (c + ":\n")
            j += 1
            for i, sc in enumerate(scs_dict[c]):
                scs_l += f'\t{j}{i + 1}. {sc}\n'

    await state.set_state(FSMAdmin.subcatfilt)
    await bot.send_message(call.from_user.id,
                           "Введите номера одной или нескольких "
                           "подкатегорий из существующих выбранных "
                           "категорий через запятую "
                           f"(например: 15, 211, 36 ):\n{scs_l}")


@dp.callback_query(lambda call: call.data == 'is_sorting')
async def is_sorting(call: types.CallbackQuery, state: FSMContext):
    msg = ""
    if state is not None:
        filargs = (await state.get_data())[f'filter_args_{call.from_user.id}']
        if filargs['sort_by'] is not None:
            params = {'Дата': 'date',
                      "Название": 'operation_name',
                      "Цена за единицу": 'price_per_unit',
                      "Количество": 'amount',
                      "Общая стоимость": 'total',
                      "Категории": 'category',
                      "Подкатегории": 'subcategory'}
            sorters = [list(params.items())[list(params.values()).index(s)][0]
                       for s in filargs['sort_by']]
            msg += "\nУже добавлена следующая сортировка:\n"
            msg += f"{', '.join(sorters)}"

    bt1 = InlineKeyboardButton(text='Сортировать', callback_data='yes_sort')
    bt2 = InlineKeyboardButton(text='Пропустить', callback_data='search')
    kb28 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
    await bot.send_message(call.from_user.id,
                           f"Сортировать операции по параметрам?{msg}",
                           reply_markup=kb28)


@dp.callback_query(lambda call: call.data == 'yes_sort')
async def sort_it_all(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.sort_it)
    params = ["Дата", "Название", "Цена за единицу", "Количество",
              "Общая стоимость", "Категории", "Подкатегории"]
    ps = ''.join([f'{i+1}. {p}\n' for i, p in enumerate(params)])
    await bot.send_message(call.from_user.id,
                           "Введите через запятую номера параметров, "
                           "по которым вы хотите "
                           "отсортировать операции. Например: 1, 3, 2 "
                           "(порядок расположения имеет значение):"
                           f"\n{ps}")


@dp.callback_query(lambda call: call.data == 'search')
async def search_operations(call: types.CallbackQuery, state: FSMContext):
    msg = ""
    if state is not None:
        query = (await state.get_data()).get(f'search_{call.from_user.id}')
        if query is not None:
            msg += f"\nУже добавлен поисковой запрос: {query}\n"

    bt1 = InlineKeyboardButton(text='Искать', callback_data='yes_find')
    bt2 = InlineKeyboardButton(text="Показать результат", callback_data='show_res')
    kb29 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
    await bot.send_message(call.from_user.id,
                           "Вы хотите добавить фильтр "
                           f"по имени операции?{msg}"
                           "(будут найдены все операции, "
                           "в которых есть введённая подстрока)",
                           reply_markup=kb29)


@dp.callback_query(lambda call: call.data == 'yes_find')
async def find_operations(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(FSMAdmin.search)
    await bot.send_message(call.from_user.id, "Введите поисковой запрос:")


@dp.callback_query(lambda call: call.data == 'show_res')
async def show_results(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        data = await state.get_data()
        filargs = data.get('filter_args_' + str(call.from_user.id))
        query = data.get('search_' + str(call.from_user.id))
        if filargs is not None:
            p = tuple(filargs['points']) if filargs['points'] is not None else None
            c = tuple(filargs['cols']) if filargs['cols'] is not None else None
            e = tuple(filargs['eqs']) if filargs['eqs'] is not None else None
            sb = (tuple(filargs['sort_by'])
                  if filargs['sort_by'] is not None else None)
            items = db.select_operations(p, c, e, filargs['ui'], sort_by=sb)
        else:
            items = db.select_operations(ui=call.from_user.id, sort_by='date')

        if query is not None:
            items = db.search_in_list(items, query)

        if items and not data.get('del', False):
            if len(items) > 100:
                items = items[:100]

            bt1 = InlineKeyboardButton(text='Завершить поиск', callback_data='pass')
            kb30 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
            await bot.send_message(call.from_user.id,
                                   f"Найдено следующее:\n{db.show_table(items)}",
                                   reply_markup=kb30)
        elif items and data.get('del', False):
            data['del_items_' + str(call.from_user.id)] = items
            await state.set_state(FSMAdmin.del_select)
            await bot.send_message(call.from_user.id,
                                   f"{db.show_table(items)}\n"
                                   f"Введите номера операций, "
                                   f"которые хотите удалить\nИЛИ\n"
                                   f"Отправьте нижнее "
                                   f"подчёркивание (_), "
                                   f"если хотите удалить "
                                   f"всё найденное.")
        else:
            bt1 = InlineKeyboardButton(text='Повторить поиск',
                                       callback_data='search')
            bt2 = InlineKeyboardButton(text='Завершить поиск', callback_data='pass')
            kb31 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2]])
            await bot.send_message(call.from_user.id,
                                   "По вашему запросу ничего не найдено.",
                                   reply_markup=kb31)
    else:
        items = db.select_operations(ui=call.from_user.id, sort_by='date')
        if items:
            if len(items) > 100:
                items = items[:100]

            bt1 = InlineKeyboardButton(text='Завершить поиск', callback_data='pass')
            kb32 = InlineKeyboardMarkup(inline_keyboard=[[bt1]])
            await bot.send_message(call.from_user.id,
                                   f"Найдено следующее:\n{db.show_table(items)}",
                                   reply_markup=kb32)
        else:
            await bot.send_message(call.from_user.id,
                                   "Извините, ничего не найдено. "
                                   "Скорее всего вы ничего не добавляли.")


@dp.callback_query(lambda call: call.data == 'delete')
async def delete_operations(call: types.CallbackQuery):
    bt1 = InlineKeyboardButton(text='Удалить всё', callback_data='delete_all')
    bt2 = InlineKeyboardButton(text='Выбрать для удаления',
                               callback_data='select_del')
    bt3 = InlineKeyboardButton(text='Восстановить удалённое',
                               callback_data='restore')
    kb33 = InlineKeyboardMarkup(inline_keyboard=[[bt1, bt2], [bt3]])
    await bot.send_message(call.from_user.id,
                           "Выберите, какие операции "
                           "вы хотите удалить (или восстановить)",
                           reply_markup=kb33)


@dp.callback_query(lambda call: call.data == 'delete_all')
async def show_all_operations(call: types.CallbackQuery, state: FSMContext):
    items = db.select_operations(ui=call.from_user.id, sort_by='date')
    if items:
        if len(items) > 100:
            items = items[:100]

        msg = ("\nВыберите номера операций для удаления "
               "(через один пробел, например: 1 4 5 6 7 8 9 34)\n"
               "ИЛИ\nОтправьте подчёркивание (_), чтобы удалить всё выданное.")
        await state.set_state(FSMAdmin.delete_it_all)
        await bot.send_message(call.from_user.id, db.show_table(items) + msg)
    else:
        await bot.send_message(call.from_user.id,
                               "Извините, ничего не найдено. "
                               "Скорее всего вы ничего не добавляли.")


@dp.callback_query(lambda call: call.data == 'restore')
async def restore_data(call: types.CallbackQuery):
    store = shelve.open('local_database/backup_data.data')
    key = [k for k in store if k.startswith(str(call.from_user.id))]
    if len(key) == 0:
        await bot.send_message(call.from_user.id,
                               'Данных для восстановления не нашлось :(\n'
                               'Возможно вы ничего не удаляли.')
    else:
        key = key[0]
        _, d = key.split('_')
        dat = store[key]
        store.close()
        if len(dat) > 2:
            example = (f"{' | '.join(map(str, dat[0][1:]))}\n"
                       f"{' | '.join(map(str, dat[1][1:]))}\n")
            msg = (f"Найдено резервное сохранение от {d}:"
                   f"\n\n{example}...\nВы хотите его восстановить?")
        if 0 < len(dat) <= 2:
            example = f"{' | '.join(map(str, dat[0][1:]))}\n"
            example += ("" if len(dat) == 1
                        else f"{' | '.join(map(str, dat[1][1:]))}\n")
            msg = (f"Найдено резервное сохранение от {d}:"
                   f"\n\n{example}Вы хотите его восстановить?")

        bt1 = InlineKeyboardButton(text='Восстановить', callback_data='backup_yes')
        bt2 = InlineKeyboardButton(text='Не восстанавливать', callback_data='pass1')
        kb34 = InlineKeyboardMarkup(inline_keyboard=[[bt1], [bt2]])
        await bot.send_message(call.from_user.id, msg, reply_markup=kb34)


@dp.callback_query(lambda call: call.data == 'backup')
async def restore_backup(call: types.CallbackQuery):
    store = shelve.open('local_database/backup_data.data')
    key = [k for k in store if k.startswith(str(call.from_user.id))]
    key = key[0]
    dat = store[key]
    for item in dat:
        db.add_operation(item)
        await bot.send_message(call.from_user.id,f"Добавлено: {item[2]}")
    else:
        await bot.send_message(call.from_user.id,
                               "Все данные успешно восстановлены!")


@dp.callback_query(lambda call: call.data.startswith('pass'))
async def pass_action(call: types.CallbackQuery, state: FSMContext):
    if state is not None:
        await state.clear()

    b = db.show_balance(call.from_user.id)

    buttons = [
        [InlineKeyboardButton(text='Добавить QR-код', callback_data='qr')],
        [InlineKeyboardButton(text='Добавить самостоятельно',
                             callback_data='hand_enter')],
        [InlineKeyboardButton(text='Посмотреть операции', 
                             callback_data='show_what')],
        [InlineKeyboardButton(text='Удаление', callback_data='delete')]
    ]
    kb1 = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    msg = (f"Доброго времени суток, {call.from_user.full_name}.\n\n\t"
           f"Ваш баланс: {b}\n\nВыберите одно из следующих действий.")
    await bot.send_message(call.from_user.id, msg, reply_markup=kb1)


if __name__ == '__main__':
    # bot.delete_webhook(drop_pending_updates=True)
    dp.start_polling(bot, on_startup=setup_on, skip_updates=True)
