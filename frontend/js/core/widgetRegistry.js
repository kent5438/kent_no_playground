/**
 * 前端 Widget / Plugin 註冊與生命週期管理器
 * 讓「氣象」、「外食推薦」、「自煮食譜」與未來新增的生活模組（如高鐵時刻表、待辦清單、採買清單）
 * 都能以獨立卡片元件註冊並掛載至對應的插槽。
 */
export class WidgetRegistry {
  constructor() {
    this.widgets = new Map();
  }

  /**
   * 註冊一個獨立的 UI Widget 模組
   * @param {Object} widgetConfig
   * @param {string} widgetConfig.id - 模組唯一識別碼
   * @param {string} widgetConfig.name - 模組名稱
   * @param {string} widgetConfig.slotSelector - 掛載的 DOM 容器選擇器
   * @param {Function} widgetConfig.mount - (containerEl, context) => Promise<void>
   * @param {Function} [widgetConfig.refresh] - () => Promise<void>
   */
  register(widgetConfig) {
    if (!widgetConfig || !widgetConfig.id) {
      throw new Error("Widget must have a valid id");
    }
    this.widgets.set(widgetConfig.id, {
      ...widgetConfig,
      enabled: widgetConfig.enabled !== false,
    });
  }

  async mountAll(context = {}) {
    const tasks = [];
    for (const [id, widget] of this.widgets.entries()) {
      if (!widget.enabled) continue;
      const container = document.querySelector(widget.slotSelector);
      if (container && typeof widget.mount === "function") {
        tasks.push(widget.mount(container, context));
      }
    }
    await Promise.all(tasks);
  }

  async refreshWidget(id) {
    const widget = this.widgets.get(id);
    if (widget && typeof widget.refresh === "function") {
      await widget.refresh();
    }
  }

  listWidgets() {
    return Array.from(this.widgets.values());
  }
}

export const widgetRegistry = new WidgetRegistry();

export function showToast(message, durationMs = 3200) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = message;
  container.appendChild(el);
  setTimeout(() => {
    el.remove();
  }, durationMs);
}
