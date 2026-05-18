import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from analyzer import analyze_receipt

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')

# media_group_id -> {'images': [], 'message': ..., 'task': ...}
media_groups: dict = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Отправь фото чека — я извлеку данные и разобью по позициям.\n"
        "Если чек длинный, можешь отправить несколько фото сразу."
    )


async def _process_group(media_group_id: str, context: ContextTypes.DEFAULT_TYPE):
    await asyncio.sleep(2)

    group = media_groups.pop(media_group_id, None)
    if not group:
        return

    message = group['message']
    count = len(group['images'])
    label = f"{count} фото" if count > 1 else "фото"
    status_msg = await message.reply_text(f"⏳ Анализирую чек ({label})...")

    try:
        result = await analyze_receipt(group['images'])
        await status_msg.delete()
        await message.reply_text(result, parse_mode='HTML')
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_msg.edit_text(f"❌ Ошибка при обработке чека: {e}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    photo = msg.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    image_bytes = bytes(await file.download_as_bytearray())

    media_group_id = msg.media_group_id

    if media_group_id:
        if media_group_id not in media_groups:
            media_groups[media_group_id] = {
                'images': [],
                'message': msg,
                'task': None,
            }

        media_groups[media_group_id]['images'].append(image_bytes)

        if media_groups[media_group_id]['task']:
            media_groups[media_group_id]['task'].cancel()

        task = asyncio.create_task(_process_group(media_group_id, context))
        media_groups[media_group_id]['task'] = task
    else:
        status_msg = await msg.reply_text("⏳ Анализирую чек...")
        try:
            result = await analyze_receipt([image_bytes])
            await status_msg.delete()
            await msg.reply_text(result, parse_mode='HTML')
        except Exception as e:
            logger.error(f"Error: {e}")
            await status_msg.edit_text(f"❌ Ошибка при обработке чека: {e}")


def main():
    if not TELEGRAM_TOKEN:
        raise ValueError("TELEGRAM_TOKEN не задан в .env")

    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    logger.info("Бот запущен")
    app.run_polling()


if __name__ == '__main__':
    main()
