import time
from bs4 import BeautifulSoup as BS
from selenium import webdriver
from selenium.common import exceptions as sel_exs
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait


test_check = ["INSERT_YOUR_LIST_OF_RECEIPTS']


class CHECK:
    url = 'https://proverkacheka.com'
    driver = webdriver.Firefox()

    def __init__(self, qr_code):
        self.qr = qr_code  # текст отсканированного qr-кода

    def get_list(self):
        """
        Функция, при отсутствии ошибок, возвращает список кортежей,
        в каждом из которых содержится информация об операции из чека
        (название, цена за единицу, количество, общая стоимость).

        :return: Список кортежей с информацией об операциях в чеке.
        При появлении исключения возвращается пустой список.
        """
        try:
            self.driver.get(self.url)  # получение веб-страницы
        except sel_exs:
            return []

        st = WebDriverWait(self.driver, 60) \
            .until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, '.b-checkform_nav > '
                                  'li:nth-child(4) > a:nth-child(1)')
            ))
        # переход на поле ввода текста qr-кода
        try:
            st.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", st)

        try:
            textarea = WebDriverWait(self.driver, 60)\
                .until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, '#b-checkform_qrraw')
                ))
            b = WebDriverWait(self.driver, 60)\
                .until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR,
                     '#b-checkform_tab-qrraw > div:nth-child(1) > '
                     'div:nth-child(1) > div:nth-child(1) > '
                     'form:nth-child(1) > div:nth-child(2) > '
                     'div:nth-child(1) > button:nth-child(1)')
                ))
        except sel_exs.TimeoutException:
            return []

        textarea.send_keys(self.qr)  # вставка текста qr-кода
        try:
            b.click()  # отправка текста qr-кода на проверку
        except Exception:
            self.driver.execute_script("arguments[0].click();", b)

        time.sleep(3)  # ждём как минимум 3 секунды,
        # чтобы результат нашего запроса прогрузился

        html = BS(self.driver.page_source, 'html5lib')
        table = html.find('tbody')
        if table is None:
            time.sleep(3)
            html = BS(self.driver.page_source, 'html5lib')
            table = html.find('tbody')
            if table is None:  # если чека нет или он не успел
                # прогрузиться, возвращаем пустой список
                time.sleep(2)

        rows = table.findChildren('tr',
                                  attrs={'class': 'b-check_item'})
        items = []
        for row in rows:  # перебираем ряды таблицы с товарами
            # и добавляем их элементы в список предметов
            _, item, per_price, count, end_price = row.findChildren(
                'td'
            )
            items.append((item.text, per_price.text,
                          count.text, end_price.text))

        return items

    def date(self, is_iso_format: bool = True):
        """
        Функция возвращает дату на основе информации,
        указанной в тексте отсканированного qr-кода
        (год, месяц, число, час, минуты).

        :return: Кортеж с информацией о дате получения чека.
        """
        try:
            dt, *_ = self.qr.split('&')
            d, tm = dt[2:].split('T', 1)
        except ValueError:
            return '1970-01-01-00-00'

        dt = tuple(map(int, (d[:4], d[4:6], d[6:], tm[:2], tm[2:4])))

        if is_iso_format:
            dt = "{:0>4.4s}-{:0>2.2s}-{:0>2.2s}" \
                 "-{:0>2.2s}-{:0>2.2s}".format(*map(str, dt))

        return dt


if __name__ == '__main__':
    with open('train_set.txt', 'w', encoding='utf-8') as f:
        for t in test_check:
            c = CHECK(t)
            print(c.date())
            products = c.get_list()
            for product in products:
                f.write(product[0] + '\n')
                print(product[0])
