import asyncio, logging, sys, os, gspread, json, uuid
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback, get_user_locale
from aiogram.fsm.context import FSMContext
from aiogram.enums.parse_mode import ParseMode
from dotenv import load_dotenv

from functions import AccessControlMiddleware, Booking, is_valid_time_format,\
    is_valid_contact_number, is_valid_email, print_summary, print_summary_viewBooking, is_admin, \
        get_admin_id_username, all_admin_id
from dataList import company_list, commands

load_dotenv()

TOKEN_API = os.getenv("TOKEN_API")
GSHEET_KEY_ID = os.getenv("GSHEET_KEY_ID")
ALLOWED_USERS = json.loads(os.environ['ALLOWED_USERS'])
gSheet_credentials_str = os.getenv("GSHEET_CREDENTIALS")
gSheet_credentials = json.loads(os.getenv("GSHEET_CREDENTIALS"))
booking_requests = {}

bot = Bot(token=TOKEN_API)
dp = Dispatcher()

dp.message.middleware(AccessControlMiddleware(ALLOWED_USERS))

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    main_menu_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="New Booking")],
        [KeyboardButton(text="View Booking")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
    )
    await message.reply("What would you like to do?", reply_markup=main_menu_kb)

@dp.message(lambda message: "new booking" in message.text.lower() or "/new_booking" in message.text.lower())
async def new_booking_handler(message: types.Message, state: FSMContext):       
    await state.set_state(Booking.user_id)
    await state.update_data(user_id=message.from_user.id)
    await state.set_state(Booking.date)
    await message.answer(
        "Please select the date of booking",
        reply_markup=await SimpleCalendar().start_calendar(),
    )

@dp.callback_query(SimpleCalendarCallback.filter(), Booking.date)
async def date_handler(call: CallbackQuery, callback_data: dict, state: FSMContext):
    calendar = SimpleCalendar()
    calendar.set_dates_range(datetime.now() - timedelta(days=1), datetime(2025, 12, 31))
    selected, date = await calendar.process_selection(call, callback_data)
    if selected:
        await state.update_data(date=date)
        await state.set_state(Booking.start_time)
        await call.message.reply(
            f'You selected {date.strftime("%d/%m/%Y")}. \nPlease enter the start time of booking (hhmm)'
        )

@dp.message(Booking.start_time)
async def start_time_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if is_valid_time_format(message.text):
        data['start_time'] = datetime.strptime(message.text, "%H%M").time().strftime("%H:%M")
    
        # If the selected date is today, check if the user's time is not before the current time
        if data['date'].date() == datetime.now().date() and data['start_time'] < datetime.now().time().strftime("%H:%M"):
            await message.reply(f"Invalid time!\n"
                                f"Start time cannot be before the current time. "
                                f"Please enter the start time of booking (hhmm)")
            return

        await state.update_data(start_time=data['start_time'])
        await state.set_state(Booking.end_time)
        await message.reply("Please enter the end time of booking (hhmm)")
    else:
        await message.reply("Invalid time format. Please enter the start time of booking (hhmm)")


@dp.message(Booking.end_time)
async def end_time_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if is_valid_time_format(message.text):
        data['end_time'] = datetime.strptime(message.text, "%H%M").time().strftime("%H:%M")

        if data['end_time'] <= data['start_time']:
                await message.reply("End time cannot be before the start time or the same as the start time. Please re-enter the end time.")
                await state.set_state(Booking.end_time)
                return

        await state.update_data(end_time=data['end_time'])
        await state.set_state(Booking.time_period)
        data["date"] = data["date"].strftime("%m/%d/%Y")

        time_period_obj = f"{data['start_time']}-{data['end_time']}"
        await state.update_data(time_period=time_period_obj)
        await state.set_state(Booking.rank_name)

        booked = False
        for values in existing_booking[1:]:
            if data['date'] == values[1]:
                if (data["start_time"]<values[3] and data["end_time"]>values[2]):
                    await message.reply(f"Rest Room has been already booked by {values[7]} on {values[1]}, from {values[2]} to {values[3]}. Please select another time slot.")
                    booked = True
                    break
        if booked:
            await state.set_state(Booking.date)  
            await message.reply("Please select another date or time of booking", reply_markup=await SimpleCalendar().start_calendar())
        else:
            await message.reply("Please enter your rank and name (E.g. 3SG XXX)")
    else:
            await message.reply("Invalid time format. Please enter the end time of booking (hhmm)")

