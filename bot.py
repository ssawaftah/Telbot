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
ADMIN_IDS = []  # سيتم إضافة آيدي المدير تلقائياً

# حالات المحادثة
ADD_CONTENT_TITLE, ADD_CONTENT, ADD_CONTENT_CATEGORY = range(3)

# ملفات البيانات
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "users.json")
CONTENT_FILE = os.path.join(DATA_DIR, "content.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
REQUESTS_FILE = os.path.join(DATA_DIR, "requests.json")

# تهيئة الملفات والبيانات
def init_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # ملف المستخدمين
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    
    # ملف المحتوى
    if not os.path.exists(CONTENT_FILE):
        with open(CONTENT_FILE, 'w', encoding='utf-8') as f:
            json.dump({"categories": [], "content": []}, f, ensure_ascii=False, indent=2)
    
    # ملف الإعدادات
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "subscription": {
                "enabled": False,
                "channels": [],
                "message": "يجب الاشتراك في القناة أولاً!"
            },
            "responses": {
                "welcome": "مرحباً! تم قبول طلبك.",
                "rejected": "تم رفض طلبك. تواصل مع المدير.",
                "help": "ℹ️ للمساعدة، تواصل مع مدير البوت."
            },
            "forwarding": {
                "enabled": False
            }
        }
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, ensure_ascii=False, indent=2)
    
    # ملف الطلبات
    if not os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)

# وظائف القراءة/الكتابة للبيانات
def read_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        if "settings" in file_path:
            return {}
        elif "content" in file_path:
            return {"categories": [], "content": []}
        elif "requests" in file_path:
            return []
        else:
            return {}

def write_json(file_path, data):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_setting(key_path):
    settings = read_json(SETTINGS_FILE)
    keys = key_path.split('.')
    value = settings
    for key in keys:
        value = value.get(key, {})
    return value

def set_setting(key_path, value):
    settings = read_json(SETTINGS_FILE)
    keys = key_path.split('.')
    current = settings
    for key in keys[:-1]:
        current = current.setdefault(key, {})
    current[keys[-1]] = value
    write_json(SETTINGS_FILE, settings)

# لوحات المفاتيح الرئيسية
def main_user_keyboard():
    return ReplyKeyboardMarkup([
        ["📂 الأقسام", "👤 الملف الشخصي"],
        ["ℹ️ المساعدة"]
    ], resize_keyboard=True)

def admin_main_keyboard():
    return ReplyKeyboardMarkup([
        ["👑 لوحة التحكم", "📊 الإحصائيات"],
        ["👥 إدارة المستخدمين", "📢 الاشتراك الإجباري"],
        ["⚙️ إعدادات الردود", "📤 الإذاعة"],
        ["📝 إدارة الأقسام", "🎭 إدارة المحتوى"],
        ["💾 النسخ الاحتياطي"]
    ], resize_keyboard=True)

def user_management_keyboard():
    return ReplyKeyboardMarkup([
        ["📋 طلبات الانضمام", "👀 عرض المستخدمين"],
        ["🗑️ حذف مستخدم", "🔔 تفعيل/إلغاء النظام"],
        ["🏠 الرئيسية"]
    ], resize_keyboard=True)

def content_management_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ إضافة محتوى", "🗑️ حذف محتوى"],
        ["✏️ تعديل محتوى", "📋 عرض المحتوى"],
        ["🏠 الرئيسية"]
    ], resize_keyboard=True)

def categories_management_keyboard():
    return ReplyKeyboardMarkup([
        ["➕ إضافة قسم", "🗑️ حذف قسم"],
        ["✏️ تعديل قسم", "📋 عرض الأقسام"],
        ["🏠 الرئيسية"]
    ], resize_keyboard=True)

def subscription_management_keyboard():
    return ReplyKeyboardMarkup([
        ["🔔 تفعيل/إلغاء", "✏️ تعديل الرسالة"],
        ["📝 إضافة قناة", "🗑️ حذف قناة"],
        ["📋 عرض القنوات", "🏠 الرئيسية"]
    ], resize_keyboard=True)

