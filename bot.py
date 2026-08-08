import asyncio
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

router = Router()

OPENING_STEPS = [
    ("Зайдите в помещение, откройте основную дверь и включите свет во всех рабочих зонах.", False),
    ("Подметите крыльцо и входную зону. После уборки отправьте фотографию.", True),
    ("Включите компьютер.", False),
    ("Запустите CRM и убедитесь, что система работает.", False),
    ("Проверьте рабочий телефон: связь, заряд, Telegram/WhatsApp.", False),
    ("Включите монитор видеонаблюдения и проверьте изображение со всех камер.", False),
    ("Откройте кассовую смену.", False),
    ("Осмотрите точку: велосипеды, аккумуляторы, проходы и оставленные проблемы.", False),
]

class Shift(StatesGroup):
    opening = State()
    waiting_photo = State()
    problem = State()


def kb(*buttons: tuple[str, str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=text, callback_data=data)] for text, data in buttons
    ])


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [("🚲 Выдать велосипед", "menu:issue"), ("↩️ Принять велосипед", "menu:return")],
        [("🔧 Передать в ремонт", "menu:repair"), ("⚠️ Сообщить о проблеме", "problem")],
        [("👤 Новый клиент", "menu:client"), ("📋 Задачи", "menu:tasks")],
        [("📷 Фото / видео", "menu:media")],
        [("🔴 Закрыть смену", "close_shift")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])


async def show_step(message: Message, state: FSMContext, index: int) -> None:
    if index >= len(OPENING_STEPS):
        await state.clear()
        await message.answer(
            f"✅ Смена открыта\nВремя: {datetime.now().strftime('%H:%M')}\nВыполнено: {len(OPENING_STEPS)}/{len(OPENING_STEPS)}",
            reply_markup=main_menu(),
        )
        return
    text, needs_photo = OPENING_STEPS[index]
    await state.set_state(Shift.waiting_photo if needs_photo else Shift.opening)
    await state.update_data(step=index)
    buttons = [("📷 Жду фото", "noop"), ("⚠️ Проблема", "problem")] if needs_photo else [("✅ Готово", "done"), ("⚠️ Проблема", "problem")]
    await message.answer(f"ШАГ {index + 1} из {len(OPENING_STEPS)}\n\n{text}", reply_markup=kb(*buttons))


@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name or "сотрудник"
    await message.answer(
        f"🚲 ГАЗУЛЬКА | РАБОТА\n\nЗдравствуйте, {name}.\nГотовы начать рабочую смену?",
        reply_markup=kb(("▶️ НАЧАТЬ СМЕНУ", "start_shift")),
    )


@router.callback_query(F.data == "start_shift")
async def start_shift(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await show_step(call.message, state, 0)


@router.callback_query(F.data == "done")
async def done(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer("Выполнено")
    data = await state.get_data()
    await show_step(call.message, state, int(data.get("step", 0)) + 1)


@router.message(Shift.waiting_photo, F.photo)
async def photo_received(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await message.answer("✅ Фото принято.")
    await show_step(message, state, int(data.get("step", 0)) + 1)


@router.message(Shift.waiting_photo)
async def photo_required(message: Message) -> None:
    await message.answer("Для выполнения этого шага нужно отправить фотографию.")


@router.callback_query(F.data == "problem")
async def problem(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.set_state(Shift.problem)
    await call.message.answer("⚠️ Опишите проблему одним сообщением. Можно приложить фото или видео.")


@router.message(Shift.problem)
async def save_problem(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    step = int(data.get("step", -1))
    await message.answer("⚠️ Проблема зафиксирована. Продолжаем.")
    if step >= 0:
        await show_step(message, state, step + 1)
    else:
        await state.clear()
        await message.answer("Возвращаю в рабочее меню.", reply_markup=main_menu())


@router.callback_query(F.data == "close_shift")
async def close_shift(call: CallbackQuery, state: FSMContext) -> None:
    await call.answer()
    await state.clear()
    await call.message.answer(
        f"🔴 Смена закрыта\nВремя: {datetime.now().strftime('%H:%M')}\n\nДо следующей смены.",
        reply_markup=kb(("▶️ НАЧАТЬ НОВУЮ СМЕНУ", "start_shift")),
    )


@router.callback_query(F.data.startswith("menu:"))
async def placeholder(call: CallbackQuery) -> None:
    await call.answer()
    await call.message.answer("Этот сценарий добавим после теста первой смены.", reply_markup=main_menu())


@router.callback_query(F.data == "noop")
async def noop(call: CallbackQuery) -> None:
    await call.answer("Отправьте фотографию сообщением")


async def main() -> None:
    if not TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
