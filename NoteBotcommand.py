from discord.ext import commands
import discord
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
from flask import Flask
from threading import Thread
import json, os, sys, re
import pandas as pd
from thongke import generate_chart_pay_by_month, generate_chart_debt


from slang_handle import handle_message, replace_slang_with_amount
# from final_core import extract_entities

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from oauth2client.service_account import ServiceAccountCredentials

# Đọc token Discord từ biến môi trường
TOKEN = os.getenv("NOTEBOT_DISCORD_NO_AI_TOKEN")

# Đọc Google Drive credentials JSON từ biến môi trường, rồi convert thành dict
creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json_str) if creds_json_str else None

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

if creds_dict:
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
else:
    raise Exception("Google Drive credentials JSON not found in environment variables")


# Load slang mapping
try:
    with open("slang_mapping.json", "r", encoding="utf-8") as f:
        slang_amount_mapping = json.load(f)
except:
    slang_amount_mapping = {}

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client_gs = gspread.authorize(creds)
sheet = client_gs.open("chi_tieu_on_dinh").sheet1

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Web server keep-alive (nếu bạn chạy trên replit hoặc cần)
app = Flask('')

@app.route('/')
def home():
    return "Bot đang chạy ngon lành!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Hàm xử lý AI message
# def process_user_message(message):
#     processed_message = replace_slang_with_amount(message, slang_amount_mapping)
#     result = extract_entities(processed_message)
#     return result

# Bot events
@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Nếu là command thì bỏ qua phần ghi chi tiêu, cho bot.process_commands xử lý
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return
    
    response = handle_message(message.content)
    if response:
        await message.reply(response)

    text = message.content
    # text = replace_slang_with_amount(text, slang_amount_mapping)

    try:
        data = {
            "payer": "",
            "amount": "",
            "spending_category": "",
            "recipients": "",
            "note": ""
        }
        content = text.split(",")
        data['spending_category'] = content[0].strip() if len(content) > 0 else ""
        data['amount'] = content[1].strip() if len(content) > 1 else ""
        data['recipients'] = content[2].strip() if len(content) > 2 else ""
        data['note'] = content[3].strip() if len(content) > 3 else ""
        #text_format = hạng mục chi, số tiền, người nhận, ghi chú.
        # data = process_user_message(text)
        if data["amount"]:
            amt_text = data["amount"].lower().replace(",", "")
            if "k" in amt_text and "tr" in amt_text:
                parts = amt_text.split("tr")
                data["amount"] = int(float(parts[1].replace("k", "")) * 1000 + float(parts[0]) * 1000000)
            elif "k" in amt_text:
                data["amount"] = int(float(amt_text.replace("k", "")) * 1000)
            elif "tr" in amt_text:
                data["amount"] = int(float(amt_text.replace("tr", "")) * 1000000)
            else:
                try:
                    data["amount"] = int(amt_text)
                except:
                    data["amount"] = 0
        else:
            data["amount"] = 0
        print(type(data), data)
        if data['amount'] == 0:
            await message.reply("Không nhận diện được số tiền.\nVui lòng gửi lại theo định dạng: hạng mục chi, số tiền, người nhận, ghi chú.\nVí dụ: ăn uống, 500k, Nghĩa, Không có ghi chú hoặc để trống.")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        username = {"harmonious_fox_17849": "Nghĩa",
            "doufang_8": "Phương",
            "ann_nguyen123": "Ngân"}
        user = username.get(message.author.name, message.author.name)
        sheet.append_row([now, data['spending_category'], data['amount'], user, data['recipients'].title(), ""])

        await message.reply(f"✅ Đã ghi chi tiêu: {data}.\nXem file google sheet [TẠI ĐÂY](https://docs.google.com/spreadsheets/d/1HtiGGXWZ6II9X_L3BxUh60e13isLuOhWL6NR1wcwvVk/edit?gid=0#gid=0)")

    except Exception as e:
        await message.reply(f"❌ Lỗi khi ghi dữ liệu: {e} \nVui lòng gửi lại theo định dạng: hạng mục chi, số tiền, người nhận, ghi chú.\nVí dụ: ăn uống, 500k, Nghĩa, Không có ghi chú hoặc để trống.")

# Bot command gửi biểu đồ
@bot.command()
async def thongkechi(ctx, time=None):
    data = sheet.get_all_values()
    #vẽ biểu đồ chi tiêu tháng
    # if time is None:
    #     pass
    # else:
    #     try:
    #         time = datetime.strptime(time, "%m/%Y").strftime("%m/%Y")
    #     except ValueError:
    #         await ctx.reply("Vui lòng nhập định dạng là MM/YYYY.")
    #         return
    chart_pay = generate_chart_pay_by_month(data, time)
    if not chart_pay:
        await ctx.reply(f"Không có dữ liệu chi tiêu trong tháng {time}.")
        return
    if time is None:
        await ctx.reply(f"📊 Không nhận được thời gian cụ thể nên thống kê toàn bộ dữ liệu chi tiêu: ", file=discord.File(chart_pay, 'chart.png'))
    else: await ctx.reply(f"📊 Thống kê chi tiêu tháng {time}:", file=discord.File(chart_pay, 'chart.png'))

@bot.command()
async def thongkeno(ctx):
    user = ctx.author.name
    data = sheet.get_all_values()
    time = datetime.now().strftime("%m/%Y")
    chart_debt = generate_chart_debt(user,data)
    if not chart_debt:
        await ctx.reply(f"{user} Không có dữ liệu.")
        return
    await ctx.reply(f"📊 Thống kê nợ đến tháng {time}:", file=discord.File(chart_debt, 'chart.png'))
# Chạy bot và web server
# keep_alive() # Deploy trên railway thì không cần nữa. Railway tự giữ bot 24/7
bot.run(TOKEN)
