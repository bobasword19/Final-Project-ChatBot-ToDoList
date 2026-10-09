
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path("todo.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            due_time TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending', 'completed')),
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()
print(f"Database siap: {DB_PATH.resolve()}")

def add_task(title, description="", due_date="", due_time=""):
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO tasks
        (title, description, due_date, due_time, status, created_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (title, description, due_date, due_time,
         datetime.now().isoformat(timespec="seconds"))
    )
    conn.commit()
    task_id = cur.lastrowid
    conn.close()
    return task_id


def get_tasks(status=None):
    conn = get_connection()

    if status in ("pending", "completed"):
        rows = conn.execute(
            """
            SELECT * FROM tasks
            WHERE status = ?
            ORDER BY
                CASE WHEN due_date = '' THEN 1 ELSE 0 END,
                due_date, due_time, id DESC
            """,
            (status,)
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM tasks
            ORDER BY
                CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                CASE WHEN due_date = '' THEN 1 ELSE 0 END,
                due_date, due_time, id DESC
            """
        ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def find_tasks(keyword):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM tasks
        WHERE title LIKE ? OR description LIKE ?
        ORDER BY id DESC
        """,
        (f"%{keyword}%", f"%{keyword}%")
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def complete_task(task_id):
    conn = get_connection()
    cur = conn.execute(
        "UPDATE tasks SET status = 'completed' WHERE id = ?",
        (task_id,)
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def set_pending(task_id):
    conn = get_connection()
    cur = conn.execute(
        "UPDATE tasks SET status = 'pending' WHERE id = ?",
        (task_id,)
    )
    conn.commit()
    changed = cur.rowcount > 0
    conn.close()
    return changed


def update_task(task_id, title=None, description=None,
                due_date=None, due_time=None):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM tasks WHERE id = ?", (task_id,)
    ).fetchone()

    if not row:
        conn.close()
        return False

    new_title = title if title is not None else row["title"]
    new_description = (
        description if description is not None else row["description"]
    )
    new_due_date = due_date if due_date is not None else row["due_date"]
    new_due_time = due_time if due_time is not None else row["due_time"]

    conn.execute(
        """
        UPDATE tasks
        SET title = ?, description = ?, due_date = ?, due_time = ?
        WHERE id = ?
        """,
        (new_title, new_description, new_due_date, new_due_time, task_id)
    )
    conn.commit()
    conn.close()
    return True


def delete_task(task_id):
    conn = get_connection()
    cur = conn.execute(
        "DELETE FROM tasks WHERE id = ?", (task_id,)
    )
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted

print("Fungsi CRUD berhasil dibuat.")

from typing import Optional
from langchain_core.tools import tool

@tool
def add_todo(
    title: str,
    description: str = "",
    due_date: str = "",
    due_time: str = "",
) -> str:
    """Add a new to-do task. due_date=YYYY-MM-DD and due_time=HH:MM when known."""
    task_id = add_task(title, description, due_date, due_time)
    return f"Task berhasil ditambahkan dengan ID {task_id}: {title}"

@tool
def list_todos(status: str = "all") -> str:
    """List to-do tasks. status must be all, pending, or completed."""
    if status not in ("all", "pending", "completed"):
        status = "all"

    tasks = get_tasks(None if status == "all" else status)
    if not tasks:
        return "Tidak ada task."

    lines = []
    for task in tasks:
        mark = "✅" if task["status"] == "completed" else "⬜"
        schedule = ""
        if task["due_date"]:
            schedule += task["due_date"]
        if task["due_time"]:
            schedule += f" {task['due_time']}"
        extra = f" | {schedule.strip()}" if schedule.strip() else ""
        lines.append(f"{mark} ID {task['id']} — {task['title']}{extra}")

    return "\n".join(lines)

@tool
def search_todos(keyword: str) -> str:
    """Search tasks by title or description."""
    tasks = find_tasks(keyword)
    if not tasks:
        return f"Tidak menemukan task yang cocok dengan '{keyword}'."

    lines = []
    for task in tasks:
        mark = "✅" if task["status"] == "completed" else "⬜"
        lines.append(
            f"{mark} ID {task['id']} — {task['title']} "
            f"(status: {task['status']})"
        )
    return "\n".join(lines)

@tool
def complete_todo(task_id: int) -> str:
    """Mark a task as completed using its numeric ID."""
    if complete_task(task_id):
        return f"Task ID {task_id} berhasil ditandai sebagai selesai."
    return f"Task ID {task_id} tidak ditemukan."

@tool
def reopen_todo(task_id: int) -> str:
    """Change a completed task back to pending using its numeric ID."""
    if set_pending(task_id):
        return f"Task ID {task_id} dikembalikan menjadi belum selesai."
    return f"Task ID {task_id} tidak ditemukan."

@tool
def update_todo(
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    due_date: Optional[str] = None,
    due_time: Optional[str] = None,
) -> str:
    """Update an existing task by ID."""
    if update_task(task_id, title, description, due_date, due_time):
        return f"Task ID {task_id} berhasil diperbarui."
    return f"Task ID {task_id} tidak ditemukan."

@tool
def delete_todo(task_id: int) -> str:
    """Delete a task permanently using its numeric ID."""
    if delete_task(task_id):
        return f"Task ID {task_id} berhasil dihapus."
    return f"Task ID {task_id} tidak ditemukan."

TODO_TOOLS = [
    add_todo, list_todos, search_todos, complete_todo,
    reopen_todo, update_todo, delete_todo
]

print("Tools:")
for t in TODO_TOOLS:
    print("-", t.name)


import os
from langchain_google_genai import ChatGoogleGenerativeAI

GEMINI = os.getenv("GEMINI")

if not GEMINI:
    raise ValueError(
        "GEMINI belum tersedia sebagai environment variable."
    )

os.environ["GOOGLE_API_KEY"] = GEMINI

MODEL_NAME = "gemini-3.5-flash-lite"

llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
)



SYSTEM_PROMPT = """
Kamu adalah TodoMate, asisten to-do list berbasis AI.

Tugas utama:
1. Membantu pengguna menambahkan task.
2. Menampilkan task.
3. Menandai task sebagai selesai atau belum selesai.
4. Mengubah task.
5. Menghapus task.
6. Mencari task.
7. Memberikan ringkasan sederhana mengenai task pengguna.

Aturan penting:
- Gunakan tools untuk semua operasi database. Jangan mengarang data task.
- Jika pengguna meminta menambahkan task, gunakan add_todo.
- Jika pengguna meminta melihat task, gunakan list_todos.
- Jika pengguna meminta menyelesaikan task, cari task terlebih dahulu jika ID belum jelas.
- Jika nama task ambigu, gunakan search_todos dan minta pengguna memilih ID yang benar.
- Jika pengguna meminta mengubah atau menghapus task tanpa ID, cari task terlebih dahulu.
- Jangan mengatakan task sudah tersimpan jika tool gagal.
- Status pending berarti belum selesai.
- Status completed berarti selesai.
- Jawab dalam Bahasa Indonesia.
- Gunakan gaya bahasa ramah, ringkas, dan jelas.
- Jangan memberikan penjelasan teknis tentang database kecuali pengguna memintanya.

Tanggal dan waktu saat ini:
{current_datetime}

Jika pengguna menggunakan kata relatif seperti hari ini, besok, atau lusa,
ubah ke tanggal absolut berdasarkan tanggal saat ini sebelum memanggil tool.
"""


from datetime import datetime
from langgraph.prebuilt import create_react_agent

def build_agent():
    prompt = SYSTEM_PROMPT.format(
        current_datetime=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    return create_react_agent(
        model=llm,
        tools=TODO_TOOLS,
        prompt=prompt,
    )


def ask_agent(agent, messages):
    result = agent.invoke({
        "messages": messages
    })

    content = result["messages"][-1].content

    # Jika Gemini mengembalikan list content blocks
    if isinstance(content, list):
        texts = []

        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))

        content = "\n".join(texts)

    return content.strip()


