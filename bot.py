import os, json, asyncio, re, random, logging
from dotenv import load_dotenv
from rapidfuzz import fuzz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import nest_asyncio
from collections import defaultdict, deque
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# =============================
# CONFIG
# =============================
load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("teknikbot")

# =============================
# TOKEN CONFIG
# =============================

TOKEN = "7739470286:AAENQyesrOL6Bu7R1WMvfIFWiUlBOQ37O_k"
FAQ_FILE = "faq.json"
SIMILARITY_THRESHOLD = 60  # toleransi fuzzy match
CLARIFICATION_THRESHOLD = 40  # skor minimal untuk ajukan klarifikasi

# Simpan context percakapan per user
user_context = defaultdict(list)
metrics = defaultdict(int)
user_profiles = defaultdict(lambda: {"tone": "formal"})
last_suggestions = defaultdict(lambda: deque(maxlen=3))
last_answer = {}
faq_cache = {
    "mtime": None,
    "faqs": [],
    "clean_questions": [],
    "vectorizer": None,
    "matrix": None,
}

INFORMAL_KEYWORDS = {
    "gw", "gue", "gua", "guaa", "guaan", "gueh",
    "lo", "lu", "elu", "kamu", "ya", "bro", "sis", "btw",
    "makasih", "thanks", "thx", "oke", "ok", "sip", "dong",
    "nih", "gini", "bang", "wkwk", "hehe", "haha",
}


def detect_tone_from_message(message: str):
    message_lower = message.lower()
    score = sum(1 for word in INFORMAL_KEYWORDS if word in message_lower)
    if score >= 2:
        return "casual"
    if score == 1 and len(message) < 60:
        return "casual"
    return None


def get_user_tone(user_id):
    return user_profiles[user_id]["tone"]


def set_user_tone(user_id, tone):
    if tone not in {"formal", "casual"}:
        return
    user_profiles[user_id]["tone"] = tone


def get_user_display_name(user):
    if not user:
        return None
    if user.first_name and user.last_name:
        return f"{user.first_name.strip()} {user.last_name.strip()}".strip()
    if user.first_name:
        return user.first_name.strip()
    if user.username:
        return user.username.strip()
    return None


def personalize(text, name):
    placeholder = name or "Anda"
    try:
        return text.format(name=placeholder)
    except Exception:
        return text


def build_feedback_markup(existing_rows=None):
    rows = []
    if existing_rows:
        rows = [list(row) for row in existing_rows]
    feedback_row = [
        InlineKeyboardButton("✅ Sudah jelas", callback_data="feedback::ok"),
        InlineKeyboardButton("❓ Masih butuh bantuan", callback_data="feedback::help"),
    ]
    rows.append(feedback_row)
    return InlineKeyboardMarkup(rows)


# =============================
# PERSONALITY & RESPONSES
# =============================
GREETINGS = [
    "halo", "hai", "hi", "hey", "haloo", "hallo", "p", "permisi", "assalamualaikum"
]

THANKS = [
    "makasih", "thanks", "terima kasih", "tengkyu", "thx", "thank you"
]

SMALL_TALK = {
    "greeting": {
        "formal": [
            "Halo {name}! 👋 Ada yang dapat saya bantu hari ini?",
            "Hai, {name}. Apakah ada yang ingin Anda tanyakan? 😊",
            "Halo {name}! Saya siap membantu. Silakan ajukan pertanyaan.",
        ],
        "casual": [
            "Halo {name}! 👋 Ada yang mau ditanya?",
            "Hai {name}, ada info yang lagi dicari? 😊",
            "Halo halo {name}! Tinggal tanya aja ya.",
        ],
    },
    "thanks": {
        "formal": [
            "Sama-sama, {name} 😊 Senang dapat membantu.",
            "Dengan senang hati, {name}. Jika ada pertanyaan lain, silakan disampaikan 👍",
            "Baik, {name}. Silakan hubungi saya kembali bila diperlukan 🙌",
        ],
        "casual": [
            "Siap, {name}! Senang bisa bantu 😊",
            "Oke {name}, kalau ada apa-apa tinggal kabarin ya 👍",
            "Sip, {name}. Kapan pun butuh bantuan bilang aja 🙌",
        ],
    },
    "confused": {
        "formal": [
            "Mohon maaf, {name}, saya belum memahami pertanyaannya 🤔 Dapatkah dijelaskan lebih rinci?",
            "Sepertinya saya belum menangkap maksud Anda, {name}. Bisa dijelaskan dengan cara lain?",
            "Saya belum memahami pertanyaannya, {name} 😅 Bisakah diperjelas lagi?",
        ],
        "casual": [
            "Maaf nih, {name}, aku belum ngeh maksudnya 🤔 Bisa dijelasin sedikit lagi?",
            "Kayaknya aku belum nangkep, {name}. Coba cerita lebih detail ya?",
            "Hmm, masih bingung nih {name} 😅 Boleh jelasin ulang?",
        ],
    },
}

