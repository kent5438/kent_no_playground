/**
 * 模組 4：全方位智慧採買清單模組（不限品類）UI 卡片元件
 * - 通用物品新增：支援任何生活採買品項（生鮮、日用、居家、3C、零食、藥妝等），並支援從自煮食譜一鍵匯入食材
 * - 自動商品類型判斷：輸入時即時預覽規則庫自動分類，後端亦支援規則庫 + LLM 自動判斷，並支援手動隨時修改分類
 * - 自訂地點清單與記憶功能：自由輸入地點 + 自動記憶 Autocomplete 下拉快選 + 管理常用地點清單；
 *   若地點為網購平台（如 momo、蝦皮、PChome、酷澎等），自動在項目旁產生帶入該商品名稱的「快速搜尋連結」
 * - 急迫性分級與雙檢視模式：🔴 緊急（今日必買）、🟡 一般（近期購買）、🟢 不急（順路/特價再買），預設依急迫性高低排序，
 *   支援「依急迫性檢視」與「依購買地點分組檢視」一鍵切換
 * - 已購買歸檔與歷史紀錄：勾選「已購買」（可選填購入金額）後自動移至「採買歷史紀錄」，支援關鍵字搜尋與「🔄 再次購買」
 */
import { showToast, widgetRegistry } from "../core/widgetRegistry.js";

let currentContainer = null;
let shoppingData = null;
let activeView = "urgency"; // 'urgency' | 'location' | 'history'
let selectedCategoryFilter = "ALL";
let selectedLocationFilter = "ALL";
let historySearchQuery = "";
let showLocationManager = false;
let showRecipeImporter = false;
let cachedTodayRecipes = [];

// 前端即時預覽用分類規則（與後端規則庫同步）
const CLIENT_CATEGORY_RULES = [
  {
    category: "🔌 3C家電",
    keywords: [
      "充電線", "type-c", "typec", "lightning", "usb", "hdmi", "網路線", "轉接頭", "充電頭", "快充",
      "行動電源", "充電器", "耳機", "airpods", "藍牙", "喇叭", "滑鼠", "鍵盤", "螢幕", "筆電", "電腦",
      "平板", "ipad", "iphone", "手機", "保護貼", "手機殼", "支架", "記憶卡", "隨身碟", "硬碟", "ssd",
      "路由器", "wifi", "延長線", "插座", "電池", "吹風機", "電風扇", "吸塵器", "除濕機", "空氣清淨機",
      "濾網", "電鍋", "氣炸鍋", "微波爐", "烤箱", "快煮壺", "電動牙刷", "檯燈", "燈泡", "3c"
    ],
  },
  {
    category: "🧻 日用清潔",
    keywords: [
      "衛生紙", "面紙", "抽取式", "廚房紙巾", "擦手紙", "濕紙巾", "化妝棉", "洗衣精", "洗衣球",
      "洗衣粉", "柔軟精", "漂白水", "去漬", "洗碗精", "洗手乳", "沐浴乳", "洗髮精", "潤髮乳",
      "洗面乳", "肥皂", "牙膏", "牙刷", "牙線", "漱口水", "垃圾袋", "菜瓜布", "海綿", "抹布",
      "拖把", "掃把", "除塵紙", "除濕盒", "除濕袋", "克潮靈", "芳香劑", "消臭", "防蚊", "殺蟲劑",
      "蟑螂藥", "清潔劑", "浴廁清潔", "魔術靈", "小蘇打", "檸檬酸", "酒精", "衛生棉", "護墊", "尿布"
    ],
  },
  {
    category: "💊 藥妝保健",
    keywords: [
      "維他命", "維生素", "b群", "魚油", "益生菌", "葉黃素", "鈣片", "膠原蛋白", "酵素", "雞精",
      "感冒藥", "普拿疼", "止痛藥", "腸胃藥", "胃散", "眼藥水", "人工淚液", "生理食鹽水", "優碘",
      "ok繃", "紗布", "棉花棒", "口罩", "酸痛貼布", "藥膏", "小護士", "護手霜", "乳液", "化妝水",
      "精華液", "眼霜", "面霜", "面膜", "防曬", "護唇膏", "卸妝", "痘痘貼", "隱形眼鏡", "保養液", "藥妝"
    ],
  },
  {
    category: "🏠 居家百貨",
    keywords: [
      "收納", "整理箱", "衣架", "曬衣", "洗衣袋", "掛勾", "置物架", "層架", "保鮮盒", "便當盒",
      "密封袋", "保鮮膜", "鋁箔紙", "烘焙紙", "夾鏈袋", "水壺", "保溫杯", "保溫瓶", "馬克杯",
      "碗", "餐盤", "盤子", "筷子", "湯匙", "叉子", "餐具", "平底鍋", "炒鍋", "湯鍋", "砧板",
      "菜刀", "剪刀", "鍋鏟", "枕頭", "床包", "被套", "棉被", "毛巾", "浴巾", "地墊", "拖鞋",
      "雨傘", "雨衣", "椅子", "坐墊", "窗簾", "五金", "螺絲", "起子", "膠帶", "雙面膠", "三秒膠",
      "瓦斯罐", "筆記本", "原子筆", "便利貼", "資料夾", "貓砂", "飼料", "鍋墊"
    ],
  },
  {
    category: "🍿 零食飲料",
    keywords: [
      "洋芋片", "餅乾", "仙貝", "米果", "爆米花", "巧克力", "糖果", "軟糖", "口香糖", "堅果",
      "杏仁", "腰果", "核桃", "開心果", "花生", "海苔", "肉乾", "魷魚絲", "泡麵", "科學麵",
      "乾拌麵", "布丁", "果凍", "冰淇淋", "雪糕", "蛋糕", "蛋捲", "鳳梨酥", "甜點", "零食",
      "可樂", "雪碧", "汽水", "沙士", "氣泡水", "礦泉水", "綠茶", "紅茶", "烏龍茶", "麥茶",
      "奶茶", "茶包", "咖啡", "濾掛", "拿鐵", "果汁", "運動飲料", "舒跑", "啤酒", "紅酒",
      "梅酒", "燕麥奶", "可可", "麥片"
    ],
  },
  {
    category: "🥬 生鮮食材",
    keywords: [
      "豬", "松阪", "梅花", "五花", "里肌", "絞肉", "排骨", "鹹豬肉", "大腸", "培根", "香腸", "貢丸",
      "牛", "牛肉", "牛排", "骰子牛", "雞", "雞腿", "雞胸", "雞柳", "雞翅", "雞蛋", "鹹蛋", "皮蛋", "蛋",
      "魚", "鱸魚", "鮭魚", "鯛魚", "鯖魚", "鱈魚", "蝦", "蝦仁", "透抽", "中卷", "魷魚", "蛤蜊", "海鮮",
      "豆腐", "豆干", "豆皮", "豆漿", "蔥", "青蔥", "蒜", "蒜頭", "蒜苗", "薑", "辣椒", "九層塔", "香菜",
      "芹菜", "洋蔥", "高麗菜", "空心菜", "地瓜葉", "青江菜", "菠菜", "白菜", "娃娃菜", "水蓮", "花椰菜",
      "苦瓜", "絲瓜", "黃瓜", "櫛瓜", "茄子", "南瓜", "番茄", "蘿蔔", "馬鈴薯", "地瓜", "玉米", "四季豆",
      "甜椒", "青椒", "酸菜", "泡菜", "竹筍", "木耳", "菇", "杏鮑菇", "香菇", "金針菇", "鴻喜菇",
      "水果", "蘋果", "香蕉", "芭樂", "奇異果", "木瓜", "西瓜", "鳳梨", "葡萄", "草莓", "柳丁", "檸檬",
      "鮮奶", "牛奶", "優格", "起司", "奶油", "米", "白米", "麵條", "烏龍麵", "冬粉", "吐司", "麵包",
      "水餃", "醬油", "蠔油", "米酒", "味醂", "魚露", "醋", "砂糖", "冰糖", "鹽", "胡椒", "太白粉",
      "香油", "麻油", "橄欖油", "食用油", "豆瓣醬", "甜麵醬", "沙茶醬", "番茄醬", "破布子", "豆腐乳", "芝麻", "高湯"
    ],
  },
];

