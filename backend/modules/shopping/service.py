"""
Module 4: 全方位智慧採買清單模組（不限品類）
- 通用物品新增：不限於食材，支援新增任何生活採買項目（生鮮食材、日用清潔、居家百貨、3C家電、零食飲料、藥妝保健、其他），並支援從自煮食譜一鍵匯入食材。
- 自動商品類型判斷：新增品項時，透過規則庫或 LLM 自動判斷並標記商品類型標籤，也支援手動修改分類。
- 自訂地點清單與記憶功能：支援自由輸入採買地點，自動記憶所有過去輸入過的地點（提供下拉快選與 Autocomplete，支援管理常用地點清單）；若地點為網購平台（如 momo、蝦皮等），自動產生帶入商品名稱的「快速搜尋連結」。
- 急迫性分級與雙檢視模式：支援 🔴 緊急（今日必買）、🟡 一般（近期購買）、🟢 不急（順路/特價再買），預設依急迫性高低排序，並支援「依急迫性檢視」與「依購買地點分組檢視」一鍵切換。
- 已購買歸檔與歷史紀錄：勾選「已購買」後自動轉存至「採買歷史紀錄」（記錄購買日期、品項、分類、購買地點與選填購入金額），支援關鍵字搜尋與「🔄 再次購買」一鍵重新加入待買清單。
"""
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.core.config import Config
from backend.core.database import get_db
from backend.core.module_registry import BaseModule

# 商品類型標籤清單
SHOPPING_CATEGORIES: List[str] = [
    "🥬 生鮮食材",
    "🧻 日用清潔",
    "🏠 居家百貨",
    "🔌 3C家電",
    "🍿 零食飲料",
    "💊 藥妝保健",
    "📦 其他",
]

# 急迫性分級設定（預設依 rank 高低排序：3 -> 2 -> 1）
URGENCY_LEVELS: Dict[str, Dict[str, Any]] = {
    "urgent": {
        "code": "urgent",
        "label": "🔴 緊急（今日必買）",
        "short_label": "🔴 緊急",
        "badge_class": "urgency-urgent",
        "rank": 3,
    },
    "normal": {
        "code": "normal",
        "label": "🟡 一般（近期購買）",
        "short_label": "🟡 一般",
        "badge_class": "urgency-normal",
        "rank": 2,
    },
    "low": {
        "code": "low",
        "label": "🟢 不急（順路/特價再買）",
        "short_label": "🟢 不急",
        "badge_class": "urgency-low",
        "rank": 1,
    },
}

