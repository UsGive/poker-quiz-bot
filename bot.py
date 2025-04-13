import logging
import os
from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Quiz content with associated video filenames
questions = [
    {
        "stage": "Preflop",
        "video": "videos/1. Part 1 (Th Ts) Pre.mp4",
        "question": "Preflop: What would you like to do with ThTs on the Button?",
        "options": {
            "A": {"text": "Call", "score": 7},
            "B": {"text": "Raise to 4", "score": 8},
            "C": {"text": "Raise to 5", "score": 8},
            "D": {"text": "Raise to 7", "score": 10}
        }
    },
    {
        "stage": "Flop",
        "video": "videos/1. Part 2 (Th Ts) Flop.mp4",
        "question": "Flop: What’s your best move here?",
        "options": {
            "A": {"text": "Check", "score": 6},
            "B": {"text": "Bet 4.2", "score": 8},
            "C": {"text": "Bet 9.35", "score": 10},
            "D": {"text": "Bet 16.7", "score": 8}
        }
    },
    {
        "stage": "Turn",
        "video": "videos/1. Part 3 (Th Ts) Turn.mp4",
        "question": "Turn: What's the right play?",
        "options": {
            "A": {"text": "Check", "score": 10},
            "B": {"text": "Bet 9", "score": 8},
            "C": {"text": "Bet 18", "score": 7},
            "D": {"text": "Bet 35.4", "score": 7}
        }
    },
    {
        "stage": "River",
        "video": "videos/1. Part 4 (Th Ts) River.mp4",
        "question": "River: What's your action?",
        "options": {
            "A": {"text": "Call", "score": 10},
            "B": {"text": "Raise to 10.04", "score": 8},
            "C": {"text": "Raise to 15", "score": 8},
            "D": {"text": "Raise All-in", "score": 7}
        }
    }
]

# Path to final explanation video
final_video = "videos/Part 5 Explanation.mp4"

user_states = {}

# Conversation state for AI Analysis
AI_STAGE = range(1)

SYSTEM_PROMPT = (
    "You are a professional poker coach. Analyze the player's reasoning concisely and clearly. "
    "Keep the answer under 100 words. Avoid introductions like 'Of course' or 'Sure'. "
    "Speak in the first person as a coach. Do not include generic phrases, focus strictly on the hand."
)

# AI analysis handlers
async def ai_analysis_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🧠 Please describe your thought process on this hand:")
    return AI_STAGE

async def ai_analysis_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    await update.message.reply_text("✅ Got it! I'm sending this to AI for analysis...")

    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            temperature=0.7,
            max_tokens=300
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ AI error: {e}")

    return ConversationHandler.END

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_states[user_id] = {"current": 0, "score": 0}
    await send_question(update, context)

# Send next question with video
async def send_question(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(update_or_query, Update):
        user_id = update_or_query.effective_user.id
        chat_id = update_or_query.effective_chat.id
    else:
        user_id = update_or_query.from_user.id
        chat_id = update_or_query.message.chat_id

    state = user_states[user_id]
    idx = state["current"]

    if idx >= len(questions):
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Quiz complete! You scored {state['score']} out of 40."
        )
        user_states[user_id] = {"current": 0, "score": 0}  # Reset for next run
        if os.path.exists(final_video):
            try:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=open(final_video, 'rb'),
                    caption="📽️ Here's the expert explanation for this hand."
                )
            except Exception as e:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ Explanation video failed to load. Error: {e}"
                )
        await context.bot.send_message(
            chat_id=chat_id,
            text="Try again 👇",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Try again"), KeyboardButton("AI Analysis")],
                 [KeyboardButton("Ask Alex")]], resize_keyboard=True, one_time_keyboard=False, selective=True
            )
        )
        return

    q = questions[idx]

    # Send video
    if os.path.exists(q["video"]):
        await context.bot.send_video(
            chat_id=chat_id,
            video=open(q["video"], 'rb'),
            caption=f"{q['stage']} — Watch this first."
        )

    # Send question
    inline_keyboard = [
        [InlineKeyboardButton(f"{key}) {value['text']}", callback_data=key)]
        for key, value in q["options"].items()
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"{q['stage']}\n\n{q['question']}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard)
    )

# Handle answer
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    state = user_states[user_id]
    idx = state["current"]
    answer = query.data

    score = questions[idx]["options"][answer]["score"]
    state["score"] += score
    state["current"] += 1

    await query.edit_message_text("✅ Answer recorded! Moving to next question...")
    await send_question(query, context)

# Build bot
conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & filters.Regex("^Ask Alex$"), ai_analysis_start)],
    states={
        AI_STAGE: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_process)],
    },
    fallbacks=[]
)

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Try again$"), start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^AI Analysis$"), start))
    app.run_polling()

# Entry point
if __name__ == '__main__':
    main()
