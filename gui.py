import threading
import webbrowser
import base64
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import STATIC_DIR, BUNDLE_STATIC_DIR, TEMPLATES_DIR, load_config, setup_logging
from main import build_headers, get_semester_list_api, query_all_data
from draw_card import draw_report_card_v2
from fanclass_login import (
    login_with_qrcode,
    delete_cookies,
    load_cookies_from_file,
    verify_cookies,
    has_saved_cookies,
)

# ===== 全局状态 =====

app_state = {
    "token": None,
    "name": None,
    # 登录状态
    "login_status": "idle",  # idle | loading_qrcode | waiting_scan | success | failed
    "login_message": "",
    "login_abort": False,
    "qrcode_base64": None,  # 二维码 base64 数据（从 Selenium 截图获取）
    # 查询状态
    "query_status": "idle",  # idle | running | done | error
    "query_progress": 0,
    "query_total": 0,
    "query_message": "",
    "query_result": None,
    # 报告
    "report_path": None,
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = load_config()
    webbrowser.open(f"http://{cfg['host']}:{cfg['port']}")
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static/icon", StaticFiles(directory=str(BUNDLE_STATIC_DIR / "icon")), name="icon")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ===== 页面路由 =====


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ===== 登录相关 API =====


@app.get("/api/login/status")
async def login_status():
    """检查当前登录状态（通过 cookies.json 存在性快速判断）"""
    if app_state["token"] and app_state["name"]:
        return {
            "logged_in": True,
            "name": app_state["name"],
            "status": app_state["login_status"],
            "message": app_state["login_message"],
        }

    # 页面刷新时，中止正在进行的登录流程
    if app_state["login_status"] in ("loading_qrcode", "waiting_scan"):
        app_state["login_abort"] = True
        app_state["login_status"] = "idle"
        app_state["login_message"] = ""
        app_state["qrcode_base64"] = None

    # 仅检测 cookies.json 是否存在，不发 API 验证请求
    has_cookies, name = has_saved_cookies()
    return {
        "logged_in": False,
        "has_cookies": has_cookies,
        "name": name,
        "status": app_state["login_status"],
        "message": app_state["login_message"],
    }


@app.post("/api/login/reuse")
async def login_reuse():
    """复用已有 cookie"""
    saved_cookies = load_cookies_from_file()
    if not saved_cookies:
        return JSONResponse({"ok": False, "message": "没有已保存的登录信息"}, status_code=400)

    verify, nick = verify_cookies(saved_cookies)
    if verify:
        app_state["token"] = saved_cookies.get("token", "")
        app_state["name"] = nick
        app_state["login_status"] = "success"
        return {"ok": True, "name": nick}
    else:
        return JSONResponse({"ok": False, "message": "登录已过期，请重新扫码"}, status_code=401)


@app.post("/api/login/qrcode")
async def start_qrcode_login():
    """发起扫码登录"""
    if app_state["login_status"] in ("loading_qrcode", "waiting_scan"):
        return {"ok": True, "message": "登录流程已在进行中"}

    app_state["login_status"] = "loading_qrcode"
    app_state["login_message"] = "正在获取二维码..."
    app_state["login_abort"] = False
    app_state["qrcode_base64"] = None

    def on_qrcode(base64_data):
        if not app_state["login_abort"]:
            app_state["qrcode_base64"] = base64_data

    def should_abort():
        return app_state["login_abort"]

    def do_login():
        try:
            app_state["login_status"] = "waiting_scan"
            app_state["login_message"] = "请使用微信扫描二维码"
            cookies = login_with_qrcode(
                qrcode_callback=on_qrcode, abort_check=should_abort
            )

            if app_state["login_abort"]:
                return  # 已被取消，不更新状态

            if cookies:
                app_state["token"] = cookies.get("token", "")
                app_state["name"] = cookies.get("name", "")
                app_state["login_status"] = "success"
                app_state["login_message"] = f"登录成功：{app_state['name']}"
                app_state["qrcode_base64"] = None
            else:
                app_state["login_status"] = "failed"
                app_state["login_message"] = "登录失败或超时，请重试"
        except Exception as e:
            if not app_state["login_abort"]:
                app_state["login_status"] = "failed"
                app_state["login_message"] = f"登录出错: {str(e)}"

    thread = threading.Thread(target=do_login, daemon=True)
    thread.start()
    return {"ok": True, "message": "登录流程已启动"}


@app.get("/api/login/poll")
async def poll_login():
    """轮询登录状态"""
    return {
        "status": app_state["login_status"],
        "message": app_state["login_message"],
        "name": app_state["name"],
        "qrcode_ready": app_state["qrcode_base64"] is not None
        and app_state["login_status"] == "waiting_scan",
    }


@app.post("/api/login/logout")
async def logout():
    """退出登录"""
    delete_cookies()
    app_state["token"] = None
    app_state["name"] = None
    app_state["login_status"] = "idle"
    app_state["login_message"] = ""
    app_state["login_abort"] = True
    app_state["qrcode_base64"] = None
    app_state["query_result"] = None
    app_state["report_path"] = None
    return {"ok": True}


# ===== 查询相关 API =====


@app.get("/api/semesters")
async def get_semesters():
    """获取学期列表"""
    if not app_state["token"]:
        return JSONResponse({"error": "未登录"}, status_code=401)

    try:
        headers = build_headers(app_state["token"])
        semesters = get_semester_list_api(headers)
        return {"semesters": semesters}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/query")
async def start_query(request: Request):
    """开始查询"""
    if not app_state["token"]:
        return JSONResponse({"error": "未登录"}, status_code=401)

    body = await request.json()
    semester_name = body.get("semester")
    if not semester_name:
        return JSONResponse({"error": "请选择学期"}, status_code=400)

    if app_state["query_status"] == "running":
        return {"ok": True, "message": "查询已在进行中"}

    app_state["query_status"] = "running"
    app_state["query_progress"] = 0
    app_state["query_total"] = 0
    app_state["query_message"] = "正在开始查询..."
    app_state["query_result"] = None

    def progress_callback(current, total, message):
        app_state["query_progress"] = current
        app_state["query_total"] = total
        app_state["query_message"] = message

    def do_query():
        try:
            result = query_all_data(
                app_state["token"],
                app_state["name"],
                semester_name,
                progress_callback=progress_callback,
            )
            app_state["query_result"] = result
            app_state["query_status"] = "done"
            app_state["query_message"] = "查询完成"
        except Exception as e:
            app_state["query_status"] = "error"
            app_state["query_message"] = f"查询出错: {str(e)}"

    thread = threading.Thread(target=do_query, daemon=True)
    thread.start()
    return {"ok": True, "message": "查询已启动"}


@app.get("/api/query/status")
async def query_status():
    """查询进度轮询"""
    return {
        "status": app_state["query_status"],
        "progress": app_state["query_progress"],
        "total": app_state["query_total"],
        "message": app_state["query_message"],
    }


@app.get("/api/query/result")
async def query_result():
    """获取查询结果"""
    if app_state["query_result"] is None:
        return JSONResponse({"error": "暂无查询结果"}, status_code=404)
    return app_state["query_result"]


# ===== 报告相关 API =====


@app.post("/api/report/generate")
async def generate_report():
    """生成报告卡片"""
    result = app_state["query_result"]
    if not result or not result.get("raw_data"):
        return JSONResponse({"error": "没有数据可生成报告"}, status_code=400)

    try:
        draw_report_card_v2(result["raw_data"], result["name"])

        # 查找最新生成的报告文件
        report_dir = STATIC_DIR / "report_cards"
        if report_dir.exists():
            files = sorted(report_dir.glob("*.png"), key=os.path.getmtime, reverse=True)
            if files:
                app_state["report_path"] = str(files[0].name)
                return {"ok": True, "filename": files[0].name}

        return JSONResponse({"error": "报告生成失败"}, status_code=500)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/api/report/image/{filename}")
async def get_report_image(filename: str):
    """获取报告卡片图片"""
    filepath = STATIC_DIR / "report_cards" / filename
    if filepath.exists():
        return FileResponse(str(filepath), media_type="image/png")
    return JSONResponse({"error": "文件不存在"}, status_code=404)


# ===== 二维码图片 =====


@app.get("/api/qrcode")
async def get_qrcode():
    """获取二维码图片（从 Selenium 截图的 base64 数据）"""
    if app_state["qrcode_base64"]:
        img_data = base64.b64decode(app_state["qrcode_base64"])
        return Response(content=img_data, media_type="image/png")
    return JSONResponse({"error": "二维码不存在"}, status_code=404)


if __name__ == "__main__":
    import uvicorn

    setup_logging()

    try:
        cfg = load_config()
        print("=" * 50)
        print("  方课提问记录查询系统")
        print("  正在启动 Web 服务...")
        print(f"  浏览器将自动打开 http://{cfg['host']}:{cfg['port']}")
        print("=" * 50)
        uvicorn.run(app, host=cfg["host"], port=cfg["port"], log_config=None)
    except KeyboardInterrupt:
        print("\n服务已停止")
    except Exception as e:
        print(f"\n启动失败: {e}")
        import traceback
        traceback.print_exc()
        input("\n按回车键退出...")