ANSWER_TEMPLATES = {
    "formal": [
        "Baik, {name}. Berikut jawabannya: {answer} 😊",
        "Penjelasannya untuk {name}: {answer_lower}",
        "Intinya, {name}: {answer} 👍",
        "Berikut penjelasannya untuk {name}: {answer}",
        "{answer} 🙌",
        "{answer} Semoga membantu, {name}. 😊",
    ],
    "casual": [
        "Oke {name}, gini ya: {answer} 😊",
        "Jadi ceritanya begini, {name}: {answer_lower}",
        "Singkatnya, {name}: {answer} 👍",
        "Nih jawaban lengkapnya buat {name}: {answer}",
        "{answer} 🙌",
        "{answer} Semoga kepake ya, {name}! 😊",
    ],
}

ANSWER_CLOSINGS = {
    "formal": [
        "\n\nApakah ada pertanyaan lain, {name}?",
        "\n\nJika masih kurang jelas, silakan ditanyakan kembali ya, {name}.",
        "\n\nSemoga membantu, {name}. 😊",
        "",
        "",
    ],
    "casual": [
        "\n\nAda yang mau ditanya lagi gak, {name}?",
        "\n\nKalau masih bingung, kabarin aja ya {name}.",
        "\n\nSemoga membantu ya, {name}! 😊",
        "",
        "",
    ],
}

FEEDBACK_PROMPT = {
    "formal": "Apakah jawaban tadi sudah membantu, {name}?",
    "casual": "Jawaban barusan udah membantu belum, {name}?",
}

FEEDBACK_OK_RESPONSE = {
    "formal": "Terima kasih atas konfirmasinya, {name}! Senang dapat membantu 😊",
    "casual": "Makasih ya, {name}! Senang bisa bantu 😊",
}

FEEDBACK_HELP_RESPONSE = {
    "formal": "Baik, {name}. Mari kita bahas kembali agar lebih jelas.",
    "casual": "Sip, {name}. Yuk kita cari tau bareng lagi.",
}

FOLLOW_UP_SUGGESTION_PROMPT = {
    "formal": "Apakah pertanyaan Anda terkait salah satu topik berikut, {name}?",
    "casual": "Kira-kira nyari info soal yang mana nih, {name}?",
}

FOLLOW_UP_DETAIL_PROMPT = {
    "formal": "Boleh jelaskan sedikit lebih detail agar saya bisa membantu lebih tepat, {name}?",
    "casual": "Coba cerita lebih detail ya, {name}, biar aku bisa bantu pas.",
}


def choose_small_talk(intent_key, tone, name):
    options = SMALL_TALK.get(intent_key, {}).get(tone) or SMALL_TALK.get(intent_key, {}).get("formal", [])
    if not options:
        return ""
    return personalize(random.choice(options), name)



# =============================
# FUNGSI FAQ
# =============================
def load_faq():
    if not os.path.exists(FAQ_FILE):
        faq_cache.update(
            {
                "mtime": None,
                "faqs": [],
                "clean_questions": [],
                "vectorizer": None,
                "matrix": None,
            }
        )
        return []

    mtime = os.path.getmtime(FAQ_FILE)
    if faq_cache["mtime"] == mtime and faq_cache["faqs"]:
        return faq_cache["faqs"]

    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    clean_questions = [clean_text(f.get("question", "")) for f in data]
    non_empty_questions = [q for q in clean_questions if q]

    vectorizer = None
    matrix = None
    if non_empty_questions:
        vectorizer = TfidfVectorizer(
            analyzer="word",
            ngram_range=(1, 2),
            min_df=1,
            lowercase=True,
        )
        vectorizer.fit(non_empty_questions)
        matrix = vectorizer.transform(clean_questions)

    faq_cache.update(
        {
            "mtime": mtime,
            "faqs": data,
            "clean_questions": clean_questions,
            "vectorizer": vectorizer,
            "matrix": matrix,
        }
    )

    return data


