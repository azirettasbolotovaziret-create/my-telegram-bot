import telebot
import sqlite3
import threading

# Твой токен
TOKEN = '8638342831:AAEMgY7t4zyww76tvc-t-X3QZvw7oEgMpV0'
bot = telebot.TeleBot(TOKEN)

# Блокировка для защиты от багов при одновременных переводах (чтобы вещи не дюпались)
db_lock = threading.Lock()

def get_conn():
    # Подключение к локальной базе данных
    return sqlite3.connect('memegift.db', check_same_thread=False)

def init_db():
    """Создание таблиц, если они еще не созданы"""
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        # Таблица пользователей
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER PRIMARY KEY,
                        username TEXT
                    )''')
        # Таблица инвентаря (serial - уникальный номер, AUTOINCREMENT гарантирует, что номера не повторяются)
        c.execute('''CREATE TABLE IF NOT EXISTS nfts (
                        serial INTEGER PRIMARY KEY AUTOINCREMENT,
                        owner_id INTEGER,
                        name TEXT
                    )''')
        conn.commit()
        conn.close()

init_db()

@bot.message_handler(commands=['start', 'help'])
def start_cmd(message):
    """Регистрация пользователя и вывод инструкций (без бесплатных бонусов)"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    # Обновляем или добавляем пользователя в базу (чтобы знать его user_id по username)
    if username:
        with db_lock:
            conn = get_conn()
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO users (user_id, username) VALUES (?, ?)", (user_id, username))
            conn.commit()
            conn.close()
            
    text = (
        "👋 **Добро пожаловать в MEMEGIFT!**\n\n"
        "Здесь ты можешь хранить, коллекционировать и передавать эксклюзивные Telegram NFT.\n"
        "⚠️ *Обрати внимание:* все NFT находятся внутри этого бота и не могут быть выведены на внешние кошельки.\n\n"
        "📖 **Инструкция и команды:**\n"
        "👤 /profile — Твой профиль\n"
        "🎒 /inventory — Твой инвентарь (список NFT и их серийные номера)\n"
        "🎁 `/send @username номер` — Отправить NFT другому пользователю\n"
        "ℹ️ /help — Показать эту инструкцию"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['profile'])
def profile_cmd(message):
    """Вывод профиля пользователя"""
    user_id = message.from_user.id
    
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM nfts WHERE owner_id = ?", (user_id,))
        count = c.fetchone()[0]
        conn.close()
        
    username_text = f"@{message.from_user.username}" if message.from_user.username else "Без юзернейма"
    
    # Исключение для Aziret_User
    if message.from_user.username == "Aziret_User":
        nft_count_text = f"{count} (Обычных) + Бесконечность 'Scooby Doo'"
    else:
        nft_count_text = str(count)

    text = (
        "👤 **Твой профиль**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔹 **Юзернейм:** {username_text}\n"
        f"🔹 **ID:** `{user_id}`\n"
        f"🔹 **Количество NFT:** {nft_count_text}\n"
        "━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['inventory'])
def inventory_cmd(message):
    """Вывод инвентаря пользователя"""
    user_id = message.from_user.id
    username = message.from_user.username
    
    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT serial, name FROM nfts WHERE owner_id = ?", (user_id,))
        nfts = c.fetchall()
        conn.close()
        
    text = "🎒 **Твой инвентарь NFT:**\n\n"
    
    if not nfts and username != "Aziret_User":
        text += "У тебя пока пусто. 😔"
    else:
        for nft in nfts:
            text += f"🖼 **{nft[1]}** | Серийный номер: `{nft[0]}`\n"
            
    # Уникальная механика для Aziret_User
    if username == "Aziret_User":
        text += "\n👑 **Эксклюзивный инвентарь создателя:**\n"
        text += "🖼 **Scooby Doo (зелёный фон)** | Серийный номер: `scooby` (Бесконечно)\n"
        text += "\n💡 *Чтобы отправить бесконечный NFT, используй:* `/send @username scooby`"

    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['send'])
def send_cmd(message):
    """Механика безопасной передачи NFT"""
    args = message.text.split()
    
    if len(args) != 3:
        bot.reply_to(message, "❌ **Неверный формат!**\nИспользование: `/send @username серийный_номер`\nПример: `/send @durov 15`", parse_mode='Markdown')
        return
        
    target_username = args[1].replace('@', '')
    serial = args[2]

    with db_lock:
        conn = get_conn()
        c = conn.cursor()
        
        # Проверяем, существует ли получатель
        c.execute("SELECT user_id FROM users WHERE username = ?", (target_username,))
        target = c.fetchone()
        
        if not target:
            bot.reply_to(message, f"❌ Пользователь @{target_username} не найден. Убедись, что он запускал бота (/start).")
            conn.close()
            return
            
        target_id = target[0]
        
        # Защита от отправки самому себе
        if target_id == message.from_user.id:
            bot.reply_to(message, "❌ Ты не можешь отправить NFT самому себе!")
            conn.close()
            return
            
        # Логика бесконечных NFT для Aziret_User
        if message.from_user.username == "Aziret_User" and serial.lower() == "scooby":
            c.execute("INSERT INTO nfts (owner_id, name) VALUES (?, ?)", (target_id, "Scooby Doo (зелёный фон)"))
            new_serial = c.lastrowid
            conn.commit()
            
            bot.reply_to(message, f"✅ Ты успешно выдал эксклюзивный NFT **'Scooby Doo (зелёный фон)'** пользователю @{target_username}!\nУникальный номер сгенерирован: `{new_serial}`", parse_mode='Markdown')
            
            # Уведомление получателю
            try:
                bot.send_message(target_id, f"🎉 **ВАМ ПРИШЕЛ ПОДАРОК!**\n\nПользователь @{message.from_user.username} отправил вам NFT!\n\n🖼 **Название:** Scooby Doo (зелёный фон)\n🔢 **Серийный номер:** `{new_serial}`\n\nПроверьте свой /inventory!", parse_mode='Markdown')
            except:
                pass # Если юзер заблокировал бота
                
            conn.close()
            return
            
        # Логика для обычных NFT по серийному номеру
        if not serial.isdigit():
            bot.reply_to(message, "❌ Серийный номер должен быть числом!")
            conn.close()
            return
            
        serial_int = int(serial)
        
        # Строгая проверка: принадлежит ли этот NFT отправителю
        c.execute("SELECT serial, name FROM nfts WHERE serial = ? AND owner_id = ?", (serial_int, message.from_user.id))
        nft = c.fetchone()
        
        if not nft:
            bot.reply_to(message, "❌ У тебя нет NFT с таким серийным номером.")
            conn.close()
            return
            
        # Передаем NFT: меняем owner_id на ID получателя (пропадает у отправителя, появляется у получателя)
        c.execute("UPDATE nfts SET owner_id = ? WHERE serial = ?", (target_id, serial_int))
        conn.commit()
        
        bot.reply_to(message, f"✅ Ты успешно отправил NFT **'{nft[1]}'** (ID: `{serial_int}`) пользователю @{target_username}!", parse_mode='Markdown')
        
        # Уведомление получателю
        try:
            bot.send_message(target_id, f"🎉 **ВАМ ПРИШЕЛ ПОДАРОК!**\n\nПользователь @{message.from_user.username} отправил вам NFT!\n\n🖼 **Название:** {nft[1]}\n🔢 **Серийный номер:** `{serial_int}`\n\nПроверьте свой /inventory!", parse_mode='Markdown')
        except:
            pass
            
        conn.close()

# Запуск бота в режиме постоянного опроса
print("Бот MEMEGIFT успешно запущен!")
bot.infinity_polling()
      
