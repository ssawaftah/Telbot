import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات البوت
BOT_TOKEN = "8240559018:AAEGsGl-pKEPM3kCenefbE4DfLMQ1Ci586g"
ADMIN_IDS = []  # سيتم إضافة آيدي المدير تلقائياً

# ملفات البيانات
USERS_FILE = "data/users.json"
CONTENT_FILE = "data/content.json"
SETTINGS_FILE = "data/settings.json"
REQUESTS_FILE = "data/requests.json"

# تهيئة الملفات
def init_files():
    os.makedirs("data", exist_ok=True)
    
    defaults = {
        USERS_FILE: {},
        CONTENT_FILE: {"categories": [], "content": []},
        SETTINGS_FILE: {
            "subscription": {"enabled": False, "channels": [], "message": "اشترك في القناة أولاً!"},
            "responses": {
                "welcome": "مرحباً! تم قبول طلبك.",
                "rejected": "تم رفض طلبك. تواصل مع المدير.",
                "subscribe": "يجب الاشتراك في القناة أولاً!"
            },
            "forwarding": False
        },
        REQUESTS_FILE: []
    }
    
    for file, default in defaults.items():
        if not os.path.exists(file):
            with open(file, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)

# وظائف القراءة/الكتابة للبيانات
def read_json(file):
    try:
        with open(file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def write_json(file, data):
    with open(file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# لوحات المفاتيح
def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📚 الأقسام", callback_data="view_categories")],
        [InlineKeyboardButton("ℹ️ المساعدة", callback_data="help"),
         InlineKeyboardButton("👤 الملف", callback_data="profile")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 إدارة المستخدمين", callback_data="admin_users")],
        [InlineKeyboardButton("📢 الاشتراك الإجباري", callback_data="admin_subscription")],
        [InlineKeyboardButton("⚙️ إعدادات الردود", callback_data="admin_responses")],
        [InlineKeyboardButton("📈 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("📤 الإذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("📝 الأقسام", callback_data="admin_categories")],
        [InlineKeyboardButton("🎭 المحتوى", callback_data="admin_content")],
        [InlineKeyboardButton("💾 النسخ الاحتياطي", callback_data="admin_backup")]
    ])

def user_management_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 طلبات الانضمام", callback_data="view_requests")],
        [InlineKeyboardButton("👀 عرض المستخدمين", callback_data="view_users")],
        [InlineKeyboardButton("🗑️ حذف مستخدم", callback_data="delete_user")],
        [InlineKeyboardButton("🔔 تفعيل/إلغاء", callback_data="toggle_users")],
        [InlineKeyboardButton("🏠 الرئيسية", callback_data="admin_main")]
    ])

