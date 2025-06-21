from discord.ext import commands
import discord
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO
from flask import Flask, request
from threading import Thread
import json, os, sys, re
import pandas as pd
from thongke import generate_chart_pay_by_month, generate_chart_debt
# from slang_handle import handle_message, replace_slang_with_amount
# from final_core import extract_entities

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Google Sheets setup
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]


# sử dụng trên render
# Lấy nội dung JSON từ biến môi trường
credentials_info = os.getenv("GOOGLE_CREDENTIALS_JSON")
# Parse string JSON thành dict
credentials_dict = json.loads(credentials_info)
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client_gs = gspread.authorize(creds)

# # sử dụng local
# creds = ServiceAccountCredentials.from_json_keyfile_name(
#     "credentials.json", scope)
# client_gs = gspread.authorize(creds)

# Load slang mapping
def load_slang_from_sheet(slang_sheet):
    rows = slang_sheet.get_all_records()
    slang_mapping = {}

    for row in rows:
        key = row['slang'].strip().lower()
        type_ = row['type']
        value_raw = row['value']

        if type_ == "number":
            value = float(value_raw)
        elif type_ == "list":
            value = [v.strip() for v in value_raw.split(",")]
        else:
            value = value_raw

        slang_mapping[key] = value

    return slang_mapping

def replace_slang(text, mapping):
    # Sắp xếp slang theo độ dài giảm dần để replace từ dài trước
    sorted_mapping = sorted(mapping.items(), key=lambda x: len(x[0]), reverse=True)
    
    for slang, real_value in sorted_mapping:
        text = text.replace(slang, str(real_value))
    return text


def update_slang_mapping_to_sheet(message_content, sheet_slang_mapping):
    # Regex tách dạng "bot ngu: something = something"
    pattern = r"bot ngu:\s*(.+?)\s*=\s*(.+)"
    match = re.match(pattern, message_content, re.IGNORECASE)

    if match:
        key = match.group(1).strip()
        value_raw = match.group(2).strip()

        # Xác định kiểu dữ liệu của value
        try:
            value = int(value_raw.replace(",", "").replace(".", ""))
            type_ = "number"
        except ValueError:
            # Nếu nhập value là list cách nhau bằng dấu ,
            if "," in value_raw:
                value = [v.strip() for v in value_raw.split(",")]
                type_ = "list"
                value_raw = ",".join(value)  # để lưu lên sheet
            else:
                value = value_raw
                type_ = "string"

        # Kiểm tra xem key đã tồn tại chưa
        rows = sheet_slang_mapping.get_all_records()
        for i, row in enumerate(rows):
            if row['slang'] == key:
                sheet_slang_mapping.update_cell(i+2, 2, type_)
                sheet_slang_mapping.update_cell(i+2, 3, value_raw)
                return f"Đã cập nhật: '{key}' → '{value_raw}'"

        # Nếu chưa có thì thêm mới
        sheet_slang_mapping.append_row([key, type_, value_raw])
        return f"Đã thêm mới: '{key}' → '{value_raw}'"
    else:
        return "Cú pháp sai rồi bro! Dùng đúng dạng: bot ngu: cái này = cái kia"

def parse_amount(amount_text, slang_mapping):
    if not amount_text:
        return 0, None

    amt_text = amount_text.lower().replace(",", "").replace(" ", "").strip()
    print(amt_text)
    total_amount = 0

    pattern = r"(\d+(?:\.\d+)?)([a-zA-ZÀ-Ỹà-ỹ]*)"  # thêm support tiếng Việt có dấu
    matches = re.findall(pattern, amt_text)
    print(matches)

    last_unit = None
    for number_part, unit_part in matches:
        try:
            base_amount = float(number_part)
        except:
            base_amount = 0

        unit_part = unit_part.strip().lower()

        if unit_part:
            if unit_part not in slang_mapping:
                return 0, f"❌ Đơn vị `{unit_part}` chưa có trong slang. Vui lòng thêm bằng lệnh `bot ngu: {unit_part} = giá trị`."
            multiplier = slang_mapping[unit_part]
            total_amount += int(base_amount * multiplier)
            last_unit = unit_part
        else:
            if last_unit and last_unit in slang_mapping:
                next_step = slang_mapping[last_unit] / 10
                total_amount += int(base_amount * next_step)
            else:
                total_amount += int(base_amount)

    return total_amount, None

