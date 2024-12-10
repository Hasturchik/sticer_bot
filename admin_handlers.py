import functools

from constants import bot, ADMINS_ID, CHANNELS_LIST
def admin_only(func):
    @functools.wraps(func)
    async def wrapper(message, *args, **kwargs):
        if str(message.from_user.id) in ADMINS_ID:
            return await func(message, *args, **kwargs)
        else:
            # Вы можете отправить сообщение пользователю, что команда доступна только в ЛС
            await bot.send_message(message.chat.id, 'Эта команда доступна только в личных сообщениях.')
            return
    return wrapper


@bot.message_handler(commands=['admin'])
async def start_message(message):
    if str(message.from_user.id) in ADMINS_ID:
        await bot.send_message(
            message.chat.id,
            (
                "Привет! Введи команду:\n\n"
                "1. `/set_channel @имя_канала` — чтобы добавить канал для проверки.\n"
                "2. `/delete_channel @имя_канала` — чтобы удалить канал из списка для проверки.\n\n"
                "Например, для канала с ссылкой https://t.me/test введи: `/set_channel @test`."
            ),
            parse_mode="Markdown"
        )
    else:
        await bot.send_message(
            message.chat.id,
            "Привет! Ты не админ"
        )


@admin_only
@bot.message_handler(commands=['set_channel'])
async def start_message(message):

    message_text = message.text.replace("/set_channel", "").strip()

    try:

        chat_admins = await bot.get_chat_administrators(message_text)

    except Exception as e:

        error_message = str(e)

        if "Bad Request: member list is inaccessible" in error_message:
            await bot.send_message(message.chat.id, 'Бот не админ в этом чате. Ему нужны админ права, иначе никак :)')
            return

        elif "Bad Request: chat not found" in error_message:
            await bot.send_message(message.chat.id, 'Чат вообще не существует. Кажется кто-то ошибся :)')
            return

        await bot.send_message(message.chat.id, f'Ошибка {e}')

        return

    try:
        bot_info = await bot.get_me()
        bot_id = bot_info.id

        if bot_id not in [admin.user.id for admin in chat_admins]:
            await bot.send_message(message.chat.id, 'Бот не админ в этом чате')
            return

        CHANNELS_LIST.append(message_text)

        await bot.send_message(message.chat.id, 'Успех!')

    except Exception as e:

        await bot.send_message(message.chat.id, f'Ошибка {e}')


@admin_only
@bot.message_handler(commands=['delete_channel'])
async def start_message(message):
    message_text = message.text.replace("/delete_channel", "").strip()
    try:
        CHANNELS_LIST.remove(message_text)
        await bot.send_message(message.chat.id, 'Успех!')
    except Exception as e:
        await bot.send_message(message.chat.id, f'Ошибка {e}')