# 自動商品類型判斷規則關鍵字庫
CATEGORY_KEYWORD_RULES: Dict[str, List[str]] = {
    "🔌 3C家電": [
        "充電線", "type-c", "typec", "lightning", "usb", "hdmi", "網路線", "轉接頭", "hub",
        "充電頭", "快充", "行動電源", "充電器", "耳機", "airpods", "藍牙", "喇叭", "音響",
        "滑鼠", "鍵盤", "螢幕", "顯示器", "筆電", "電腦", "平板", "ipad", "iphone", "手機",
        "保護貼", "手機殼", "支架", "記憶卡", "sd卡", "隨身碟", "硬碟", "ssd", "路由器",
        "wifi", "wi-fi", "分享器", "交換器", "延長線", "插座", "電池", "鈕扣電池", "鹼性電池",
        "吹風機", "電風扇", "循環扇", "吸塵器", "掃地機器人", "除濕機", "空氣清淨機", "濾網",
        "電鍋", "電子鍋", "氣炸鍋", "微波爐", "烤箱", "電磁爐", "快煮壺", "熱水瓶", "刮鬍刀",
        "電動牙刷", "檯燈", "燈泡", "led燈", "相機", "鏡頭", "手錶", "智慧手錶", "遙控器", "3c"
    ],
    "🧻 日用清潔": [
        "衛生紙", "面紙", "抽取式", "廚房紙巾", "擦手紙", "濕紙巾", "酒精濕巾", "化妝棉",
        "洗衣精", "洗衣球", "洗衣膠囊", "洗衣粉", "柔軟精", "漂白水", "去漬", "衣領精",
        "洗碗精", "洗潔精", "蔬果洗潔", "洗手乳", "沐浴乳", "洗髮精", "潤髮乳", "護髮",
        "洗面乳", "肥皂", "香皂", "牙膏", "牙刷", "牙線", "牙線棒", "漱口水", "垃圾袋",
        "菜瓜布", "海綿", "科技海綿", "抹布", "拖把", "掃把", "除塵紙", "黏塵紙", "滾輪",
        "除濕盒", "除濕袋", "克潮靈", "芳香劑", "消臭", "除臭", "防蚊", "殺蟲劑", "蟑螂藥",
        "螞蟻藥", "清潔劑", "浴廁清潔", "馬桶清潔", "威猛先生", "魔術靈", "小蘇打粉", "檸檬酸",
        "過碳酸鈉", "酒精", "乾洗手", "衛生棉", "護墊", "棉條", "紙尿褲", "尿布", "潔衣"
    ],
    "💊 藥妝保健": [
        "維他命", "維生素", "b群", "魚油", "益生菌", "葉黃素", "鈣片", "鎂", "鋅", "鐵劑",
        "膠原蛋白", "酵素", "蔓越莓", "雞精", "滴雞精", "人蔘", "蜆精", "感冒藥", "普拿疼",
        "止痛藥", "退燒", "腸胃藥", "胃散", "若元錠", "表飛鳴", "止瀉", "過敏藥", "眼藥水",
        "人工淚液", "生理食鹽水", "優碘", "雙氧水", "ok繃", "創可貼", "紗布", "棉棒", "棉花棒",
        "透氣膠帶", "醫療口罩", "口罩", "酸痛貼布", "撒隆巴斯", "藥膏", "小護士", "曼秀雷敦",
        "護手霜", "乳液", "身體乳", "化妝水", "精華液", "眼霜", "面霜", "面膜", "防曬",
        "隔離霜", "粉底", "口紅", "護唇膏", "卸妝水", "卸妝油", "卸妝乳", "痘痘貼", "隱形眼鏡",
        "保養液", "體溫計", "血壓計", "藥妝", "保健"
    ],
    "🏠 居家百貨": [
        "收納盒", "收納箱", "收納籃", "整理箱", "衣架", "曬衣夾", "曬衣架", "洗衣網", "洗衣袋",
        "掛勾", "無痕掛勾", "置物架", "層架", "保鮮盒", "便當盒", "密封袋", "保鮮膜", "鋁箔紙",
        "烘焙紙", "保鮮袋", "夾鏈袋", "水壺", "保溫杯", "保溫瓶", "馬克杯", "玻璃杯", "冷水壺",
        "碗", "餐盤", "盤子", "筷子", "湯匙", "叉子", "餐具", "吸管", "平底鍋", "炒鍋", "湯鍋",
        "鍋蓋", "砧板", "菜刀", "水果刀", "削皮刀", "剪刀", "開瓶器", "鍋鏟", "湯勺", "濾網",
        "枕頭", "枕頭套", "床包", "床單", "被套", "棉被", "涼被", "毛毯", "毛巾", "浴巾",
        "腳踏墊", "地墊", "巧拼", "拖鞋", "室內拖", "雨傘", "折疊傘", "雨衣", "鞋櫃", "椅子",
        "坐墊", "靠墊", "窗簾", "門簾", "五金", "螺絲", "起子", "扳手", "鎚子", "捲尺", "美工刀",
        "膠帶", "雙面膠", "三秒膠", "瞬間膠", "電池", "打火機", "瓦斯罐", "筆記本", "原子筆",
        "便利貼", "資料夾", "信封", "膠水", "貓砂", "寵物", "飼料", "花盆", "培養土"
    ],
    "🍿 零食飲料": [
        "洋芋片", "餅乾", "蘇打餅", "仙貝", "米果", "爆米花", "巧克力", "糖果", "軟糖", "喉糖",
        "口香糖", "堅果", "杏仁", "腰果", "核桃", "開心果", "瓜子", "花生", "海苔", "肉乾",
        "豬肉乾", "牛肉乾", "魷魚絲", "鱈魚香絲", "豆乾", "泡麵", "科學麵", "王子麵", "乾拌麵",
        "杯麵", "布丁", "果凍", "愛玉", "仙草", "冰淇淋", "雪糕", "冰棒", "蛋糕", "蛋捲", "鳳梨酥",
        "甜點", "零食", "零嘴", "可樂", "雪碧", "汽水", "沙士", "氣泡水", "礦泉水", "飲用水",
        "綠茶", "紅茶", "烏龍茶", "麥茶", "奶茶", "鮮奶茶", "茶葉", "茶包", "咖啡", "咖啡豆",
        "濾掛咖啡", "即溶咖啡", "拿鐵", "美式咖啡", "果汁", "柳橙汁", "蘋果汁", "運動飲料",
        "舒跑", "寶礦力", "能量飲", "啤酒", "紅酒", "白酒", "梅酒", "威士忌", "清酒", "燕麥奶",
        "杏仁奶", "可可", "阿華田", "美祿", "麥片", "穀片"
    ],
    "🥬 生鮮食材": [
        "豬", "松阪豬", "梅花豬", "五花肉", "里肌", "絞肉", "排骨", "鹹豬肉", "大腸", "培根", "火腿", "香腸", "貢丸",
        "牛", "牛肉", "牛排", "骰子牛", "牛肋", "牛五花", "牛腱",
        "雞", "雞腿", "雞胸", "雞柳", "雞翅", "雞肉", "雞蛋", "皮蛋", "鹹蛋", "鹹鴨蛋", "鳥蛋", "蛋",
        "魚", "鱸魚", "鮭魚", "鯛魚", "鯖魚", "鱈魚", "秋刀魚", "吳郭魚", "虱目魚", "吻仔魚", "魚排",
        "蝦", "蝦仁", "白蝦", "草蝦", "透抽", "中卷", "小卷", "魷魚", "蛤蜊", "文蛤", "蚵仔", "牡蠣", "干貝", "海鮮",
        "豆腐", "嫩豆腐", "板豆腐", "百頁豆腐", "豆干", "豆皮", "豆包", "豆漿",
        "青蔥", "蔥", "蒜", "蒜頭", "蒜瓣", "蒜苗", "薑", "老薑", "嫩薑", "辣椒", "九層塔", "香菜", "芹菜", "洋蔥",
        "高麗菜", "空心菜", "地瓜葉", "青江菜", "大陸妹", "A菜", "菠菜", "小白菜", "大白菜", "娃娃菜", "水蓮", "花椰菜",
        "青花菜", "苦瓜", "白玉苦瓜", "絲瓜", "小黃瓜", "大黃瓜", "櫛瓜", "茄子", "南瓜", "冬瓜", "番茄", "牛番茄",
        "小番茄", "紅蘿蔔", "白蘿蔔", "馬鈴薯", "地瓜", "山藥", "芋頭", "玉米", "玉米筍", "秋葵", "四季豆", "毛豆",
        "甜椒", "青椒", "彩椒", "高麗菜", "酸菜", "泡菜", "筍", "竹筍", "蘆筍", "蓮藕", "木耳", "海帶", "昆布",
        "菇", "杏鮑菇", "香菇", "鮮香菇", "乾香菇", "金針菇", "鴻喜菇", "雪白菇", "秀珍菇", "蘑菇",
        "水果", "蘋果", "香蕉", "芭樂", "奇異果", "木瓜", "西瓜", "鳳梨", "葡萄", "草莓", "藍莓", "柳丁", "橘子", "檸檬",
        "酪梨", "水蜜桃", "櫻桃", "火龍果", "芒果", "文旦", "梨子",
        "鮮奶", "牛奶", "保久乳", "優格", "優酪乳", "起司", "乳酪", "奶油", "無鹽奶油", "鮮奶油",
        "白米", "糙米", "糯米", "米", "麵條", "烏龍麵", "意麵", "義大利麵", "冬粉", "米粉", "吐司", "麵包", "饅頭",
        "水餃", "蔥油餅", "蛋餅皮", "湯圓", "年糕",
        "醬油", "醬油膏", "薄鹽醬油", "蠔油", "素蠔油", "米酒", "味醂", "魚露", "烏醋", "白醋", "果醋", "檸檬汁",
        "砂糖", "細砂糖", "冰糖", "黑糖", "鹽", "鹽巴", "海鹽", "胡椒", "白胡椒", "黑胡椒", "太白粉", "地瓜粉", "麵粉",
        "玉米粉", "香油", "麻油", "黑麻油", "橄欖油", "沙拉油", "葵花油", "食用油", "花椒油", "辣油", "豆瓣醬",
        "辣豆瓣醬", "甜麵醬", "沙茶醬", "番茄醬", "美乃滋", "胡麻醬", "破布子", "豆腐乳", "芝麻", "白芝麻", "柴魚", "高湯"
    ],
}