# أوامر البوت الرئيسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # إذا كان المدير
    if not ADMIN_IDS:
        ADMIN_IDS.append(user_id)
        await update.message.reply_text(
            "👑 تم تعيينك كمدير للبوت!\n\n"
            "يمكنك الآن استخدام لوحة التحكم للإدارة الكاملة للبوت.",
            reply_markup=admin_main_keyboard()
        )
        return
    
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    
    if user_id in users:
        if users[user_id]["approved"]:
            # التحقق من الاشتراك الإجباري
            if get_setting("subscription.enabled"):
                if not await check_subscription(user_id, context):
                    channels = get_setting("subscription.channels")
                    channels_text = "\n".join([f"• {ch}" for ch in channels])
                    
                    keyboard = ReplyKeyboardMarkup([
                        ["✅ تحقق من الاشتراك"],
                        ["🏠 الرئيسية"]
                    ], resize_keyboard=True)
                    
                    await update.message.reply_text(
                        f"{get_setting('subscription.message')}\n\n"
                        f"القنوات المطلوبة:\n{channels_text}",
                        reply_markup=keyboard
                    )
                    return
            
            await update.message.reply_text(
                "مرحباً مرة أخرى! 👋\n"
                "اختر من القائمة أدناه:",
                reply_markup=main_user_keyboard()
            )
        else:
            await update.message.reply_text("⏳ طلبك قيد المراجعة من قبل المدير...")
    else:
        # إضافة مستخدم جديد
        user_data = {
            "username": update.effective_user.username,
            "first_name": update.effective_user.first_name,
            "join_date": datetime.now().isoformat(),
            "approved": False
        }
        users[user_id] = user_data
        write_json(USERS_FILE, users)
        
        # إضافة طلب انضمام
        request_data = {
            "user_id": user_id,
            "username": user_data["username"],
            "first_name": user_data["first_name"],
            "date": datetime.now().isoformat()
        }
        requests.append(request_data)
        write_json(REQUESTS_FILE, requests)
        
        # إشعار المديرين
        for admin_id in ADMIN_IDS:
            try:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ قبول", callback_data=f"accept_{user_id}"),
                     InlineKeyboardButton("❌ رفض", callback_data=f"reject_{user_id}")],
                    [InlineKeyboardButton("📋 طلبات الانضمام", callback_data="view_requests")]
                ])
                
                await context.bot.send_message(
                    admin_id,
                    f"📥 طلب انضمام جديد!\n\n"
                    f"👤 الاسم: {user_data['first_name']}\n"
                    f"🆔 الآيدي: {user_id}\n"
                    f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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
    user_id = str(update.effective_user.id)
    text = update.message.text
    
    if user_id in ADMIN_IDS:
        # أوامر المدير
        if text == "👑 لوحة التحكم":
            await show_admin_dashboard(update, context)
        elif text == "👥 إدارة المستخدمين":
            await show_user_management(update, context)
        elif text == "📋 طلبات الانضمام":
            await show_join_requests(update, context)
        elif text == "👀 عرض المستخدمين":
            await show_all_users(update, context)
        elif text == "📝 إدارة الأقسام":
            await show_categories_management(update, context)
        elif text == "🎭 إدارة المحتوى":
            await show_content_management(update, context)
        elif text == "📢 الاشتراك الإجباري":
            await show_subscription_management(update, context)
        elif text == "📊 الإحصائيات":
            await show_statistics(update, context)
        elif text == "📂 الأقسام":
            await show_categories_to_user(update, context)
        elif text == "🏠 الرئيسية":
            await update.message.reply_text("🏠 الرئيسية", reply_markup=admin_main_keyboard())
    else:
        # أوامر المستخدم العادي
        if text == "📂 الأقسام":
            await show_categories_to_user(update, context)
        elif text == "👤 الملف الشخصي":
            await show_user_profile(update, context)
        elif text == "ℹ️ المساعدة":
            await update.message.reply_text(get_setting("responses.help"))
        elif text == "✅ تحقق من الاشتراك":
            if await check_subscription(user_id, context):
                await update.message.reply_text(
                    "✅ تم التحقق من اشتراكك بنجاح!\n"
                    "يمكنك الآن استخدام البوت.",
                    reply_markup=main_user_keyboard()
                )
            else:
                channels = get_setting("subscription.channels")
                channels_text = "\n".join([f"• {ch}" for ch in channels])
                await update.message.reply_text(
                    f"❌ لم يتم التحقق من اشتراكك بعد!\n\n"
                    f"يجب الاشتراك في:\n{channels_text}"
                )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = str(update.effective_user.id)
    
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
    requests = read_json(REQUESTS_FILE)
    
    active_users = len([u for u in users.values() if u.get('approved', False)])
    pending_requests = len(requests)
    categories_count = len(content.get('categories', []))
    content_count = len(content.get('content', []))
    
    stats_text = (
        "👑 لوحة تحكم المدير\n\n"
        f"📊 الإحصائيات:\n"
        f"• 👥 المستخدمين النشطين: {active_users}\n"
        f"• ⏳ الطلبات المعلقة: {pending_requests}\n"
        f"• 📂 الأقسام: {categories_count}\n"
        f"• 🎭 المحتوى: {content_count}\n\n"
        f"اختر من القائمة أدناه للإدارة:"
    )
    
    await update.message.reply_text(stats_text, reply_markup=admin_main_keyboard())

async def show_user_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "👥 إدارة المستخدمين\n\n"
        "يمكنك من هنا:\n"
        "• 📋 عرض طلبات الانضمام\n"
        "• 👀 عرض جميع المستخدمين\n"
        "• 🗑️ حذف مستخدم\n"
        "• 🔔 تفعيل/إلغاء نظام الطلبات"
    )
    
    await update.message.reply_text(text, reply_markup=user_management_keyboard())

