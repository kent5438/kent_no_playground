"""
Module 3: 每兩小時自煮正餐推薦與歷史紀錄
- 排程觸發時間：每日 06:00 開始，每隔 2 小時 (06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00)
  自動生成新一輪的「5 種家常自煮正餐料理」（適合下飯、家常且食材容易取得，避免連續兩輪重複）。
- 詳細食譜檢視：預估烹飪時間與份量（預設 2 人份）、精確食材與調味料清單（含克數/匙數）、條列式烹飪步驟與火候小撇步。
- 當日歷史紀錄與自動清理：保留當天所有時段推薦過的料理與食譜，每日 00:00 / 05:59 自動清空前一天歷史紀錄。
- 我的最愛（永久保留）：任何推薦、歷史或自訂產出的食譜皆可一鍵收藏完整內容，永久保存於 SQLite 不受隔日清理影響。
- 輸入食材產出食譜：輸入冰箱現有食材即可產出專屬家常食譜（支援 LLM AI 即時研發與本地智慧食譜引擎）。
"""
import copy
import json
import random
import re
import urllib.request
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.core.config import Config
from backend.core.database import get_db, cleanup_previous_days
from backend.core.module_registry import BaseModule

SCHEDULE_SLOTS = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]

# 常見食材同義詞 / 分類輔助表（供本地食譜匹配與動態食譜產出使用）
INGREDIENT_SYNONYMS: Dict[str, List[str]] = {
    "豬肉": ["豬", "松阪豬", "梅花豬", "五花肉", "豬五花", "豬絞肉", "里肌肉", "豬里肌", "鹹豬肉", "豬排", "肉片", "肉末"],
    "雞肉": ["雞", "雞腿", "去骨雞腿", "雞胸", "雞柳", "雞里肌", "雞翅"],
    "牛肉": ["牛", "牛里肌", "牛肉片", "骰子牛", "板腱", "牛肋", "牛五花", "牛排"],
    "雞蛋": ["蛋", "雞蛋", "荷包蛋", "鹹蛋", "鹹鴨蛋", "皮蛋"],
    "蝦仁": ["蝦", "蝦仁", "白蝦", "草蝦", "鮮蝦"],
    "魚": ["魚", "鱸魚", "鯛魚", "鮭魚", "鯖魚", "鱈魚", "吳郭魚", "魚排", "魚片"],
    "海鮮": ["魷魚", "透抽", "中卷", "花枝", "蛤蜊", "蚵仔", "干貝", "蝦", "魚"],
    "豆腐": ["豆腐", "板豆腐", "嫩豆腐", "雞蛋豆腐", "百頁豆腐", "豆干", "黃豆干"],
    "菇": ["菇", "杏鮑菇", "香菇", "鮮香菇", "金針菇", "鴻喜菇", "雪白菇", "秀珍菇", "蘑菇"],
    "高麗菜": ["高麗菜", "甘藍"],
    "空心菜": ["空心菜", "蕹菜"],
    "番茄": ["番茄", "蕃茄", "牛番茄", "小番茄"],
    "茄子": ["茄子", "麻糬茄子"],
    "苦瓜": ["苦瓜", "白玉苦瓜", "山苦瓜"],
    "洋蔥": ["洋蔥"],
    "青蔥": ["蔥", "青蔥", "蔥花", "蔥段"],
    "蒜頭": ["蒜", "蒜頭", "蒜瓣", "蒜末", "蒜片", "蒜苗"],
    "薑": ["薑", "老薑", "嫩薑", "薑絲", "薑末", "薑片"],
    "九層塔": ["九層塔", "羅勒"],
    "大腸": ["大腸", "滷大腸", "豬大腸"],
}

AROMATIC_KEYWORDS = {"蒜", "蒜頭", "蒜瓣", "蒜末", "蒜片", "蔥", "青蔥", "蔥花", "薑", "老薑", "嫩薑", "辣椒", "紅辣椒", "九層塔", "香菜"}
PROTEIN_KEYWORDS = (
    "豬", "牛", "雞", "鴨", "羊", "肉", "排骨", "培根", "火腿", "香腸", "貢丸", "大腸",
    "魚", "鮭魚", "鱸魚", "鯛魚", "鯖魚", "鱈魚", "蝦", "蛤蜊", "蚵", "魷魚", "透抽", "中卷", "花枝", "干貝", "海鮮",
    "蛋", "雞蛋", "鹹蛋", "皮蛋", "豆腐", "豆干", "豆皮", "豆包", "毛豆"
)
STAPLE_KEYWORDS = ("飯", "白飯", "米", "麵", "烏龍麵", "義大利麵", "冬粉", "米粉", "年糕", "泡麵", "吐司", "馬鈴薯", "地瓜", "南瓜", "芋頭", "山藥")
ROOT_OR_STEW_KEYWORDS = ("蘿蔔", "白蘿蔔", "紅蘿蔔", "馬鈴薯", "地瓜", "南瓜", "冬瓜", "芋頭", "蓮藕", "筍", "玉米", "排骨", "牛肋", "牛腩", "雞腿", "豆腐", "大白菜", "娃娃菜", "丸", "菇")
LEAFY_VEG_KEYWORDS = ("高麗菜", "空心菜", "地瓜葉", "青江菜", "菠菜", "小白菜", "大陸妹", "A菜", "水蓮", "花椰菜", "青花菜", "四季豆", "秋葵", "芹菜", "絲瓜", "小黃瓜", "櫛瓜", "茄子", "苦瓜", "甜椒", "青椒", "彩椒", "番茄", "洋蔥", "菜")

