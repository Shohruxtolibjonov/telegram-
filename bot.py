import asyncio
import json
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiohttp import web
import aiosqlite

# Configuration
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
WEB_APP_URL = "https://your-netlify-app.netlify.app"  # Replace with your Netlify URL
ADMIN_IDS = [123456789]  # Replace with admin Telegram IDs

# Initialize bot
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
logging.basicConfig(level=logging.INFO)

# Database setup
async def init_db():
    async with aiosqlite.connect('edubot.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                name TEXT,
                phone TEXT,
                language TEXT DEFAULT 'uz',
                is_pro INTEGER DEFAULT 0,
                pro_requested INTEGER DEFAULT 0,
                registered_at TEXT
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_id INTEGER,
                game_type TEXT,
                title TEXT,
                questions TEXT,
                share_link TEXT,
                created_at TEXT,
                FOREIGN KEY (creator_id) REFERENCES users(user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS game_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id INTEGER,
                player_id INTEGER,
                score INTEGER,
                played_at TEXT,
                FOREIGN KEY (game_id) REFERENCES games(id)
            )
        ''')
        await db.commit()

# Language texts
TEXTS = {
    'uz': {
        'welcome': "🎮 Ta'lim o'yinlari platformasiga xush kelibsiz!\n\nTilni tanlang:",
        'request_name': "Ismingizni kiriting:",
        'request_contact': "Telefon raqamingizni yuboring:",
        'registration_complete': "✅ Ro'yxatdan o'tdingiz!\n\nEndi o'yinlar yaratishingiz va o'ynashingiz mumkin.",
        'main_menu': "🏠 Asosiy menyu",
        'open_app': "🎮 O'yinlar platformasini ochish",
        'contact_admin': "📞 Admin bilan bog'lanish",
        'admin_contacted': "✅ Xabaringiz adminga yuborildi!"
    },
    'en': {
        'welcome': "🎮 Welcome to Educational Games Platform!\n\nSelect your language:",
        'request_name': "Enter your name:",
        'request_contact': "Share your phone number:",
        'registration_complete': "✅ Registration complete!\n\nYou can now create and play games.",
        'main_menu': "🏠 Main Menu",
        'open_app': "🎮 Open Games Platform",
        'contact_admin': "📞 Contact Admin",
        'admin_contacted': "✅ Your message was sent to admin!"
    },
    'ru': {
        'welcome': "🎮 Добро пожаловать на платформу образовательных игр!\n\nВыберите язык:",
        'request_name': "Введите ваше имя:",
        'request_contact': "Поделитесь номером телефона:",
        'registration_complete': "✅ Регистрация завершена!\n\nТеперь вы можете создавать и играть в игры.",
        'main_menu': "🏠 Главное меню",
        'open_app': "🎮 Открыть платформу игр",
        'contact_admin': "📞 Связаться с админом",
        'admin_contacted': "✅ Ваше сообщение отправлено администратору!"
    }
}

# User state management
user_states = {}

# Start command
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (message.from_user.id,))
        user = await cursor.fetchone()
    
    if user:
        await show_main_menu(message)
    else:
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="🇺🇿 O'zbek"), KeyboardButton(text="🇬🇧 English")],
                [KeyboardButton(text="🇷🇺 Русский")]
            ],
            resize_keyboard=True
        )
        await message.answer(TEXTS['uz']['welcome'], reply_markup=keyboard)
        user_states[message.from_user.id] = {'step': 'language'}

# Language selection
@dp.message(F.text.in_(["🇺🇿 O'zbek", "🇬🇧 English", "🇷🇺 Русский"]))
async def select_language(message: types.Message):
    lang_map = {"🇺🇿 O'zbek": "uz", "🇬🇧 English": "en", "🇷🇺 Русский": "ru"}
    lang = lang_map[message.text]
    user_states[message.from_user.id] = {'step': 'name', 'language': lang}
    
    await message.answer(
        TEXTS[lang]['request_name'],
        reply_markup=types.ReplyKeyboardRemove()
    )

# Name input
@dp.message(F.text & ~F.text.startswith('/'))
async def handle_text_input(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    
    if state.get('step') == 'name':
        user_states[user_id]['name'] = message.text
        user_states[user_id]['step'] = 'contact'
        lang = state.get('language', 'uz')
        
        keyboard = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📱 Share Contact", request_contact=True)]],
            resize_keyboard=True
        )
        await message.answer(TEXTS[lang]['request_contact'], reply_markup=keyboard)

# Contact received
@dp.message(F.contact)
async def handle_contact(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    
    if state.get('step') == 'contact':
        async with aiosqlite.connect('edubot.db') as db:
            await db.execute('''
                INSERT OR REPLACE INTO users (user_id, username, name, phone, language, registered_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                message.from_user.username or '',
                state.get('name', ''),
                message.contact.phone_number,
                state.get('language', 'uz'),
                datetime.now().isoformat()
            ))
            await db.commit()
        
        lang = state.get('language', 'uz')
        await message.answer(
            TEXTS[lang]['registration_complete'],
            reply_markup=types.ReplyKeyboardRemove()
        )
        user_states.pop(user_id, None)
        await show_main_menu(message)

