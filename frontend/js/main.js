/**
 * 個人每日生活與飲食儀表板 - 前端主入口 (main.js)
 * 負責：
 * 1. 初始化並註冊三大核心 Widget 模組（氣象、外食三選一、每兩小時自煮食譜）
 * 2. 管理全域設定 Modal（預設新竹縣竹東鎮，支援儲存於 LocalStorage 與 SQLite）
 * 3. 管理 Widget / Plugin 擴充架構預覽 Modal（展示如何一鍵開啟待辦/採買清單或高鐵時刻表模組）
 */
import { widgetRegistry, showToast } from "./core/widgetRegistry.js";
import { WeatherWidget } from "./widgets/weatherWidget.js";
import { DiningWidget } from "./widgets/diningWidget.js";
import { RecipesWidget } from "./widgets/recipesWidget.js";
import { ShoppingWidget } from "./widgets/shoppingWidget.js";

// 註冊四大核心與擴充生活模組
widgetRegistry.register(WeatherWidget);
widgetRegistry.register(DiningWidget);
widgetRegistry.register(RecipesWidget);
widgetRegistry.register(ShoppingWidget);

let globalContext = {
  settings: null,
  locations: {},
  systemStatus: null,
  onSettingsUpdated: async () => {
    await refreshAllContextAndWidgets();
  },
};

async function fetchInitialContext() {
  const [settingsRes, statusRes] = await Promise.all([
    fetch("/api/settings"),
    fetch("/api/system/status"),
  ]);
  const settingsData = await settingsRes.json();
  const statusData = await statusRes.json();

  globalContext.settings = settingsData.settings;
  globalContext.locations = settingsData.locations;
  globalContext.systemStatus = statusData;

  const pluginCountEl = document.getElementById("plugin-count");
  if (pluginCountEl) {
    pluginCountEl.textContent = String(widgetRegistry.listWidgets().length);
  }

  const lanUrlEl = document.getElementById("lan-url-text");
  if (lanUrlEl && statusData?.network) {
    const net = statusData.network;
    const primaryLanUrl = (net.lan_urls && net.lan_urls[0]) || net.bind_url || `http://0.0.0.0:${net.port || 8000}`;
    lanUrlEl.textContent = primaryLanUrl.replace(/^http:\/\//, "");
  }

  // 若 LocalStorage 尚無紀錄，寫入預設值（新竹縣竹東鎮）
  if (!localStorage.getItem("pref_county")) {
    localStorage.setItem("pref_county", globalContext.settings.county);
    localStorage.setItem("pref_town", globalContext.settings.town);
    localStorage.setItem("pref_lat", String(globalContext.settings.lat));
    localStorage.setItem("pref_lng", String(globalContext.settings.lng));
    localStorage.setItem("pref_radius", String(globalContext.settings.radius));
  }
}

async function refreshAllContextAndWidgets() {
  await fetchInitialContext();
  await widgetRegistry.mountAll(globalContext);
}

function startLiveClock() {
  const el = document.getElementById("clock-text");
  if (!el) return;
  const update = () => {
    const now = new Date();
    const dateStr = now.toLocaleDateString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      weekday: "short",
    });
    const timeStr = now.toLocaleTimeString("zh-TW", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
    el.textContent = `${dateStr} ${timeStr}`;
  };
  update();
  setInterval(update, 1000);
}

function initSettingsModal() {
  const modal = document.getElementById("settings-modal");
  const openBtn = document.getElementById("btn-open-settings");
  const closeBtn = document.getElementById("btn-close-settings-modal");
  const form = document.getElementById("settings-form");
  const countySelect = document.getElementById("setting-county");
  const townSelect = document.getElementById("setting-town");
  const latInput = document.getElementById("setting-lat");
  const lngInput = document.getElementById("setting-lng");
  const radiusInput = document.getElementById("setting-radius");
  const resetBtn = document.getElementById("btn-reset-zhudong");

  const populateTowns = (county, selectedTown) => {
    const towns = globalContext.locations[county] || [];
    townSelect.innerHTML = towns
      .map((t) => `<option value="${t.town}" ${t.town === selectedTown ? "selected" : ""}>${t.town}</option>`)
      .join("");
  };

  openBtn.addEventListener("click", () => {
    const s = globalContext.settings;
    const counties = Object.keys(globalContext.locations);
    countySelect.innerHTML = counties
      .map((c) => `<option value="${c}" ${c === s.county ? "selected" : ""}>${c}</option>`)
      .join("");
    populateTowns(s.county, s.town);
    latInput.value = s.lat;
    lngInput.value = s.lng;
    radiusInput.value = s.radius;
    modal.classList.remove("hidden");
  });

  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });

  countySelect.addEventListener("change", () => {
    const county = countySelect.value;
    const towns = globalContext.locations[county] || [];
    const first = towns[0] || { town: "", lat: 24.7376, lng: 121.0887 };
    populateTowns(county, first.town);
    latInput.value = first.lat;
    lngInput.value = first.lng;
  });

  townSelect.addEventListener("change", () => {
    const county = countySelect.value;
    const town = townSelect.value;
    const found = (globalContext.locations[county] || []).find((t) => t.town === town);
    if (found) {
      latInput.value = found.lat;
      lngInput.value = found.lng;
    }
  });

  resetBtn.addEventListener("click", () => {
    countySelect.value = "新竹縣";
    populateTowns("新竹縣", "竹東鎮");
    latInput.value = 24.7376;
    lngInput.value = 121.0887;
    radiusInput.value = 2500;
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = {
      county: countySelect.value,
      town: townSelect.value,
      lat: parseFloat(latInput.value),
      lng: parseFloat(lngInput.value),
      radius: parseInt(radiusInput.value, 10),
      refresh_modules: true,
    };

    localStorage.setItem("pref_county", payload.county);
    localStorage.setItem("pref_town", payload.town);
    localStorage.setItem("pref_lat", String(payload.lat));
    localStorage.setItem("pref_lng", String(payload.lng));
    localStorage.setItem("pref_radius", String(payload.radius));

    await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    modal.classList.add("hidden");
    await refreshAllContextAndWidgets();
    showToast(`✅ 已儲存設定：${payload.county}${payload.town} (半徑 ${payload.radius}m)`);
  });
}