@dp.message(Booking.rank_name)
async def rank_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(rank_name=message.text)
    await state.set_state(Booking.contact_number)
    await message.reply("Please enter your contact number (SG number only)")

@dp.message(Booking.contact_number)
async def contact_number_handler(message: types.Message, state: FSMContext):
    if is_valid_contact_number(message.text):
        await state.update_data(contact_number=message.text)
        await state.set_state(Booking.company)
        company_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=company) for company in company_list[i : i + 3]]
                for i in range(0, len(company_list), 3)
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await message.reply("Please select the company", reply_markup=company_keyboard)
    else:
        await message.reply(
            "Invalid contact number. Please enter a valid contact number"
        )

@dp.message(Booking.company)
async def company_handler(message: types.Message, state: FSMContext):
    await state.update_data(company=message.text)
    await state.set_state(Booking.reason)
    await message.reply("Please enter the reason for booking")

@dp.message(Booking.reason)
async def reason_handler(message: types.Message, state: FSMContext):
    await state.update_data(reason=message.text)
    data = await state.get_data()
    await state.set_state(Booking.confirmation)
    await message.reply(print_summary(data)+"\nConfirm booking?",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Yes"), KeyboardButton(text="No")]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

@dp.message(lambda message: message.text.lower() == "yes", Booking.confirmation)
async def confirmation_handler(message: types.Message, state: FSMContext):
    data = await state.get_data() 
    
    # Generate a unique identifier for this booking request
    booking_id = str(uuid.uuid4())
    booking_requests[booking_id] = {"data": data, "processed": False, "message_ids": {}}
    booking_request = (f"New booking request from {data['company']}\n\n"+print_summary(data)+"\n\n")

    if not is_admin(message.from_user.id):
        inline_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Approve", callback_data=f"approve_{booking_id}"),
            InlineKeyboardButton(text="Reject", callback_data=f"reject_{booking_id}")],
        ])

        for admin_id in all_admin_id():
            try:
                sent_message = await bot.send_message(admin_id, booking_request, reply_markup=inline_kb)
                booking_requests[booking_id]["message_ids"][admin_id] = sent_message.message_id
            except Exception as e:
                logging.error(f"Error sending message to admin {admin_id}: {e}")

        await message.reply(
            f"Your booking request has been sent for approval. You will be notified once it is reviewed.\n\n"+print_summary(data)
        )
    else:
        data["date"] = data["date"].strftime("%m/%d/%Y")
        worksheet.append_row(list(data.values()), value_input_option="USER_ENTERED")
        global existing_booking
        existing_booking = worksheet.get_all_values()
    await state.clear()
    await start_handler(message) 

@dp.callback_query(lambda call: call.data.startswith("approve_"))
async def approve_booking(call: CallbackQuery):
    booking_id = call.data.split("_")[1]
    booking_info = booking_requests.get(booking_id)

    if booking_info and not booking_info["processed"]:
        data = booking_info["data"]
        booking_info["processed"] = True

        for admin_id, message_id in booking_info["message_ids"].items():
            try:
                await bot.edit_message_reply_markup(admin_id, message_id, reply_markup=None)
            except Exception as e:
                logging.error(f"Error removing inline keyboard for admin {admin_id}: {e}")

        approval_message = f"Booking approved by {get_admin_id_username(call.from_user.id)[1]}\n\n{print_summary(data)}"
        
        for admin_id in all_admin_id():
            await bot.send_message(admin_id, approval_message)

        user_message = (
            f"Your booking has been *APPROVED* by {get_admin_id_username(call.from_user.id)[1]}!\n\n{print_summary(data)}"
        )
        await bot.send_message(data['user_id'], user_message, parse_mode=ParseMode.MARKDOWN)   

        data["date"] = data["date"].strftime("%m/%d/%Y")
        worksheet.append_row(list(data.values()), value_input_option="USER_ENTERED")
        global existing_booking
        existing_booking = worksheet.get_all_values()

        await call.answer("Booking approved")
    else:
        await call.answer("Booking not found")

    await start_handler(call.message) 


