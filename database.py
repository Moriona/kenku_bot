import os

from pyairtable import Api
from datetime import datetime, timezone

AIRTABLE_TOKEN = os.environ.get("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")
api = Api(AIRTABLE_TOKEN)
games_table = api.table(AIRTABLE_BASE_ID, "games")
bookings_table = api.table(AIRTABLE_BASE_ID, "bookings")

def get_games():
    records = games_table.all()
    return [{"id": record["id"], **record["fields"]} for record in records]

def get_bookings(game_id):
    #records = bookings_table.all()
    formula = f"{{game_id}} = '{game_id}'"
    records = bookings_table.all(formula=formula)
    return [{"id": r["id"], **r["fields"]} for r in records]
    #return [{"id": r["id"], **r["fields"]} for r in records if r["fields"].get("game_id") == game_id]

def get_waiting_first(game_id):
    #records = bookings_table.all()
    #waiting = [{"id": r["id"], **r["fields"]} for r in records if r["fields"].get("game_id") == game_id and r["fields"].get("status") == "waiting"]
    #if waiting:
        #return waiting[0]
    #return None
    formula = f"AND({{game_id}} = '{game_id}', {{status}} = 'waiting')"
    records = bookings_table.all(
        formula=formula,
        sort=["created_at"]  # или нужное поле сортировки
    )
    if records:
        r = records[0]
        return {"id": r["id"], **r["fields"]}
    return None


def add_booking(game_id, game_name, vk_id, player_name, status = "confirmed"):
    now_utc = datetime.now(timezone.utc).isoformat()
    bookings_table.create({
        "game_id": game_id,
        "game_name": game_name,
        "vk_id": vk_id,
        "player_name": player_name,
        "status": status,
        "link": f"vk.com/id{vk_id}",
        "created_at": now_utc
    })

def cancel_booking(booking_id, status="cancelled"):
    bookings_table.update(booking_id, {"status": status})

def change_status(booking_id, status):
    bookings_table.update(booking_id, {"status": status})

def update_booked_count(game_id, new_count):
    games_table.update(game_id, {"booked": new_count})

def update_notified(game_id, field):
    games_table.update(game_id, {field: True})

def get_user_bookings(vk_id):
    #records = bookings_table.all()
    #return [{"id": r["id"], **r["fields"]} for r in records if r["fields"].get("vk_id") == vk_id]
    formula = f"AND({{vk_id}} = {int(vk_id)}, {{status}} != 'cancelled')"
    records = bookings_table.all(formula=formula)
    return [{"id": r["id"], **r["fields"]} for r in records]