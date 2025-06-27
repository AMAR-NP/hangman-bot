import random
import logging
import sqlite3
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# ===== SETUP LOGGING =====
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== GAME CONFIGURATION =====
FALLBACK_DICT = {
    "PYTHON": "A snake that's fluent in syntax.",
    "JAVASCRIPT": "Often tied in knots, but makes websites run.",
    "TELEGRAM": "It delivers texts, stickers, and bots alike.",
    "HANGMAN": "Your limbs depend on your guesses in this game.",
    "DEVELOPER": "One who builds with lines but no bricks.",
    "GAMING": "When pixels meet passion and reflex.",
    "PROGRAMMING": "Long word for long hours of logic loops.",
    "LOFT": "A small space up high or a stylish apartment?",
    "GAZE": "A lingering look or a crystal ball skill.",
    "MINT": "Tingly fresh and good for leaves and code.",
    "BRIM": "The edge that barely holds it all together.",
    "COVE": "A curve in the coast or a hollow in sound.",
    "SNAP": "Quick motion with a sound to match.",
    "WISP": "A curl of air or a soft spirit-like trail.",
    "HUSH": "Silence's twin, often whispered.",
    "DUNE": "Where sand sleeps and wind sketches.",
    "GLIM": "A faint light or a rare spark of insight.",
    "CRISP": "Sharp and cool—like a chip or a breeze.",
    "BLAZE": "Flame's cousin, often in comic books.",
    "NUDGE": "A soft push that might change your mind.",
    "TWINE": "Twisted strands that hold things close.",
    "PLUME": "Feathered puff or a poet's breath.",
    "GRASP": "A firm hold on ideas or objects.",
    "KNACK": "A knack for problems, often quirky.",
    "SLOPE": "This slope's slippery—step carefully.",
    "QUEST": "The dragon's trail or the hero's aim.",
    "FABLE": "A tale that teaches, told with charm.",
    "FLINT": "Hard as rock, but sparks fly when struck.",
    "SPIRE": "It reaches for the sky, but never leaves the ground.",
    "DRIFT": "It moves without purpose, like snow or thought.",
    "FORGE": "Where metal meets fire—or truth meets fiction.",
    "RAVEN": "Dark as night, it croaks of omens.",
    "CHIME": "It sings when struck, marking time or mood.",
    "FLICK": "A quick move or a short film.",
    "GRIME": "Dirt's stubborn cousin, clings to effort.",
    "THORN": "Beauty's bodyguard on a stem.",
    "CRATE": "A box with purpose, often wooden and worn.",
    "SPOOK": "A whisper in the dark or a sudden chill.",
    "BRISK": "Quick and cool, like a morning walk.",
    "LEDGE": "A narrow edge where birds or danger rest.",
    "MIRTH": "Laughter's quieter twin, full of light.",
    "KNOLL": "A hill so small it barely boasts."
}

# ===== HANGMAN ASCII ART =====
HANGMAN_ART = [
    """
    ┌─────
    │    │
    │    
    │    
    │    
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😮
    │    
    │    
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😮
    │    │
    │    
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😮
    │   /│
    │    
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😮
    │   /│\\
    │    
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😮
    │   /│\\
    │   / 
    │    
    ┴───────
    """,
    """
    ┌─────
    │    │
    │    😵
    │   /│\\
    │   / \\
    │    
    ┴───────
    """
]

# ===== GAME STATE =====
games = {}