def clean_text(text):
    text = re.sub(r"[^a-zA-Z0-9\s]", "", text)
    return text.lower().strip()


def detect_intent(user_q):
    """Deteksi apakah ini greeting, thanks, atau pertanyaan biasa"""
    q_lower = user_q.lower().strip()
    
    # Cek greeting
    if any(greet in q_lower for greet in GREETINGS) and len(q_lower) < 20:
        return "greeting"
    
    # Cek thanks
    if any(thx in q_lower for thx in THANKS):
        return "thanks"
    
    return "question"


def find_best_faq(user_q):
    faqs = load_faq()
    if not faqs:
        return []

    user_q_clean = clean_text(user_q)
    clean_questions = faq_cache["clean_questions"]
    vectorizer = faq_cache["vectorizer"]
    matrix = faq_cache["matrix"]

    if not clean_questions:
        return []

    fuzzy_scores = []
    for question in clean_questions:
        if question:
            fuzzy_scores.append(fuzz.WRatio(user_q_clean, question))
        else:
            fuzzy_scores.append(0)

    if vectorizer is not None and matrix is not None:
        user_vec = vectorizer.transform([user_q_clean])
        cosine_scores = linear_kernel(user_vec, matrix).flatten()
    else:
        cosine_scores = [0.0 for _ in clean_questions]

    ranked_results = []
    for idx, faq in enumerate(faqs):
        fuzzy_score = float(fuzzy_scores[idx]) if idx < len(fuzzy_scores) else 0.0
        tfidf_raw = float(cosine_scores[idx]) if idx < len(cosine_scores) else 0.0
        tfidf_score = max(0.0, min(tfidf_raw * 100, 100.0))
        combined_score = 0.6 * fuzzy_score + 0.4 * tfidf_score

        ranked_results.append(
            {
                "question": faq.get("question", ""),
                "answer": faq.get("answer", ""),
                "score": combined_score,
                "fuzzy": fuzzy_score,
                "tfidf": tfidf_score,
                "index": idx,
            }
        )

    ranked_results.sort(key=lambda item: item["score"], reverse=True)

    return ranked_results[:3]


# =============================
# HUMANIZE RESPONSE
# =============================
def humanize_answer(question, answer, user_q, user_name=None, tone="formal"):
    """Bikin jawaban dari FAQ jadi lebih natural dan humanis"""
    name_placeholder = user_name or "Anda"

    response_templates = ANSWER_TEMPLATES.get(tone, ANSWER_TEMPLATES["formal"])
    closings = ANSWER_CLOSINGS.get(tone, ANSWER_CLOSINGS["formal"])

    base_response = random.choice(response_templates).format(
        name=name_placeholder,
        answer=answer,
        answer_lower=answer.lower(),
    )
    
    closing = random.choice(closings).format(name=name_placeholder)
    
    return base_response + closing


