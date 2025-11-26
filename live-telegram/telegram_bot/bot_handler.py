"""
Telegram Bot Command Handler
Handles /start, /subscribe, /unsubscribe, /status, /trade commands
"""
import os
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Show chat ID"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    message = f"""
🤖 **QuantTrade Bot**

Hoş geldiniz {user.first_name}!

📋 **Bilgileriniz:**
• Chat ID: `{chat_id}`
• Kullanıcı Adı: @{user.username or 'N/A'}
• İsim: {user.first_name} {user.last_name or ''}

📌 **Abone olmak için:**
Admin'e şu bilgileri iletin ya da `/subscribe` komutunu kullanın.

💡 **Komutlar:**
/start - Bu mesajı göster
/subscribe - Otomatik abone ol
/unsubscribe - Aboneliği iptal et
/status - Abone durumunu göster
    """
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /subscribe command - Auto subscribe user"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # Try to add subscriber via backend API
    try:
        response = requests.post(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            json={
                "name": f"{user.first_name} {user.last_name or ''}".strip(),
                "chat_id": str(chat_id),
                "role": "Trader"
            },
            timeout=10
        )
        
        if response.ok:
            await update.message.reply_text(
                "✅ Başarıyla abone oldunuz!\n\n"
                "Artık günlük trading sinyallerini alacaksınız. 📈"
            )
        else:
            await update.message.reply_text(
                "⚠️ Abone olurken bir hata oluştu.\n\n"
                f"Lütfen admin ile iletişime geçin.\nChat ID: `{chat_id}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        print(f"Error subscribing user: {e}")
        await update.message.reply_text(
            "❌ Backend'e bağlanılamadı.\n\n"
            f"Manuel eklemek için Chat ID: `{chat_id}`",
            parse_mode='Markdown'
        )


async def unsubscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /unsubscribe command - Deactivate subscription"""
    chat_id = update.effective_chat.id
    
    try:
        # Get all subscribers
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            timeout=10
        )
        
        if response.ok:
            subscribers = response.json()
            user_sub = next((s for s in subscribers if s['chat_id'] == str(chat_id)), None)
            
            if user_sub:
                # Deactivate user
                update_response = requests.put(
                    f"{BACKEND_API_URL}/api/telegram/subscribers/{user_sub['id']}",
                    json={"active": False},
                    timeout=10
                )
                
                if update_response.ok:
                    await update.message.reply_text(
                        "✅ Aboneliğiniz iptal edildi.\n\n"
                        "Tekrar abone olmak için /subscribe kullanın."
                    )
                else:
                    await update.message.reply_text("⚠️ Abonelik iptal edilemedi.")
            else:
                await update.message.reply_text(
                    "ℹ️ Zaten abone değilsiniz.\n\n"
                    "Abone olmak için /subscribe kullanın."
                )
        else:
            await update.message.reply_text("⚠️ Sunucuya bağlanılamadı.")
            
    except Exception as e:
        print(f"Error unsubscribing user: {e}")
        await update.message.reply_text("❌ Bir hata oluştu.")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command - Show subscription status"""
    chat_id = update.effective_chat.id
    
    try:
        response = requests.get(
            f"{BACKEND_API_URL}/api/telegram/subscribers",
            timeout=10
        )
        
        if response.ok:
            subscribers = response.json()
            user_sub = next((s for s in subscribers if s['chat_id'] == str(chat_id)), None)
            
            if user_sub:
                status_emoji = "✅" if user_sub['active'] else "⏸"
                status_text = "Aktif" if user_sub['active'] else "Pasif"
                
                message = f"""
📊 **Abonelik Durumunuz**