function predictCategoryClient(itemName) {
  if (!itemName || !itemName.trim()) return "📦 其他";
  const lower = itemName.trim().toLowerCase();
  let bestCat = "📦 其他";
  let bestLen = 0;
  for (const rule of CLIENT_CATEGORY_RULES) {
    for (const kw of rule.keywords) {
      const kwLower = kw.toLowerCase();
      if (lower.includes(kwLower) && kwLower.length > bestLen) {
        bestCat = rule.category;
        bestLen = kwLower.length;
      }
    }
  }
  return bestCat;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export const ShoppingWidget = {
  id: "shopping",
  name: "全方位智慧採買清單模組（不限品類）",
  description: "通用生活品項與自煮食譜一鍵匯入、規則庫/LLM自動分類、自訂地點記憶與網購快速搜尋連結、急迫性與地點雙檢視、歷史紀錄與再次購買",
  slotSelector: "#widget-slot-extensions",

  async mount(container) {
    currentContainer = container;
    container.classList.remove("hidden");
    await this.loadData();
  },

  async refresh() {
    await this.loadData();
  },

  async loadData() {
    const qParam = encodeURIComponent(historySearchQuery || "");
    const res = await fetch(`/api/modules/shopping?q=${qParam}`);
    shoppingData = await res.json();
    this.render();
  },

  async loadTodayRecipesForQuickImport() {
    try {
      const res = await fetch("/api/modules/recipes");
      const data = await res.json();
      cachedTodayRecipes = data?.latest?.recipes || [];
    } catch (e) {
      cachedTodayRecipes = [];
    }
  },

  render() {
    if (!currentContainer || !shoppingData) return;
    const stats = shoppingData.stats || {};
    const locations = shoppingData.locations || [];
    const categories = shoppingData.categories || [];
    const savedDefaultLoc = localStorage.getItem("pref_shopping_location") || (locations[0]?.name || "全聯");

    const datalistOptions = locations
      .map((l) => `<option value="${escapeHtml(l.name)}">${l.is_online ? "🌐 網購平台" : "🏪 實體通路"} (使用 ${l.usage_count} 次)</option>`)
      .join("");

    const pinnedChipsHtml = locations
      .slice(0, 8)
      .map(
        (l) => `
        <button type="button" class="loc-quick-chip ${l.is_online ? "is-online" : ""}" data-quick-loc="${escapeHtml(l.name)}" title="點擊快速帶入「${escapeHtml(l.name)}」">
          ${l.is_online ? "🛍️" : "📍"} ${escapeHtml(l.name)}
        </button>
      `
      )
      .join("");

    const categoryOptionsHtml = [
      `<option value="auto">✨ 自動判斷分類 (規則庫 / AI)</option>`,
      ...categories.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`),
    ].join("");

    currentContainer.innerHTML = `
      <article class="widget-card shopping-widget-card">
        <div class="widget-header">
          <div class="widget-title-group">
            <span class="widget-icon">🛒</span>
            <div>
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <h2 class="widget-title">全方位智慧採買清單模組（不限品類）</h2>
                <span class="badge badge-danger-soft">🔴 今日必買 ${stats.urgent_count || 0}</span>
                <span class="badge badge-info">待買總計 ${stats.pending_total || 0} 項</span>
                <span class="badge badge-success">涵蓋 ${stats.active_locations_count || 0} 個採買地點</span>
              </div>
              <p class="widget-subtitle">
                支援生鮮食材、日用清潔、居家百貨、3C家電、零食飲料、藥妝保健 • 自動記憶地點與網購快速搜尋連結
              </p>
            </div>
          </div>

          <div class="widget-controls">
            <button type="button" class="btn btn-outline btn-sm" id="btn-toggle-recipe-importer">
              🥘 從自煮食譜一鍵匯入食材
            </button>
            <button type="button" class="btn btn-outline btn-sm" id="btn-toggle-location-manager">
              📍 管理常用地點 (${locations.length})
            </button>
          </div>
        </div>

        <div class="widget-body">
          <!-- 展開面板 1：從目前推薦的自煮食譜一鍵匯入食材 -->
          ${showRecipeImporter ? this.renderRecipeImporterPanel(savedDefaultLoc) : ""}

          <!-- 展開面板 2：管理常用地點清單與自訂網購搜尋記憶 -->
          ${showLocationManager ? this.renderLocationManagerPanel(locations) : ""}

          <!-- 通用採買物品新增表單 -->
          <form id="shopping-add-form" class="shopping-add-box">
            <div class="shopping-form-grid">
              <div class="shopping-field-name">
                <label for="shopping-input-name">
                  <span>1. 品項名稱（不限品類）</span>
                  <span id="shopping-auto-cat-preview" class="auto-cat-hint">✨ 輸入名稱自動預判分類</span>
                </label>
                <input
                  type="text"
                  id="shopping-input-name"
                  class="form-control"
                  placeholder="例如：松阪豬肉、抽取式衛生紙、Type-C 充電線、葉黃素..."
                  required
                />
              </div>

              <div class="shopping-field-note">
                <label for="shopping-input-note">2. 數量 / 規格備註（選填）</label>
                <input
                  type="text"
                  id="shopping-input-note"
                  class="form-control"
                  placeholder="例如：2 盒、220 克、2 公尺..."
                />
              </div>

              <div class="shopping-field-cat">
                <label for="shopping-input-category">3. 商品類型（自動/手動）</label>
                <select id="shopping-input-category" class="form-control">
                  ${categoryOptionsHtml}
                </select>
              </div>

              <div class="shopping-field-loc">
                <label for="shopping-input-location">4. 採買地點（自由輸入/記憶快選）</label>
                <input
                  type="text"
                  id="shopping-input-location"
                  class="form-control"
                  list="shopping-locations-datalist"
                  value="${escapeHtml(savedDefaultLoc)}"
                  placeholder="全聯、好市多、宜得利、momo購物網、蝦皮..."
                  autocomplete="off"
                />
                <datalist id="shopping-locations-datalist">
                  ${datalistOptions}
                </datalist>
              </div>

              <div class="shopping-field-urgency">
                <label for="shopping-input-urgency">5. 急迫性分級</label>
                <select id="shopping-input-urgency" class="form-control">
                  <option value="urgent">🔴 緊急（今日必買）</option>
                  <option value="normal" selected>🟡 一般（近期購買）</option>
                  <option value="low">🟢 不急（順路/特價再買）</option>
                </select>
              </div>

              <div class="shopping-field-submit">
                <button type="submit" class="btn btn-primary" style="width: 100%; height: 39px;">
                  ➕ 新增待買
                </button>
              </div>
            </div>

            <!-- 記憶地點快選膠囊列 -->
            <div class="shopping-quick-loc-row">
              <span class="quick-loc-label">⚡ 點擊快速帶入常用/記憶地點：</span>
              <div class="quick-loc-chips">
                ${pinnedChipsHtml}
              </div>
            </div>
          </form>

          <!-- 檢視模式切換列：依急迫性檢視 vs 依購買地點分組檢視 vs 採買歷史紀錄 -->
          <div class="shopping-toolbar">
            <div class="tab-group">
              <button
                type="button"
                class="tab-btn ${activeView === "urgency" ? "active" : ""}"
                data-shopping-view="urgency"
              >
                🔥 依急迫性檢視 (${stats.pending_total || 0})
              </button>
              <button
                type="button"
                class="tab-btn ${activeView === "location" ? "active" : ""}"
                data-shopping-view="location"
              >
                🏪 依購買地點分組檢視 (${stats.active_locations_count || 0} 店)
              </button>
              <button
                type="button"
                class="tab-btn ${activeView === "history" ? "active" : ""}"
                data-shopping-view="history"
              >
                📜 採買歷史紀錄 (${stats.history_total_count || 0})
              </button>
            </div>

            ${
              activeView === "urgency"
                ? this.renderCategoryFilterBar(categories, shoppingData.items || [])
                : activeView === "location"
                ? this.renderLocationFilterBar(shoppingData.grouped_by_location || [])
                : `<div class="history-spend-badge">💰 歷史累計記錄金額：<strong>NT$ ${(stats.history_total_spent || 0).toLocaleString()}</strong></div>`
            }
          </div>

          <!-- 主內容視圖區 -->
          <div class="shopping-content-area">
            ${
              activeView === "urgency"
                ? this.renderUrgencyView(shoppingData.items || [], categories, locations)
                : activeView === "location"
                ? this.renderLocationGroupedView(shoppingData.grouped_by_location || [], categories, locations)
                : this.renderHistoryView(shoppingData.history || [], stats)
            }
          </div>
        </div>

        <div class="widget-footer">
          <span>💡 提示：勾選「✅ 已購買」可選填購入金額並自動歸檔至歷史紀錄；地點設為 momo 或蝦皮等網購平台將自動產生商品搜尋連結。</span>
          <span>預設排序：🔴 緊急 → 🟡 一般 → 🟢 不急</span>
        </div>
      </article>
    `;

    this.bindEvents();
  },

  renderRecipeImporterPanel(defaultLoc) {
    const recipesHtml = cachedTodayRecipes.length
      ? cachedTodayRecipes
          .map(
            (r) => `
          <div class="recipe-import-chip">
            <div>
              <strong>🥘 ${escapeHtml(r.title)}</strong>
              <div style="font-size: 0.76rem; color: var(--text-muted); margin-top: 2px;">
                食材 (${(r.ingredients || []).length}項)：${escapeHtml((r.ingredients || []).map((i) => i.name.replace(/[\(（].*[\)）]/g, "")).join("、"))}
              </div>
            </div>
            <div style="display: flex; gap: 6px; align-items: center; flex-shrink: 0;">
              <button
                type="button"
                class="btn btn-primary btn-sm"
                data-import-recipe='${encodeURIComponent(JSON.stringify(r))}'
                data-include-seasonings="false"
              >
                🛒 匯入食材 (${(r.ingredients || []).length})
              </button>
              <button
                type="button"
                class="btn btn-outline btn-sm"
                data-import-recipe='${encodeURIComponent(JSON.stringify(r))}'
                data-include-seasonings="true"
                title="連同調味料一併匯入待買清單"
              >
                +含調味料
              </button>
            </div>
          </div>
        `
          )
          .join("")
      : `<p style="font-size: 0.84rem; color: var(--text-muted);">正在載入今日推薦自煮食譜...</p>`;

    return `
      <div class="shopping-subpanel">
        <div class="shopping-subpanel-header">
          <div>
            <strong>🥘 從今日推薦自煮食譜一鍵匯入食材</strong>
            <span style="font-size: 0.78rem; color: var(--text-secondary); margin-left: 8px;">
              自動標記為「🥬 生鮮食材」與「🔴 緊急（今日必買）」，您也可以在上方食譜詳細視窗中單獨匯入個別食材
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <label style="font-size: 0.78rem; color: var(--text-secondary);">匯入採買地點：</label>
            <input type="text" id="recipe-import-target-loc" class="form-control" style="width: 120px; padding: 4px 8px; font-size: 0.82rem;" value="${escapeHtml(defaultLoc)}" />
            <button type="button" class="btn-icon" id="btn-close-recipe-importer" style="width: 28px; height: 28px;">✕</button>
          </div>
        </div>
        <div class="recipe-import-grid">
          ${recipesHtml}
        </div>
      </div>
    `;
  },

  renderLocationManagerPanel(locations) {
    const locChips = locations
      .map(
        (l) => `
        <div class="managed-loc-card ${l.is_pinned ? "pinned" : ""}">
          <div style="display: flex; align-items: center; gap: 6px;">
            <span>${l.is_online ? "🛍️" : "🏪"}</span>
            <strong>${escapeHtml(l.name)}</strong>
            ${l.is_online ? `<span class="badge badge-accent" style="font-size: 0.68rem;">網購自動搜尋連結</span>` : ""}
            <span style="font-size: 0.73rem; color: var(--text-muted);">(${l.usage_count}次)</span>
          </div>
          <div style="display: flex; align-items: center; gap: 4px;">
            <button
              type="button"
              class="btn btn-outline btn-sm"
              style="padding: 2px 7px; font-size: 0.72rem;"
              data-loc-action="toggle_pin"
              data-loc-name="${escapeHtml(l.name)}"
              title="${l.is_pinned ? "取消常用釘選" : "設為常用釘選"}"
            >
              ${l.is_pinned ? "📌 常用" : "☆ 釘選"}
            </button>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              style="padding: 2px 7px; font-size: 0.72rem; color: #dc2626;"
              data-loc-action="delete"
              data-loc-name="${escapeHtml(l.name)}"
              title="從記憶清單中移除"
            >
              ✕
            </button>
          </div>
        </div>
      `
      )
      .join("");

    return `
      <div class="shopping-subpanel">
        <div class="shopping-subpanel-header">
          <div>
            <strong>📍 管理常用採買地點與記憶清單</strong>
            <span style="font-size: 0.78rem; color: var(--text-secondary); margin-left: 8px;">
              系統會自動記憶所有輸入過的地點；若包含 momo、蝦皮、PChome、酷澎、博客來、Yahoo、淘寶、Amazon 會自動啟用網購搜尋連結
            </span>
          </div>
          <button type="button" class="btn-icon" id="btn-close-location-manager" style="width: 28px; height: 28px;">✕</button>
        </div>
        <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
          <input
            type="text"
            id="new-managed-loc-name"
            class="form-control"
            style="max-width: 220px; font-size: 0.84rem;"
            placeholder="新增常用地點（如：寶雅、大潤發、酷澎）"
          />
          <input
            type="text"
            id="new-managed-loc-url"
            class="form-control"
            style="max-width: 320px; font-size: 0.84rem;"
            placeholder="自訂網購搜尋網址（選填，以 {q} 代表商品名）"
          />
          <button type="button" class="btn btn-primary btn-sm" id="btn-add-managed-loc">➕ 新增常用地點</button>
        </div>
        <div class="managed-loc-grid">
          ${locChips}
        </div>
      </div>
    `;
  },

  renderCategoryFilterBar(categories, items) {
    const counts = { ALL: items.length };
    for (const c of categories) counts[c] = 0;
    for (const it of items) {
      counts[it.category] = (counts[it.category] || 0) + 1;
    }

    const pills = [
      `<button type="button" class="filter-pill ${selectedCategoryFilter === "ALL" ? "active" : ""}" data-cat-filter="ALL">全部品類 (${counts.ALL})</button>`,
      ...categories
        .filter((c) => counts[c] > 0 || selectedCategoryFilter === c)
        .map(
          (c) => `
          <button type="button" class="filter-pill ${selectedCategoryFilter === c ? "active" : ""}" data-cat-filter="${escapeHtml(c)}">
            ${escapeHtml(c)} (${counts[c] || 0})
          </button>
        `
        ),
    ].join("");

    return `<div class="filter-pills-row">${pills}</div>`;
  },

  renderLocationFilterBar(locationGroups) {
    const pills = [
      `<button type="button" class="filter-pill ${selectedLocationFilter === "ALL" ? "active" : ""}" data-loc-filter="ALL">全部賣場 (${locationGroups.length} 店)</button>`,
      ...locationGroups.map(
        (g) => `
        <button type="button" class="filter-pill ${selectedLocationFilter === g.location ? "active" : ""}" data-loc-filter="${escapeHtml(g.location)}">
          ${g.is_online ? "🛍️" : "🏪"} ${escapeHtml(g.location)} (${g.total_count})
        </button>
      `
      ),
    ].join("");

    return `<div class="filter-pills-row">${pills}</div>`;
  },

  renderUrgencyView(items, categories, locations) {
    const filtered =
      selectedCategoryFilter === "ALL"
        ? items
        : items.filter((it) => it.category === selectedCategoryFilter);

    if (!filtered.length) {
      return `
        <div class="shopping-empty-state">
          <div style="font-size: 2rem; margin-bottom: 6px;">🎉</div>
          <strong>目前待買清單沒有符合條件的項目</strong>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            可在上方表單新增任何生活採買品項，或點擊「🥘 從自煮食譜一鍵匯入食材」！
          </p>
        </div>
      `;
    }

    const groups = [
      {
        code: "urgent",
        title: "🔴 緊急（今日必買）",
        desc: "優先採買項目，建議今日下班或出門時立刻購入",
        headerClass: "urgency-group-urgent",
        items: filtered.filter((x) => x.urgency === "urgent"),
      },
      {
        code: "normal",
        title: "🟡 一般（近期購買）",
        desc: "本週日常補給與網購待結帳項目",
        headerClass: "urgency-group-normal",
        items: filtered.filter((x) => x.urgency === "normal"),
      },
      {
        code: "low",
        title: "🟢 不急（順路/特價再買）",
        desc: "順路經過賣場或遇到促銷免運時再購入即可",
        headerClass: "urgency-group-low",
        items: filtered.filter((x) => x.urgency === "low"),
      },
    ];

    return groups
      .filter((g) => g.items.length > 0)
      .map(
        (g) => `
        <div class="shopping-group-section">
          <div class="shopping-group-header ${g.headerClass}">
            <div>
              <strong>${g.title}</strong>
              <span class="group-count-pill">${g.items.length} 項</span>
            </div>
            <span class="group-desc-text">${g.desc}</span>
          </div>
          <div class="shopping-items-list">
            ${g.items.map((item) => this.renderShoppingItemRow(item, categories, locations)).join("")}
          </div>
        </div>
      `
      )
      .join("");
  },

  renderLocationGroupedView(locationGroups, categories, locations) {
    const filteredGroups =
      selectedLocationFilter === "ALL"
        ? locationGroups
        : locationGroups.filter((g) => g.location === selectedLocationFilter);

    if (!filteredGroups.length) {
      return `
        <div class="shopping-empty-state">
          <div style="font-size: 2rem; margin-bottom: 6px;">🏪</div>
          <strong>目前沒有待買項目分組</strong>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            新增採買品項並輸入採買地點後，到達特定賣場即可在此集中查看該店所有待買清單！
          </p>
        </div>
      `;
    }

    return `
      <div class="location-groups-grid">
        ${filteredGroups
          .map(
            (g) => `
          <div class="location-group-card">
            <div class="location-group-header">
              <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                <span style="font-size: 1.2rem;">${g.is_online ? "🛍️" : "🏪"}</span>
                <h3 class="location-group-title">${escapeHtml(g.location)}</h3>
                <span class="badge ${g.is_online ? "badge-accent" : "badge-info"}">
                  ${g.is_online ? "網購平台 • 已啟用快速搜尋連結" : "實體賣場"}
                </span>
              </div>
              <div style="display: flex; align-items: center; gap: 6px;">
                ${g.urgent_count > 0 ? `<span class="badge badge-danger-soft">🔴 緊急 ${g.urgent_count}</span>` : ""}
                <span class="badge badge-success">待買 ${g.total_count} 項</span>
              </div>
            </div>
            <div class="shopping-items-list">
              ${g.items.map((item) => this.renderShoppingItemRow(item, categories, locations)).join("")}
            </div>
          </div>
        `
          )
          .join("")}
      </div>
    `;
  },

  renderShoppingItemRow(item, categories, locations) {
    const catSelectOptions = categories
      .map((c) => `<option value="${escapeHtml(c)}" ${c === item.category ? "selected" : ""}>${escapeHtml(c)}</option>`)
      .join("");

    const urgSelectOptions = [
      { code: "urgent", label: "🔴 緊急（今日必買）" },
      { code: "normal", label: "🟡 一般（近期購買）" },
      { code: "low", label: "🟢 不急（順路/特價再買）" },
    ]
      .map((u) => `<option value="${u.code}" ${u.code === item.urgency ? "selected" : ""}>${u.label}</option>`)
      .join("");

    // 若地點為網購平台（如 momo、蝦皮），自動在項目旁產生帶入該商品名稱的「快速搜尋連結」
    const onlineLinksHtml = (item.online_search_links || [])
      .map(
        (link) => `
        <a
          href="${escapeHtml(link.url)}"
          target="_blank"
          rel="noopener noreferrer"
          class="online-search-link-btn"
          title="在新分頁開啟 ${escapeHtml(link.platform)} 並自動帶入「${escapeHtml(link.keyword)}」搜尋"
        >
          ${escapeHtml(link.label)} ↗
        </a>
      `
      )
      .join("");

    return `
      <div class="shopping-item-row urgency-border-${item.urgency}" data-item-id="${item.id}">
        <div class="shopping-item-main">
          <!-- 勾選已購買核取按鈕 -->
          <button
            type="button"
            class="shopping-check-circle"
            data-complete-id="${item.id}"
            title="點擊勾選「已購買」並移入歷史紀錄"
            aria-label="勾選已購買"
          >
            ✓
          </button>

          <div class="shopping-item-info">
            <div class="shopping-item-title-line">
              <strong class="shopping-item-name">${escapeHtml(item.name)}</strong>
              ${
                item.quantity_note
                  ? `<span class="shopping-item-note">${escapeHtml(item.quantity_note)}</span>`
                  : ""
              }
              ${
                item.source_recipe
                  ? `<span class="badge badge-accent" style="font-size: 0.7rem;">🥘 食譜：${escapeHtml(item.source_recipe)}</span>`
                  : ""
              }
              ${onlineLinksHtml}
            </div>

            <!-- 可隨時手動調整的分類、採買地點與急迫性控制列 -->
            <div class="shopping-item-meta-controls">
              <div class="inline-meta-field" title="點擊可手動修改商品分類">
                <select class="inline-select" data-update-field="category" data-item-id="${item.id}" aria-label="修改商品分類">
                  ${catSelectOptions}
                </select>
                ${item.auto_categorized ? `<span class="auto-tag" title="由系統自動判斷分類">自動分類</span>` : ""}
              </div>

              <div class="inline-meta-field" title="修改採買地點（若改為 momo/蝦皮 將自動產生快速搜尋連結）">
                <span class="meta-icon">${item.is_online_location ? "🛍️" : "📍"}</span>
                <input
                  type="text"
                  class="inline-loc-input"
                  list="shopping-locations-datalist"
                  value="${escapeHtml(item.location)}"
                  data-update-field="location"
                  data-item-id="${item.id}"
                  aria-label="修改採買地點"
                />
              </div>

              <div class="inline-meta-field" title="調整急迫性分級">
                <select class="inline-select urgency-select-${item.urgency}" data-update-field="urgency" data-item-id="${item.id}" aria-label="修改急迫性">
                  ${urgSelectOptions}
                </select>
              </div>
            </div>
          </div>
        </div>

        <!-- 右側：選填購入金額 + 已購買歸檔按鈕 + 刪除 -->
        <div class="shopping-item-actions">
          <div class="purchase-price-group">
            <span class="currency-prefix">NT$</span>
            <input
              type="number"
              step="1"
              min="0"
              class="purchase-price-input"
              id="purchase-price-${item.id}"
              placeholder="金額(選填)"
              aria-label="選填購入金額"
            />
          </div>
          <button
            type="button"
            class="btn btn-success-soft btn-sm"
            data-complete-id="${item.id}"
            title="標記為已購買並轉存至採買歷史紀錄"
          >
            ✅ 已購買
          </button>
          <button
            type="button"
            class="btn btn-outline btn-sm"
            data-delete-id="${item.id}"
            title="從待買清單移除（不存入歷史）"
            style="color: var(--text-muted);"
          >
            🗑️
          </button>
        </div>
      </div>
    `;
  },

  renderHistoryView(historyItems, stats) {
    const rowsHtml = historyItems.length
      ? historyItems
          .map((h) => {
            const onlineLinksHtml = (h.online_search_links || [])
              .map(
                (link) => `
                <a
                  href="${escapeHtml(link.url)}"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="online-search-link-btn"
                >
                  ${escapeHtml(link.label)} ↗
                </a>
              `
              )
              .join("");

            return `
              <div class="history-item-row">
                <div class="history-item-left">
                  <span class="history-date-badge">📅 ${escapeHtml(h.purchased_date)}</span>
                  <div>
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                      <strong style="font-size: 0.96rem;">${escapeHtml(h.name)}</strong>
                      ${h.quantity_note ? `<span class="shopping-item-note">${escapeHtml(h.quantity_note)}</span>` : ""}
                      <span class="badge badge-info">${escapeHtml(h.category)}</span>
                      <span class="badge badge-outline-loc">📍 ${escapeHtml(h.location)}</span>
                      ${onlineLinksHtml}
                    </div>
                  </div>
                </div>

                <div class="history-item-right">
                  <div class="purchase-price-group" title="可隨時補填或修改購入金額">
                    <span class="currency-prefix">NT$</span>
                    <input
                      type="number"
                      step="1"
                      min="0"
                      class="purchase-price-input"
                      value="${h.price !== null && h.price !== undefined ? h.price : ""}"
                      placeholder="未填金額"
                      data-history-price-id="${h.id}"
                      aria-label="購入金額"
                    />
                  </div>
                  <button
                    type="button"
                    class="btn btn-primary btn-sm"
                    data-repurchase-id="${h.id}"
                    title="一鍵將此常買品項重新加入待買清單（保留原分類與購買地點）"
                  >
                    🔄 再次購買
                  </button>
                  <button
                    type="button"
                    class="btn btn-outline btn-sm"
                    data-delete-history-id="${h.id}"
                    title="刪除此筆歷史紀錄"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            `;
          })
          .join("")
      : `
        <div class="shopping-empty-state">
          <div style="font-size: 1.8rem; margin-bottom: 6px;">📜</div>
          <strong>${historySearchQuery ? `找不到符合「${escapeHtml(historySearchQuery)}」的採買歷史紀錄` : "目前尚無已購買歷史紀錄"}</strong>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            在待買清單勾選「✅ 已購買」後，系統會自動記錄購買日期、品項、分類、地點與金額於此。
          </p>
        </div>
      `;

    return `
      <div class="history-search-bar">
        <div style="display: flex; align-items: center; gap: 8px; flex: 1; max-width: 460px;">
          <input
            type="search"
            id="shopping-history-search"
            class="form-control"
            value="${escapeHtml(historySearchQuery)}"
            placeholder="🔍 關鍵字搜尋歷史紀錄（品項名稱、分類、購買地點如：全聯、鮮奶、B群...）"
          />
          ${
            historySearchQuery
              ? `<button type="button" class="btn btn-outline btn-sm" id="btn-clear-history-search">清除</button>`
              : ""
          }
        </div>
        <span style="font-size: 0.8rem; color: var(--text-secondary);">
          共顯示 ${historyItems.length} 筆紀錄 • 點擊「🔄 再次購買」即可一鍵重新加入待買清單
        </span>
      </div>
      <div class="history-items-list">
        ${rowsHtml}
      </div>
    `;
  },

  bindEvents() {
    // 1. 品項名稱輸入時，即時預覽自動判斷的商品類型標籤
    const nameInput = currentContainer.querySelector("#shopping-input-name");
    const catSelect = currentContainer.querySelector("#shopping-input-category");
    const previewEl = currentContainer.querySelector("#shopping-auto-cat-preview");
    if (nameInput && previewEl) {
      nameInput.addEventListener("input", () => {
        const val = nameInput.value.trim();
        if (!val) {
          previewEl.textContent = "✨ 輸入名稱自動預判分類";
          return;
        }
        const predicted = predictCategoryClient(val);
        previewEl.textContent = `✨ 自動判斷：${predicted}`;
      });
    }

    // 2. 點擊常用地點快選膠囊
    const locInput = currentContainer.querySelector("#shopping-input-location");
    currentContainer.querySelectorAll("[data-quick-loc]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const loc = btn.getAttribute("data-quick-loc");
        if (locInput && loc) {
          locInput.value = loc;
          localStorage.setItem("pref_shopping_location", loc);
        }
      });
    });

    // 3. 新增採買品項表單送出
    const addForm = currentContainer.querySelector("#shopping-add-form");
    if (addForm) {
      addForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const name = nameInput.value.trim();
        if (!name) return;
        const noteInput = currentContainer.querySelector("#shopping-input-note");
        const urgSelect = currentContainer.querySelector("#shopping-input-urgency");
        const locationVal = (locInput?.value || "全聯").trim() || "全聯";
        localStorage.setItem("pref_shopping_location", locationVal);

        const payload = {
          name,
          quantity_note: noteInput ? noteInput.value.trim() : "",
          category: catSelect ? catSelect.value : "auto",
          location: locationVal,
          urgency: urgSelect ? urgSelect.value : "normal",
          history_query: historySearchQuery,
        };

        const res = await fetch("/api/modules/shopping/items", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          if (activeView === "history") activeView = "urgency";
          selectedCategoryFilter = "ALL";
          this.render();
          showToast(
            `🛒 已新增「${name}」(${json.added.category}${json.added.auto_categorized ? " • 自動分類" : ""}) @ ${locationVal}`
          );
        }
      });
    }

    // 4. 切換檢視模式（依急迫性檢視 / 依購買地點分組檢視 / 採買歷史紀錄）
    currentContainer.querySelectorAll("[data-shopping-view]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeView = btn.getAttribute("data-shopping-view");
        this.render();
      });
    });

    // 5. 品類過濾膠囊與地點過濾膠囊
    currentContainer.querySelectorAll("[data-cat-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedCategoryFilter = btn.getAttribute("data-cat-filter");
        this.render();
      });
    });
    currentContainer.querySelectorAll("[data-loc-filter]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedLocationFilter = btn.getAttribute("data-loc-filter");
        this.render();
      });
    });

    // 6. 待買項目行內即時修改（手動修改分類、修改採買地點、調整急迫性）
    currentContainer.querySelectorAll("[data-update-field]").forEach((el) => {
      const eventType = el.tagName === "SELECT" ? "change" : "change";
      el.addEventListener(eventType, async () => {
        const itemId = parseInt(el.getAttribute("data-item-id"), 10);
        const field = el.getAttribute("data-update-field");
        const val = el.value.trim();
        if (!itemId || !field || !val) return;

        const res = await fetch("/api/modules/shopping/items/update", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: itemId,
            [field]: val,
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast(`✅ 已更新項目${field === "category" ? "分類" : field === "location" ? "採買地點" : "急迫性"}為「${val}」`);
        }
      });
    });

    // 7. 勾選「已購買」歸檔至歷史紀錄（含選填購入金額）
    currentContainer.querySelectorAll("[data-complete-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const itemId = parseInt(btn.getAttribute("data-complete-id"), 10);
        const priceEl = currentContainer.querySelector(`#purchase-price-${itemId}`);
        const priceVal = priceEl && priceEl.value.trim() !== "" ? parseFloat(priceEl.value) : null;

        const res = await fetch("/api/modules/shopping/items/complete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            id: itemId,
            price: priceVal,
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          const priceStr = json.completed?.price != null ? ` (購入金額 NT$ ${json.completed.price})` : "";
          showToast(`🎉 已完成採買「${json.completed?.name || ""}」${priceStr}，已歸檔至歷史紀錄！`);
        }
      });
    });

    // 8. 刪除待買品項
    currentContainer.querySelectorAll("[data-delete-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const itemId = parseInt(btn.getAttribute("data-delete-id"), 10);
        const res = await fetch("/api/modules/shopping/items/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id: itemId, history_query: historySearchQuery }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast("🗑️ 已從待買清單移除該項目");
        }
      });
    });

    // 9. 歷史紀錄關鍵字搜尋
    const histSearchInput = currentContainer.querySelector("#shopping-history-search");
    if (histSearchInput) {
      let debounceTimer = null;
      histSearchInput.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          historySearchQuery = histSearchInput.value;
          await this.loadData();
          const newInput = currentContainer.querySelector("#shopping-history-search");
          if (newInput) {
            newInput.focus();
            newInput.setSelectionRange(newInput.value.length, newInput.value.length);
          }
        }, 220);
      });
    }
    const clearSearchBtn = currentContainer.querySelector("#btn-clear-history-search");
    if (clearSearchBtn) {
      clearSearchBtn.addEventListener("click", async () => {
        historySearchQuery = "";
        await this.loadData();
      });
    }

    // 10. 歷史紀錄「🔄 再次購買」按鈕
    currentContainer.querySelectorAll("[data-repurchase-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const historyId = parseInt(btn.getAttribute("data-repurchase-id"), 10);
        const res = await fetch("/api/modules/shopping/history/repurchase", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ history_id: historyId, history_query: historySearchQuery }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast(`🔄 已將「${json.repurchased?.name}」重新加入待買清單 (@ ${json.repurchased?.location})！`);
        }
      });
    });

    // 11. 歷史紀錄修改/補填購入金額
    currentContainer.querySelectorAll("[data-history-price-id]").forEach((input) => {
      input.addEventListener("change", async () => {
        const historyId = parseInt(input.getAttribute("data-history-price-id"), 10);
        const priceVal = input.value.trim() !== "" ? parseFloat(input.value) : null;
        const res = await fetch("/api/modules/shopping/history/price", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            history_id: historyId,
            price: priceVal,
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast("💰 已更新歷史紀錄購入金額");
        }
      });
    });

    // 12. 刪除單筆歷史紀錄
    currentContainer.querySelectorAll("[data-delete-history-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const historyId = parseInt(btn.getAttribute("data-delete-history-id"), 10);
        const res = await fetch("/api/modules/shopping/history/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ history_id: historyId, history_query: historySearchQuery }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast("🗑️ 已刪除該筆歷史紀錄");
        }
      });
    });

    // 13. 展開/收合「從自煮食譜一鍵匯入食材」面板
    const toggleRecipeBtn = currentContainer.querySelector("#btn-toggle-recipe-importer");
    const closeRecipeBtn = currentContainer.querySelector("#btn-close-recipe-importer");
    if (toggleRecipeBtn) {
      toggleRecipeBtn.addEventListener("click", async () => {
        showRecipeImporter = !showRecipeImporter;
        if (showRecipeImporter) {
          await this.loadTodayRecipesForQuickImport();
        }
        this.render();
      });
    }
    if (closeRecipeBtn) {
      closeRecipeBtn.addEventListener("click", () => {
        showRecipeImporter = false;
        this.render();
      });
    }

    currentContainer.querySelectorAll("[data-import-recipe]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const recipe = JSON.parse(decodeURIComponent(btn.getAttribute("data-import-recipe")));
        const includeSeasonings = btn.getAttribute("data-include-seasonings") === "true";
        const targetLocEl = currentContainer.querySelector("#recipe-import-target-loc");
        const targetLoc = (targetLocEl?.value || "全聯").trim() || "全聯";

        const res = await fetch("/api/modules/shopping/import-recipe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            recipe_title: recipe.title,
            ingredients: recipe.ingredients || [],
            include_seasonings: includeSeasonings,
            seasonings: recipe.seasonings || [],
            location: targetLoc,
            urgency: "urgent",
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          activeView = "urgency";
          this.render();
          showToast(`🥘 已從「${recipe.title}」一鍵匯入 ${json.imported.imported_count} 項食材至待買清單 (@ ${targetLoc})！`);
        }
      });
    });

    // 14. 展開/收合「管理常用地點清單」面板
    const toggleLocBtn = currentContainer.querySelector("#btn-toggle-location-manager");
    const closeLocBtn = currentContainer.querySelector("#btn-close-location-manager");
    if (toggleLocBtn) {
      toggleLocBtn.addEventListener("click", () => {
        showLocationManager = !showLocationManager;
        this.render();
      });
    }
    if (closeLocBtn) {
      closeLocBtn.addEventListener("click", () => {
        showLocationManager = false;
        this.render();
      });
    }

    const addManagedLocBtn = currentContainer.querySelector("#btn-add-managed-loc");
    if (addManagedLocBtn) {
      addManagedLocBtn.addEventListener("click", async () => {
        const nameEl = currentContainer.querySelector("#new-managed-loc-name");
        const urlEl = currentContainer.querySelector("#new-managed-loc-url");
        const locName = (nameEl?.value || "").trim();
        if (!locName) return;

        const res = await fetch("/api/modules/shopping/locations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "add",
            name: locName,
            search_url_template: (urlEl?.value || "").trim(),
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast(`📍 已新增並記憶常用地點：「${locName}」`);
        }
      });
    }

    currentContainer.querySelectorAll("[data-loc-action]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const action = btn.getAttribute("data-loc-action");
        const locName = btn.getAttribute("data-loc-name");
        const res = await fetch("/api/modules/shopping/locations", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action,
            name: locName,
            history_query: historySearchQuery,
          }),
        });
        const json = await res.json();
        if (json.ok) {
          shoppingData = json.data;
          this.render();
          showToast(action === "delete" ? `🗑️ 已移除記憶地點「${locName}」` : `📌 已更新「${locName}」常用釘選狀態`);
        }
      });
    });
  },
};
