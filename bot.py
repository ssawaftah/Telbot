import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات البوت
BOT_TOKEN = "8240559018:AAEGsGl-pKEPM3kCenefbE4DfLMQ1Ci586g"
ADMIN_IDS = [6455001010]  # ضع آيدي المدير هنا (استبدل 123456789 بآيديك الحقيقي)

# حالات المحادثة
ADD_CATEGORY_NAME, ADD_CATEGORY_ICON = range(2)
ADD_CONTENT_TITLE, ADD_CONTENT_TYPE, ADD_CONTENT_FILE, ADD_CONTENT_CATEGORY = range(4)

# ملفات البيانات
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONTENT_FILE = os.path.join(DATA_DIR, "content.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# تهيئة البيانات الافتراضية
def init_default_data():
    default_data = {
        USERS_FILE: {},
        CONTENT_FILE: {
            "categories": [
                {"id": 1, "name": "القسم الأول", "icon": "📚", "created_date": datetime.now().isoformat()},
                {"id": 2, "name": "القسم الثاني", "icon": "🎨", "created_date": datetime.now().isoformat()}
            ],
            "content": []
        },
        SETTINGS_FILE: {
            "subscription": {
                "enabled": False,
                "channels": ["@channel_username"],
                "message": "📢 يجب الاشتراك في القناة أولاً لتتمكن من استخدام البوت"
            },
            "responses": {
                "welcome": "🎉 مرحباً! تم قبول طلبك بنجاح.\nيمكنك الآن استخدام البوت والاستفادة من محتوانا.",
                "rejected": "❌ تم رفض طلبك.\nللمساعدة تواصل مع المدير.",
                "help": "ℹ️ للمساعدة تواصل مع مدير البوت."
            },
            "forwarding": {
                "enabled": False
            }
        }
    }
    
    for file_path, default_content in default_data.items():
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(default_content, f, ensure_ascii=False, indent=2)

# وظائف البيانات
def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def write_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_setting(key_path):
    settings = read_json(SETTINGS_FILE)
    keys = key_path.split('.')
    value = settings
    for key in keys:
        value = value.get(key, {}) if isinstance(value, dict) else value
    return value

def is_admin(user_id):
    return str(user_id) in [str(admin_id) for admin_id in ADMIN_IDS]

# لوحات المفاتيح
def get_user_keyboard():
    return ReplyKeyboardMarkup([
        ["📂 تصفح الأقسام", "👤 ملفي الشخصي"],
        ["ℹ️ المساعدة"]
    ], resize_keyboard=True)

def get_admin_keyboard():
    return ReplyKeyboardMarkup([
        ["👑 لوحة التحكم", "📊 الإحصائيات"],
        ["👥 إدارة المستخدمين", "📢 الاشتراك الإجباري"],
        ["📝 إدارة الأقسام", "🎭 إدارة المحتوى"],
        ["⚙️ الإعدادات العامة", "📤 البث للمستخدمين"]
    ], resize_keyboard=True)

def get_back_to_main_keyboard(is_admin=False):
    if is_admin:
        return ReplyKeyboardMarkup([["🏠 الرئيسية"]], resize_keyboard=True)
    else:
        return ReplyKeyboardMarkup([["🏠 الرئيسية"]], resize_keyboard=True)

def get_categories_keyboard():
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    keyboard = []
    for category in categories:
        keyboard.append([f"{category['icon']} {category['name']}"])
    
    keyboard.append(["🏠 الرئيسية"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# الأوامر الرئيسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name
    
    # إذا كان المدير
    if is_admin(user_id):
        await update.message.reply_text(
            f"👑 أهلاً بك يا {user_name}!\n"
            "أنت مسجل كمشرف على البوت.\n\n"
            "اختر من لوحة التحكم أدناه:",
            reply_markup=get_admin_keyboard()
        )
        return
    
    users = read_json(USERS_FILE)
    user_key = str(user_id)
    
    if user_key in users:
        user_data = users[user_key]
        if user_data.get("approved", False):
            # التحقق من الاشتراك الإجباري
            if get_setting("subscription.enabled"):
                if not await check_subscription(user_id, context):
                    channels = get_setting("subscription.channels")
                    channels_text = "\n".join([f"• {ch}" for ch in channels])
                    
                    await update.message.reply_text(
                        f"{get_setting('subscription.message')}\n\n"
                        f"القنوات المطلوبة:\n{channels_text}\n\n"
                        "بعد الاشتراك، اضغط على /start مرة أخرى",
                        reply_markup=ReplyKeyboardMarkup([["✅ تحقق من الاشتراك"]], resize_keyboard=True)
                    )
                    return
            
            await update.message.reply_text(
                f"مرحباً مرة أخرى {user_name}! 👋\n"
                "اختر من القائمة أدناه:",
                reply_markup=get_user_keyboard()
            )
        else:
            await update.message.reply_text(
                "⏳ طلبك قيد المراجعة من قبل المدير...\n"
                "سيتم إعلامك فور الموافقة على طلبك.",
                reply_markup=ReplyKeyboardMarkup([["⏳ انتظر الموافقة"]], resize_keyboard=True)
            )
    else:
        # تسجيل مستخدم جديد
        user_data = {
            "username": update.effective_user.username,
            "first_name": user_name,
            "join_date": datetime.now().isoformat(),
            "approved": False
        }
        users[user_key] = user_data
        write_json(USERS_FILE, users)
        
        # إشعار المديرين
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
                    f"👤 المستخدم: {user_name}\n"
                    f"🆔 الآيدي: {user_key}\n"
                    f"📅 الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error notifying admin: {e}")
        
        await update.message.reply_text(
            "✅ تم إرسال طلب انضمامك بنجاح!\n"
            "سيتم مراجعته من قبل المدير قريباً.",
            reply_markup=ReplyKeyboardMarkup([["⏳ انتظر الموافقة"]], resize_keyboard=True)
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if is_admin(user_id):
        await handle_admin_commands(update, context, text)
    else:
        await handle_user_commands(update, context, text)

async def handle_admin_commands(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if text == "👑 لوحة التحكم":
        await show_admin_dashboard(update, context)
    elif text == "👥 إدارة المستخدمين":
        await show_user_management(update, context)
    elif text == "📊 الإحصائيات":
        await show_statistics(update, context)
    elif text == "📝 إدارة الأقسام":
        await show_categories_management(update, context)
    elif text == "🎭 إدارة المحتوى":
        await show_content_management(update, context)
    elif text == "📢 الاشتراك الإجباري":
        await show_subscription_management(update, context)
    elif text == "📂 تصفح الأقسام":
        await show_categories_to_user(update, context)
    elif text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 العودة للرئيسية", reply_markup=get_admin_keyboard())
    else:
        await handle_category_selection(update, context, text)

async def handle_user_commands(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    if text == "📂 تصفح الأقسام":
        await show_categories_to_user(update, context)
    elif text == "👤 ملفي الشخصي":
        await show_user_profile(update, context)
    elif text == "ℹ️ المساعدة":
        await update.message.reply_text(get_setting("responses.help"))
    elif text == "✅ تحقق من الاشتراك":
        if await check_subscription(update.effective_user.id, context):
            await update.message.reply_text(
                "✅ تم التحقق من اشتراكك بنجاح!\n"
                "يمكنك الآن استخدام البوت.",
                reply_markup=get_user_keyboard()
            )
        else:
            channels = get_setting("subscription.channels")
            channels_text = "\n".join([f"• {ch}" for ch in channels])
            await update.message.reply_text(
                f"❌ لم يتم التحقق من اشتراكك بعد!\n\n"
                f"يجب الاشتراك في:\n{channels_text}"
            )
    elif text == "🏠 الرئيسية":
        await update.message.reply_text("🏠 العودة للرئيسية", reply_markup=get_user_keyboard())
    else:
        await handle_category_selection(update, context, text)

async def handle_category_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    for category in categories:
        if text == f"{category['icon']} {category['name']}":
            await show_category_content(update, context, category['id'])
            return
    
    await update.message.reply_text("❌ لم أفهم طلبك. اختر من القائمة أدناه:")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text("❌ ليس لديك صلاحية للقيام بهذا الإجراء.")
        return
    
    if data.startswith("accept_"):
        target_user = data.split("_")[1]
        await accept_user(update, context, target_user)
    elif data.startswith("reject_"):
        target_user = data.split("_")[1]
        await reject_user(update, context, target_user)
    elif data == "view_requests":
        await show_join_requests(update, context)

# وظائف المدير
async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    content = read_json(CONTENT_FILE)
    
    active_users = len([u for u in users.values() if u.get('approved', False)])
    total_users = len(users)
    pending_requests = len([u for u in users.values() if not u.get('approved', False)])
    categories_count = len(content.get('categories', []))
    content_count = len(content.get('content', []))
    
    stats_text = (
        "👑 لوحة تحكم المدير\n\n"
        "📊 الإحصائيات السريعة:\n"
        f"• 👥 المستخدمين النشطين: {active_users}\n"
        f"• ⏳ طلبات الانتظار: {pending_requests}\n"
        f"• 📂 الأقسام: {categories_count}\n"
        f"• 🎭 محتوى: {content_count}\n\n"
        "اختر من القائمة أدناه للإدارة:"
    )
    
    await update.message.reply_text(stats_text, reply_markup=get_admin_keyboard())

async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    pending_users = [uid for uid, data in users.items() if not data.get('approved', False)]
    
    text = "👥 إدارة المستخدمين\n\n"
    if pending_users:
        text += f"لديك {len(pending_users)} طلب انتظار\n"
        text += "استخدم الأزرار أدناه للتحكم:"
    else:
        text += "لا توجد طلبات انتظار حالياً.\n"
    
    keyboard = ReplyKeyboardMarkup([
        ["📋 عرض طلبات الانتظار", "👀 عرض جميع المستخدمين"],
        ["🗑️ حذف مستخدم", "🏠 الرئيسية"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(text, reply_markup=keyboard)

async def show_join_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    pending_users = {uid: data for uid, data in users.items() if not data.get('approved', False)}
    
    if not pending_users:
        await update.message.reply_text("📭 لا توجد طلبات انضمام معلقة.")
        return
    
    text = "📋 طلبات الانضمام المعلقة:\n\n"
    for user_id, user_data in pending_users.items():
        text += f"👤 {user_data['first_name']}\n"
        text += f"🆔 {user_id}\n"
        text += f"📅 {user_data['join_date'][:10]}\n"
        
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_id}"),
             InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")]
        ])
        
        await update.message.reply_text(text, reply_markup=keyboard)
        text = "─" * 30 + "\n"

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    active_users = {uid: data for uid, data in users.items() if data.get('approved', False)}
    
    if not active_users:
        await update.message.reply_text("👥 لا يوجد مستخدمين نشطين.")
        return
    
    text = f"👥 جميع المستخدمين النشطين ({len(active_users)}):\n\n"
    for user_id, user_data in list(active_users.items())[:20]:  # عرض أول 20 مستخدم
        text += f"👤 {user_data['first_name']}\n"
        text += f"🆔 {user_id}\n"
        text += f"📅 {user_data['join_date'][:10]}\n"
        text += "─" * 20 + "\n"
    
    await update.message.reply_text(text)

async def accept_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    
    if target_user_id in users:
        users[target_user_id]["approved"] = True
        write_json(USERS_FILE, users)
        
        # إرسال رسالة للمستخدم
        try:
            await context.bot.send_message(
                int(target_user_id),
                get_setting("responses.welcome"),
                reply_markup=get_user_keyboard()
            )
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        await update.callback_query.edit_message_text(f"✅ تم قبول المستخدم: {users[target_user_id]['first_name']}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    
    if target_user_id in users:
        user_name = users[target_user_id]['first_name']
        
        # إرسال رسالة للمستخدم
        try:
            await context.bot.send_message(int(target_user_id), get_setting("responses.rejected"))
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        del users[target_user_id]
        write_json(USERS_FILE, users)
        
        await update.callback_query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    content = read_json(CONTENT_FILE)
    
    active_users = len([u for u in users.values() if u.get('approved', False)])
    total_users = len(users)
    categories_count = len(content.get('categories', []))
    content_count = len(content.get('content', []))
    
    text = (
        "📊 الإحصائيات التفصيلية\n\n"
        f"👥 المستخدمين:\n"
        f"• النشطين: {active_users}\n"
        f"• الإجمالي: {total_users}\n"
        f"• النسبة: {round((active_users/total_users)*100 if total_users > 0 else 0, 1)}%\n\n"
        f"🎭 المحتوى:\n"
        f"• الأقسام: {categories_count}\n"
        f"• العناصر: {content_count}\n\n"
        f"⚙️ الإعدادات:\n"
        f"• الاشتراك الإجباري: {'✅ مفعل' if get_setting('subscription.enabled') else '❌ معطل'}\n"
        f"• التحويل: {'✅ مفعل' if get_setting('forwarding.enabled') else '❌ معطل'}"
    )
    
    await update.message.reply_text(text)

async def show_categories_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    text = "📝 إدارة الأقسام\n\n"
    if categories:
        text += "الأقسام الحالية:\n"
        for cat in categories:
            text += f"• {cat['icon']} {cat['name']} (ID: {cat['id']})\n"
    else:
        text += "لا توجد أقسام حالياً.\n"
    
    keyboard = ReplyKeyboardMarkup([
        ["➕ إضافة قسم جديد", "🗑️ حذف قسم"],
        ["📋 عرض الأقسام", "🏠 الرئيسية"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(text, reply_markup=keyboard)

async def show_content_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    items_count = len(content.get("content", []))
    
    text = f"🎭 إدارة المحتوى\n\nإجمالي العناصر: {items_count}\n\n"
    text += "اختر الإجراء المطلوب:"
    
    keyboard = ReplyKeyboardMarkup([
        ["➕ إضافة محتوى جديد", "🗑️ حذف محتوى"],
        ["📋 عرض المحتوى", "🏠 الرئيسية"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(text, reply_markup=keyboard)

async def show_subscription_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = get_setting("subscription.enabled")
    channels = get_setting("subscription.channels")
    
    text = (
        "📢 إدارة الاشتراك الإجباري\n\n"
        f"الحالة: {'✅ مفعل' if enabled else '❌ معطل'}\n"
        f"عدد القنوات: {len(channels)}\n"
        f"الرسالة: {get_setting('subscription.message')}\n\n"
        "اختر الإجراء:"
    )
    
    keyboard = ReplyKeyboardMarkup([
        ["🔔 تفعيل/إلغاء", "✏️ تعديل الرسالة"],
        ["📝 إضافة قناة", "🗑️ حذف قناة"],
        ["🏠 الرئيسية"]
    ], resize_keyboard=True)
    
    await update.message.reply_text(text, reply_markup=keyboard)

async def show_categories_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    if not categories:
        await update.message.reply_text("📭 لا توجد أقسام متاحة حالياً.")
        return
    
    await update.message.reply_text(
        "📂 الأقسام المتاحة:\nاختر القسم الذي تريد تصفحه:",
        reply_markup=get_categories_keyboard()
    )

async def show_category_content(update: Update, context: ContextTypes.DEFAULT_TYPE, category_id: int):
    content_data = read_json(CONTENT_FILE)
    category_content = [item for item in content_data.get("content", []) if item.get("category_id") == category_id]
    
    if not category_content:
        await update.message.reply_text("📭 لا يوجد محتوى في هذا القسم حالياً.")
        return
    
    # هنا يمكنك تطوير عرض المحتوى حسب نوعه (صور، فيديوهات، إلخ)
    text = f"📂 محتوى القسم:\n\n"
    for item in category_content[:10]:  # عرض أول 10 عناصر
        text += f"• {item.get('title', 'بدون عنوان')}\n"
    
    if len(category_content) > 10:
        text += f"\n... و{len(category_content) - 10} عنصر آخر"
    
    await update.message.reply_text(text)

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    users = read_json(USERS_FILE)
    user_key = str(user_id)
    
    if user_key in users:
        user_data = users[user_key]
        text = (
            f"👤 ملفك الشخصي\n\n"
            f"• الاسم: {user_data['first_name']}\n"
            f"• المعرف: @{user_data.get('username', 'غير متوفر')}\n"
            f"• تاريخ الانضمام: {user_data['join_date'][:10]}\n"
            f"• الحالة: {'✅ مفعل' if user_data.get('approved', False) else '⏳ قيد المراجعة'}"
        )
    else:
        text = "❌ لم يتم العثور على بياناتك."
    
    await update.message.reply_text(text)

async def check_subscription(user_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # هذه دالة تحتاج لتطبيق للتحقق من اشتراك المستخدم في القنوات
    # حالياً نعتبر أن المستخدم مشترك (للتجربة)
    return True

def main():
    # تهيئة البيانات
    init_default_data()
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # بدء البوت
    print("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
