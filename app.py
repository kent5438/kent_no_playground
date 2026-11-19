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

from backend.core.config import Config, get_lan_ips
from backend.core.database import init_db, get_settings, update_settings, cleanup_previous_days
from backend.core.module_registry import registry
from backend.core.scheduler import scheduler
from backend.modules.weather.service import weather_module
from backend.modules.dining.service import dining_module
from backend.modules.recipes.service import recipes_module
from backend.modules.shopping.service import shopping_module

# 註冊四大核心與擴充生活模組
registry.register(weather_module)
registry.register(dining_module)
registry.register(recipes_module)
registry.register(shopping_module)


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
            lan_ips = get_lan_ips()
            port = Config.PORT
            self._send_json({
                "status": "ok",
                "server_time": datetime.now().isoformat(),
                "scheduler_last_tick": scheduler.last_tick,
                "network": {
                    "host": Config.HOST,
                    "port": port,
                    "bind_url": f"http://{Config.HOST}:{port}",
                    "lan_ips": lan_ips,
                    "lan_urls": [f"http://{ip}:{port}" for ip in lan_ips],
                },
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

        # 6. 模組 4：全方位智慧採買清單模組 API
        if path == "/api/modules/shopping":
            q = query.get("q", [""])[0]
            data = shopping_module.get_dashboard_data(history_query=q)
            self._send_json(data)
            return

        if path == "/api/modules/shopping/classify":
            name = query.get("name", [""])[0]
            res = shopping_module.classify_category(name, use_llm=True)
            self._send_json(res)
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

        # 模組 4：新增採買品項
        if path == "/api/modules/shopping/items":
            name = (body.get("name") or "").strip()
            if not name:
                self._send_json({"ok": False, "error": "請輸入品項名稱"}, status=400)
                return
            added = shopping_module.add_item(
                name=name,
                quantity_note=body.get("quantity_note", ""),
                category=body.get("category"),
                location=body.get("location", "全聯"),
                urgency=body.get("urgency", "normal"),
                source_recipe=body.get("source_recipe", ""),
            )
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": True, "added": added, "data": data})
            return

        # 模組 4：更新待買品項（修改分類、地點、急迫性、名稱或備註）
        if path == "/api/modules/shopping/items/update":
            item_id = int(body.get("id", 0))
            res = shopping_module.update_item(item_id, body)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "result": res, "data": data})
            return

        # 模組 4：勾選「已購買」歸檔至歷史紀錄
        if path == "/api/modules/shopping/items/complete":
            item_id = int(body.get("id", 0))
            price = body.get("price")
            res = shopping_module.complete_item(item_id, price=price)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "completed": res, "data": data})
            return

        # 模組 4：刪除待買品項
        if path == "/api/modules/shopping/items/delete":
            item_id = int(body.get("id", 0))
            res = shopping_module.delete_item(item_id)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "data": data})
            return

        # 模組 4：從自煮食譜一鍵匯入食材
        if path == "/api/modules/shopping/import-recipe":
            res = shopping_module.import_from_recipe(
                recipe_title=body.get("recipe_title", ""),
                ingredients=body.get("ingredients", []),
                include_seasonings=bool(body.get("include_seasonings", False)),
                seasonings=body.get("seasonings", []),
                location=body.get("location", "全聯"),
                urgency=body.get("urgency", "urgent"),
            )
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": True, "imported": res, "data": data})
            return

        # 模組 4：從歷史紀錄「🔄 再次購買」
        if path == "/api/modules/shopping/history/repurchase":
            history_id = int(body.get("history_id", 0))
            urgency = body.get("urgency")
            res = shopping_module.repurchase_from_history(history_id, urgency=urgency)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "repurchased": res, "data": data})
            return

        # 模組 4：更新歷史紀錄購入金額
        if path == "/api/modules/shopping/history/price":
            history_id = int(body.get("history_id", 0))
            price = body.get("price")
            res = shopping_module.update_history_price(history_id, price)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "result": res, "data": data})
            return

        # 模組 4：刪除單筆歷史紀錄
        if path == "/api/modules/shopping/history/delete":
            history_id = int(body.get("history_id", 0))
            res = shopping_module.delete_history_item(history_id)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": res.get("ok", False), "data": data})
            return

        # 模組 4：管理常用地點清單（新增 / 釘選切換 / 刪除記憶地點）
        if path == "/api/modules/shopping/locations":
            action = body.get("action", "add")
            loc_name = (body.get("name") or "").strip()
            res = {"ok": False}
            if action == "add" and loc_name:
                res = shopping_module.remember_location(
                    loc_name,
                    is_pinned=True,
                    custom_url=(body.get("search_url_template") or "").strip(),
                )
                res["ok"] = True
            elif action == "delete" and loc_name:
                res = shopping_module.delete_location(loc_name)
            elif action == "toggle_pin" and loc_name:
                res = shopping_module.toggle_pin_location(loc_name)
            data = shopping_module.get_dashboard_data(history_query=body.get("history_query", ""))
            self._send_json({"ok": True, "location_result": res, "data": data})
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


def run_server(port: int = None, host: str = None):
    init_db()
    scheduler.start()
    host = host or Config.HOST  # 一律綁定為 0.0.0.0
    port = port or Config.PORT
    lan_ips = get_lan_ips()
    server = HTTPServer((host, port), DashboardRequestHandler)
    print("=" * 72)
    print(" 🌿 個人每日生活與飲食儀表板 (Personal Daily Life & Meal Dashboard)")
    print(f" 🌐 網路綁定設定： Host 已綁定為 {host}:{port} (已開放區網跨裝置連線)")
    print(f" 💻 本機瀏覽網址： http://0.0.0.0:{port}")
    if lan_ips:
        print(" 📱 區網連線提示（手機 / 平板 / 同網路下其他裝置請直接開啟以下網址）：")
        for ip in lan_ips:
            print(f"    👉 http://{ip}:{port}")
    else:
        print(f" 📱 區網連線提示：請使用本機區網 IP 連線 http://<您的區網IP>:{port}")
    print(" 📦 已載入模組：", ", ".join([m["name"] for m in registry.list_metadata()]))
    print("=" * 72)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n正在關閉伺服器與排程器...")
        scheduler.stop()
        server.server_close()


if __name__ == "__main__":
    run_server()
