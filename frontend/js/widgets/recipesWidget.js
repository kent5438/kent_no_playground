/**
 * 模組 3：每兩小時自煮正餐推薦與歷史紀錄 UI 卡片元件
 * - 每日 06:00 起每隔 2 小時 (06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00...)
 *   自動生成新一輪「5 種家常自煮正餐料理」（下飯、家常、食材易得，避免連續兩輪重複）
 * - 點擊任一道料理展開彈出視窗檢視詳細食譜（2人份、精確克數/匙數、步驟與火候小撇步）
 * - 提供「最新自煮正餐推薦」與「今日歷史紀錄時間軸」切換，以及每日 00:00 自動清空前日紀錄
 */
import { showToast } from "../core/widgetRegistry.js";

let currentContainer = null;
let recipesData = null;
let activeTab = "latest"; // 'latest' | 'history'

export const RecipesWidget = {
  id: "recipes",
  name: "每兩小時自煮正餐推薦與歷史紀錄",
  description: "每 2 小時自動生成 5 道不重複家常下飯正餐，含 2 人份精確克數食譜與今日歷史時間軸",
  slotSelector: "#widget-slot-right",

  async mount(container) {
    currentContainer = container;
    await this.loadData();
    this.initModalHandlers();
  },

  async refresh() {
    await this.loadData();
  },

  async loadData() {
    const res = await fetch("/api/modules/recipes");
    recipesData = await res.json();
    this.render();
  },

  async triggerNewBatch() {
    const res = await fetch("/api/modules/recipes/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    recipesData = await res.json();
    activeTab = "latest";
    this.render();
    showToast("🍳 已生成新一輪 5 道不重複家常下飯料理，並自動存入今日歷史紀錄！");
  },

  render() {
    if (!currentContainer || !recipesData) return;
    const latest = recipesData.latest;
    const history = recipesData.history || [];

    currentContainer.innerHTML = `
      <article class="widget-card">
        <div class="widget-header">
          <div class="widget-title-group">
            <span class="widget-icon">🥘</span>
            <div>
              <h2 class="widget-title">每兩小時自煮正餐推薦（5 道家常下飯菜）</h2>
              <p class="widget-subtitle">
                排程：06:00 起每 2 小時自動更新 • 連續兩輪不重複 • 00:00 自動清空前日紀錄
              </p>
            </div>
          </div>

          <div class="widget-controls">
            <button class="btn btn-primary btn-sm" id="btn-generate-recipes" title="立即觸發新一輪 5 道不重複料理推薦">
              ✨ 立即換新一輪 (5道)
            </button>
          </div>
        </div>

        <div class="widget-body">
          <!-- 分頁切換：最新推薦 vs 今日歷史紀錄時間軸 -->
          <div class="weather-tabs-header">
            <div class="tab-group">
              <button class="tab-btn ${activeTab === "latest" ? "active" : ""}" data-recipe-tab="latest">
                🔥 最新推薦時段 (${latest ? latest.slot_time : recipesData.current_slot})
              </button>
              <button class="tab-btn ${activeTab === "history" ? "active" : ""}" data-recipe-tab="history">
                🕰️ 今日歷史紀錄時間軸 (${history.length} 個時段 / 共 ${history.length * 5} 道)
              </button>
            </div>
            <span class="badge badge-accent">點擊任一料理卡片檢視 2 人份詳細食譜</span>
          </div>

          ${activeTab === "latest" ? this.renderLatestHtml(latest) : this.renderHistoryHtml(history)}
        </div>

        <div class="widget-footer">
          <span>資料來源：${latest ? latest.source : "家常食譜引擎"}</span>
          <span>今日累積批次：${history.length} 輪（隔日 00:00 自動清理）</span>
        </div>
      </article>
    `;

    this.bindEvents();
  },

  renderLatestHtml(latestBatch) {
    if (!latestBatch || !latestBatch.recipes) {
      return `<p style="padding: 20px; color: var(--text-muted);">尚無推薦料理，請點擊右上角生成。</p>`;
    }

    const cardsHtml = latestBatch.recipes
      .map(
        (recipe, idx) => `
        <div class="recipe-item-card" data-recipe-json='${encodeURIComponent(JSON.stringify(recipe))}' role="button" tabindex="0">
          <div class="recipe-item-left">
            <div class="recipe-index-circle">${idx + 1}</div>
            <div>
              <div class="recipe-item-title">
                <span>${recipe.title}</span>
                <span class="badge badge-info">${recipe.category || "家常菜"}</span>
              </div>
              <div class="recipe-item-sub">${recipe.subtitle || ""}</div>
              <div class="recipe-tags-row">
                <span class="recipe-tag">⏱️ ${recipe.prep_time_min} 分鐘</span>
                <span class="recipe-tag">👥 ${recipe.servings}</span>
                ${(recipe.tags || []).map((t) => `<span class="recipe-tag">#${t}</span>`).join("")}
              </div>
            </div>
          </div>

          <div class="recipe-item-right">
            <span class="btn btn-outline btn-sm">📖 詳細食譜 →</span>
          </div>
        </div>
      `
      )
      .join("");

    return `<div class="recipes-Grid">${cardsHtml}</div>`;
  },

  renderHistoryHtml(historyBatches = []) {
    if (!historyBatches.length) {
      return `<p style="padding: 20px; color: var(--text-muted);">今日尚無歷史紀錄。</p>`;
    }

    const timelineHtml = historyBatches
      .map((batch, bIdx) => {
        const createdTime = new Date(batch.created_at).toLocaleTimeString("zh-TW", {
          hour: "2-digit",
          minute: "2-digit",
        });
        const chipsHtml = (batch.recipes || [])
          .map(
            (r, rIdx) => `
            <div class="timeline-recipe-chip" data-recipe-json='${encodeURIComponent(JSON.stringify(r))}' role="button" tabindex="0">
              <div style="font-weight: 700; font-size: 0.88rem; color: var(--text-main);">
                ${rIdx + 1}. ${r.title}
              </div>
              <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                <span>⏱️ ${r.prep_time_min}分 • ${r.servings}</span>
                <span style="color: var(--accent); font-weight: 600;">查看食譜 →</span>
              </div>
            </div>
          `
          )
          .join("");

        return `
          <div class="timeline-batch">
            <div class="timeline-batch-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="timeline-slot-badge">🕒 時段：${batch.slot_time}</span>
                ${bIdx === 0 ? `<span class="badge badge-success">最新一輪</span>` : `<span class="badge badge-info">當日歷史紀錄</span>`}
              </div>
              <span style="font-size: 0.76rem; color: var(--text-muted);">記錄於 ${batch.date} ${createdTime}</span>
            </div>
            <div class="timeline-recipes-chips">
              ${chipsHtml}
            </div>
          </div>
        `;
      })
      .join("");

    return `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
        <span style="font-size: 0.82rem; color: var(--text-secondary);">
          💡 晚上想煮中午或早上看過的菜色？點擊下方任一時段的料理即可隨時開啟完整食譜：
        </span>
        ${
          historyBatches.length > 1
            ? `<button class="btn btn-outline btn-sm" id="btn-clear-old-history">🧹 僅保留最新一輪</button>`
            : ""
        }
      </div>
      <div class="history-timeline">${timelineHtml}</div>
    `;
  },

  bindEvents() {
    // 切換最新推薦 / 今日歷史紀錄分頁
    currentContainer.querySelectorAll("[data-recipe-tab]").forEach((btn) => {
      btn.addEventListener("click", () => {
        activeTab = btn.getAttribute("data-recipe-tab");
        this.render();
      });
    });

    // 立即生成新一輪 5 道
    const genBtn = currentContainer.querySelector("#btn-generate-recipes");
    if (genBtn) {
      genBtn.addEventListener("click", async () => {
        genBtn.disabled = true;
        genBtn.textContent = "⏳ 正在生成 5 道家常菜...";
        await this.triggerNewBatch();
      });
    }

    // 清理舊批次按鈕
    const clearBtn = currentContainer.querySelector("#btn-clear-old-history");
    if (clearBtn) {
      clearBtn.addEventListener("click", async () => {
        const res = await fetch("/api/modules/recipes/cleanup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ keep_latest: true }),
        });
        const json = await res.json();
        recipesData = json.data;
        this.render();
        showToast("🧹 已清理今日早期批次，保留最新一輪推薦！");
      });
    }

    // 點擊任一料理卡片開啟詳細食譜 Modal
    currentContainer.querySelectorAll("[data-recipe-json]").forEach((card) => {
      card.addEventListener("click", () => {
        const raw = card.getAttribute("data-recipe-json");
        if (!raw) return;
        const recipe = JSON.parse(decodeURIComponent(raw));
        this.openRecipeModal(recipe);
      });
    });
  },

  initModalHandlers() {
    const modal = document.getElementById("recipe-modal");
    const closeBtn = document.getElementById("btn-close-recipe-modal");
    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.add("hidden");
      });
    }
  },

  openRecipeModal(recipe) {
    const modal = document.getElementById("recipe-modal");
    if (!modal) return;

    document.getElementById("recipe-modal-category").textContent = recipe.category || "家常自煮正餐";
    document.getElementById("recipe-modal-title").textContent = recipe.title;
    document.getElementById("recipe-modal-subtitle").textContent = recipe.subtitle || "";

    const ingredientsHtml = (recipe.ingredients || [])
      .map((i) => `<div class="ing-row"><span>${i.name}</span><span class="ing-amount">${i.amount}</span></div>`)
      .join("");

    const seasoningsHtml = (recipe.seasonings || [])
      .map((s) => `<div class="ing-row"><span>${s.name}</span><span class="ing-amount">${s.amount}</span></div>`)
      .join("");

    const stepsHtml = (recipe.steps || [])
      .map(
        (step, idx) => `
        <div class="step-item">
          <div class="step-num">${idx + 1}</div>
          <div>${step}</div>
        </div>
      `
      )
      .join("");

    document.getElementById("recipe-modal-body").innerHTML = `
      <div class="recipe-detail-summary">
        <div>
          <span>預估烹飪時間</span>
          <strong>⏱️ ${recipe.prep_time_min} 分鐘</strong>
        </div>
        <div>
          <span>預設份量</span>
          <strong>👥 ${recipe.servings || "2 人份"}</strong>
        </div>
        <div>
          <span>難易度</span>
          <strong>⭐ ${recipe.difficulty || "簡單"}</strong>
        </div>
        <div>
          <span>每份預估熱量</span>
          <strong>🔥 ${recipe.calories_per_serving || "350 kcal"}</strong>
        </div>
      </div>

      <div class="recipe-two-cols">
        <div class="recipe-list-box">
          <h4>🥬 精確食材清單（含克數）</h4>
          ${ingredientsHtml}
        </div>
        <div class="recipe-list-box">
          <h4>🧂 調味料清單（含匙數/毫升）</h4>
          ${seasoningsHtml}
        </div>
      </div>

      <div class="steps-box">
        <h4>👩‍🍳 條列式烹飪步驟</h4>
        ${stepsHtml}
      </div>

      <div class="fire-tips-box">
        <strong>🔥 主廚火候小撇步：</strong><br/>
        ${recipe.fire_tips || "維持中大火快炒，起鍋前淋入少許香油即可完美上桌！"}
      </div>
    `;

    modal.classList.remove("hidden");
  },
};