# أوامر البوت
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    settings = read_json(SETTINGS_FILE)
    
    # إذا كان المدير
    if not ADMIN_IDS:
        ADMIN_IDS.append(user_id)
        await update.message.reply_text("✅ تم تعيينك كمدير للبوت!")
        await show_admin_panel(update, context)
        return
    
    if user_id in users:
        if users[user_id]["approved"]:
            # التحقق من الاشتراك إذا كان مفعلاً
            if settings["subscription"]["enabled"]:
                if not await check_subscription(user_id, context):
                    channels = "\n".join(settings["subscription"]["channels"])
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("📢 قنوات الاشتراك", url=channels)],
                        [InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_subscription")]
                    ])
                    await update.message.reply_text(settings["responses"]["subscribe"], reply_markup=keyboard)
                    return
            
            await update.message.reply_text("مرحباً مرة أخرى! 👋", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("⏳ طلبك قيد المراجعة...")
    else:
        # إضافة طلب جديد
        user_data = {
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "join_date": datetime.now().isoformat(),
            "approved": False
        }
        users[user_id] = user_data
        write_json(USERS_FILE, users)
        
        request_data = {
            "user_id": user_id,
            "username": user_data["username"],
            "first_name": user_data["first_name"],
            "date": datetime.now().isoformat()
        }
        requests.append(request_data)
        write_json(REQUESTS_FILE, requests)
        
        # إشعار المدير
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_id}"),
                     InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")],
                    [InlineKeyboardButton("📋 طلبات الانضمام", callback_data="view_requests")]
                ])
                await context.bot.send_message(
                    admin_id,
                    f"📥 طلب انضمام جديد!\n👤 المستخدم: {user_data['first_name']}\n🆔 الآيدي: {user_id}",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Error notifying admin: {e}")
        
        await update.message.reply_text("✅ تم إرسال طلب انضمامك! سيتم مراجعته قريباً.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(update.effective_user.id)
    
    # أوامر المدير
    if data == "admin_main":
        await show_admin_panel(update, context)
    
    elif data == "admin_users":
        await show_user_management(update, context)
    
    elif data == "view_requests":
        await show_join_requests(update, context)
    
    elif data.startswith("accept_"):
        target_user = data.split("_")[1]
        await accept_user(update, context, target_user)
    
    elif data.startswith("reject_"):
        target_user = data.split("_")[1]
        await reject_user(update, context, target_user)
    
    # أوامر المستخدمين
    elif data == "view_categories":
        await show_categories(update, context)
    
    elif data == "help":
        await query.edit_message_text("ℹ️ للمساعدة تواصل مع المدير.")
    
    elif data == "profile":
        await show_profile(update, context)

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        return
    
    users = read_json(USERS_FILE)
    content = read_json(CONTENT_FILE)
    requests = read_json(REQUESTS_FILE)
    
    stats_text = f"""
👑 لوحة تحكم المدير

الإحصائيات:
• 👥 المستخدمين: {len([u for u in users.values() if u['approved']])}
• ⏳ الطلبات المعلقة: {len(requests)}
• 📊 المحتوى: {len(content.get('content', []))}
• 📂 الأقسام: {len(content.get('categories', []))}
"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(stats_text, reply_markup=admin_keyboard())
    else:
        await update.message.reply_text(stats_text, reply_markup=admin_keyboard())

async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        return
    
    users = read_json(USERS_FILE)
    approved_users = len([u for u in users.values() if u['approved']])
    
    text = f"""
👥 إدارة المستخدمين

• المستخدمين النشطين: {approved_users}
• الطلبات المعلقة: {len(read_json(REQUESTS_FILE))}
"""
    
    await update.callback_query.edit_message_text(text, reply_markup=user_management_keyboard())

async def show_join_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in ADMIN_IDS:
        return
    
    requests = read_json(REQUESTS_FILE)
    
    if not requests:
        text = "📭 لا توجد طلبات انضمام معلقة."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="admin_main")]])
    else:
        text = "📋 طلبات الانضمام:\n\n"
        keyboard_buttons = []
        
        for req in requests:
            text += f"👤 {req['first_name']} (@{req['username']})\n🆔 {req['user_id']}\n📅 {req['date'][:10]}\n────────────\n"
            
            keyboard_buttons.append([
                InlineKeyboardButton(f"✅ {req['first_name']}", callback_data=f"accept_{req['user_id']}"),
                InlineKeyboardButton(f"❌ رفض", callback_data=f"reject_{req['user_id']}")
            ])
        
        keyboard_buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="admin_main")])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)

async def accept_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    
    if target_user_id in users:
        users[target_user_id]["approved"] = True
        
        # إزالة من طلبات الانضمام
        requests = [r for r in requests if r['user_id'] != target_user_id]
        
        write_json(USERS_FILE, users)
        write_json(REQUESTS_FILE, requests)
        
        # إرسال رسالة للمستخدم
        try:
            settings = read_json(SETTINGS_FILE)
            await context.bot.send_message(target_user_id, settings["responses"]["welcome"])
        except:
            pass
        
        await update.callback_query.edit_message_text(f"✅ تم قبول المستخدم {target_user_id}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    
    if target_user_id in users:
        del users[target_user_id]
        
        # إزالة من طلبات الانضمام
        requests = [r for r in requests if r['user_id'] != target_user_id]
        
        write_json(USERS_FILE, users)
        write_json(REQUESTS_FILE, requests)
        
        # إرسال رسالة للمستخدم
        try:
            settings = read_json(SETTINGS_FILE)
            await context.bot.send_message(target_user_id, settings["responses"]["rejected"])
        except:
            pass
        
        await update.callback_query.edit_message_text(f"❌ تم رفض المستخدم {target_user_id}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    if not categories:
        text = "📭 لا توجد أقسام متاحة حالياً."
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="start")]])
    else:
        text = "📂 الأقسام المتاحة:\n\n"
        keyboard_buttons = []
        
        for cat in categories:
            text += f"• {cat.get('icon', '📁')} {cat.get('name', 'بدون اسم')}\n"
            keyboard_buttons.append([InlineKeyboardButton(
                f"{cat.get('icon', '📁')} {cat.get('name', 'بدون اسم')}", 
                callback_data=f"category_{cat.get('id', '')}"
            )])
        
        keyboard_buttons.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="start")])
        keyboard = InlineKeyboardMarkup(keyboard_buttons)
    
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = read_json(USERS_FILE)
    
    if user_id in users:
        user_data = users[user_id]
        text = f"""
👤 ملفك الشخصي

• الاسم: {user_data['first_name']}
• المعرف: @{user_data.get('username', 'غير متوفر')}
• تاريخ الانضمام: {user_data['join_date'][:10]}
• الحالة: {'✅ مفعل' if user_data['approved'] else '⏳ قيد المراجعة'}
"""
    else:
        text = "❌ لم يتم العثور على بياناتك."
    
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🏠 الرئيسية", callback_data="start")]])
    await update.callback_query.edit_message_text(text, reply_markup=keyboard)

async def check_subscription(user_id: str, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # هذه الدالة تحتاج لتطبيق للتحقق من اشتراك المستخدم في القنوات
    # حالياً نعتبر أن المستخدم مشترك
    return True

def main():
    # تهيئة الملفات
    init_files()
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # بدء البوت
    print("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
