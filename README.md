## Telegram bot for budget managing

This project consists of 4 parts: parser, database, category classifier and asynchronous bot.

1. Parser takes text for scanned QR code from bill, opens website for getting bills data, inserts it and recieves all the purchase data.
2. Database for bot is made with sqlite and functions for constructing query from arguments and some other actions with data.
3. Category classifier have been trained on self labeled data to identify a product category by its name. 
4. Asynchronous bot is implemented on aiogram.

Abilities:

* Loading QR code data and getting infromation from it;
* Manual entry of purchases data using template;
* Viewing purchases history, word filter, data filter and columns sort;
* Deleting entries from list and backup of last deletion;
* Current balance view (incomes and expenses difference);
* Category prediction (with ability to change it manualy);
* Viewing graphs of categories distribution and balance history.