import pandas as pd
import streamlit as st

# ================================================================
# DATABASE
# ================================================================

init_db()

# ================================================================
# STREAMLIT CONFIG
# ================================================================

st.set_page_config(
    page_title="TodoMate AI",
    layout="wide",
)

# ================================================================
# HELPER
# ================================================================

def get_task_dataframe(status="all"):
    tasks = get_tasks(None if status == "all" else status)

    if not tasks:
        return pd.DataFrame()

    rows = []
    for task in tasks:
        rows.append({
            "ID": task["id"],
            "Tugas": task["title"],
            "Deskripsi": task["description"] or "-",
            "Tanggal": task["due_date"] or "-",
            "Waktu": task["due_time"] or "-",
            "Status": (
                "✅ Selesai"
                if task["status"] == "completed"
                else "⬜ Belum selesai"
            ),
        })

    return pd.DataFrame(rows)


def task_status_from_prompt(prompt):
    text = prompt.lower()

    if any(word in text for word in [
        "belum selesai",
        "belum dikerjakan",
        "pending",
        "yang belum selesai",
        "tugas pending",
    ]):
        return "pending"

    if any(word in text for word in [
        "sudah selesai",
        "telah selesai",
        "selesai",
        "completed",
        "yang selesai",
    ]):
        return "completed"

    return "all"


