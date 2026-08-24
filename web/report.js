(function () {
  const h = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;",
  })[c]);
  const number = (value, digits = 2) => value == null ? "—" : Number(value).toLocaleString("ja-JP", {maximumFractionDigits:digits});
  const percent = (value, digits = 1) => value == null ? "—" : `${(Number(value) * 100).toFixed(digits)}%`;
  const yieldPercent = (value) => value == null ? "—" : `${number(value, 2)}%`;
  const money = (value) => value == null ? "—" : `¥${Number(value).toLocaleString("ja-JP", {maximumFractionDigits:0})}`;
  const oku = (value) => value == null ? "—" : `${number(Number(value) / 1e8, 1)}億円`;
  const list = (items, empty = "検出項目なし") => `<ul>${items?.length ? items.map((x) => `<li>${h(x)}</li>`).join("") : `<li>${empty}</li>`}</ul>`;
  const safeUrl = (value) => {
    try {
      const url = new URL(value);
      return ["http:", "https:"].includes(url.protocol) ? h(url.href) : "";
    } catch { return ""; }
  };

  function sparkline(values) {
    const data = (values || []).map(Number).filter(Number.isFinite);
    if (data.length < 2) return '<div class="chartEmpty">価格系列は次回更新後に表示されます。</div>';
    const width = 720, height = 220, pad = 24;
    const min = Math.min(...data), max = Math.max(...data), span = max - min || 1;
    const points = data.map((value, index) => {
      const x = pad + index / (data.length - 1) * (width - pad * 2);
      const y = height - pad - (value - min) / span * (height - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="52週株価推移"><line x1="${pad}" y1="${height-pad}" x2="${width-pad}" y2="${height-pad}"/><polyline points="${points}"/><text x="${pad}" y="18">高値 ${money(max)}</text><text x="${pad}" y="${height-4}">安値 ${money(min)}</text><text x="${width-pad}" y="18" text-anchor="end">現在 ${money(data[data.length-1])}</text></svg>`;
  }

  function scenario(stock, name, growth, targetPer, years = 3) {
    const eps = Number(stock.scenario_base_eps);
    const price = Number(stock.price);
    if (!Number.isFinite(eps) || eps <= 0 || !Number.isFinite(price) || price <= 0) {
      return `<tr><th>${name}</th><td>${percent(growth)}</td><td>${number(targetPer,1)}倍</td><td colspan="3">EPSまたは株価データ不足</td></tr>`;
    }
    const target = eps * (1 + growth) ** years * targetPer;
    const total = target / price - 1;
    const annual = (target / price) ** (1 / years) - 1;
    return `<tr><th>${name}</th><td>${percent(growth)}</td><td>${number(targetPer,1)}倍</td><td>${money(target)}</td><td>${percent(total)}</td><td>${percent(annual)}</td></tr>`;
  }

  function build(stock, saved = {}) {
    const baseGrowth = Number(stock.scenario_growth_default ?? 0.05);
    const basePer = Number(stock.scenario_per_default ?? 15);
    const company = safeUrl(stock.company_website);
    const yahoo = `https://finance.yahoo.co.jp/quote/${encodeURIComponent(stock.code)}.T/disclosure`;
    const edinet = "https://disclosure2.edinet-fsa.go.jp/";
    const tdnet = "https://www.release.tdnet.info/inbs/I_main_00.html";
    const sourceDescription = stock.source_doc_id
      ? `${h(stock.source_name || "有価証券報告書")}／${h(stock.source_date || "日付不明")}／文書ID ${h(stock.source_doc_id)}`
      : "EDINET資料の自動解析なし（リンク先で銘柄コードを検索）";
    const classification = globalThis.JapaneseLabels?.classification(stock) || "業種分類は企業IRで確認";
    const businessText = globalThis.JapaneseLabels?.business(stock) ||
      "事業概要データは未取得です。会社IRで事業構成と収益源を確認してください。";
    const business = `<p>${h(businessText)}</p>`;
    const generated = new Date().toLocaleString("ja-JP");
    const entryPrice = Number(saved.watch_entry_price);
    const currentPrice = Number(stock.price);
    const shares = Number(saved.watch_shares) > 0 ? Number(saved.watch_shares) : 100;
    let virtualPosition = "";
    if (saved.watched && entryPrice > 0 && currentPrice > 0) {
      const cost = entryPrice * shares;
      const value = currentPrice * shares;
      const profit = value - cost;
      const rate = profit / cost;
      const sign = profit >= 0 ? "+" : "−";
      const tone = profit >= 0 ? "gain" : "loss";
      const addedAt = saved.watch_added_at
        ? new Date(saved.watch_added_at).toLocaleString("ja-JP")
        : "記録なし";
      virtualPosition = `<section><p class="eyebrow">ウォッチリスト仮想運用</p><h2>仮想100株ポジション</h2><div class="grid">${[["登録日時",addedAt],["仮想株数",`${number(shares,0)}株`],["取得基準株価",money(entryPrice)],["投資額",money(cost)],["最新評価額",money(value)],["評価損益",`${sign}${money(Math.abs(profit))}（${sign}${Math.abs(rate*100).toFixed(1)}%）`]].map(([a,b],index)=>`<div class="metric"><span>${a}</span><b class="${index===5?tone:""}">${b}</b></div>`).join("")}</div><p class="disclaimer">実際の約定・保有ではありません。ウォッチ追加時（既存登録は機能開始時）の保存株価を基準に、保存データの最新株価で算出しています。リアルタイム価格ではありません。</p></section>`;
    }
    return `<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>${h(stock.code)} ${h(stock.name)} 詳細投資判断レポート</title><style>
      :root{--ink:#17231d;--green:#315b46;--paper:#f6f4ed;--line:#d7d5cb;--warn:#8a4b35}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Yu Gothic",sans-serif;line-height:1.65}.toolbar{position:sticky;top:0;display:flex;gap:8px;justify-content:flex-end;padding:10px 4vw;background:#17231d;z-index:2}.toolbar button{border:1px solid #b9c6bc;background:#fff;padding:9px 13px;cursor:pointer}.report{max-width:960px;margin:28px auto;background:#fff;padding:48px}.cover{border-bottom:4px solid var(--green);padding-bottom:24px;margin-bottom:30px}.cover small,.eyebrow{letter-spacing:.14em;color:#68766e;font-size:10px}.cover h1{font:500 38px Georgia,"Yu Mincho",serif;margin:8px 0}.cover .decision{display:flex;flex-wrap:wrap;gap:9px;margin-top:16px}.pill{border:1px solid var(--line);padding:7px 10px;background:#f3f5ec;font-size:12px}.score{font:bold 20px Georgia;color:var(--green)}.gain{color:#217047}.loss{color:#a14235}section{margin:30px 0;break-inside:avoid}h2{font:500 25px Georgia,"Yu Mincho",serif;border-bottom:1px solid var(--line);padding-bottom:8px}h3{font-size:14px}.grid{display:grid;grid-template-columns:repeat(3,1fr);border-left:1px solid var(--line);border-top:1px solid var(--line)}.metric{padding:11px;border-right:1px solid var(--line);border-bottom:1px solid var(--line)}.metric span{display:block;color:#6d7871;font-size:9px}.metric b{font-size:13px}.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}.box{border:1px solid var(--line);padding:15px}.box ul{margin:8px 0;padding-left:20px;font-size:12px}svg{width:100%;height:auto;background:#f7f8f4}svg line{stroke:#c7cec7}svg polyline{fill:none;stroke:var(--green);stroke-width:3}svg text{font-size:11px;fill:#657168}.chartEmpty{padding:50px;text-align:center;background:#f6f6f2;color:#788179}table{width:100%;border-collapse:collapse;font-size:11px}th,td{border:1px solid var(--line);padding:9px;text-align:right}th:first-child,td:first-child{text-align:left}.sources a{display:block;color:var(--green);margin:6px 0}.note{background:#f5f1e5;border-left:4px solid #b89b4d;padding:14px}.disclaimer{font-size:9px;color:#69736d;border-top:1px solid var(--line);padding-top:14px}.pageBreak{break-before:page}@media(max-width:700px){.report{padding:24px;margin:0}.grid{grid-template-columns:repeat(2,1fr)}.two{grid-template-columns:1fr}.cover h1{font-size:28px}}@media print{body{background:#fff}.toolbar{display:none}.report{max-width:none;margin:0;padding:10mm}@page{size:A4;margin:12mm}}
    </style></head><body><div class="toolbar"><button onclick="window.print()">PDF保存・印刷</button><button onclick="downloadHtml()">HTMLをダウンロード</button></div><main class="report">
      <header class="cover"><small>詳細投資判断レポート／${h(generated)}</small><h1>${h(stock.code)}　${h(stock.name)}</h1><p>${h(stock.market || "")}　${h(classification)}</p><div class="decision"><span class="pill">最終機械判定 <b>${h(stock.investment_decision || "データ補完を優先")}</b></span><span class="pill">総合 <b class="score">${stock.investment_score ?? 0}</b>/100</span><span class="pill">候補 ${stock.tenbagger_score ?? 0}</span><span class="pill">触媒 ${stock.catalyst_score ?? 0}</span><span class="pill">リスク ${stock.risk_score ?? 0}</span><span class="pill">データ信頼度 ${stock.data_quality_score ?? 0}%</span></div></header>
      <section><p class="eyebrow">判断要約</p><h2>判断要約</h2><div class="two"><div class="box"><h3>投資仮説を支える材料</h3>${list([...(stock.tenbagger_reasons||[]),...(stock.catalyst_signals||[]),...(stock.risk_protections||[])].slice(0,9))}</div><div class="box"><h3>反証・撤退条件として確認する材料</h3>${list([...(stock.tenbagger_risks||[]),...(stock.catalyst_checks||[]),...(stock.risk_reasons||[])].slice(0,9))}</div></div></section>
      <section><p class="eyebrow">事業・ファンダメンタル分析</p><h2>事業・ファンダメンタル分析</h2>${business}<div class="grid">
        ${[["株価",money(stock.price)],["時価総額",oku(stock.market_cap)],["PER",stock.per==null?"—":`${number(stock.per)}倍`],["PBR",stock.pbr==null?"—":`${number(stock.pbr)}倍`],["ネットキャッシュ比率",number(stock.net_cash_ratio)],["フリーCF",oku(stock.free_cash_flow)],["ROE",percent(stock.return_on_equity)],["ROA",percent(stock.return_on_assets)],["粗利率",percent(stock.gross_margin)],["負債資本倍率",stock.debt_to_equity==null?"—":`${number(stock.debt_to_equity)}%`],["配当利回り",yieldPercent(stock.dividend_yield)],["営業CF",oku(stock.operating_cash_flow)]].map(([a,b])=>`<div class="metric"><span>${a}</span><b>${b}</b></div>`).join("")}
      </div><div class="grid">
        ${[["売上3年平均成長率",percent(stock.revenue_cagr_3y)],["営業利益3年平均成長率",percent(stock.operating_income_cagr_3y)],["四半期売上 前年同期比",percent(stock.quarterly_revenue_growth)],["四半期営業利益 前年同期比",stock.operating_profit_turnaround?"黒字転換":percent(stock.quarterly_operating_income_growth)],["営業利益率",percent(stock.operating_margin)],["予想1株利益（EPS）成長率",percent(stock.forward_eps_growth??stock.earnings_growth)]].map(([a,b])=>`<div class="metric"><span>${a}</span><b>${b}</b></div>`).join("")}
      </div></section>
      <section class="pageBreak"><p class="eyebrow">チャート・需給分析</p><h2>52週チャート・需給分析</h2>${sparkline(stock.price_history_52w)}<div class="grid">
        ${[["テクニカル判定",stock.technical_score==null?"未取得":`${h(stock.technical_trend||"未判定")}・${stock.technical_score}点`],["20日移動平均",money(stock.ma20)],["50日移動平均",money(stock.ma50)],["200日移動平均",money(stock.ma200)],["相対力指数（RSI・14日）",number(stock.rsi14,1)],["60日年率変動率",percent(stock.volatility_60d)],["1年最大下落率",percent(stock.max_drawdown_1y)],["52週騰落率",percent(stock.return_52w)],["出来高比率",stock.volume_ratio_20d==null?"—":`${number(stock.volume_ratio_20d)}倍`]].map(([a,b])=>`<div class="metric"><span>${a}</span><b>${b}</b></div>`).join("")}
      </div><div class="two"><div class="box"><h3>チャート上の支持材料</h3>${list(stock.technical_signals)}</div><div class="box"><h3>チャート上の警戒材料</h3>${list(stock.technical_cautions)}</div></div></section>
      <section><p class="eyebrow">シナリオ分析</p><h2>3年シナリオ</h2><table><thead><tr><th>ケース</th><th>1株利益（EPS）成長率</th><th>出口株価収益率（PER）</th><th>想定株価</th><th>現在値比</th><th>年率</th></tr></thead><tbody>${scenario(stock,"弱気",Math.max(-.2,baseGrowth-.10),Math.max(6,basePer-4))}${scenario(stock,"基本",baseGrowth,basePer)}${scenario(stock,"強気",Math.min(.4,baseGrowth+.10),Math.min(30,basePer+5))}</tbody></table><p class="disclaimer">1株利益（EPS）が一定率で成長し、指定した株価収益率（PER）で評価される単純な感応度分析です。業績・株価を予測するものではありません。</p></section>
      <section><p class="eyebrow">一次情報・精査項目</p><h2>IR一次情報と確認事項</h2><div class="two"><div class="box sources">${company?`<a href="${company}" target="_blank">企業公式サイト</a>`:""}<a href="${h(yahoo)}" target="_blank">開示情報一覧</a><a href="${tdnet}" target="_blank">TDnet 適時開示</a><a href="${edinet}" target="_blank">EDINET 開示書類</a><p>${sourceDescription}</p></div><div class="box"><h3>最終確認チェックリスト</h3>${list(["最新決算短信と会社計画の前提","セグメント別の売上・利益構成","上方修正・下方修正と一過性要因","大株主・希薄化・資本配分","競争優位性と市場規模","投資仮説が崩れる条件と許容損失"])}</div></div></section>
      ${virtualPosition}<section><p class="eyebrow">投資判断メモ</p><h2>利用者メモ</h2><div class="note"><b>確信度：${h(saved.conviction||"未設定")}</b><p>${h(saved.note||"メモ未入力")}</p></div></section>
      <p class="disclaimer">本レポートは公開データを機械処理した調査支援資料であり、投資助言・将来収益の保証ではありません。Yahoo Finance由来データには遅延・欠損・勘定科目差があり得ます。売買前に会社IR、TDnet、EDINETの原資料を確認してください。</p>
    </main><script>function downloadHtml(){const blob=new Blob(['<!doctype html>'+document.documentElement.outerHTML],{type:'text/html;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='${h(stock.code)}-investment-report.html';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}</script></body></html>`;
  }

  function open(stock, saved) {
    const html = build(stock, saved);
    const url = URL.createObjectURL(new Blob([html], {type:"text/html;charset=utf-8"}));
    const tab = window.open(url, "_blank", "noopener");
    if (!tab) {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${stock.code}-investment-report.html`;
      anchor.click();
    }
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }

  window.StockReport = {build, open};
})();
