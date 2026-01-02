from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, TEACHER_ID
import sqlite3

# ---------------- INIT ----------------
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# ---------------- DB INIT ----------------
cursor.execute("""
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    name TEXT,
    text TEXT,
    grade INTEGER
)
""")
conn.commit()

# ---------------- STATES ----------------
class StudentForm(StatesGroup):
    waiting_name = State()
    waiting_report = State()

# ---------------- START ----------------
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.from_user.id == TEACHER_ID:
        await message.answer("👨‍🏫 Вы вошли как преподаватель")
    else:
        await message.answer("👨‍🎓 Введите ваше имя:")
        await StudentForm.waiting_name.set()

# ---------------- NAME ----------------
@dp.message_handler(state=StudentForm.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("✅ Имя сохранено. Теперь отправьте отчёт текстом.")
    await StudentForm.waiting_report.set()

# ---------------- REPORT ----------------
@dp.message_handler(state=StudentForm.waiting_report)
async def get_report(message: types.Message, state: FSMContext):
    data = await state.get_data()
    name = data["name"]

    cursor.execute(
        "INSERT INTO reports (tg_id, name, text, grade) VALUES (?, ?, ?, ?)",
        (message.from_user.id, name, message.text, None)
    )
    conn.commit()

    report_id = cursor.lastrowid

    await message.answer("✅ Отчёт отправлен")
    await state.finish()

    await bot.send_message(
        TEACHER_ID,
        f"📄 НОВЫЙ ОТЧЁТ\n\n"
        f"Имя: {name}\n"
        f"ID отчёта: {report_id}\n\n"
        f"{message.text}"
    )

# ---------------- REPORTS (TEACHER) ----------------
@dp.message_handler(commands=['reports'])
async def reports(message: types.Message):
    if message.from_user.id != TEACHER_ID:
        return

    cursor.execute("SELECT id, name, text, grade FROM reports")
    rows = cursor.fetchall()

    if not rows:
        await message.answer("Отчётов пока нет")
        return

    for r in rows:
        await message.answer(
            f"🆔 ID отчёта: {r[0]}\n"
            f"👤 Имя: {r[1]}\n\n"
            f"📄 Отчёт:\n{r[2]}\n\n"
            f"⭐ Оценка: {r[3]}"
        )

# ---------------- GRADE ----------------
@dp.message_handler(commands=['grade'])
@dp.message_handler(commands=['grade'])
async def grade(message: types.Message):
    if message.from_user.id != TEACHER_ID:
        return

    try:
        _, report_id, grade = message.text.split()

        grade = int(grade)

        if grade < 2 or grade > 5:
            await message.answer("❌ Оценка должна быть от 2 до 5")
            return

        cursor.execute(
            "SELECT tg_id FROM reports WHERE id = ?",
            (report_id,)
        )
        row = cursor.fetchone()

        if not row:
            await message.answer("❌ Отчёт не найден")
            return

        student_tg_id = row[0]

        cursor.execute(
            "UPDATE reports SET grade = ? WHERE id = ?",
            (grade, report_id)
        )
        conn.commit()

        await message.answer("✅ Оценка сохранена")

        await bot.send_message(
            student_tg_id,
            f"📢 Ваш отчёт проверен.\n⭐ Оценка: {grade}"
        )

    except ValueError:
        await message.answer("❌ Оценка должна быть числом (2–5)")
    except:
        await message.answer("❌ Формат: /grade ID_отчёта оценка")


# ---------------- RUN ----------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
