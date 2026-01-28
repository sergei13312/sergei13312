import os
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

DB_PATH = os.getenv("NOTES_DB_PATH", "notes.db")


@dataclass
class Note:
    note_id: int
    note_date: str
    text: str


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                note_date TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def add_note(note_date: str, text: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO notes (note_date, text, created_at) VALUES (?, ?, ?)",
            (note_date, text, datetime.utcnow().isoformat()),
        )


def fetch_notes(where_clause: str = "", params: Iterable[str] = ()) -> list[Note]:
    query = "SELECT id, note_date, text FROM notes"
    if where_clause:
        query = f"{query} WHERE {where_clause}"
    query = f"{query} ORDER BY note_date, id"
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(query, params).fetchall()
    return [Note(note_id=row[0], note_date=row[1], text=row[2]) for row in rows]


def delete_note(note_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return cur.rowcount


def parse_date(candidate: str) -> str | None:
    try:
        return datetime.strptime(candidate, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def format_notes(notes: list[Note]) -> str:
    if not notes:
        return "Заметки не найдены."
    lines: list[str] = []
    for note in notes:
        lines.append(f"#{note.note_id} | {note.note_date} | {note.text}")
    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = (
        "Привет! Я бот-ежедневник.\n\n"
        "Команды:\n"
        "/add <текст> — заметка на сегодня\n"
        "/add <YYYY-MM-DD> <текст> — заметка на дату\n"
        "/today — заметки на сегодня\n"
        "/date <YYYY-MM-DD> — заметки на дату\n"
        "/list — все заметки\n"
        "/delete <id> — удалить заметку\n"
    )
    await update.message.reply_text(message)


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /add <текст> или /add <YYYY-MM-DD> <текст>")
        return

    first_arg = context.args[0]
    parsed_date = parse_date(first_arg)
    if parsed_date:
        if len(context.args) < 2:
            await update.message.reply_text("Укажите текст заметки после даты.")
            return
        note_date = parsed_date
        text = " ".join(context.args[1:]).strip()
    else:
        note_date = date.today().isoformat()
        text = " ".join(context.args).strip()

    if not text:
        await update.message.reply_text("Текст заметки не должен быть пустым.")
        return

    add_note(note_date, text)
    await update.message.reply_text(f"Заметка добавлена на {note_date}.")


async def today(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    today_str = date.today().isoformat()
    notes = fetch_notes("note_date = ?", (today_str,))
    await update.message.reply_text(format_notes(notes))


async def by_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /date <YYYY-MM-DD>")
        return
    parsed_date = parse_date(context.args[0])
    if not parsed_date:
        await update.message.reply_text("Неверный формат даты. Используйте YYYY-MM-DD.")
        return
    notes = fetch_notes("note_date = ?", (parsed_date,))
    await update.message.reply_text(format_notes(notes))


async def list_notes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    notes = fetch_notes()
    await update.message.reply_text(format_notes(notes))


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Использование: /delete <id>")
        return
    try:
        note_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID должен быть числом.")
        return
    deleted = delete_note(note_id)
    if deleted:
        await update.message.reply_text(f"Заметка #{note_id} удалена.")
    else:
        await update.message.reply_text(f"Заметка #{note_id} не найдена.")


def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Не задан TELEGRAM_BOT_TOKEN")

    init_db()

    application = Application.builder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add", add))
    application.add_handler(CommandHandler("today", today))
    application.add_handler(CommandHandler("date", by_date))
    application.add_handler(CommandHandler("list", list_notes))
    application.add_handler(CommandHandler("delete", delete))

    application.run_polling()


if __name__ == "__main__":
    main()
