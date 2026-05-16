import os
import requests
from datetime import datetime, timezone

TABRIKA_TOKEN = os.environ.get("TABRIKA_TOKEN")
GAMES_TABLE_ID = os.environ.get("GAMES_TABLE_ID")
BOOKINGS_TABLE_ID = os.environ.get("BOOKINGS_TABLE_ID")
DATABASE_ID = os.environ.get("DATABASE_ID")

def get_games():
    response = requests.get(
        "https://api.tabrica.ru/public/record/list",
        params={
            'database_id': DATABASE_ID,
            'table_id': GAMES_TABLE_ID,
            'response_format': 'names'
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )

    data = response.json()
    records = data['data']['records']
    return [r for r in records if r.get('name')]


def get_bookings(game_id):
    response = requests.get(
        "https://api.tabrica.ru/public/record/list",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'where': f'(game_id,eq,{game_id})',
            'response_format': 'names'
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )
    data = response.json()
    records = data['data']['records']
    return records

def get_waiting_first(game_id):
    response = requests.get(
        "https://api.tabrica.ru/public/record/list",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'where': f'(game_id,eq,{game_id})~and(status,eq,waiting)',
            'response_format': 'names'
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )
    data = response.json()
    records = data['data']['records']
    if records:
        return records[0]
    return None

def add_booking(game_id, game_name, vk_id, player_name, status = "confirmed"):
    response = requests.post(
        "https://api.tabrica.ru/public/record/create",
        params= {
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID
        },
        json={
            "data": {
                'game_id': game_id,
                'game_name': game_name,
                'vk_id': vk_id,
                'player_name': player_name,
                'status': status,
                'link': f"vk.com/id{vk_id}",
                'created_at': datetime.now(timezone.utc).isoformat()}
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )
    print(response.status_code)
    print(response.json())

def cancel_booking(booking_id, status="cancelled"):
    response = requests.put(
        "https://api.tabrica.ru/public/record/update",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'row_id': booking_id},
        json={
            'data': {
                'status': status
            }
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )
    print(response.status_code)
    print(response.json())

def change_status(booking_id, status):
    response = requests.put(
        "https://api.tabrica.ru/public/record/update",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'row_id': booking_id
        },
        json = {
            'data': {
                'status': status
            }
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )

def update_booked_count(game_id, new_count):
    response = requests.put(
        "https://api.tabrica.ru/public/record/update",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'row_id': game_id
        },
        json={
            'data': {
                'booked': new_count
            }
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )

def update_notified(game_id, field):
    response = requests.put(
        "https://api.tabrica.ru/public/record/update",
        params={
            'database_id': DATABASE_ID,
            'table_id': GAMES_TABLE_ID,
            'row_id': game_id
        },
        json={
            'data': {
                field: True
            }
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )

def get_user_bookings(vk_id):
    response = requests.get(
        "https://api.tabrica.ru/public/record/list",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'where': f'(vk_id,eq,{vk_id})~and(status,eq,confirmed)',
            'response_format': 'names'
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )
    data = response.json()
    records = data['data']['records']
    return records

def delete_game(game_id):
    response = requests.delete(
        "https://api.tabrica.ru/public/record/delete",
        params={
            'database_id': DATABASE_ID,
            'table_id': GAMES_TABLE_ID,
            'row_id': game_id
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )

def delete_booking(booking_id):
    response = requests.delete(
        "https://api.tabrica.ru/public/record/delete",
        params={
            'database_id': DATABASE_ID,
            'table_id': BOOKINGS_TABLE_ID,
            'row_id': booking_id
        },
        headers={
            'Authorization': f'Bearer {TABRIKA_TOKEN}'
        }
    )