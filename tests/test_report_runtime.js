const assert = require("node:assert");

global.window = global;
require("../web/i18n.js");
require("../web/report.js");

const html = window.StockReport.build({
  code: "9999", name: "テスト<&>", market: "プライム", price: 1000,
  sector: "Technology", industry: "Software - Application",
  business_summary: "An English business description.",
  market_cap: 20e9, per: 12, pbr: 1.1, net_cash_ratio: 0.5,
  free_cash_flow: 2e9, return_on_equity: 0.15, return_on_assets: 0.08,
  gross_margin: 0.4, debt_to_equity: 20, dividend_yield: 0.02,
  operating_cash_flow: 3e9, revenue_cagr_3y: 0.15,
  operating_income_cagr_3y: 0.2, quarterly_revenue_growth: 0.18,
  quarterly_operating_income_growth: 0.25, operating_margin: 0.12,
  forward_eps_growth: 0.15, scenario_base_eps: 80,
  scenario_growth_default: 0.15, scenario_per_default: 18,
  investment_decision: "有力候補", investment_score: 70,
  tenbagger_score: 72, catalyst_score: 65, risk_score: 15, data_quality_score: 90,
  price_history_52w: [700, 750, 800, 900, 1000],
  technical_trend: "上昇", technical_score: 75, ma20: 960, ma50: 900,
  ma200: 820, rsi14: 62, volatility_60d: 0.25, max_drawdown_1y: -0.18,
  technical_signals: ["株価が50日移動平均を上回る"], technical_cautions: [],
  tenbagger_reasons: ["成長"], catalyst_signals: ["加速"], risk_protections: ["現金"],
  tenbagger_risks: [], catalyst_checks: [], risk_reasons: [],
}, {conviction:"高", note:"決算を継続確認"});

assert.match(html, /詳細投資判断レポート/);
assert.match(html, /52週チャート・需給分析/);
assert.match(html, /PDF保存・印刷/);
assert.match(html, /HTMLをダウンロード/);
assert.match(html, /弱気/);
assert.match(html, /テスト&lt;&amp;&gt;/);
assert.match(html, /情報技術／業務用ソフトウェア/);
assert.match(html, /具体的な事業内容、収益構成/);
assert.doesNotMatch(html, /An English business description/);
assert.doesNotMatch(html, /EXECUTIVE SUMMARY/);
assert.doesNotMatch(html, /テスト<&>/);
console.log("report runtime ok");