sheet = client_gs.open("chi_tieu_on_dinh")
sheet_log = sheet.worksheet('log')
sheet_slang_mapping = sheet.worksheet('slang_mapping')
slang_mapping = load_slang_from_sheet(sheet_slang_mapping)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Web server keep-alive (nếu bạn chạy trên replit hoặc cần)
app = Flask('')


@app.route('/')
def home():
    user_agent = request.headers.get('User-Agent')
    print(f"Ping từ: {request.remote_addr} - User-Agent: {user_agent}")
    return "Bot đang chạy ngon lành!"


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()

# Bot events
@bot.event
async def on_ready():
    print(f"✅ Bot đã đăng nhập thành {bot.user}")


@bot.event
async def on_message(message):
    global slang_mapping
    slang_mapping = load_slang_from_sheet(sheet_slang_mapping)
    if message.author == bot.user:
        return

    # Nếu là command thì bỏ qua phần ghi chi tiêu, cho bot.process_commands xử lý
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    if message.content.lower().startswith("thống kê nợ"):
        user = message.author.name
        # slang_mapping = load_slang_from_sheet(sheet_slang_mapping)
        name = replace_slang(user, slang_mapping)
        data = sheet_log.get_all_values()
        time = datetime.now().strftime("%m/%Y")
        chart_debt = generate_chart_debt(name, data)
        if not chart_debt:
            await message.reply(f"{name} Không có dữ liệu.")
            return
        await message.reply(f"📊 Thống kê nợ đến tháng {time}:",
                        file=discord.File(chart_debt, 'chart.png'))
        return

    # response = handle_message(message.content)
    # if response:
    #     await message.reply(response)

    if message.content.lower().startswith("bot ngu:"):
        response = update_slang_mapping_to_sheet(message.content, sheet_slang_mapping)
        await message.reply(response)
        # slang_mapping = load_slang_from_sheet(sheet_slang_mapping)
        return
    
    if message.content.lower().startswith("format"):
        response = f"ℹ️**Người chi** *(không cần ghi nếu dùng tài khoản của bạn)*, \n\
        **Hạng mục chi**, \n\
        **Số tiền**, \n\
        **Người nhận**, \n\
        **Ghi chú** *(không cần ghi nếu không có)*."
        await message.reply(response)
        return

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
        #text_format = người chi, hạng mục chi, số tiền, người nhận, ghi chú.


        content = text.split(",")
        content = [c.strip() for c in content]

        
        # Nếu có 5 phần tử: người chi, hạng mục, số tiền, người nhận, ghi chú
        if len(content) == 5:
            data['payer'] = replace_slang(content[0].lower(), slang_mapping).title()
            data['spending_category'] = content[1]
            data['amount'] = content[2]
            content[3] = replace_slang(content[3].lower(), slang_mapping).title()
            data['recipients'] = content[3]
            data['note'] = content[4]
        # Nếu có 4 phần tử: có thể là [người chi, hạng mục, số tiền, người nhận] hoặc [hạng mục, số tiền, người nhận, ghi chú]
        elif len(content) == 4:
            know_names = slang_mapping.get("username", [])
            content[0] = replace_slang(content[0].lower(), slang_mapping).title()
            # Nếu phần tử đầu là tên người trong danh sách thì lấy làm payer
            if content[0].title() in know_names:
                data['payer'] = content[0]
                data['spending_category'] = content[1]
                data['amount'] = content[2]
                content[3] = replace_slang(content[3].lower(), slang_mapping).title()
                data['recipients'] = content[3]
                data['note'] = ""
            else:
                data['payer'] = slang_mapping.get(message.author.name, message.author.name)
                data['spending_category'] = content[0]
                data['amount'] = content[1]
                content[2] = replace_slang(content[2].lower(), slang_mapping).title()
                data['recipients'] = content[2]
                data['note'] = content[3]
        # Nếu có 3 phần tử: hạng mục, số tiền, người nhận
        elif len(content) == 3:
            data['payer'] = slang_mapping.get(message.author.name, message.author.name)
            data['spending_category'] = content[0]
            data['amount'] = content[1]
            content[2] = replace_slang(content[2].lower(), slang_mapping).title()
            data['recipients'] = content[2]
            data['note'] = ""
        # Nếu có 2 phần tử: hạng mục, số tiền
        elif len(content) == 2:
            data['payer'] = slang_mapping.get(message.author.name, message.author.name)
            data['spending_category'] = content[0]
            data['amount'] = content[1]
            data['recipients'] = "Mọi Người"
            data['note'] = ""
        else:
            await message.reply("Cú pháp chưa đúng bro! Nhập đủ ít nhất 2 phần tử: hạng mục, số tiền nha!")
            return

        data["amount"] = parse_amount(data['amount'], slang_mapping)[0]

        # if data["amount"]:
        #     amt_text = data["amount"].lower().replace(",", "")
        #     if "k" in amt_text and "tr" in amt_text:
        #         parts = amt_text.split("tr")
        #         data["amount"] = int(
        #             float(parts[1].replace("k", "")) * 1000 +
        #             float(parts[0]) * 1000000)
        #     elif "k" in amt_text:
        #         data["amount"] = int(float(amt_text.replace("k", "")) * 1000)
        #     elif "tr" in amt_text:
        #         data["amount"] = int(
        #             float(amt_text.replace("tr", "")) * 1000000)
        #     else:
        #         try:
        #             data["amount"] = int(amt_text)
        #         except:
        #             data["amount"] = 0
        # else:
        #     data["amount"] = 0
        # if data['amount'] == 0:
        #     await message.reply(
        #         "Không nhận diện được số tiền.\nVui lòng gửi lại theo định dạng: hạng mục chi, số tiền, người nhận, ghi chú.\nVí dụ: ăn uống, 500k, Nghĩa, Không có ghi chú thì để trống."
        #     )
        #     return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # user = knowledge.username.get(message.author.name, message.author.name)
        
        sheet_log.append_row([
            now, data['spending_category'], data['amount'], data['payer'],
            data['recipients'].title(), data['note']
        ])

        await message.reply(
            f"✅ Đã ghi vào sheet:\n\
                    Người chi: ***{data['payer']}***\n\
                    Hạng mục chi: ***{data['spending_category']}***\n\
                    Số tiền:"+f" ***{data['amount']:,}".replace(",",".")+f"đ***\n\
                    Người Nhận: ***{data['recipients'].title()}***\n\
                    Ghi chú: ***{data['note'] or 'Không có'}***\n\
                    Xem file google sheet [***TẠI ĐÂY***](https://docs.google.com/spreadsheets/d/1HtiGGXWZ6II9X_L3BxUh60e13isLuOhWL6NR1wcwvVk/edit?gid=0#gid=0)"
        )

    except Exception as e:
        await message.reply(
            f"❌ Lỗi khi ghi dữ liệu: {e} \nVui lòng gửi lại theo định dạng: người chi, hạng mục chi, số tiền, người nhận, ghi chú.\nVí dụ: ghi giùm người chi hoặc để trống, ăn uống, 500k, Nghĩa, Không có ghi chú hoặc để trống."
        )


