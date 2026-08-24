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
    if (url.includes("model_review.json")) return {
      status:"検証運用中", snapshot_count:3,
      current_quality:{stock_count:1,failed_count:0,coverage_percent:{price:100},anomalies:[]},
      horizons:[{days:30,candidates:{count:5,average_return:.12,gain_30_rate:.2,loss_20_rate:0},control:{average_return:.03},excess_return:.09}],
      proposals:[{status:"観測中",title:"現行基準を維持",evidence:"標本不足",change:"変更なし",risk:"短期機会"}],
    };
    if (url.includes("ai_review.json")) return {status:"未設定",summary:"通常の検証には影響しません。",agreements:[],objections:[]};
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
  global.ScreenerApp.setWatched(
    {code:"9999", price:1000}, true, "2026-08-24T00:00:00Z",
  );
  const saved = JSON.parse(localStorage.getItem("tenbagger-research-v1"))["9999"];
  assert.equal(saved.watch_entry_price, 1000);
  assert.equal(saved.watch_shares, 100);
  assert.equal(saved.watch_added_at, "2026-08-24T00:00:00Z");
  const position = global.ScreenerApp.positionPanel({code:"9999", price:1200});
  assert.match(position, /仮想100株ポジション/);
  assert.match(position, /\+¥20,000/);
  assert.match(position, /\+20\.0%/);
  global.ScreenerApp.setWatched({code:"9999", price:1200}, false);
  const removed = JSON.parse(localStorage.getItem("tenbagger-research-v1"))["9999"];
  assert.equal(removed.watched, false);
  assert.equal(removed.watch_entry_price, undefined);
  global.ScreenerApp.renderGovernance();
  assert.match(element("cards").innerHTML, /判定精度を継続検証/);
  assert.match(element("cards").innerHTML, /自動変更なし/);
  assert.match(element("cards").innerHTML, /現行基準を維持/);
  console.log("app runtime ok");
});
