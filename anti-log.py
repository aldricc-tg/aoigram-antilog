import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from telethon import TelegramClient
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.errors import SessionPasswordNeededError

# ==================== KONFIGURASI UTAMA ====================
BOT_TOKEN = '8646773334:AAEW9z8KozhxMMz67HpKrVgwXwdtXnTbmhE'          # Token Bot Telegram Utama
API_ID = 38159111                      # API ID dari my.telegram.org
API_HASH = 'c8314564639096716b7ade4992b33870'            # API HASH dari my.telegram.org
BANNER_IMAGE = "https://files.catbox.moe/tv97vi.jpg" 
# ====================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Database Penyimpanan Senter (In-Memory untuk contoh, gunakan Database untuk produksi)
# Format: { phone: { "client": TelethonClient, "active": True, "whitelist": [hash1, hash2], "name": ... } }
MANAGED_ACCOUNTS = {}

# State FSM untuk Registrasi Akun
class RegState(StatesGroup):
    waiting_phone = State()
    waiting_otp = State()
    waiting_password = State()

# ==================== KEYBOARDS UTAMA ====================

def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Tambah Akun", callback_data="acc_add"),
         InlineKeyboardButton(text="🟢 Kelola Akun", callback_data="acc_manage")],
        [InlineKeyboardButton(text="🛡️ Whitelist Perangkat", callback_data="acc_whitelist"),
         InlineKeyboardButton(text="🔄 Reconnect Massal", callback_data="acc_reconnect")],
        [InlineKeyboardButton(text="📢 Channel & 🛠️ Support", callback_data="menu_info")]
    ])

# ==================== HANDLER /START ====================

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    caption = (
        "✨ **P A N E L • A N T I - L O G • P R O** ✨\n"
        "───────────────────────────────\n"
        "🛡️ Sistem perlindungan akun Telegram tingkat lanjut.\n\n"
        f"📊 **Total Akun Diproteksi:** `{len(MANAGED_ACCOUNTS)} Akun`\n\n"
        "Silakan pilih menu di bawah ini:"
    )
    await message.answer_photo(photo=BANNER_IMAGE, caption=caption, reply_markup=main_menu_kb(), parse_mode="Markdown")

# ==================== FITUR 1: TAMBAH AKUN (REGISTER) ====================

@dp.callback_query(F.data == "acc_add")
async def start_add_account(callback: CallbackQuery, state: FSMContext):
    caption = (
        "➕ **T A M B A H • A K U N** ➕\n"
        "───────────────────────────────\n"
        "Silakan ketik dan kirim **Nomor Telepon** Telegram yang ingin diproteksi:\n\n"
        "_Contoh: +6281234567890_"
    )
    await callback.message.edit_caption(
        caption=caption,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Batal", callback_data="main_menu")]]),
        parse_mode="Markdown"
    )
    await state.set_state(RegState.waiting_phone)
    await callback.answer()

@dp.message(RegState.waiting_phone)
async def get_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    session_name = f"session_{phone.replace('+', '')}"
    
    client = TelegramClient(session_name, API_ID, API_HASH)
    await client.connect()
    
    try:
        sent = await client.send_code_request(phone)
        await state.update_data(phone=phone, session=session_name, hash=sent.phone_code_hash, client=client)
        
        await message.answer(
            f"🔑 **KODE OTP DIKIRIM KE `{phone}`**\n\n"
            "Silakan ketik dan kirim kode OTP yang masuk ke Telegram Anda:",
            parse_mode="Markdown"
        )
        await state.set_state(RegState.waiting_otp)
    except Exception as e:
        await message.answer(f"❌ Gagal mengirim OTP: `{e}`\nKetik /start untuk mengulang.")
        await state.clear()
        await client.disconnect()

@dp.message(RegState.waiting_otp)
async def get_otp(message: Message, state: FSMContext):
    otp = message.text.strip().replace(" ", "")
    data = await state.get_data()
    client: TelegramClient = data["client"]
    
    try:
        await client.sign_in(phone=data["phone"], code=otp, phone_code_hash=data["hash"])
        await finalize_account_login(message, data, state)
    except SessionPasswordNeededError:
        await message.answer(
            "🔒 **VERIFIKASI 2FA DIPERLUKAN**\n\n"
            "Akun ini menggunakan Password Cloud (2FA). Silakan ketik password Anda:",
            parse_mode="Markdown"
        )
        await state.set_state(RegState.waiting_password)
    except Exception as e:
        await message.answer(f"❌ OTP Salah atau Error: `{e}`\nSilakan ulangi dari /start.")
        await state.clear()
        await client.disconnect()