# 網購平台識別與快速搜尋連結規則庫
ONLINE_PLATFORM_RULES: List[Dict[str, Any]] = [
    {
        "keywords": ["momo", "富邦momo"],
        "platform_name": "momo購物網",
        "url_template": "https://www.momoshop.com.tw/search/searchShop.jsp?keyword={q}",
        "icon": "🛍️",
    },
    {
        "keywords": ["蝦皮", "shopee"],
        "platform_name": "蝦皮購物",
        "url_template": "https://shopee.tw/search?keyword={q}",
        "icon": "🧡",
    },
    {
        "keywords": ["pchome", "pc home"],
        "platform_name": "PChome 24h",
        "url_template": "https://24h.pchome.com.tw/search/?q={q}",
        "icon": "📦",
    },
    {
        "keywords": ["酷澎", "coupang"],
        "platform_name": "Coupang 酷澎",
        "url_template": "https://www.tw.coupang.com/np/search?q={q}",
        "icon": "🚀",
    },
    {
        "keywords": ["博客來", "books"],
        "platform_name": "博客來",
        "url_template": "https://search.books.com.tw/search/query/key/{q}",
        "icon": "📚",
    },
    {
        "keywords": ["yahoo", "奇摩購物"],
        "platform_name": "Yahoo購物中心",
        "url_template": "https://tw.buy.yahoo.com/search/product?p={q}",
        "icon": "🟣",
    },
    {
        "keywords": ["淘寶", "天貓", "taobao", "tmall"],
        "platform_name": "淘寶網",
        "url_template": "https://s.taobao.com/search?q={q}",
        "icon": "🌏",
    },
    {
        "keywords": ["amazon", "亞馬遜"],
        "platform_name": "Amazon",
        "url_template": "https://www.amazon.com/s?k={q}",
        "icon": "🛒",
    },
]

# 預設常用採買地點清單
DEFAULT_LOCATIONS: List[Dict[str, Any]] = [
    {"name": "全聯", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 8},
    {"name": "好市多", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 6},
    {"name": "momo購物網", "is_online": 1, "search_url_template": "https://www.momoshop.com.tw/search/searchShop.jsp?keyword={q}", "is_pinned": 1, "usage_count": 6},
    {"name": "蝦皮購物", "is_online": 1, "search_url_template": "https://shopee.tw/search?keyword={q}", "is_pinned": 1, "usage_count": 5},
    {"name": "宜得利", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 4},
    {"name": "五金行", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 3},
    {"name": "竹東傳統市場", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 4},
    {"name": "屈臣氏 / 康是美", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 3},
    {"name": "PChome 24h", "is_online": 1, "search_url_template": "https://24h.pchome.com.tw/search/?q={q}", "is_pinned": 1, "usage_count": 2},
    {"name": "家樂福", "is_online": 0, "search_url_template": "", "is_pinned": 1, "usage_count": 2},
]


def clean_search_keyword(raw_name: str) -> str:
    """移除食材處理括號註記（如：松阪豬肉（逆紋斜切片） -> 松阪豬肉），讓網購搜尋更精準。"""
    if not raw_name:
        return ""
    cleaned = re.sub(r"[\(（][^\)）]*[\)）]", "", raw_name).strip()
    return cleaned or raw_name.strip()