function initPluginModal() {
  const modal = document.getElementById("plugin-modal");
  const openBtn = document.getElementById("btn-open-plugin-modal");
  const closeBtn = document.getElementById("btn-close-plugin-modal");
  const bodyEl = document.getElementById("plugin-modal-body");

  openBtn.addEventListener("click", () => {
    const activeWidgets = widgetRegistry.listWidgets();
    const apiStatus = globalContext.systemStatus?.api_keys_configured || {};
    const netInfo = globalContext.systemStatus?.network || {};
    const lanUrlsHtml = (netInfo.lan_urls || []).length
      ? netInfo.lan_urls.map((u) => `<code>${u}</code>`).join(" 、 ")
      : `<code>${netInfo.bind_url || "http://0.0.0.0:8000"}</code>`;

    bodyEl.innerHTML = `
      <div class="form-hint-box" style="margin-bottom: 16px;">
        🌐 <strong>網路綁定狀態：</strong>Host 已綁定為 <code>${netInfo.host || "0.0.0.0"}:${netInfo.port || 8000}</code><br/>
        📱 <strong>區網跨裝置連線網址（手機/平板同網路直接開啟）：</strong>${lanUrlsHtml}
      </div>

      <div style="margin-bottom: 18px;">
        <h4 style="margin-bottom: 8px; font-size: 0.95rem;">🔑 外部 API 金鑰連線狀態 (.env)</h4>
        <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
          <div class="recipe-list-box">
            <div style="font-size: 0.78rem; color: var(--text-muted);">CWA 氣象開放資料</div>
            <strong style="font-size: 0.88rem; color: ${apiStatus.cwa ? "var(--success)" : "var(--primary)"};">
              ${apiStatus.cwa ? "● Live API 已連線" : "● 擬真預報模型 (Fallback)"}
            </strong>
          </div>
          <div class="recipe-list-box">
            <div style="font-size: 0.78rem; color: var(--text-muted);">Google Maps Places</div>
            <strong style="font-size: 0.88rem; color: ${apiStatus.google_maps ? "var(--success)" : "var(--primary)"};">
              ${apiStatus.google_maps ? "● Live API 已連線" : "● 在地竹東精選庫 (Fallback)"}
            </strong>
          </div>
          <div class="recipe-list-box">
            <div style="font-size: 0.78rem; color: var(--text-muted);">LLM 食譜生成 API</div>
            <strong style="font-size: 0.88rem; color: ${apiStatus.llm ? "var(--success)" : "var(--primary)"};">
              ${apiStatus.llm ? "● Live LLM 已連線" : "● 25道家常食譜庫 (Fallback)"}
            </strong>
          </div>
        </div>
      </div>

      <h4 style="margin-bottom: 8px; font-size: 0.95rem;">📦 已啟用的核心 Widget 模組 (${activeWidgets.length})</h4>
      <div style="display: flex; flex-direction: column; gap: 10px; margin-bottom: 18px;">
        ${activeWidgets
          .map(
            (w) => `
          <div class="place-card" style="padding: 12px 14px;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
              <div>
                <strong>${w.name}</strong> <code style="font-size: 0.76rem; color: var(--primary);">[${w.id}]</code>
                <div style="font-size: 0.8rem; color: var(--text-secondary);">${w.description || ""}</div>
              </div>
              <span class="badge badge-success">運作中 • 插槽 ${w.slotSelector}</span>
            </div>
          </div>
        `
          )
          .join("")}
      </div>

      <h4 style="margin-bottom: 8px; font-size: 0.95rem;">🚀 預留未來擴充模組插槽 (#widget-slot-extensions)</h4>
      <p style="font-size: 0.82rem; color: var(--text-secondary); margin-bottom: 10px;">
        系統已設計前後端雙向插件註冊器（<code>backend/core/module_registry.py</code> 與 <code>frontend/js/core/widgetRegistry.js</code>）。未來新增生活模組僅需註冊即可掛載：
      </p>
      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px;">
        <div class="recipe-list-box">
          <strong>🚄 高鐵時刻表模組</strong>
          <p style="font-size: 0.76rem; color: var(--text-muted); margin-top: 4px;">新竹站 ⇄ 台北/左營即時班次查詢卡片</p>
        </div>
        <div class="recipe-list-box">
          <strong>🛒 食材採買清單模組</strong>
          <p style="font-size: 0.76rem; color: var(--text-muted); margin-top: 4px;">自煮食譜一鍵匯入超市採買勾選清單</p>
        </div>
        <div class="recipe-list-box">
          <strong>✅ 每日待辦清單模組</strong>
          <p style="font-size: 0.76rem; color: var(--text-muted); margin-top: 4px;">個人日常任務與提醒事項管理卡片</p>
        </div>
      </div>
    `;
    modal.classList.remove("hidden");
  });

  closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.classList.add("hidden");
  });
}

async function bootstrap() {
  startLiveClock();
  await fetchInitialContext();
  await widgetRegistry.mountAll(globalContext);
  initSettingsModal();
  initPluginModal();
}

document.addEventListener("DOMContentLoaded", bootstrap);
