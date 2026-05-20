import asyncio
import os

from datetime import datetime, timezone
from vkbottle import Keyboard, KeyboardButtonColor, Text, OpenLink, Callback, GroupEventType
from vkbottle.bot import Bot, Message

from database import get_games, get_bookings, add_booking, update_booked_count, get_user_bookings, cancel_booking, \
    get_waiting_first, change_status, update_notified, delete_game, delete_booking
from apscheduler.schedulers.asyncio import AsyncIOScheduler

TOKEN = os.environ.get("VK_TOKEN")
bot = Bot(token=TOKEN)

def format_date(game: dict) -> str:
    dt = game.get('datetime')
    if not dt or not dt.get('formatted_date'):
        return "Дата не указана"
    return f'{dt['formatted_date']} (MSK, UTC+3)'


def get_game_by_id(games, game_id):
    return next((g for g in games if g.get("id") == game_id), None)

def main_keyboard():
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text("Расписание игр"), color=KeyboardButtonColor.PRIMARY)
    keyboard.add(Text("Моё расписание"), color=KeyboardButtonColor.PRIMARY)
    return keyboard.get_json()

def game_keyboard(game_id, announcement):
    keyboard = Keyboard(one_time=False)
    if announcement:
        keyboard.add(OpenLink(announcement, "Анонс"))
    keyboard.row()
    keyboard.add(
        Callback(
            f"Записаться",
            payload={
                "cmd": "book",
                "game_id": game_id
            }
        ),
        color=KeyboardButtonColor.POSITIVE)
    keyboard.add(
        Callback(
            "Назад",
            payload={"cmd": "back_to_schedule"}
        ),
        color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()

def user_game_keyboard(game_id, booking_id, announcement):
    keyboard = Keyboard(one_time=False)
    if announcement:
        keyboard.add(OpenLink(announcement, "Анонс"))
    keyboard.row()
    keyboard.add(
        Callback(
            f"Отменить запись",
            payload={
                "cmd": "cancel",
                "game_id": game_id,
                "booking_id": booking_id
            }
        ),
        color=KeyboardButtonColor.NEGATIVE)
    keyboard.add(
        Callback(
            "Назад",
            payload={"cmd": "back_to_personal"}
        ),
        color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()

def games_list_keyboard(games):
    keyboard = Keyboard(one_time=False)
    for game in games:
        name = game["name"][:40]
        game_id = game["id"]
        keyboard.add(
            Callback(
                name,
                payload={
                    "cmd": "select_game",
                    "game_id": game_id
                }
            )
        )
        keyboard.row()
    keyboard.add(Text("В главное меню"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()

def user_games_list_keyboard(games):
    keyboard = Keyboard(one_time=False)
    for game in games:
        name = game["name"][:40]
        keyboard.add(
            Callback(
                name,
                payload={
                    "cmd": "select_user_game",
                    "game_id": game["id"]
                }
            )
        )
        keyboard.row()
    keyboard.add(Text("В главное меню"), color=KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()

async def check_notifications():
    try:
        games = get_games()
        for game in games:
            raw_dt = game.get("datetime")
            if not raw_dt:
                continue
            dt = datetime.fromtimestamp(raw_dt['timestamp'], tz=timezone.utc)
            delta = dt - datetime.now(timezone.utc)
            if 0 < delta.total_seconds() <= 86400 and not game.get("notified_day", False):
                game_id = game.get("id")
                bookings = get_bookings(game_id)
                confirmed = [b for b in bookings if b.get("status") == "confirmed"]
                for b in confirmed:
                    await bot.api.messages.send(
                        user_id=b["vk_id"],
                        message=f"Вы записаны на игру {game['name']}, которая пройдет завтра в {format_date(game)} по адресу {game.get('place', 'не заполнено')}.",
                        random_id=0)
                update_notified(game["id"], "notified_day")
            elif 0 < delta.total_seconds() <= 7200 and not game.get("notified_hour", False):
                game_id = game.get("id")
                bookings = get_bookings(game_id)
                confirmed = [b for b in bookings if b.get("status") == "confirmed"]
                for b in confirmed:
                    await bot.api.messages.send(
                        user_id=b["vk_id"],
                        message=f"Вы записаны на игру {game['name']}, которая пройдет сегодня в {format_date(game)} по адресу {game.get('place', 'не заполнено')}.",
                        random_id=0)
                update_notified(game["id"], "notified_hour")
    except Exception as e:
        print("Ошибка в check_notifications:", e)

async def cleanup_old_games():
    try:
        games = get_games()
        now = datetime.now(timezone.utc)
        for game in games:
            raw_dt = game.get("datetime")
            if not raw_dt:
                continue
            dt = datetime.fromtimestamp(raw_dt['timestamp'], tz=timezone.utc)
            if (now - dt).total_seconds() > 3 * 86400:
                game_id = game.get("id")
                bookings = get_bookings(game_id)
                for b in bookings:
                    delete_booking(b["id"])
                delete_game(game_id)
    except Exception as e:
        print("Ошибка в cleanup_old_games:", e)


async def send_main_schedule(user_id: int):
    games = get_games()
    games_open = [g for g in games if g.get("is_open", False)]
    games_open = sorted(games_open, key=lambda g: g.get("timestamp", 0))
    response = "Доступные игры:\n\n"
    for game in games_open:
        response += f"🎲 {game['name']}\n"
        response += f"📜 {game.get('description', 'не заполнено')}\n"
        response += f"🕵️‍♂️ Мастер: {game.get('game_master', 'не заполнено')}\n"
        response += f"⚙️ Система: {game.get('system', 'не заполнена')}\n"
        response += f"💫 Формат: {game.get('format', 'не заполнено')}\n"
        response += f"📅 {format_date(game)}\n"
        booked = game.get("booked") or 0
        max_players = game.get("max_players") or 0
        if booked >= max_players:
            response += "Мест нет (лист ожидания).\n\n"
        else:
            response += f"Свободно мест: {max_players - booked}\n\n\n"
    await bot.api.messages.send(
        user_id=user_id,
        message=response,
        keyboard=games_list_keyboard(games_open),
        random_id=0)

async def handle_select_game(event: dict):
    payload = event["object"]["payload"]
    user_id = event["object"]["user_id"]
    game_id = payload.get("game_id")
    games = get_games()
    games_open = [g for g in games if g.get("is_open", False)]
    games_open = sorted(games_open, key=lambda g: g.get("timestamp", 0))
    game = get_game_by_id(games, game_id)
    if not game:
        await bot.api.messages.send(
            user_id=user_id,
            message="Игра не найдена.",
            keyboard=games_list_keyboard(games_open),
            random_id=0)
        return
    response = f"🎲 {game['name']}\n"
    response += f"📜 {game.get('description', 'не заполнено')}\n\n"
    response += f"🕵️‍♂️ Мастер: {game.get('game_master', 'не заполнено')}\n"
    response += f"⚙️ Система: {game.get('system', 'не заполнена')}\n"
    response += f"💫 Формат: {game.get('format', 'не заполнено')}\n"
    response += f"📅 {format_date(game)}\n"
    response += f"📌 Адрес: {game.get('place', 'не заполнено')}\n"
    response += f"💰 Стоимость: {game.get('price', 'бесплатно')}\n\n"
    booked = game.get("booked") or 0
    max_players = game.get("max_players") or 0
    if booked >= max_players:
        response += "Мест нет (лист ожидания).\n\n"
    else:
        response += f"Свободно мест: {max_players - booked}\n\n\n"
    bookings = get_bookings(game_id)
    confirmed = [b for b in bookings if b.get("status") == "confirmed"]
    waiting = [b for b in bookings if b.get("status") == "waiting"]
    if confirmed:
        response += "\nИгроки:\n"
        for b in confirmed:
            response += f"{b['player_name']} — {b['link']}\n"
        if waiting:
            response += "\nЛист ожидания:\n"
            for b in waiting:
                response += f"{b['player_name']} — {b['link']}\n"
    await bot.api.messages.send(
        user_id=user_id,
        message=response,
        keyboard=game_keyboard(game_id, game.get("announcement")),
        random_id=0)

async def handle_select_user_game(event: dict):
    payload = event["object"]["payload"]
    user_id = event["object"]["user_id"]
    game_id = payload.get("game_id")
    bookings = get_user_bookings(user_id)
    if not bookings:
        await bot.api.messages.send(
            user_id=user_id,
            message="Вы не записаны ни на одну игру.",
            keyboard=user_games_list_keyboard([]),
            random_id=0
        )
        return
    games = get_games()
    user_games = []
    for booking in bookings:
        game = next((g for g in games if g.get("id") == booking.get("game_id")), None)
        if game:
            user_games.append(game)
    game = get_game_by_id(games, game_id)
    if not game:
        await bot.api.messages.send(
            user_id=user_id,
            message="Игра не найдена.",
            keyboard=user_games_list_keyboard(user_games),
            random_id=0)
        return
    response = f"🎲 {game['name']}\n"
    response += f"📜 {game.get('description', 'не заполнено')}\n\n"
    response += f"🕵️‍♂️ Мастер: {game.get('game_master', 'не заполнено')}\n"
    response += f"⚙️ Система: {game.get('system', 'не заполнена')}\n"
    response += f"💫 Формат: {game.get('format', 'не заполнено')}\n"
    response += f"📅 {format_date(game)}\n"
    response += f"📌 Адрес: {game.get('place', 'не заполнено')}\n"
    response += f"💰 Стоимость: {game.get('price', 'бесплатно')}\n\n"
    booked = game.get("booked") or 0
    max_players = game.get("max_players") or 0
    if booked >= max_players:
        response += "Мест нет (лист ожидания).\n\n"
    else:
        response += f"Свободно мест: {max_players - booked}\n\n\n"
    bookings = get_bookings(game_id)
    booking = next((b for b in bookings if b.get("game_id") == game_id and b.get("vk_id") == user_id), None)
    if not booking:
        await bot.api.messages.send(
            user_id=user_id,
            message="Запись не найдена.",
            random_id=0)
        return
    confirmed = [b for b in bookings if b.get("status") == "confirmed"]
    waiting = [b for b in bookings if b.get("status") == "waiting"]
    if confirmed:
        response += "\nИгроки:\n"
        for b in confirmed:
            response += f"{b['player_name']} — {b['link']}\n"
        if waiting:
            response += "\nЛист ожидания:\n"
            for b in waiting:
                response += f"{b['player_name']} — {b['link']}\n"
    await bot.api.messages.send(
        user_id=user_id,
        message=response,
        keyboard=user_game_keyboard(game_id, booking["id"], game.get("announcement")),
        random_id=0
    )

async def handle_book(event: dict):
    payload = event["object"]["payload"]
    user_id = event["object"]["user_id"]
    game_id = payload.get("game_id")
    user_info = await bot.api.users.get(user_ids=user_id)
    player_name = f"{user_info[0].first_name} {user_info[0].last_name}"
    games = get_games()
    game = get_game_by_id(games, game_id)
    if not game:
        await bot.api.messages.send(user_id=user_id, message="Игра не найдена.", random_id = 0)
        return
    if not game.get("is_open", False):
        await bot.api.messages.send(user_id=user_id, message="Игра недоступна для записи.", random_id = 0)
        return
    existing = get_bookings(game_id)
    already_booked = any(b.get("vk_id") == user_id and b.get("status") in ("confirmed", "waiting") for b in existing)
    if already_booked:
        await bot.api.messages.send(user_id=user_id, message="Вы уже записаны на эту игру.", random_id = 0)
        return
    booked = game.get("booked") or 0
    max_players = game.get("max_players") or 0
    if booked >= max_players:
        add_booking(game_id, game["name"], user_id, player_name, status = "waiting")
        await bot.api.messages.send(
            user_id=user_id,
            message=f"{player_name}, все места заняты. Вы добавлены в лист ожидания.",
            random_id = 0)
        return
    add_booking(game_id, game["name"], user_id, player_name)
    update_booked_count(game["id"], booked + 1)
    await bot.api.messages.send(user_id=user_id, message=f"{player_name}, вы записаны на игру {game['name']}.", random_id = 0)

async def handle_back_to_schedule(event: dict):
    user_id = event["object"]["user_id"]
    games = get_games()
    games_open = [g for g in games if g.get("is_open", False)]
    games_open = sorted(games_open, key=lambda g: g.get("timestamp", 0))
    await bot.api.messages.send(
        user_id=user_id,
        message="Выберите игру:",
        keyboard=games_list_keyboard(games_open),
        random_id=0)

async def handle_cancel(event: dict):
    payload = event["object"]["payload"]
    booking_id = payload.get("booking_id")
    game_id = payload.get("game_id")
    user_id = event["object"]["user_id"]
    user_info = await bot.api.users.get(user_ids=user_id)
    player_name = f"{user_info[0].first_name} {user_info[0].last_name}"
    games = get_games()
    game = get_game_by_id(games, game_id)
    if not game:
        return
    booked = game.get("booked") or 0
    cancel_booking(booking_id)
    await asyncio.sleep(0.5)
    bookings = get_bookings(game_id)
    confirmed = [b for b in bookings if b.get("status") == "confirmed"]
    update_booked_count(game["id"], len(confirmed))
    await asyncio.sleep(0.5)
    waiting = get_waiting_first(game_id)
    await bot.api.messages.send(
        user_id=user_id,
        message=f"{player_name}, ваша запись на игру {game['name']} отменена.",
        random_id = 0)
    if not waiting:
        return
    change_status(waiting["id"], status = "confirmed")
    bookings = get_bookings(game_id)
    confirmed = [b for b in bookings if b.get("status") == "confirmed"]
    update_booked_count(game["id"], len(confirmed))
    await bot.api.messages.send(
        user_id=waiting["vk_id"],
        message=f"{waiting['player_name']}, ваша запись на игру {game['name']} подтверждена.",
        random_id = 0)

async def handle_back_to_personal(event: dict):
    user_id = event["object"]["user_id"]
    bookings = get_user_bookings(user_id)
    games = get_games()
    user_games = []
    for booking in bookings:
        game = get_game_by_id(games, booking.get("game_id"))
        if game:
            user_games.append(game)
    await bot.api.messages.send(
        user_id=user_id,
        message="Ваши игры:",
        keyboard=user_games_list_keyboard(user_games),
        random_id = 0
    )

async def handle_show_players(event: dict):
    payload = event["object"]["payload"]
    game_id = payload.get("game_id")
    user_id = event["object"]["user_id"]
    games = get_games()
    game = get_game_by_id(games, game_id)
    bookings = get_bookings(game_id)
    confirmed = [b for b in bookings if b.get("status") == "confirmed"]
    waiting = [b for b in bookings if b.get("status") == "waiting"]
    if not confirmed:
        await bot.api.messages.send(user_id=user_id, message="Записанных игроков нет.", random_id=0)
        return
    response = f"Игроки — {game['name']}:\n"
    for b in confirmed:
        response += f"{b['player_name']} — {b['link']}\n"
    if waiting:
        response += "\nЛист ожидания:\n"
        for b in waiting:
            response += f"{b['player_name']} — {b['link']}\n"
    await bot.api.messages.send(user_id=user_id, message=response, random_id=0)

@bot.on.raw_event(GroupEventType.MESSAGE_EVENT)
async def callback_handler(event: dict):
    await bot.api.messages.send_message_event_answer(
        event_id=event["object"]["event_id"],
        user_id=event["object"]["user_id"],
        peer_id=event["object"]["peer_id"],
    )
    payload = event["object"]["payload"]
    cmd = payload.get("cmd")
    if cmd == "select_game":
        await handle_select_game(event)
    elif cmd == "book":
        await handle_book(event)
    elif cmd == "back_to_schedule":
        await handle_back_to_schedule(event)
    elif cmd == "cancel":
        await handle_cancel(event)
    elif cmd == "select_user_game":
        await handle_select_user_game(event)
    elif cmd == "back_to_personal":
        await handle_back_to_personal(event)
    elif cmd == "show_players":
        await handle_show_players(event)

@bot.on.message(text=["Начать", "начать", "Старт", "старт", "start", "Start", "/start"])
async def start_handler(message: Message):
    await message.answer("🐦‍⬛ Добро пожаловать в Логово Кенку!", keyboard=main_keyboard())

@bot.on.message(text="В главное меню")
async def back_handler(message: Message):
    await message.answer("Главное меню", keyboard=main_keyboard())

@bot.on.message(text="К расписанию")
async def back_to_schedule_handler(message: Message):
    games = get_games()
    games_open = [g for g in games if g.get("is_open", False)]
    games_open = sorted(games_open, key=lambda g: g.get("timestamp", 0))
    await message.answer("Расписание игр", keyboard=games_list_keyboard(games_open))

@bot.on.message(text="К моему расписанию")
async def back_to_personal_schedule_handler(message: Message):
    user_id = message.from_id
    bookings = get_user_bookings(user_id)
    if not bookings:
        await message.answer("Вы не записаны ни на одну игру.")
        return
    games = get_games()
    user_games = []
    for booking in bookings:
        game = get_game_by_id(games, booking.get("game_id"))
        if game:
            user_games.append(game)
    await message.answer("Ваши игры:", keyboard=user_games_list_keyboard(user_games))

@bot.on.message(text="Расписание игр")
async def show_schedule(message: Message):
    await send_main_schedule(message.from_id)

@bot.on.message(text="Моё расписание")
async def personal_schedule(message: Message):
    user_id = message.from_id
    bookings = get_user_bookings(user_id)
    if not bookings:
        await message.answer("Вы не записаны ни на одну игру.")
        return
    games = get_games()
    user_games = []
    for booking in bookings:
        game = get_game_by_id(games, booking.get("game_id"))
        if game:
            user_games.append(game)
    response = "Ваши игры:\n\n"
    for game in user_games:
        response += f"🎲 {game['name']}\n"
        response += f"{game.get('description', 'не заполнено')}\n"
        response += f"Система: {game.get('system', 'не заполнена')}\n"
        response += f"📅 {format_date(game)}\n"
        response += f"Стоимость: {game.get('price', 'бесплатно')}\n\n\n"
    await message.answer(response, keyboard=user_games_list_keyboard(user_games))


scheduler = AsyncIOScheduler()

async def on_startup():

    scheduler.add_job(check_notifications, "interval", minutes=30)
    scheduler.add_job(cleanup_old_games, "interval", hours=24)
    scheduler.start()
    print("Scheduler started")

async def on_shutdown():
    scheduler.shutdown(wait=False)

bot.loop_wrapper.on_startup.append(on_startup())
bot.loop_wrapper.on_shutdown.append(on_shutdown())

def main():
    print("Бот запускается...")
    bot.run_forever()

if __name__ == "__main__":
    main()