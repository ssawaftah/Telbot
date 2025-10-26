import os
import json
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from datetime import datetime
import sqlite3

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# بيانات البوت
BOT_TOKEN = "8240559018:AAEGsGl-pKEPM3kCenefbE4DfLMQ1Ci586g"
ADMIN_IDS = []  # سيتم إضافة آيدي المدير تلقائياً

# حالات المحادثة
ADD_CATEGORY, ADD_CONTENT_TITLE, ADD_CONTENT, ADD_CONTENT_CATEGORY = range(4)

# تهيئة قاعدة البيانات
def init_database():
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    
    # جدول المستخدمين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            join_date TEXT,
            approved INTEGER DEFAULT 0,
            subscribed INTEGER DEFAULT 0
        )
    ''')
    
    # جدول الأقسام
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            icon TEXT,
            created_date TEXT
        )
    ''')
    
    # جدول المحتوى
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content_type TEXT,
            file_id TEXT,
            text_content TEXT,
            category_id INTEGER,
            created_date TEXT,
            FOREIGN KEY (category_id) REFERENCES categories (id)
        )
    ''')
    
    # جدول الإعدادات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # إعدادات افتراضية
    default_settings = [
        ('subscription_enabled', 'false'),
        ('subscription_channels', '[]'),
        ('subscription_message', 'يجب الاشتراك في القناة أولاً!'),
        ('welcome_message', 'مرحباً! تم قبول طلبك.'),
        ('rejected_message', 'تم رفض طلبك. تواصل مع المدير.'),
        ('forwarding_enabled', 'false')
    ]
    
    cursor.executemany('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', default_settings)
    conn.commit()
    conn.close()

# وظائف قاعدة البيانات
def get_db_connection():
    return sqlite3.connect('bot_data.db')

def get_setting(key):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_setting(key, value):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
    conn.commit()
    conn.close()

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
        ["💾 النسخ الاحتياطي", "🔧 الإعدادات"]
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

# أوامر البوت الرئيسية
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # إذا كان المدير
    if not ADMIN_IDS:
        ADMIN_IDS.append(user_id)
        await update.message.reply_text(
            "👑 تم تعيينك كمدير للبوت!\n\n"
            "يمكنك الآن استخدام لوحة التحكم للإدارة الكاملة للبوت.",
            reply_markup=admin_main_keyboard()
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # التحقق إذا كان المستخدم موجوداً
    cursor.execute('SELECT approved FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    
    if user:
        if user[0]:  # إذا كان مفعل
            # التحقق من الاشتراك الإجباري
            if get_setting('subscription_enabled') == 'true':
                if not await check_subscription(user_id, context):
                    channels = json.loads(get_setting('subscription_channels'))
                    channels_text = "\n".join([f"• {ch}" for ch in channels])
                    
                    keyboard = ReplyKeyboardMarkup([
                        ["✅ تحقق من الاشتراك"],
                        ["🏠 الرئيسية"]
                    ], resize_keyboard=True)
                    
                    await update.message.reply_text(
                        f"{get_setting('subscription_message')}\n\n"
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
        cursor.execute(
            'INSERT INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)',
            (user_id, update.effective_user.username, update.effective_user.first_name, datetime.now().isoformat())
        )
        conn.commit()
        
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
                    f"👤 الاسم: {update.effective_user.first_name}\n"
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
    
    conn.close()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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
        elif text == "➕ إضافة محتوى":
            await start_add_content(update, context)
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
            await update.message.reply_text("ℹ️ للمساعدة، تواصل مع مدير البوت.")
        elif text == "✅ تحقق من الاشتراك":
            if await check_subscription(user_id, context):
                await update.message.reply_text(
                    "✅ تم التحقق من اشتراكك بنجاح!\n"
                    "يمكنك الآن استخدام البوت.",
                    reply_markup=main_user_keyboard()
                )
            else:
                channels = json.loads(get_setting('subscription_channels'))
                channels_text = "\n".join([f"• {ch}" for ch in channels])
                await update.message.reply_text(
                    f"❌ لم يتم التحقق من اشتراكك بعد!\n\n"
                    f"يجب الاشتراك في:\n{channels_text}"
                )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    user_id = update.effective_user.id
    
    if data.startswith("accept_"):
        target_user = int(data.split("_")[1])
        await accept_user(update, context, target_user)
    elif data.startswith("reject_"):
        target_user = int(data.split("_")[1])
        await reject_user(update, context, target_user)
    elif data == "view_requests":
        await show_join_requests(update, context)

# وظائف المدير
async def show_admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # الإحصائيات
    cursor.execute('SELECT COUNT(*) FROM users WHERE approved = 1')
    active_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE approved = 0')
    pending_requests = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM categories')
    categories_count = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM content')
    content_count = cursor.fetchone()[0]
    
    conn.close()
    
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, join_date FROM users WHERE approved = 0')
    requests = cursor.fetchall()
    conn.close()
    
    if not requests:
        await update.message.reply_text("📭 لا توجد طلبات انضمام معلقة.")
        return
    
    text = "📋 طلبات الانضمام المعلقة:\n\n"
    for req in requests:
        text += f"👤 {req[2]} (@{req[1]})\n🆔 {req[0]}\n📅 {req[3][:10]}\n"
        text += "────────────\n"
    
    await update.message.reply_text(text, reply_markup=user_management_keyboard())

async def show_all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, join_date FROM users WHERE approved = 1')
    users = cursor.fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("👥 لا يوجد مستخدمين نشطين.")
        return
    
    text = f"👥 جميع المستخدمين ({len(users)}):\n\n"
    for user in users[:50]:  # عرض أول 50 مستخدم فقط
        text += f"👤 {user[2]} (@{user[1]})\n🆔 {user[0]}\n📅 {user[3][:10]}\n"
        text += "────────────\n"
    
    if len(users) > 50:
        text += f"\n... وعرض {len(users) - 50} مستخدم آخر"
    
    await update.message.reply_text(text, reply_markup=user_management_keyboard())

async def accept_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET approved = 1 WHERE user_id = ?', (target_user_id,))
    conn.commit()
    
    # الحصول على بيانات المستخدم
    cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (target_user_id,))
    user_name = cursor.fetchone()[0]
    conn.close()
    
    # إرسال رسالة للمستخدم
    try:
        welcome_msg = get_setting('welcome_message')
        await context.bot.send_message(target_user_id, welcome_msg)
    except Exception as e:
        logger.error(f"Error sending message to user: {e}")
    
    await update.callback_query.edit_message_text(f"✅ تم قبول المستخدم: {user_name}")

async def reject_user(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # الحصول على بيانات المستخدم قبل الحذف
    cursor.execute('SELECT first_name FROM users WHERE user_id = ?', (target_user_id,))
    user_name = cursor.fetchone()[0]
    
    cursor.execute('DELETE FROM users WHERE user_id = ?', (target_user_id,))
    conn.commit()
    conn.close()
    
    # إرسال رسالة للمستخدم
    try:
        rejected_msg = get_setting('rejected_message')
        await context.bot.send_message(target_user_id, rejected_msg)
    except Exception as e:
        logger.error(f"Error sending message to user: {e}")
    
    await update.callback_query.edit_message_text(f"❌ تم رفض المستخدم: {user_name}")

# إدارة الأقسام
async def show_categories_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, icon FROM categories')
    categories = cursor.fetchall()
    conn.close()
    
    text = "📝 إدارة الأقسام\n\n"
    if categories:
        text += "الأقسام الحالية:\n"
        for cat in categories:
            text += f"• {cat[2]} {cat[1]} (ID: {cat[0]})\n"
    else:
        text += "لا توجد أقسام حالياً.\n"
    
    text += "\nاختر من القائمة:"
    await update.message.reply_text(text, reply_markup=categories_management_keyboard())

async def show_categories_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, icon FROM categories')
    categories = cursor.fetchall()
    conn.close()
    
    if not categories:
        await update.message.reply_text("📭 لا توجد أقسام متاحة حالياً.")
        return
    
    keyboard = []
    for cat in categories:
        keyboard.append([f"{cat[2]} {cat[1]}"])
    
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

async def start_add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📝 إضافة محتوى جديد\n\n"
        "الخطوة 1/3:\n"
        "أرسل عنوان المحتوى:"
    )
    return ADD_CONTENT_TITLE

async def add_content_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['content_title'] = update.message.text
    await update.message.reply_text(
        "الخطوة 2/3:\n"
        "أرسل المحتوى (صورة، فيديو، نص، أو قصة):\n\n"
        "لإنهاء إضافة القصة الطويلة، اكتب /done"
    )
    return ADD_CONTENT

async def add_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # هذه دالة مبسطة - تحتاج لتطوير أكثر
    content_text = update.message.text
    if content_text == '/done':
        await update.message.reply_text("✅ تم حفظ المحتوى بنجاح!")
        return ConversationHandler.END
    
    # حفظ المحتوى مؤقتاً
    context.user_data['content_data'] = content_text
    await update.message.reply_text("الخطوة 3/3: اختر القسم (سيتم تطويره)")
    return ADD_CONTENT_CATEGORY

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username, first_name, join_date, approved FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        text = (
            f"👤 ملفك الشخصي\n\n"
            f"• الاسم: {user[1]}\n"
            f"• المعرف: @{user[0] if user[0] else 'غير متوفر'}\n"
            f"• تاريخ الانضمام: {user[2][:10]}\n"
            f"• الحالة: {'✅ مفعل' if user[3] else '⏳ قيد المراجعة'}"
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
    # تهيئة قاعدة البيانات
    init_database()
    
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة handlers
    application.add_handler(CommandHandler("start", start))
    
    # محادثة إضافة المحتوى
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ إضافة محتوى$"), start_add_content)],
        states={
            ADD_CONTENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content_title)],
            ADD_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content)],
            ADD_CONTENT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_content)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # بدء البوت
    print("🤖 البوت يعمل...")
    application.run_polling()

if __name__ == "__main__":
    main()
