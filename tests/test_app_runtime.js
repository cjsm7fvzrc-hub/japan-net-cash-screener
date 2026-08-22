const assert = require("node:assert");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id, value: id === "sort" ? "tenbagger" : "", textContent: "", innerHTML: "",
      className: "", style: {}, addEventListener() {},
    });
  }
  return elements.get(id);
}

global.document = {
  getElementById: element,
  querySelectorAll() { return []; },
  querySelector() { return null; },
};
global.localStorage = {
  values: new Map(),
  getItem(key) { return this.values.get(key) ?? null; },
  setItem(key, value) { this.values.set(key, value); },
};
global.setInterval = () => 0;
global.fetch = async (url) => ({
  async json() {
    if (url.includes("status.json")) return {
      progress: 100, processed: 1, total: 1, failed: 0, state: "completed",
      updated_at: "2026-08-22T00:00:00Z", message: "完了",
    };
    return {generated_at: "2026-08-22T00:00:00Z", stocks: [{
      code: "9999", name: "テスト", market: "プライム", price: 1000,
      sector: "Technology", industry: "Software - Application",
      market_cap: 10e9, per: 12, pbr: 1, net_cash: 5e9, net_cash_ratio: 0.5,
      passed: false, tenbagger_score: 70, catalyst_score: 65,
      investment_score: 68, investment_decision: "有力候補",
      risk_score: 10, risk_level: "低", data_quality_score: 90,
      risk_reasons: [], risk_protections: ["営業キャッシュフローが黒字"],
      catalyst_signals: ["成長"], catalyst_checks: [],
      tenbagger_reasons: ["成長"], tenbagger_risks: [],
    }]};
  },
});

require("../web/i18n.js");
require("../web/app.js");
setImmediate(() => {
  assert.match(element("cards").innerHTML, /総合投資判断/);
  assert.match(element("cards").innerHTML, /有力候補/);
  assert.match(element("cards").innerHTML, /情報技術／業務用ソフトウェア/);
  assert.doesNotMatch(element("cards").innerHTML, /Technology/);
  assert.equal(element("progressText").textContent, "100.0%");
  console.log("app runtime ok");
});