# 精心設計的 25 道台灣家常下飯正餐食譜庫（全數具備精確克數/匙數、2人份設定、步驟與火候小撇步）
HOME_COOKING_RECIPE_BANK: List[Dict[str, Any]] = [
    {
        "id": "r01",
        "title": "蔥爆嫩煎松阪豬",
        "subtitle": "脆彈多汁、蔥香濃郁的白飯殺手",
        "category": "豬肉料理",
        "tags": ["極度下飯", "15分鐘快手", "超市常備"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "365 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "松阪豬肉（逆紋斜切片）", "amount": "220 克"},
            {"name": "青蔥（切 4 公分斜段，蔥白蔥綠分開）", "amount": "4 支（約 80 克）"},
            {"name": "蒜頭（拍碎切片）", "amount": "3 瓣（約 15 克）"},
            {"name": "紅辣椒（去籽斜切片，配色用）", "amount": "1/2 根"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "1 大匙（15 ml）"},
            {"name": "蠔油（或素蠔油）", "amount": "1 茶匙（5 ml）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/2 茶匙（2.5 克）"},
            {"name": "白胡椒粉", "amount": "1/4 茶匙"},
            {"name": "香油", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "將松阪豬肉逆著紋路斜切成約 0.3 公分薄片，口感才會爽脆不柴。",
            "平底鍋不放油（或僅刷薄油），開中小火將松阪豬片平鋪入鍋，兩面乾煎約 2.5 分鐘至邊緣微焦金黃、逼出豬油香氣。",
            "轉中大火，放入蔥白段與蒜片，利用鍋中豬油爆香 30 秒至蒜香四溢。",
            "沿著鍋邊淋入米酒與醬油熗出鍋氣，接著加入蠔油、細砂糖與白胡椒粉快速翻炒均勻。",
            "最後倒入蔥綠段與辣椒片，大火翻炒 15 秒，淋上香油即可關火起鍋。"
        ],
        "fire_tips": "火候小撇步：松阪豬一開始用「中小火乾煎」能逼出多餘油脂並創造脆口焦香；下蔥綠後務必轉「大火快炒不超過 15 秒」，才能保持青蔥翠綠與爽脆甜度！"
    },
    {
        "id": "r02",
        "title": "金沙鹹蛋苦瓜炒肉片",
        "subtitle": "鹹香起沙包裹甘甜白玉苦瓜",
        "category": "經典台菜",
        "tags": ["甘香不苦", "金沙下飯", "家常熱炒"],
        "prep_time_min": 20,
        "servings": "2 人份",
        "calories_per_serving": "310 kcal",
        "difficulty": "適中",
        "ingredients": [
            {"name": "白玉苦瓜（去籽刮除白膜、切薄片）", "amount": "280 克（約半條）"},
            {"name": "熟鹹鴨蛋（蛋黃蛋白分開壓碎）", "amount": "2 顆"},
            {"name": "梅花豬肉片", "amount": "120 克"},
            {"name": "蒜末", "amount": "10 克（約 2 瓣）"},
            {"name": "蔥花", "amount": "15 克"},
        ],
        "seasonings": [
            {"name": "食用油", "amount": "1.5 大匙（22 ml）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "冰糖或細砂糖", "amount": "1/2 茶匙（中和苦味）"},
            {"name": "香油", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "將白玉苦瓜對剖，用湯匙徹底刮除內側白色海綿膜（苦味來源），斜切成 0.3 公分薄片。",
            "煮一鍋滾水加少許鹽，放入苦瓜片汆燙 45 秒後立刻撈出瀝乾備用。",
            "熱鍋下 1.5 大匙油，開中小火放入壓碎的「鹹蛋黃」，用鍋鏟背不斷畫圈炒至冒出細密金黃泡沫。",
            "轉中大火加入蒜末與梅花豬肉片炒至肉片變白，熗入 1 大匙米酒。",
            "倒入苦瓜片、鹹蛋白碎與 1/2 茶匙糖，翻炒約 1 分鐘讓金沙均勻裹滿苦瓜，撒蔥花淋香油即完成。"
        ],
        "fire_tips": "火候小撇步：炒鹹蛋黃時一定要維持「小火慢炒」，若火太大蛋黃會直接焦黑且無法起泡出沙；看見蛋黃冒出細密泡泡時立刻下食材，包裹力最佳！"
    },
    {
        "id": "r03",
        "title": "九層塔香三杯杏鮑菇雞球",
        "subtitle": "黑麻油與老薑香氣撲鼻、雞腿肉鮮嫩多汁",
        "category": "雞肉料理",
        "tags": ["台式三杯", "白飯殺手", "香氣滿分"],
        "prep_time_min": 22,
        "servings": "2 人份",
        "calories_per_serving": "420 kcal",
        "difficulty": "適中",
        "ingredients": [
            {"name": "去骨雞腿肉（切 3 公分一口塊）", "amount": "260 克（約 1 隻大雞腿）"},
            {"name": "杏鮑菇（滾刀切塊）", "amount": "150 克（約 2 根）"},
            {"name": "老薑（切薄片）", "amount": "20 克（約 8 片）"},
            {"name": "整顆蒜瓣（去皮不切碎）", "amount": "6 瓣"},
            {"name": "新鮮九層塔葉", "amount": "25 克（一大把）"},
        ],
        "seasonings": [
            {"name": "黑麻油", "amount": "1.5 大匙（22 ml）"},
            {"name": "一般食用油（防麻油苦化）", "amount": "1 茶匙（5 ml）"},
            {"name": "醬油膏", "amount": "1.5 大匙（22 ml）"},
            {"name": "米酒", "amount": "2 大匙（30 ml）"},
            {"name": "冰糖", "amount": "1 茶匙（5 克）"},
        ],
        "steps": [
            "鍋中先放 1 茶匙一般食用油與老薑片，小火乾煸約 2 分鐘至薑片邊緣捲曲微乾。",
            "倒入雞腿肉塊（雞皮朝下）與杏鮑菇塊，轉中火煎至雞皮金黃、杏鮑菇表面微焦出水。",
            "倒入黑麻油與整顆蒜瓣翻炒 1 分鐘至蒜頭表面微金黃。",
            "加入米酒、醬油膏與冰糖，轉中小火蓋鍋悶煮 3 分鐘，隨後開蓋轉大火收乾醬汁至濃稠亮澤。",
            "關火前投入新鮮九層塔葉，利用餘溫快速翻拌 10 秒即可上桌。"
        ],
        "fire_tips": "火候小撇步：黑麻油不耐高溫久煸（容易變苦），因此先用一般油慢火煸香老薑、煎熟雞腿後，中段再下黑麻油，最後收汁轉大火讓冰糖焦糖化掛汁！"
    },
    {
        "id": "r04",
        "title": "川味麻婆嫩豆腐（家常微辣版）",
        "subtitle": "滑嫩豆腐吸飽肉末醬汁，一匙就能扒完一碗飯",
        "category": "豆腐/豬肉",
        "tags": ["一鍋到底", "極致下飯", "15分鐘上桌"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "295 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "盒裝嫩豆腐或板豆腐（切 2 公分方塊）", "amount": "1 盒（300 克）"},
            {"name": "豬絞肉（細絞，肥瘦 3:7）", "amount": "120 克"},
            {"name": "蒜末与薑末", "amount": "各 1 茶匙（共 10 克）"},
            {"name": "蔥花", "amount": "20 克"},
        ],
        "seasonings": [
            {"name": "辣豆瓣醬（不吃辣可換不辣豆瓣醬）", "amount": "1.5 大匙（22 克）"},
            {"name": "醬油", "amount": "1 茶匙（5 ml）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/2 茶匙"},
            {"name": "溫熱水或高湯", "amount": "120 ml"},
            {"name": "太白粉水（太白粉 1 茶匙 + 水 2 大匙）", "amount": "1 份"},
            {"name": "花椒油或香油", "amount": "1 茶匙"},
        ],
        "steps": [
            "豆腐切丁後放入加了 1/2 茶匙鹽的熱水中浸泡 3 分鐘（可去除豆腥味並讓豆腐不易碎）。",
            "熱鍋下 1 大匙油，中火將豬絞肉炒散至表面微焦、油脂清澈（不能有腥水）。",
            "將絞肉推至鍋邊，下蒜末、薑末與辣豆瓣醬，用小火炒出紅油香氣後與絞肉拌勻。",
            "注入 120ml 溫水、醬油、米酒與砂糖煮滾，放入瀝乾的豆腐丁，轉中小火慢煨 3 分鐘讓豆腐入味。",
            "分兩次淋入太白粉水，用鍋鏟背面輕推鍋底讓湯汁濃稠包裹豆腐，最後淋花椒油、撒蔥花起鍋。"
        ],
        "fire_tips": "火候小撇步：炒豆瓣醬時務必轉「小火」炒出紅油才不會燒焦發苦；勾芡時分成兩次下太白粉水，第一次定味、第二次收亮，豆腐既滑嫩又不會出水！"
    },
    {
        "id": "r05",
        "title": "番茄滑蛋炒鮮蝦仁",
        "subtitle": "酸甜茄汁融合滑嫩雞蛋與彈牙蝦仁",
        "category": "海鮮/蛋料理",
        "tags": ["酸甜開胃", "老少咸宜", "高蛋白"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "285 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "新鮮白蝦仁（開背去腸泥）", "amount": "150 克（約 12 隻）"},
            {"name": "雞蛋", "amount": "3 顆"},
            {"name": "牛番茄（切滾刀塊）", "amount": "1 大顆（約 180 克）"},
            {"name": "蔥花", "amount": "15 克"},
        ],
        "seasonings": [
            {"name": "番茄醬", "amount": "1.5 大匙（22 克）"},
            {"name": "細砂糖", "amount": "1 茶匙（5 克）"},
            {"name": "鹽巴", "amount": "1/2 茶匙（分兩次用）"},
            {"name": "米酒", "amount": "1 茶匙（醃蝦用）"},
            {"name": "牛奶或清水（加進蛋液更滑嫩）", "amount": "1.5 大匙（22 ml）"},
        ],
        "steps": [
            "蝦仁用紙巾吸乾水分，加 1/4 茶匙鹽與米酒抓醃；雞蛋打散加入 1/4 茶匙鹽與牛奶拌勻。",
            "熱鍋下 1 大匙油，中大火將蝦仁兩面煎約 45 秒至八分熟捲曲，淋入蛋液，用鍋鏟大動作推炒至七分熟凝結後立刻盛出備用。",
            "原鍋再補少許油，放入牛番茄塊與 2 大匙水，中火炒至番茄邊緣軟化出汁。",
            "加入番茄醬與細砂糖炒出紅亮醬汁，倒回剛剛的滑蛋蝦仁。",
            "大火快速翻拌 10 秒讓茄汁裹上蛋塊，撒上蔥花即可關火。"
        ],
        "fire_tips": "火候小撇步：滑蛋要嫩的關鍵是「中大火熱油下鍋、七分熟立刻離鍋」，最後跟番茄醬汁合炒時只需 10 秒餘溫，雞蛋就會像餐廳一樣滑嫩多汁！"
    },
    {
        "id": "r06",
        "title": "客家小炒（豆干魷魚五花肉）",
        "subtitle": "竹東在地經典風味、芹菜與醬香越嚼越香",
        "category": "客家家常",
        "tags": ["竹東在地味", "下飯首選", "香氣十足"],
        "prep_time_min": 20,
        "servings": "2 人份",
        "calories_per_serving": "390 kcal",
        "difficulty": "適中",
        "ingredients": [
            {"name": "豬五花肉（切 0.5 公分寬條）", "amount": "140 克"},
            {"name": "黃豆干（切 0.5 公分厚條）", "amount": "3 片（約 120 克）"},
            {"name": "發泡魷魚（或新鮮透抽切條）", "amount": "100 克"},
            {"name": "芹菜（切 4 公分段）", "amount": "60 克"},
            {"name": "青蔥（切段）與蒜片", "amount": "蔥 2 支、蒜 3 瓣"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "1.5 大匙（22 ml）"},
            {"name": "米酒", "amount": "1.5 大匙（22 ml）"},
            {"name": "冰糖或砂糖", "amount": "1/2 茶匙"},
            {"name": "白胡椒粉", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "五花肉條直接放入乾鍋，開中小火煸炒至表面微焦、逼出豬油後推到鍋邊。",
            "利用鍋中豬油放入豆干條，中小火慢煎至豆干表面起金黃微泡、外酥內嫩。",
            "加入蒜片、蔥白段與魷魚條，轉中大火爆香翻炒 45 秒。",
            "沿鍋邊淋入醬油與米酒熗香，加入砂糖與白胡椒粉翻炒讓豆干與肉條吸飽醬色。",
            "最後投入芹菜段與蔥綠，大火快炒 20 秒斷生即可盛盤。"
        ],
        "fire_tips": "火候小撇步：豆干一定要用中小火煎到表面微焦「起虎皮」，後續下醬油熗鍋時才能吸進醬香且口感Q彈；魷魚不可久炒以免變硬！"
    },
    {
        "id": "r07",
        "title": "蒜苗炒鹹豬肉（附檸檬醋沾醬）",
        "subtitle": "蒜苗清甜平衡五花鹹香，簡單快炒超開胃",
        "category": "豬肉料理",
        "tags": ["10分鐘快炒", "客家風味", "下飯配菜"],
        "prep_time_min": 12,
        "servings": "2 人份",
        "calories_per_serving": "375 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "市售或自製客家鹹豬肉（切薄片）", "amount": "180 克"},
            {"name": "新鮮青蒜苗（蒜白斜切片、蒜綠切段）", "amount": "2 大支（約 90 克）"},
            {"name": "紅辣椒（斜切片）", "amount": "1/2 根"},
        ],
        "seasonings": [
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/4 茶匙（提鮮平衡鹹度）"},
            {"name": "白醋 + 檸檬汁（沾醬用，可選）", "amount": "各 1 茶匙"},
        ],
        "steps": [
            "鹹豬肉若冷凍過先退冰，斜刀切成 0.2~0.3 公分薄片；青蒜苗洗淨斜切片，將蒜白與蒜綠分開放。",
            "平底鍋不放油，開中小火放入鹹豬肉片，兩面乾煎約 2 分鐘至肥肉部分呈透明微脆、逼出油脂。",
            "轉大火放入蒜白片與辣椒片，翻炒 40 秒至蒜白散發濃郁辛香。",
            "沿鍋邊熗入 1 大匙米酒與 1/4 茶匙砂糖，接著投入蒜綠段大火翻炒 15 秒即可起鍋。"
        ],
        "fire_tips": "火候小撇步：鹹豬肉本身已有鹹度與油脂，全程不需額外加油加鹽；先中小火逼油讓肥肉脆口不膩，下蒜苗後轉大火快炒鎖住蒜苗水分！"
    },
    {
        "id": "r08",
        "title": "紅燒家常豆腐煲（鮮菇肉片版）",
        "subtitle": "外韌內嫩的煎豆腐吸滿鹹甜醬汁",
        "category": "豆腐料理",
        "tags": ["營養均衡", "醬香濃郁", "暖胃家常"],
        "prep_time_min": 18,
        "servings": "2 人份",
        "calories_per_serving": "290 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "板豆腐（切 1 公分厚片）", "amount": "1 盒（300 克）"},
            {"name": "梅花豬肉片", "amount": "100 克"},
            {"name": "鮮香菇（切片）与紅蘿蔔片", "amount": "香菇 3 朵、紅蘿蔔 30 克"},
            {"name": "蔥段與蒜片", "amount": "蔥 2 支、蒜 2 瓣"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "1.5 大匙（22 ml）"},
            {"name": "蠔油", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/2 茶匙"},
            {"name": "清水", "amount": "100 ml"},
            {"name": "太白粉水（勾薄芡）", "amount": "1 大匙"},
            {"name": "香油", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "板豆腐用紙巾吸乾表面水分；平底鍋放 1.5 大匙油，中火將豆腐兩面煎至金黃微恰（每面約 2.5 分鐘）後先盛出。",
            "原鍋放入蒜片、蔥白段、豬肉片、香菇片與紅蘿蔔片炒香至肉片變色。",
            "加入醬油、蠔油、細砂糖與 100ml 清水煮滾，放回煎好的黃金板豆腐。",
            "轉中小火蓋鍋煨煮 3 分鐘讓豆腐內部吸飽湯汁。",
            "放入蔥綠段，淋入太白粉水收成亮澤薄芡，滴上香油即可盛盤。"
        ],
        "fire_tips": "火候小撇步：煎板豆腐時「下鍋後前 2 分鐘不要翻動」，等底面結出金黃硬殼再翻面就絕不會破；煎過的板豆腐氣孔打開，紅燒時更能吸滿湯汁！"
    },
    {
        "id": "r09",
        "title": "照燒奶油嫩煎雞腿排",
        "subtitle": "日式鹹甜照燒醬混搭淡淡奶油香，大人小孩都愛",
        "category": "雞肉料理",
        "tags": ["零失敗", "便當主菜", "日式家常"],
        "prep_time_min": 18,
        "servings": "2 人份",
        "calories_per_serving": "410 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "去骨雞腿排（肉厚處劃刀斷筋）", "amount": "2 片（約 320 克）"},
            {"name": "洋蔥（切絲，鋪底吸汁用）", "amount": "1/2 顆（約 100 克）"},
            {"name": "熟白芝麻", "amount": "1 茶匙"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "2 大匙（30 ml）"},
            {"name": "味醂", "amount": "2 大匙（30 ml）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1 茶匙（5 克）"},
            {"name": "無鹽奶油", "amount": "10 克"},
        ],
        "steps": [
            "將醬油、味醂、米酒與細砂糖在碗中調勻成「黃金比例照燒醬」備用。",
            "平底鍋不放油，雞腿排「雞皮朝下」冷鍋入鍋，開中小火慢煎約 5 分鐘至雞皮金黃酥脆，逼出多餘雞油（用紙巾吸除多餘油脂）。",
            "翻面後把洋蔥絲放入鍋邊，續煎 3 分鐘至雞肉八分熟、洋蔥變軟。",
            "倒入調好的照燒醬汁，轉中大火煮至醬汁冒泡收濃，期間將醬汁不斷淋在雞腿上。",
            "起鍋前放入 10 克無鹽奶油融化拌勻增添光澤，切塊鋪在洋蔥絲上並撒白芝麻。"
        ],
        "fire_tips": "火候小撇步：煎雞腿排一定要「雞皮朝下中小火慢煎」，且在倒照燒醬前先用紙巾把逼出的雞油擦掉，醬汁才不會油水分離，能完美扒附在雞皮上！"
    },
    {
        "id": "r10",
        "title": "蒜香空心菜炒沙茶牛肉",
        "subtitle": "熱炒店必點經典，牛肉滑嫩、青菜脆綠",
        "category": "牛肉料理",
        "tags": ["10分鐘快手", "鐵質豐富", "台式熱炒"],
        "prep_time_min": 12,
        "servings": "2 人份",
        "calories_per_serving": "330 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "牛里肌或火鍋牛肉片", "amount": "160 克"},
            {"name": "空心菜（洗淨切段，梗葉分開）", "amount": "1 把（約 220 克）"},
            {"name": "蒜末", "amount": "15 克（約 3 瓣）"},
            {"name": "紅辣椒片（可省略）", "amount": "1/2 根"},
        ],
        "seasonings": [
            {"name": "沙茶醬", "amount": "1 大匙（15 克）"},
            {"name": "醬油", "amount": "1 大匙（15 ml，其中 1 茶匙醃肉）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "太白粉（醃牛肉鎖汁用）", "amount": "1 茶匙"},
            {"name": "食用油", "amount": "1.5 大匙"},
        ],
        "steps": [
            "牛肉片加入 1 茶匙醬油、1 茶匙米酒與 1 茶匙太白粉抓勻，最後淋 1 茶匙油鎖住水分。",
            "熱鍋下 1 大匙油，大火將牛肉片入鍋快炒約 30 秒至七分熟變色，立刻盛出備用。",
            "原鍋下蒜末、辣椒與空心菜梗，大火翻炒 30 秒。",
            "加入空心菜葉、沙茶醬、剩餘醬油與米酒，大火快炒 20 秒至菜葉剛變軟。",
            "倒回七分熟牛肉片，翻拌 10 秒即可關火盛盤。"
        ],
        "fire_tips": "火候小撇步：牛肉與空心菜分開炒、最後合體是餐廳不老不黑的秘訣！全程維持「大火快炒」，空心菜下鍋到出鍋不超過 1 分鐘最翠綠。"
    },
    {
        "id": "r11",
        "title": "打拋豬肉佐香煎荷包蛋",
        "subtitle": "九層塔與檸檬魚露香氣交織，泰式國民下飯菜",
        "category": "豬肉料理",
        "tags": ["白飯殺手", "開胃首選", "15分鐘上桌"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "430 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "豬絞肉（粗絞口感更佳）", "amount": "220 克"},
            {"name": "小番茄（對半切）", "amount": "8 顆（約 70 克）"},
            {"name": "新鮮九層塔葉", "amount": "25 克"},
            {"name": "蒜末與紅辣椒末", "amount": "蒜 15 克、辣椒 1 根"},
            {"name": "雞蛋（煎半熟荷包蛋）", "amount": "2 顆"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "1 大匙（15 ml）"},
            {"name": "魚露（或薄鹽醬油）", "amount": "1 大匙（15 ml）"},
            {"name": "蠔油", "amount": "1 茶匙（5 ml）"},
            {"name": "細砂糖", "amount": "1 茶匙（5 克）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "新鮮檸檬汁", "amount": "1 大匙（起鍋前淋）"},
        ],
        "steps": [
            "先用平底鍋煎好 2 顆邊緣酥脆的半熟荷包蛋盛出備用。",
            "原鍋不加油（或少許油），開中大火將豬絞肉鋪平，煎 1.5 分鐘後再翻炒至絞肉粒粒分明、逼出香氣。",
            "加入蒜末與辣椒末爆香 30 秒，沿鍋邊淋入米酒、醬油、魚露、蠔油與砂糖翻炒上色。",
            "放入對切的小番茄炒 30 秒至微軟出汁，接著投入九層塔葉拌炒 10 秒。",
            "關火後淋上新鮮檸檬汁拌勻，搭配荷包蛋與白飯享用。"
        ],
        "fire_tips": "火候小撇步：豬絞肉下鍋後「先鋪平煎香再炒散」，能去除肉腥味並產生焦香顆粒感；檸檬汁一定要在「關火後」再淋，酸香才不會揮發變苦！"
    },
    {
        "id": "r12",
        "title": "樹子破布子清蒸鮮鱸魚",
        "subtitle": "甘甜破布子提鮮、魚肉細緻無腥味",
        "category": "海鮮料理",
        "tags": ["低脂健康", "免顧火", "清爽下飯"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "240 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "金目鱸魚排（或吳郭魚/鯛魚片）", "amount": "1 大片（約 280 克）"},
            {"name": "嫩豆腐（切片鋪底）", "amount": "1/2 盒（150 克）"},
            {"name": "薑絲與蔥絲", "amount": "各 15 克"},
        ],
        "seasonings": [
            {"name": "罐頭破布子（含醬汁）", "amount": "2 大匙（30 克）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "薄鹽醬油", "amount": "1 茶匙（5 ml）"},
            {"name": "香油", "amount": "1 茶匙"},
        ],
        "steps": [
            "嫩豆腐切 1 公分厚片鋪在深盤底部，將洗淨擦乾的鱸魚排放在豆腐上。",
            "在魚排表面均勻淋上破布子（連同罐頭甘甜湯汁）、米酒、薄鹽醬油，並鋪上一半的薑絲。",
            "蒸鍋或炒鍋水滾後，放入魚盤蓋上鍋蓋，以中大火蒸 8 分鐘。",
            "關火後鋪上剩餘的新鮮蔥絲與薑絲，淋上 1 茶匙香油，再蓋回鍋蓋悶 30 秒即可端出。"
        ],
        "fire_tips": "火候小撇步：蒸魚一定要等「水完全大滾」後再放魚入鍋計時，無骨魚排蒸 8 分鐘最鮮嫩；利用關火後悶 30 秒讓蔥絲散發清香又不變黃！"
    },
    {
        "id": "r13",
        "title": "塔香茄子燒肉末",
        "subtitle": "茄子軟嫩入味不變黑、鹹甜蒜香超配飯",
        "category": "蔬菜/豬肉",
        "tags": ["茄子不黑秘訣", "熱炒經典", "開胃家常"],
        "prep_time_min": 18,
        "servings": "2 人份",
        "calories_per_serving": "305 kcal",
        "difficulty": "適中",
        "ingredients": [
            {"name": "麻糬茄子（切 5 公分段後對剖）", "amount": "2 條（約 240 克）"},
            {"name": "豬絞肉", "amount": "100 克"},
            {"name": "蒜末與薑末", "amount": "各 10 克"},
            {"name": "新鮮九層塔葉", "amount": "20 克"},
        ],
        "seasonings": [
            {"name": "醬油膏", "amount": "1.5 大匙（22 ml）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/2 茶匙"},
            {"name": "白醋（少許，維持茄子紫色）", "amount": "1/2 茶匙"},
            {"name": "清水", "amount": "60 ml"},
        ],
        "steps": [
            "茄子切好後立即放入加了 1/2 茶匙白醋與少許鹽的水中浸泡防氧化變黑，下鍋前瀝乾。",
            "平底鍋放 1.5 大匙油，將茄子「紫皮朝下」排入鍋中，開中火半煎半悶 2.5 分鐘至茄肉軟化且保持鮮亮紫色，先盛出。",
            "原鍋放入豬絞肉炒至變白出香，加入蒜末與薑末爆香。",
            "倒入醬油膏、米酒、細砂糖與 60ml 清水煮滾，放回茄子轉中小火燒 1.5 分鐘收汁。",
            "起鍋前加入九層塔葉翻拌均勻即可。"
        ],
        "fire_tips": "火候小撇步：不用油炸也能讓茄子保持亮紫色的秘訣是「紫皮朝下接觸熱油、蓋鍋半煎悶 2 分鐘」，隔絕空氣就能保持漂亮色澤且少油健康！"
    },
    {
        "id": "r14",
        "title": "滑蛋洋蔥豬排丼（台日混搭家常版）",
        "subtitle": "焦糖洋蔥與鹹甜高湯煨煮軟嫩里肌豬排",
        "category": "豬肉/蛋料理",
        "tags": ["一鍋主食", "滑嫩甘甜", "快速晚餐"],
        "prep_time_min": 18,
        "servings": "2 人份",
        "calories_per_serving": "415 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "豬里肌肉排（用刀背拍鬆切厚條）", "amount": "200 克（2 片）"},
            {"name": "洋蔥（逆紋切絲）", "amount": "1/2 顆（約 120 克）"},
            {"name": "雞蛋（輕輕打散，保留部分蛋白）", "amount": "3 顆"},
            {"name": "蔥花", "amount": "15 克"},
        ],
        "seasonings": [
            {"name": "醬油", "amount": "1.5 大匙（22 ml）"},
            {"name": "味醂（或米酒+1茶匙糖）", "amount": "1.5 大匙（22 ml）"},
            {"name": "清水或柴魚高湯", "amount": "100 ml"},
            {"name": "太白粉（薄裹豬排表面）", "amount": "1 茶匙"},
        ],
        "steps": [
            "豬里肌排兩面用刀背輕拍斷筋，撒少許鹽與胡椒，表面薄拍一層太白粉（鎖住肉汁並讓醬汁濃稠）。",
            "平底鍋下 1 大匙油，中火將豬排兩面煎至金黃熟透（約 3 分鐘），取出切寬條。",
            "原鍋放入洋蔥絲炒至半透明微焦香，倒入醬油、味醂與 100ml 高湯煮滾，排入切好的豬排條。",
            "轉中小火，先淋入 2/3 的蛋液，蓋鍋煮 40 秒至半凝固；再淋入剩餘 1/3 蛋液與蔥花，關火悶 20 秒即可滑入飯碗或盤中。"
        ],
        "fire_tips": "火候小撇步：蛋液「分兩次下鍋」是日式丼飯滑嫩的精髓！第一次熟度約八分提供香氣，第二次關火利用餘溫悶出半熟滑蛋口感。"
    },
    {
        "id": "r15",
        "title": "薑絲大腸炒酸菜（溫和開胃家常版）",
        "subtitle": "竹東客家庄代表菜，微酸脆爽超醒胃",
        "category": "客家家常",
        "tags": ["竹東名菜", "酸香開胃", "10分鐘快炒"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "340 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "熟滷大腸或處理好的熟豬大腸（切斜段）", "amount": "200 克"},
            {"name": "嫩薑（切細絲）", "amount": "40 克"},
            {"name": "客家酸菜心（洗淨泡水 5 分鐘切絲）", "amount": "60 克"},
            {"name": "紅辣椒絲與蔥段", "amount": "辣椒半根、蔥 1 支"},
        ],
        "seasonings": [
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "白醋（或客家米醋）", "amount": "1.5 大匙（22 ml）"},
            {"name": "醬油", "amount": "1 茶匙（5 ml）"},
            {"name": "細砂糖", "amount": "1 茶匙（5 克，柔和酸度）"},
            {"name": "香油", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "買回的熟大腸斜切成一口大小，入滾水加 1 茶匙米酒汆燙 30 秒去油撈出瀝乾。",
            "熱鍋下 1 大匙油，放入薑絲與酸菜絲，中大火爆炒 1 分鐘把酸菜水分炒乾、釋放香氣。",
            "倒入大腸段、辣椒絲與蔥段，翻炒 45 秒。",
            "加入醬油與細砂糖炒勻，起鍋前沿著鍋邊淋入白醋，大火翻拌 5 秒淋香油立即出鍋。"
        ],
        "fire_tips": "火候小撇步：白醋如果太早下鍋會隨蒸氣揮發掉；一定要在「起鍋前最後 5 秒」沿著高溫鍋邊淋入，酸香撲鼻且溫和回甘！"
    },
    {
        "id": "r16",
        "title": "蒜蓉奶油醬燒杏鮑菇骰子牛",
        "subtitle": "多汁杏鮑菇與嫩煎牛肉塊，居家居酒屋風味",
        "category": "牛肉料理",
        "tags": ["15分鐘快手", "香氣濃郁", "高蛋白"],
        "prep_time_min": 15,
        "servings": "2 人份",
        "calories_per_serving": "380 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "板腱或牛肋條切骰子塊（2 公分方塊）", "amount": "180 克"},
            {"name": "杏鮑菇（切 2 公分方塊）", "amount": "150 克"},
            {"name": "蒜片", "amount": "4 瓣（約 20 克）"},
            {"name": "蔥花", "amount": "15 克"},
        ],
        "seasonings": [
            {"name": "無鹽奶油", "amount": "10 克"},
            {"name": "醬油", "amount": "1 大匙（15 ml）"},
            {"name": "蠔油", "amount": "1 茶匙（5 ml）"},
            {"name": "黑胡椒粗粒", "amount": "1/2 茶匙"},
            {"name": "米酒", "amount": "1 茶匙"},
        ],
        "steps": [
            "杏鮑菇切方塊後直接放入乾鍋，中火乾烙 2 分鐘至表面金黃出水、散發蕈菇香氣，先推至鍋邊。",
            "鍋中加 1 茶匙油與蒜片炒至金黃，放入骰子牛肉塊，開大火將四面煎至微焦（約 1.5 分鐘，保持內部七分熟）。",
            "加入無鹽奶油、醬油、蠔油與米酒，大火翻炒 20 秒讓醬汁包裹牛肉與杏鮑菇。",
            "撒上黑胡椒粗粒與蔥花即可關火上桌。"
        ],
        "fire_tips": "火候小撇步：杏鮑菇「先乾鍋不加油烙到出水」，能去除生菇味並讓口感像鮑魚一樣Q彈；骰子牛則要用大火快速封住表面鎖住肉汁！"
    },
    {
        "id": "r17",
        "title": "醬爆高麗菜回鍋肉片",
        "subtitle": "甜麵醬與豆瓣醬交融，高麗菜爽脆甘甜",
        "category": "豬肉/蔬菜",
        "tags": ["一菜有肉有菜", "下飯神菜", "家常必備"],
        "prep_time_min": 16,
        "servings": "2 人份",
        "calories_per_serving": "360 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "五花肉或梅花豬肉片", "amount": "150 克"},
            {"name": "高麗菜（手撕成一口大片）", "amount": "220 克"},
            {"name": "豆干（切薄片）", "amount": "2 片（約 70 克）"},
            {"name": "蒜片与青蔥段", "amount": "蒜 3 瓣、蔥 2 支"},
        ],
        "seasonings": [
            {"name": "甜麵醬（或醬油膏）", "amount": "1 大匙（15 克）"},
            {"name": "豆瓣醬", "amount": "1/2 大匙（7 克）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "細砂糖", "amount": "1/2 茶匙"},
        ],
        "steps": [
            "熱鍋下少許油，先放入高麗菜葉大火快炒 40 秒至七分熟微軟，先盛出瀝乾水分（避免後續出水沖淡醬香）。",
            "原鍋放入五花肉片與豆干片，中小火煎炒至肉片微捲、豆干微焦。",
            "放入蒜片、甜麵醬與豆瓣醬，小火炒出濃郁醬香，熗入米酒與砂糖。",
            "倒回高麗菜與青蔥段，轉大火快速翻炒 20 秒讓醬汁均勻裹上即可。"
        ],
        "fire_tips": "火候小撇步：高麗菜「先單獨大火快炒至七分熟盛出」，等肉片與醬料炒香後再回鍋合炒 20 秒，整盤菜就不會水水的，既脆口又入味！"
    },
    {
        "id": "r18",
        "title": "腐乳空心菜炒嫩雞柳",
        "subtitle": "甘醇豆腐乳帶出蔬菜清甜與滑嫩雞柳",
        "category": "雞肉/蔬菜",
        "tags": ["低脂高蛋白", "開胃鹹香", "12分鐘快炒"],
        "prep_time_min": 12,
        "servings": "2 人份",
        "calories_per_serving": "275 kcal",
        "difficulty": "簡單",
        "ingredients": [
            {"name": "雞里肌或雞胸肉（順紋切條）", "amount": "160 克"},
            {"name": "空心菜（或高麗菜/水蓮，切段）", "amount": "200 克"},
            {"name": "蒜末与辣椒絲", "amount": "蒜 2 瓣、辣椒半根"},
        ],
        "seasonings": [
            {"name": "甘甜白豆腐乳（連同腐乳汁壓泥）", "amount": "1.5 塊（約 25 克）"},
            {"name": "米酒", "amount": "1 大匙（15 ml）"},
            {"name": "溫水（調開腐乳用）", "amount": "1 大匙（15 ml）"},
            {"name": "太白粉（醃雞柳用）", "amount": "1 茶匙"},
        ],
        "steps": [
            "雞柳加 1 茶匙米酒與 1 茶匙太白粉抓勻；豆腐乳在碗中與剩餘米酒、溫水壓成滑順腐乳醬汁。",
            "熱鍋下 1 大匙油，中火將雞柳滑炒 1 分鐘至八分熟變白，先盛出。",
            "原鍋爆香蒜末與辣椒絲，放入空心菜梗炒 20 秒，接著下菜葉與調好的腐乳醬汁。",
            "放回雞柳，轉大火快速翻炒 25 秒讓腐乳香氣均勻附著即可起鍋。"
        ],
        "fire_tips": "火候小撇步：豆腐乳一定要「事先在碗裡加米酒與溫水壓成醬汁」，若整塊直接丟入熱鍋，菜都炒老了腐乳還沒化開！"
    },
]


class RecipesModule(BaseModule):
    module_id = "recipes"
    name = "每兩小時自煮正餐推薦與歷史紀錄"
    description = "每日 06:00 起每 2 小時自動生成 5 道家常下飯正餐（避免連續兩輪重複），提供詳細 2 人份食譜、輸入食材產出食譜、永久我的最愛收藏與今日歷史紀錄時間軸。"

    def get_current_slot_label(self, now_dt: Optional[datetime] = None) -> str:
        now_dt = now_dt or datetime.now()
        h = now_dt.hour
        if h < 6:
            return "06:00"
        even_h = h if h % 2 == 0 else h - 1
        even_h = min(22, max(6, even_h))
        return f"{even_h:02d}:00"

    @staticmethod
    def _recipe_key(recipe: Dict[str, Any]) -> str:
        return str((recipe or {}).get("title") or "").strip()

    @staticmethod
    def _normalize_recipe(recipe: Dict[str, Any], fallback_servings: str = "2 人份") -> Dict[str, Any]:
        """確保食譜欄位完整、結構一致，方便永久收藏與前端渲染。"""
        raw = recipe if isinstance(recipe, dict) else {}
        title = str(raw.get("title") or "家常自煮料理").strip()

        def _norm_items(items: Any) -> List[Dict[str, str]]:
            out = []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        name = str(it.get("name") or "").strip()
                        amount = str(it.get("amount") or "適量").strip()
                        if name:
                            out.append({"name": name, "amount": amount})
                    elif isinstance(it, str) and it.strip():
                        out.append({"name": it.strip(), "amount": "適量"})
            return out

        def _norm_str_list(vals: Any) -> List[str]:
            if isinstance(vals, list):
                return [str(v).strip() for v in vals if str(v).strip()]
            return []

        try:
            prep_min = int(raw.get("prep_time_min") or 18)
        except Exception:
            prep_min = 18

        normalized = {
            "id": str(raw.get("id") or f"custom-{uuid.uuid4().hex[:8]}"),
            "title": title,
            "subtitle": str(raw.get("subtitle") or "家常下飯、香氣十足的自煮料理").strip(),
            "category": str(raw.get("category") or "家常料理").strip(),
            "tags": _norm_str_list(raw.get("tags")) or ["家常自煮", "下飯料理"],
            "prep_time_min": max(5, min(180, prep_min)),
            "servings": str(raw.get("servings") or fallback_servings).strip(),
            "calories_per_serving": str(raw.get("calories_per_serving") or "340 kcal").strip(),
            "difficulty": str(raw.get("difficulty") or "簡單").strip(),
            "ingredients": _norm_items(raw.get("ingredients")),
            "seasonings": _norm_items(raw.get("seasonings")),
            "steps": _norm_str_list(raw.get("steps")),
            "fire_tips": str(raw.get("fire_tips") or "維持中大火快炒鎖住食材原味，起鍋前點少許香油即可提香上桌！").strip(),
        }
        if raw.get("matched_ingredients"):
            normalized["matched_ingredients"] = _norm_str_list(raw.get("matched_ingredients"))
        return normalized

    def get_dashboard_data(self, force_generate_new: bool = False) -> Dict[str, Any]:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 確保隔日自動清理前一天以前的歷史紀錄（不會清理 favorite_recipes）
        cleanup_previous_days(today_str)

        if force_generate_new:
            slot_time = now.strftime("%H:%M") + " (手動刷新)"
            self.generate_batch(today_str, slot_time)

        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, date_str, slot_time, recipes_json, source, created_at
                FROM recipe_batches
                WHERE date_str = ?
                ORDER BY id DESC
                """,
                (today_str,),
            ).fetchall()

        if not rows:
            # 首次啟動時，自動補齊今日從 06:00 到目前時段的排程歷史紀錄，讓時間軸與最新推薦立即完整呈現
            self._seed_today_slots_up_to_now(now, today_str)
            with get_db() as conn:
                rows = conn.execute(
                    """
                    SELECT id, date_str, slot_time, recipes_json, source, created_at
                    FROM recipe_batches
                    WHERE date_str = ?
                    ORDER BY id DESC
                    """,
                    (today_str,),
                ).fetchall()

        batches = []
        for r in rows:
            batches.append({
                "batch_id": r["id"],
                "date": r["date_str"],
                "slot_time": r["slot_time"],
                "recipes": json.loads(r["recipes_json"]),
                "source": r["source"],
                "created_at": r["created_at"],
            })

        favorites = self.list_favorites()
        favorite_keys = [f["recipe_key"] for f in favorites]
        custom_batches = self.list_custom_batches(limit=8)
        latest_batch = batches[0] if batches else None

        return {
            "date": today_str,
            "current_slot": self.get_current_slot_label(now),
            "schedule_interval": "每日 06:00 起，每 2 小時更新一輪 (06:00 ~ 22:00)，每日 00:00 自動清空前日紀錄（我的最愛永久保留）",
            "latest": latest_batch,
            "history": batches,
            "total_batches_today": len(batches),
            "favorites": favorites,
            "favorite_keys": favorite_keys,
            "total_favorites": len(favorites),
            "custom_batches": custom_batches,
            "latest_custom": custom_batches[0] if custom_batches else None,
            "llm_enabled": Config.has_valid_key(Config.LLM_API_KEY),
        }

    # ==========================================================
    # 功能 1：食譜我的最愛（永久保留，不受隔日歷史清理影響）
    # ==========================================================
    def list_favorites(self, query: str = "") -> List[Dict[str, Any]]:
        q = (query or "").strip().lower()
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, recipe_key, title, category, recipe_json, source_label, saved_at
                FROM favorite_recipes
                ORDER BY id DESC
                """
            ).fetchall()

        results = []
        for r in rows:
            try:
                recipe_obj = json.loads(r["recipe_json"])
            except Exception:
                continue
            if q:
                haystack = " ".join([
                    r["title"] or "",
                    r["category"] or "",
                    str(recipe_obj.get("subtitle") or ""),
                    " ".join(recipe_obj.get("tags") or []),
                    " ".join(str(i.get("name") or "") for i in (recipe_obj.get("ingredients") or [])),
                ]).lower()
                if q not in haystack:
                    continue
            results.append({
                "fav_id": r["id"],
                "recipe_key": r["recipe_key"],
                "title": r["title"],
                "category": r["category"],
                "source_label": r["source_label"],
                "saved_at": r["saved_at"],
                "recipe": recipe_obj,
            })
        return results

    def get_favorite_keys(self) -> List[str]:
        with get_db() as conn:
            rows = conn.execute("SELECT recipe_key FROM favorite_recipes ORDER BY id DESC").fetchall()
            return [r["recipe_key"] for r in rows]

    def toggle_favorite(self, recipe: Dict[str, Any], source_label: str = "") -> Dict[str, Any]:
        if not isinstance(recipe, dict) or not str(recipe.get("title") or "").strip():
            return {"ok": False, "error": "無效的食譜資料"}

        normalized = self._normalize_recipe(recipe)
        recipe_key = self._recipe_key(normalized)
        now_iso = datetime.now().isoformat()

        with get_db() as conn:
            existing = conn.execute(
                "SELECT id FROM favorite_recipes WHERE recipe_key = ?",
                (recipe_key,),
            ).fetchone()

            if existing:
                conn.execute("DELETE FROM favorite_recipes WHERE id = ?", (existing["id"],))
                return {
                    "ok": True,
                    "favorited": False,
                    "recipe_key": recipe_key,
                    "title": normalized["title"],
                }

            cur = conn.execute(
                """
                INSERT INTO favorite_recipes (recipe_key, title, category, recipe_json, source_label, saved_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    recipe_key,
                    normalized["title"],
                    normalized.get("category", "家常料理"),
                    json.dumps(normalized, ensure_ascii=False),
                    (source_label or "自煮正餐推薦").strip(),
                    now_iso,
                ),
            )
            return {
                "ok": True,
                "favorited": True,
                "fav_id": cur.lastrowid,
                "recipe_key": recipe_key,
                "title": normalized["title"],
                "saved_at": now_iso,
            }

    def delete_favorite(self, fav_id: Optional[int] = None, recipe_key: Optional[str] = None) -> Dict[str, Any]:
        with get_db() as conn:
            if fav_id:
                deleted = conn.execute("DELETE FROM favorite_recipes WHERE id = ?", (int(fav_id),)).rowcount
                return {"ok": deleted > 0, "deleted": deleted}
            if recipe_key:
                deleted = conn.execute(
                    "DELETE FROM favorite_recipes WHERE recipe_key = ?",
                    (recipe_key.strip(),),
                ).rowcount
                return {"ok": deleted > 0, "deleted": deleted}
        return {"ok": False, "deleted": 0, "error": "請提供 fav_id 或 recipe_key"}

    # ==========================================================
    # 功能 2：輸入食材產出食譜（支援 LLM AI + 本地智慧匹配與合成）
    # ==========================================================
    @staticmethod
    def _parse_ingredients_input(raw_input: Any) -> List[str]:
        if isinstance(raw_input, list):
            parts = [str(x).strip() for x in raw_input]
        else:
            text = str(raw_input or "").strip()
            parts = re.split(r"[,，、;；\n\r+/\s]+", text)

        cleaned: List[str] = []
        seen = set()
        for p in parts:
            item = p.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            cleaned.append(item)
        return cleaned

    def list_custom_batches(self, limit: int = 8) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                """
                SELECT id, ingredients_input, ingredients_json, servings, preference, recipes_json, source, created_at
                FROM custom_recipe_batches
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            ).fetchall()

        out = []
        for r in rows:
            try:
                out.append({
                    "batch_id": r["id"],
                    "ingredients_input": r["ingredients_input"],
                    "ingredients": json.loads(r["ingredients_json"]),
                    "servings": r["servings"],
                    "preference": r["preference"],
                    "recipes": json.loads(r["recipes_json"]),
                    "source": r["source"],
                    "created_at": r["created_at"],
                })
            except Exception:
                continue
        return out

    def delete_custom_batch(self, batch_id: int) -> Dict[str, Any]:
        with get_db() as conn:
            deleted = conn.execute(
                "DELETE FROM custom_recipe_batches WHERE id = ?",
                (int(batch_id),),
            ).rowcount
        return {"ok": deleted > 0, "deleted": deleted}

    def generate_from_ingredients(
        self,
        ingredients_input: Any,
        servings: str = "2 人份",
        preference: str = "",
        count: int = 3,
    ) -> Dict[str, Any]:
        ingredients_list = self._parse_ingredients_input(ingredients_input)
        if not ingredients_list:
            return {"ok": False, "error": "請至少輸入一項食材（例如：雞腿肉、高麗菜、蒜頭）"}

        servings = (servings or "2 人份").strip() or "2 人份"
        preference = (preference or "").strip()
        count = max(1, min(5, int(count or 3)))

        recipes: Optional[List[Dict[str, Any]]] = None
        source = ""

        if Config.has_valid_key(Config.LLM_API_KEY):
            recipes = self._generate_from_ingredients_via_llm(
                ingredients_list=ingredients_list,
                servings=servings,
                preference=preference,
                count=count,
            )
            if recipes:
                source = f"LLM 食材專屬食譜研發 ({Config.LLM_MODEL})"

        if not recipes:
            recipes = self._generate_from_ingredients_local(
                ingredients_list=ingredients_list,
                servings=servings,
                preference=preference,
                count=count,
            )
            source = "智慧家常食譜引擎（依據輸入食材自動匹配與研發）"

        normalized_recipes = [self._normalize_recipe(r, fallback_servings=servings) for r in recipes[:count]]
        now_iso = datetime.now().isoformat()
        ingredients_display = "、".join(ingredients_list)

        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO custom_recipe_batches (
                    ingredients_input, ingredients_json, servings, preference, recipes_json, source, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ingredients_display,
                    json.dumps(ingredients_list, ensure_ascii=False),
                    servings,
                    preference,
                    json.dumps(normalized_recipes, ensure_ascii=False),
                    source,
                    now_iso,
                ),
            )
            batch_id = cur.lastrowid

            # 僅保留最近 10 次食材產出紀錄，保持資料庫輕量（收藏至我的最愛則永久保留）
            conn.execute(
                """
                DELETE FROM custom_recipe_batches
                WHERE id NOT IN (
                    SELECT id FROM custom_recipe_batches ORDER BY id DESC LIMIT 10
                )
                """
            )

        return {
            "ok": True,
            "batch": {
                "batch_id": batch_id,
                "ingredients_input": ingredients_display,
                "ingredients": ingredients_list,
                "servings": servings,
                "preference": preference,
                "recipes": normalized_recipes,
                "source": source,
                "created_at": now_iso,
            },
        }

    def _generate_from_ingredients_via_llm(
        self,
        ingredients_list: List[str],
        servings: str,
        preference: str,
        count: int = 3,
    ) -> Optional[List[Dict[str, Any]]]:
        """串接 Gemini / OpenAI 相容 API 依據使用者輸入食材產出專屬食譜 JSON。"""
        try:
            ing_str = "、".join(ingredients_list)
            pref_clause = f"風格/口感偏好：{preference}。" if preference else "風格：台灣家常、下飯好上手。"
            prompt = (
                f"使用者目前手邊有以下食材：{ing_str}。\n"
                f"請以這些食材為核心主角，設計 {count} 道風格各異的台灣家常自煮正餐料理（份量：{servings}）。\n"
                f"{pref_clause}\n"
                "可搭配台灣家庭廚房常見基本辛香料與調味料（蔥、薑、蒜、醬油、米酒、油、鹽、糖、胡椒、太白粉等），"
                "但每道菜都必須明確運用使用者輸入的主要食材，並在步驟中寫清楚處理方式與火候。\n"
                "請回傳純 JSON Array（不要加任何說明文字），每個元素包含：\n"
                "id, title, subtitle, category, tags(字串陣列), prep_time_min(整數), "
                f"servings('{servings}'), calories_per_serving, difficulty('簡單'|'適中'), "
                "matched_ingredients(字串陣列，列出本道料理使用到哪些使用者輸入食材), "
                "ingredients(物件陣列，含 name 與精確克數/顆數 amount), "
                "seasonings(物件陣列，含 name 與精確匙數/ml amount), "
                "steps(條列式字串陣列，4-6 步), fire_tips(主廚火候小撇步字串)。"
            )

            provider = (Config.LLM_PROVIDER or "gemini").lower()
            text = ""

            if provider == "openai":
                url = "https://api.openai.com/v1/chat/completions"
                payload = {
                    "model": Config.LLM_MODEL or "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "你是專業台灣家常料理主廚，請只回傳合法 JSON Array。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.7,
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {Config.LLM_API_KEY}",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    text = result["choices"][0]["message"]["content"]
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.LLM_MODEL}:generateContent?key={Config.LLM_API_KEY}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"},
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=25) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    text = result["candidates"][0]["content"]["parts"][0]["text"]

            cleaned_text = text.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
                cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

            parsed = json.loads(cleaned_text)
            if isinstance(parsed, dict) and isinstance(parsed.get("recipes"), list):
                parsed = parsed["recipes"]
            if isinstance(parsed, list) and len(parsed) >= 1:
                return parsed[:count]
        except Exception:
            return None
        return None

    @staticmethod
    def _expand_ingredient_terms(term: str) -> List[str]:
        terms = [term]
        for canonical, aliases in INGREDIENT_SYNONYMS.items():
            if term == canonical or term in aliases or any(a in term or term in a for a in aliases if len(a) >= 2):
                terms.append(canonical)
                terms.extend(aliases)
        return list(dict.fromkeys(terms))

    @staticmethod
    def _serving_scale(servings: str) -> float:
        if "1" in servings:
            return 0.6
        if "4" in servings or "3" in servings:
            return 1.6
        return 1.0

    @staticmethod
    def _classify_ingredient(item: str) -> str:
        if item in AROMATIC_KEYWORDS:
            return "aromatic"
        if any(k in item for k in PROTEIN_KEYWORDS):
            return "protein"
        if any(k in item for k in STAPLE_KEYWORDS):
            return "staple"
        if any(k in item for k in LEAFY_VEG_KEYWORDS) or any(k in item for k in ROOT_OR_STEW_KEYWORDS):
            return "vegetable"
        return "other"

    def _generate_from_ingredients_local(
        self,
        ingredients_list: List[str],
        servings: str = "2 人份",
        preference: str = "",
        count: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        本地智慧食譜引擎：
        1. 先從精選台灣家常食譜庫中尋找高相關度匹配食譜（最多取 1 道，避免每次都只出舊食譜）
        2. 依據使用者輸入的實際食材（蛋白質 / 蔬菜 / 澱粉 / 辛香料）動態研發多道不同烹調風格的專屬食譜
        """
        results: List[Dict[str, Any]] = []
        used_titles = set()
        non_aromatics = [x for x in ingredients_list if x not in AROMATIC_KEYWORDS]
        core_inputs = non_aromatics or ingredients_list

        # Step 1: 檢查精選家常食譜庫是否有高度匹配的經典料理
        scored_bank = []
        for recipe in HOME_COOKING_RECIPE_BANK:
            recipe_text = recipe["title"] + " " + " ".join(i["name"] for i in recipe.get("ingredients", []))
            matched = []
            core_matched = 0
            for user_ing in ingredients_list:
                expanded = self._expand_ingredient_terms(user_ing)
                if any(tok in recipe_text for tok in expanded if tok):
                    matched.append(user_ing)
                    if user_ing not in AROMATIC_KEYWORDS:
                        core_matched += 1
            if core_matched >= 1 and (core_matched >= 2 or len(core_inputs) == 1):
                scored_bank.append((core_matched, len(matched), recipe, matched))

        scored_bank.sort(key=lambda x: (x[0], x[1]), reverse=True)
        if scored_bank:
            best_core, _, best_recipe, matched_ings = scored_bank[0]
            # 只有當配對到至少 1 個核心主角食材時納入 1 道經典菜，其餘交由客製化合成
            if best_core >= 1:
                cloned = copy.deepcopy(best_recipe)
                cloned["id"] = f"ing-bank-{cloned['id']}-{uuid.uuid4().hex[:4]}"
                cloned["servings"] = servings
                cloned["matched_ingredients"] = matched_ings
                cloned["tags"] = list(dict.fromkeys(["經典匹配"] + cloned.get("tags", [])))[:4]
                results.append(cloned)
                used_titles.add(cloned["title"])

        # Step 2: 依輸入食材動態合成專屬家常食譜
        synthesized = self._synthesize_recipes_for_ingredients(
            ingredients_list=ingredients_list,
            servings=servings,
            preference=preference,
        )
        for rec in synthesized:
            if len(results) >= count:
                break
            if rec["title"] not in used_titles:
                results.append(rec)
                used_titles.add(rec["title"])

        return results[:count]

    def _synthesize_recipes_for_ingredients(
        self,
        ingredients_list: List[str],
        servings: str = "2 人份",
        preference: str = "",
    ) -> List[Dict[str, Any]]:
        scale = self._serving_scale(servings)
        proteins, vegs, staples, aromatics, others = [], [], [], [], []

        for item in ingredients_list:
            cat = self._classify_ingredient(item)
            if cat == "protein":
                proteins.append(item)
            elif cat == "vegetable":
                vegs.append(item)
            elif cat == "staple":
                staples.append(item)
            elif cat == "aromatic":
                aromatics.append(item)
            else:
                others.append(item)

        main_items = proteins + vegs + staples + others
        if not main_items:
            main_items = list(ingredients_list)

        primary_name = "、".join(main_items[:2]) if len(main_items) >= 2 else main_items[0]
        short_name = "".join(main_items[:2]) if len("".join(main_items[:2])) <= 8 else primary_name
        has_egg = any("蛋" in x for x in ingredients_list)
        has_garlic = any("蒜" in x for x in ingredients_list)
        has_scallion = any("蔥" in x for x in ingredients_list)
        has_ginger = any("薑" in x for x in ingredients_list)

        def _g(base_g: int) -> str:
            val = int(round((base_g * scale) / 10.0) * 10)
            return f"{max(30, val)} 克"

        def _build_base_ings(extra_items: List[Dict[str, str]]) -> List[Dict[str, str]]:
            out = []
            for p in proteins:
                amt = f"{max(2, int(round(3 * scale)))} 顆" if "蛋" in p else (f"1 盒（{_g(280)}）" if "豆腐" in p else _g(180))
                out.append({"name": f"{p}（洗淨切適口大小）", "amount": amt})
            for v in vegs:
                out.append({"name": f"{v}（洗淨切塊或切段）", "amount": _g(160)})
            for st in staples:
                out.append({"name": f"{st}（備妥切塊或備用）", "amount": _g(180)})
            for ot in others:
                out.append({"name": f"{ot}（切適口大小）", "amount": _g(150)})
            for ar in aromatics:
                out.append({"name": f"{ar}（切末或切段爆香）", "amount": "約 20 克"})
            for ex in extra_items:
                if not any(ex["key"] in x for x in ingredients_list):
                    out.append({"name": ex["name"], "amount": ex["amount"]})
            return out

        main_category = (
            "肉類/家常快炒" if proteins else ("蔬食家常" if vegs else "自訂食材料理")
        )
        pref_tag = preference if preference and preference != "不限（家常下飯）" else ""

        # 料理方案 1：蒜香醬燒家常快炒（萬用下飯王）
        stir_ings = _build_base_ings([
            {"key": "蒜", "name": "蒜頭（拍碎切末）", "amount": "3 瓣（約 15 克）"},
            {"key": "蔥", "name": "青蔥（切段，蔥白蔥綠分開）", "amount": "2 支"},
        ])
        protein_step = (
            f"熱鍋下 1 大匙油，中火將「{'、'.join(proteins)}」先下鍋煎炒約 1.5 分鐘至表面微金黃出香，先推至鍋邊。"
            if proteins else
            "熱鍋下 1 大匙油，開中小火先爆香蒜末與蔥白約 30 秒至香氣四溢。"
        )
        veg_targets = vegs + staples + others
        veg_step = (
            f"放入「{'、'.join(veg_targets)}」與爆香辛香料，轉中大火翻炒約 1.5~2 分鐘至食材轉亮並開始軟化。"
            if veg_targets else
            "加入爆香蒜末與蔥白快速翻炒 30 秒，讓食材充分吸收蒜香。"
        )
        recipe_stir = {
            "id": f"ing-stir-{uuid.uuid4().hex[:6]}",
            "title": f"蒜香醬燒{short_name}",
            "subtitle": f"善用手邊的{primary_name}，大火熗鍋醬香濃郁超下飯",
            "category": main_category,
            "tags": [t for t in ["食材客製", "15分鐘快炒", "極度下飯", pref_tag] if t][:4],
            "prep_time_min": 15,
            "servings": servings,
            "calories_per_serving": "345 kcal",
            "difficulty": "簡單",
            "matched_ingredients": list(ingredients_list),
            "ingredients": stir_ings,
            "seasonings": [
                {"name": "醬油", "amount": "1.5 大匙（22 ml）"},
                {"name": "蠔油（或素蠔油）", "amount": "1 茶匙（5 ml）"},
                {"name": "米酒", "amount": "1 大匙（15 ml）"},
                {"name": "細砂糖", "amount": "1/2 茶匙（提鮮）"},
                {"name": "白胡椒粉與香油", "amount": "各少許"},
            ],
            "steps": [
                f"將「{'、'.join(ingredients_list)}」洗淨瀝乾，切成大小一致的適口塊狀或片狀，確保受熱均勻。",
                protein_step,
                veg_step,
                "沿著熱鍋邊淋入米酒與醬油熗出鍋氣，接著加入蠔油、細砂糖與 2 大匙清水翻炒均勻讓醬汁包裹食材。",
                "起鍋前撒入蔥綠段與少許白胡椒粉，大火快炒 15 秒，滴上香油即可盛盤開飯。",
            ],
            "fire_tips": f"火候小撇步：將{primary_name}切至大小相近能避免生熟不均；醬油與米酒務必「沿著滾燙鍋邊淋下」熗出焦香鍋氣，起鍋前大火收汁 15 秒最下飯！",
        }

        # 料理方案 2：滑蛋 / 奶油椒鹽香煎版本（換一種完全不同的口感）
        if has_egg:
            non_egg_mains = [x for x in main_items if "蛋" not in x]
            egg_partner = (
                "".join(non_egg_mains[:2])
                if non_egg_mains and len("".join(non_egg_mains[:2])) <= 8
                else ("、".join(non_egg_mains[:2]) if non_egg_mains else "家常")
            )
            pan_title = f"黃金滑蛋嫩炒{egg_partner}"
            pan_sub = "蛋香滑嫩包裹食材原味，零失敗的餐廳級家常菜"
            pan_ings = _build_base_ings([
                {"key": "蔥", "name": "蔥花", "amount": "15 克"},
                {"key": "蒜", "name": "蒜末", "amount": "10 克"},
            ])
            pan_seasonings = [
                {"name": "鹽巴", "amount": "1/2 茶匙"},
                {"name": "米酒", "amount": "1 茶匙（去腥提香）"},
                {"name": "牛奶或清水（拌入蛋液更嫩）", "amount": "1.5 大匙"},
                {"name": "白胡椒粉", "amount": "1/4 茶匙"},
                {"name": "香油", "amount": "1/2 茶匙"},
            ]
            pan_steps = [
                f"將蛋打散加入 1/4 茶匙鹽、米酒與牛奶拌勻；其餘食材（{'、'.join([x for x in ingredients_list if '蛋' not in x] or ingredients_list)}）洗淨切小片或細丁。",
                "熱鍋下 1 大匙油，中火將主食材與蒜末炒熟至微焦香，加少許鹽調味後平鋪於鍋中。",
                "轉中大火淋入蛋液，靜置 8 秒待底部略凝固，再用鍋鏟由外往內輕推折疊至七分熟滑嫩狀態。",
                "關火撒上蔥花、白胡椒粉與香油，利用鍋中餘溫拌 5 秒即可滑出盛盤。",
            ]
            pan_tips = "火候小撇步：蛋液下鍋前加一點牛奶或清水，並於「七分熟立刻關火」靠餘溫熟成，就能炒出像港式茶餐廳一樣水嫩發亮的黃金滑蛋！"
        else:
            pan_title = f"蒜蓉奶油椒鹽煎{short_name}"
            pan_sub = "奶油焦香融合黑胡椒辛香，少醬油也能吃出食材鮮甜"
            pan_ings = _build_base_ings([
                {"key": "蒜", "name": "蒜片", "amount": "4 瓣（約 20 克）"},
                {"key": "蔥", "name": "蔥花或九層塔（提香用）", "amount": "15 克"},
            ])
            pan_seasonings = [
                {"name": "無鹽奶油", "amount": "12 克"},
                {"name": "一般食用油", "amount": "1 茶匙（防奶油焦黑）"},
                {"name": "鹽巴（或海鹽）", "amount": "1/2 茶匙"},
                {"name": "黑胡椒粗粒", "amount": "1/2 茶匙"},
                {"name": "米酒（或味醂）", "amount": "1 茶匙"},
            ]
            pan_steps = [
                f"將「{'、'.join(ingredients_list)}」洗淨後徹底用紙巾擦乾表面水分（乾爽才容易煎出焦香）。",
                "平底鍋加 1 茶匙食用油，開中火將食材平鋪入鍋乾煎約 2~3 分鐘至兩面微焦金黃。",
                "轉中小火放入無鹽奶油與蒜片，讓奶油融化起泡並均勻沾裹所有食材，煎出濃郁蒜蓉奶香。",
                "撒上鹽巴、黑胡椒粗粒與米酒快炒 20 秒，起鍋前點綴蔥花即可享用。",
            ]
            pan_tips = "火候小撇步：先用一般食用油把食材煎出金黃表皮，後段再轉「中小火下無鹽奶油」，這樣奶油既不會燒焦發苦，又能完美巴附在食材上！"

        recipe_pan = {
            "id": f"ing-pan-{uuid.uuid4().hex[:6]}",
            "title": pan_title,
            "subtitle": pan_sub,
            "category": "香煎/快手料理",
            "tags": [t for t in ["食材客製", "焦香開胃", "少油煙", pref_tag] if t][:4],
            "prep_time_min": 14,
            "servings": servings,
            "calories_per_serving": "320 kcal",
            "difficulty": "簡單",
            "matched_ingredients": list(ingredients_list),
            "ingredients": pan_ings,
            "seasonings": pan_seasonings,
            "steps": pan_steps,
            "fire_tips": pan_tips,
        }

        # 料理方案 3：暖胃一鍋到底家常燉煲 / 鮮味煨煮
        stew_ings = _build_base_ings([
            {"key": "薑", "name": "老薑（切片或切絲）", "amount": "15 克"},
            {"key": "蔥", "name": "青蔥（切段）", "amount": "2 支"},
            {"key": "蒜", "name": "整顆蒜瓣（去皮）", "amount": "3 瓣"},
        ])
        is_light = "清淡" in preference or "湯" in preference
        stew_title = f"薑香鮮甜{short_name}暖胃湯煲" if is_light else f"家常醬香{short_name}一鍋煲"
        stew_sub = (
            "清爽甘甜、原汁原味，一鍋同時滿足主菜與熱湯"
            if is_light else
            "慢火煨煮讓每口食材吸飽鮮甜湯汁，拌飯一流"
        )
        stew_seasonings = (
            [
                {"name": "清水或昆布高湯", "amount": "400 ml"},
                {"name": "米酒", "amount": "1 大匙（15 ml）"},
                {"name": "鹽巴", "amount": "3/4 茶匙（依口味調整）"},
                {"name": "白胡椒粉", "amount": "1/4 茶匙"},
                {"name": "香油", "amount": "1/2 茶匙"},
            ]
            if is_light else
            [
                {"name": "清水或高湯", "amount": "180 ml"},
                {"name": "醬油", "amount": "1.5 大匙（22 ml）"},
                {"name": "味醂（或冰糖 1 茶匙）", "amount": "1 大匙（15 ml）"},
                {"name": "米酒", "amount": "1 大匙（15 ml）"},
                {"name": "太白粉水（可選，收薄芡用）", "amount": "1 大匙"},
            ]
        )
        recipe_stew = {
            "id": f"ing-stew-{uuid.uuid4().hex[:6]}",
            "title": stew_title,
            "subtitle": stew_sub,
            "category": "一鍋煲/暖胃家常",
            "tags": [t for t in ["食材客製", "一鍋到底", "免顧火", pref_tag] if t][:4],
            "prep_time_min": 20,
            "servings": servings,
            "calories_per_serving": "310 kcal",
            "difficulty": "簡單",
            "matched_ingredients": list(ingredients_list),
            "ingredients": stew_ings,
            "seasonings": stew_seasonings,
            "steps": [
                f"將「{'、'.join(ingredients_list)}」洗淨切塊備用；耐煮食材切稍大塊，易熟食材保留完整口感。",
                "深鍋或砂鍋加 1 茶匙油，小火煸香薑片與蒜瓣 30 秒，再放入較耐煮的主食材略微翻炒出香氣。",
                f"注入{'400ml 清水/高湯與米酒' if is_light else '180ml 清水、醬油、味醂與米酒'}煮至大滾，撈除表面浮沫。",
                "轉中小火蓋上鍋蓋慢煨 6~8 分鐘至食材入味軟嫩，最後 2 分鐘再放入易熟青菜或嫩食材。",
                f"開蓋試味道微調鹹淡，{'撒蔥花、白胡椒粉與香油' if is_light else '轉中大火略收湯汁（或勾薄芡）並撒上蔥段'}即可整鍋上桌。",
            ],
            "fire_tips": "火候小撇步：燉煮時「先大火煮滾去浮沫，再轉中小火加蓋慢煨」，食材才會軟嫩不散且湯汁清甜濃郁；葉菜類務必最後 2 分鐘再放才不會變黃！",
        }

        # 根據偏好調整呈現順序
        candidates = [recipe_stir, recipe_pan, recipe_stew]
        if "清淡" in preference or "湯" in preference or "一鍋" in preference:
            candidates = [recipe_stew, recipe_pan, recipe_stir]
        elif "快手" in preference or "15" in preference:
            candidates = [recipe_pan, recipe_stir, recipe_stew]
        return candidates

    def _seed_today_slots_up_to_now(self, now_dt: datetime, today_str: str) -> None:
        """首次開啟儀表板時，依據當前時間自動建立今日已過時段的歷史紀錄 (最多最近 3 個時段)，方便立即體驗歷史時間軸。"""
        current_h = now_dt.hour
        eligible_slots = [s for s in SCHEDULE_SLOTS if int(s.split(":")[0]) <= max(6, current_h)]
        slots_to_seed = eligible_slots[-3:] if len(eligible_slots) > 3 else eligible_slots
        if not slots_to_seed:
            slots_to_seed = ["06:00"]
        for slot in slots_to_seed:
            self.generate_batch(today_str, slot)

    def generate_batch(self, today_str: Optional[str] = None, slot_time: Optional[str] = None) -> Dict[str, Any]:
        now = datetime.now()
        today_str = today_str or now.strftime("%Y-%m-%d")
        slot_time = slot_time or self.get_current_slot_label(now)

        # 取得上一輪推薦的料理 ID / 名稱，確保「避免連續兩輪重複」
        prev_titles = set()
        with get_db() as conn:
            prev_row = conn.execute(
                "SELECT recipes_json FROM recipe_batches WHERE date_str = ? ORDER BY id DESC LIMIT 1",
                (today_str,),
            ).fetchone()
            if prev_row:
                try:
                    prev_list = json.loads(prev_row["recipes_json"])
                    prev_titles = {item["title"] for item in prev_list}
                except Exception:
                    pass

        recipes = None
        source = ""
        if Config.has_valid_key(Config.LLM_API_KEY):
            recipes = self._generate_via_llm(prev_titles)
            if recipes:
                source = f"LLM 食譜生成 API ({Config.LLM_MODEL})"

        if not recipes:
            recipes = self._select_from_recipe_bank(prev_titles, count=5)
            source = "精選台灣家常下飯食譜庫 (設定 LLM_API_KEY 可啟用 AI 無限動態生成)"

        now_iso = now.isoformat()
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO recipe_batches (date_str, slot_time, recipes_json, source, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (today_str, slot_time, json.dumps(recipes, ensure_ascii=False), source, now_iso),
            )
            batch_id = cur.lastrowid

        return {
            "batch_id": batch_id,
            "date": today_str,
            "slot_time": slot_time,
            "recipes": recipes,
            "source": source,
            "created_at": now_iso,
        }

    def _select_from_recipe_bank(self, exclude_titles: set, count: int = 5) -> List[Dict[str, Any]]:
        non_overlapping = [r for r in HOME_COOKING_RECIPE_BANK if r["title"] not in exclude_titles]
        if len(non_overlapping) >= count:
            return random.sample(non_overlapping, count)
        return random.sample(HOME_COOKING_RECIPE_BANK, count)

    def _generate_via_llm(self, exclude_titles: set) -> Optional[List[Dict[str, Any]]]:
        """串接 Gemini API 生成 5 道不重複的家常下飯正餐食譜 JSON。"""
        try:
            exclude_str = "、".join(exclude_titles) if exclude_titles else "無"
            prompt = (
                "請推薦 5 道台灣家常自煮正餐料理（需適合下飯、家常且超市或市場食材容易取得）。"
                f"請避免與上一輪料理重複（上一輪為：{exclude_str}）。"
                "請回傳純 JSON Array，每個元素包含：id, title, subtitle, category, tags(陣列), "
                "prep_time_min(整數), servings('2 人份'), calories_per_serving, difficulty, "
                "ingredients(含 name, amount 克數), seasonings(含 name, amount 匙數/ml), "
                "steps(字串陣列), fire_tips(火候小撇步字串)。"
            )
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{Config.LLM_MODEL}:generateContent?key={Config.LLM_API_KEY}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                text = result["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                if isinstance(parsed, list) and len(parsed) >= 5:
                    return parsed[:5]
        except Exception:
            return None
        return None

    def clear_today_history(self, keep_latest: bool = True) -> Dict[str, Any]:
        today_str = datetime.now().strftime("%Y-%m-%d")
        with get_db() as conn:
            if keep_latest:
                latest = conn.execute(
                    "SELECT id FROM recipe_batches WHERE date_str = ? ORDER BY id DESC LIMIT 1",
                    (today_str,),
                ).fetchone()
                if latest:
                    deleted = conn.execute(
                        "DELETE FROM recipe_batches WHERE date_str = ? AND id != ?",
                        (today_str, latest["id"]),
                    ).rowcount
                    return {"deleted": deleted, "kept_latest_id": latest["id"]}
            deleted = conn.execute("DELETE FROM recipe_batches WHERE date_str = ?", (today_str,)).rowcount
            return {"deleted": deleted}

    def on_cron_tick(self, now_dt: datetime) -> None:
        """
        1. 每日 00:00 或 05:59 自動清理前一天歷史紀錄（我的最愛永久保留）
        2. 每日 06:00 開始，每隔 2 小時 (06:00, 08:00, ..., 22:00) 自動生成新一輪 5 道家常料理
        """
        today_str = now_dt.strftime("%Y-%m-%d")
        time_str = now_dt.strftime("%H:%M")

        if time_str in ("00:00", "05:59"):
            cleanup_previous_days(today_str)

        if time_str in SCHEDULE_SLOTS:
            job_key = "recipes_2hr"
            with get_db() as conn:
                row = conn.execute("SELECT last_run_date, last_run_slot FROM cron_logs WHERE job_key = ?", (job_key,)).fetchone()
                if row and row["last_run_date"] == today_str and row["last_run_slot"] == time_str:
                    return
                conn.execute(
                    "INSERT OR REPLACE INTO cron_logs (job_key, last_run_date, last_run_slot, updated_at) VALUES (?, ?, ?, ?)",
                    (job_key, today_str, time_str, now_dt.isoformat()),
                )
            self.generate_batch(today_str, time_str)


recipes_module = RecipesModule()
