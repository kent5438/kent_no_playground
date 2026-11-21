/**
 * 模組 1：中央氣象署 (CWA) 天氣預報 UI 卡片元件
 * - 支援未來 24-48 小時逐時預報 & 未來 7 天每週預報切換
 * - 支援台灣縣市與鄉鎮區即時下拉選單切換與搜尋過濾 (預設：新竹縣竹東鎮)
 * - 偏好設定同步儲存於 LocalStorage 與後端 SQLite 資料庫
 */
import { showToast } from "../core/widgetRegistry.js";

let currentContainer = null;
let currentContext = null;
let activeView = "hourly"; // 'hourly' | 'weekly'
let weatherData = null;

export const WeatherWidget = {
  id: "weather",
  name: "中央氣象署 (CWA) 天氣預報",
  description: "逐時 (24-48hr) 與每週 (7天) 氣溫、降雨機率/降雨量 (mm)、風速/風向預報",
  slotSelector: "#widget-slot-top",

  async mount(container, context) {
    currentContainer = container;
    currentContext = context;
    await this.loadData(false);
  },

  async refresh() {
    await this.loadData(true);
  },

  async loadData(forceRefresh = false) {
    const savedCounty = localStorage.getItem("pref_county") || currentContext?.settings?.county || "新竹縣";
    const savedTown = localStorage.getItem("pref_town") || currentContext?.settings?.town || "竹東鎮";

    const url = `/api/modules/weather?county=${encodeURIComponent(savedCounty)}&town=${encodeURIComponent(savedTown)}&refresh=${forceRefresh}`;
    const res = await fetch(url);
    weatherData = await res.json();
    this.render();
  },

  render() {
    if (!currentContainer || !weatherData) return;
    const loc = weatherData.location;
    const cur = weatherData.current;
    const locationsMap = currentContext?.locations || { "新竹縣": [{ town: "竹東鎮", lat: 24.7376, lng: 121.0887 }] };
    const counties = Object.keys(locationsMap);
    const townsForCounty = locationsMap[loc.county] || [{ town: loc.town }];

    const countyOptionsHtml = counties
      .map((c) => `<option value="${c}" ${c === loc.county ? "selected" : ""}>${c}</option>`)
      .join("");

    const townOptionsHtml = townsForCounty
      .map((t) => `<option value="${t.town}" ${t.town === loc.town ? "selected" : ""}>${t.town}</option>`)
      .join("");

    const updatedTimeStr = weatherData.updated_at
      ? new Date(weatherData.updated_at).toLocaleTimeString("zh-TW", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      : "";

    currentContainer.innerHTML = `
      <article class="widget-card">
        <div class="widget-header">
          <div class="widget-title-group">
            <span class="widget-icon">🌤️</span>
            <div>
              <h2 class="widget-title">中央氣象署（CWA）即時與未來天氣預報</h2>
              <p class="widget-subtitle">目前設定地點：<strong>${loc.full_name}</strong> • 每日自動排程更新</p>
            </div>
          </div>

          <div class="widget-controls">
            <select id="weather-quick-county" class="form-control" style="width: auto; padding: 5px 10px; font-size: 0.84rem;" aria-label="選擇縣市">
              ${countyOptionsHtml}
            </select>
            <select id="weather-quick-town" class="form-control" style="width: auto; padding: 5px 10px; font-size: 0.84rem;" aria-label="選擇鄉鎮市區">
              ${townOptionsHtml}
            </select>
            <button class="btn btn-outline btn-sm" id="btn-weather-refresh" title="立即向氣象服務重新抓取">
              🔄 手動重新整理
            </button>
          </div>
        </div>

        <div class="widget-body">
          <div class="weather-top-grid">
            <!-- 左側：當前天氣摘要卡片 -->
            <div class="weather-current-box">
              <div>
                <div class="weather-loc-badge">📍 ${loc.county} ${loc.town}</div>
                <div class="weather-main-temp" style="margin-top: 12px;">
                  <span class="weather-big-icon">${cur.icon}</span>
                  <div>
                    <div class="weather-big-deg">${cur.temp}°C</div>
                    <div class="weather-cond-text">${cur.condition} • ${cur.comfort}</div>
                  </div>
                </div>
              </div>

              <div class="weather-metrics-grid">
                <div class="weather-metric-item">
                  <span>今日高低溫</span>
                  <strong>${cur.min_temp}° ~ ${cur.max_temp}°C</strong>
                </div>
                <div class="weather-metric-item">
                  <span>降雨機率 / 雨量</span>
                  <strong>💧 ${cur.pop}% (${cur.rainfall_mm} mm)</strong>
                </div>
                <div class="weather-metric-item">
                  <span>風向 / 風級</span>
                  <strong>🧭 ${cur.wind_dir} (${cur.wind_scale})</strong>
                </div>
                <div class="weather-metric-item">
                  <span>平均風速</span>
                  <strong>💨 ${cur.wind_speed_ms} m/s</strong>
                </div>
              </div>
            </div>

            <!-- 右側：逐時預報 (24-48小時) 與 每週預報 (7天) 切換區 -->
            <div style="min-width: 0;">
              <div class="weather-tabs-header">
                <div class="tab-group" role="tablist">
                  <button class="tab-btn ${activeView === "hourly" ? "active" : ""}" data-weather-tab="hourly">
                    ⏱️ 每小時預報 (未來 36 小時)
                  </button>
                  <button class="tab-btn ${activeView === "weekly" ? "active" : ""}" data-weather-tab="weekly">
                    📅 每週預報 (未來 7 天)
                  </button>
                </div>
                <span class="badge badge-info">包含：氣溫 (°C) • 降雨機率/雨量 (mm) • 風速/風向</span>
              </div>

              ${activeView === "hourly" ? this.renderHourlyHtml(weatherData.hourly) : this.renderWeeklyHtml(weatherData.weekly)}
            </div>
          </div>
        </div>

        <div class="widget-footer">
          <span>資料來源：${weatherData.source}</span>
          <span>最後更新時間：${updatedTimeStr}</span>
        </div>
      </article>
    `;

    this.bindEvents();
  },

  renderHourlyHtml(hourlyList = []) {
    const itemsHtml = hourlyList
      .map(
        (h) => `
        <div class="hourly-item">
          <span class="hourly-date-tag">${h.date_label}</span>
          <div class="hourly-time">${h.time}</div>
          <div class="hourly-icon" title="${h.condition}">${h.icon}</div>
          <div class="hourly-temp">${h.temp}°C</div>
          <div class="hourly-rain" title="預估降雨量 ${h.rainfall_mm} mm">💧 ${h.pop}% / ${h.rainfall_mm}mm</div>
          <div class="hourly-wind">💨 ${h.wind_dir}<br/>${h.wind_speed_ms}m/s (${h.wind_scale})</div>
        </div>
      `
      )
      .join("");
    return `<div class="hourly-scroll">${itemsHtml}</div>`;
  },

  renderWeeklyHtml(weeklyList = []) {
    const cardsHtml = weeklyList
      .map(
        (d) => `
        <div class="weekly-card">
          <div class="weekly-day">${d.day_name}</div>
          <div class="weekly-date">${d.date}</div>
          <div class="weekly-icon" title="${d.condition}">${d.icon}</div>
          <div style="font-size: 0.78rem; font-weight: 600; color: var(--text-secondary);">${d.condition}</div>
          <div class="weekly-temps">
            <span>${d.max_temp}°</span> / <span class="low">${d.min_temp}°C</span>
          </div>
          <div class="hourly-rain">💧 ${d.pop}% (${d.rainfall_mm}mm)</div>
          <div class="weekly-meta">💨 ${d.wind_summary}</div>
        </div>
      `
      )
      .join("");
    return `<div class="weekly-grid">${cardsHtml}</div>`;
  },

  bindEvents() {
    // 切換每小時 / 每週分頁
    currentContainer.querySelectorAll("[data-weather-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeView = btn.getAttribute("data-weather-tab");
        this.render();
      });
    });

    // 手動重新整理按鈕
    const refreshBtn = currentContainer.querySelector("#btn-weather-refresh");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "⏳ 更新中...";
        await this.loadData(true);
        showToast(`✅ 已更新 ${weatherData.location.full_name} 最新氣象預報`);
      });
    }

    // 快速切換縣市與鄉鎮
    const countySelect = currentContainer.querySelector("#weather-quick-county");
    const townSelect = currentContainer.querySelector("#weather-quick-town");

    if (countySelect) {
      countySelect.addEventListener("change", async () => {
        const newCounty = countySelect.value;
        const locationsMap = currentContext?.locations || {};
        const firstTownObj = (locationsMap[newCounty] && locationsMap[newCounty][0]) || { town: "", lat: 24.7376, lng: 121.0887 };
        await this.applyLocationChange(newCounty, firstTownObj.town, firstTownObj.lat, firstTownObj.lng);
      });
    }

    if (townSelect) {
      townSelect.addEventListener("change", async () => {
        const county = countySelect.value;
        const newTown = townSelect.value;
        const locationsMap = currentContext?.locations || {};
        const townObj = (locationsMap[county] || []).find((t) => t.town === newTown) || { lat: 24.7376, lng: 121.0887 };
        await this.applyLocationChange(county, newTown, townObj.lat, townObj.lng);
      });
    }
  },

  async applyLocationChange(county, town, lat, lng) {
    localStorage.setItem("pref_county", county);
    localStorage.setItem("pref_town", town);
    localStorage.setItem("pref_lat", String(lat));
    localStorage.setItem("pref_lng", String(lng));

    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ county, town, lat, lng, refresh_modules: true }),
    });

    if (currentContext && currentContext.onSettingsUpdated) {
      await currentContext.onSettingsUpdated();
    } else {
      await this.loadData(true);
    }
    showToast(`📍 已切換地點至「${county}${town}」，並同步儲存偏好設定`);
  },
};
