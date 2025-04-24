"""
 Категории трат:
Жильё
    Ипотека
    Аренда
    Ремонт и обслуживание
    Налоги
    Улучшения / украшения
    Электричество
    Отопление
    Мусор
    Газ
Транспорт
    Автокредит
    Топливо
    Обслуживание / ремонт
    Автомобильные сборы
    Парковка
    Общественный транспорт
    Дорожные сборы
    Перевоз
    Такси
    Поезд
    Самолёт
    Метро
    Электричка
    Самокаты
    Водный транспорт
Еда
    Крупы / макароны / каши
    Мясо / морепродукты
    Овощи / фрукты / ягоды
    Полуфабрикаты
    Молочная продукция
    Сладкое
    Хлебобулочные
    Консервы
    Приправы / соусы / сиропы
    Напитки
    Ресторан / кафе
    Фастфуд
    Чай / кофе
    ПАВ
    Алкоголь
Товары
    Одежда
    Обувь
    Бельё
    Аксессуары
    Личная гигиена
    Бытовая химия
    Бытовая техника
    Электроника
    Инструменты / утварь
    Мебель
    Запчасти / детали
    Посуда
    Ремонт
    Остальное
Услуги
    Интернет
    Телефон
    Разрешения
    Документы
    Программное обеспечение
    Медицинская страховка
    Страхование автомобиля
    Страхование жизни
    Страхование имущества
    Страхование домашних животных
    Парикмахерская
    Платные подписки
    Доставка
    Кредит
    Долг
Здоровье
    Уход за полостью рта
    Специализированная помощь
    Лекарства
    Медицинское оборудование
    Платные мед. услуги
    Личная гигиена
    Психолог
Образование
    Курсы
    Автошкола
    Учебники / пособия
    Обучение
    Репетитор
    Канцелярия
Развлечения
    Хобби
    Спорт
    Отдых
    Ювелир
    Косметика
    Мероприятия
    Искусство
    Книги
    Журналы / газеты
    Видеоигры
    Игрушки
Разное
    Домашние животные
    Семья
    Растения / цветы
    Подарки / помощь
    Связанное с религией
    Штрафы
    Неизвестно


 Категории доходов:
Зарплата
Возврат
Алименты
Выплаты
    Гранты
    Пенсии
    Стипендии
    Премии
    Призы
    Пособия
Бизнес / инвестиции
    Дивиденды
    Предпринимательство
    Депозит
Подарки / помощь
"""

import random
import pickle
from sklearn import metrics
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import SGDClassifier
# from sklearn.model_selection import GridSearchCV
# from sklearn.model_selection import ParameterGrid
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


def update_data():
    # Обновление данных в датасете расходов
    lines = open('data_set_ex.txt', encoding='utf-8').readlines()
    random.shuffle(lines)  # перемешивание данных из датасета
    X, Y = [], []
    for line in lines:
        it, lb = line.split(' @ ')
        lb = lb.rstrip()
        if lb not in ['Жильё', "Услуги", "Транспорт", "Разное", "Товары",
                      "Здоровье", "Развлечение", "Еда", "Образование"]:
            if lb in ['доровье', 'Тоовары', 'Образоавние',
                      'ТОвары', 'Эдоровье']:
                # Если допущена ошибка в написании метка,
                # то заменяем её на правильно написанную
                rep = {'доровье': 'Здоровье', 'Тоовары': "Товары",
                       'Образоавние': "Образование", 'ТОвары': "Товары",
                       'Эдоровье': "Здоровье"}
                lb = rep[lb]
            
            # Если введено М, то скорее всего произошла опечатка
            # при попытке нажать Ctrl + V, и определить метку нужно заново
            if lb == 'м':
                print(it, end=' - > ')
                lb = input()
    
        X.append(it)
        Y.append(lb)
    
    
    print(set(Y))  # Вывод всех различных меток
    input('Enter any key to continue: ')  # задержка
    
    # Разделение данных на тренировочный, тестовый и валидационный сеты
    X_train, X_valid, y_train, y_valid = train_test_split(
        X, Y, test_size=0.1, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(
        X_train, y_train, test_size=0.2, random_state=42)
    
    print(set(y_train), set(y_test), set(y_valid), sep='\n')
    # проверка на наличие всех различных меток в каждом сете
    input('Enter any key to continue: ')
    
    pickle.dump([X_train, X_test, X_valid, y_train, y_test, y_valid],
                open('data_set_ex.data', 'wb'))  # сохранение данных в файле
    
    
    # Обновление данных в датасете доходов
    lines = open('data_set_in.txt', encoding='utf-8').readlines()
    random.shuffle(lines)  # перемешивание данных из датасета
    X, Y = [], []
    for line in lines:
        it, lb = line.split(' @ ')
        lb = lb.rstrip()
    
        X.append(it)
        Y.append(lb)
    
    
    print(set(Y))  # Вывод всех различных меток
    input('Enter any key to continue: ')  # задержка
    
    # Разделение данных на тренировочный, тестовый и валидационный сеты
    X_train, X_valid, y_train, y_valid = train_test_split(
        X, Y, test_size=0.2, random_state=21)
    X_train, X_test, y_train, y_test = train_test_split(
        X_train, y_train, test_size=0.3, random_state=21)
    
    print(set(y_train), set(y_test), set(y_valid), sep='\n')
    # проверка на наличие всех различных меток в каждом сете
    input('Enter any key to continue: ')
    
    pickle.dump([X_train, X_test, X_valid, y_train, y_test, y_valid],
                open('data_set_in.data', 'wb'))  # сохранение данных в файле



def make_categorizer(dataset):
    X_train, X_test, X_valid, y_train, y_test, y_valid = pickle.load(
        open(dataset, 'rb'))  # загрузка наборов данных

    if __name__ == '__main__':
        # Проверка на наличие всех возможных меток во все сетах
        print(set(y_train), set(y_test), set(y_valid), sep='\n')
        input('Enter any key to continue: ')

    # Конструирование классификатора
    sgd_clf = Pipeline([
        ('tfidf', TfidfVectorizer()),
        ('sgd_clf', SGDClassifier(random_state=42, penalty='l2',
                                  loss='modified_huber',
                                  class_weight='balanced'))])
    sgd_clf.fit(X_train, y_train)  # обучение классификатора

    if __name__ == '__main__':
        # Вывод данных тестовой выборки
        predicted_sgd = sgd_clf.predict(X_test)
        print(metrics.classification_report(predicted_sgd, y_test))
        print(sgd_clf.score(X_test, y_test))

        # Вывод данных валидационной выборки
        predicted_sgd_val = sgd_clf.predict(X_valid)
        print(metrics.classification_report(predicted_sgd_val, y_valid))
        print(sgd_clf.score(X_valid, y_valid))

    return sgd_clf


if __name__ == '__main__':
    # Классификатор, определяющий категории доходов
    in_cat = make_categorizer('data_set_in.data')
    # Классификатор, определяющий категории расходов
    ex_cat = make_categorizer('data_set_ex.data')

    # сохранение обученных нейронных сетей в файле
    pickle.dump([ex_cat, in_cat], open('categorizer.data', 'wb'))
