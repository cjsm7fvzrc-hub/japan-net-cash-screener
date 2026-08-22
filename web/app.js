const $ = (id) => document.getElementById(id);
let stocks = [],
  mode = "tenbagger";
const storage = {
  read(key, fallback) {
    try {
      return JSON.parse(localStorage.getItem(key)) ?? fallback;
    } catch {
      return fallback;
    }
  },
  write(key, value) {
    try {
      localStorage.setItem(key, JSON.stringify(value));
    } catch {}
  },
};
let research = storage.read("tenbagger-research-v1", {}),
  alerts = storage.read("tenbagger-alerts-v1", []);
const esc = (v) =>
  String(v ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const yen = (n, b = false) =>
  n == null
    ? "—"
    : b
      ? `${(n / 1e8).toLocaleString("ja-JP", { maximumFractionDigits: 1 })}億円`
      : `¥${n.toLocaleString("ja-JP", { maximumFractionDigits: 0 })}`;
const num = (n, d = 2) => (n == null ? "—" : Number(n).toFixed(d)),
  pct = (n, d = 1) => (n == null ? "—" : `${(Number(n) * 100).toFixed(d)}%`),
  date = (v) => (v ? new Date(v).toLocaleString("ja-JP") : "—");
function metric(name, value, ok, main = false) {
  const mark =
    ok === undefined
      ? ""
      : `<i class="${ok ? "yes" : "no"}"> ${ok ? "○" : "×"}</i>`;
  return `<div class="metric ${main ? "main" : ""}"><span>${name}${mark}</span><b>${value}</b></div>`;
}
function points(items, kind) {
  if (!items?.length) return "<li>検出項目なし</li>";
  return items.map((x) => `<li class="${kind}">${esc(x)}</li>`).join("");
}
const watched = (code) => Boolean(research[code]?.watched);
function decisionPanel(s) {
  const score = s.investment_score ?? 0;
  const risk = s.risk_score ?? 0;
  return `<section class="decisionPanel"><div class="kHead"><div><small>PHASE 3 / DECISION & DOWNSIDE</small><h4>総合投資判断</h4></div><div class="score"><b>${score}</b><span>/100</span></div></div><div class="decisionBadges"><strong>${esc(s.investment_decision || "更新待ち")}</strong><span class="risk risk-${esc(s.risk_level || "低")}">リスク ${esc(s.risk_level || "—")}・${risk}点</span><span>データ信頼度 ${s.data_quality_score ?? 0}%</span></div><div class="evidence"><div><b>下値を支える材料</b><ul>${points(s.risk_protections, "positive")}</ul></div><div><b>割安の罠・下振れ要因</b><ul>${points(s.risk_reasons, "caution")}</ul></div></div></section>`;
}
function workbench(s) {
  const saved = research[s.code] || {};
  const scenario = saved.scenario || {};
  const eps = scenario.eps ?? s.scenario_base_eps ?? "";
  const growth = scenario.growth ?? Math.round((s.scenario_growth_default ?? 0.05) * 100);
  const targetPer = scenario.per ?? s.scenario_per_default ?? 15;
  const years = scenario.years ?? 3;
  return `<section class="workbench"><div class="workbenchHead"><div><small>PHASE 4–5 / RESEARCH WORKBENCH</small><h4>3年シナリオ・投資メモ</h4></div><button class="watchButton ${watched(s.code) ? "active" : ""}" data-action="watch" data-code="${esc(s.code)}">${watched(s.code) ? "★ 監視中" : "☆ ウォッチ"}</button></div><div class="scenarioGrid"><label>基準EPS<input type="number" step="0.01" data-scenario="eps" data-code="${esc(s.code)}" value="${esc(eps)}"></label><label>年成長率<input type="number" step="1" data-scenario="growth" data-code="${esc(s.code)}" value="${esc(growth)}"><i>%</i></label><label>出口PER<input type="number" step="0.5" data-scenario="per" data-code="${esc(s.code)}" value="${esc(targetPer)}"><i>倍</i></label><label>期間<input type="number" min="1" max="10" data-scenario="years" data-code="${esc(s.code)}" value="${esc(years)}"><i>年</i></label></div><button class="calculate" data-action="calculate" data-code="${esc(s.code)}">シナリオを計算</button><div class="scenarioResult" id="scenario-${esc(s.code)}">入力値から将来株価と年率リターンを試算します。</div><div class="journal"><label>確信度<select data-journal="conviction" data-code="${esc(s.code)}"><option value="">未設定</option>${["低","中","高"].map((x) => `<option ${saved.conviction === x ? "selected" : ""}>${x}</option>`).join("")}</select></label><label>調査メモ<textarea data-journal="note" data-code="${esc(s.code)}" placeholder="投資仮説、確認事項、撤退条件を記録">${esc(saved.note || "")}</textarea></label></div><p class="estimateNote">メモとウォッチリストはこのブラウザ内に保存されます。シナリオは予測ではなく感応度確認です。</p></section>`;
}
function safeUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? esc(url.href) : "";
  } catch {
    return "";
  }
}
function kiyohara(s) {
  const score = s.kiyohara_score ?? 0,
    doc = s.kiyohara_confidence === "資料確認済み";
  const source = s.source_doc_id
    ? `<p class="source">参照：${esc(s.source_name || "有価証券報告書")}（${esc(s.source_date || "日付不明")}／EDINET ${esc(s.source_doc_id)}）</p>`
    : "";
  return `<section class="kiyohara"><div class="kHead"><div><small>KIYOHARA-STYLE ESTIMATE</small><h4>清原式・推定評価</h4></div><div class="score"><b>${score}</b><span>/100</span></div></div><div class="verdictRow"><strong class="verdict v${score >= 75 ? 4 : score >= 55 ? 3 : score >= 35 ? 2 : 1}">${esc(s.kiyohara_verdict || "判定準備中")}</strong><span>${doc ? "有価証券報告書を反映" : "数値ベースの暫定評価"}</span></div><p class="kSummary">${esc(s.kiyohara_summary || "次回の更新で推定評価を生成します。")}</p><div class="evidence"><div><b>評価した材料</b><ul>${points(s.kiyohara_positives, "positive")}</ul></div><div><b>注意・反対材料</b><ul>${points(s.kiyohara_cautions, "caution")}</ul></div></div>${source}<p class="estimateNote">公開情報から機械的に推定した調査支援情報であり、清原達郎氏本人の判断・投資助言ではありません。</p></section>`;
}
function tenbagger(s) {
  const score = s.tenbagger_score ?? 0;
  return `<section class="tenbagger"><div class="kHead"><div><small>RESEARCH PRIORITY</small><h4>テンバガー候補評価</h4></div><div class="score"><b>${score}</b><span>/100</span></div></div><div class="verdictRow"><strong class="typeBadge type-${esc(s.tenbagger_type || "継続観察")}">${esc(s.tenbagger_type || "継続観察")}</strong><span>${esc(s.tenbagger_verdict || "更新待ち")}</span></div><div class="growthMetrics">${metric("売上高 3年CAGR", pct(s.revenue_cagr_3y), s.revenue_cagr_3y >= 0.1)}${metric("営業利益 3年CAGR", pct(s.operating_income_cagr_3y), s.operating_income_cagr_3y >= 0.1)}${metric("四半期売上 YoY", pct(s.quarterly_revenue_growth), s.quarterly_revenue_growth >= 0.1)}${metric("営業利益率", pct(s.operating_margin), s.operating_margin >= 0.1)}${metric("利益率の前年差", s.operating_margin_change == null ? "—" : `${s.operating_margin_change >= 0 ? "+" : ""}${pct(s.operating_margin_change)}`, s.operating_margin_change >= 0.02)}${metric("52週高値から", pct(s.distance_from_52w_high), s.distance_from_52w_high >= -0.15)}</div><div class="evidence"><div><b>候補になった理由</b><ul>${points(s.tenbagger_reasons, "positive")}</ul></div><div><b>先に確認するリスク</b><ul>${points(s.tenbagger_risks, "caution")}</ul></div></div><p class="estimateNote">将来の株価上昇を予測・保証する点数ではなく、追加調査の優先順位です。</p></section>`;
}
function catalysts(s) {
  const score = s.catalyst_score ?? 0;
  const website = safeUrl(s.company_website);
  const companyLink = website
    ? `<a href="${website}" target="_blank" rel="noopener noreferrer">企業サイト</a>`
    : "";
  const yahoo = `https://finance.yahoo.co.jp/quote/${encodeURIComponent(s.code)}.T/disclosure`;
  const links = [
    companyLink,
    `<a href="${yahoo}" target="_blank" rel="noopener noreferrer">開示情報</a>`,
    '<a href="https://www.release.tdnet.info/inbs/I_main_00.html" target="_blank" rel="noopener noreferrer">TDnet</a>',
  ].filter(Boolean).join("");
  const epsGrowth = s.forward_eps_growth ?? s.earnings_growth;
  const operatingGrowth = s.operating_profit_turnaround
    ? "黒字転換"
    : pct(s.quarterly_operating_income_growth);
  return `<section class="catalyst"><div class="kHead"><div><small>PHASE 2 / CHANGE & CATALYST</small><h4>変化・触媒モニター</h4></div><div class="score"><b>${score}</b><span>/100</span></div></div><div class="verdictRow"><strong class="signal signal-${score >= 70 ? "strong" : score >= 50 ? "watch" : "neutral"}">${esc(s.revision_signal || "更新待ち")}</strong><span>${esc(s.transformation_signal || "変化を観察")}</span></div>${s.sector || s.industry ? `<p class="businessLine">${esc([s.sector, s.industry].filter(Boolean).join(" / "))}</p>` : ""}<div class="growthMetrics">${metric("四半期営業利益 YoY", operatingGrowth, s.operating_profit_turnaround || s.quarterly_operating_income_growth >= 0.1)}${metric("売上成長の加速度", pct(s.revenue_acceleration), s.revenue_acceleration >= 0.05)}${metric("利益成長の加速度", pct(s.operating_income_acceleration), s.operating_income_acceleration >= 0.1)}${metric("予想EPS成長", pct(epsGrowth), epsGrowth >= 0.1)}${metric("出来高 / 20日平均", s.volume_ratio_20d == null ? "—" : `${num(s.volume_ratio_20d)}倍`, s.volume_ratio_20d >= 1.5)}${metric("52週騰落率", pct(s.return_52w), s.return_52w > 0)}</div><div class="evidence"><div><b>検出した変化</b><ul>${points(s.catalyst_signals, "positive")}</ul></div><div><b>決算・IRで確認する点</b><ul>${points(s.catalyst_checks, "caution")}</ul></div></div><div class="researchLinks"><span>一次情報を確認</span>${links}</div><p class="estimateNote">「上方修正兆候」は公表済みの業績修正を示すものではありません。決算数値と予想値から追加確認の優先度を機械判定しています。</p></section>`;
}
function updateAlerts(nextStocks, generatedAt) {
  const previous = storage.read("tenbagger-snapshot-v1", {});
  if (previous.generatedAt && previous.generatedAt !== generatedAt) {
    const oldRows = previous.rows || {};
    nextStocks.filter((s) => watched(s.code)).forEach((s) => {
      const old = oldRows[s.code];
      if (!old) return;
      const changes = [];
      const investmentDelta = (s.investment_score ?? 0) - (old.investment_score ?? 0);
      const catalystDelta = (s.catalyst_score ?? 0) - (old.catalyst_score ?? 0);
      const riskDelta = (s.risk_score ?? 0) - (old.risk_score ?? 0);
      const priceDelta = old.price ? (s.price ?? old.price) / old.price - 1 : 0;
      if (investmentDelta >= 10) changes.push(`総合スコア +${investmentDelta}点`);
      if (catalystDelta >= 15) changes.push(`触媒スコア +${catalystDelta}点`);
      if (riskDelta >= 15) changes.push(`リスク +${riskDelta}点`);
      if (Math.abs(priceDelta) >= 0.1) changes.push(`株価 ${priceDelta >= 0 ? "+" : ""}${pct(priceDelta)}`);
      if (s.revision_signal === "上方修正兆候・強" && old.revision_signal !== s.revision_signal)
        changes.push("上方修正兆候・強へ変化");
      if (changes.length) alerts.unshift({code:s.code, name:s.name, changes, at:generatedAt});
    });
    alerts = alerts.slice(0, 60);
    storage.write("tenbagger-alerts-v1", alerts);
  }
  const rows = Object.fromEntries(nextStocks.map((s) => [s.code, {
    price:s.price, investment_score:s.investment_score, catalyst_score:s.catalyst_score,
    risk_score:s.risk_score, revision_signal:s.revision_signal,
  }]));
  storage.write("tenbagger-snapshot-v1", {generatedAt, rows});
}
function renderAlerts() {
  const watchedCount = Object.values(research).filter((x) => x.watched).length;
  $("summary").textContent = `ウォッチ ${watchedCount}社／変化通知 ${alerts.length}件`;
  $("cards").innerHTML = alerts.length
    ? `<div class="alertList">${alerts.map((a) => `<article class="alertItem"><small>${date(a.at)}</small><h3>${esc(a.code)}　${esc(a.name)}</h3><ul>${a.changes.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></article>`).join("")}</div>`
    : '<div class="empty">ウォッチ銘柄を登録すると、データ更新時のスコア・リスク・株価の大きな変化をここに記録します。</div>';
}
function render() {
  const q = $("search").value.trim(),
    type = $("candidateType").value,
    sort = $("sort").value;
  let shown = stocks.filter(
    (s) =>
      `${s.code}${s.name}`.includes(q) && (!type || s.tenbagger_type === type),
  );
  if (mode === "alerts") {
    renderAlerts();
    return;
  }
  if (mode === "kiyohara") shown = shown.filter((s) => s.passed);
  if (mode === "tenbagger")
    shown = shown.filter((s) => (s.tenbagger_score || 0) >= 45);
  if (mode === "catalyst")
    shown = shown.filter((s) => (s.catalyst_score || 0) >= 30);
  if (mode === "decision")
    shown = shown.filter((s) => (s.investment_score || 0) >= 40);
  if (mode === "risk") shown = shown.filter((s) => (s.risk_score || 0) >= 30);
  if (mode === "watchlist") shown = shown.filter((s) => watched(s.code));
  const sorter = {
    tenbagger: (a, b) => (b.tenbagger_score || 0) - (a.tenbagger_score || 0),
    kiyohara: (a, b) => (b.kiyohara_score || 0) - (a.kiyohara_score || 0),
    growth: (a, b) => (b.revenue_cagr_3y ?? -99) - (a.revenue_cagr_3y ?? -99),
    netcash: (a, b) => (b.net_cash_ratio ?? -99) - (a.net_cash_ratio ?? -99),
    catalyst: (a, b) => (b.catalyst_score || 0) - (a.catalyst_score || 0),
    decision: (a, b) => (b.investment_score || 0) - (a.investment_score || 0),
    risk: (a, b) => (b.risk_score || 0) - (a.risk_score || 0),
  }[sort];
  shown.sort(sorter);
  $("summary").textContent =
    `保存済み ${stocks.length.toLocaleString()}社／表示 ${shown.length.toLocaleString()}社`;
  if (!shown.length) {
    $("cards").innerHTML =
      '<div class="empty">該当する銘柄はありません。成長指標は次回の銘柄更新後から順次表示されます。</div>';
    return;
  }
  $("cards").innerHTML = shown
    .map(
      (s) =>
        `<article class="stock"><div class="stockHead"><div><small>${esc(s.code)} ・ ${esc(s.market)}</small><h3>${esc(s.name)}</h3><button class="reportButton" data-action="report" data-code="${esc(s.code)}">詳細レポートを発行</button></div><div class="headScores"><span class="miniScore">総合 <b>${s.investment_score ?? 0}</b></span><span class="miniScore">候補 <b>${s.tenbagger_score ?? 0}</b></span><span class="miniScore">変化 <b>${s.catalyst_score ?? 0}</b></span><span class="badge ${s.passed ? "pass" : ""}">${s.passed ? "清原条件合格" : "条件外"}</span></div></div><div class="metrics">${metric("株価", yen(s.price))}${metric("時価総額", yen(s.market_cap, true), s.market_cap >= 2e9)}${metric("PER", s.per == null ? "—" : num(s.per) + "倍", s.per > 0 && s.per <= 10)}${metric("PBR", s.pbr == null ? "—" : num(s.pbr) + "倍", s.pbr > 0 && s.pbr <= 1)}${metric("ネットキャッシュ", yen(s.net_cash, true))}${metric("ネットキャッシュ比率", num(s.net_cash_ratio), s.net_cash_ratio >= 1, true)}</div>${mode === "kiyohara" ? kiyohara(s) : `${tenbagger(s)}${catalysts(s)}${decisionPanel(s)}${["decision","watchlist"].includes(mode) ? workbench(s) : ""}`}${s.financial_date ? `<p class="asof">財務基準日：${esc(s.financial_date)}</p>` : ""}${s.error ? `<p class="errorText">取得失敗：${esc(s.error)}</p>` : ""}</article>`,
    )
    .join("");
}
async function load() {
  try {
    const [status, result] = await Promise.all([
      fetch("data/status.json?" + Date.now()).then((r) => r.json()),
      fetch("data/results.json?" + Date.now()).then((r) => r.json()),
    ]);
    const progress = Number(status.progress || 0);
    $("progressText").textContent = progress.toFixed(1) + "%";
    $("processed").textContent =
      `${Number(status.processed || 0).toLocaleString()} / ${Number(status.total || 0).toLocaleString()}社`;
    $("failed").textContent =
      Number(status.failed || 0).toLocaleString() + "件";
    $("updated").textContent = date(status.updated_at);
    $("progressBar").style.width = Math.min(100, progress) + "%";
    $("statusMessage").textContent = status.message || "—";
    $("stateBadge").textContent =
      status.state === "completed"
        ? "更新完了"
        : status.state === "running"
          ? "更新中"
          : "待機中";
    $("stateBadge").className = status.state === "running" ? "running" : "";
    stocks = result.stocks || [];
    updateAlerts(stocks, result.generated_at);
    $("passCount").textContent =
      stocks.filter((s) => s.passed).length.toLocaleString() + "社";
    $("dataTime").textContent = "保存データ生成：" + date(result.generated_at);
    render();
  } catch (e) {
    $("stateBadge").textContent = "読込エラー";
    $("stateBadge").className = "error";
    $("statusMessage").textContent =
      "保存済みデータを読み込めませんでした。しばらく後に再読み込みしてください。";
    $("cards").innerHTML =
      '<div class="empty">初回の自動更新が完了すると結果が表示されます。</div>';
  }
}
$("search").addEventListener("input", render);
$("candidateType").addEventListener("change", render);
$("sort").addEventListener("change", render);
$("cards").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const code = button.dataset.code;
  const stock = stocks.find((s) => String(s.code) === String(code));
  if (!stock) return;
  research[code] ||= {};
  if (button.dataset.action === "report") {
    if (window.StockReport) window.StockReport.open(stock, research[code]);
    return;
  }
  if (button.dataset.action === "watch") {
    research[code].watched = !research[code].watched;
    storage.write("tenbagger-research-v1", research);
    render();
    return;
  }
  if (button.dataset.action === "calculate") {
    const read = (field) => Number(document.querySelector(`[data-scenario="${field}"][data-code="${code}"]`)?.value);
    const eps = read("eps"), growth = read("growth"), targetPer = read("per"), years = read("years");
    const output = $(`scenario-${code}`);
    if (![eps, growth, targetPer, years].every(Number.isFinite) || eps <= 0 || targetPer <= 0 || years < 1) {
      output.textContent = "正のEPS・PER・期間を入力してください。";
      return;
    }
    const futurePrice = eps * (1 + growth / 100) ** years * targetPer;
    const totalReturn = stock.price ? futurePrice / stock.price - 1 : null;
    const annualReturn = stock.price ? (futurePrice / stock.price) ** (1 / years) - 1 : null;
    output.innerHTML = `<b>想定株価 ${yen(futurePrice)}</b><span>現在値比 ${pct(totalReturn)}／年率 ${pct(annualReturn)}</span>`;
    research[code].scenario = {eps, growth, per:targetPer, years};
    storage.write("tenbagger-research-v1", research);
  }
});
$("cards").addEventListener("input", (event) => {
  const field = event.target.dataset.journal;
  const code = event.target.dataset.code;
  if (!field || !code) return;
  research[code] ||= {};
  research[code][field] = event.target.value;
  storage.write("tenbagger-research-v1", research);
});
$("cards").addEventListener("change", (event) => {
  if (!event.target.dataset.journal) return;
  research[event.target.dataset.code] ||= {};
  research[event.target.dataset.code][event.target.dataset.journal] = event.target.value;
  storage.write("tenbagger-research-v1", research);
});
document.querySelectorAll(".modeTabs button").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".modeTabs button")
      .forEach((x) => x.classList.remove("active"));
    button.classList.add("active");
    mode = button.dataset.mode;
    $("sort").value = mode === "kiyohara" ? "kiyohara" : mode === "catalyst" ? "catalyst" : mode === "risk" ? "risk" : ["decision","watchlist"].includes(mode) ? "decision" : "tenbagger";
    render();
  }),
);
load();
setInterval(load, 60000);
