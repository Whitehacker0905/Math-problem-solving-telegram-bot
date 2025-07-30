from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
import logging
import asyncio

BOT_TOKEN = "8207247321:AAGh4l0lMu-RwsgaVTaIBOY0Pi2-4vPFQeg"  # Replace this
ADMIN_ID = 985374783               # Replace with your Telegram numeric ID

forward_map = {}  # forwarded_msg_id ➝ {'user_id': int, 'completed': bool, 'admin_msg_ids': [int]}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- User sends a photo ---
async def handle_user_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    photo = update.message.photo[-1]

    forwarded = await context.bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=update.effective_chat.id,
        message_id=update.message.message_id
    )

    forward_map[forwarded.message_id] = {
        'user_id': user.id,
        'completed': False,
        'admin_msg_ids': []
    }

    logger.info(f"Forwarded photo from {user.id} to admin (msg {forwarded.message_id})")

# --- Admin replies to forwarded photo ---
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    reply_to = update.message.reply_to_message
    if not reply_to:
        return

    original_msg_id = reply_to.message_id
    info = forward_map.get(original_msg_id)

    if not info:
        logger.warning("No matching user for this message.")
        return

    user_id = info['user_id']

    # /done command to clean up
    if update.message.text and update.message.text.strip().lower() == "/done":
        info['completed'] = True
        status_msg = await update.message.reply_text("✅ Marked as completed. Cleaning up in 5 seconds...")
        await asyncio.sleep(5)

        # Delete the status message too
        try:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=status_msg.message_id)
        except Exception as e:
            logger.warning(f"Couldn't delete status message: {e}")

        # Delete forwarded message
        try:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=original_msg_id)
        except Exception as e:
            logger.warning(f"Couldn't delete forwarded message: {e}")

        # Delete admin's /done message
        try:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=update.message.message_id)
        except Exception as e:
            logger.warning(f"Couldn't delete /done message: {e}")

        # Delete admin's previous replies (if any)
        for msg_id in info.get('admin_msg_ids', []):
            try:
                await context.bot.delete_message(chat_id=ADMIN_ID, message_id=msg_id)
            except Exception as e:
                logger.warning(f"Couldn't delete admin reply {msg_id}: {e}")

        return

    if info['completed']:
        logger.info("Thread already marked as completed — ignoring.")
        return

    # Handle reply types and forward them to the user
    if update.message.text:
        sent = await context.bot.send_message(chat_id=user_id, text=update.message.text)
    elif update.message.photo:
        sent = await context.bot.send_photo(chat_id=user_id, photo=update.message.photo[-1].file_id)
    elif update.message.voice:
        sent = await context.bot.send_voice(chat_id=user_id, voice=update.message.voice.file_id)
    else:
        logger.warning("Unsupported message type.")
        return

    # Save this admin reply's message ID for later cleanup
    info['admin_msg_ids'].append(update.message.message_id)
    logger.info(f"Forwarded admin reply to user {user_id} and tracked msg {update.message.message_id}")

# --- Main ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # User sends a photo (not from admin)
    app.add_handler(MessageHandler(filters.PHOTO & (~filters.User(ADMIN_ID)), handle_user_photo))

    # Admin replies to forwarded message (text, photo, or voice)
    reply_filter = filters.User(ADMIN_ID) & (filters.TEXT | filters.PHOTO | filters.VOICE)
    app.add_handler(MessageHandler(reply_filter, handle_admin_reply))

    print("Relay bot with ✅ cleanup is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

