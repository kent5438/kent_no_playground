/**
 * 模組 3：每兩小時自煮正餐推薦與歷史紀錄 UI 卡片元件
 * - 每日 06:00 起每隔 2 小時 (06:00, 08:00, 10:00, 12:00, 14:00, 16:00, 18:00, 20:00...)
 *   自動生成新一輪「5 種家常自煮正餐料理」（下飯、家常、食材易得，避免連續兩輪重複）
 * - 點擊任一道料理展開彈出視窗檢視詳細食譜（2人份、精確克數/匙數、步驟與火候小撇步）
 * - 支援「❤️ 我的最愛」永久收藏（完整食譜內容永久保存，不隨每日 00:00 歷史紀錄清空）
 * - 支援「🥕 輸入食材產出食譜」（輸入冰箱現有食材即可產出專屬家常食譜）
 * - 提供「最新推薦」、「食材產食譜」、「我的最愛」與「今日歷史紀錄」四分頁切換
 */
import { showToast, widgetRegistry } from "../core/widgetRegistry.js";

let currentContainer = null;
let recipesData = null;
let activeTab = "latest"; // 'latest' | 'ingredients' | 'favorites' | 'history'
let selectedCustomBatchId = null;
let ingredientDraft = "";
let servingsDraft = "2 人份";
let preferenceDraft = "";
let favoriteSearchQuery = "";
let currentModalRecipe = null;
let currentModalSourceLabel = "";
let modalHandlersBound = false;

