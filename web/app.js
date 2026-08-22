const $ = (id) => document.getElementById(id);
let stocks = [],
  mode = "tenbagger";
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
function render() {
  const q = $("search").value.trim(),
    type = $("candidateType").value,
    sort = $("sort").value;
  let shown = stocks.filter(
    (s) =>
      `${s.code}${s.name}`.includes(q) && (!type || s.tenbagger_type === type),
  );
  if (mode === "kiyohara") shown = shown.filter((s) => s.passed);
  if (mode === "tenbagger")
    shown = shown.filter((s) => (s.tenbagger_score || 0) >= 45);
  const sorter = {
    tenbagger: (a, b) => (b.tenbagger_score || 0) - (a.tenbagger_score || 0),
    kiyohara: (a, b) => (b.kiyohara_score || 0) - (a.kiyohara_score || 0),
    growth: (a, b) => (b.revenue_cagr_3y ?? -99) - (a.revenue_cagr_3y ?? -99),
    netcash: (a, b) => (b.net_cash_ratio ?? -99) - (a.net_cash_ratio ?? -99),
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
        `<article class="stock"><div class="stockHead"><div><small>${esc(s.code)} ・ ${esc(s.market)}</small><h3>${esc(s.name)}</h3></div><div class="headScores"><span class="miniScore">候補 <b>${s.tenbagger_score ?? 0}</b></span><span class="badge ${s.passed ? "pass" : ""}">${s.passed ? "清原条件合格" : "条件外"}</span></div></div><div class="metrics">${metric("株価", yen(s.price))}${metric("時価総額", yen(s.market_cap, true), s.market_cap >= 2e9)}${metric("PER", s.per == null ? "—" : num(s.per) + "倍", s.per > 0 && s.per <= 10)}${metric("PBR", s.pbr == null ? "—" : num(s.pbr) + "倍", s.pbr > 0 && s.pbr <= 1)}${metric("ネットキャッシュ", yen(s.net_cash, true))}${metric("ネットキャッシュ比率", num(s.net_cash_ratio), s.net_cash_ratio >= 1, true)}</div>${tenbagger(s)}${mode === "kiyohara" ? kiyohara(s) : ""}${s.financial_date ? `<p class="asof">財務基準日：${esc(s.financial_date)}</p>` : ""}${s.error ? `<p class="errorText">取得失敗：${esc(s.error)}</p>` : ""}</article>`,
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
document.querySelectorAll(".modeTabs button").forEach((button) =>
  button.addEventListener("click", () => {
    document
      .querySelectorAll(".modeTabs button")
      .forEach((x) => x.classList.remove("active"));
    button.classList.add("active");
    mode = button.dataset.mode;
    $("sort").value = mode === "kiyohara" ? "kiyohara" : "tenbagger";
    render();
  }),
);
load();
setInterval(load, 60000);
