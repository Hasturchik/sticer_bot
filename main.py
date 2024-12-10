import random
import re
import string

import aiohttp
from telebot.async_telebot import AsyncTeleBot
import cv2
import os
import asyncio
import uuid
from replicate import Client
bot_username = None
from constants import TEMP_DIR, bot, ADMINS_ID

from work_with_image import apply_filter, delete_temp_files, generate_sticker_pack
import admin_handlers

# Папка для сохранения временных файлов
os.makedirs(TEMP_DIR, exist_ok=True)

user_data = {}
async def is_participant(message):
    from admin_handlers import CHANNELS_LIST
    missing_channels = []  # Список каналов, на которые пользователь не подписан

    for channel in CHANNELS_LIST:
        try:
            member = await bot.get_chat_member(channel, message.from_user.id)
        except Exception as e:
            error_message = str(e)

            if "Bad Request: member list is inaccessible" in error_message or 'bot was kicked from the channel chat' in error_message:
                for admin in ADMINS_ID:
                    await bot.send_message(
                        admin,
                        f"⚠️ <b>Проблема с чатом</b> {channel}\n\n"
                        "Бот потерял админ-права или доступ к этому чату.\n"
                        "👉 Пожалуйста, <b>удалите чат из списка проверяемых</b> "
                        "или свяжитесь с его администрацией.\n\n"
                        "Бот будет напоминать, пока одно из условий не выполнится. 😊",
                        parse_mode="HTML"
                    )
            else:
                await bot.send_message(message.chat.id, f"⚠️ Ошибка: {e}")
            continue

        if member.status == "left":  # Если пользователь не подписан
            missing_channels.append(channel)

    # Если есть каналы, на которые пользователь не подписан
    if missing_channels:
        channels_links = "\n".join(
            [f"👉 <a href='https://t.me/{channel.lstrip('@')}'>{channel}</a>" for channel in missing_channels]

        )
        await bot.send_message(
            message.chat.id,
            f"❌ <b>Присоединение к каналам</b>\n\n"
            "Вы не подписаны на следующие каналы:\n\n"
            f"{channels_links}\n\n"
            "👉 Пожалуйста, подпишитесь на них, чтобы продолжить пользоваться ботом! 😊",
            parse_mode="HTML"
        )
        return False

    return True

# Обработчик команды /start
@bot.message_handler(commands=['start'])
async def start_message(message):
    participant = await is_participant(message)
    if participant == False:
        return
    await bot.send_message(
            message.chat.id,
            "Привет! Отправь мне своё фото, и я создам стикеры с твоим лицом!"
        )


@bot.message_handler(content_types=['text'])
async def handle_text(message):
    user_id = message.chat.id
    text = message.text.strip().upper()

    if user_id in user_data and user_data[user_id].get('awaiting_gender'):
        if text in ['М', 'Ж']:
            user_data[user_id]['gender'] = text
            user_data[user_id]['awaiting_gender'] = False
            await bot.send_message(user_id, "Спасибо! Теперь отправьте своё фото для обработки.")
        else:
            await bot.send_message(user_id, "Пожалуйста, укажите 'М' для мужского или 'Ж'")

# Обработчик фотографий
@bot.message_handler(content_types=['photo'])
async def handle_photo(message):
    if message.chat.type != 'private':
        await bot.send_message(message.chat.id, 'Эта команда доступна только в личных сообщениях.')
        return

    participant = await is_participant(message)
    if participant == False:
        return

    user_id = message.chat.id
    # Спрашиваем пол пользователя, если он ещё не указан
    if user_id not in user_data or 'gender' not in user_data[user_id]:
        await bot.send_message(
            user_id,
            "Какой у вас пол? Напишите 'М' для мужского или 'Ж' для женского."
        )
        user_data[user_id] = {'awaiting_gender': True}
        return

    # Проверяем, был ли указан пол
    if user_data[user_id].get('awaiting_gender'):
        await bot.send_message(
            user_id,
            "Пожалуйста, укажите свой пол, написав 'М' или 'Ж', перед отправкой фото."
        )
        return

    unique_id = str(uuid.uuid4())  # Уникальный идентификатор для каждого запроса
    try:
        # Скачиваем фото пользователя
        file_id = message.photo[-1].file_id
        file_info = await bot.get_file(file_id)
        downloaded_file = await bot.download_file(file_info.file_path)
        user_photo_path = os.path.join(TEMP_DIR, f"user_{message.chat.id}_{unique_id}.jpg")

        with open(user_photo_path, "wb") as file:
            file.write(downloaded_file)

        await bot.send_message(message.chat.id, "Фото получено! Начинаю обработку...")

        gender = user_data[user_id]['gender']
        template_dir = "template_sticer_M" if gender == 'М' else "template_sticer_W"
        templates = [os.path.join(template_dir, f) for f in os.listdir(template_dir) if f.endswith(('.jpg', '.png', '.webp'))]

        # Обрабатываем шаблоны параллельно
        tasks = [
            apply_filter(template, user_photo_path, unique_id)
            for template in templates
        ]
        try:
            processed_photo_paths = await asyncio.gather(*tasks)
        except Exception as e:
            await bot.send_message(message.chat.id, e)
            return

        # Генерация стикеров
        sticker_pack_url, stickers_paths = await generate_sticker_pack(processed_photo_paths, message.chat.id, unique_id, bot_username)

        await bot.send_message(message.chat.id, sticker_pack_url)

        # Удаление временных файлов
        await delete_temp_files(user_photo_path, *stickers_paths)

    except Exception as e:
        await bot.send_message(message.chat.id, f"Произошла ошибка: {e}")



async def main():
    global bot_username  # Указываем, что будем использовать глобальную переменную
    bot_info = await bot.get_me()
    bot_username = bot_info.username  # Получаем юзернейм без символа @
    print(f'bot {bot_username} started')
    await bot.infinity_polling()

if __name__ == "__main__":
    asyncio.run(main())