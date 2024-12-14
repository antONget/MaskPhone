import telebot
import sqlite3
import logging
import requests
import time
import re
# -*- coding: utf-8 -*-
API_TOKEN = "7182842262:AAFBRFrmNTeJ8Uhj_9d5Rs7B-Opvh08IxQI"
bot = telebot.TeleBot(API_TOKEN, threaded=False)

conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS users 
                  (id INTEGER PRIMARY KEY, username TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS operator_choices 
                  (user_id INTEGER PRIMARY KEY, operator TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS ads 
                  (id INTEGER PRIMARY KEY AUTOINCREMENT, ad_text TEXT NOT NULL)''')
conn.commit()



# Подгрузка с файла
def load_masks_from_file():
    mask_file = {}
    with open("mask.txt", "r") as file:
        exec(file.read(), mask_file)
    return mask_file


masks = load_masks_from_file()
def save_operator_choice(user_id, operator):
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO operator_choices (user_id, operator) VALUES (?, ?)', (user_id, operator))
    conn.commit()
    cursor.close()

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    cursor.execute('INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)', (user_id, username))
    conn.commit()

    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row('Мегафон', 'МТС')
    admin_ids = [5214191800, 6969088783]  # Список ID администраторов

    if message.chat.id in admin_ids:
        keyboard.row('Админка')
    bot.send_message(message.chat.id, "Добро пожаловать, я помогу тебе понять маску")
    cursor.execute('SELECT ad_text FROM ads ORDER BY id DESC LIMIT 1')
    last_ad = cursor.fetchone()
    ad_text = last_ad[0] if last_ad else "Нет активной рекламы"
    bot.send_message(message.chat.id, ad_text)
    bot.send_message(message.chat.id,
                     "Выберите оператора ниже, после чего введите 7 цифр номера <u>без кода оператора</u>:",
                     parse_mode='HTML', reply_markup=keyboard)


@bot.message_handler(func=lambda message: message.text == 'Админка')
def handle_admin_button(message):
    admin_ids = [5214191800, 6969088783]  # Список ID администраторов
    if message.chat.id in admin_ids:
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=create_admin_keyboard())


def create_admin_keyboard():
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton('Добавить маски Загрузить файл', callback_data='add_all_mask'),
        telebot.types.InlineKeyboardButton('Скачать маски', callback_data='dow_all_mask')
    )
    keyboard.row(
        telebot.types.InlineKeyboardButton('Количество пользователей', callback_data='user_count'),
        telebot.types.InlineKeyboardButton('Редактировать рекламу', callback_data='edit_ad')
    )
    return keyboard


@bot.message_handler(func=lambda message: message.text.lower() in ['мегафон', 'мтс'])
def handle_operator_choice(message):
    operator = message.text.lower()
    save_operator_choice(message.from_user.id, operator)

    if operator == 'мегафон':
        bot.send_message(message.chat.id, "Введите номер Мегафон, 7 цифр, <u>без кода оператора</u>:",
                         parse_mode='HTML')
        bot.register_next_step_handler(message, handle_megafon_mask_check)
    elif operator == 'мтс':
        bot.send_message(message.chat.id, "Введите номер МТС, 7 цифр, <u>без кода оператора</u>:", parse_mode='HTML')
        bot.register_next_step_handler(message, handle_mts_mask_check)
    else:
        bot.send_message(message.chat.id, "Выберите оператора: Мегафон или МТС")



def convert_number_to_mask(number):
    number_to_letter = {}
    mask = ''
    next_letter = 'A'
    for digit in number:
        if digit not in number_to_letter:
            if next_letter > 'X':  # Если следующая буква выходит за рамки 'D', слишком много уникальных цифр
                raise ValueError("Input number has more than four unique digits.")
            number_to_letter[digit] = next_letter
            if next_letter != 'E':  # Инкрементируем только до 'D'
                next_letter = chr(ord(next_letter) + 1)
        mask += number_to_letter[digit]
    return mask
# Пример использования функции:
# Пример использования функции:
number = '0200320'
mask = convert_number_to_mask(number)
print(mask)  # Ожидаемый результат: 'ABCDEEE'

# Пример использования функции:
number = '0200320'
mask = convert_number_to_mask(number)
print(mask)  # Ожидаемый результат: 'ABCDEEE'

def mask_to_regex(mask):
    pattern_parts = []
    group_counter = 1
    group_map = {}

    for char in mask:
        if char not in group_map:
            group_map[char] = group_counter
            group_counter += 1
            pattern_parts.append(r'(\d)')
        else:
            group_number = group_map[char]
            pattern_parts.append(fr'\{group_number}')

    return '^' + ''.join(pattern_parts) + '$'

def check_number_against_masks(number, masks):
    converted_mask = convert_number_to_mask(number)
    for mask_category, mask_list in masks.items():
        if converted_mask in mask_list:
            return mask_category.split('_')[1], converted_mask
    return "обычный", converted_mask




# валидация
def is_valid_mask(mask):
    if not bool(re.match(r'^\d{7}$', mask)):
        return False
    try:
        letter_mask = convert_number_to_mask(mask)
    except ValueError as e:
        return False  # Превышено количество уникальных цифр
    return all(letter in 'ABCDE' for letter in letter_mask)

def extract_last_7_digits(input_str):
    # Извлекаем все цифры из строки
    digits = re.sub(r'\D', '', input_str)
    return digits[-7:]


def get_mts_mask_status(mask):
    for mask_list, status in [
        (masks.get('mts_exclusive_masks', []), "Эксклюзивный 1000000 ₽"),
        (masks.get('mts_top_infinity_masks', []), "ТОП-Инфинити 500000 ₽"),
        (masks.get('mts_infinity_masks', []), "Инфинити 150000 ₽"),
        (masks.get('mts_premium_masks', []), "Премиум 26000 ₽"),
        (masks.get('mts_prestige_masks', []), "Престиж 21000 ₽"),
        (masks.get('mts_vip_masks', []), "VIP 16000 ₽"),
        (masks.get('mts_platinum_masks', []), "Платина 5500 ₽"),
        (masks.get('mts_gold_masks', []), "Золото 1000 ₽"),
    ]:
        for pattern in mask_list:
            if re.match(mask_to_regex(pattern), mask):
                return status, pattern
    return "Обычный", ''

def get_megafon_mask_status(mask):
    for mask_list, status in [
        (masks.get('megafon_vip_masks', []), "VIP"),
        (masks.get('megafon_platinum_masks', []), "Платина"),
        (masks.get('megafon_gold_masks', []), "Золото"),
        (masks.get('megafon_silver_masks', []), "Серебро"),
        (masks.get('megafon_bronza_masks', []), "Бронза"),
    ]:
        for pattern in mask_list:
            if re.match(mask_to_regex(pattern), mask):
                return status, pattern
    return "Обычный", ''


def get_user_operator(user_id):
    cursor.execute('SELECT operator FROM operator_choices WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    else:
        return None


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id
    operator = get_user_operator(user_id)
    if operator:
        if operator == 'мегафон':
            handle_megafon_mask_check(message)
        elif operator == 'мтс':
            handle_mts_mask_check(message)
    else:
        bot.send_message(message.chat.id, "Выберите оператора: Мегафон или МТС")


def handle_mts_mask_check(message):
    raw_input = message.text
    logging.info(f"Received mask input: {raw_input}")

    # Извлекаем последние 7 цифр из входящего сообщения
    mask = extract_last_7_digits(raw_input)

    converted_mask = convert_number_to_mask(mask)

    if not is_valid_mask(mask):
        bot.send_message(message.chat.id, "Вы ввели некорректную маску, попробуйте еще раз", parse_mode='HTML')
    else:
        status, matching_pattern = get_mts_mask_status(mask)
        if matching_pattern:
            bot.send_message(message.chat.id, f"МТС: {mask} {status} (Маска: {converted_mask})")
        else:
            bot.send_message(message.chat.id, f"МТС: {mask} {status} ")

def handle_megafon_mask_check(message):
    raw_input = message.text
    logging.info(f"Received mask input: {raw_input}")

    # Извлеките последние 7 цифр из входящего сообщения
    mask = extract_last_7_digits(raw_input)

    converted_mask = convert_number_to_mask(mask)

    if not is_valid_mask(mask):
        bot.send_message(message.chat.id, "Вы ввели некорректную маску, попробуйте еще раз", parse_mode='HTML')
    else:
        status, matching_pattern = get_megafon_mask_status(mask)
        if matching_pattern:
            bot.send_message(message.chat.id, f"Мегафон: {mask} {status} (Маска: {converted_mask})")
        else:
            bot.send_message(message.chat.id, f"Статус маски Мегафон: {mask} {status} ")




@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    if call.data == 'add_all_mask':
        msg = bot.send_message(call.message.chat.id, 'Пожалуйста, отправьте файл mask.txt')
        bot.register_next_step_handler(msg, receive_mask_file)

    elif call.data == 'dow_all_mask':
        with open("mask.txt", "rb") as mask_file:
            bot.send_document(call.message.chat.id, mask_file)
        bot.answer_callback_query(call.id)

    elif call.data == 'user_count':
        cursor.execute('SELECT COUNT(*) FROM users')
        count = cursor.fetchone()[0]
        bot.answer_callback_query(call.id, text=f'В базе зарегистрировано: {count}')

    elif call.data == 'edit_ad':
        message = bot.send_message(call.message.chat.id, 'Напишите текст для рекламы:')
        bot.register_next_step_handler(message, save_ad_text)


@bot.message_handler(content_types=['document'])
def receive_mask_file(message):
    document_id = message.document.file_id
    file_info = bot.get_file(document_id)
    downloaded_file = bot.download_file(file_info.file_path)

    with open("mask.txt", "wb") as new_mask_file:
        new_mask_file.write(downloaded_file)


    bot.reply_to(message, 'Файл mask.txt успешно загружен и обновлен.')


def save_ad_text(message):
    ad_text = message.text
    cursor.execute('INSERT INTO ads (ad_text) VALUES (?)', (ad_text,))
    conn.commit()
    bot.send_message(message.chat.id, 'Текст рекламы сохранен.')


MAX_RESTART_ATTEMPTS = 999
restart_attempts = 0
restart_delay = 5

logging.basicConfig(level=logging.ERROR)


def start_polling():
    global restart_attempts
    while restart_attempts < MAX_RESTART_ATTEMPTS:
        try:
            bot.polling(none_stop=True)
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection error: {e}")
            time.sleep(restart_delay)
            restart_attempts += 1
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            time.sleep(restart_delay)
            restart_attempts += 1


if __name__ == '__main__':
    start_polling()
    if restart_attempts == MAX_RESTART_ATTEMPTS:
        logging.error("Reached maximum restart attempts. Exiting script.")