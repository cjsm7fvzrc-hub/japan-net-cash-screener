(function () {
  const sectors = {
    "Technology":"情報技術", "Financial Services":"金融サービス",
    "Consumer Cyclical":"一般消費財", "Industrials":"資本財・産業",
    "Healthcare":"ヘルスケア", "Communication Services":"通信サービス",
    "Consumer Defensive":"生活必需品", "Basic Materials":"素材",
    "Real Estate":"不動産", "Energy":"エネルギー", "Utilities":"公益事業",
  };
  const industries = {
    "Software - Application":"業務用ソフトウェア", "Software - Infrastructure":"基盤ソフトウェア",
    "Information Technology Services":"情報技術サービス", "Semiconductors":"半導体",
    "Semiconductor Equipment & Materials":"半導体製造装置・材料", "Electronic Components":"電子部品",
    "Computer Hardware":"コンピューター機器", "Communication Equipment":"通信機器",
    "Consumer Electronics":"家電・電子機器", "Internet Content & Information":"インターネット情報サービス",
    "Banks - Regional":"地方銀行", "Banks - Diversified":"総合銀行",
    "Insurance - Life":"生命保険", "Insurance - Property & Casualty":"損害保険",
    "Insurance - Diversified":"総合保険", "Asset Management":"資産運用",
    "Capital Markets":"証券・資本市場", "Credit Services":"信用・決済サービス",
    "Auto Manufacturers":"自動車製造", "Auto Parts":"自動車部品",
    "Specialty Chemicals":"特殊化学", "Chemicals":"化学", "Steel":"鉄鋼",
    "Building Materials":"建設資材", "Construction":"建設", "Engineering & Construction":"建設・エンジニアリング",
    "Industrial Distribution":"産業資材卸売", "Specialty Industrial Machinery":"産業機械",
    "Farm & Heavy Construction Machinery":"農業・建設機械", "Conglomerates":"複合企業",
    "Medical Devices":"医療機器", "Drug Manufacturers - Specialty & Generic":"医薬品",
    "Biotechnology":"バイオテクノロジー", "Diagnostics & Research":"診断・研究サービス",
    "Telecom Services":"通信サービス", "Entertainment":"娯楽・コンテンツ",
    "Advertising Agencies":"広告", "Publishing":"出版", "Broadcasting":"放送",
    "Packaged Foods":"加工食品", "Beverages - Non-Alcoholic":"清涼飲料",
    "Beverages - Brewers":"酒類", "Household & Personal Products":"家庭用品・化粧品",
    "Grocery Stores":"食品小売", "Restaurants":"外食", "Apparel Retail":"衣料品小売",
    "Department Stores":"百貨店", "Specialty Retail":"専門小売",
    "Real Estate Services":"不動産サービス", "Real Estate - Development":"不動産開発",
    "REIT - Diversified":"総合不動産投資信託", "Oil & Gas Integrated":"総合石油・ガス",
    "Oil & Gas E&P":"石油・ガス開発", "Utilities - Regulated Electric":"電力",
    "Utilities - Regulated Gas":"ガス", "Airlines":"航空", "Railroads":"鉄道",
    "Marine Shipping":"海運", "Integrated Freight & Logistics":"物流",
  };
  const hasJapanese = (value) => /[ぁ-んァ-ヶ一-龠]/.test(String(value || ""));
  const sector = (value) => sectors[value] || (hasJapanese(value) ? value : "");
  const industry = (value) => industries[value] || (hasJapanese(value) ? value : "");
  const classification = (stock) => [sector(stock?.sector), industry(stock?.industry)].filter(Boolean).join("／") || "業種分類は企業IRで確認";
  const business = (stock) => {
    if (hasJapanese(stock?.business_summary)) return stock.business_summary;
    const label = classification(stock);
    return `${label}に属する企業です。具体的な事業内容、収益構成、主要顧客、競争優位性は会社の最新IR資料で確認してください。`;
  };
  globalThis.JapaneseLabels = {sector, industry, classification, business};
})();