async def show_join_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    requests = read_json(REQUESTS_FILE)
    
    if not requests:
        await update.message.reply_text("📭 لا توجد طلبات انضمام معلقة.")
        return
    
    text = "📋 طلبات الانضمام المعلقة:\n\n"
    for req in requests:
        text += f"👤 {req['first_name']} (@{req['username']})\n🆔 {req['user_id']}\n📅 {req['date'][:10]}\n"
        text += "────────────\n"
    
    await update.message.reply_text(text, reply_markup=user_management_keyboard())

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    active_users = {uid: data for uid, data in users.items() if data.get('approved', False)}
    
    if not active_users:
        await update.message.reply_text("👥 لا يوجد مستخدمين نشطين.")
        return
    
    text = f"👥 جميع المستخدمين ({len(active_users)}):\n\n"
    for user_id, user_data in list(active_users.items())[:50]:  # عرض أول 50 مستخدم فقط
        text += f"👤 {user_data['first_name']} (@{user_data['username']})\n🆔 {user_id}\n📅 {user_data['join_date'][:10]}\n"
        text += "────────────\n"
    
    if len(active_users) > 50:
        text += f"\n... وعرض {len(active_users) - 50} مستخدم آخر"
    
    await update.message.reply_text(text, reply_markup=user_management_keyboard())

