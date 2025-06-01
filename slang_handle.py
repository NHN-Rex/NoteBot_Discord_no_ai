import os
import json
import re

# Đường dẫn đến file slang_mapping.json trong thư mục bot
slang_mapping_path = os.path.join(os.path.dirname(__file__), '..', 'bot', 'slang_mapping.json')

# Load mapping nếu đã có
try:
    with open(slang_mapping_path, encoding="utf-8") as f:
        slang_amount_mapping = json.load(f)
except:
    slang_amount_mapping = {}


def replace_slang_with_amount(message_text, slang_mapping):
    # Regex: số và slang ghép lại
    pattern = re.compile(r'\b(\d+)\s*([^\W\d_]+)\b', re.IGNORECASE)
    def repl(m):
        number = int(m.group(1))
        slang = m.group(2).lower()
        # print(f"Đang xử lý slang: {slang} với số: {number}")
        if slang in slang_mapping:
            total = number * slang_mapping[slang]
            if total/1000000<1:
                return f"{total/1000:.0f}k"
            else:
                if (total-int(total/1000000)*1000000)/1000 < 100000:
                    return (f"{int(total/1000000):.0f}tr")
                else:
                    return (f"{int(total/1000000):.0f}tr{(total-int(total/1000000)*1000000)/1000:.0f}k")
            # return str(total)
        else:
            # Nếu slang không có trong mapping, trả lại nguyên cụm ban đầu
            return m.group(0)

    # Thay thế tất cả cụm số + slang nếu slang có trong mapping
    message_text = pattern.sub(repl, message_text)

    return message_text



def handle_message(message):
    if message.lower().startswith("bot dạy:"):
        try:
            content = message.split("bot dạy:")[1].strip()
            slang_with_num, amount = content.split("=")
            slang_with_num = slang_with_num.strip()
            amount = int(amount.strip())

            # Lấy ra phần slang bỏ số đứng trước nếu có
            # Ví dụ "1 lít" => "lít"
            slang_parts = slang_with_num.split()
            if len(slang_parts) > 1 and slang_parts[0].isdigit():
                slang = " ".join(slang_parts[1:])
            else:
                slang = slang_with_num

            slang_amount_mapping[slang] = amount

            # Lưu lại file
            with open("slang_mapping.json", "w", encoding="utf-8") as f:
                json.dump(slang_amount_mapping, f, ensure_ascii=False)

            return f"Ok, đã nhớ {slang} là {amount}!"
        except Exception as e:
            print(e)
            return "Sai cú pháp rồi, gửi kiểu: bot dạy: 1 lít = 100000"
    else:
        return process_spending_message(message)


def process_spending_message(message):
    result = []
    for slang, value in slang_amount_mapping.items():
        if slang in message:
            # print(f"Tìm thấy slang: {slang} = {value}")
            result.append((slang, value))
    return result
