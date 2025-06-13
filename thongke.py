import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.ticker import FuncFormatter
import pytz
timezone = pytz.timezone("Asia/Ho_Chi_Minh")


def generate_chart_pay_by_month(data, time=None):
    df = pd.DataFrame(data[1:], columns=data[0])

    # Làm sạch dữ liệu
    df['NGÀY'] = pd.to_datetime(df['NGÀY'], errors='coerce', dayfirst=True)
    df['TIỀN'] = df['TIỀN'].str.replace(r'[₫\s]', '', regex=True).str.replace(',', '', regex=False)
    df['TIỀN'] = pd.to_numeric(df['TIỀN'], errors='coerce')
    df = df.dropna(subset=['NGÀY'])

    if time:
        try:
            month, year = map(int, time.split('/'))
            if month < 1 or month > 12:
                print("Tháng không hợp lệ. Vui lòng nhập tháng từ 1 đến 12.")
                return False
            df_filtered = df[(df['NGÀY'].dt.month == month) & (df['NGÀY'].dt.year == year)]
        except Exception as e:
            print(f"Lỗi định dạng thời gian: {e}")
            return False
    else:

        df_filtered = df

    # Thống kê
    result = df_filtered.groupby('NGƯỜI CHI')['TIỀN'].sum().to_dict()
    
    if not result:
        return False

    # Vẽ biểu đồ
    plt.figure(figsize=(10, 6))
    bars = plt.bar(result.keys(), result.values(), color='skyblue')

    plt.xlabel('')
    plt.ylabel('Số tiền (VNĐ)')
    try:
        plt.title(f"Thống kê chi tiêu tháng {month}/{year}")
    except:
        plt.title("Thống kê toàn bộ dữ liệu chi tiêu")
    plt.gca().yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{int(x):,}"))

    for i, (name, value) in enumerate(result.items()):
        plt.text(i, value, f"{int(value):,}", ha='center', va='bottom', fontsize=10)

    plt.tight_layout()

    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return buf


# load lại và làm sạch data
def load_data(data):
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = [col.strip() for col in df.columns]

        # Ép kiểu ngày
        df['NGÀY'] = pd.to_datetime(df['NGÀY'], errors='coerce', dayfirst=True)

        # Làm sạch cột TIỀN:
        df['TIỀN'] = df['TIỀN'].str.replace(r'[₫\s]', '', regex=True)  # bỏ ₫ và khoảng trắng
        df['TIỀN'] = df['TIỀN'].str.replace(',', '', regex=False)      # bỏ dấu phẩy hàng nghìn

        # Giữ dấu chấm thập phân, sau đó ép kiểu float
        df['TIỀN'] = pd.to_numeric(df['TIỀN'], errors='coerce')

        data = df.dropna(subset=['NGÀY'])
        # print(self.df[['NGÀY', 'NGƯỜI CHI', 'TIỀN']])
        # print(f"✅ Đã tải {len(self.df)} dòng dữ liệu (sau khi xử lý ngày và tiền)")
        return data

