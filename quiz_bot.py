import logging
import json
import random
import asyncio

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import BadRequest

TOKEN = "8164456272:AAFwri2tzz3PaNN6TS07snz1YkVSawCeXkc"
QUIZ_LENGTH = 25

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

def load_questions():
    try:
        with open('questions.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Ошибка загрузки questions.json: {e}")
        return []

async def present_question(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    user_data = context.user_data
    index = user_data.get('current_question_index', 0)

    if index >= len(user_data.get('quiz_questions', [])):
        score = user_data.get('score', 0)
        total = len(user_data.get('quiz_questions', []))

        restart_button = [[InlineKeyboardButton("🔄 Пройти ещё раз", callback_data="restart_cycle")]]
        reply_markup = InlineKeyboardMarkup(restart_button)

        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Квиз завершён! ✅\nРезультат: {score} из {total}.",
            reply_markup=reply_markup
        )

        for key in ['quiz_questions', 'current_question_index', 'score', 'quiz_message_id', 'current_question_options']:
            user_data.pop(key, None)
        return

    question = user_data['quiz_questions'][index]
    options = question['options'][:]
    random.shuffle(options)

    keyboard = [[InlineKeyboardButton(opt, callback_data=str(i))] for i, opt in enumerate(options)]
    reply_markup = InlineKeyboardMarkup(keyboard)

    user_data['current_question_options'] = options

    message = await context.bot.send_message(
        chat_id=chat_id,
        text=f"Вопрос {index + 1} из {QUIZ_LENGTH}:\n\n{question['question']}",
        reply_markup=reply_markup
    )

    user_data['quiz_message_id'] = message.message_id

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["/quiz"], ["/restart"]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Добро пожаловать! 📘\n\nВыбери команду:\n- /quiz — начать квиз\n- /restart — сбросить прогресс",
        reply_markup=markup
    )

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'used_question_indices' in context.user_data:
        context.user_data['used_question_indices'].clear()
    await update.message.reply_text("Прогресс сброшен. Используй /quiz для новой попытки.")

async def quiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    context.user_data.pop('quiz_message_id', None)

    all_questions = load_questions()
    if not all_questions:
        await context.bot.send_message(chat_id, "Ошибка загрузки вопросов.")
        return

    used = context.user_data.setdefault('used_question_indices', set())
    available = [(i, q) for i, q in enumerate(all_questions) if i not in used]

    if len(available) < QUIZ_LENGTH:
        await context.bot.send_message(chat_id, "Все вопросы пройдены. Используй /restart.")
        return

    sample = random.sample(available, QUIZ_LENGTH)
    indices, quiz_questions = zip(*sample)

    context.user_data['used_question_indices'].update(indices)
    context.user_data.update({
        'quiz_questions': list(quiz_questions),
        'current_question_index': 0,
        'score': 0
    })

    await present_question(context, chat_id)

async def handle_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "restart_cycle":
        if 'used_question_indices' in context.user_data:
            context.user_data['used_question_indices'].clear()
        await query.message.edit_text("Прогресс сброшен. Используй /quiz для новой попытки.")
        return

    user_data = context.user_data
    chat_id = query.message.chat_id
    msg_id = query.message.message_id

    if msg_id != user_data.get('quiz_message_id'):
        return

    try:
        selected_index = int(query.data)
    except ValueError:
        return

    index = user_data.get('current_question_index', 0)
    question = user_data['quiz_questions'][index]
    selected_option = user_data['current_question_options'][selected_index]
    correct = question['correct_answer']

    if selected_option == correct:
        user_data['score'] += 1
        response = "✅ Верно!"
    else:
        response = f"❌ Неверно.\nПравильный ответ: {correct}"

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=msg_id,
            text=f"{query.message.text}\n\n{response}",
            reply_markup=None
        )
    except BadRequest:
        pass

    user_data['current_question_index'] += 1
    await asyncio.sleep(2)
    await present_question(context, chat_id)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("quiz", quiz))
    app.add_handler(CommandHandler("restart", restart))
    app.add_handler(CallbackQueryHandler(handle_answer))

    print("Бот запущен.")
    app.run_polling()

if __name__ == '__main__':
    main()
