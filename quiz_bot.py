import json
import random
import os
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

with open('questions.json', 'r', encoding='utf-8') as f:
    all_questions = json.load(f)

USER_STATE_FILE = 'user_state.json'

def load_user_state():
    try:
        with open(USER_STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_user_state(state):
    with open(USER_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f)

@dp.message()
async def start_quiz(message: types.Message):
    if message.text not in ['/start', '/quiz']:
        return

    user_id = str(message.from_user.id)
    state = load_user_state()

    if user_id not in state:
        state[user_id] = {
            'asked': [],
            'score': 0
        }

    user_data = state[user_id]
    unanswered = [q for i, q in enumerate(all_questions) if i not in user_data['asked']]

    if not unanswered:
        await message.answer(f"Вы ответили на все вопросы! Ваш результат: {user_data['score']} из {len(all_questions)}.")
        state.pop(user_id)
        save_user_state(state)
        return

    question = random.choice(unanswered)
    index = all_questions.index(question)
    user_data['asked'].append(index)

    correct = None
    options = []
    for ans in question['answers']:
        if ans.startswith('#'):
            correct = ans[1:]
            options.append(correct)
        else:
            options.append(ans)

    random.shuffle(options)

    keyboard = InlineKeyboardMarkup(row_width=1)
    for option in options:
        keyboard.add(InlineKeyboardButton(text=option, callback_data=f"{index}:{option}"))

    save_user_state(state)
    await message.answer(question['question'], reply_markup=keyboard)

@dp.callback_query()
async def handle_answer(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    state = load_user_state()
    if user_id not in state:
        await callback.answer("Начните сначала с /quiz")
        return

    index, answer = callback.data.split(':')
    index = int(index)
    question = all_questions[index]

    correct = [a[1:] for a in question['answers'] if a.startswith('#')][0]

    if answer == correct:
        state[user_id]['score'] += 1
        response = "✅ Верно!"
    else:
        response = f"❌ Неверно. Правильный ответ: {correct}"

    save_user_state(state)
    await callback.message.edit_reply_markup()
    await callback.message.answer(response)
    await start_quiz(callback.message)

# Webhook config
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://your-app-name.up.railway.app
WEBHOOK_PATH = f"/webhook/{API_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

async def main():
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

if __name__ == '__main__':
    web.run_app(main(), host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