# Main menu
async def show_main_menu(message: types.Message):
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT language FROM users WHERE user_id = ?', (message.from_user.id,))
        result = await cursor.fetchone()
        lang = result[0] if result else 'uz'
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=TEXTS[lang]['open_app'], web_app=WebAppInfo(url=WEB_APP_URL))],
            [KeyboardButton(text=TEXTS[lang]['contact_admin'])]
        ],
        resize_keyboard=True
    )
    await message.answer(TEXTS[lang]['main_menu'], reply_markup=keyboard)

# Admin commands
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("❌ Access denied")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 View Users", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton(text="✅ Pending Approvals", callback_data="admin_approvals")]
    ])
    await message.answer("👨‍💼 Admin Panel", reply_markup=keyboard)

@dp.callback_query(F.data == "admin_users")
async def admin_view_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM users')
        total = (await cursor.fetchone())[0]
        cursor = await db.execute('SELECT COUNT(*) FROM users WHERE is_pro = 1')
        pro_users = (await cursor.fetchone())[0]
    
    text = f"📊 User Statistics:\n\n👥 Total Users: {total}\n⭐ Pro Users: {pro_users}"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_view_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT COUNT(*) FROM games')
        total_games = (await cursor.fetchone())[0]
        cursor = await db.execute('SELECT COUNT(*) FROM game_stats')
        total_plays = (await cursor.fetchone())[0]
    
    text = f"📊 Platform Statistics:\n\n🎮 Total Games: {total_games}\n🎯 Total Plays: {total_plays}"
    await callback.message.edit_text(text)
    await callback.answer()

@dp.callback_query(F.data == "admin_approvals")
async def admin_view_approvals(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('''
            SELECT user_id, name, username FROM users 
            WHERE pro_requested = 1 AND is_pro = 0
        ''')
        pending = await cursor.fetchall()
    
    if not pending:
        await callback.message.edit_text("✅ No pending approval requests")
        await callback.answer()
        return
    
    keyboard = []
    for user_id, name, username in pending:
        keyboard.append([
            InlineKeyboardButton(
                text=f"✅ Approve {name} (@{username})",
                callback_data=f"approve_{user_id}"
            )
        ])
    
    await callback.message.edit_text(
        "⏳ Pending Pro Feature Requests:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("approve_"))
async def approve_pro(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Access denied", show_alert=True)
        return
    
    user_id = int(callback.data.split("_")[1])
    
    async with aiosqlite.connect('edubot.db') as db:
        await db.execute('UPDATE users SET is_pro = 1, pro_requested = 0 WHERE user_id = ?', (user_id,))
        await db.commit()
    
    await bot.send_message(user_id, "🎉 Congratulations! Your Pro access has been approved!")
    await callback.answer("✅ Approved!", show_alert=True)
    await admin_view_approvals(callback)

# Web API for frontend
routes = web.RouteTableDef()

@routes.get('/api/user/{user_id}')
async def get_user(request):
    user_id = int(request.match_info['user_id'])
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = await cursor.fetchone()
        if user:
            return web.json_response({
                'user_id': user[0],
                'username': user[1],
                'name': user[2],
                'phone': user[3],
                'language': user[4],
                'is_pro': user[5],
                'pro_requested': user[6]
            })
        return web.json_response({'error': 'User not found'}, status=404)

@routes.post('/api/games')
async def create_game(request):
    data = await request.json()
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('''
            INSERT INTO games (creator_id, game_type, title, questions, share_link, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['creator_id'],
            data['game_type'],
            data['title'],
            json.dumps(data['questions']),
            data['share_link'],
            datetime.now().isoformat()
        ))
        await db.commit()
        game_id = cursor.lastrowid
    return web.json_response({'game_id': game_id, 'success': True})

@routes.get('/api/games/{user_id}')
async def get_user_games(request):
    user_id = int(request.match_info['user_id'])
    async with aiosqlite.connect('edubot.db') as db:
        cursor = await db.execute('SELECT * FROM games WHERE creator_id = ?', (user_id,))
        games = await cursor.fetchall()
        return web.json_response([{
            'id': g[0],
            'game_type': g[2],
            'title': g[3],
            'share_link': g[5],
            'created_at': g[6]
        } for g in games])

@routes.post('/api/request-pro')
async def request_pro(request):
    data = await request.json()
    user_id = data['user_id']
    async with aiosqlite.connect('edubot.db') as db:
        await db.execute('UPDATE users SET pro_requested = 1 WHERE user_id = ?', (user_id,))
        await db.commit()
    
    for admin_id in ADMIN_IDS:
        await bot.send_message(admin_id, f"🔔 New Pro access request from user {user_id}")
    
    return web.json_response({'success': True})

@routes.options('/{tail:.*}')
async def cors_preflight(request):
    return web.Response(headers={
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type'
    })

@web.middleware
async def cors_middleware(request, handler):
    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

async def start_web_server():
    app = web.Application(middlewares=[cors_middleware])
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logging.info("Web API started on port 8080")

async def main():
    await init_db()
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())