@dp.message(RegState.waiting_password)
async def get_password(message: Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    client: TelegramClient = data["client"]
    
    try:
        await client.sign_in(password=password)
        await finalize_account_login(message, data, state)
    except Exception as e:
        await message.answer(f"❌ Password 2FA Salah: `{e}`\nSilakan ulangi dari /start.")
        await state.clear()
        await client.disconnect()

async def finalize_account_login(message: Message, data: dict, state: FSMContext):
    phone = data["phone"]
    client = data["client"]
    
    # Simpan ke Database Global Managed Accounts
    MANAGED_ACCOUNTS[phone] = {
        "client": client,
        "active": True,
        "whitelist": [],
        "session": data["session"]
    }
    
    # Jalankan background monitoring worker untuk akun ini
    asyncio.create_task(background_account_guard(phone))
    
    await message.answer(
        f"🎉 **BERHASIL TERDAFTAR!**\n\n"
        f"Akun `{phone}` kini resmi diproteksi sistem anti-log 24/7.\n"
        "Ketik /start untuk kembali ke menu utama.",
        parse_mode="Markdown"
    )
    await state.clear()

# ==================== FITUR 2 & 4: KELOLA AKUN & TOGGLE ON/OFF ====================

@dp.callback_query(F.data == "acc_manage")
async def menu_manage_accounts(callback: CallbackQuery):
    if not MANAGED_ACCOUNTS:
        caption = "📂 **KELOLA AKUN**\n\nBelum ada akun yang terdaftar di sistem."
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Kembali", callback_data="main_menu")]])
    else:
        caption = "🟢 **DAFTAR AKUN & KONTROL STATUS**\n\nKlik tombol di bawah untuk mengubah status ON/OFF atau menghapus akun:"
        buttons = []
        for phone, info in MANAGED_ACCOUNTS.items():
            status = "🟢 ON" if info["active"] else "🔴 OFF"
            buttons.append([
                InlineKeyboardButton(text=f"{phone} [{status}]", callback_data=f"toggle_{phone}"),
                InlineKeyboardButton(text="🗑️ Hapus", callback_data=f"del_{phone}")
            ])
        buttons.append([InlineKeyboardButton(text="🔙 Kembali ke Menu Utama", callback_data="main_menu")])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        
    await callback.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_account(callback: CallbackQuery):
    phone = callback.data.replace("toggle_", "")
    if phone in MANAGED_ACCOUNTS:
        MANAGED_ACCOUNTS[phone]["active"] = not MANAGED_ACCOUNTS[phone]["active"]
        state_text = "diaktifkan (ON)" if MANAGED_ACCOUNTS[phone]["active"] else "dimatikan (OFF)"
        await callback.answer(f"Proteksi akun {phone} berhasil {state_text}!")
        await menu_manage_accounts(callback)

@dp.callback_query(F.data.startswith("del_"))
async def delete_account(callback: CallbackQuery):
    phone = callback.data.replace("del_", "")
    if phone in MANAGED_ACCOUNTS:
        try:
            await MANAGED_ACCOUNTS[phone]["client"].disconnect()
        except:
            pass
        del MANAGED_ACCOUNTS[phone]
        await callback.answer(f"Akun {phone} berhasil dihapus dari sistem.")
        await menu_manage_accounts(callback)

# ==================== FITUR 3: WHITELIST PERANGKAT (SESSION INSPECTOR) ====================

@dp.callback_query(F.data == "acc_whitelist")
async def menu_whitelist_list(callback: CallbackQuery):
    if not MANAGED_ACCOUNTS:
        await callback.answer("Belum ada akun terdaftar!", show_alert=True)
        return
        
    caption = "🛡️ **WHISHLIST PERANGKAT TEPERCAYA**\n\nPilih akun untuk melihat perangkat aktif dan atur whitelist:"
    buttons = []
    for phone in MANAGED_ACCOUNTS.keys():
        buttons.append([InlineKeyboardButton(text=f"📱 Cek Sesi: {phone}", callback_data=f"sessions_{phone}")])
    buttons.append([InlineKeyboardButton(text="🔙 Kembali", callback_data="main_menu")])
    
    await callback.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("sessions_"))
