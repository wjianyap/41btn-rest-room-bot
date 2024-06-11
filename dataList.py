from aiogram import types

company_list = [
    "FALCON",
    "GLORY",
    "HAWK",
    "SHRIKE",
    "HERON"
]

commands = [
    types.BotCommand(command="/start", description="Start the bot"),
    types.BotCommand(command="/new_booking", description="Create new booking"),
    types.BotCommand(command="/view_booking", description="View your booking"),
    types.BotCommand(command="/help", description="Get help"),
    types.BotCommand(command="/about", description="About the bot")
]