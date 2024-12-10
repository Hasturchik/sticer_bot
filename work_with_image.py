import random
import re
import string
import replicate
import aiohttp
from telebot.async_telebot import AsyncTeleBot
import cv2
import os
import asyncio
import uuid
from replicate import Client
bot_username = None
from constants import REPLICATE_API_TOKEN, TEMP_DIR, bot


async def apply_filter(template_path, user_photo_path, unique_id):
    """
    Обработка изображения с использованием Replicate.
    """
    client = Client(api_token=REPLICATE_API_TOKEN)
    try:
        with open(user_photo_path, "rb") as swap_image, open(template_path, "rb") as input_image:
            output = await client.async_run(
                "codeplugtech/face-swap:278a81e7ebb22db98bcba54de985d22cc1abeead2754eb1f2af717247be69b34",
                input={
                    "swap_image": swap_image,
                    "input_image": input_image,
                },
            )
        output_path = os.path.join(TEMP_DIR, f"processed_{unique_id}_{os.path.basename(template_path)}")
        output = str(output)
        await download_replicate_image(output, output_path)
        return output_path
    except Exception as e:
        raise Exception(f"Ошибка обработки шаблона {template_path}: {e}")


async def download_replicate_image(url, output_path):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"Ошибка загрузки изображения с Replicate: {url}")
            with open(output_path, "wb") as f:
                f.write(await response.read())


async def delete_temp_files(*files):
    for file in files:
        if os.path.exists(file):
            os.remove(file)


async def generate_sticker_pack(image_paths, chat_id, unique_id, bot_username):
    """
    Генерация набора стикеров из обработанных изображений.
    """
    stickers = []
    sticker_set_name = f"user_{chat_id}_{unique_id}_stickers"
    sticker_set_name = re.sub(r'[^a-zA-Z0-9_]', '_', sticker_set_name) + f"_by_{bot_username}"
    if len(sticker_set_name) >= 63:
        sticker_set_name = sticker_set_name[-63:]
    if not sticker_set_name[0].isalpha():
        random_letter = random.choice(string.ascii_letters)
        sticker_set_name = random_letter + sticker_set_name[1:]
    title = f"Stickers by {chat_id}"

    # Проверка, существует ли уже стикер-пак
    try:
        await bot.get_sticker_set(sticker_set_name)
        is_new_set = False
    except Exception:
        is_new_set = True
    # Генерация стикеров
    for idx, image_path in enumerate(image_paths):
        sticker_path = os.path.join(TEMP_DIR, f"sticker_{chat_id}_{unique_id}_{idx}.webp")
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Ошибка при чтении изображения {image_path}")

        resized_image = cv2.resize(image, (512, 512))
        cv2.imwrite(sticker_path, resized_image)
        await delete_temp_files(image_path)

        with open(sticker_path, "rb") as sticker_file:
            if is_new_set:
                # Создаем новый набор стикеров
                await bot.create_new_sticker_set(
                    user_id=chat_id,
                    name=sticker_set_name,
                    title=title,
                    png_sticker=sticker_file,
                    emojis=["😀"]
                )
                is_new_set = False
            else:
                # Добавляем стикер в существующий набор
                await bot.add_sticker_to_set(
                    user_id=chat_id,
                    name=sticker_set_name,
                    png_sticker=sticker_file,
                    emojis=["😀"]
                )
        stickers.append(sticker_path)
        sticker_set_url = f"https://t.me/addstickers/{sticker_set_name}"

    return sticker_set_url, stickers