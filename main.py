from telegram.ext import Updater, CommandHandler, CallbackContext, MessageHandler, Filters
from telegram import Update, ChatMember, MessageEntity
import datetime
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

# File to store the last activity data
ACTIVITY_FILE = "activity_data.json"


def load_activity_data():
    try:
        with open(ACTIVITY_FILE, 'r') as file:
            data = json.load(file)
            return {int(user_id): {'date': datetime.datetime.fromisoformat(item['date']), 'username': item['username']}
                    for user_id, item in data.items()}
    except FileNotFoundError:
        return {}


def save_activity_data(activity_data):
    with open(ACTIVITY_FILE, 'w') as file:
        data = {str(user_id): {'date': item['date'].isoformat(), 'username': item['username']} for user_id, item in
                activity_data.items()}
        json.dump(data, file)


# Load the last activity data from the file
last_activity = load_activity_data()


def is_user_admin(update: Update, context: CallbackContext) -> bool:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    chat_member = context.bot.get_chat_member(chat_id, user_id)
    return chat_member.status in [ChatMember.ADMINISTRATOR, ChatMember.CREATOR]


def track_activity(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name
    last_activity[user_id] = {'date': datetime.datetime.utcnow(), 'username': username}
    save_activity_data(last_activity)


def track_new_members(update: Update, context: CallbackContext) -> None:
    new_members = update.message.new_chat_members
    for member in new_members:
        user_id = member.id
        username = member.username or member.first_name
        last_activity[user_id] = {'date': datetime.datetime.utcnow(), 'username': username}
    save_activity_data(last_activity)


def ban_or_kick(update: Update, context: CallbackContext) -> None:
    if not is_user_admin(update, context):
        update.message.reply_text("You are not authorized to use this command.")
        return

    args = context.args
    if len(args) != 2 or args[0] not in ['ban', 'kick'] or not args[1].isdigit():
        update.message.reply_text("Usage: /(ban|kick) <number_of_days>")
        return

    action, days = args[0], int(args[1])
    now = datetime.datetime.utcnow()

    for user_id, item in last_activity.items():
        if (now - item['date']).days >= days:
            if action == 'kick':
                context.bot.kick_chat_member(update.message.chat_id, user_id, until_date=now)
                context.bot.unban_chat_member(update.message.chat_id, user_id)
            else:
                context.bot.kick_chat_member(update.message.chat_id, user_id,
                                             until_date=now + datetime.timedelta(days=days))
            update.message.reply_text(f"User {item['username']} (ID: {user_id}) has been {action}ed for {days} days.")


def show_inactive(update: Update, context: CallbackContext) -> None:
    if not is_user_admin(update, context):
        update.message.reply_text("You are not authorized to use this command.")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        update.message.reply_text("Usage: /show <number_of_days>")
        return

    days = int(args[0])
    now = datetime.datetime.utcnow()
    inactive_users = [(user_id, item['username']) for user_id, item in last_activity.items() if
                      (now - item['date']).days >= days]

    if not inactive_users:
        update.message.reply_text("No inactive users found.")
    else:
        message = "List of inactive users:\n" + "\n".join(
            [f"{username} (ID: {user_id})" for user_id, username in inactive_users])
        update.message.reply_text(message)


def main() -> None:
    updater = Updater(TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("ban_or_kick", ban_or_kick))
    dp.add_handler(CommandHandler("show", show_inactive))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, track_new_members))

    media_filters = Filters.audio | Filters.document | Filters.photo | Filters.video | Filters.video_note | Filters.voice
    dp.add_handler(MessageHandler(media_filters & ~Filters.command, track_activity))

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    main()