@dp.callback_query(lambda call: call.data.startswith("reject_"))
async def reject_booking(call: CallbackQuery):
    booking_id = call.data.split("_")[1]
    booking_info = booking_requests.get(booking_id)

    if booking_info and not booking_info["processed"]:
        data = booking_info["data"]
        booking_info["processed"] = True
        
        for admin_id, message_id in booking_info["message_ids"].items():
            try:
                await bot.edit_message_reply_markup(admin_id, message_id, reply_markup=None)
            except Exception as e:
                logging.error(f"Error removing inline keyboard for admin {admin_id}: {e}")

        rejection_message = f"Booking rejected by {get_admin_id_username(call.from_user.id)[1]}\n\n{print_summary(data)}"

        for admin_id in all_admin_id():
            await bot.send_message(admin_id, rejection_message)

        user_message = (
            f"Your booking request has been *REJECTED* by {get_admin_id_username(call.from_user.id)[1]}.\n\n{print_summary(data)}"
        )
        await bot.send_message(data['user_id'], user_message, parse_mode=ParseMode.MARKDOWN)

        await call.answer("Booking rejected")
    else:
        await call.answer("Booking not found")
    
    await start_handler(call.message) 
    
@dp.message(lambda message: message.text.lower() == "no", Booking.confirmation)
async def no_confirmation_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await start_handler(message)

@dp.message(lambda message: "view booking" in message.text.lower() or "/view_booking" in message.text.lower())
async def view_booking_handler(message: types.Message, state: FSMContext):
    await state.set_state(Booking.company_for_view)
    company_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=company) for company in company_list[i : i + 3]]
            for i in range(0, len(company_list), 3)
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await message.reply("Please select your company", reply_markup=company_keyboard)

@dp.message(Booking.company_for_view)
async def company_for_view_handler(message: types.Message, state: FSMContext):
    company = message.text
    existing_booking = worksheet.get_all_values()
    user_bookings = [row for row in existing_booking[1:] if row[7] == company if (row[7] == company) and (datetime.strptime(row[1], "%m/%d/%Y") >= datetime.now())]
    if not user_bookings:
        await message.reply(f"No bookings found for {company}.")
    else:
        booking_details = "\n\n".join([print_summary_viewBooking(dict(zip(existing_booking[0], booking))) for booking in user_bookings])
        await message.reply(f"41Btn Rest Room Booking for {company}:\n{booking_details}")
    
    await state.clear()
    await start_handler(message)

@dp.message(lambda message: message.text.lower() == "/help")
async def help_handler(message: types.Message):
    await message.answer(f"This is the help handler\n" f"help")


@dp.message(lambda message: message.text.lower() == "/about")
async def about_handler(message: types.Message):
    await message.answer(f"This is the about handler")


@dp.message(lambda message: message.text.lower() == "/end")
async def end_handler(message: types.Message):
    await message.answer(
        f"Ending previous command...\n"
        f"Anything else I can do for you?\n\n"
        f"Please type /start to start again."
    )


async def main() -> None:
    global worksheet, existing_booking
    # open google sheets using credentials
    gc = gspread.service_account_from_dict(gSheet_credentials)
    sh = gc.open_by_key(GSHEET_KEY_ID)
    worksheet = sh.worksheet("BtnRestRoom_Booking_Details")
    existing_booking = worksheet.get_all_values()
    logging.info("Existing bookings fetched and stored in memory")
    await bot.set_my_commands(commands)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())