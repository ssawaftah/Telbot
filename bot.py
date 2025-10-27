import os
import json
import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# بيانات البوت - سيتم تعيين التوكن من متغير البيئة
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# قراءة ADMIN_IDS من متغير البيئة
ADMIN_IDS_ENV = os.getenv('ADMIN_IDS')
if ADMIN_IDS_ENV:
    ADMIN_IDS = [int(admin_id.strip()) for admin_id in ADMIN_IDS_ENV.split(',') if admin_id.strip().isdigit()]
else:
    ADMIN_IDS = []

# حالات المحادثة
(
    ADD_CHANNEL_NAME, ADD_CHANNEL_LINK,
    ADD_CONTENT_TITLE, ADD_CONTENT_TYPE, ADD_CONTENT_FILE, ADD_CONTENT_TEXT,
    DELETE_USER, DELETE_CHANNEL, DELETE_CONTENT,
    EDIT_RESPONSE, EDIT_SUBSCRIPTION_MESSAGE, ADD_SUBSCRIPTION_CHANNEL, DELETE_SUBSCRIPTION_CHANNEL,
    BROADCAST_MESSAGE, SEND_TO_USER,
    BACKUP_RESTORE
) = range(16)

# ملفات البيانات
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONTENT_FILE = os.path.join(DATA_DIR, "content.json")
CHANNELS_FILE = os.path.join(DATA_DIR, "channels.json")  # لقنوات البوت العادية
SUBSCRIPTION_CHANNELS_FILE = os.path.join(DATA_DIR, "subscription_channels.json")  # لقنوات الاشتراك الإجباري
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")

class BotDatabase:
    @staticmethod
    def init_default_data():
        default_data = {
            USERS_FILE: {},
            CONTENT_FILE: {
                "content": []
            },
            CHANNELS_FILE: {
                "channels": []  # قنوات البوت العادية
            },
            SUBSCRIPTION_CHANNELS_FILE: {
                "channels": ["@ineswangy"]  # قنوات الاشتراك الإجباري فقط
            },
            SETTINGS_FILE: {
                "subscription": {
                    "enabled": False,
                    "message": "📢 يجب الاشتراك في القناة أولاً لتتمكن من استخدام البوت"
                },
                "responses": {
                    "welcome": "🎉 مرحباً! تم قبول طلبك بنجاح.\nيمكنك الآن استخدام البوت والاستفادة من محتوانا.",
                    "rejected": "❌ تم رفض طلبك.\nللمساعدة تواصل مع المدير.",
                    "help": "ℹ️ للمساعدة تواصل مع مدير البوت.",
                    "subscribe_success": "✅ تم التحقق من اشتراكك بنجاح!",
                    "subscribe_failed": "❌ لم يتم التحقق من اشتراكك بعد!"
                },
                "forwarding": {
                    "enabled": True  # تفعيل التحويل افتراضياً
                }
            },
            REQUESTS_FILE: []
        }
        
        for file_path, default_content in default_data.items():
            if not os.path.exists(file_path):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(default_content, f, ensure_ascii=False, indent=2)

    @staticmethod
    def read_json(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            if "settings" in file_path:
                return {}
            elif "content" in file_path:
                return {"content": []}
            elif "channels" in file_path:
                return {"channels": []}
            elif "subscription_channels" in file_path:
                return {"channels": []}
            elif "requests" in file_path:
                return []
            else:
                return {}

    @staticmethod
    def write_json(file_path, data):
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def get_setting(key_path):
        settings = BotDatabase.read_json(SETTINGS_FILE)
        keys = key_path.split('.')
        value = settings
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, {})
            else:
                value = {}
        return value

    @staticmethod
    def set_setting(key_path, value):
        settings = BotDatabase.read_json(SETTINGS_FILE)
        keys = key_path.split('.')
        current = settings
        for key in keys[:-1]:
            current = current.setdefault(key, {})
        current[keys[-1]] = value
        BotDatabase.write_json(SETTINGS_FILE, settings)

    @staticmethod
    def add_user(user_id, username, first_name):
        users = BotDatabase.read_json(USERS_FILE)
        users[str(user_id)] = {
            "username": username,
            "first_name": first_name,
            "join_date": datetime.now().isoformat(),
            "approved": False
        }
        BotDatabase.write_json(USERS_FILE, users)
        
        requests = BotDatabase.read_json(REQUESTS_FILE)
        requests.append({
            "user_id": str(user_id),
            "username": username,
            "first_name": first_name,
            "date": datetime.now().isoformat()
        })
        BotDatabase.write_json(REQUESTS_FILE, requests)

    @staticmethod
    def get_pending_requests():
        users = BotDatabase.read_json(USERS_FILE)
        return [user_id for user_id, data in users.items() if not data.get('approved', False)]

    @staticmethod
    def get_approved_users():
        users = BotDatabase.read_json(USERS_FILE)
        return [user_id for user_id, data in users.items() if data.get('approved', False)]

    @staticmethod
    def generate_content_id():
        """توليد رقم فريد مكون من 6-8 أرقام"""
        content_data = BotDatabase.read_json(CONTENT_FILE)
        existing_ids = [item.get('id', 0) for item in content_data.get('content', [])]
        
        while True:
            # توليد رقم بين 100000 و 99999999 (6-8 أرقام)
            new_id = random.randint(100000, 99999999)
            if new_id not in existing_ids:
                return new_id

    # === دوال قنوات البوت العادية ===
    @staticmethod
    def add_channel(name, link):
        channels_data = BotDatabase.read_json(CHANNELS_FILE)
        new_id = max([ch.get('id', 0) for ch in channels_data.get("channels", [])] or [0]) + 1
        
        new_channel = {
            "id": new_id,
            "name": name,
            "link": link,
            "created_date": datetime.now().isoformat()
        }
        
        channels_data["channels"].append(new_channel)
        BotDatabase.write_json(CHANNELS_FILE, channels_data)
        return new_id

    @staticmethod
    def get_channels():
        channels_data = BotDatabase.read_json(CHANNELS_FILE)
        return channels_data.get("channels", [])

    @staticmethod
    def delete_channel(channel_id):
        channels_data = BotDatabase.read_json(CHANNELS_FILE)
        channels = channels_data.get("channels", [])
        
        channel_to_delete = None
        for channel in channels:
            if channel['id'] == channel_id:
                channel_to_delete = channel
                break
        
        if channel_to_delete:
            channels_data["channels"] = [ch for ch in channels if ch['id'] != channel_id]
            BotDatabase.write_json(CHANNELS_FILE, channels_data)
            return channel_to_delete
        
        return None

    # === دوال قنوات الاشتراك الإجباري ===
    @staticmethod
    def get_subscription_channels():
        """الحصول على قنوات الاشتراك الإجباري"""
        subscription_data = BotDatabase.read_json(SUBSCRIPTION_CHANNELS_FILE)
        return subscription_data.get("channels", [])

    @staticmethod
    def add_subscription_channel(channel):
        """إضافة قناة للاشتراك الإجباري"""
        subscription_data = BotDatabase.read_json(SUBSCRIPTION_CHANNELS_FILE)
        channels = subscription_data.get("channels", [])
        
        if channel not in channels:
            channels.append(channel)
            subscription_data["channels"] = channels
            BotDatabase.write_json(SUBSCRIPTION_CHANNELS_FILE, subscription_data)
            return True
        return False

    @staticmethod
    def delete_subscription_channel(channel_index):
        """حذف قناة من الاشتراك الإجباري"""
        subscription_data = BotDatabase.read_json(SUBSCRIPTION_CHANNELS_FILE)
        channels = subscription_data.get("channels", [])
        
        if 0 <= channel_index < len(channels):
            deleted_channel = channels.pop(channel_index)
            subscription_data["channels"] = channels
            BotDatabase.write_json(SUBSCRIPTION_CHANNELS_FILE, subscription_data)
            return deleted_channel
        return None

    @staticmethod
    def add_content(title, content_type, text_content="", file_id="", content_id=None):
        content_data = BotDatabase.read_json(CONTENT_FILE)
        
        if content_id is None:
            content_id = BotDatabase.generate_content_id()
        
        new_content = {
            "id": content_id,
            "title": title,
            "content_type": content_type,
            "text_content": text_content,
            "file_id": file_id,
            "created_date": datetime.now().isoformat()
        }
        
        content_data["content"].append(new_content)
        BotDatabase.write_json(CONTENT_FILE, content_data)
        return new_content

    @staticmethod
    def get_content_by_id(content_id):
        content_data = BotDatabase.read_json(CONTENT_FILE)
        for item in content_data.get("content", []):
            if item['id'] == content_id:
                return item
        return None

    @staticmethod
    def get_all_content():
        content_data = BotDatabase.read_json(CONTENT_FILE)
        return content_data.get("content", [])

    @staticmethod
    def delete_content(content_id):
        content_data = BotDatabase.read_json(CONTENT_FILE)
        content_items = content_data.get("content", [])
        
        content_to_delete = None
        for item in content_items:
            if item['id'] == content_id:
                content_to_delete = item
                break
        
        if content_to_delete:
            content_data["content"] = [item for item in content_items if item['id'] != content_id]
            BotDatabase.write_json(CONTENT_FILE, content_data)
            return content_to_delete
        
        return None

