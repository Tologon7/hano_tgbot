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

# ---------------- STATES ----------------
class StudentForm(StatesGroup):
    waiting_name = State()


# ---------------- START ----------------
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    if message.from_user.id == TEACHER_ID:
        await message.answer("👨‍🏫 Вы вошли как преподаватель")
    else:
        cursor.execute(
            "SELECT id FROM students WHERE tg_id = ?",
            (message.from_user.id,)
        )
        student = cursor.fetchone()

        if student:
            await message.answer("👨‍🎓 Вы уже зарегистрированы.\nОтправьте отчёт текстом.")
        else:
            await message.answer("👨‍🎓 Введите ваше имя:")
            await StudentForm.waiting_name.set()


# ---------------- ВВОД ИМЕНИ ----------------
@dp.message_handler(state=StudentForm.waiting_name)
async def get_name(message: types.Message, state: FSMContext):
    cursor.execute(
        "INSERT INTO students (tg_id, name) VALUES (?, ?)",
        (message.from_user.id, message.text)
    )
    conn.commit()

    await message.answer("✅ Имя сохранено. Теперь отправьте отчёт текстом.")
    await state.finish()


# ---------------- СТУДЕНТ: ОТЧЁТ ----------------
@dp.message_handler(
    lambda message: message.from_user.id != TEACHER_ID
    and not message.text.startswith("/")
)
async def student_report(message: types.Message):
    cursor.execute(
        "SELECT id, name FROM students WHERE tg_id = ?",
        (message.from_user.id,)
    )
    student = cursor.fetchone()

    if not student:
        await message.answer("Сначала напишите /start")
        return

    student_id, name = student

    cursor.execute(
        "INSERT INTO reports (student_id, text, grade) VALUES (?, ?, ?)",
        (student_id, message.text, None)
    )
    conn.commit()

    report_id = cursor.lastrowid

    await message.answer("✅ Отчёт отправлен")

    await bot.send_message(
        TEACHER_ID,
        f"📄 НОВЫЙ ОТЧЁТ\n\n"
        f"Имя студента: {name}\n"
        f"ID студента: {student_id}\n"
        f"ID отчёта: {report_id}\n\n"
        f"{message.text}"
    )


# ---------------- ПРЕПОДАВАТЕЛЬ: ОТЧЁТЫ ----------------
@dp.message_handler(commands=['reports'])
async def reports(message: types.Message):
    if message.from_user.id != TEACHER_ID:
        return

    cursor.execute("""
    SELECT reports.id, students.id, students.name, reports.text, reports.grade
    FROM reports
    JOIN students ON reports.student_id = students.id
    """)

    rows = cursor.fetchall()

    if not rows:
        await message.answer("Отчётов пока нет")
        return

    for r in rows:
        await message.answer(
            f"🆔 ID отчёта: {r[0]}\n"
            f"🧑 Студент: {r[2]}\n"
            f"🆔 ID студента: {r[1]}\n\n"
            f"📄 Отчёт:\n{r[3]}\n\n"
            f"⭐ Оценка: {r[4]}"
        )


# ---------------- ПРЕПОДАВАТЕЛЬ: ОЦЕНКА ----------------
@dp.message_handler(commands=['grade'])
async def grade(message: types.Message):
    if message.from_user.id != TEACHER_ID:
        return

    try:
        _, report_id, grade = message.text.split()

        cursor.execute(
            "SELECT students.tg_id FROM reports "
            "JOIN students ON reports.student_id = students.id "
            "WHERE reports.id = ?",
            (report_id,)
        )
        student = cursor.fetchone()

        if not student:
            await message.answer("❌ Отчёт не найден")
            return

        student_tg_id = student[0]

        cursor.execute(
            "UPDATE reports SET grade = ? WHERE id = ?",
            (grade, report_id)
        )
        conn.commit()

        await message.answer("✅ Оценка сохранена")

        await bot.send_message(
            student_tg_id,
            f"📢 Ваш отчёт проверен.\n"
            f"⭐ Оценка: {grade}"
        )

    except:
        await message.answer("❌ Формат: /grade ID_отчёта оценка")


# ---------------- RUN ----------------
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