# =============================
# HANDLER TELEGRAM
# =============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_context[user_id] = []  # Reset context
    set_user_tone(user_id, "formal")
    name = get_user_display_name(update.effective_user)
    
    greeting_text = (
        "Halo {name}! 👋 Saya asisten virtual Program Studi Teknik Informatika.\n\n"
        "Anda dapat menanyakan apa pun terkait prodi, dan saya akan membantu sebisa mungkin. 😊\n\n"
        "Silakan bertanya dengan bahasa Anda sendiri. 🙌"
    )
    await update.message.reply_text(personalize(greeting_text, name))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_q = update.message.text.strip()
    user_id = update.message.from_user.id
    user_name = get_user_display_name(update.effective_user)
    detected_tone = detect_tone_from_message(user_q)
    if detected_tone:
        set_user_tone(user_id, detected_tone)
    tone = get_user_tone(user_id)
    name_placeholder = user_name or "Anda"
    logger.info("Incoming message | user=%s | text=%s", user_id, user_q)
    
    # Deteksi intent dulu
    intent = detect_intent(user_q)
    
    # Handle small talk
    if intent == "greeting":
        response = choose_small_talk("greeting", tone, user_name)
        metrics["greeting"] += 1
        await update.message.reply_text(response)
        return
    
    if intent == "thanks":
        response = choose_small_talk("thanks", tone, user_name)
        metrics["thanks"] += 1
        await update.message.reply_text(response)
        return
    
    # Cari FAQ
    matches = find_best_faq(user_q)

    if not matches:
        response = choose_small_talk("confused", tone, user_name)
        metrics["no_match"] += 1
        logger.info("FAQ match not found | user=%s | text=%s", user_id, user_q)

        faqs = load_faq()
        if faqs:
            sample_questions = random.sample([f["question"] for f in faqs], min(3, len(faqs)))
            response += "\n\nMungkin Anda bermaksud menanyakan:\n"
            for i, sq in enumerate(sample_questions, 1):
                response += f"{i}. {sq}\n"

        await update.message.reply_text(response)
        return

    best_match = matches[0]
    best_score = best_match["score"]
    logger.info(
        "FAQ match candidate | user=%s | score=%.2f | fuzzy=%.2f | tfidf=%.2f | question=%s",
        user_id,
        best_score,
        best_match.get("fuzzy", 0.0),
        best_match.get("tfidf", 0.0),
        best_match["question"],
    )

    if best_score < CLARIFICATION_THRESHOLD:
        response = choose_small_talk("confused", tone, user_name)
        metrics["clarification_prompt"] += 1
        logger.info(
            "Clarification requested | user=%s | score=%s | matches=%s",
            user_id,
            best_score,
            [m["question"] for m in matches],
        )

        keyboard_buttons = [
            [InlineKeyboardButton(text=m["question"], callback_data=f"faq::{m['index']}")]
            for m in matches
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_buttons) if keyboard_buttons else None
        last_suggestions[user_id].clear()
        for m in matches:
            last_suggestions[user_id].append(
                {"question": m["question"], "index": m["index"]}
            )
        last_answer[user_id] = None

        await update.message.reply_text(response, reply_markup=reply_markup)
        return

    if best_score < SIMILARITY_THRESHOLD:
        keyboard_buttons = [
            [InlineKeyboardButton(text=m["question"], callback_data=f"faq::{m['index']}")]
            for m in matches
        ]
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        last_suggestions[user_id].clear()
        for m in matches:
            last_suggestions[user_id].append(
                {"question": m["question"], "index": m["index"]}
            )
        last_answer[user_id] = None

        clarification_text = (
            f"Saya menemukan beberapa pertanyaan yang mungkin relevan, {name_placeholder}. "
            "Silakan pilih salah satu:"
        )
        metrics["clarification_menu"] += 1
        logger.info(
            "Clarification menu shown | user=%s | score=%s | options=%s",
            user_id,
            best_score,
            [m["question"] for m in matches],
        )
        await update.message.reply_text(clarification_text, reply_markup=reply_markup)
        return

    # Simpan ke context (max 5 interaksi terakhir)
    user_context[user_id].append(f"Q: {user_q[:50]}")
    if len(user_context[user_id]) > 5:
        user_context[user_id].pop(0)

    # Generate jawaban natural tanpa LLM
    response = humanize_answer(
        best_match["question"],
        best_match["answer"],
        user_q,
        user_name=user_name,
        tone=tone,
    )
    last_answer[user_id] = best_match["question"]

    suggestions = [
        m for m in matches[1:] if m["score"] >= CLARIFICATION_THRESHOLD
    ]
    last_suggestions[user_id].clear()

    if suggestions:
        keyboard_buttons = [
            [InlineKeyboardButton(text=m["question"], callback_data=f"faq::{m['index']}")]
            for m in suggestions
        ]
        for m in suggestions:
            last_suggestions[user_id].append(
                {"question": m["question"], "index": m["index"]}
            )
        reply_markup = InlineKeyboardMarkup(keyboard_buttons)
        metrics["answer_with_suggestions"] += 1
        logger.info(
            "FAQ answered with suggestions | user=%s | base=%s | suggestions=%s",
            user_id,
            best_match["question"],
            [m["question"] for m in suggestions],
        )
        await update.message.reply_text(response, reply_markup=reply_markup)
    else:
        last_suggestions[user_id].clear()
        metrics["answer_direct"] += 1
        logger.info(
            "FAQ answered directly | user=%s | question=%s",
            user_id,
            best_match["question"],
        )
        await update.message.reply_text(response)

    feedback_template = FEEDBACK_PROMPT.get(tone, FEEDBACK_PROMPT["formal"])
    feedback_prompt = personalize(feedback_template, user_name)
    await update.message.reply_text(feedback_prompt, reply_markup=build_feedback_markup())


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = (query.data or "").strip()
    name = get_user_display_name(query.from_user)
    tone = get_user_tone(user_id)
    logger.info("Callback received | user=%s | data=%s", user_id, data)
    await query.answer()

    if data.startswith("feedback::"):
        action = data.split("::", 1)[1] if "::" in data else ""
        await query.edit_message_reply_markup(reply_markup=None)
        if action == "ok":
            metrics["feedback_ok"] += 1
            logger.info("Feedback positive | user=%s", user_id)
            appreciation_template = FEEDBACK_OK_RESPONSE.get(tone, FEEDBACK_OK_RESPONSE["formal"])
            appreciation = personalize(appreciation_template, name)
            await query.message.reply_text(appreciation)
        elif action == "help":
            metrics["feedback_help"] += 1
            logger.info("Feedback follow-up requested | user=%s", user_id)
            follow_template = FEEDBACK_HELP_RESPONSE.get(tone, FEEDBACK_HELP_RESPONSE["formal"])
            await query.message.reply_text(personalize(follow_template, name))

            suggestions = list(last_suggestions[user_id])
            if suggestions:
                prompt_template = FOLLOW_UP_SUGGESTION_PROMPT.get(tone, FOLLOW_UP_SUGGESTION_PROMPT["formal"])
                keyboard_buttons = [
                    [InlineKeyboardButton(text=s["question"], callback_data=f"faq::{s['index']}")]
                    for s in suggestions
                ]
                await query.message.reply_text(
                    personalize(prompt_template, name),
                    reply_markup=InlineKeyboardMarkup(keyboard_buttons),
                )
            else:
                detail_template = FOLLOW_UP_DETAIL_PROMPT.get(tone, FOLLOW_UP_DETAIL_PROMPT["formal"])
                await query.message.reply_text(personalize(detail_template, name))
        else:
            logger.warning("Unknown feedback action | user=%s | action=%s", user_id, action)
        return

    if not data.startswith("faq::"):
        logger.warning("Unknown callback data | user=%s | data=%s", user_id, data)
        return

    try:
        idx = int(data.split("::", 1)[1])
    except (ValueError, TypeError):
        logger.error("Invalid callback data | user=%s | data=%s", user_id, data)
        return

    faqs = load_faq()
    if idx < 0 or idx >= len(faqs):
        await query.answer("Mohon maaf, informasi tidak tersedia.", show_alert=True)
        logger.error("FAQ index out of range | user=%s | idx=%s", user_id, idx)
        return

    faq = faqs[idx]
    user_context[user_id].append(f"CB: {faq['question'][:50]}")
    if len(user_context[user_id]) > 5:
        user_context[user_id].pop(0)

    answer_text = humanize_answer(
        faq["question"],
        faq["answer"],
        faq["question"],
        user_name=name,
        tone=tone,
    )
    last_answer[user_id] = faq["question"]
    last_suggestions[user_id].clear()

    metrics["callback_answered"] += 1
    logger.info(
        "Callback answered | user=%s | question=%s",
        user_id,
        faq["question"],
    )

    await query.message.reply_text(answer_text)
    feedback_template = FEEDBACK_PROMPT.get(tone, FEEDBACK_PROMPT["formal"])
    feedback_prompt = personalize(feedback_template, name)
    await query.message.reply_text(feedback_prompt, reply_markup=build_feedback_markup())


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = ["Statistik interaksi bot:"]
    for key, value in sorted(metrics.items()):
        lines.append(f"- {key}: {value}")
    await update.message.reply_text("\n".join(lines))

# =============================
# MAIN APP
# =============================
async def main():
    token = TOKEN
    if not token:
        raise RuntimeError(
            "Token Telegram belum diset. Isi TELEGRAM_TOKEN di .env atau langsung isi HARD_CODED_TOKEN di bot.py."
        )
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))

    print("🤖 Bot sedang berjalan. Tekan CTRL+C untuk berhenti.")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())
