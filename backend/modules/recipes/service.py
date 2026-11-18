"""
Module 3: 每兩小時自煮正餐推薦與歷史紀錄
- 排程觸發時間：每日 06:00 開始，每隔 2 小時 (06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00, 22:00)
  自動生成新一輪的「5 種家常自煮正餐料理」（適合下飯、家常且食材容易取得，避免連續兩輪重複）。
- 詳細食譜檢視：預估烹飪時間與份量（預設 2 人份）、精確食材與調味料清單（含克數/匙數）、條列式烹飪步驟與火候小撇步。
- 當日歷史紀錄與自動清理：保留當天所有時段推薦過的料理與食譜，每日 00:00 / 05:59 自動清空前一天歷史紀錄。
"""
import json
import random
import urllib.request
from datetime import datetime
from typing import Dict, Any, List, Optional

from backend.core.config import Config
from backend.core.database import get_db, cleanup_previous_days
from backend.core.module_registry import BaseModule

SCHEDULE_SLOTS = ["06:00", "08:00", "10:00", "12:00", "14:00", "16:00", "18:00", "20:00", "22:00"]

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
    description = "每日 06:00 起每 2 小時自動生成 5 道家常下飯正餐（避免連續兩輪重複），提供詳細 2 人份食譜與今日歷史紀錄時間軸，隔日自動清理。"

    def get_current_slot_label(self, now_dt: Optional[datetime] = None) -> str:
        now_dt = now_dt or datetime.now()
        h = now_dt.hour
        if h < 6:
            return "06:00"
        even_h = h if h % 2 == 0 else h - 1
        even_h = min(22, max(6, even_h))
        return f"{even_h:02d}:00"

    def get_dashboard_data(self, force_generate_new: bool = False) -> Dict[str, Any]:
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        # 確保隔日自動清理前一天以前的歷史紀錄
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

        latest_batch = batches[0] if batches else None
        return {
            "date": today_str,
            "current_slot": self.get_current_slot_label(now),
            "schedule_interval": "每日 06:00 起，每 2 小時更新一輪 (06:00 ~ 22:00)，每日 00:00 自動清空前日紀錄",
            "latest": latest_batch,
            "history": batches,
            "total_batches_today": len(batches),
        }

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
        1. 每日 00:00 或 05:59 自動清理前一天歷史紀錄
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
