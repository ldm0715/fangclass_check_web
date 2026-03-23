import requests
from draw_card import draw_report_card_v2
from config import INFO_DIR

my_headers = None
NAME = None
token = None


def data_extract(data, target_name):
    """整合每节课的数据"""
    result_list = []

    date = data.get("date")
    class_name = data.get("class")
    period = data.get("period")
    classroom = data.get("offline_classroom")

    for report in data.get("report", []):
        reporter_name = report.get("reporter")

        for ask_student in report.get("ask_student", []):
            if "nick" in ask_student:
                if ask_student["nick"] == target_name:
                    if "is_validate" in ask_student:
                        if ask_student["is_validate"]:
                            validate = "有效"
                        else:
                            validate = "无效"
                    else:
                        validate = "未出结果"
                    result = f"{validate} + {date} + {class_name} + {period} + {classroom} + {reporter_name}"
                    result_list.append(result)
    return result_list


def get_each_class_result(id, headers, target_name):
    """给每节课发送请求"""
    class_url = f"https://class.fangban.net/api/course/info/{id}"
    try:
        response = requests.get(class_url, headers=headers)

        if response.status_code == 200:
            each_class_json = response.json()
            each_class_list = data_extract(each_class_json["data"], target_name)
            return each_class_list
        else:
            print(f"--- 请求失败 状态码: {response.status_code} ---")
            return []

    except requests.exceptions.RequestException as e:
        print(f"--- 发生网络错误: {e} ---")
        return []


def get_dates_by_name(json_data, name="厅", theme="#297ECC"):
    """获取研讨厅上课的时间列表"""
    found_dates = set()
    data_list = json_data.get("data", [])
    for entry in data_list:
        stats_list = entry.get("course_stats", [])
        for stat in stats_list:
            if stat.get("name") == name and stat.get("theme") == theme:
                entry_date = entry.get("date")
                if entry_date:
                    found_dates.add(entry_date)
                break
    return sorted(list(found_dates))


def get_class_id(date, headers):
    """获取指定日期每节课程的id"""
    class_id_list = set()
    course_query_url = f"https://class.fangban.net/api/course/list/?date={date}"

    res = requests.get(course_query_url, headers=headers)
    if res.status_code == 200:
        res_json = res.json()
        if res_json:
            data_list = res_json.get("data", [])["data"]
            for entry in data_list:
                id = entry.get("id")
                if id:
                    class_id_list.add(id)
        return list(class_id_list)
    else:
        print("课程查询失败")
        return []


def get_course_date(name, headers):
    """获取某学期的研讨厅上课日期列表"""
    query_url = f"https://class.fangban.net/api/course/calendar_list/?name={name}"

    response = requests.get(query_url, headers=headers)

    if response.status_code == 200:
        res_json = response.json()
        if res_json:
            class_date_list = get_dates_by_name(res_json)
            return class_date_list
        else:
            print("上课日期查询失败")
    else:
        print(f"--- 请求失败 状态码: {response.status_code} ---")

    return []


def get_semester_list_api(headers):
    """获取学期列表（供 GUI 调用，不打印）"""
    query_url = "https://class.fangban.net/api/semester/list/"

    responses = requests.get(query_url, headers=headers)

    semester_list = []
    responses_json = responses.json()
    data = responses_json["data"]
    for semester in data:
        semester_list.append(semester["name"])
    return semester_list


def build_headers(token_str):
    """构建 API 请求头"""
    return {
        "Connection": "keep-alive",
        "sec-ch-ua-platform": '"Windows"',
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
        "token": token_str,
        "sec-ch-ua-mobile": "?0",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://class.fangban.net/course",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "identity",
        "Cookie": "token=%s" % token_str,
    }


def query_all_data(token_str, target_name, semester_name, progress_callback=None):
    """
    查询指定学期的所有提问数据。
    返回结构化结果字典。
    progress_callback(current, total, message) 可选进度回调。
    """
    headers = build_headers(token_str)

    all_course_date = get_course_date(name=semester_name, headers=headers)
    total_dates = len(all_course_date)

    if progress_callback:
        progress_callback(0, total_dates, f"共找到 {total_dates} 个上课日期")

    total_result = []

    for idx, date in enumerate(all_course_date):
        if progress_callback:
            progress_callback(idx, total_dates, f"正在查询 {date} 的课程数据...")

        class_id_list = get_class_id(date, headers)
        if class_id_list:
            for cid in class_id_list:
                result = get_each_class_result(cid, headers, target_name)
                if result:
                    total_result.extend(result)

    if progress_callback:
        progress_callback(total_dates, total_dates, "查询完成")

    # 解析结果
    results = []
    raw_data = ""
    valid_count = 0
    invalid_count = 0
    unknown_count = 0

    for line in total_result:
        parts = [p.strip() for p in line.split(" + ")]
        if len(parts) >= 6:
            status, date, class_name, period, classroom, reporter = parts[:6]
            results.append({
                "status": status,
                "date": date,
                "class": class_name,
                "period": period,
                "classroom": classroom,
                "reporter": reporter,
            })
            if status == "有效":
                valid_count += 1
            elif status == "无效":
                invalid_count += 1
            else:
                unknown_count += 1
        raw_data += line + "\n"

    total_count = len(results)
    valid_rate = "{:.2f}%".format(
        (valid_count / total_count) * 100 if total_count > 0 else 0
    )

    return {
        "name": target_name,
        "semester": semester_name,
        "raw_data": raw_data,
        "results": results,
        "total": total_count,
        "valid": valid_count,
        "invalid": invalid_count,
        "unknown": unknown_count,
        "valid_rate": valid_rate,
    }


# ===== 以下为原始 CLI 入口 =====


def set_headers():
    global my_headers
    global token
    my_headers = build_headers(token)


def set_global_header():
    from fanclass_login import get_token

    token_and_name = get_token()
    if not token_and_name:
        token_and_name = {}
    global NAME
    global token

    token = token_and_name.get("token", "")
    NAME = token_and_name.get("name", "")

    set_headers()


def get_semester_list():
    semester_list = get_semester_list_api(my_headers)
    print("--------------------------------------")
    print(semester_list)
    print(f"共查询到 {len(semester_list)} 个学期")
    return semester_list


def delete_cookie(choice):
    cookie_path = INFO_DIR / "cookies.json"

    if cookie_path.exists():
        cookie_path.unlink()
        print("✓ 已退出登录，删除cookie文件")
    else:
        print("❌ cookie文件不存在，无法删除")


def main():
    set_global_header()

    semester_list = get_semester_list()
    print("支持查询的学期：")
    for index, semester in enumerate(semester_list):
        print(f"{index + 1}. {semester}")

    choice = input("请输入要查询的学期（数字）：")
    course_name = semester_list[int(choice) - 1]

    if token is None or NAME is None:
        print("姓名或token不能为空")
        return

    print(f"---开始查询【{NAME}】的提问情况---")

    result = query_all_data(token, NAME, course_name)

    if result["total"] == 0:
        print("未查询到记录")
    else:
        print(f"{NAME}共提问【{result['total']}】次")
        print(f"其中，有效【{result['valid']}】次，无效【{result['invalid']}】次，未出结果【{result['unknown']}】次")
        print(f"有效率：{result['valid_rate']}")
        draw_report_card_v2(result["raw_data"], NAME)

    print("---查询结束---")

    choice = input("是否退出登录？(y/n)")
    if choice.lower() == "y":
        delete_cookie(choice)

    print("程序已结束。")


if __name__ == "__main__":
    main()
