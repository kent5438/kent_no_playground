/**
 * 模組 2：住家周邊外食三選一（Google Maps 串接）UI 卡片元件
 * - 排程觸發時間：06:00 早餐、10:00 午餐、16:00 晚餐
 * - 篩選住家周邊營業中、評價 4.0★ 以上餐廳，隨機推薦不重複 3 間
 * - 顯示店名、評分、距離、營業狀態與一鍵開啟 Google Maps 導航連結
 */
import { showToast } from "../core/widgetRegistry.js";

let currentContainer = null;
let diningData = null;
let selectedPeriod = null; // 'breakfast' | 'lunch' | 'dinner'

export const DiningWidget = {
  id: "dining",
  name: "住家周邊外食三選一",
  description: "每日 06:00 / 10:00 / 16:00 自動搜尋住家周邊 4.0★ 以上營業中餐廳並隨機推薦 3 間",
  slotSelector: "#widget-slot-left",

  async mount(container) {
    currentContainer = container;
    await this.loadData();
  },

  async refresh() {
    await this.loadData();
  },

  async loadData() {
    const res = await fetch("/api/modules/dining");
    diningData = await res.json();
    if (!selectedPeriod) {
      selectedPeriod = diningData.active_period || "lunch";
    }
    this.render();
  },

  async rerollCurrentPeriod() {
    const period = selectedPeriod || "lunch";
    const res = await fetch("/api/modules/dining/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ period }),
    });
    diningData = await res.json();
    this.render();
    const periodObj = diningData.periods[period];
    showToast(`🎲 已為「${periodObj.label}」重新隨機挑選 3 間 4.0★+ 不重複餐廳！`);
  },

  render() {
    if (!currentContainer || !diningData) return;
    const loc = diningData.location;
    const periodObj = diningData.periods[selectedPeriod] || diningData.periods.lunch;
    const places = periodObj.places || [];
    const updatedStr = periodObj.updated_at
      ? new Date(periodObj.updated_at).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit" })
      : "";

    currentContainer.innerHTML = `
      <article class="widget-card">
        <div class="widget-header">
          <div class="widget-title-group">
            <span class="widget-icon">🍽️</span>
            <div>
              <h2 class="widget-title">今日三餐外食三選一推薦</h2>
              <p class="widget-subtitle">
                中心點：${loc.county}${loc.town} (${loc.lat.toFixed(4)}, ${loc.lng.toFixed(4)}) • 半徑 ${(loc.radius / 1000).toFixed(1)} km
              </p>
            </div>
          </div>

          <div class="widget-controls">
            <button class="btn btn-outline btn-sm" id="btn-dining-reroll" title="重新隨機抽選本餐期 3 間不重複的 4.0★+ 店家">
              🎲 換一組三選一
            </button>
          </div>
        </div>

        <div class="widget-body">
          <!-- 三餐時段切換 Tabs -->
          <div class="weather-tabs-header">
            <div class="tab-group" style="width: 100%; display: grid; grid-template-columns: repeat(3, 1fr);">
              <button class="tab-btn ${selectedPeriod === "breakfast" ? "active" : ""}" data-dining-period="breakfast">
                🥐 早餐 (06:00)
              </button>
              <button class="tab-btn ${selectedPeriod === "lunch" ? "active" : ""}" data-dining-period="lunch">
                🍱 午餐 (10:00)
              </button>
              <button class="tab-btn ${selectedPeriod === "dinner" ? "active" : ""}" data-dining-period="dinner">
                🍲 晚餐 (16:00)
              </button>
            </div>
          </div>

          <div class="dining-schedule-bar">
            <span>⏰ 排程更新時間：每日 <strong>${periodObj.scheduled_time}</strong> 自動觸發</span>
            <span class="badge badge-success">📏 嚴格篩選：半徑 ${loc.radius} 公尺內</span>
          </div>

          <div class="dining-cards-list">
            ${
              places.length === 0
                ? `
              <div class="shopping-empty-state">
                <div style="font-size: 1.8rem; margin-bottom: 6px;">📍</div>
                <strong>目前設定半徑 ${loc.radius} 公尺內找不到符合條件的餐廳</strong>
                <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
                  請點擊右上角「⚙️ 地點與座標設定」調大外食搜尋半徑（例如 1000 ~ 2500 公尺），或直接前往 Google Maps 探索周邊。
                </p>
              </div>
            `
                : places
                    .map(
                      (place, idx) => `
              <div class="place-card">
                <div class="place-card-top">
                  <div>
                    <div class="place-name">
                      <span class="place-rank-num">${idx + 1}</span>${place.name}
                    </div>
                    <div class="place-category">${place.category || "在地人氣餐廳"}</div>
                  </div>
                  ${
                    place.rating != null
                      ? `<span class="place-rating-badge" title="評價 ${place.rating} 顆星 (${place.reviews || 0} 則評論)">
                          ★ ${Number(place.rating).toFixed(1)} (${place.reviews || 0})
                        </span>`
                      : `<span class="badge badge-info">📍 真實地圖店家</span>`
                  }
                </div>

                <div class="place-meta-row">
                  <span class="place-status-open">● ${place.open_status_text || "營業中"}</span>
                  <span>📏 距離約 <strong>${place.distance_text}</strong></span>
                  <span>🕒 ${place.open_hours}</span>
                  <span>💰 ${place.price_level || "平價"}</span>
                </div>

                <div class="place-card-actions">
                  <span class="place-address">📍 ${place.address}</span>
                  <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
                    ${
                      place.maps_search_url
                        ? `<a href="${place.maps_search_url}" target="_blank" rel="noopener noreferrer" class="btn btn-outline btn-sm" title="在 Google Maps 查看此店家評價與實景">
                            🔍 查看店家
                          </a>`
                        : ""
                    }
                    <a href="${place.maps_url}" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" title="以精確座標開啟 Google Maps 導航">
                      🗺️ 精準導航
                    </a>
                  </div>
                </div>
              </div>
            `
                    )
                    .join("")
            }
          </div>
        </div>

        <div class="widget-footer">
          <span>資料來源：${periodObj.source}</span>
          <span>本輪生成時間：${updatedStr}</span>
        </div>
      </article>
    `;

    this.bindEvents();
  },

  bindEvents() {
    currentContainer.querySelectorAll("[data-dining-period]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedPeriod = btn.getAttribute("data-dining-period");
        this.render();
      });
    });

    const rerollBtn = currentContainer.querySelector("#btn-dining-reroll");
    if (rerollBtn) {
      rerollBtn.addEventListener("click", async () => {
        rerollBtn.disabled = true;
        rerollBtn.textContent = "⏳ 挑選中...";
        await this.rerollCurrentPeriod();
      });
    }
  },
};
