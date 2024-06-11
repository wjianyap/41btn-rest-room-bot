import re, os, json, datetime
from aiogram import types, BaseMiddleware
from aiogram.fsm.state import State, StatesGroup
from email_validator import validate_email, EmailNotValidError
from dotenv import load_dotenv

load_dotenv()

ADMIN_USERS_STR = os.getenv("ADMIN_USERS")
ADMIN_USERS = json.loads(ADMIN_USERS_STR)

class AccessControlMiddleware(BaseMiddleware):
    def __init__(self, allowed_users):
        super().__init__()
        self.allowed_users = allowed_users

    async def __call__(self, handler, event: types.Message, data):
        if event.from_user.id not in self.allowed_users:
            print(
                f"Unauthorized access denied for {event.from_user.username} with ID of: {event.from_user.id}"
            )
            await event.answer(f"You are not authorized to use this bot.")
            return
        return await handler(event, data)
    
class Booking(StatesGroup):
    user_id = State()
    date = State()
    start_time = State()
    end_time = State()
    time_period = State()
    rank_name = State()
    contact_number = State()
    company = State()
    reason = State()
    confirmation = State()
    company_for_view = State()

def is_valid_time_format(time_str):
    if len(time_str) != 4:
        return None
    try:
        hours = int(time_str[:2])
        minutes = int(time_str[2:])
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return True
        else:
            return False
    except ValueError:
        return False

def is_valid_contact_number(contact_number):
    if re.match(r"^[3689]\d{7}$", contact_number):
        return True
    else:
        return False

def is_valid_email(email):
    try:
        # Validate.
        v = validate_email(email)
        # Replace with normalized form.
        email = v["email"]
        return True
    except EmailNotValidError as e:
        # Email is not valid, exception message is human-readable
        print(str(e))
        return False
    
def print_summary(data):
    day_of_week = data["date"].strftime("%A")
    date = data['date'].strftime("%d/%m/%Y")
    return (
            f"Booking Details\n"
            f"================\n"
            f"Facility: 41SAR Btn Rest Room\n"
            f"Date: {date} ({day_of_week})\n"
            f"Time: {data['time_period']}\n"
            f"Rank and Name: {data['rank_name']}\n"
            f"Contact Number: {data['contact_number']}\n"
            f"Company: {data['company']}\n"
            f"Reason: {data['reason']}\n"
    )

def print_summary_viewBooking(data):
    data["date"] = datetime.datetime.strptime(data["date"], "%m/%d/%Y")
    day_of_week = data["date"].strftime("%A")
    date = data['date'].strftime("%d/%m/%Y")
    return (
            f"Date: {date} ({day_of_week})\n"
            f"Time: {data['time_period']}\n"
            f"Rank and Name: {data['rank_name']}\n"
            f"Contact Number: {data['contact_number']}\n"
            f"Reason: {data['reason']}"
    )


def is_admin(user_id):
    for key in ADMIN_USERS.keys():
        key = int(key)
        if user_id == key:
            return True
    return False

def get_admin_id_username(user_id):
    for key, value in ADMIN_USERS.items():
        key = int(key)
        if user_id == key:
            admin_id = key
            admin_name = value
    return admin_id, admin_name

def all_admin_id():
    admin_id_list = []
    for key in ADMIN_USERS.keys():
        admin_id_list.append(int(key))
    return admin_id_list