def should_show_task_table(prompt):
    text = prompt.lower()

    keywords = [
        "tugas", "task", "todo", "daftar", "list",
        "apa saja", "belum selesai", "sudah selesai",
        "pending", "completed",
    ]

    return any(keyword in text for keyword in keywords)


# ================================================================
# HEADER
# ================================================================

st.title("TodoMate AI")
st.caption(
    "Asisten to-do list berbasis AI — "
    "kelola tugas melalui percakapan."
)

# ================================================================
# SIDEBAR
# ================================================================

with st.sidebar:
    st.header("⚙️ Pengaturan")

    st.info(f"**Model:** `{MODEL_NAME}`")
    st.caption("Gemini API menggunakan Colab Secret `GEMINI`.")

    st.divider()

    tasks = get_tasks()

    pending_count = sum(
        t["status"] == "pending"
        for t in tasks
    )

    completed_count = sum(
        t["status"] == "completed"
        for t in tasks
    )

    total_count = len(tasks)

    st.subheader("📊 Ringkasan Tugas")

    col1, col2 = st.columns(2)
    col1.metric("⬜ Belum selesai", pending_count)
    col2.metric("✅ Selesai", completed_count)

    st.caption(f"Total tugas: **{total_count}**")

    st.divider()

    if st.button("🗑️ Reset Chat", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pop("agent", None)
        st.rerun()

# ================================================================
# SESSION STATE
# ================================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

# ================================================================
# AGENT
# ================================================================

if "agent" not in st.session_state:
    try:
        st.session_state.agent = build_agent()
    except Exception as e:
        st.error(f"Gagal membuat AI agent: {e}")
        st.stop()

# ================================================================
# RIWAYAT CHAT
# ================================================================

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ================================================================
# CHAT INPUT
# ================================================================

prompt = st.chat_input(
    "Ketik perintah, misalnya: Tambahkan tugas belajar Python besok..."
)

if prompt:
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
    })

    with st.chat_message("user"):
        st.markdown(prompt)

    agent_messages = [
        {
            "role": m["role"],
            "content": m["content"],
        }
        for m in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        with st.spinner("TodoMate sedang memproses..."):
            try:
                response = ask_agent(
                    st.session_state.agent,
                    agent_messages,
                )

                st.markdown(response)

                if should_show_task_table(prompt):
                    status = task_status_from_prompt(prompt)
                    df = get_task_dataframe(status)

                    if not df.empty:
                        label = {
                            "all": "📋 Daftar Semua Tugas",
                            "pending": "⬜ Tugas Belum Selesai",
                            "completed": "✅ Tugas Selesai",
                        }[status]

                        st.markdown(f"**{label}**")

                        st.dataframe(
                            df,
                            use_container_width=True,
                            hide_index=True,
                        )
                    else:
                        st.info(
                            "Tidak ada tugas pada kategori tersebut."
                        )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                })

            except Exception as e:
                error_message = (
                    "Terjadi kesalahan saat memproses permintaan. "
                    f"Detail: {e}"
                )

                st.error(error_message)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message,
                })

# ================================================================
# TASK BOARD
# ================================================================

st.divider()
st.subheader("📋 Daftar Tugas")

task_filter = st.radio(
    "Filter",
    ["Semua", "Belum selesai", "Selesai"],
    horizontal=True,
)

filter_map = {
    "Semua": "all",
    "Belum selesai": "pending",
    "Selesai": "completed",
}

df_tasks = get_task_dataframe(
    filter_map[task_filter]
)

if df_tasks.empty:
    st.info("Belum ada tugas pada kategori ini.")
else:
    st.dataframe(
        df_tasks,
        use_container_width=True,
        hide_index=True,
    )