const QUICK_INGREDIENTS = [
  "雞腿肉",
  "豬五花",
  "牛肉片",
  "雞蛋",
  "豆腐",
  "蝦仁",
  "高麗菜",
  "番茄",
  "杏鮑菇",
  "馬鈴薯",
  "洋蔥",
  "蒜頭",
];

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function formatDateTimeShort(isoStr) {
  if (!isoStr) return "";
  try {
    const d = new Date(isoStr);
    return d.toLocaleString("zh-TW", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  } catch {
    return isoStr;
  }
}

export const RecipesWidget = {
  id: "recipes",
  name: "每兩小時自煮正餐推薦與歷史紀錄",
  description: "每 2 小時自動生成 5 道家常下飯正餐，支援輸入食材產出食譜、我的最愛永久收藏與今日歷史時間軸",
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

  isFavorited(recipe) {
    const key = String(recipe?.title || "").trim();
    if (!key) return false;
    return (recipesData?.favorite_keys || []).includes(key);
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

  async toggleFavorite(recipe, sourceLabel = "") {
    if (!recipe || !recipe.title) return;
    const res = await fetch("/api/modules/recipes/favorites/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipe,
        source_label: sourceLabel || "自煮正餐推薦",
      }),
    });
    const json = await res.json();
    if (!json.ok) {
      showToast(`⚠️ 收藏操作失敗：${json.error || "請稍後再試"}`);
      return;
    }
    recipesData = json.data;
    this.render();
    this.syncModalFavoriteButton();

    if (json.favorited) {
      showToast(`❤️ 已將「${recipe.title}」完整食譜永久加入我的最愛！`);
    } else {
      showToast(`💔 已從我的最愛移除「${recipe.title}」`);
    }
  },

  async generateByIngredients(ingredientsText, servings, preference) {
    const trimmed = String(ingredientsText || "").trim();
    if (!trimmed) {
      showToast("⚠️ 請先輸入至少一項食材（例如：雞腿肉、高麗菜、蒜頭）");
      return false;
    }
    const res = await fetch("/api/modules/recipes/generate-by-ingredients", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ingredients: trimmed,
        servings: servings || "2 人份",
        preference: preference || "",
        count: 3,
      }),
    });
    const json = await res.json();
    if (!json.ok) {
      showToast(`⚠️ ${json.error || "產出食譜失敗，請稍後再試"}`);
      return false;
    }
    recipesData = json.data;
    selectedCustomBatchId = json.batch?.batch_id || null;
    activeTab = "ingredients";
    this.render();
    showToast(`🥕 已依據「${json.batch.ingredients_input}」產出 ${json.batch.recipes.length} 道專屬食譜！`);
    return true;
  },

  async deleteCustomBatch(batchId) {
    const res = await fetch("/api/modules/recipes/custom/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ batch_id: batchId }),
    });
    const json = await res.json();
    if (json.ok) {
      recipesData = json.data;
      if (selectedCustomBatchId === batchId) {
        selectedCustomBatchId = recipesData.latest_custom?.batch_id || null;
      }
      this.render();
      showToast("🗑️ 已移除該筆食材產出紀錄");
    }
  },

  render() {
    if (!currentContainer || !recipesData) return;
    const latest = recipesData.latest;
    const history = recipesData.history || [];
    const favorites = recipesData.favorites || [];
    const customBatches = recipesData.custom_batches || [];

    let tabContentHtml = "";
    if (activeTab === "latest") {
      tabContentHtml = this.renderLatestHtml(latest);
    } else if (activeTab === "ingredients") {
      tabContentHtml = this.renderIngredientsGeneratorHtml(customBatches);
    } else if (activeTab === "favorites") {
      tabContentHtml = this.renderFavoritesHtml(favorites);
    } else {
      tabContentHtml = this.renderHistoryHtml(history);
    }

    currentContainer.innerHTML = `
      <article class="widget-card">
        <div class="widget-header">
          <div class="widget-title-group">
            <span class="widget-icon">🥘</span>
            <div>
              <h2 class="widget-title">每兩小時自煮正餐推薦（5 道家常下飯菜）</h2>
              <p class="widget-subtitle">
                排程：06:00 起每 2 小時更新 • 支援輸入食材產出食譜 • 我的最愛永久保留
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
          <!-- 分頁切換：最新推薦 / 食材產食譜 / 我的最愛 / 今日歷史紀錄 -->
          <div class="weather-tabs-header recipes-tabs-header">
            <div class="tab-group recipes-tab-group">
              <button class="tab-btn ${activeTab === "latest" ? "active" : ""}" data-recipe-tab="latest">
                🔥 最新推薦 (${escapeHtml(latest ? latest.slot_time : recipesData.current_slot)})
              </button>
              <button class="tab-btn ${activeTab === "ingredients" ? "active" : ""}" data-recipe-tab="ingredients">
                🥕 食材產食譜
              </button>
              <button class="tab-btn ${activeTab === "favorites" ? "active" : ""}" data-recipe-tab="favorites">
                ❤️ 我的最愛 (${favorites.length})
              </button>
              <button class="tab-btn ${activeTab === "history" ? "active" : ""}" data-recipe-tab="history">
                🕰️ 今日歷史 (${history.length}輪)
              </button>
            </div>
          </div>

          ${tabContentHtml}
        </div>

        <div class="widget-footer">
          <span>資料來源：${escapeHtml(latest ? latest.source : "家常食譜引擎")}</span>
          <span>今日累積：${history.length} 輪（00:00清空）• ❤️ 永久收藏：${favorites.length} 道</span>
        </div>
      </article>
    `;

    this.bindEvents();
  },

  renderRecipeCardHtml(recipe, idx, options = {}) {
    const {
      sourceLabel = "自煮正餐推薦",
      isFavoriteView = false,
      savedAt = "",
      favId = null,
      showMatchedIngredients = false,
    } = options;

    const favorited = this.isFavorited(recipe);
    const encodedRecipe = encodeURIComponent(JSON.stringify(recipe));
    const encodedSource = encodeURIComponent(sourceLabel);

    const matchedBadgeHtml =
      showMatchedIngredients && recipe.matched_ingredients && recipe.matched_ingredients.length
        ? `<span class="recipe-tag recipe-tag-matched">✅ 運用：${escapeHtml(recipe.matched_ingredients.join("、"))}</span>`
        : "";

    const favMetaHtml = isFavoriteView
      ? `<div class="recipe-fav-meta">💾 永久收藏於 ${escapeHtml(formatDateTimeShort(savedAt))}${sourceLabel ? ` • 來源：${escapeHtml(sourceLabel)}` : ""}</div>`
      : "";

    const favButtonHtml = isFavoriteView
      ? `
        <button
          type="button"
          class="btn btn-outline btn-sm btn-fav-toggle is-favorited"
          data-toggle-fav-recipe="${encodedRecipe}"
          data-fav-source="${encodedSource}"
          ${favId ? `data-fav-id="${favId}"` : ""}
          title="從我的最愛移除此食譜"
        >
          💔 取消收藏
        </button>
      `
      : `
        <button
          type="button"
          class="btn btn-outline btn-sm btn-fav-toggle ${favorited ? "is-favorited" : ""}"
          data-toggle-fav-recipe="${encodedRecipe}"
          data-fav-source="${encodedSource}"
          title="${favorited ? "已永久收藏至我的最愛（點擊可取消）" : "將完整食譜永久加入我的最愛"}"
        >
          ${favorited ? "❤️ 已收藏" : "🤍 收藏"}
        </button>
      `;

    return `
      <div
        class="recipe-item-card ${favorited ? "is-favorited-card" : ""}"
        data-recipe-json="${encodedRecipe}"
        data-recipe-source="${encodedSource}"
        role="button"
        tabindex="0"
      >
        <div class="recipe-item-left">
          <div class="recipe-index-circle ${isFavoriteView ? "is-fav-circle" : ""}">
            ${isFavoriteView ? "❤️" : idx + 1}
          </div>
          <div>
            <div class="recipe-item-title">
              <span>${escapeHtml(recipe.title)}</span>
              <span class="badge badge-info">${escapeHtml(recipe.category || "家常菜")}</span>
            </div>
            <div class="recipe-item-sub">${escapeHtml(recipe.subtitle || "")}</div>
            ${favMetaHtml}
            <div class="recipe-tags-row">
              ${matchedBadgeHtml}
              <span class="recipe-tag">⏱️ ${escapeHtml(recipe.prep_time_min)} 分鐘</span>
              <span class="recipe-tag">👥 ${escapeHtml(recipe.servings || "2 人份")}</span>
              ${(recipe.tags || []).map((t) => `<span class="recipe-tag">#${escapeHtml(t)}</span>`).join("")}
            </div>
          </div>
        </div>

        <div class="recipe-item-right recipe-card-actions">
          ${favButtonHtml}
          <button
            type="button"
            class="btn btn-outline btn-sm btn-quick-import-recipe"
            data-quick-import-recipe="${encodedRecipe}"
            title="一鍵將此料理所需食材匯入下方智慧採買清單"
          >
            🛒 匯入食材
          </button>
          <span class="btn btn-outline btn-sm">📖 詳細食譜 →</span>
        </div>
      </div>
    `;
  },

  renderLatestHtml(latestBatch) {
    if (!latestBatch || !latestBatch.recipes) {
      return `<p style="padding: 20px; color: var(--text-muted);">尚無推薦料理，請點擊右上角生成。</p>`;
    }

    const sourceLabel = `每2小時推薦 (${latestBatch.slot_time})`;
    const cardsHtml = latestBatch.recipes
      .map((recipe, idx) => this.renderRecipeCardHtml(recipe, idx, { sourceLabel }))
      .join("");

    return `
      <div class="recipe-subhint-bar">
        <span class="badge badge-accent">點擊任一料理卡片檢視 2 人份詳細食譜</span>
        <span style="font-size: 0.78rem; color: var(--text-muted);">💡 點擊 🤍 收藏 即可將完整食譜永久保留於「❤️ 我的最愛」</span>
      </div>
      <div class="recipes-Grid">${cardsHtml}</div>
    `;
  },

  renderIngredientsGeneratorHtml(customBatches = []) {
    const activeBatch =
      customBatches.find((b) => b.batch_id === selectedCustomBatchId) || customBatches[0] || null;

    const quickChipsHtml = QUICK_INGREDIENTS.map(
      (ing) => `
        <button type="button" class="quick-ing-chip" data-quick-ing="${escapeHtml(ing)}">
          + ${escapeHtml(ing)}
        </button>
      `
    ).join("");

    const prefOptions = [
      { value: "", label: "不限（家常下飯）" },
      { value: "15分鐘快手", label: "⚡ 15分鐘快手" },
      { value: "清淡健康", label: "🥗 清淡健康" },
      { value: "重口味白飯殺手", label: "🌶️ 重口味白飯殺手" },
      { value: "暖胃湯煲 / 一鍋到底", label: "🍲 暖胃湯煲 / 一鍋到底" },
    ];

    const servingOptions = ["1 人份", "2 人份", "3-4 人份"];

    let resultsHtml = "";
    if (activeBatch && activeBatch.recipes && activeBatch.recipes.length) {
      const sourceLabel = `食材產出 (${activeBatch.ingredients_input})`;
      const ingPills = (activeBatch.ingredients || [])
        .map((i) => `<span class="badge badge-success">🥬 ${escapeHtml(i)}</span>`)
        .join("");

      const cardsHtml = activeBatch.recipes
        .map((recipe, idx) =>
          this.renderRecipeCardHtml(recipe, idx, {
            sourceLabel,
            showMatchedIngredients: true,
          })
        )
        .join("");

      const historyChipsHtml =
        customBatches.length > 1
          ? `
            <div class="custom-history-bar">
              <span class="custom-history-label">🕒 近期食材產出紀錄：</span>
              <div class="custom-history-chips">
                ${customBatches
                  .map(
                    (b) => `
                  <div class="custom-history-chip-wrap ${b.batch_id === activeBatch.batch_id ? "active" : ""}">
                    <button type="button" class="custom-history-chip-btn" data-select-custom-batch="${b.batch_id}">
                      ${escapeHtml(b.ingredients_input)}
                    </button>
                    <button type="button" class="custom-history-chip-del" data-delete-custom-batch="${b.batch_id}" title="移除此紀錄">✕</button>
                  </div>
                `
                  )
                  .join("")}
              </div>
            </div>
          `
          : "";

      resultsHtml = `
        ${historyChipsHtml}
        <div class="custom-result-header">
          <div class="custom-result-ings">
            <strong style="font-size: 0.85rem;">✨ 專屬產出結果：</strong>
            ${ingPills}
            <span class="badge badge-info">👥 ${escapeHtml(activeBatch.servings)}</span>
            ${activeBatch.preference ? `<span class="badge badge-warning">${escapeHtml(activeBatch.preference)}</span>` : ""}
          </div>
          <span style="font-size: 0.75rem; color: var(--text-muted);">
            ${escapeHtml(activeBatch.source)} • ${escapeHtml(formatDateTimeShort(activeBatch.created_at))}
          </span>
        </div>
        <div class="recipes-Grid">${cardsHtml}</div>
      `;
    } else {
      resultsHtml = `
        <div class="recipe-empty-state">
          <div style="font-size: 2rem; margin-bottom: 6px;">🥕🍳</div>
          <strong>輸入冰箱現有食材，立即產出 3 道專屬家常食譜！</strong>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            支援自由輸入多項食材（用逗號、頓號或空白分隔），也可直接點擊上方常用食材快選標籤；產出的食譜皆可點 🤍 永久收藏至我的最愛。
          </p>
        </div>
      `;
    }

    return `
      <form id="ingredients-recipe-form" class="recipe-ingredients-panel">
        <div class="form-group" style="margin-bottom: 10px;">
          <label for="input-custom-ingredients">
            🥬 輸入您手邊現有的食材（可用頓號、逗號或空白分隔）
          </label>
          <div class="ingredients-input-row">
            <input
              type="text"
              id="input-custom-ingredients"
              class="form-control"
              placeholder="例如：雞腿肉、高麗菜、蒜頭、雞蛋"
              value="${escapeHtml(ingredientDraft)}"
              autocomplete="off"
              required
            />
            <button type="button" class="btn btn-outline btn-sm" id="btn-clear-ing-input" title="清空輸入框">
              清空
            </button>
          </div>
        </div>

        <div class="quick-ing-row">
          <span class="quick-ing-label">快選食材：</span>
          ${quickChipsHtml}
        </div>

        <div class="ingredients-options-row">
          <div class="form-group">
            <label for="select-custom-servings">👥 份量</label>
            <select id="select-custom-servings" class="form-control">
              ${servingOptions
                .map(
                  (opt) =>
                    `<option value="${escapeHtml(opt)}" ${opt === servingsDraft ? "selected" : ""}>${escapeHtml(opt)}</option>`
                )
                .join("")}
            </select>
          </div>

          <div class="form-group">
            <label for="select-custom-preference">🎯 料理風格偏好</label>
            <select id="select-custom-preference" class="form-control">
              ${prefOptions
                .map(
                  (opt) =>
                    `<option value="${escapeHtml(opt.value)}" ${opt.value === preferenceDraft ? "selected" : ""}>${escapeHtml(opt.label)}</option>`
                )
                .join("")}
            </select>
          </div>

          <div class="ingredients-submit-wrap">
            <button type="submit" class="btn btn-primary" id="btn-submit-ingredients-recipe">
              🍳 產出專屬食譜 (3道)
            </button>
          </div>
        </div>
      </form>

      ${resultsHtml}
    `;
  },

  renderFavoritesListHtml(favorites = [], query = "") {
    const q = String(query || "").trim().toLowerCase();
    const filtered = q
      ? favorites.filter((f) => {
          const r = f.recipe || {};
          const hay = [
            f.title,
            f.category,
            f.source_label,
            r.subtitle,
            ...(r.tags || []),
            ...(r.ingredients || []).map((i) => i.name),
          ]
            .join(" ")
            .toLowerCase();
          return hay.includes(q);
        })
      : favorites;

    if (!favorites.length) {
      return `
        <div class="recipe-empty-state">
          <div style="font-size: 2rem; margin-bottom: 6px;">❤️📖</div>
          <strong>目前還沒有收藏的食譜</strong>
          <p style="font-size: 0.82rem; color: var(--text-muted); margin-top: 4px;">
            在「最新推薦」、「今日歷史」、「食材產食譜」或食譜詳細視窗中點擊 <strong>🤍 收藏</strong>，即可將完整食譜永久保存於這裡！
          </p>
        </div>
      `;
    }

    if (!filtered.length) {
      return `
        <div class="recipe-empty-state">
          <strong>找不到符合「${escapeHtml(query)}」的收藏食譜</strong>
          <p style="font-size: 0.8rem; color: var(--text-muted); margin-top: 4px;">請試著更換菜名或食材關鍵字。</p>
        </div>
      `;
    }

    return `
      <div class="recipes-Grid">
        ${filtered
          .map((fav, idx) =>
            this.renderRecipeCardHtml(fav.recipe, idx, {
              sourceLabel: fav.source_label,
              isFavoriteView: true,
              savedAt: fav.saved_at,
              favId: fav.fav_id,
            })
          )
          .join("")}
      </div>
    `;
  },

  renderFavoritesHtml(favorites = []) {
    return `
      <div class="recipe-fav-banner">
        <div>
          <strong>💎 永久保留區（我的最愛）</strong>
          <div style="font-size: 0.78rem; color: var(--text-secondary); margin-top: 2px;">
            已收藏的食譜皆完整保留所有食材克數、調味料、烹飪步驟與火候小撇步，不受每日 00:00 清空前日紀錄影響。
          </div>
        </div>
        ${
          favorites.length > 0
            ? `
            <div class="fav-search-wrap">
              <input
                type="search"
                id="input-fav-search"
                class="form-control"
                placeholder="🔍 搜尋收藏菜名或食材..."
                value="${escapeHtml(favoriteSearchQuery)}"
              />
            </div>
          `
            : ""
        }
      </div>
      <div id="favorites-list-container">
        ${this.renderFavoritesListHtml(favorites, favoriteSearchQuery)}
      </div>
    `;
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
        const sourceLabel = `今日歷史 (${batch.slot_time})`;
        const chipsHtml = (batch.recipes || [])
          .map((r, rIdx) => {
            const favorited = this.isFavorited(r);
            const encodedRecipe = encodeURIComponent(JSON.stringify(r));
            const encodedSource = encodeURIComponent(sourceLabel);
            return `
              <div
                class="timeline-recipe-chip ${favorited ? "is-favorited-chip" : ""}"
                data-recipe-json="${encodedRecipe}"
                data-recipe-source="${encodedSource}"
                role="button"
                tabindex="0"
              >
                <div class="timeline-chip-top">
                  <div style="font-weight: 700; font-size: 0.88rem; color: var(--text-main);">
                    ${rIdx + 1}. ${escapeHtml(r.title)}
                  </div>
                  <button
                    type="button"
                    class="btn-chip-fav ${favorited ? "is-favorited" : ""}"
                    data-toggle-fav-recipe="${encodedRecipe}"
                    data-fav-source="${encodedSource}"
                    title="${favorited ? "已永久收藏（點擊取消）" : "加入我的最愛（永久保留）"}"
                    aria-label="切換收藏"
                  >
                    ${favorited ? "❤️" : "🤍"}
                  </button>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; justify-content: space-between;">
                  <span>⏱️ ${escapeHtml(r.prep_time_min)}分 • ${escapeHtml(r.servings || "2 人份")}</span>
                  <span style="color: var(--accent); font-weight: 600;">查看食譜 →</span>
                </div>
              </div>
            `;
          })
          .join("");

        return `
          <div class="timeline-batch">
            <div class="timeline-batch-header">
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="timeline-slot-badge">🕒 時段：${escapeHtml(batch.slot_time)}</span>
                ${bIdx === 0 ? `<span class="badge badge-success">最新一輪</span>` : `<span class="badge badge-info">當日歷史紀錄</span>`}
              </div>
              <span style="font-size: 0.76rem; color: var(--text-muted);">記錄於 ${escapeHtml(batch.date)} ${escapeHtml(createdTime)}</span>
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
          💡 晚上想煮早上看過的菜色？點 🤍 可永久收藏至「❤️ 我的最愛」，不怕隔日 00:00 清空：
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

  bindRecipeListEvents(scopeEl) {
    if (!scopeEl) return;

    // 切換「我的最愛」永久收藏按鈕
    scopeEl.querySelectorAll("[data-toggle-fav-recipe]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const raw = btn.getAttribute("data-toggle-fav-recipe");
        const src = btn.getAttribute("data-fav-source");
        if (!raw) return;
        const recipe = JSON.parse(decodeURIComponent(raw));
        const sourceLabel = src ? decodeURIComponent(src) : "自煮正餐推薦";
        await this.toggleFavorite(recipe, sourceLabel);
      });
    });

    // 點擊卡片上的「🛒 匯入食材」按鈕一鍵匯入採買清單
    scopeEl.querySelectorAll("[data-quick-import-recipe]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const raw = btn.getAttribute("data-quick-import-recipe");
        if (!raw) return;
        const recipe = JSON.parse(decodeURIComponent(raw));
        await this.importRecipeToShoppingList(recipe, false);
      });
    });

    // 點擊任一料理卡片開啟詳細食譜 Modal
    scopeEl.querySelectorAll("[data-recipe-json]").forEach((card) => {
      card.addEventListener("click", () => {
        const raw = card.getAttribute("data-recipe-json");
        const src = card.getAttribute("data-recipe-source");
        if (!raw) return;
        const recipe = JSON.parse(decodeURIComponent(raw));
        const sourceLabel = src ? decodeURIComponent(src) : "自煮正餐推薦";
        this.openRecipeModal(recipe, sourceLabel);
      });
    });
  },

  bindEvents() {
    // 切換分頁
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

    // 清理舊批次按鈕（僅影響今日排程歷史，不影響我的最愛）
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
        showToast("🧹 已清理今日早期批次（我的最愛已永久保留）！");
      });
    }

    // 食材產食譜表單事件
    const ingForm = currentContainer.querySelector("#ingredients-recipe-form");
    const ingInput = currentContainer.querySelector("#input-custom-ingredients");
    const servSelect = currentContainer.querySelector("#select-custom-servings");
    const prefSelect = currentContainer.querySelector("#select-custom-preference");
    const clearIngBtn = currentContainer.querySelector("#btn-clear-ing-input");

    if (ingInput) {
      ingInput.addEventListener("input", () => {
        ingredientDraft = ingInput.value;
      });
    }
    if (servSelect) {
      servSelect.addEventListener("change", () => {
        servingsDraft = servSelect.value;
      });
    }
    if (prefSelect) {
      prefSelect.addEventListener("change", () => {
        preferenceDraft = prefSelect.value;
      });
    }
    if (clearIngBtn && ingInput) {
      clearIngBtn.addEventListener("click", () => {
        ingInput.value = "";
        ingredientDraft = "";
        ingInput.focus();
      });
    }

    // 快選食材標籤
    currentContainer.querySelectorAll("[data-quick-ing]").forEach((chip) => {
      chip.addEventListener("click", () => {
        if (!ingInput) return;
        const ing = chip.getAttribute("data-quick-ing");
        const currentParts = ingInput.value
          .split(/[,，、;；\s+/]+/)
          .map((s) => s.trim())
          .filter(Boolean);
        if (!currentParts.includes(ing)) {
          currentParts.push(ing);
          ingInput.value = currentParts.join("、");
          ingredientDraft = ingInput.value;
        }
        ingInput.focus();
      });
    });

    if (ingForm) {
      ingForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        const submitBtn = currentContainer.querySelector("#btn-submit-ingredients-recipe");
        const val = ingInput ? ingInput.value : ingredientDraft;
        const servings = servSelect ? servSelect.value : servingsDraft;
        const pref = prefSelect ? prefSelect.value : preferenceDraft;
        ingredientDraft = val;
        servingsDraft = servings;
        preferenceDraft = pref;

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = "⏳ 正在研發專屬食譜...";
        }
        const ok = await this.generateByIngredients(val, servings, pref);
        if (!ok && submitBtn) {
          submitBtn.disabled = false;
          submitBtn.textContent = "🍳 產出專屬食譜 (3道)";
        }
      });
    }

    // 切換 / 刪除近期食材產出紀錄
    currentContainer.querySelectorAll("[data-select-custom-batch]").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedCustomBatchId = parseInt(btn.getAttribute("data-select-custom-batch"), 10);
        this.render();
      });
    });
    currentContainer.querySelectorAll("[data-delete-custom-batch]").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = parseInt(btn.getAttribute("data-delete-custom-batch"), 10);
        await this.deleteCustomBatch(id);
      });
    });

    // 我的最愛即時搜尋過濾（保留輸入焦點）
    const favSearchInput = currentContainer.querySelector("#input-fav-search");
    if (favSearchInput) {
      favSearchInput.addEventListener("input", () => {
        favoriteSearchQuery = favSearchInput.value;
        const listContainer = currentContainer.querySelector("#favorites-list-container");
        if (listContainer) {
          listContainer.innerHTML = this.renderFavoritesListHtml(
            recipesData.favorites || [],
            favoriteSearchQuery
          );
          this.bindRecipeListEvents(listContainer);
        }
      });
    }

    // 綁定所有食譜卡片的收藏 / 匯入 / 開啟詳情事件
    this.bindRecipeListEvents(currentContainer);
  },

  async importRecipeToShoppingList(recipe, includeSeasonings = false, customLocation = null) {
    const loc = customLocation || localStorage.getItem("pref_shopping_location") || "全聯";
    const res = await fetch("/api/modules/shopping/import-recipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipe_title: recipe.title,
        ingredients: recipe.ingredients || [],
        include_seasonings: includeSeasonings,
        seasonings: recipe.seasonings || [],
        location: loc,
        urgency: "urgent",
      }),
    });
    const json = await res.json();
    if (json.ok) {
      await widgetRegistry.refreshWidget("shopping");
      showToast(`🛒 已將「${recipe.title}」共 ${json.imported.imported_count} 項食材匯入採買清單 (@ ${loc})！`);
    }
  },

  async importSingleIngredientToShoppingList(name, amount, recipeTitle, customLocation = null) {
    const loc = customLocation || localStorage.getItem("pref_shopping_location") || "全聯";
    const res = await fetch("/api/modules/shopping/import-recipe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        recipe_title: recipeTitle,
        ingredients: [{ name, amount }],
        include_seasonings: false,
        location: loc,
        urgency: "urgent",
      }),
    });
    const json = await res.json();
    if (json.ok) {
      await widgetRegistry.refreshWidget("shopping");
      showToast(`🛒 已將「${name}」加入採買清單 (@ ${loc})！`);
    }
  },

  syncModalFavoriteButton() {
    const favBtn = document.getElementById("btn-modal-toggle-fav");
    if (!favBtn || !currentModalRecipe) return;
    const favorited = this.isFavorited(currentModalRecipe);
    favBtn.classList.toggle("is-favorited", favorited);
    favBtn.textContent = favorited ? "❤️ 已永久收藏" : "🤍 收藏至我的最愛";
    favBtn.title = favorited
      ? "此食譜已永久收藏於我的最愛（點擊可取消收藏）"
      : "將完整食譜永久收藏至我的最愛";
  },

  initModalHandlers() {
    if (modalHandlersBound) return;
    modalHandlersBound = true;

    const modal = document.getElementById("recipe-modal");
    const closeBtn = document.getElementById("btn-close-recipe-modal");
    const modalFavBtn = document.getElementById("btn-modal-toggle-fav");

    if (closeBtn && modal) {
      closeBtn.addEventListener("click", () => modal.classList.add("hidden"));
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.classList.add("hidden");
      });
    }

    if (modalFavBtn) {
      modalFavBtn.addEventListener("click", async () => {
        if (!currentModalRecipe) return;
        await this.toggleFavorite(currentModalRecipe, currentModalSourceLabel);
      });
    }
  },

  openRecipeModal(recipe, sourceLabel = "自煮正餐推薦") {
    const modal = document.getElementById("recipe-modal");
    if (!modal) return;

    currentModalRecipe = recipe;
    currentModalSourceLabel = sourceLabel || "自煮正餐推薦";

    document.getElementById("recipe-modal-category").textContent = recipe.category || "家常自煮正餐";
    document.getElementById("recipe-modal-title").textContent = recipe.title;
    document.getElementById("recipe-modal-subtitle").textContent = recipe.subtitle || "";
    this.syncModalFavoriteButton();

    const defaultLoc = localStorage.getItem("pref_shopping_location") || "全聯";

    const ingredientsHtml = (recipe.ingredients || [])
      .map(
        (i) => `
        <div class="ing-row">
          <span>${escapeHtml(i.name)}</span>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="ing-amount">${escapeHtml(i.amount)}</span>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              style="padding: 2px 7px; font-size: 0.72rem;"
              data-single-ing-name="${encodeURIComponent(i.name)}"
              data-single-ing-amt="${encodeURIComponent(i.amount)}"
              title="單獨將此項食材加入採買清單"
            >
              +採買
            </button>
          </div>
        </div>
      `
      )
      .join("");

    const seasoningsHtml = (recipe.seasonings || [])
      .map(
        (s) => `
        <div class="ing-row">
          <span>${escapeHtml(s.name)}</span>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="ing-amount">${escapeHtml(s.amount)}</span>
            <button
              type="button"
              class="btn btn-outline btn-sm"
              style="padding: 2px 7px; font-size: 0.72rem;"
              data-single-ing-name="${encodeURIComponent(s.name)}"
              data-single-ing-amt="${encodeURIComponent(s.amount)}"
              title="單獨將此項調味料加入採買清單"
            >
              +採買
            </button>
          </div>
        </div>
      `
      )
      .join("");

    const stepsHtml = (recipe.steps || [])
      .map(
        (step, idx) => `
        <div class="step-item">
          <div class="step-num">${idx + 1}</div>
          <div>${escapeHtml(step)}</div>
        </div>
      `
      )
      .join("");

    const matchedBannerHtml =
      recipe.matched_ingredients && recipe.matched_ingredients.length
        ? `
          <div class="form-hint-box" style="margin-bottom: 14px;">
            🥬 <strong>運用到的指定食材：</strong>${escapeHtml(recipe.matched_ingredients.join("、"))}
          </div>
        `
        : "";

    const modalBody = document.getElementById("recipe-modal-body");
    modalBody.innerHTML = `
      ${matchedBannerHtml}
      <div class="recipe-detail-summary">
        <div>
          <span>預估烹飪時間</span>
          <strong>⏱️ ${escapeHtml(recipe.prep_time_min)} 分鐘</strong>
        </div>
        <div>
          <span>預設份量</span>
          <strong>👥 ${escapeHtml(recipe.servings || "2 人份")}</strong>
        </div>
        <div>
          <span>難易度</span>
          <strong>⭐ ${escapeHtml(recipe.difficulty || "簡單")}</strong>
        </div>
        <div>
          <span>每份預估熱量</span>
          <strong>🔥 ${escapeHtml(recipe.calories_per_serving || "350 kcal")}</strong>
        </div>
      </div>

      <!-- 一鍵匯入智慧採買清單快捷列 -->
      <div class="recipe-import-banner">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span>🛒 <strong>一鍵匯入採買清單：</strong></span>
          <label for="modal-recipe-import-loc" style="font-size: 0.8rem; color: var(--text-secondary);">採買地點</label>
          <input
            type="text"
            id="modal-recipe-import-loc"
            class="form-control"
            list="shopping-locations-datalist"
            value="${escapeHtml(defaultLoc)}"
            style="width: 125px; padding: 4px 8px; font-size: 0.82rem;"
          />
        </div>
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <button type="button" class="btn btn-primary btn-sm" id="btn-modal-import-ings">
            🥬 匯入全部食材 (${(recipe.ingredients || []).length} 項)
          </button>
          <button type="button" class="btn btn-outline btn-sm" id="btn-modal-import-all">
            🧂 匯入食材 + 調味料
          </button>
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
        ${escapeHtml(recipe.fire_tips || "維持中大火快炒，起鍋前淋入少許香油即可完美上桌！")}
      </div>
    `;

    // 綁定 Modal 內的一鍵匯入食材按鈕
    const locInputEl = modalBody.querySelector("#modal-recipe-import-loc");
    const importIngsBtn = modalBody.querySelector("#btn-modal-import-ings");
    const importAllBtn = modalBody.querySelector("#btn-modal-import-all");

    if (importIngsBtn) {
      importIngsBtn.addEventListener("click", async () => {
        const loc = (locInputEl?.value || "全聯").trim() || "全聯";
        await this.importRecipeToShoppingList(recipe, false, loc);
      });
    }
    if (importAllBtn) {
      importAllBtn.addEventListener("click", async () => {
        const loc = (locInputEl?.value || "全聯").trim() || "全聯";
        await this.importRecipeToShoppingList(recipe, true, loc);
      });
    }

    modalBody.querySelectorAll("[data-single-ing-name]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const loc = (locInputEl?.value || "全聯").trim() || "全聯";
        const ingName = decodeURIComponent(btn.getAttribute("data-single-ing-name"));
        const ingAmt = decodeURIComponent(btn.getAttribute("data-single-ing-amt"));
        await this.importSingleIngredientToShoppingList(ingName, ingAmt, recipe.title, loc);
      });
    });

    modal.classList.remove("hidden");
  },
};
