import os
import requests
from bs4 import BeautifulSoup as BS



#  Ручное определение категории для датасета
def data_labeling():
    pd = open('preparing_data.txt', encoding='utf-8').readlines()
    ds = open('data_set_in.txt', 'w', encoding='utf-8')
    
    for item in pd:
        item = item.strip()
        label = input(item + ' -> ')
        ds.write(f'{item} @ {label}\n')  # запись новых тренировочных данных
    
    ds.close()
    
    input("-" * 50)  # задержка перед переходом к следующей части кода


# Сбор всех товаров по категориям с первых веб-страниц
# (первые 50 предметов)
r = requests.get('https://shopliga.ru/categories/')
soup = BS(r.content, 'html.parser')
catg_links = soup.find_all('a', {'class': 'cat_title_full_width'})
# список ссылок на веб-страницы с категориями
catg_links = [('https://shopliga.ru' + link['href'], link.text)
              for link in catg_links]


def get_products(url):
    """
    Функция предназначена для получения всех предметов с веб-страницы
    указанного сайт (url).
    
    Args:
        url (str): Ссылка на веб-страницу с таблицей товаров.

    Returns:
        list[str]: Список найденных на веб-странице товаров.
            Если таковых не найдено или произошла ошибка соединения,
            возвращает пустой список.
    """
    try:
        r2 = requests.get(url)
    except requests.exceptions.ConnectionError:
        return []

    soup2 = BS(r2.content, 'html.parser')
    products = soup2.find_all('a', {'class': 'product-item-name'})
    return [a.text for a in products]


q = input('1. Рсходы\n2. Доходы\n')  # Выбор файла для дозаписи
if q == '1':
    f = open(os.path.dirname(os.path.dirname( __file__))
             + '/data_define/data_set_ex.txt', 'a', encoding='utf-8')
elif q == '2':
    f = open(os.path.dirname(os.path.dirname( __file__))
             + '\data_define\data_set_in.txt', 'a', encoding='utf-8')

for link, catg in catg_links:
    print(catg + ':')
    req = requests.get(link)
    subsoup = BS(req.content, 'html.parser')
    subcatg_links = subsoup.select('div.col-md-3 > div > div > ul > li > a')
    # поиск всех подкатегорий в категории
    if subcatg_links:
        # если подкатегории найдены, то создаём список со ссылками на них,
        subcatg_links = [('https://shopliga.ru' + link['href'], link.text)
                         for link in subcatg_links]
    else:
        # иначе ищем нужную категорию на основном сайте
        # и собираем соответствующий список оттуда
        c_l = soup.find_all('a', {'class': 'cat_title_full_width'})
        titles = [a.text for a in c_l]
        i = titles.index(catg)
        ct = c_l[i]
        ct = ct.findParent('div')
        ct = ct.findChildren('a')
        subcatg_links = [('https://shopliga.ru' + link['href'], link.text)
                         for link in ct]

    k = 0  # счётчик пропуска
    for sublink, subcatg in subcatg_links:
        k -= 1
        if k > 0:  # пока счётчик больше нуля, подкатегория пропускается
            continue

        print("\t" + subcatg + ':')
        items = get_products(sublink)  # получение списка товаров из подкатегории
        if not items:
            continue

        is_separately = input('Определять категории по-отдельности (0 или 1)? ')
        # если введено число больше 1,
        # то оно считывается как значение счётчика пропусков
        if int(is_separately) > 1 and k <= 0:
            k = int(is_separately)
        
        # Если введено 1, то каждому предмету нужно будет присваивать метку отдельно
        if int(is_separately) == 1:
            for item in items:
                label = input('\t\t' + item + ' -> ')
                f.write(f'{item} @ {label}\n')
                
        # если же введено 0,
        # то для всех предметов из списка будет присвоена одна метка
        elif int(is_separately) == 0:
            c_label = input('Введите общую для всех товаров категорию: ')
            for item in items:
                f.write(f'{item} @ {c_label}\n')

f.close()


# проверка работоспособности парсинга
if __name__ == '__main__':
    html = BS(open('html_parse_text.txt', 'rb').read(), 'html5lib')
    table = html.find('tbody')
    rows = table.findChildren('tr', attrs={'class': 'b-check_item'})
    items = []
    for row in rows:
        _, item, per_price, count, end_price = row.findChildren('td')
        print(item.text, per_price.text, count.text, end_price.text)