async def accept_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    
    if target_user_id in users:
        users[target_user_id]["approved"] = True
        write_json(USERS_FILE, users)
        
        # إزالة من طلبات الانضمام
        requests = [r for r in requests if r['user_id'] != target_user_id]
        write_json(REQUESTS_FILE, requests)
        
        # إرسال رسالة للمستخدم
        try:
            welcome_msg = get_setting("responses.welcome")
            await context.bot.send_message(int(target_user_id), welcome_msg)
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        await update.callback_query.edit_message_text(f"✅ تم قبول المستخدم: {users[target_user_id]['first_name']}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: str):
    users = read_json(USERS_FILE)
    requests = read_json(REQUESTS_FILE)
    
    if target_user_id in users:
        user_name = users[target_user_id]['first_name']
        del users[target_user_id]
        write_json(USERS_FILE, users)
        
        # إزالة من طلبات الانضمام
        requests = [r for r in requests if r['user_id'] != target_user_id]
        write_json(REQUESTS_FILE, requests)
        
        # إرسال رسالة للمستخدم
        try:
            rejected_msg = get_setting("responses.rejected")
            await context.bot.send_message(int(target_user_id), rejected_msg)
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
        
        await update.callback_query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")
    else:
        await update.callback_query.edit_message_text("❌ المستخدم غير موجود")

# إدارة الأقسام
async def show_categories_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    text = "📝 إدارة الأقسام\n\n"
    if categories:
        text += "الأقسام الحالية:\n"
        for cat in categories:
            text += f"• {cat.get('icon', '📁')} {cat.get('name', 'بدون اسم')} (ID: {cat.get('id', 'N/A')})\n"
    else:
        text += "لا توجد أقسام حالياً.\n"
    
    text += "\nاختر من القائمة:"
    await update.message.reply_text(text, reply_markup=categories_management_keyboard())

async def show_categories_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    content = read_json(CONTENT_FILE)
    categories = content.get("categories", [])
    
    if not categories:
        await update.message.reply_text("📭 لا توجد أقسام متاحة حالياً.")
        return
    
    keyboard = []
    for cat in categories:
        keyboard.append([f"{cat.get('icon', '📁')} {cat.get('name', 'بدون اسم')}"])
    
    keyboard.append(["🏠 الرئيسية"])
    
    await update.message.reply_text(
        "📂 الأقسام المتاحة:\nاختر القسم الذي تريد تصفحه:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# إدارة المحتوى
async def show_content_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🎭 إدارة المحتوى\n\n"
        "يمكنك من هنا:\n"
        "• ➕ إضافة محتوى جديد\n"
        "• 🗑️ حذف محتوى\n"
        "• ✏️ تعديل محتوى\n"
        "• 📋 عرض جميع المحتوى"
    )
    
    await update.message.reply_text(text, reply_markup=content_management_keyboard())

async def show_subscription_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    enabled = "✅ مفعل" if get_setting("subscription.enabled") else "❌ معطل"
    channels = get_setting("subscription.channels")
    
    text = (
        "📢 إدارة الاشتراك الإجباري\n\n"
        f"الحالة: {enabled}\n"
        f"عدد القنوات: {len(channels)}\n"
        f"الرسالة: {get_setting('subscription.message')}\n\n"
        "اختر الإجراء:"
    )
    
    await update.message.reply_text(text, reply_markup=subscription_management_keyboard())

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = read_json(USERS_FILE)
    content = read_json(CONTENT_FILE)
    requests = read_json(REQUESTS_FILE)
    
    active_users = len([u for u in users.values() if u.get('approved', False)])
    total_users = len(users)
    pending_requests = len(requests)
    categories_count = len(content.get('categories', []))
    content_count = len(content.get('content', []))
    
    text = (
        "📊 الإحصائيات التفصيلية\n\n"
        f"👥 المستخدمين:\n"
        f"• النشطين: {active_users}\n"
        f"• الإجمالي: {total_users}\n"
        f"• الطلبات المعلقة: {pending_requests}\n\n"
        f"🎭 المحتوى:\n"
        f"• الأقسام: {categories_count}\n"
        f"• العناصر: {content_count}\n\n"
        f"⚙️ الإعدادات:\n"
        f"• الاشتراك الإجباري: {'✅' if get_setting('subscription.enabled') else '❌'}\n"
        f"• التحويل: {'✅' if get_setting('forwarding.enabled') else '❌'}"
    )
    
    await update.message.reply_text(text, reply_markup=admin_main_keyboard())

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    users = read_json(USERS_FILE)
    
    if user_id in users:
        user_data = users[user_id]
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

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.", reply_markup=admin_main_keyboard())
    return ConversationHandler.END

def main():
    # تهيئة البيانات
    init_data()
    
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