def detect_online_platforms(location_name: str, custom_template: str = "") -> List[Dict[str, str]]:
    """判斷地點是否為網購平台，並回傳對應的搜尋模板清單。"""
    if not location_name:
        return []
    loc_lower = location_name.lower()
    matched = []
    for rule in ONLINE_PLATFORM_RULES:
        if any(kw in loc_lower for kw in rule["keywords"]):
            matched.append({
                "platform_name": rule["platform_name"],
                "url_template": rule["url_template"],
                "icon": rule["icon"],
            })
    if not matched and custom_template and "{q}" in custom_template:
        matched.append({
            "platform_name": location_name,
            "url_template": custom_template,
            "icon": "🔗",
        })
    return matched


def build_online_search_links(item_name: str, location_name: str, custom_template: str = "") -> List[Dict[str, str]]:
    """若地點為網購平台（如 momo、蝦皮），自動產生帶入該商品名稱的快速搜尋連結。"""
    platforms = detect_online_platforms(location_name, custom_template)
    if not platforms:
        return []
    keyword = clean_search_keyword(item_name)
    encoded_q = urllib.parse.quote(keyword)
    links = []
    for p in platforms:
        url = p["url_template"].replace("{q}", encoded_q)
        links.append({
            "platform": p["platform_name"],
            "icon": p["icon"],
            "keyword": keyword,
            "url": url,
            "label": f"{p['icon']} {p['platform_name']}搜「{keyword}」",
        })
    return links


