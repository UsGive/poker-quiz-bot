import logging
import os
from openai import OpenAI
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters, ConversationHandler
)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# === PROMPT ===
SYSTEM_PROMPT = (
    "You are a professional poker coach. Analyze the player's reasoning based on the hand. "
    "Respond strictly to the point. Keep your answer under 100 words. Avoid filler phrases like 'of course', 'obviously', or 'sure'. "
    "Be concise, clear, and direct. Focus only on the relevant actions. "
    "If the opponent might have a flush or straight, but it's not confirmed yet, refer to it as a 'draw' or 'possible draw'. "
    "Do not speculate beyond the given information."
)

# === TEST SECTION ===
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
final_video = "videos/Part 5 Explanation.mp4"
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Удаляем условие, которое мешает запуску теста
    user_states[user_id] = {"current": 0, "score": 0}
    await update.message.reply_text("📍 Starting the quiz...")  # Чтобы видеть, что функция вызвалась
    await send_question(update, context)

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
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Quiz complete! You scored {state['score']} out of 40.")
        user_states[user_id] = {"current": 0, "score": 0}
        if os.path.exists(final_video):
            await context.bot.send_video(chat_id=chat_id, video=open(final_video, 'rb'), caption="📽️ Here's the expert explanation for this hand.")
        await context.bot.send_message(
            chat_id=chat_id,
            text="Choose an option 👇",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("Try again"), KeyboardButton("Ask Alex")],
                 [KeyboardButton("AI Analysis")]], resize_keyboard=True
            )
        )
        return

    q = questions[idx]
    if os.path.exists(q["video"]):
        await context.bot.send_video(chat_id=chat_id, video=open(q["video"], 'rb'), caption=f"{q['stage']} — Watch this first.")
    inline_keyboard = [[InlineKeyboardButton(f"{k}) {v['text']}", callback_data=k)] for k, v in q["options"].items()]
    await context.bot.send_message(chat_id=chat_id, text=f"{q['stage']}\n\n{q['question']}", reply_markup=InlineKeyboardMarkup(inline_keyboard))

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

# === AI ANALYSIS ===
AI_STAGE_1, AI_STAGE_2, AI_STAGE_3, AI_STAGE_4, AI_STAGE_5, AI_STAGE_6 = range(6)

async def ai_analysis_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Step 1 of 6:\nWhat's your position and hand?\n\n🃏 Example: Button, Th Ts")
    return AI_STAGE_1

async def ai_analysis_stage_1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['position_hand'] = update.message.text
    await update.message.reply_text("Step 2 of 6:\nEnter stacks in BBs.\n\n💰 Example: Hero 100bb, Villain 80bb")
    return AI_STAGE_2

async def ai_analysis_stage_2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['stacks'] = update.message.text
    await update.message.reply_text("Step 3 of 6:\nDescribe preflop actions.\n\n♠️ Example: Hero raises to 2bb, BB calls")
    return AI_STAGE_3

async def ai_analysis_stage_3(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['preflop'] = update.message.text
    await update.message.reply_text("Step 4 of 6:\nDescribe flop actions.\n\n♦️ Example: Flop Jc 5s 3h — Hero bets 3bb, Villain calls")
    return AI_STAGE_4

async def ai_analysis_stage_4(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['flop'] = update.message.text
    await update.message.reply_text("Step 5 of 6:\nDescribe turn and river actions.\n\n🃓 Example: Turn Qh — check-check, River 6c — Hero checks, Villain bets 10bb, Hero folds")
    return AI_STAGE_5

async def ai_analysis_stage_5(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['turn_river'] = update.message.text
    await update.message.reply_text("Step 6 of 6:\nOptional: Add any extra context (result, notes, etc.)\n\n📌 Example: Opponent showed AK, pot was 40bb")
    return AI_STAGE_6

async def ai_analysis_stage_6(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['notes'] = update.message.text
    await update.message.reply_text("✅ Got it! Sending to AI for analysis...")
    full_input = (
        f"Position and Hand: {context.user_data['position_hand']}\n"
        f"Stacks: {context.user_data['stacks']}\n"
        f"Preflop: {context.user_data['preflop']}\n"
        f"Flop: {context.user_data['flop']}\n"
        f"Turn and River: {context.user_data['turn_river']}\n"
        f"Extra Notes: {context.user_data['notes']}"
    )
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": full_input}],
            temperature=0.7, max_tokens=300
        )
        reply = response.choices[0].message.content
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"⚠️ AI error: {e}")
    return ConversationHandler.END

conv_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.TEXT & filters.Regex("^AI Analysis$"), ai_analysis_start)],
    states={
        AI_STAGE_1: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_1)],
        AI_STAGE_2: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_2)],
        AI_STAGE_3: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_3)],
        AI_STAGE_4: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_4)],
        AI_STAGE_5: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_5)],
        AI_STAGE_6: [MessageHandler(filters.TEXT & (~filters.COMMAND), ai_analysis_stage_6)],
    },
    fallbacks=[]
)

def main():
    app = ApplicationBuilder().token(os.getenv("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Try again$"), start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(conv_handler)
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^Ask Alex$"), start))
    app.run_polling()

if __name__ == '__main__':
    main()