# thống kê nợ từng người
def total_debt_by_person_in_month(data, month=None, year=None):
        data = load_data(data)
        pd.set_option('display.float_format', '{:,.0f}'.format)
        payer = data['NGƯỜI CHI'].unique().tolist()
        
        
        # data['NGƯỜI NHẬN'] = data['NGƯỜI NHẬN']
        all_names = []

        known_names = ['Mọi Người']

        for recipients in data['NGƯỜI NHẬN']:
            if recipients in known_names:
                all_names.append(recipients)
            else:
                # Những trường hợp còn lại (như 'Mọi Người', 'Nhi', 'Nghĩa') để nguyên từng cái
                all_names.extend(recipients.split(' '))  # giả sử mỗi tên cách nhau bằng dấu ' '

        unique_names = list(set(payer+all_names))  # Loại bỏ trùng lặp
        # print(unique_names)
        debt_by_person = {}
        done_pairs = set()
        total_pay_by_p = total_pay_by_r = 0
        def chia_tien(row):
            recipients = row["NGƯỜI NHẬN"]
            amount = row["TIỀN"]

            if recipients == "Mọi Người":
                return amount / 5
            else:
                num_recipients = len(recipients.split(" "))
                return amount / num_recipients if num_recipients > 0 else amount

        for p in unique_names: # p là payer
            for r in unique_names: # r là receiver
                if p != r and (p, r) not in done_pairs and (r, p) not in done_pairs:
                    df_filtered = data[
                    (
                        ((data['NGƯỜI CHI'] == p) & (data['NGƯỜI NHẬN'] == r)) |
                        ((data['NGƯỜI CHI'] == r) & (data['NGƯỜI NHẬN'] == p)) |
                        ((data['NGƯỜI CHI'] == p) & (data['NGƯỜI NHẬN'] == 'Mọi Người')) |
                        ((data['NGƯỜI CHI'] == r) & (data['NGƯỜI NHẬN'] == 'Mọi Người')) |
                        (
                            (data['NGƯỜI CHI'] == p) &
                            (data['NGƯỜI NHẬN'].str.contains(r, na=False))
                        ) |
                        (
                            (data['NGƯỜI CHI'] == r) &
                            (data['NGƯỜI NHẬN'].str.contains(p, na=False))
                        )
                    )]
                    
                    # df_filtered.loc[df_filtered["NGƯỜI NHẬN"] == "Mọi Người", "TIỀN"] /= 5  # Giả sử có 5 người chi tiêu chung, chia đều tiền cho mỗi người
                    if df_filtered.empty:
                        continue
                    df_filtered["TIỀN"] = df_filtered.apply(chia_tien, axis=1)
                    total_pay_by_p = df_filtered[df_filtered['NGƯỜI CHI'] == p]['TIỀN'].sum()
                    total_pay_by_r = df_filtered[df_filtered['NGƯỜI CHI'] == r]['TIỀN'].sum()
                    debt = total_pay_by_p-total_pay_by_r
                    if debt > 0:
                        debt_by_person[(p, r)] = debt
                    elif debt < 0:
                        debt_by_person[(r, p)] = -debt

                done_pairs.add((p, r))  # Loại bỏ người đã tính để tránh tính lại
        df = pd.DataFrame([(p[0], p[1], r) for p,r in debt_by_person.items() if p[1] != 'Mọi Người'], columns=['Chủ nợ', 'Người nợ', 'Số tiền'])
        df_group_detail = df.groupby(['Người nợ', 'Chủ nợ'])['Số tiền'].sum().reset_index().sort_values(by='Người nợ')
        return df_group_detail


import knowledge

def generate_chart_debt(name, data):
    df_debt = total_debt_by_person_in_month(data)
    name = knowledge.username.get(name, name)  # Lấy tên người từ dict nếu có
    
    # Người mà name nợ
    df_person_r = df_debt[df_debt['Người nợ'] == name][['Chủ nợ', 'Số tiền']].copy()
    df_person_r.rename(columns={'Chủ nợ': 'Tên người'}, inplace=True)
    df_person_r['Giá trị'] = -df_person_r['Số tiền']  # Âm
    
    # display(df_person_r)  # Hiển thị bảng người nợ

    # Người mà nợ name
    df_person_p = df_debt[df_debt['Chủ nợ'] == name][['Người nợ', 'Số tiền']].copy()
    df_person_p.rename(columns={'Người nợ': 'Tên người'}, inplace=True)
    df_person_p['Giá trị'] = df_person_p['Số tiền']  # Dương
    # display(df_person_p)

    # Gộp lại
    df_all = pd.concat([df_person_r[['Tên người', 'Giá trị']], df_person_p[['Tên người', 'Giá trị']]])
    
    if df_all.empty:
        print(f"{name} không có khoản nợ nào.")
        return
    
    plt.figure(figsize=(10,6))
    ax = sns.barplot(data=df_all, x='Tên người', y='Giá trị', palette='coolwarm', width=0.5)

    plt.title(f'Thống kê nợ của {name} đến {datetime.now(timezone).strftime("%d/%m/%Y")}')
    plt.ylabel('Số tiền (VNĐ)')
    plt.xlabel('')

    ax.axhline(0, color='black', linewidth=1)  # Đường mốc 0
    
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f'{int(x):,}'))

    # Hiện giá trị trên đầu cột
    for p in ax.patches:
        height = p.get_height()
        if height != 0:
            ax.text(p.get_x() + p.get_width()/2., height + (5_000 if height > 0 else -5_000),
                    f'{int(height):,}', ha='center', va='bottom' if height > 0 else 'top',
                    fontsize=9, color='black', fontweight='bold')
            
    # plt.tight_layout()
    # plt.show()


    buf = BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf