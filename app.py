#!/usr/bin/env python3
"""
個人每日生活與飲食儀表板 (Personal Daily Life & Meal Dashboard)
主程式與 RESTful API / 靜態檔案伺服器 (Zero-Dependency Python 3 標準庫即可直接啟動)
"""
import json
import mimetypes
import os
import sys
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"

from backend.core.config import Config
from backend.core.database import init_db, get_settings, update_settings, cleanup_previous_days
from backend.core.module_registry import registry
from backend.core.scheduler import scheduler
from backend.modules.weather.service import weather_module
from backend.modules.dining.service import dining_module
from backend.modules.recipes.service import recipes_module

# 註冊三大核心生活模組（未來若新增高鐵時刻表、待辦清單、採買清單等模組，僅需在此處 registry.register(...)）
registry.register(weather_module)
registry.register(dining_module)
registry.register(recipes_module)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 簡潔的伺服器日誌輸出
        sys.stdout.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}\n")

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # 1. 系統與插件架構資訊 API
        if path == "/api/system/status":
            self._send_json({
                "status": "ok",
                "server_time": datetime.now().isoformat(),
                "scheduler_last_tick": scheduler.last_tick,
                "api_keys_configured": {
                    "cwa": Config.has_valid_key(Config.CWA_API_KEY),
                    "google_maps": Config.has_valid_key(Config.GOOGLE_MAPS_API_KEY),
                    "llm": Config.has_valid_key(Config.LLM_API_KEY),
                },
                "registered_modules": registry.list_metadata(),
                "settings": get_settings(),
            })
            return

        # 2. 使用者地點與座標偏好設定 API
        if path == "/api/settings":
            self._send_json({
                "settings": get_settings(),
                "locations": weather_module.get_locations(),
            })
            return

        # 3. 模組 1：中央氣象署 (CWA) 天氣預報 API
        if path == "/api/modules/weather":
            county = query.get("county", [None])[0]
            town = query.get("town", [None])[0]
            refresh = query.get("refresh", ["false"])[0].lower() == "true"
            data = weather_module.get_forecast(county=county, town=town, force_refresh=refresh)
            self._send_json(data)
            return

        # 4. 模組 2：住家周邊外食三選一 API
        if path == "/api/modules/dining":
            refresh_period = query.get("refresh", [None])[0]
            data = dining_module.get_today_recommendations(force_refresh_period=refresh_period)
            self._send_json(data)
            return

        # 5. 模組 3：每兩小時自煮正餐推薦與歷史紀錄 API
        if path == "/api/modules/recipes":
            refresh = query.get("refresh", ["false"])[0].lower() == "true"
            data = recipes_module.get_dashboard_data(force_generate_new=refresh)
            self._send_json(data)
            return

        # 靜態前端檔案服務
        self._serve_static(path)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json_body()

        # 更新地點與半徑設定
        if path == "/api/settings":
            updated = update_settings(body)
            # 若同時勾選重新整理氣象與外食推薦
            if body.get("refresh_modules", True):
                weather_module.get_forecast(county=updated["county"], town=updated["town"], force_refresh=True)
                dining_module.get_today_recommendations(force_refresh_period="all")
            self._send_json({"ok": True, "settings": updated})
            return

        # 手動觸發外食某時段重新抽選 3 間
        if path == "/api/modules/dining/refresh":
            period = body.get("period", "all")
            data = dining_module.get_today_recommendations(force_refresh_period=period)
            self._send_json(data)
            return

        # 手動觸發生成新一輪 5 道自煮正餐料理
        if path == "/api/modules/recipes/generate":
            slot_label = body.get("slot_time") or (datetime.now().strftime("%H:%M") + " 手動推薦")
            today_str = datetime.now().strftime("%Y-%m-%d")
            recipes_module.generate_batch(today_str, slot_label)
            data = recipes_module.get_dashboard_data(force_generate_new=False)
            self._send_json(data)
            return

        # 手動清理歷史紀錄
        if path == "/api/modules/recipes/cleanup":
            keep_latest = body.get("keep_latest", True)
            res = recipes_module.clear_today_history(keep_latest=keep_latest)
            data = recipes_module.get_dashboard_data(force_generate_new=False)
            self._send_json({"cleanup": res, "data": data})
            return

        self._send_json({"error": "Not found"}, status=404)

    def _serve_static(self, req_path: str):
        if req_path in ("/", ""):
            file_path = FRONTEND_DIR / "index.html"
        else:
            clean_rel = req_path.lstrip("/")
            file_path = (FRONTEND_DIR / clean_rel).resolve()
            if not str(file_path).startswith(str(FRONTEND_DIR.resolve())):
                self._send_json({"error": "Forbidden"}, status=403)
                return

        if not file_path.exists() or not file_path.is_file():
            self._send_json({"error": f"File not found: {req_path}"}, status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"
        if mime_type.startswith("text/") or mime_type in ("application/javascript", "application/json"):
            mime_type += "; charset=utf-8"

        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def run_server(port: int = None):
    init_db()
    scheduler.start()
    port = port or Config.PORT
    server = HTTPServer(("0.0.0.0", port), DashboardRequestHandler)
    print("=" * 68)
    print(" 🌿 個人每日生活與飲食儀表板 (Personal Daily Life & Meal Dashboard)")
    print(f" 🚀 伺服器已啟動： http://localhost:{port}")
    print(" 📦 已載入模組：", ", ".join([m["name"] for m in registry.list_metadata()]))
    print("=" * 68)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在關閉伺服器與排程器...")
        scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    run_server()