class ShoppingModule(BaseModule):
    module_id = "shopping"
    name = "全方位智慧採買清單模組（不限品類）"
    description = (
        "支援任何生活品項與自煮食譜一鍵匯入、規則庫/LLM 自動分類、自訂地點記憶與網購快速搜尋連結、"
        "急迫性分級與地點分組雙檢視模式、已購買歸檔歷史與再次購買。"
    )

    def on_startup(self) -> None:
        self._ensure_seed_data()

    def _ensure_seed_data(self) -> None:
        """首次啟動時初始化預設常用地點與示範採買項目，開箱即用。"""
        now_iso = datetime.now().isoformat()
        today_str = datetime.now().strftime("%Y-%m-%d")
        with get_db() as conn:
            loc_count = conn.execute("SELECT COUNT(*) AS c FROM shopping_locations").fetchone()["c"]
            if loc_count == 0:
                for loc in DEFAULT_LOCATIONS:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO shopping_locations
                        (name, is_online, search_url_template, is_pinned, usage_count, last_used_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            loc["name"],
                            loc["is_online"],
                            loc["search_url_template"],
                            loc["is_pinned"],
                            loc["usage_count"],
                            now_iso,
                        ),
                    )

            item_count = conn.execute("SELECT COUNT(*) AS c FROM shopping_items").fetchone()["c"]
            hist_count = conn.execute("SELECT COUNT(*) AS c FROM shopping_history").fetchone()["c"]
            if item_count == 0 and hist_count == 0:
                seed_items = [
                    {
                        "name": "松阪豬肉",
                        "quantity_note": "220 克（晚餐自煮食材）",
                        "category": "🥬 生鮮食材",
                        "auto_categorized": 1,
                        "location": "全聯",
                        "urgency": "urgent",
                        "urgency_rank": 3,
                        "source_recipe": "蔥爆嫩煎松阪豬",
                    },
                    {
                        "name": "青蔥與蒜頭",
                        "quantity_note": "青蔥 1 把、蒜頭 1 袋",
                        "category": "🥬 生鮮食材",
                        "auto_categorized": 1,
                        "location": "全聯",
                        "urgency": "urgent",
                        "urgency_rank": 3,
                        "source_recipe": "蔥爆嫩煎松阪豬",
                    },
                    {
                        "name": "三層抽取式衛生紙 (24包/袋)",
                        "quantity_note": "1 大袋（家用庫存見底）",
                        "category": "🧻 日用清潔",
                        "auto_categorized": 1,
                        "location": "好市多",
                        "urgency": "urgent",
                        "urgency_rank": 3,
                        "source_recipe": "",
                    },
                    {
                        "name": "Type-C 100W 編織快充充電線",
                        "quantity_note": "2 公尺 x 1 條",
                        "category": "🔌 3C家電",
                        "auto_categorized": 1,
                        "location": "蝦皮購物",
                        "urgency": "normal",
                        "urgency_rank": 2,
                        "source_recipe": "",
                    },
                    {
                        "name": "除濕機 HEPA 替換濾網",
                        "quantity_note": "1 組（滿額免運入手）",
                        "category": "🔌 3C家電",
                        "auto_categorized": 1,
                        "location": "momo購物網",
                        "urgency": "normal",
                        "urgency_rank": 2,
                        "source_recipe": "",
                    },
                    {
                        "name": "矽膠防滑隔熱鍋墊與保鮮盒組",
                        "quantity_note": "玻璃保鮮盒 600ml x 2",
                        "category": "🏠 居家百貨",
                        "auto_categorized": 1,
                        "location": "宜得利",
                        "urgency": "low",
                        "urgency_rank": 1,
                        "source_recipe": "",
                    },
                    {
                        "name": "無調味綜合堅果 & 濾掛咖啡",
                        "quantity_note": "辦公室下午茶補給",
                        "category": "🍿 零食飲料",
                        "auto_categorized": 1,
                        "location": "好市多",
                        "urgency": "low",
                        "urgency_rank": 1,
                        "source_recipe": "",
                    },
                ]
                for it in seed_items:
                    conn.execute(
                        """
                        INSERT INTO shopping_items
                        (name, quantity_note, category, auto_categorized, location, urgency, urgency_rank, source_recipe, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            it["name"],
                            it["quantity_note"],
                            it["category"],
                            it["auto_categorized"],
                            it["location"],
                            it["urgency"],
                            it["urgency_rank"],
                            it["source_recipe"],
                            now_iso,
                            now_iso,
                        ),
                    )

                seed_history = [
                    {
                        "name": "牧場鮮奶 1858ml",
                        "quantity_note": "1 瓶",
                        "category": "🥬 生鮮食材",
                        "location": "全聯",
                        "urgency": "urgent",
                        "price": 179.0,
                        "purchased_date": today_str,
                        "purchased_at": now_iso,
                    },
                    {
                        "name": "高單位維他命 B群 + 葉黃素膠囊",
                        "quantity_note": "60 粒裝",
                        "category": "💊 藥妝保健",
                        "location": "momo購物網",
                        "urgency": "normal",
                        "price": 580.0,
                        "purchased_date": today_str,
                        "purchased_at": now_iso,
                    },
                    {
                        "name": "濃縮抗菌洗衣精補充包",
                        "quantity_note": "1600g x 2 包",
                        "category": "🧻 日用清潔",
                        "location": "全聯",
                        "urgency": "normal",
                        "price": 218.0,
                        "purchased_date": today_str,
                        "purchased_at": now_iso,
                    },
                ]
                for h in seed_history:
                    conn.execute(
                        """
                        INSERT INTO shopping_history
                        (name, quantity_note, category, location, urgency, price, purchased_date, purchased_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            h["name"],
                            h["quantity_note"],
                            h["category"],
                            h["location"],
                            h["urgency"],
                            h["price"],
                            h["purchased_date"],
                            h["purchased_at"],
                        ),
                    )

    def classify_category(self, item_name: str, use_llm: bool = True) -> Dict[str, str]:
        """
        透過規則庫或 LLM 自動判斷商品類型標籤。
        優先順序：精準關鍵字規則庫 -> LLM API (若有設定) -> 預設『📦 其他』
        """
        if not item_name or not item_name.strip():
            return {"category": "📦 其他", "method": "default", "matched_keyword": ""}

        text = item_name.strip().lower()

        # 尋找最長匹配關鍵字，避免短字誤判（例如「醬油膏」vs「牙膏」）
        best_cat = None
        best_kw = ""
        for cat, keywords in CATEGORY_KEYWORD_RULES.items():
            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in text and len(kw_lower) > len(best_kw):
                    best_cat = cat
                    best_kw = kw

        if best_cat:
            return {"category": best_cat, "method": "rule", "matched_keyword": best_kw}

        if use_llm and Config.has_valid_key(Config.LLM_API_KEY):
            llm_cat = self._classify_via_llm(item_name)
            if llm_cat in SHOPPING_CATEGORIES:
                return {"category": llm_cat, "method": "llm", "matched_keyword": "AI 語意推論"}

        return {"category": "📦 其他", "method": "default", "matched_keyword": ""}

    def _classify_via_llm(self, item_name: str) -> Optional[str]:
        """當規則庫未命中且已設定 LLM_API_KEY 時，使用 LLM 自動判斷商品分類。"""
        try:
            cats_str = "、".join(SHOPPING_CATEGORIES)
            prompt = (
                f"請將採買項目「{item_name}」歸類至以下其中一個分類：{cats_str}。"
                "請只回傳該分類的完整字串（含 Emoji），不要有任何其他文字。"
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.LLM_MODEL}:generateContent?key={Config.LLM_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                ans = result["candidates"][0]["content"]["parts"][0]["text"].strip()
                for c in SHOPPING_CATEGORIES:
                    if c in ans or c.split(" ", 1)[-1] in ans:
                        return c
        except Exception:
            pass
        return None

    def remember_location(self, location_name: str, is_pinned: Optional[bool] = None, custom_url: str = "") -> Dict[str, Any]:
        """自動記憶使用者輸入過的採買地點，並判斷是否為網購平台。"""
        loc = (location_name or "全聯").strip() or "全聯"
        now_iso = datetime.now().isoformat()
        platforms = detect_online_platforms(loc, custom_url)
        is_online = 1 if platforms else 0
        url_template = platforms[0]["url_template"] if platforms else custom_url

        with get_db() as conn:
            existing = conn.execute(
                "SELECT name, is_online, search_url_template, is_pinned, usage_count FROM shopping_locations WHERE name = ?",
                (loc,),
            ).fetchone()
            if existing:
                new_count = existing["usage_count"] + 1
                pinned_val = (1 if is_pinned else 0) if is_pinned is not None else existing["is_pinned"]
                tpl_val = custom_url or existing["search_url_template"] or url_template
                online_val = 1 if (is_online or tpl_val) else existing["is_online"]
                conn.execute(
                    """
                    UPDATE shopping_locations
                    SET usage_count = ?, is_pinned = ?, is_online = ?, search_url_template = ?, last_used_at = ?
                    WHERE name = ?
                    """,
                    (new_count, pinned_val, online_val, tpl_val, now_iso, loc),
                )
            else:
                pinned_val = 1 if is_pinned is None or is_pinned else 0
                conn.execute(
                    """
                    INSERT INTO shopping_locations
                    (name, is_online, search_url_template, is_pinned, usage_count, last_used_at)
                    VALUES (?, ?, ?, ?, 1, ?)
                    """,
                    (loc, is_online, url_template, pinned_val, now_iso),
                )
        return {"name": loc, "is_online": bool(is_online), "search_url_template": url_template}

    def get_locations(self) -> List[Dict[str, Any]]:
        self._ensure_seed_data()
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT name, is_online, search_url_template, is_pinned, usage_count, last_used_at
                FROM shopping_locations
                ORDER BY is_pinned DESC, usage_count DESC, last_used_at DESC
                """
            ).fetchall()
        result = []
        for r in rows:
            platforms = detect_online_platforms(r["name"], r["search_url_template"])
            result.append({
                "name": r["name"],
                "is_online": bool(r["is_online"] or platforms),
                "search_url_template": r["search_url_template"] or (platforms[0]["url_template"] if platforms else ""),
                "is_pinned": bool(r["is_pinned"]),
                "usage_count": r["usage_count"],
                "last_used_at": r["last_used_at"],
            })
        return result

    def delete_location(self, location_name: str) -> Dict[str, Any]:
        with get_db() as conn:
            deleted = conn.execute("DELETE FROM shopping_locations WHERE name = ?", (location_name,)).rowcount
        return {"deleted": deleted > 0, "name": location_name}

    def toggle_pin_location(self, location_name: str) -> Dict[str, Any]:
        with get_db() as conn:
            row = conn.execute("SELECT is_pinned FROM shopping_locations WHERE name = ?", (location_name,)).fetchone()
            if not row:
                return {"ok": False}
            new_pin = 0 if row["is_pinned"] else 1
            conn.execute("UPDATE shopping_locations SET is_pinned = ? WHERE name = ?", (new_pin, location_name))
        return {"ok": True, "name": location_name, "is_pinned": bool(new_pin)}

    def _enrich_item(self, row_dict: Dict[str, Any], loc_map: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        urg_code = row_dict.get("urgency", "normal")
        urg_info = URGENCY_LEVELS.get(urg_code, URGENCY_LEVELS["normal"])
        loc_name = row_dict.get("location", "全聯") or "全聯"
        custom_tpl = loc_map.get(loc_name, {}).get("search_url_template", "")
        search_links = build_online_search_links(row_dict["name"], loc_name, custom_tpl)
        return {
            "id": row_dict["id"],
            "name": row_dict["name"],
            "quantity_note": row_dict.get("quantity_note", ""),
            "category": row_dict["category"],
            "auto_categorized": bool(row_dict.get("auto_categorized", 1)),
            "location": loc_name,
            "is_online_location": len(search_links) > 0,
            "online_search_links": search_links,
            "urgency": urg_info["code"],
            "urgency_label": urg_info["label"],
            "urgency_short": urg_info["short_label"],
            "urgency_rank": urg_info["rank"],
            "source_recipe": row_dict.get("source_recipe", ""),
            "created_at": row_dict.get("created_at", ""),
            "updated_at": row_dict.get("updated_at", ""),
        }

    def get_dashboard_data(self, history_query: str = "") -> Dict[str, Any]:
        self._ensure_seed_data()
        locations = self.get_locations()
        loc_map = {l["name"]: l for l in locations}

        with get_db() as conn:
            # 預設依急迫性高低排序 (urgency_rank DESC, id DESC)
            item_rows = conn.execute(
                """
                SELECT id, name, quantity_note, category, auto_categorized, location,
                       urgency, urgency_rank, source_recipe, created_at, updated_at
                FROM shopping_items
                ORDER BY urgency_rank DESC, id DESC
                """
            ).fetchall()

            q_clean = (history_query or "").strip()
            if q_clean:
                like_pat = f"%{q_clean}%"
                hist_rows = conn.execute(
                    """
                    SELECT id, name, quantity_note, category, location, urgency, price, purchased_date, purchased_at
                    FROM shopping_history
                    WHERE name LIKE ? OR category LIKE ? OR location LIKE ? OR quantity_note LIKE ?
                    ORDER BY id DESC
                    LIMIT 100
                    """,
                    (like_pat, like_pat, like_pat, like_pat),
                ).fetchall()
            else:
                hist_rows = conn.execute(
                    """
                    SELECT id, name, quantity_note, category, location, urgency, price, purchased_date, purchased_at
                    FROM shopping_history
                    ORDER BY id DESC
                    LIMIT 100
                    """
                ).fetchall()

            total_hist_row = conn.execute(
                "SELECT COUNT(*) AS cnt, COALESCE(SUM(price), 0) AS total_spent FROM shopping_history"
            ).fetchone()

        items = [self._enrich_item(dict(r), loc_map) for r in item_rows]

        # 建立「依購買地點分組檢視」結構（方便到達特定賣場時集中查看該店待買清單）
        location_groups_dict: Dict[str, List[Dict[str, Any]]] = {}
        for it in items:
            loc_key = it["location"]
            location_groups_dict.setdefault(loc_key, []).append(it)

        grouped_by_location = []
        for loc_name, group_items in location_groups_dict.items():
            urgent_cnt = sum(1 for x in group_items if x["urgency"] == "urgent")
            is_online = any(x["is_online_location"] for x in group_items)
            grouped_by_location.append({
                "location": loc_name,
                "is_online": is_online,
                "total_count": len(group_items),
                "urgent_count": urgent_cnt,
                "items": group_items,  # 內部同樣維持急迫性高低排序
            })
        # 地點分組排序：含有緊急項目的賣場優先，其次依待買數量高低
        grouped_by_location.sort(key=lambda g: (g["urgent_count"], g["total_count"]), reverse=True)

        history_list = []
        for hr in hist_rows:
            hd = dict(hr)
            loc_name = hd.get("location", "全聯") or "全聯"
            custom_tpl = loc_map.get(loc_name, {}).get("search_url_template", "")
            history_list.append({
                "id": hd["id"],
                "name": hd["name"],
                "quantity_note": hd.get("quantity_note", ""),
                "category": hd["category"],
                "location": loc_name,
                "online_search_links": build_online_search_links(hd["name"], loc_name, custom_tpl),
                "urgency": hd.get("urgency", "normal"),
                "price": hd["price"],
                "purchased_date": hd["purchased_date"],
                "purchased_at": hd["purchased_at"],
            })

        return {
            "items": items,
            "grouped_by_location": grouped_by_location,
            "locations": locations,
            "categories": SHOPPING_CATEGORIES,
            "urgency_levels": list(URGENCY_LEVELS.values()),
            "history": history_list,
            "history_query": q_clean,
            "stats": {
                "pending_total": len(items),
                "urgent_count": sum(1 for x in items if x["urgency"] == "urgent"),
                "normal_count": sum(1 for x in items if x["urgency"] == "normal"),
                "low_count": sum(1 for x in items if x["urgency"] == "low"),
                "active_locations_count": len(grouped_by_location),
                "history_total_count": total_hist_row["cnt"] if total_hist_row else 0,
                "history_total_spent": round(float(total_hist_row["total_spent"] or 0), 1) if total_hist_row else 0,
            },
        }

    def add_item(
        self,
        name: str,
        quantity_note: str = "",
        category: Optional[str] = None,
        location: str = "全聯",
        urgency: str = "normal",
        source_recipe: str = "",
    ) -> Dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValueError("品項名稱不可為空")

        # 自動商品類型判斷（若未指定或選擇 auto / 自動判斷）
        if not category or category in ("auto", "✨ 自動判斷", ""):
            cls_res = self.classify_category(clean_name, use_llm=True)
            final_cat = cls_res["category"]
            auto_flag = 1
        else:
            final_cat = category if category in SHOPPING_CATEGORIES else self.classify_category(clean_name)["category"]
            auto_flag = 0

        clean_loc = (location or "全聯").strip() or "全聯"
        self.remember_location(clean_loc)

        urg_info = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS["normal"])
        now_iso = datetime.now().isoformat()

        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO shopping_items
                (name, quantity_note, category, auto_categorized, location, urgency, urgency_rank, source_recipe, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    (quantity_note or "").strip(),
                    final_cat,
                    auto_flag,
                    clean_loc,
                    urg_info["code"],
                    urg_info["rank"],
                    (source_recipe or "").strip(),
                    now_iso,
                    now_iso,
                ),
            )
            new_id = cur.lastrowid

        return {"added_id": new_id, "category": final_cat, "auto_categorized": bool(auto_flag)}

    def update_item(self, item_id: int, updates: Dict[str, Any]) -> Dict[str, Any]:
        now_iso = datetime.now().isoformat()
        with get_db() as conn:
            existing = conn.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
            if not existing:
                return {"ok": False, "error": "找不到該採買項目"}

            name = (updates.get("name") if "name" in updates else existing["name"]).strip() or existing["name"]
            quantity_note = (
                updates.get("quantity_note") if "quantity_note" in updates else existing["quantity_note"]
            ).strip()

            category = updates.get("category") if "category" in updates else existing["category"]
            auto_categorized = existing["auto_categorized"]
            if "category" in updates:
                if category in ("auto", "✨ 自動判斷"):
                    category = self.classify_category(name)["category"]
                    auto_categorized = 1
                else:
                    auto_categorized = 0

            location = (updates.get("location") if "location" in updates else existing["location"]).strip() or "全聯"
            if "location" in updates:
                self.remember_location(location)

            urgency = updates.get("urgency") if "urgency" in updates else existing["urgency"]
            urg_info = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS["normal"])

            conn.execute(
                """
                UPDATE shopping_items
                SET name = ?, quantity_note = ?, category = ?, auto_categorized = ?,
                    location = ?, urgency = ?, urgency_rank = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    name,
                    quantity_note,
                    category,
                    auto_categorized,
                    location,
                    urg_info["code"],
                    urg_info["rank"],
                    now_iso,
                    item_id,
                ),
            )
        return {"ok": True, "item_id": item_id}

    def delete_item(self, item_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            deleted = conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,)).rowcount
        return {"ok": deleted > 0, "item_id": item_id}

    def complete_item(self, item_id: int, price: Optional[float] = None) -> Dict[str, Any]:
        """
        勾選「已購買」：從待買清單移除，並自動轉存至「採買歷史紀錄」
        （記錄購買日期、品項、分類、購買地點，並可選填購入金額）。
        """
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        now_iso = now.isoformat()

        parsed_price = None
        if price is not None and str(price).strip() != "":
            try:
                parsed_price = round(float(price), 1)
            except Exception:
                parsed_price = None

        with get_db() as conn:
            row = conn.execute("SELECT * FROM shopping_items WHERE id = ?", (item_id,)).fetchone()
            if not row:
                return {"ok": False, "error": "找不到該待買項目"}

            cur = conn.execute(
                """
                INSERT INTO shopping_history
                (name, quantity_note, category, location, urgency, price, purchased_date, purchased_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["name"],
                    row["quantity_note"],
                    row["category"],
                    row["location"],
                    row["urgency"],
                    parsed_price,
                    today_str,
                    now_iso,
                ),
            )
            history_id = cur.lastrowid
            conn.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))

        return {
            "ok": True,
            "completed_item_id": item_id,
            "history_id": history_id,
            "name": row["name"],
            "price": parsed_price,
        }

    def import_from_recipe(
        self,
        recipe_title: str,
        ingredients: List[Dict[str, str]],
        include_seasonings: bool = False,
        seasonings: Optional[List[Dict[str, str]]] = None,
        location: str = "全聯",
        urgency: str = "urgent",
    ) -> Dict[str, Any]:
        """從自煮食譜一鍵匯入食材（與選配調味料）至待買清單，並自動分類。"""
        clean_loc = (location or "全聯").strip() or "全聯"
        self.remember_location(clean_loc)
        urg_info = URGENCY_LEVELS.get(urgency, URGENCY_LEVELS["urgent"])
        now_iso = datetime.now().isoformat()

        entries_to_import = []
        for ing in ingredients or []:
            ing_name = (ing.get("name") or "").strip()
            ing_amt = (ing.get("amount") or "").strip()
            if ing_name:
                entries_to_import.append((ing_name, ing_amt))

        if include_seasonings and seasonings:
            for sea in seasonings:
                sea_name = (sea.get("name") or "").strip()
                sea_amt = (sea.get("amount") or "").strip()
                if sea_name and "水" not in sea_name:
                    entries_to_import.append((sea_name, sea_amt))

        imported_names = []
        with get_db() as conn:
            for raw_name, amount in entries_to_import:
                display_name = clean_search_keyword(raw_name) or raw_name
                note_parts = []
                if amount:
                    note_parts.append(amount)
                if raw_name != display_name:
                    note_parts.append(raw_name)
                if recipe_title:
                    note_parts.append(f"食譜：{recipe_title}")
                quantity_note = " • ".join(note_parts)

                cat_info = self.classify_category(raw_name, use_llm=False)
                category = cat_info["category"] if cat_info["category"] != "📦 其他" else "🥬 生鮮食材"

                conn.execute(
                    """
                    INSERT INTO shopping_items
                    (name, quantity_note, category, auto_categorized, location, urgency, urgency_rank, source_recipe, created_at, updated_at)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        display_name,
                        quantity_note,
                        category,
                        clean_loc,
                        urg_info["code"],
                        urg_info["rank"],
                        recipe_title,
                        now_iso,
                        now_iso,
                    ),
                )
                imported_names.append(display_name)

        return {
            "ok": True,
            "recipe_title": recipe_title,
            "imported_count": len(imported_names),
            "imported_items": imported_names,
            "location": clean_loc,
        }

    def repurchase_from_history(self, history_id: int, urgency: Optional[str] = None) -> Dict[str, Any]:
        """歷史紀錄『🔄 再次購買』：一鍵將常買消耗品重新加入待買清單。"""
        now_iso = datetime.now().isoformat()
        with get_db() as conn:
            h_row = conn.execute("SELECT * FROM shopping_history WHERE id = ?", (history_id,)).fetchone()
            if not h_row:
                return {"ok": False, "error": "找不到該歷史紀錄"}

            urg_code = urgency or h_row["urgency"] or "normal"
            urg_info = URGENCY_LEVELS.get(urg_code, URGENCY_LEVELS["normal"])
            loc = h_row["location"] or "全聯"

            cur = conn.execute(
                """
                INSERT INTO shopping_items
                (name, quantity_note, category, auto_categorized, location, urgency, urgency_rank, source_recipe, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?, ?, '', ?, ?)
                """,
                (
                    h_row["name"],
                    h_row["quantity_note"],
                    h_row["category"],
                    loc,
                    urg_info["code"],
                    urg_info["rank"],
                    now_iso,
                    now_iso,
                ),
            )
            new_item_id = cur.lastrowid

        self.remember_location(loc)
        return {
            "ok": True,
            "new_item_id": new_item_id,
            "name": h_row["name"],
            "location": loc,
            "category": h_row["category"],
        }

    def update_history_price(self, history_id: int, price: Optional[float]) -> Dict[str, Any]:
        parsed_price = None
        if price is not None and str(price).strip() != "":
            try:
                parsed_price = round(float(price), 1)
            except Exception:
                parsed_price = None
        with get_db() as conn:
            updated = conn.execute(
                "UPDATE shopping_history SET price = ? WHERE id = ?",
                (parsed_price, history_id),
            ).rowcount
        return {"ok": updated > 0, "history_id": history_id, "price": parsed_price}

    def delete_history_item(self, history_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            deleted = conn.execute("DELETE FROM shopping_history WHERE id = ?", (history_id,)).rowcount
        return {"ok": deleted > 0, "history_id": history_id}


shopping_module = ShoppingModule()
