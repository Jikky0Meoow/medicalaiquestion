import os
import logging
from telegram import Update, Poll, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from utils import extract_text_from_file, generate_mcq
from storage import can_upload_file, register_file_upload, reset_user_score, add_user_answer, get_user_score
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
logging.basicConfig(level=logging.INFO)
app = ApplicationBuilder().token(BOT_TOKEN).build()

active_users = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 مرحبًا! أرسل ملف PDF/PPT لإنشاء اختبار طبي.")

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if not can_upload_file(user_id):
        await update.message.reply_text("⚠️ وصلت إلى الحد الأقصى للتحميل.")
        return

    file = update.message.document
    msg = await update.message.reply_text("📥 جاري تحليل الملف...")
    file_obj = await file.get_file()
    path = await file_obj.download_to_drive()
    text = extract_text_from_file(path)

    if len(text.strip()) < 100:
        await msg.edit_text("❌ النص قصير جدًا.")
        return

    register_file_upload(user_id)
    active_users[user_id] = {"text": text, "questions": [], "current": 0}
    await msg.edit_text(
        "✅ تم التحليل بنجاح. اختر عدد الأسئلة:",
        reply_markup=ReplyKeyboardMarkup([[str(i)] for i in [5, 10, 15, 20]], one_time_keyboard=True)
    )

async def handle_question_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in active_users:
        return

    try:
        num = int(update.message.text)
        text = active_users[user_id]["text"]
        await update.message.reply_text("⚙️ جاري إنشاء الأسئلة...")
        questions = generate_mcq(text, num)
        active_users[user_id]["questions"] = questions
        reset_user_score(user_id)
        await send_next_batch(update, context)
    except ValueError:
        await update.message.reply_text("⚠️ الرجاء إدخال رقم صحيح.")

async def send_next_batch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = active_users[user_id]
    qlist = user_data["questions"]
    current_idx = user_data["current"]

    if current_idx >= len(qlist):
        score = get_user_score(user_id)
        await update.message.reply_text(
            f"🎉 النتيجة النهائية: {score}/{len(qlist)}",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    for q in qlist[current_idx:current_idx + 5]:
        msg = await update.message.reply_poll(
            question=q["question"],
            options=q["options"],
            type=Poll.QUIZ,
            correct_option_id=q["correct"],
            is_anonymous=False
        )
        context.chat_data[msg.poll.id] = {"user_id": user_id, "correct": q["correct"]}

    user_data["current"] += 5

    if user_data["current"] < len(qlist):
        keyboard = [[InlineKeyboardButton("المزيد ➡️", callback_data="next_batch")]]
    else:
        keyboard = [[InlineKeyboardButton("عرض النتيجة 🏁", callback_data="show_result")]]
    
    await update.message.reply_text(
        "اضغط لاستكمال الاختبار:" if "next_batch" in keyboard[0][0].callback_data else "اضغط لرؤية النتيجة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "next_batch":
        await send_next_batch(query, context)
    elif query.data == "show_result":
        user_id = query.from_user.id
        score = get_user_score(user_id)
        total = len(active_users[user_id]["questions"])
        await query.edit_message_text(f"✅ النتيجة: {score}/{total}")

async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    poll_answer = update.poll_answer
    data = context.chat_data.get(poll_answer.poll_id)
    if data:
        add_user_answer(data["user_id"], poll_answer.option_ids[0] == data["correct"])

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question_count))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.POLL_ANSWER, handle_poll_answer))

if __name__ == "__main__":
    app.run_polling()