# ===== DATABASE FUNCTIONS =====
def init_db():
    """Initialize the database"""
    conn = sqlite3.connect('hangman_scores.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players
                 (user_id INTEGER PRIMARY KEY, 
                  username TEXT,
                  games_played INTEGER DEFAULT 0,
                  games_won INTEGER DEFAULT 0,
                  total_score INTEGER DEFAULT 0,
                  last_played TEXT)''')
    conn.commit()
    conn.close()

def get_player_stats(user_id: int):
    """Get player statistics from the database"""
    conn = sqlite3.connect('hangman_scores.db')
    c = conn.cursor()
    c.execute('''SELECT games_played, games_won, total_score 
                 FROM players 
                 WHERE user_id = ?''', (user_id,))
    stats = c.fetchone()
    conn.close()
    return stats

def get_leaderboard(limit: int = 10):
    """Get top players from the database"""
    conn = sqlite3.connect('hangman_scores.db')
    c = conn.cursor()
    c.execute('''SELECT username, games_won, total_score 
                 FROM players 
                 ORDER BY total_score DESC 
                 LIMIT ?''', (limit,))
    leaderboard = c.fetchall()
    conn.close()
    return leaderboard

def update_score(user_id: int, username: str, won: bool, score: int = 0):
    """Update player stats in the database"""
    conn = sqlite3.connect('hangman_scores.db')
    c = conn.cursor()
    
    # Get current stats
    c.execute('SELECT * FROM players WHERE user_id = ?', (user_id,))
    player = c.fetchone()
    
    if player:
        games_played = player[2] + 1
        games_won = player[3] + (1 if won else 0)
        total_score = player[4] + score
        c.execute('''UPDATE players 
                     SET games_played = ?, 
                         games_won = ?,
                         total_score = ?,
                         last_played = ?,
                         username = ?
                     WHERE user_id = ?''',
                  (games_played, games_won, total_score, datetime.now().isoformat(), username, user_id))
    else:
        c.execute('''INSERT INTO players 
                     (user_id, username, games_played, games_won, total_score, last_played)
                     VALUES (?, ?, 1, ?, ?, ?)''',
                  (user_id, username, 1 if won else 0, score, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

# ===== GAME FUNCTIONS =====
def get_random_word():
    """Select a random word and its hint from the dictionary"""
    word = random.choice(list(FALLBACK_DICT.keys()))
    return word, FALLBACK_DICT[word]

def display_game_state(game):
    """Generate the current game status message"""
    displayed_word = " ".join(
        letter if letter in game["guessed_letters"] else "_"
        for letter in game["word"]
    )
    return (
        f"🔠 Word: {displayed_word}\n"
        f"💡 Hint: {game['hint']}\n"
        f"📝 Guessed: {', '.join(sorted(game['guessed_letters'])) or 'None'}\n"
        f"❤️ Lives: {game['lives']}/6\n"
        f"{HANGMAN_ART[6 - game['lives']]}"
    )

# ===== TELEGRAM HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        user = update.effective_user
        word, hint = get_random_word()
        
        games[chat_id] = {
            "word": word,
            "hint": hint,
            "guessed_letters": [],
            "lives": 6,
            "player_id": user.id,
            "player_name": user.full_name
        }
        
        await update.message.reply_text(
            f"🎮 *Hangman Game Started!* {user.mention_markdown()}\n"
            f"📏 Word has {len(word)} letters\n"
            f"💡 Hint: {hint}",
            parse_mode="Markdown"
        )
        await send_game_update(update, chat_id)
        
    except Exception as e:
        logger.error(f"Start error: {e}")
        await update.message.reply_text("🚨 Failed to start game. Please try again.")

async def send_game_update(update: Update, chat_id):
    """Send the current game state"""
    try:
        game = games[chat_id]
        await update.message.reply_text(display_game_state(game))
    except KeyError:
        await update.message.reply_text("Game not found. Type /start to begin.")
    except BadRequest:
        await update.message.reply_text(display_game_state(game).replace("💡", "Hint:").replace("🔠", "Word:"))

async def handle_guess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        chat_id = update.message.chat_id
        user = update.effective_user
        user_input = update.message.text.upper()
        
        if chat_id not in games:
            await update.message.reply_text("Type /start to begin a new game!")
            return
        
        game = games[chat_id]
        
        # Input validation
        if len(user_input) != 1 or not user_input.isalpha():
            await update.message.reply_text("Please enter a single letter!")
            return
            
        if user_input in game["guessed_letters"]:
            await update.message.reply_text("You already guessed that letter!")
            return
            
        # Process guess
        game["guessed_letters"].append(user_input)
        
        if user_input not in game["word"]:
            game["lives"] -= 1
            await update.message.reply_text("❌ Incorrect guess!")
        else:
            await update.message.reply_text("✅ Correct guess!")
        
        # Check game status
        if all(letter in game["guessed_letters"] for letter in game["word"]):
            score = len(game["word"]) * 10 + game["lives"] * 5
            update_score(
                user_id=game["player_id"],
                username=game["player_name"],
                won=True,
                score=score
            )
            await update.message.reply_text(
                f"🎉 *You won!* The word was: {game['word']}\n"
                f"🏆 Score: +{score} points!\n"
                "Play again with /start\n"
                "Check /stats for your progress",
                parse_mode="Markdown"
            )
            del games[chat_id]
        elif game["lives"] <= 0:
            update_score(
                user_id=game["player_id"],
                username=game["player_name"],
                won=False
            )
            await update.message.reply_text(
                f"💀 *Game Over!* The word was: {game['word']}\n\n"
                "Play again with /start\n"
                "Check /stats for your progress",
                parse_mode="Markdown"
            )
            del games[chat_id]
        else:
            await send_game_update(update, chat_id)
            
    except Exception as e:
        logger.error(f"Guess error: {e}")
        await update.message.reply_text("🚨 Error processing your guess. Please try again.")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        stats = get_player_stats(user.id)
        
        if not stats:
            await update.message.reply_text("You haven't played any games yet! Type /start to begin.")
            return
            
        win_percentage = (stats[1] / stats[0]) * 100 if stats[0] > 0 else 0
        
        await update.message.reply_text(
            f"📊 *Your Stats* {user.mention_markdown()}\n\n"
            f"🎮 Games Played: {stats[0]}\n"
            f"🏆 Games Won: {stats[1]} ({win_percentage:.1f}%)\n"
            f"⭐ Total Score: {stats[2]}\n\n"
            "Check /leaderboard for top players",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Stats error: {e}")
        await update.message.reply_text("🚨 Couldn't fetch your stats. Please try again.")

async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        leaderboard = get_leaderboard()
        
        if not leaderboard:
            await update.message.reply_text("No players yet! Be the first with /start")
            return
            
        leaderboard_text = "🏆 *Top Players* 🏆\n\n"
        for i, (username, wins, score) in enumerate(leaderboard, 1):
            leaderboard_text += f"{i}. {username}: {score} pts ({wins} wins)\n"
            
        await update.message.reply_text(
            leaderboard_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
        await update.message.reply_text("🚨 Couldn't fetch leaderboard. Please try again.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 *Hangman Bot Help*\n\n"
        "🔹 /start - Begin new game\n"
        "🔹 /stats - View your statistics\n"
        "🔹 /leaderboard - See top players\n"
        "🔹 /help - Show this message\n\n"
        "How to play:\n"
        "1. Guess letters one at a time\n"
        "2. Solve the word before the hangman is complete\n"
        "3. Earn more points for longer words and remaining lives",
        parse_mode="Markdown"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle all errors."""
    logger.error(msg="Exception while handling update:", exc_info=context.error)
    if update and hasattr(update, 'message'):
        try:
            await update.message.reply_text('⚠️ An error occurred. Please try again or /start a new game.')
        except:
            pass

# ===== BOT SETUP =====
def main():
    """Run the bot."""
    # Initialize database
    init_db()
    
    # Create Application
    application = Application.builder().token("7762698810:AAHJdUVaS17C3pJnYYS-kxlViFsL4-iIgzA").build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("leaderboard", show_leaderboard))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_guess))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    logger.info("Bot is running and polling...")
    application.run_polling()

if __name__ == "__main__":
    main()