import json
import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils import executor
import os

API_TOKEN = os.getenv("API_TOKEN")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

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

def get_question(user_id):
    user_id = str(user_id)
    state = load_user_state()
    user_data = state.get(user_id, {"asked": []})
    asked = user_data["asked"]

    remaining = [q for i, q in enumerate(all_questions) if str(i) not in asked]
    if not remaining:
        return None, None

    question = random.choice(remaining)
    question_index = all_questions.index(question)
    user_data["asked"].append(str(question_index))
    state[user_id] = user_data
    save_user_state(state)
    return question, question_index

def reset_user(user_id):
    state = load_user_state()
    state[str(user_id)] = {"asked": []}
    save_user_state(state)

@dp.message_handler(commands=['start', 'quiz'])
async def start_quiz(message: types.Message):
    user_id = message.from_user.id
    question, index = get_question(user_id)

    if question is None:
        markup = InlineKeyboardMarkup().add(
            InlineKeyboardButton("Пройти ещё раз", callback_data="restart_quiz")
        )
        await message.answer("Вы прошли все вопросы! 🎉", reply_markup=markup)
        return

    text = question['question']
    options = question['options']
    buttons = [
        InlineKeyboardButton(opt.replace("#", ""), callback_data=f"{index}:{i}")
        for i, opt in enumerate(options)
    ]
    markup = InlineKeyboardMarkup(row_width=1).add(*buttons)
    await message.answer(text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("restart_quiz"))
async def restart_quiz(callback: types.CallbackQuery):
    reset_user(callback.from_user.id)
    await callback.message.edit_text("Начинаем заново!")
    await start_quiz(callback.message)

@dp.callback_query_handler(lambda c: ":" in c.data)
async def handle_answer(callback: types.CallbackQuery):
    index, choice = callback.data.split(":")
    question = all_questions[int(index)]
    correct = [i for i, a in enumerate(question['answers']) if "#" in a]
    choice = int(choice)

    if choice in correct:
        reply = "✅ Верно!"
    else:
        correct_text = question['answers'][correct[0]].replace("#", "")
        reply = f"❌ Неверно. Правильный ответ: {correct_text}"

    await callback.message.edit_text(f"{question['question']}\n\n{reply}")
    await start_quiz(callback.message)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