{status_emoji} Durum: **{status_text}**
👤 İsim: {user_sub['name']}
🏷 Rol: {user_sub['role']}
💬 Chat ID: `{chat_id}`
                """
                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(
                    "ℹ️ Abone değilsiniz.\n\n"
                    f"Chat ID: `{chat_id}`\n"
                    "Abone olmak için /subscribe kullanın.",
                    parse_mode='Markdown'
                )
        else:
            await update.message.reply_text("⚠️ Durum sorgulanamadı.")
            
    except Exception as e:
        print(f"Error checking status: {e}")
        await update.message.reply_text("❌ Bir hata oluştu.")


async def broadcast_message(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Broadcasts a message to all active subscribers."""
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/telegram/subscribers", timeout=10)
        if response.ok:
            subscribers = response.json()
            for sub in subscribers:
                if sub.get("active"):
                    try:
                        await context.bot.send_message(chat_id=sub["chat_id"], text=message, parse_mode='Markdown')
                    except Exception as e:
                        print(f"Error sending message to {sub['chat_id']}: {e}")
        else:
            print(f"Error fetching subscribers for broadcast: {response.status_code}")
    except Exception as e:
        print(f"Error in broadcast_message: {e}")


async def trade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /trade - Run portfolio analysis (Admin only)
    Executes live_portfolio_manager.py and broadcasts summary to all subscribers
    """
    chat_id = update.effective_chat.id
    
    # Get subscriber info
    try:
        response = requests.get(f"{BACKEND_API_URL}/api/telegram/subscribers", timeout=10)
        if not response.ok:
            await update.message.reply_text("❌ Subscriber bilgisi alınamadı")
            return
        
        subscribers = response.json()
        user_sub = next((s for s in subscribers if s["chat_id"] == str(chat_id)), None)
        
        if not user_sub or user_sub.get("role") != "Admin":
            await update.message.reply_text("❌ Bu komutu sadece Admin kullanabilir")
            return
    except Exception as e:
        print(f"Error checking permissions: {e}")
        await update.message.reply_text("❌ Yetki kontrolünde hata")
        return
    
    await update.message.reply_text("🚀 Portfolio analizi başlatılıyor...")
    
    try:
        # Get portfolio script path
        script_dir = Path(__file__).parent
        project_root = script_dir.parent.parent
        portfolio_script = project_root / "src" / "quanttrade" / "models_2.0" / "live_portfolio_manager.py"
        
        if not portfolio_script.exists():
            summary = f"❌ Portfolio manager script bulunamadı"
            await broadcast_message(context, summary)
            return
        
        # Run live_portfolio_manager.py
        result = subprocess.run(
            [sys.executable, str(portfolio_script)],
            cwd=str(portfolio_script.parent),
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            # Success - send output
            summary = f"✅ Live Portfolio Manager\n\n{result.stdout}"
        else:
            # Error
            summary = f"❌ Portfolio Manager Hatası\n\n{result.stdout}"
        
        # Broadcast to all active subscribers
        await broadcast_message(context, summary)
        
    except subprocess.TimeoutExpired:
        summary = "❌ Portfolio analizi timeout (5 dakika+)"
        await broadcast_message(context, summary)
    except Exception as e:
        summary = f"❌ Portfolio analizi başarısız: {str(e)}"
        await broadcast_message(context, summary)


def main():
    """Start the bot"""
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
    
    print("🤖 QuantTrade Bot başlatılıyor...")
    print(f"📡 Backend: {BACKEND_API_URL}")
    
    # Create application
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("subscribe", subscribe_command))
    application.add_handler(CommandHandler("unsubscribe", unsubscribe_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(CommandHandler("trade", trade_command))
    
    print("✅ Bot hazır! Komutlar dinleniyor...")
    print("\n💡 Kullanılabilir komutlar:")
    print("   /start - Bot bilgisi ve Chat ID")
    print("   /subscribe - Otomatik abone ol")
    print("   /unsubscribe - Aboneliği iptal et")
    print("   /status - Abone durumu")
    print("   /trade - Portfolio analizi çalıştır (Admin)")
    print("\n🔄 Bot çalışıyor... (Durdurmak için Ctrl+C)")
    
    # Start polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
