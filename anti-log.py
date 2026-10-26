import asyncio
import logging
import re
from telethon import TelegramClient, events, Button
from telethon.tl.functions.account import GetAuthorizationsRequest, ResetAuthorizationRequest
from telethon.errors import SessionPasswordNeededError

# ==================== KONFIGURASI UTAMA ====================
API_ID = 831456463909                      # Ganti dengan API ID Anda dari my.telegram.org
API_HASH = 'c8314564639096716b7ade4992b33870'            # Ganti dengan API HASH Anda
BOT_TOKEN = '8646773334:AAEW9z8KozhxMMz67HpKrVgwXwdtXnTbmhE'          # Token Bot dari @BotFather
# ====================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Inisialisasi Bot menggunakan Telethon
bot = TelegramClient('bot_panel_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Database penyimpanan akun yang diproteksi & state register sementara
MANAGED_ACCOUNTS = {}
USER_STATES = {}

# ==================== MENU UTAMA ====================
def main_menu_buttons():
    return [
        [Button.inline("➕ Tambah Akun", data="acc_add"), Button.inline("🟢 Kelola Akun", data="acc_manage")],
        [Button.inline("🛡️ Whitelist Perangkat", data="acc_whitelist"), Button.inline("📢 Info & Support", data="menu_info")]
    ]

@bot.on(events.NewMessage(pattern='/start'))
async def cmd_start(event):
    USER_STATES.pop(event.sender_id, None)
    caption = (
        "✨ **P A N E L • A N T I - L O G • P R O** ✨\n"
        "───────────────────────────────\n"
        "🛡️ Sistem perlindungan akun Telegram tingkat lanjut.\n\n"
        f"📊 **Total Akun Diproteksi:** `{len(MANAGED_ACCOUNTS)} Akun`\n\n"
        "Silakan pilih menu di bawah ini:"
    )
    await event.respond(caption, buttons=main_menu_buttons(), parse_mode='md')

# ==================== HANDLER TOMBOL INTERAKTIF ====================
@bot.on(events.CallbackQuery)
async def callback_handler(event):
    data = event.data.decode('utf-8')
    user_id = event.sender_id
    
    if data == "main_menu":
        USER_STATES.pop(user_id, None)
        caption = (
            "✨ **P A N E L • A N T I - L O G • P R O** ✨\n"
            "───────────────────────────────\n"
            "🛡️ Sistem perlindungan akun Telegram tingkat lanjut.\n\n"
            f"📊 **Total Akun Diproteksi:** `{len(MANAGED_ACCOUNTS)} Akun`\n\n"
            "Silakan pilih menu di bawah ini:"
        )
        await event.edit(caption, buttons=main_menu_buttons(), parse_mode='md')

    elif data == "acc_add":
        USER_STATES[user_id] = {"step": "waiting_phone"}
        caption = (
            "➕ **T A M B A H • A K U N** ➕\n"
            "───────────────────────────────\n"
            "Silakan ketik dan kirim **Nomor Telepon** Telegram Anda ke chat ini:\n\n"
            "_Contoh: +6281234567890_"
        )
        await event.edit(caption, buttons=[[Button.inline("🔙 Batal", data="main_menu")]], parse_mode='md')

    elif data == "acc_manage":
        if not MANAGED_ACCOUNTS:
            caption = "🟢 **KELOLA AKUN**\n\nBelum ada akun yang terdaftar di sistem."
            buttons = [[Button.inline("🔙 Kembali", data="main_menu")]]
        else:
            caption = "🟢 **DAFTAR AKUN & KONTROL STATUS**\n\nKlik untuk ubah status ON/OFF atau hapus:"
            buttons = []
            for phone, info in MANAGED_ACCOUNTS.items():
                status = "🟢 ON" if info["active"] else "🔴 OFF"
                buttons.append([
                    Button.inline(f"{phone} [{status}]", data=f"toggle_{phone}"),
                    Button.inline("🗑️ Hapus", data=f"del_{phone}")
                ])
            buttons.append([Button.inline("🔙 Kembali", data="main_menu")])
        await event.edit(caption, buttons=buttons, parse_mode='md')

    elif data.startswith("toggle_"):
        phone = data.replace("toggle_", "")
        if phone in MANAGED_ACCOUNTS:
            MANAGED_ACCOUNTS[phone]["active"] = not MANAGED_ACCOUNTS[phone]["active"]
            await event.answer(f"Status akun {phone} diubah!")
            # Refresh menu manage
            await callback_handler(type('obj', (object,), {'data': b'acc_manage', 'sender_id': user_id, 'edit': event.edit, 'answer': event.answer})())

    elif data.startswith("del_"):
        phone = data.replace("del_", "")
        if phone in MANAGED_ACCOUNTS:
            try:
                await MANAGED_ACCOUNTS[phone]["client"].disconnect()
            except:
                pass
            del MANAGED_ACCOUNTS[phone]
            await event.answer(f"Akun {phone} dihapus.")
            await callback_handler(type('obj', (object,), {'data': b'acc_manage', 'sender_id': user_id, 'edit': event.edit, 'answer': event.answer})())

    elif data == "menu_info":
        caption = (
            "📢 **C H A N N E L  &  S U P P O R T** 🛠️\n"
            "───────────────────────────────\n"
            "• Channel: [Join Channel](https://t.me/your_channel)\n"
            "• Support: [Hubungi Admin](https://t.me/your_admin)"
        )
        await event.edit(caption, buttons=[[Button.inline("🔙 Kembali", data="main_menu")]], parse_mode='md')

# ==================== HANDLER INPUT CHAT (FSM REGISTER) ====================
@bot.on(events.NewMessage(incoming=True))
async def message_handler(event):
    if event.is_private and event.message.message.startswith('/'):
        return # Abaikan perintah command
        
    user_id = event.sender_id
    state_data = USER_STATES.get(user_id)
    if not state_data:
        return
        
    text = event.raw_text.strip()
    step = state_data.get("step")

    if step == "waiting_phone":
        phone = text
        session_name = f"session_{phone.replace('+', '')}"
        client = TelegramClient(session_name, API_ID, API_HASH)
        await client.connect()
        
        try:
            sent = await client.send_code_request(phone)
            USER_STATES[user_id] = {
                "step": "waiting_otp",
                "phone": phone,
                "session": session_name,
                "hash": sent.phone_code_hash,
                "client": client
            }
            await event.respond(f"🔑 Kode OTP dikirim ke `{phone}`.\n\nSilakan kirim kode OTP tersebut ke sini:", parse_mode='md')
        except Exception as e:
            await event.respond(f"❌ Gagal mengirim OTP: `{e}`\nKetik /start untuk mengulang.", parse_mode='md')
            USER_STATES.pop(user_id, None)
            await client.disconnect()

    elif step == "waiting_otp":
        otp = text.replace(" ", "")
        client = state_data["client"]
        try:
            await client.sign_in(phone=state_data["phone"], code=otp, phone_code_hash=state_data["hash"])
            await finalize_login(event, state_data)
        except SessionPasswordNeededError:
            USER_STATES[user_id]["step"] = "waiting_password"
            await event.respond("🔒 Akun ini menggunakan Verifikasi 2FA.\n\nSilakan kirim **Password Cloud (2FA)** Anda:", parse_mode='md')
        except Exception as e:
            await event.respond(f"❌ OTP Salah atau Error: `{e}`\nKetik /start untuk mengulang.", parse_mode='md')
            USER_STATES.pop(user_id, None)
            await client.disconnect()

    elif step == "waiting_password":
        password = text
        client = state_data["client"]
        try:
            await client.sign_in(password=password)
            await finalize_login(event, state_data)
        except Exception as e:
            await event.respond(f"❌ Password 2FA Salah: `{e}`\nKetik /start untuk mengulang.", parse_mode='md')
            USER_STATES.pop(user_id, None)
            await client.disconnect()

async def finalize_login(event, data):
    phone = data["phone"]
    client = data["client"]
    user_id = event.sender_id
    
    MANAGED_ACCOUNTS[phone] = {
        "client": client,
        "active": True,
        "whitelist": [],
        "session": data["session"]
    }
    
    asyncio.create_task(background_account_guard(phone))
    USER_STATES.pop(user_id, None)
    
    await event.respond(
        f"🎉 **BERHASIL TERDAFTAR!**\n\nAkun `{phone}` kini diproteksi sistem anti-log.\nKetik /start untuk kembali ke menu.",
        parse_mode='md'
    )

# ==================== WORKER BACKGROUND ANTI-LOG ====================
async def background_account_guard(phone: str):
    while phone in MANAGED_ACCOUNTS:
        acc = MANAGED_ACCOUNTS.get(phone)
        if acc and acc["active"]:
            try:
                auths = await acc["client"](GetAuthorizationsRequest())
                for s in auths.authorizations:
                    if not s.current and s.hash not in acc["whitelist"]:
                        await acc["client"](ResetAuthorizationRequest(hash=s.hash))
                        # Jika ingin bot mengirim notifikasi blokir ke Anda, tambahkan kode kirim pesan ke chat ID Anda di sini
            except Exception:
                pass
        await asyncio.sleep(15)

print("========================================")
print("  BOT ANTI-LOGIN TELETHON BERJALAN!     ")
print("========================================")

# Jalankan bot
bot.run_until_disconnected()