# Bot command gửi biểu đồ
@bot.command()
async def thongkechi(ctx, time=None):
    data = sheet_log.get_all_values()
    chart_pay = generate_chart_pay_by_month(data, time)
    if not chart_pay:
        await ctx.reply(f"Không có dữ liệu chi tiêu trong tháng {time}.")
        return
    if time is None:
        await ctx.reply(
            f"📊 Không nhận được thời gian cụ thể nên thống kê toàn bộ dữ liệu chi tiêu: ",
            file=discord.File(chart_pay, 'chart.png'))
    else:
        await ctx.reply(f"📊 Thống kê chi tiêu tháng {time}:",
                        file=discord.File(chart_pay, 'chart.png'))


@bot.command()
async def thongkeno(ctx):
    user = ctx.author.name
    name = replace_slang(user, slang_mapping)
    data = sheet_log.get_all_values()
    time = datetime.now().strftime("%m/%Y")
    chart_debt = generate_chart_debt(name, data)
    if not chart_debt:
        await ctx.reply(f"{name} Không có dữ liệu.")
        return
    await ctx.reply(f"📊 Thống kê nợ đến tháng {time}:",
                    file=discord.File(chart_debt, 'chart.png'))


@bot.event
async def on_disconnect():
    print("Bot đã bị mất kết nối...")

@bot.event
async def on_resumed():
    print("Bot đã kết nối lại thành công!")

# Chạy bot và web server
keep_alive()
bot.run(os.getenv('NoteBotDiscordToken'))