async def view_account_sessions(callback: CallbackQuery):
    phone = callback.data.replace("sessions_", "")
    acc = MANAGED_ACCOUNTS.get(phone)
    
    if not acc:
        await callback.answer("Akun tidak ditemukan.", show_alert=True)
        return
        
    try:
        auths = await acc["client"](GetAuthorizationsRequest())
        caption = f"📱 **PERANGKAT AKTIF: `{phone}`**\n───────────────────────────────\n"
        buttons = []
        
        for s in auths.authorizations:
            is_whitelisted = s.hash in acc["whitelist"]
            w_label = "⭐ [WHITELISTED]" if is_whitelisted else "🔒 [STANDARD]"
            caption += f"• `{s.device_model}` ({s.platform})\n  IP: `{s.ip}` | {w_label}\n\n"
            
            # Tombol untuk whitelist / unwhitelist
            action_data = f"unwhite_{phone}_{s.hash}" if is_whitelisted else f"white_{phone}_{s.hash}"
            action_text = f"❌ Hapus Whitelist ({s.device_model[:10]})" if is_whitelisted else f"⭐ Jadikan Whitelist ({s.device_model[:10]})"
            buttons.append([InlineKeyboardButton(text=action_text, callback_data=action_data)])
            
        buttons.append([InlineKeyboardButton(text="🔙 Kembali", callback_data="acc_whitelist")])
        await callback.message.edit_caption(caption=caption, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")
    except Exception as e:
        await callback.answer(f"Gagal memuat sesi: {e}", show_alert=True)

@dp.callback_query(F.data.startswith(("white_", "unwhite_")))
async def modify_whitelist(callback: CallbackQuery):
    parts = callback.data.split("_", 2)
    action, phone, session_hash = parts[0], parts[1], int(parts[2]) if parts[2].isdigit() else parts[2]
    
    if phone in MANAGED_ACCOUNTS:
        if action == "white":
            if session_hash not in MANAGED_ACCOUNTS[phone]["whitelist"]:
                MANAGED_ACCOUNTS[phone]["whitelist"].append(session_hash)
            await callback.answer("Perangkat berhasil dimasukkan ke Whitelist!")
        else:
            if session_hash in MANAGED_ACCOUNTS[phone]["whitelist"]:
                MANAGED_ACCOUNTS[phone]["whitelist"].remove(session_hash)
            await callback.answer("Perangkat dihapus dari Whitelist!")
            
        # Refresh view
        callback.data = f"sessions_{phone}"
        await view_account_sessions(callback)

# ==================== FITUR 4B: RECONNECT MASSAL ====================

@dp.callback_query(F.data == "acc_reconnect")
async def reconnect_all_accounts(callback: CallbackQuery):
    count = 0
    for phone, acc in MANAGED_ACCOUNTS.items():
        try:
            if not acc["client"].is_connected():
                await acc["client"].connect()
            count += 1
        except:
            pass
    await callback.answer(f"Berhasil menyambungkan ulang {count} akun ke peladen Telegram!", show_alert=True)

# ==================== BACKGROUND MONITORING GUARD ====================

async def background_account_guard(phone: str):
    """Worker latar belakang untuk proteksi anti-log otomatis per akun"""
    while phone in MANAGED_ACCOUNTS:
        acc = MANAGED_ACCOUNTS.get(phone)
        # Jika akun aktif di-ON-kan oleh owner
        if acc and acc["active"]:
            try:
                auths = await acc["client"](GetAuthorizationsRequest())
                for s in auths.authorizations:
                    # Jika bukan sesi saat ini DAN tidak masuk dalam whitelist
                    if not s.current and s.hash not in acc["whitelist"]:
                        # Otomatis terminate sesi asing!
                        await acc["client"](ResetAuthorizationRequest(hash=s.hash))
                        
                        # Kirim Notifikasi Rich Aesthetic ke Admin
                        alert_msg = (
                            "✨ **S Y S T E M  •  S E C U R I T Y** ✨\n"
                            f"🏷️ **Target Akun:** `{phone}`\n"
                            "───────────────────────────────\n"
                            "🛡️ *Status:* `UNAUTHORIZED LOGIN BLOCKED`\n\n"
                            "╭─────────────────────────────╮\n"
                            f"│ 📱 **Device**  : `{s.device_model} ({s.platform})`\n"
                            f"│ 🌐 **IP Address** : `{s.ip}`\n"
                            f"│ 📍 **Location** : `{s.country}`\n"
                            f"│ ⚡ **Action**   : `AUTO-TERMINATED`\n"
                            "╰─────────────────────────────╯"
                        )
                        # Kirim ke chat room pemilik bot (bisa diatur ke chat_id Anda)
                        # await bot.send_message(ADMIN_CHAT_ID, alert_msg, parse_mode="Markdown")
            except Exception:
                pass
        
        # Cek berkala setiap 15 detik
        await asyncio.sleep(15)

# ==================== MENU INFO & SUPPORT ====================

@dp.callback_query(F.data == "menu_info")
async def menu_info(callback: CallbackQuery):
    caption = (
        "📢 **C H A N N E L  &  S U P P O R T** 🛠️\n"
        "───────────────────────────────\n"
        "• Channel Resmi: [Klik Disini](https://t.me/your_channel)\n"
        "• Customer Service: [Hubungi Admin](https://t.me/your_admin)\n\n"
        "💎 *Bot Anti-Login Pro v3.0 - All Rights Reserved*"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Kembali", callback_data="main_menu")]])
    await callback.message.edit_caption(caption=caption, reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "main_menu")
async def back_to_main(callback: CallbackQuery):
    caption = (
        "✨ **P A N E L • A N T I - L O G • P R O** ✨\n"
        "───────────────────────────────\n"
        "🛡️ Sistem perlindungan akun Telegram tingkat lanjut.\n\n"
        f"📊 **Total Akun Diproteksi:** `{len(MANAGED_ACCOUNTS)} Akun`\n\n"
        "Silakan pilih menu di bawah ini:"
    )
    await callback.message.edit_caption(caption=caption, reply_markup=main_menu_kb(), parse_mode="Markdown")
    await callback.answer()

# ==================== MAIN RUNNER ====================

async def main():
    print("========================================")
    print("  BOT ANTI-LOGIN PRO PANEL BERJALAN!   ")
    print("========================================")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())