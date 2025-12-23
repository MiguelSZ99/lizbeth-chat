from flask import Flask, render_template, request, jsonify, redirect, url_for
import os
import random
import sqlite3
from datetime import datetime

# Optional Supabase (only used if env vars exist)
USE_SUPABASE = False
supabase = None

try:
    from supabase import create_client, Client  # type: ignore
except Exception:
    create_client = None
    Client = None

app = Flask(__name__)

# ==========================
#  CONFIG
# ==========================
CHAT_ID = os.getenv("CHAT_ID", "Lizbeth")  # chat identifier
MAX_MENSAJES = int(os.getenv("MAX_MENSAJES", "20"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY and create_client:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    USE_SUPABASE = True

DB_PATH = os.getenv("SQLITE_PATH", "messages.db")

# ==========================
#  FRASES (moods)
# ==========================
EMOCIONES = {
    "ternura": [
        "Cada que veo un mensaje tuyo me acuerdo del primero que te mandé, como si no te conociera y todo empezara de cero.",
        "Eres un mundo al que quiero conocer por cielo y tierra.",
        "Me gustaría saber qué se siente mirarte a los ojos… no sé si me ponga nervioso.",
        "En cualquier momento nos podemos dejar de hablar, pero sé que te vas a acordar de mí.",
        "Sé que somos mundos diferentes… pero quiero sentir esa adrenalina contigo."
    ],
    "risa": [
        "¿Quieres jugar otro juego más comprometido? Se tienen que respetar las reglas 😄",
        "¿Subirías una montaña conmigo?",
        "Seguro pusiste cara rara leyendo mis ocurrencias 😂",
        "Grábate todo de mí porque no soy un video para que le des retroceder.",
        "No te coqueteo… solo me sale natural; y si lo ves coqueteo, avísame.",
        "¿Saldrías de noche conmigo y no regresar hasta el día siguiente, cansada pero contenta?"
    ],
    "picante": [
        "¿Qué harías si te beso?",
        "No pases una noche conmigo porque vas a querer otra… y no siempre voy a estar disponible.",
        "¿Te dejarías hacer lo que yo te diga y obedecer como niña buena?",
        "No sigas viendo esto 😏",
        "¿Qué harías si beso tu cuello, tomo tu cintura y te jalo hacia mí?",
        "¿Qué harías si cierro la puerta y jugamos a los nudos… pero tú vas primero?",
        "¿Me dejarías poner mi mano en tu cuello y someterte mientras te digo cosas que nunca te han dicho?",
        "No tengo prisa contigo… pero el deseo se puede acumular."
    ],
    "sorpresa": [
        "¿Irias por CDMX conmigo a 10 lados diferentes? Yo escojo 9 y tú escojes el último ✨",
        "Tú y yo en la oscuridad… que solo nuestras manos sientan lo que está pasando.",
        "Quiero verte en persona, pero eso se dará natural y sin presiones.",
        "¿Me dejarías entrar a tu mente?",
        "Que todo esto sea un secreto… los tesoros se guardan bien."
    ]
}

# ==========================
#  SQLITE helpers (fallback)
# ==========================
def sqlite_init():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat TEXT NOT NULL,
        de TEXT NOT NULL,
        texto TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    con.commit()
    con.close()

def sqlite_guardar(chat: str, de: str, texto: str):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "INSERT INTO mensajes (chat, de, texto, created_at) VALUES (?, ?, ?, ?)",
        (chat, de, texto, datetime.utcnow().isoformat() + "Z")
    )
    con.commit()
    con.close()

def sqlite_historial(chat: str, limit: int):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT de, texto, created_at FROM mensajes WHERE chat=? ORDER BY id ASC LIMIT ?",
        (chat, limit)
    )
    rows = cur.fetchall()
    con.close()
    return [{"de": r[0], "texto": r[1], "created_at": r[2]} for r in rows]

# ==========================
#  Supabase helpers
# ==========================
def supa_guardar(chat: str, de: str, texto: str):
    # Assumes table "mensajes" with columns: chat (text), de (text), texto (text)
    supabase.table("mensajes").insert({"chat": chat, "de": de, "texto": texto}).execute()

def supa_historial(chat: str, limit: int):
    res = (
        supabase.table("mensajes")
        .select("de, texto, created_at")
        .eq("chat", chat)
        .order("created_at", desc=False)
        .limit(limit)
        .execute()
    )
    return res.data if res.data else []

# ==========================
#  Unified helpers
# ==========================
def guardar_mensaje(de: str, texto: str):
    if USE_SUPABASE:
        supa_guardar(CHAT_ID, de, texto)
    else:
        sqlite_guardar(CHAT_ID, de, texto)

def obtener_historial():
    if USE_SUPABASE:
        return supa_historial(CHAT_ID, MAX_MENSAJES)
    return sqlite_historial(CHAT_ID, MAX_MENSAJES)

# Init sqlite for local use
sqlite_init()

# ==========================
#  ROUTES
# ==========================
@app.route("/")
def home():
    return redirect(url_for("app_view"))

@app.route("/app", methods=["GET", "POST"])
def app_view():
    if request.method == "POST":
        # mood button -> generate phrase
        if "emocion" in request.form:
            emo = request.form.get("emocion", "")
            if emo in EMOCIONES:
                frase = random.choice(EMOCIONES[emo])
                # show it after redirect (no duplicate on refresh)
                return redirect(url_for("app_view", f=frase))

        # chat message from her
        if "pregunta" in request.form:
            texto = (request.form.get("pregunta") or "").strip()
            if texto:
                guardar_mensaje("ella", texto)
            return redirect(url_for("app_view"))

    frase = request.args.get("f")
    return render_template("index.html", frase_generada=frase, estado_url=url_for("estado"))

@app.route("/panel_miguel", methods=["GET"])
def panel_miguel():
    return render_template("miguel.html", estado_url=url_for("estado"), post_url=url_for("post_miguel"))

@app.route("/post_miguel", methods=["POST"])
def post_miguel():
    texto = (request.form.get("respuesta") or "").strip()
    if texto:
        guardar_mensaje("miguel", texto)
    return redirect(url_for("panel_miguel"))

@app.route("/estado")
def estado():
    return jsonify({"historial": obtener_historial(), "chat": CHAT_ID, "storage": "supabase" if USE_SUPABASE else "sqlite"})

@app.route("/favicon.ico")
def favicon():
    return ("", 204)

if __name__ == "__main__":
    # debug=True only for local dev
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
