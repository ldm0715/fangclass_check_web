from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

from config import REPORT_DIR as report_dir


def draw_report_card(raw_data, total, valid, invalid, rate, nickname):
    items = [line.strip().split(" + ") for line in raw_data.strip().split("\n")]
    # total = 13
    # valid = 9
    # invalid = 4
    # rate = "69.23%"

    # --- 2. 卡片配置 ---
    canvas_width = 800
    canvas_height = 1000
    bg_color = (245, 247, 250)  # 浅灰色背景
    card_color = (255, 255, 255)  # 白色卡片
    primary_color = (64, 158, 255)  # 蓝色
    text_color = (51, 51, 51)
    success_color = (103, 194, 58)
    danger_color = (245, 108, 108)

    # 创建画布
    img = Image.new("RGB", (canvas_width, canvas_height), bg_color)
    draw = ImageDraw.Draw(img)

    # 加载字体 (请确保路径下有中文字体文件，如黑体)
    # Windows路径参考: "C:/Windows/Fonts/msyh.ttc" (微软雅黑)
    try:
        font_title = ImageFont.truetype("msyh.ttc", 36)
        font_sub = ImageFont.truetype("msyh.ttc", 20)
        font_body = ImageFont.truetype("msyh.ttc", 18)
    except:
        font_title = font_sub = font_body = ImageFont.load_default()

    # --- 3. 绘制UI ---
    # 绘制圆角矩形卡片
    draw.rounded_rectangle([40, 40, 760, 960], radius=20, fill=card_color)

    # 标题
    draw.text(
        (80, 80), f"{nickname} · 提问数据统计报告", font=font_title, fill=text_color
    )
    draw.line([80, 140, 720, 140], fill=(230, 230, 230), width=2)

    # 统计概览数据
    stats = [
        ("总提问", str(total)),
        ("有效", str(valid)),
        ("无效", str(invalid)),
        ("未出结果", str(total - valid - invalid)),
        ("有效率", rate),
    ]
    for i, (label, val) in enumerate(stats):
        x_pos = 80 + i * 130
        draw.text((x_pos, 170), label, font=font_sub, fill=(150, 150, 150))
        val_color = success_color if label == "有效率" else text_color
        draw.text((x_pos, 205), val, font=font_title, fill=val_color)

    # 明细列表表头
    draw.rectangle([80, 280, 720, 320], fill=(240, 245, 255))
    headers = ["状态", "日期", "班级", "期数", "教室", "主讲人"]
    for i, h in enumerate(headers):
        draw.text((90 + i * 110, 290), h, font=font_body, fill=primary_color)

    # 循环绘制明细数据
    for i, item in enumerate(items):
        y = 330 + i * 45
        # 隔行变色
        if i % 2 == 1:
            draw.rectangle([80, y - 5, 720, y + 35], fill=(250, 250, 250))

        # 状态着色
        status_color = success_color if item[0] == "有效" else danger_color
        draw.text((90, y), item[0], font=font_body, fill=status_color)

        # 其它文字
        for j in range(1, len(item)):
            draw.text((90 + j * 110, y), item[j], font=font_body, fill=(100, 100, 100))

    # 保存图片
    img.save("data_card.png")
    print("数据卡片已生成：data_card.png")


