import local_database.fb_sql as db
import pickle
import time
from matplotlib import pyplot as plt
# from parser.fb_parser import CHECK


clf_ex, clf_in = pickle.load(
    open('data_define\\categorizer.data', 'rb'))
ct_ex_list, ct_in_list, subct_ex_dict, subct_in_dict = \
    pickle.load(open('local_database\\cts_lists.data', 'rb'))

check_list = ['INSERT_YOUR_RECEIPT_HERE']


if __name__ == '__main__':
    print("{:0>4.4s}-{:0>2.2s}-{:0>2.2s}-{:0>2.2s}-{:0>2.2s}"
          .format(*map(str, (2022, 1, 30, 0, 1))))


def define_cts_ex(oper_name):
    ct = clf_ex.predict([oper_name])[0]
    print(*it, sep='   ')
    while True:
        q = input(f'The category for {it[0]} is {ct}.\n'
                  f'1. Change category\n2. Set subcategory\n')
        if q == '1':
            t_ex = ''.join([f'{i + 1}. {c}\n'
                            for i, c in enumerate(ct_ex_list)])
            ct = ct_ex_list[
                int(input('Enter one fo the next categories '
                          f'for {it[0]}:\n{t_ex}')) - 1]
        elif q == '2':
            t_ex = ''.join([f'{i + 1}. {c}\n'
                            for i, c in enumerate(subct_ex_dict[ct])])
            subct = input('Enter one fo the next subcategories '
                          f'for {it[0]} \neither type '
                          'your own category \neither type whitespace '
                          'for no subcategory\nor type "cansel" '
                          f'for returning back:\n{t_ex}')

            if subct.lower() == 'cansel':
                continue

            if subct == ' ':
                subct = None
                break
            elif subct.isdigit():
                subct = subct_ex_dict[ct][int(subct) - 1]
                break
            else:
                break

    return ct, subct


for qr in check_list:
    st = time.perf_counter()
    # t = CHECK(qr)
    li = t.get_list()
    date = t.date()
    print(date)
    if not li:
        q = input('Information from the check wasn\'t loaded.\n'
                  '1. Pass\n2. Enter information on your own '
                  'by the scheme below:\noperation name, '
                  'price per unit, amount, total cost '
                  '(separateing each parameter by three whitespaces '
                  'like this \/).\n'
                  'Мука Белиевская в/с 2кг 1/   82.00   1   82.00\n'
                  'Салфетки комфорт бум б/рис   21.00   2   42.00\n'
                  'Яблоки   159.90   0.866   138.47\n'
                  '   100   1   100 (you can pass name by this way)\n')

        if q == '1':
            continue

        if q == '2':
            i = 0
            while q.lower() != 'end':
                i += 1
                op = input(f'Enter operation {i}: ')
                op = op.split('   ')

                ct, subct = define_cts_ex(op[0])

                operation = ('1', date, op[0], *map(float, op[1:]),
                             ct, subct)
                db.add_operation(operation)
                print(f'Operation {operation[2]} / {ct} / {subct} '
                      'added successfully!')
                q = input('If you want to exit type word "end",'
                          ' type any message otherwise:\n')

            continue

    print(time.perf_counter() - st)
    for it in li:
        ct, subct = define_cts_ex(it[0])

        operation = ('1', date, it[0].strip(), *it[1:], ct, subct)
        db.add_operation(operation)
        print(f'Operation {operation[2]} / {ct} / {subct} '
              'added successfully!\n\n')
        # 28.367970580002293 10/15 are right