class KeyboardManager:
    @staticmethod
    def get_user_keyboard():
        return ReplyKeyboardMarkup([
            ["📺 قنوات نسونجي", "🔍 ID"],
            ["ℹ️ المساعدة"]
        ], resize_keyboard=True)

    @staticmethod
    def get_admin_keyboard():
        return ReplyKeyboardMarkup([
            ["👑 لوحة التحكم", "📊 الإحصائيات"],
            ["👥 إدارة المستخدمين", "📢 الاشتراك الإجباري"],
            ["📺 إدارة القنوات", "🎭 إدارة المحتوى"],
            ["⚙️ الإعدادات العامة", "📤 البث للمستخدمين"],
            ["💾 النسخ الاحتياطي"]
        ], resize_keyboard=True)

    @staticmethod
    def get_waiting_keyboard():
        return ReplyKeyboardMarkup([["⏳ انتظر الموافقة"]], resize_keyboard=True)

    @staticmethod
    def get_back_keyboard():
        return ReplyKeyboardMarkup([["🏠 الرئيسية"]], resize_keyboard=True)

    @staticmethod
    def get_channels_keyboard():
        channels = BotDatabase.get_channels()
        
        keyboard = []
        for channel in channels:
            keyboard.append([f"📺 {channel['name']}"])
        
        keyboard.append(["🏠 الرئيسية"])
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    @staticmethod
    def get_channels_inline_keyboard():
        channels = BotDatabase.get_channels()
        
        keyboard = []
        for channel in channels:
            keyboard.append([InlineKeyboardButton(f"📺 {channel['name']}", url=channel['link'])])
        
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_main")])
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    def get_user_management_keyboard():
        return ReplyKeyboardMarkup([
            ["📋 طلبات الانتظار", "👀 المستخدمين النشطين"],
            ["🗑️ حذف مستخدم", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_channels_management_keyboard():
        return ReplyKeyboardMarkup([
            ["➕ إضافة قناة", "🗑️ حذف قناة"],
            ["📋 عرض القنوات", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_content_management_keyboard():
        return ReplyKeyboardMarkup([
            ["➕ إضافة محتوى", "🗑️ حذف محتوى"],
            ["📋 عرض المحتوى", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_subscription_management_keyboard():
        return ReplyKeyboardMarkup([
            ["🔔 تفعيل/إلغاء", "✏️ تعديل الرسالة"],
            ["📝 إضافة قناة اشتراك", "🗑️ حذف قناة اشتراك"],
            ["📋 عرض قنوات الاشتراك", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_settings_keyboard():
        return ReplyKeyboardMarkup([
            ["✏️ تعديل رسالة الترحيب", "✏️ تعديل رسالة الرفض"],
            ["✏️ تعديل رسالة المساعدة", "🔔 تفعيل/إلغاء التحويل"],
            ["🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_broadcast_keyboard():
        return ReplyKeyboardMarkup([
            ["📢 بث لجميع المستخدمين", "👤 بث لمستخدم محدد"],
            ["📋 عرض المستخدمين", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_backup_keyboard():
        return ReplyKeyboardMarkup([
            ["💾 تنزيل نسخة", "🔄 رفع نسخة"],
            ["📋 عرض النسخ", "🏠 الرئيسية"]
        ], resize_keyboard=True)

    @staticmethod
    def get_text_input_keyboard():
        return ReplyKeyboardMarkup([
            ["✅ إنهاء وحفظ", "❌ إلغاء الإضافة"],
            ["🏠 الرئيسية"]
        ], resize_keyboard=True)

def is_admin(user_id):
    return str(user_id) in [str(admin_id) for admin_id in ADMIN_IDS]

def is_user_approved(user_id):
    users = BotDatabase.read_json(USERS_FILE)
    user_data = users.get(str(user_id), {})
    return user_data.get('approved', False)

async def check_subscription(user_id, context):
    """التحقق من اشتراك المستخدم في قنوات الاشتراك الإجباري فقط"""
    if not BotDatabase.get_setting("subscription.enabled"):
        return True
    
    channels = BotDatabase.get_subscription_channels()  # استخدام قنوات الاشتراك الإجباري فقط
    if not channels:
        return True
    
    try:
        for channel in channels:
            # التحقق من اشتراك المستخدم في القناة
            chat_member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if chat_member.status in ['left', 'kicked', 'restricted']:
                return False
        return True
    except Exception as e:
        logger.error(f"Error checking subscription for {user_id}: {e}")
        return False

async def forward_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE, action_type: str, details: str = ""):
    """تحويل إجراءات المستخدم إلى المديرين"""
    if not BotDatabase.get_setting("forwarding.enabled"):
        return
    
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    username = f"@{update.effective_user.username}" if update.effective_user.username else "لا يوجد"
    
    # نص الرسالة المحولة
    forward_text = (
        f"📩 إجراء مستخدم جديد\n\n"
        f"👤 المستخدم: {user_name}\n"
        f"🆔 الآيدي: {user_id}\n"
        f"📧 اليوزر: {username}\n"
        f"🎯 الإجراء: {action_type}\n"
        f"📝 التفاصيل: {details}\n"
        f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # إرسال للمديرين
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, forward_text)
        except Exception as e:
            logger.error(f"Error forwarding message to admin {admin_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if not ADMIN_IDS:
        ADMIN_IDS.append(user_id)
        await update.message.reply_text(
            "*👑 تم تعيينك كمشرف رئيسي للبوت!\n\n*"
            "يمكنك الآن استخدام لوحة التحكم للإدارة الكاملة للبوت.",
            parse_mode='Markdown',
            reply_markup=KeyboardManager.get_admin_keyboard()
        )
        return
    
    users = BotDatabase.read_json(USERS_FILE)
    user_key = str(user_id)
    
    if user_key in users:
        user_data = users[user_key]
        if user_data.get("approved", False):
            # التحقق من الاشتراك الإجباري - يستخدم قنوات الاشتراك الإجباري فقط
            if BotDatabase.get_setting("subscription.enabled"):
                if not await check_subscription(user_id, context):
                    channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
                    channels_text = "\n".join([f"• {ch}" for ch in channels])
                    
                    await update.message.reply_text(
                        f"{BotDatabase.get_setting('subscription.message')}\n\n"
                        f"القنوات المطلوبة:\n{channels_text}\n\n"
                        "بعد الاشتراك، اضغط على /start مرة أخرى",
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup([["✅ تحقق من الاشتراك"]], resize_keyboard=True)
                    )
                    return
            
            # المستخدم مفعل وملتزم بالاشتراك
            if is_admin(user_id):
                await update.message.reply_text(
                    f"👑 أهلاً بك يا {update.effective_user.first_name}!\n"
                    "أنت مسجل كمشرف على البوت.\n\n"
                    "اختر من لوحة التحكم أدناه:",
                    reply_markup=KeyboardManager.get_admin_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"*مرحباً بعودتك يا {update.effective_user.first_name}! 👋*\n"
                    "_يسرّنا رؤيتك مجدداً._\n\n"
                    "⬇️ *اختر أحد الأقسام أدناه للمتابعة:*",
                    parse_mode='Markdown',
                    reply_markup=KeyboardManager.get_user_keyboard()
                )
                # تحويل إجراء بدء المحادثة
                await forward_user_action(update, context, "بدء المحادثة", "قام المستخدم ببدء محادثة جديدة")
        else:
            # المستخدم غير مفعل
            await update.message.reply_text(
                "*⏳ طلبك قيد المراجعة من قبل المدير...\n*"
                "سيتم إعلامك فور الموافقة على طلبك.",
                parse_mode='Markdown',
                reply_markup=KeyboardManager.get_waiting_keyboard()
            )
    else:
        # مستخدم جديد
        BotDatabase.add_user(user_id, update.effective_user.username, update.effective_user.first_name)
        
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_key}"),
                     InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_key}")],
                    [InlineKeyboardButton("📋 طلبات الانضمام", callback_data="view_requests")]
                ])
                
                await context.bot.send_message(
                    admin_id,
                    f"📥 طلب انضمام جديد!\n\n"
                    f"👤 المستخدم: {update.effective_user.first_name}\n"
                    f"🆔 الآيدي: {user_key}\n"
                    f"📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error notifying admin: {e}")
        
        await update.message.reply_text(
            "✅ تم إرسال طلب انضمامك بنجاح!\n"
            "سيتم مراجعته من قبل المدير قريباً.",
            reply_markup=KeyboardManager.get_waiting_keyboard()
        )
        
        # تحويل إجراء طلب انضمام جديد
        await forward_user_action(update, context, "طلب انضمام جديد", f"اسم المستخدم: {update.effective_user.first_name}")

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    
    # التحقق من أن المستخدم مفعل
    if not is_user_approved(user_id):
        await update.message.reply_text(
            "⏳ طلبك قيد المراجعة من قبل المدير...\n"
            "سيتم إعلامك فور الموافقة على طلبك.",
            reply_markup=KeyboardManager.get_waiting_keyboard()
        )
        return
    
    # التحقق من الاشتراك الإجباري
    if BotDatabase.get_setting("subscription.enabled"):
        if not await check_subscription(user_id, context):
            channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
            channels_text = "\n".join([f"• {ch}" for ch in channels])
            
            await update.message.reply_text(
                f"{BotDatabase.get_setting('subscription.message')}\n\n"
                f"القنوات المطلوبة:\n{channels_text}\n\n"
                "بعد الاشتراك، اضغط على /start مرة أخرى",
                reply_markup=ReplyKeyboardMarkup([["✅ تحقق من الاشتراك"]], resize_keyboard=True)
            )
            return
    
    if text == "📺 قنوات نسونجي":
        await show_channels_to_user(update, context)
        await forward_user_action(update, context, "عرض القنوات", "قام المستخدم بعرض قائمة القنوات")
    elif text == "🔍 ID":
        await ask_for_content_id(update, context)
        await forward_user_action(update, context, "طلب إدخال ID", "قام المستخدم بطلب إدخال رقم المحتوى")
    elif text == "ℹ️ المساعدة":
        await update.message.reply_text(BotDatabase.get_setting("responses.help"))
        await forward_user_action(update, context, "طلب المساعدة", "قام المستخدم بطلب المساعدة")
    elif text == "✅ تحقق من الاشتراك":
        if await check_subscription(update.effective_user.id, context):
            await update.message.reply_text(
                BotDatabase.get_setting("responses.subscribe_success"),
                reply_markup=KeyboardManager.get_user_keyboard()
            )
            await forward_user_action(update, context, "تحقق من الاشتراك", "نجح التحقق من الاشتراك")
        else:
            channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
            channels_text = "\n".join([f"• {ch}" for ch in channels])
            await update.message.reply_text(
                f"{BotDatabase.get_setting('responses.subscribe_failed')}\n\n"
                f"يجب الاشتراك في:\n{channels_text}"
            )
            await forward_user_action(update, context, "تحقق من الاشتراك", "فشل التحقق من الاشتراك")
    elif text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 العودة للرئيسية", reply_markup=KeyboardManager.get_user_keyboard())
        await forward_user_action(update, context, "العودة للرئيسية", "قام المستخدم بالعودة للصفحة الرئيسية")
    elif text == "⏳ انتظر الموافقة":
        await update.message.reply_text(
            "⏳ طلبك قيد المراجعة من قبل المدير...\n"
            "سيتم إعلامك فور الموافقة على طلبك.",
            reply_markup=KeyboardManager.get_waiting_keyboard()
        )
    else:
        await handle_channel_selection(update, context, text)

async def show_channels_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_channels()  # قنوات البوت العادية فقط
    
    if not channels:
        await update.message.reply_text("📭 لا توجد قنوات متاحة حالياً.")
        return
    
    await update.message.reply_text(
        "📺 قنوات نسونجي:\nاختر القناة التي تريد زيارتها:",
        reply_markup=KeyboardManager.get_channels_keyboard()
    )

async def ask_for_content_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 أدخل رقم المحتوى (ID):",
        reply_markup=ReplyKeyboardMarkup([["🏠 الرئيسية"]], resize_keyboard=True)
    )
    context.user_data['waiting_for_id'] = True

async def handle_channel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    channels = BotDatabase.get_channels()  # قنوات البوت العادية فقط
    
    for channel in channels:
        if text == f"📺 {channel['name']}":
            await update.message.reply_text(
                f"📺 {channel['name']}\n\n"
                f"رابط القناة: {channel['link']}\n\n"
                "انقر على الزر أدناه لزيارة القناة:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📺 زيارة القناة", url=channel['link'])],
                    [InlineKeyboardButton("🔙 رجوع", callback_data="back_to_channels")]
                ])
            )
            await forward_user_action(update, context, "زيارة قناة", f"اختار المستخدم قناة: {channel['name']}")
            return
    
    # معالجة إدخال ID
    if context.user_data.get('waiting_for_id'):
        try:
            content_id = int(text)
            content = BotDatabase.get_content_by_id(content_id)
            if content:
                await show_content_item_from_message(update, context, content_id)
                await forward_user_action(update, context, "عرض محتوى", f"عرض المحتوى برقم: {content_id} - {content['title']}")
            else:
                await update.message.reply_text("❌ لم يتم العثور على محتوى بهذا الرقم.")
                await forward_user_action(update, context, "بحث عن محتوى", f"بحث عن محتوى برقم: {content_id} - غير موجود")
        except ValueError:
            await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
            await forward_user_action(update, context, "إدخال خاطئ", f"أدخل المستخدم: {text} - ليس رقماً صحيحاً")
        
        context.user_data['waiting_for_id'] = False
        return
    
    # تحويل أي رسالة أخرى من المستخدم
    if not is_admin(update.effective_user.id):
        await forward_user_action(update, context, "رسالة نصية", f"أرسل المستخدم: {text}")
        await update.message.reply_text("❌ لم أفهم طلبك. اختر من القائمة أدناه:", reply_markup=KeyboardManager.get_user_keyboard())
    else:
        await update.message.reply_text("❌ لم أفهم طلبك. اختر من القائمة أدناه:", reply_markup=KeyboardManager.get_admin_keyboard())

async def show_content_item_from_message(update: Update, context: ContextTypes.DEFAULT_TYPE, content_id: int):
    """عرض عنصر محتوى من رسالة عادية"""
    content_item = BotDatabase.get_content_by_id(content_id)
    
    if not content_item:
        await update.message.reply_text("❌ المحتوى غير موجود.")
        return
    
    try:
        if content_item['content_type'] == 'text':
            message_text = f"**{content_item['title']}**\n\n{content_item['text_content']}"
            
            if len(message_text) > 4096:
                parts = [message_text[i:i+4096] for i in range(0, len(message_text), 4096)]
                for i, part in enumerate(parts):
                    await update.message.reply_text(part, parse_mode='Markdown')
            else:
                await update.message.reply_text(message_text, parse_mode='Markdown')
            
        elif content_item['content_type'] == 'photo':
            await update.message.reply_photo(
                photo=content_item['file_id'],
                caption=f"🖼️ {content_item['title']}",
                parse_mode='Markdown'
            )
            
        elif content_item['content_type'] == 'video':
            await update.message.reply_video(
                video=content_item['file_id'],
                caption=f"🎬 {content_item['title']}",
                parse_mode='Markdown'
            )
            
        elif content_item['content_type'] == 'document':
            await update.message.reply_document(
                document=content_item['file_id'],
                caption=f"📄 {content_item['title']}",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Error showing content {content_id}: {e}")
        await update.message.reply_text(
            f"📖 {content_item['title']}\n\n{content_item.get('text_content', 'المحتوى غير متوفر')}"
        )

async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    user_id = update.effective_user.id
    
    if text == "👑 لوحة التحكم":
        await show_admin_dashboard(update, context)
    elif text == "👥 إدارة المستخدمين":
        await show_user_management(update, context)
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
    elif text == "📺 إدارة القنوات":
        await show_channels_management(update, context)
    elif text == "🎭 إدارة المحتوى":
        await show_content_management(update, context)
    elif text == "📢 الاشتراك الإجباري":
        await show_subscription_management(update, context)
    elif text == "⚙️ الإعدادات العامة":
        await show_settings_management(update, context)
    elif text == "📤 البث للمستخدمين":
        await show_broadcast_management(update, context)
    elif text == "💾 النسخ الاحتياطي":
        await show_backup_management(update, context)
    elif text == "📺 قنوات نسونجي":
        await show_channels_to_user(update, context)
    elif text == "🔍 ID":
        await ask_for_content_id(update, context)
    elif text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 العودة للرئيسية", reply_markup=KeyboardManager.get_admin_keyboard())
    elif text == "📋 طلبات الانتظار":
        await show_pending_requests(update, context)
    elif text == "👀 المستخدمين النشطين":
        await show_active_users(update, context)
    elif text == "🗑️ حذف مستخدم":
        await start_delete_user(update, context)
    elif text == "➕ إضافة قناة":
        await start_add_channel(update, context)
    elif text == "🗑️ حذف قناة":
        await start_delete_channel(update, context)
    elif text == "📋 عرض القنوات":
        await show_all_channels(update, context)
    elif text == "➕ إضافة محتوى":
        await start_add_content(update, context)
    elif text == "🗑️ حذف محتوى":
        await start_delete_content(update, context)
    elif text == "📋 عرض المحتوى":
        await show_all_content(update, context)
    elif text == "🔔 تفعيل/إلغاء":
        await toggle_subscription(update, context)
    elif text == "✏️ تعديل الرسالة":
        await start_edit_subscription_message(update, context)
    elif text == "📝 إضافة قناة اشتراك":
        await start_add_subscription_channel(update, context)
    elif text == "🗑️ حذف قناة اشتراك":
        await start_delete_subscription_channel(update, context)
    elif text == "📋 عرض قنوات الاشتراك":
        await show_subscription_channels(update, context)
    elif text == "✏️ تعديل رسالة الترحيب":
        await start_edit_response(update, context, "welcome")
    elif text == "✏️ تعديل رسالة الرفض":
        await start_edit_response(update, context, "rejected")
    elif text == "✏️ تعديل رسالة المساعدة":
        await start_edit_response(update, context, "help")
    elif text == "🔔 تفعيل/إلغاء التحويل":
        await toggle_forwarding(update, context)
    elif text == "📢 بث لجميع المستخدمين":
        await start_broadcast(update, context)
    elif text == "👤 بث لمستخدم محدد":
        await start_send_to_user(update, context)
    elif text == "💾 تنزيل نسخة":
        await download_backup(update, context)
    elif text == "🔄 رفع نسخة":
        await start_restore_backup(update, context)
    elif text == "📋 عرض النسخ":
        await show_backups(update, context)
    else:
        await handle_channel_selection(update, context, text)

# دالة handle_message الموحدة
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    # التحقق من أن المستخدم مفعل أولاً
    if not is_user_approved(user_id) and not is_admin(user_id):
        await update.message.reply_text(
            "⏳ طلبك قيد المراجعة من قبل المدير...\n"
            "سيتم إعلامك فور الموافقة على طلبك.",
            reply_markup=KeyboardManager.get_waiting_keyboard()
        )
        return
    
    if is_admin(user_id):
        await handle_admin_message(update, context, text)
    else:
        await handle_user_message(update, context, text)

async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = BotDatabase.read_json(USERS_FILE)
    content = BotDatabase.get_all_content()
    channels = BotDatabase.get_channels()
    subscription_channels = BotDatabase.get_subscription_channels()
    
    active_users = len([u for u in users.values() if u.get('approved', False)])
    total_users = len(users)
    pending_requests = len(BotDatabase.get_pending_requests())
    channels_count = len(channels)
    subscription_channels_count = len(subscription_channels)
    content_count = len(content)
    
    stats_text = (
        "👑 لوحة تحكم المدير\n\n"
        "📊 الإحصائيات السريعة:\n"
        f"• 👥 المستخدمين النشطين: {active_users}\n"
        f"• ⏳ طلبات الانتظار: {pending_requests}\n"
        f"• 📺 قنوات البوت: {channels_count}\n"
        f"• 📢 قنوات الاشتراك: {subscription_channels_count}\n"
        f"• 🎭 محتوى: {content_count}\n\n"
        "اختر من القائمة أدناه للإدارة:"
    )
    
    await update.message.reply_text(stats_text, reply_markup=KeyboardManager.get_admin_keyboard())

async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_count = len(BotDatabase.get_pending_requests())
    active_count = len(BotDatabase.get_approved_users())
    
    text = (
        "👥 إدارة المستخدمين\n\n"
        f"📊 الإحصائيات:\n"
        f"• طلبات الانتظار: {pending_count}\n"
        f"• المستخدمين النشطين: {active_count}\n\n"
        "اختر الإجراء المطلوب:"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_user_management_keyboard())

async def show_pending_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_users = BotDatabase.get_pending_requests()
    users_data = BotDatabase.read_json(USERS_FILE)
    
    if not pending_users:
        await update.message.reply_text("📭 لا توجد طلبات انضمام معلقة.")
        return
    
    text = "📋 طلبات الانضمام المعلقة:\n\n"
    for user_id in pending_users[:5]:
        user_data = users_data.get(user_id, {})
        text += f"👤 {user_data.get('first_name', 'Unknown')}\n"
        text += f"🆔 {user_id}\n"
        text += f"📅 {user_data.get('join_date', '')[:10]}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_id}"),
             InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")]
        ])
        
        await update.message.reply_text(text, reply_markup=keyboard)
        text = "─" * 30 + "\n"

async def show_active_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_users = BotDatabase.get_approved_users()
    users_data = BotDatabase.read_json(USERS_FILE)
    
    if not active_users:
        await update.message.reply_text("👥 لا يوجد مستخدمين نشطين.")
        return
    
    text = f"👥 المستخدمين النشطين ({len(active_users)}):\n\n"
    for user_id in active_users[:15]:
        user_data = users_data.get(user_id, {})
        text += f"👤 {user_data.get('first_name', 'Unknown')}\n"
        text += f"🆔 {user_id}\n"
        text += f"📅 {user_data.get('join_date', '')[:10]}\n"
        text += "─" * 20 + "\n"
    
    await update.message.reply_text(text)

async def start_delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🗑️ حذف مستخدم\n\n"
        "أرسل الآيدي الخاص بالمستخدم الذي تريد حذفه:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return DELETE_USER

async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    users = BotDatabase.read_json(USERS_FILE)
    
    if user_id in users:
        user_name = users[user_id]['first_name']
        del users[user_id]
        BotDatabase.write_json(USERS_FILE, users)
        
        requests = BotDatabase.read_json(REQUESTS_FILE)
        requests = [r for r in requests if r['user_id'] != user_id]
        BotDatabase.write_json(REQUESTS_FILE, requests)
        
        await update.message.reply_text(f"✅ تم حذف المستخدم: {user_name}")
    else:
        await update.message.reply_text("❌ لم يتم العثور على المستخدم.")
    
    return ConversationHandler.END

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = BotDatabase.read_json(USERS_FILE)
    content = BotDatabase.get_all_content()
    channels = BotDatabase.get_channels()
    subscription_channels = BotDatabase.get_subscription_channels()
    
    active_users = len(BotDatabase.get_approved_users())
    total_users = len(users)
    pending_requests = len(BotDatabase.get_pending_requests())
    channels_count = len(channels)
    subscription_channels_count = len(subscription_channels)
    content_count = len(content)
    
    text = (
        "📊 الإحصائيات التفصيلية\n\n"
        f"👥 المستخدمين:\n"
        f"• النشطين: {active_users}\n"
        f"• الإجمالي: {total_users}\n"
        f"• طلبات الانتظار: {pending_requests}\n"
        f"• النسبة: {round((active_users/total_users)*100 if total_users > 0 else 0, 1)}%\n\n"
        f"🎭 المحتوى:\n"
        f"• قنوات البوت: {channels_count}\n"
        f"• قنوات الاشتراك: {subscription_channels_count}\n"
        f"• العناصر: {content_count}\n\n"
        f"⚙️ الإعدادات:\n"
        f"• الاشتراك الإجباري: {'✅ مفعل' if BotDatabase.get_setting('subscription.enabled') else '❌ معطل'}\n"
        f"• التحويل: {'✅ مفعل' if BotDatabase.get_setting('forwarding.enabled') else '❌ معطل'}"
    )
    
    await update.message.reply_text(text)

async def show_channels_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_channels()  # قنوات البوت العادية فقط
    
    text = "📺 إدارة قنوات البوت\n\n"
    if channels:
        text += "القنوات الحالية:\n"
        for channel in channels:
            text += f"• {channel['name']} - {channel['link']}\n"
    else:
        text += "لا توجد قنوات حالياً.\n"
    
    text += "\nاختر الإجراء المطلوب:"
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_channels_management_keyboard())

async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "➕ إضافة قناة جديدة للبوت\n\n"
        "أرسل اسم القناة:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return ADD_CHANNEL_NAME

async def add_channel_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_name = update.message.text.strip()
    
    if not channel_name:
        await update.message.reply_text("❌ الرجاء إدخال اسم صحيح للقناة.")
        return ADD_CHANNEL_NAME
        
    context.user_data['channel_name'] = channel_name
    
    await update.message.reply_text(
        "أرسل رابط القناة:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return ADD_CHANNEL_LINK

async def add_channel_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_link = update.message.text.strip()
    channel_name = context.user_data['channel_name']
    
    if not channel_link.startswith('https://') and not channel_link.startswith('@'):
        await update.message.reply_text("❌ الرجاء إدخال رابط صحيح للقناة.")
        return ADD_CHANNEL_LINK
    
    channel_id = BotDatabase.add_channel(channel_name, channel_link)
    
    await update.message.reply_text(
        f"✅ تم إضافة قناة البوت بنجاح!\n\n"
        f"اسم القناة: {channel_name}\n"
        f"الرابط: {channel_link}\n"
        f"رقم القناة: {channel_id}",
        reply_markup=KeyboardManager.get_admin_keyboard()
    )
    
    return ConversationHandler.END

async def start_delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_channels()  # قنوات البوت العادية فقط
    
    if not channels:
        await update.message.reply_text("❌ لا توجد قنوات بوت لحذفها.")
        return ConversationHandler.END
    
    text = "🗑️ حذف قناة بوت\n\nالقنوات الحالية:\n"
    for channel in channels:
        text += f"• {channel['id']}: {channel['name']} - {channel['link']}\n"
    
    text += "\nأرسل رقم القناة التي تريد حذفها:"
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_back_keyboard())
    return DELETE_CHANNEL

async def delete_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        channel_id = int(update.message.text)
        deleted_channel = BotDatabase.delete_channel(channel_id)
        
        if deleted_channel:
            await update.message.reply_text(
                f"✅ تم حذف قناة البوت: {deleted_channel['name']}",
                reply_markup=KeyboardManager.get_admin_keyboard()
            )
        else:
            await update.message.reply_text("❌ لم يتم العثور على قناة البوت.")
    
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
    
    return ConversationHandler.END

async def show_all_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_channels()  # قنوات البوت العادية فقط
    
    if not channels:
        await update.message.reply_text("📭 لا توجد قنوات بوت.")
        return
    
    text = "📋 جميع قنوات البوت:\n\n"
    for channel in channels:
        text += f"• {channel['name']}\n"
        text += f"  🆔 الرقم: {channel['id']}\n"
        text += f"  🔗 الرابط: {channel['link']}\n"
        text += f"  📅 التاريخ: {channel.get('created_date', '')[:10]}\n\n"
    
    await update.message.reply_text(text)

async def show_content_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content_items = BotDatabase.get_all_content()
    items_count = len(content_items)
    
    text = f"🎭 إدارة المحتوى\n\nإجمالي العناصر: {items_count}\n\n"
    text += "اختر الإجراء المطلوب:"
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_content_management_keyboard())

async def start_add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "➕ إضافة محتوى جديد\n\n"
        "أرسل عنوان المحتوى:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return ADD_CONTENT_TITLE

async def add_content_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['content_title'] = update.message.text
    
    keyboard = ReplyKeyboardMarkup([
        ["📝 نص", "🖼️ صورة"],
        ["🎬 فيديو", "📄 ملف"],
        ["🏠 الرئيسية"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(
        "اختر نوع المحتوى:",
        reply_markup=keyboard
    )
    return ADD_CONTENT_TYPE

async def add_content_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content_type_map = {
        "📝 نص": "text",
        "🖼️ صورة": "photo", 
        "🎬 فيديو": "video",
        "📄 ملف": "document"
    }
    
    selected_type = content_type_map.get(update.message.text, "text")
    context.user_data['content_type'] = selected_type
    
    if selected_type == "text":
        # بدء تجميع النص
        context.user_data['content_text'] = ""
        context.user_data['text_parts'] = []
        
        await update.message.reply_text(
            "📝 أضف المحتوى النصي\n\n"
            "يمكنك إرسال النص على عدة رسائل\n"
            "وعند الانتهاء اضغط على زر '✅ إنهاء وحفظ'",
            reply_markup=KeyboardManager.get_text_input_keyboard()
        )
        return ADD_CONTENT_TEXT
    else:
        await update.message.reply_text(
            f"أرسل {update.message.text} الآن:",
            reply_markup=KeyboardManager.get_back_keyboard()
        )
        return ADD_CONTENT_FILE

async def add_content_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text
    
    # معالجة الأزرار
    if user_input == "✅ إنهاء وحفظ":
        text_content = context.user_data.get('content_text', '')
        if not text_content:
            await update.message.reply_text(
                "❌ لم يتم إضافة أي نص. الرجاء إرسال النص أولاً.",
                reply_markup=KeyboardManager.get_text_input_keyboard()
            )
            return ADD_CONTENT_TEXT
        
        context.user_data['text_content'] = text_content
        
        # إنشاء المحتوى
        new_content = BotDatabase.add_content(
            context.user_data['content_title'],
            context.user_data['content_type'],
            text_content,
            ""
        )
        
        # تنظيف البيانات المؤقتة
        if 'content_text' in context.user_data:
            del context.user_data['content_text']
        if 'text_parts' in context.user_data:
            del context.user_data['text_parts']
        
        await update.message.reply_text(
            f"✅ تم إضافة المحتوى بنجاح!\n\n"
            f"📖 العنوان: {new_content['title']}\n"
            f"🎯 النوع: {new_content['content_type']}\n"
            f"🆔 الرقم: {new_content['id']}\n"
            f"📊 عدد الأحرف: {len(new_content['text_content'])}",
            reply_markup=KeyboardManager.get_admin_keyboard()
        )
        
        return ConversationHandler.END
    
    elif user_input == "❌ إلغاء الإضافة":
        # تنظيف البيانات المؤقتة
        if 'content_text' in context.user_data:
            del context.user_data['content_text']
        if 'text_parts' in context.user_data:
            del context.user_data['text_parts']
        
        await update.message.reply_text(
            "❌ تم إلغاء إضافة المحتوى.",
            reply_markup=KeyboardManager.get_admin_keyboard()
        )
        return ConversationHandler.END
    
    else:
        # إضافة النص إلى المحتوى
        current_text = context.user_data.get('content_text', '')
        new_text = user_input
        
        if current_text:
            context.user_data['content_text'] = current_text + "\n\n" + new_text
        else:
            context.user_data['content_text'] = new_text
        
        # حفظ الأجزاء للمراجعة
        if 'text_parts' not in context.user_data:
            context.user_data['text_parts'] = []
        context.user_data['text_parts'].append(new_text)
        
        text_length = len(context.user_data['content_text'])
        parts_count = len(context.user_data['text_parts'])
        
        await update.message.reply_text(
            f"✅ تم إضافة الجزء النصي ({parts_count}).\n"
            f"إجمالي النص: {text_length} حرف\n\n"
            "يمكنك إرسال المزيد من النص أو اضغط على '✅ إنهاء وحفظ' لحفظ المحتوى",
            reply_markup=KeyboardManager.get_text_input_keyboard()
        )
        return ADD_CONTENT_TEXT

async def add_content_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content_type = context.user_data['content_type']
    file_id = None
    
    if content_type == "photo" and update.message.photo:
        file_id = update.message.photo[-1].file_id
    elif content_type == "video" and update.message.video:
        file_id = update.message.video.file_id
    elif content_type == "document" and update.message.document:
        file_id = update.message.document.file_id
    
    if file_id:
        # إنشاء المحتوى
        new_content = BotDatabase.add_content(
            context.user_data['content_title'],
            context.user_data['content_type'],
            "",
            file_id
        )
        
        await update.message.reply_text(
            f"✅ تم إضافة المحتوى بنجاح!\n\n"
            f"📖 العنوان: {new_content['title']}\n"
            f"🎯 النوع: {new_content['content_type']}\n"
            f"🆔 الرقم: {new_content['id']}",
            reply_markup=KeyboardManager.get_admin_keyboard()
        )
        
        return ConversationHandler.END
    else:
        await update.message.reply_text(
            "❌ لم يتم إرسال ملف من النوع المطلوب. حاول مرة أخرى.",
            reply_markup=KeyboardManager.get_back_keyboard()
        )
        return ADD_CONTENT_FILE

async def start_delete_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content_items = BotDatabase.get_all_content()
    
    if not content_items:
        await update.message.reply_text("❌ لا يوجد محتوى لحذفه.")
        return ConversationHandler.END
    
    text = "🗑️ حذف محتوى\n\nالمحتوى الحالي:\n"
    for item in content_items[:10]:
        text += f"• {item['id']}: {item['title']} ({item['content_type']})\n"
    
    if len(content_items) > 10:
        text += f"\n... و{len(content_items) - 10} عنصر آخر"
    
    text += "\n\nأرسل رقم المحتوى الذي تريد حذفه:"
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_back_keyboard())
    return DELETE_CONTENT

async def delete_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        content_id = int(update.message.text)
        deleted_content = BotDatabase.delete_content(content_id)
        
        if deleted_content:
            await update.message.reply_text(
                f"✅ تم حذف المحتوى: {deleted_content['title']}",
                reply_markup=KeyboardManager.get_admin_keyboard()
            )
        else:
            await update.message.reply_text("❌ لم يتم العثور على المحتوى.")
    
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
    
    return ConversationHandler.END

async def show_all_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content_items = BotDatabase.get_all_content()
    
    if not content_items:
        await update.message.reply_text("📭 لا يوجد محتوى.")
        return
    
    text = "📋 جميع المحتويات:\n\n"
    for item in content_items[:15]:
        text += f"• {item['title']}\n"
        text += f"  🆔 الرقم: {item['id']}\n"
        text += f"  🎯 النوع: {item['content_type']}\n"
        text += f"  📅 التاريخ: {item.get('created_date', '')[:10]}\n\n"
    
    if len(content_items) > 15:
        text += f"📎 ... و{len(content_items) - 15} عنصر آخر"
    
    await update.message.reply_text(text)

async def show_subscription_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = BotDatabase.get_setting("subscription.enabled")
    channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
    
    text = (
        "📢 إدارة الاشتراك الإجباري\n\n"
        f"الحالة: {'✅ مفعل' if enabled else '❌ معطل'}\n"
        f"عدد القنوات: {len(channels)}\n"
        f"الرسالة: {BotDatabase.get_setting('subscription.message')}\n\n"
        "اختر الإجراء:"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_subscription_management_keyboard())

async def toggle_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_state = BotDatabase.get_setting("subscription.enabled")
    new_state = not current_state
    BotDatabase.set_setting("subscription.enabled", new_state)
    
    await update.message.reply_text(
        f"✅ تم {'تفعيل' if new_state else 'إلغاء تفعيل'} الاشتراك الإجباري.",
        reply_markup=KeyboardManager.get_subscription_management_keyboard()
    )

async def start_edit_subscription_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✏️ تعديل رسالة الاشتراك الإجباري\n\n"
        f"الرسالة الحالية:\n{BotDatabase.get_setting('subscription.message')}\n\n"
        "أرسل الرسالة الجديدة:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return EDIT_SUBSCRIPTION_MESSAGE

async def edit_subscription_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_message = update.message.text
    BotDatabase.set_setting("subscription.message", new_message)
    
    await update.message.reply_text(
        "✅ تم تحديث رسالة الاشتراك الإجباري.",
        reply_markup=KeyboardManager.get_subscription_management_keyboard()
    )
    return ConversationHandler.END

async def start_add_subscription_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 إضافة قناة للاشتراك الإجباري\n\n"
        "أرسل معرف القناة (مثال: @channel_username):",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return ADD_SUBSCRIPTION_CHANNEL

async def add_subscription_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel = update.message.text.strip()
    
    if BotDatabase.add_subscription_channel(channel):
        await update.message.reply_text(
            f"✅ تم إضافة قناة الاشتراك: {channel}",
            reply_markup=KeyboardManager.get_subscription_management_keyboard()
        )
    else:
        await update.message.reply_text(
            "❌ القناة موجودة مسبقاً.",
            reply_markup=KeyboardManager.get_subscription_management_keyboard()
        )
    
    return ConversationHandler.END

async def start_delete_subscription_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
    
    if not channels:
        await update.message.reply_text("❌ لا توجد قنوات اشتراك لحذفها.")
        return ConversationHandler.END
    
    text = "🗑️ حذف قناة اشتراك\n\nالقنوات الحالية:\n"
    for i, channel in enumerate(channels, 1):
        text += f"{i}. {channel}\n"
    
    text += "\nأرسل رقم القناة التي تريد حذفها:"
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_back_keyboard())
    return DELETE_SUBSCRIPTION_CHANNEL

async def delete_subscription_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        channel_index = int(update.message.text) - 1
        deleted_channel = BotDatabase.delete_subscription_channel(channel_index)
        
        if deleted_channel:
            await update.message.reply_text(
                f"✅ تم حذف قناة الاشتراك: {deleted_channel}",
                reply_markup=KeyboardManager.get_subscription_management_keyboard()
            )
        else:
            await update.message.reply_text("❌ رقم القناة غير صحيح.")
    
    except ValueError:
        await update.message.reply_text("❌ الرجاء إدخال رقم صحيح.")
    
    return ConversationHandler.END

async def show_subscription_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = BotDatabase.get_subscription_channels()  # استخدام القنوات الصحيحة
    
    if not channels:
        await update.message.reply_text("📭 لا توجد قنوات اشتراك مسجلة.")
        return
    
    text = "📋 قنوات الاشتراك الإجباري:\n\n"
    for i, channel in enumerate(channels, 1):
        text += f"{i}. {channel}\n"
    
    await update.message.reply_text(text)

async def show_settings_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "⚙️ الإعدادات العامة\n\n"
        "يمكنك من هنا تعديل رسائل البوت والإعدادات المختلفة.\n\n"
        "اختر الإعداد الذي تريد تعديله:"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_settings_keyboard())

async def start_edit_response(update: Update, context: ContextTypes.DEFAULT_TYPE, response_type: str):
    context.user_data['response_type'] = response_type
    current_message = BotDatabase.get_setting(f"responses.{response_type}")
    
    response_names = {
        "welcome": "رسالة الترحيب",
        "rejected": "رسالة الرفض", 
        "help": "رسالة المساعدة"
    }
    
    await update.message.reply_text(
        f"✏️ تعديل {response_names[response_type]}\n\n"
        f"الرسالة الحالية:\n{current_message}\n\n"
        "أرسل الرسالة الجديدة:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return EDIT_RESPONSE

async def edit_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    response_type = context.user_data['response_type']
    new_message = update.message.text
    
    BotDatabase.set_setting(f"responses.{response_type}", new_message)
    
    response_names = {
        "welcome": "رسالة الترحيب",
        "rejected": "رسالة الرفض",
        "help": "رسالة المساعدة"
    }
    
    await update.message.reply_text(
        f"✅ تم تحديث {response_names[response_type]}.",
        reply_markup=KeyboardManager.get_settings_keyboard()
    )
    return ConversationHandler.END

async def toggle_forwarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_state = BotDatabase.get_setting("forwarding.enabled")
    new_state = not current_state
    BotDatabase.set_setting("forwarding.enabled", new_state)
    
    await update.message.reply_text(
        f"✅ تم {'تفعيل' if new_state else 'إلغاء تفعيل'} نظام التحويل.",
        reply_markup=KeyboardManager.get_settings_keyboard()
    )

async def show_broadcast_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    active_users = len(BotDatabase.get_approved_users())
    
    text = (
        "📤 البث للمستخدمين\n\n"
        f"عدد المستخدمين النشطين: {active_users}\n\n"
        "اختر نوع البث:"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_broadcast_keyboard())

async def start_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📢 بث لجميع المستخدمين\n\n"
        "أرسل الرسالة التي تريد بثها لجميع المستخدمين:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return BROADCAST_MESSAGE

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    active_users = BotDatabase.get_approved_users()
    
    success_count = 0
    fail_count = 0
    
    for user_id in active_users:
        try:
            await context.bot.send_message(int(user_id), message)
            success_count += 1
        except Exception as e:
            fail_count += 1
    
    await update.message.reply_text(
        f"✅ تم إرسال الرسالة:\n"
        f"• ✅ الناجح: {success_count}\n"
        f"• ❌ الفاشل: {fail_count}",
        reply_markup=KeyboardManager.get_admin_keyboard()
    )
    
    return ConversationHandler.END

async def start_send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👤 إرسال رسالة لمستخدم محدد\n\n"
        "أرسل الآيدي الخاص بالمستخدم:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return SEND_TO_USER

async def send_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.text.strip()
    context.user_data['target_user'] = user_id
    
    await update.message.reply_text(
        f"أرسل الرسالة للمستخدم {user_id}:",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return BROADCAST_MESSAGE

async def show_backup_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "💾 النسخ الاحتياطي\n\n"
        "يمكنك من هنا تنزيل نسخة احتياطية من بيانات البوت أو رفع نسخة سابقة.\n\n"
        "اختر الإجراء:"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_backup_keyboard())

async def download_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء وتنزيل نسخة احتياطية"""
    try:
        # إنشاء بيانات النسخة الاحتياطية
        backup_data = {
            "users": BotDatabase.read_json(USERS_FILE),
            "content": BotDatabase.read_json(CONTENT_FILE),
            "channels": BotDatabase.read_json(CHANNELS_FILE),
            "subscription_channels": BotDatabase.read_json(SUBSCRIPTION_CHANNELS_FILE),
            "settings": BotDatabase.read_json(SETTINGS_FILE),
            "backup_date": datetime.now().isoformat(),
            "backup_info": "تم إنشاء هذه النسخة بواسطة بوت التليجرام"
        }
        
        # حفظ النسخة الاحتياطية في ملف مؤقت
        backup_filename = f"bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=2)
        
        # إرسال الملف للمستخدم
        with open(backup_filename, 'rb') as f:
            await update.message.reply_document(
                document=f,
                filename=backup_filename,
                caption="💾 النسخة الاحتياطية للبوت\n\n"
                       "يمكنك حفظ هذا الملف واستخدامه لاستعادة البيانات لاحقاً."
            )
        
        # حذف الملف المؤقت
        os.remove(backup_filename)
        
        await update.message.reply_text(
            "✅ تم تنزيل النسخة الاحتياطية بنجاح!",
            reply_markup=KeyboardManager.get_backup_keyboard()
        )
        
    except Exception as e:
        logger.error(f"Error creating backup: {e}")
        await update.message.reply_text(
            "❌ حدث خطأ أثناء إنشاء النسخة الاحتياطية.",
            reply_markup=KeyboardManager.get_backup_keyboard()
        )

async def start_restore_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔄 رفع واستعادة نسخة احتياطية\n\n"
        "الرجاء إرسال ملف النسخة الاحتياطية (JSON):",
        reply_markup=KeyboardManager.get_back_keyboard()
    )
    return BACKUP_RESTORE

async def restore_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document:
            # تحميل الملف
            file = await update.message.document.get_file()
            file_path = f"temp_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            await file.download_to_drive(file_path)
            
            # قراءة البيانات من الملف
            with open(file_path, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            # التحقق من صحة البيانات
            if not all(key in backup_data for key in ['users', 'content', 'channels', 'settings']):
                await update.message.reply_text(
                    "❌ ملف النسخة الاحتياطية غير صالح.",
                    reply_markup=KeyboardManager.get_backup_keyboard()
                )
                os.remove(file_path)
                return ConversationHandler.END
            
            # استعادة البيانات
            BotDatabase.write_json(USERS_FILE, backup_data.get('users', {}))
            BotDatabase.write_json(CONTENT_FILE, backup_data.get('content', {}))
            BotDatabase.write_json(CHANNELS_FILE, backup_data.get('channels', {}))
            BotDatabase.write_json(SETTINGS_FILE, backup_data.get('settings', {}))
            
            # استعادة قنوات الاشتراك الإجباري إذا كانت موجودة
            if 'subscription_channels' in backup_data:
                BotDatabase.write_json(SUBSCRIPTION_CHANNELS_FILE, backup_data.get('subscription_channels', {}))
            
            # تنظيف الملف المؤقت
            os.remove(file_path)
            
            await update.message.reply_text(
                f"✅ تم استعادة النسخة الاحتياطية بنجاح!\n"
                f"📅 تاريخ النسخة: {backup_data.get('backup_date', 'غير معروف')}",
                reply_markup=KeyboardManager.get_admin_keyboard()
            )
        else:
            await update.message.reply_text(
                "❌ لم يتم إرسال ملف النسخة الاحتياطية.",
                reply_markup=KeyboardManager.get_backup_keyboard()
            )
    
    except json.JSONDecodeError:
        await update.message.reply_text(
            "❌ ملف النسخة الاحتياطية تالف أو غير صالح.",
            reply_markup=KeyboardManager.get_backup_keyboard()
        )
    except Exception as e:
        logger.error(f"Error restoring backup: {e}")
        await update.message.reply_text(
            f"❌ حدث خطأ أثناء استعادة النسخة: {str(e)}",
            reply_markup=KeyboardManager.get_backup_keyboard()
        )
    
    return ConversationHandler.END

async def show_backups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض معلومات عن النسخ الاحتياطية"""
    text = (
        "📋 معلومات النسخ الاحتياطية\n\n"
        "💾 **تنزيل نسخة**:\n"
        "• ينشئ نسخة احتياطية كاملة من بيانات البوت\n"
        "• يتم تنزيلها كملف JSON\n"
        "• يمكنك حفظها على جهازك\n\n"
        "🔄 **رفع نسخة**:\n"
        "• استعادة البيانات من ملف نسخة احتياطية\n"
        "• يجب أن يكون الملف بصيغة JSON\n"
        "• سيتم استبدال جميع البيانات الحالية\n\n"
        "⚠️ **ملاحظة مهمة**:\n"
        "• احتفظ بنسخ احتياطية في مكان آمن\n"
        "• تأكد من صحة الملف قبل الرفع\n"
        "• الاستعادة تحذف جميع البيانات الحالية"
    )
    
    await update.message.reply_text(text, reply_markup=KeyboardManager.get_backup_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    # التحقق من أن المستخدم مفعل
    if not is_user_approved(user_id) and not is_admin(user_id):
        await query.edit_message_text(
            "⏳ طلبك قيد المراجعة من قبل المدير...\n"
            "سيتم إعلامك فور الموافقة على طلبك."
        )
        return
    
    if data.startswith("content_"):
        content_id = int(data.split("_")[1])
        await show_content_item_from_message(update, context, content_id)
    elif data == "back_to_channels":
        await show_channels_to_user(update, context)
    elif data == "back_to_main":
        if is_admin(user_id):
            await query.edit_message_text("🏠 العودة للرئيسية", reply_markup=KeyboardManager.get_admin_keyboard())
        else:
            await query.edit_message_text("🏠 العودة للرئيسية", reply_markup=KeyboardManager.get_user_keyboard())
    elif not is_admin(user_id):
        await query.edit_message_text("❌ ليس لديك صلاحية للقيام بهذا الإجراء.")
        return
    elif data.startswith("accept_"):
        target_user = data.split("_")[1]
        await accept_user_callback(update, context, target_user)
    elif data.startswith("reject_"):
        target_user = data.split("_")[1]
        await reject_user_callback(update, context, target_user)
    elif data == "view_requests":
        await show_pending_requests(update, context)

async def accept_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = BotDatabase.read_json(USERS_FILE)
    
    if target_user_id in users:
        users[target_user_id]["approved"] = True
        BotDatabase.write_json(USERS_FILE, users)
        
        requests = BotDatabase.read_json(REQUESTS_FILE)
        requests = [r for r in requests if r['user_id'] != target_user_id]
        BotDatabase.write_json(REQUESTS_FILE, requests)
        
        try:
            await context.bot.send_message(
                int(target_user_id),
                BotDatabase.get_setting("responses.welcome"),
                reply_markup=KeyboardManager.get_user_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        await update.callback_query.edit_message_text(f"✅ تم قبول المستخدم: {users[target_user_id]['first_name']}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def reject_user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = BotDatabase.read_json(USERS_FILE)
    
    if target_user_id in users:
        user_name = users[target_user_id]['first_name']
        
        try:
            await context.bot.send_message(int(target_user_id), BotDatabase.get_setting("responses.rejected"))
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        del users[target_user_id]
        BotDatabase.write_json(USERS_FILE, users)
        
        requests = BotDatabase.read_json(REQUESTS_FILE)
        requests = [r for r in requests if r['user_id'] != target_user_id]
        BotDatabase.write_json(REQUESTS_FILE, requests)
        
        await update.callback_query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

def main():
    # التحقق من وجود التوكن
    if BOT_TOKEN == 'YOUR_BOT_TOKEN_HERE':
        print("❌ لم يتم تعيين التوكن! يرجى تعيين متغير البيئة BOT_TOKEN")
        return
    
    BotDatabase.init_default_data()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # محادثات المدير
    add_channel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة قناة$"), start_add_channel)],
        states={
            ADD_CHANNEL_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_name)],
            ADD_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_channel_link)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    delete_channel_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ حذف قناة$"), start_delete_channel)],
        states={
            DELETE_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_channel)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    add_content_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة محتوى$"), start_add_content)],
        states={
            ADD_CONTENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content_title)],
            ADD_CONTENT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content_type)],
            ADD_CONTENT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content_text)],
            ADD_CONTENT_FILE: [MessageHandler(filters.PHOTO | filters.VIDEO | filters.Document.ALL, add_content_file)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    delete_content_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ حذف محتوى$"), start_delete_content)],
        states={
            DELETE_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_content)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    delete_user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗑️ حذف مستخدم$"), start_delete_user)],
        states={
            DELETE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_user)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    subscription_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ تعديل الرسالة$"), start_edit_subscription_message),
            MessageHandler(filters.Regex("^📝 إضافة قناة اشتراك$"), start_add_subscription_channel),
            MessageHandler(filters.Regex("^🗑️ حذف قناة اشتراك$"), start_delete_subscription_channel),
        ],
        states={
            EDIT_SUBSCRIPTION_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_subscription_message)],
            ADD_SUBSCRIPTION_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_subscription_channel)],
            DELETE_SUBSCRIPTION_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, delete_subscription_channel)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    settings_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ تعديل رسالة الترحيب$"), lambda u, c: start_edit_response(u, c, "welcome")),
            MessageHandler(filters.Regex("^✏️ تعديل رسالة الرفض$"), lambda u, c: start_edit_response(u, c, "rejected")),
            MessageHandler(filters.Regex("^✏️ تعديل رسالة المساعدة$"), lambda u, c: start_edit_response(u, c, "help")),
        ],
        states={
            EDIT_RESPONSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_response)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    broadcast_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📢 بث لجميع المستخدمين$"), start_broadcast),
            MessageHandler(filters.Regex("^👤 بث لمستخدم محدد$"), start_send_to_user),
        ],
        states={
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_message)],
            SEND_TO_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_to_user)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    backup_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔄 رفع نسخة$"), start_restore_backup)],
        states={
            BACKUP_RESTORE: [MessageHandler(filters.Document.ALL, restore_backup)],
        },
        fallbacks=[MessageHandler(filters.Regex("^🏠 الرئيسية$"), show_admin_dashboard)]
    )
    
    # إضافة جميع handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(add_channel_conv)
    application.add_handler(delete_channel_conv)
    application.add_handler(add_content_conv)
    application.add_handler(delete_content_conv)
    application.add_handler(delete_user_conv)
    application.add_handler(subscription_conv)
    application.add_handler(settings_conv)
    application.add_handler(broadcast_conv)
    application.add_handler(backup_conv)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