def draw_report_card_v2(raw_data, nickname):

    # --- 1. 数据解析 ---


    items = [
        line.strip().split(" + ")
        for line in raw_data.strip().split("\n")
        if line.strip()
    ]
    total = len(items)
    valid = sum(1 for i in items if i[0] == "有效")
    invalid = sum(1 for i in items if i[0] == "无效")
    unknown = total - valid - invalid
    rate = f"{valid/total*100:.2f}%"

    dates = [item[1] for item in items]
    latest_date = max(dates) if dates else "未知日期"

    # --- 2. 动态布局计算 (核心修复部分) ---
    headers = ["状态", "日期", "班级", "期数", "教室", "提问人"]
    margin_x = 80  # 左右边距
    col_width = 130  # 每列宽度
    top_area_height = 280  # 顶部标题和统计区高度
    row_height = 45  # 每一行数据的高度
    header_height = 40  # 表头高度

    # 【修复逻辑】先计算列表会在哪里结束
    list_start_y = top_area_height
    list_end_y = list_start_y + header_height + (len(items) * row_height)

    # 【修复逻辑】页脚位置 = 列表结束位置 + 40px 间距
    footer_y = list_end_y + 40

    # 【修复逻辑】总高度 = 页脚位置 + 60px 底部留白
    canvas_height = footer_y + 60
    canvas_width = margin_x * 2 + (len(headers) * col_width) - 20

    bg_color = (245, 247, 250)
    card_color = (255, 255, 255)
    primary_color = (64, 158, 255)
    text_color = (51, 51, 51)
    success_color = (103, 194, 58)
    danger_color = (245, 108, 108)

    img = Image.new("RGB", (canvas_width, canvas_height), bg_color)
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("msyh.ttc", 36)
        font_sub = ImageFont.truetype("msyh.ttc", 20)
        font_body = ImageFont.truetype("msyh.ttc", 18)
        font_footer = ImageFont.truetype("msyh.ttc", 16)
    except:
        font_title = font_sub = font_body = font_footer = ImageFont.load_default()

    # --- 3. 绘制UI ---
    # 背景卡片 (高度动态跟随 canvas_height)
    draw.rounded_rectangle(
        [40, 40, canvas_width - 40, canvas_height - 40], radius=20, fill=card_color
    )

    # 标题
    draw.text(
        (margin_x, 80),
        f"{nickname} · 提问数据统计报告",
        font=font_title,
        fill=text_color,
    )
    draw.line(
        [margin_x, 140, canvas_width - margin_x, 140], fill=(230, 230, 230), width=2
    )

    # 统计概览
    stats = [
        ("总提问", str(total)),
        ("有效", str(valid)),
        ("无效", str(invalid)),
        ("未出结果", str(unknown)),
        ("有效率", rate),
    ]
    for i, (label, val) in enumerate(stats):
        x_pos = margin_x + i * 130
        draw.text((x_pos, 170), label, font=font_sub, fill=(150, 150, 150))
        val_color = success_color if label == "有效率" else text_color
        draw.text((x_pos, 205), val, font=font_title, fill=val_color)

    # 表头
    draw.rectangle(
        [margin_x, list_start_y, canvas_width - margin_x, list_start_y + header_height],
        fill=(240, 245, 255),
    )
    for i, h in enumerate(headers):
        draw.text(
            (margin_x + 10 + i * col_width, list_start_y + 10),
            h,
            font=font_body,
            fill=primary_color,
        )

    # 数据行
    for i, item in enumerate(items):
        y = list_start_y + header_height + i * row_height

        if i % 2 == 1:
            draw.rectangle(
                [margin_x, y, canvas_width - margin_x, y + row_height],
                fill=(250, 250, 250),
            )

        if item[0] == "有效":
            status_color = success_color
        elif item[0] == "无效":
            status_color = danger_color
        else:
            status_color = (230, 162, 60)
        draw.text((margin_x + 10, y + 12), item[0], font=font_body, fill=status_color)

        for j in range(1, len(item)):
            draw.text(
                (margin_x + 10 + j * col_width, y + 12),
                item[j],
                font=font_body,
                fill=(100, 100, 100),
            )

    # --- 4. 绘制页脚 (位置已修正) ---
    footer_text = f"数据更新至: {latest_date}  |  总计 {len(items)} 条记录"

    # 分割线
    draw.line(
        [margin_x, footer_y - 20, canvas_width - margin_x, footer_y - 20],
        fill=(240, 240, 240),
        width=1,
    )
    # 文字
    draw.text(
        (margin_x, footer_y - 10), footer_text, font=font_footer, fill=(150, 150, 150)
    )

    if not report_dir.exists():
        report_dir.mkdir(parents=True)

    #  卡片命名： 日期 + 名字 + “valiad_report”
    today_date = datetime.now().strftime("%Y-%m-%d")

    save_path = report_dir / f"{today_date}_{nickname}_valiad_report_card.png"

    img.save(save_path)
    print(f"修正版卡片已生成：尺寸 {canvas_width}x{canvas_height}")


if __name__ == "__main__":
    raw_data = """
    无效 + 2025-09-25 + 教学8班 + 第203期 + B2-408 + 党广源
    有效 + 2025-10-16 + 教学9班 + 第205期 + B2-301 + 田梓汎
    无效 + 2025-10-16 + 教学3班 + 第205期 + B2-401 + 游贵鹏
    有效 + 2025-10-16 + 教学6班 + 第205期 + B2-406 + 邓宇航
    有效 + 2025-11-13 + 教学3班 + 第209期 + B2-401 + 孙维政
    有效 + 2025-11-13 + 教学9班 + 第209期 + B2-301 + 刘以嘉
    有效 + 2025-11-20 + 教学3班 + 第210期 + B2-401 + 杨剑弘
    无效 + 2025-11-20 + 教学3班 + 第210期 + B2-401 + 胡达
    有效 + 2025-12-11 + 教学9班 + 第213期 + B2-301 + 陈英杰
    有效 + 2025-12-18 + 教学4班 + 第214期 + B2-402 + 戴楠俊
    有效 + 2025-12-18 + 教学4班 + 第214期 + B2-402 + 刘浩
    有效 + 2025-12-18 + 教学4班 + 第214期 + B2-402 + 许婉莹
    无效 + 2025-12-18 + 教学4班 + 第214期 + B2-402 + 游贵鹏
    """
    draw_report_card_v2(raw_data, "测试用户")
