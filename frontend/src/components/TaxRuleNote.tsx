// Official basis for how invoice tax is rounded, so anyone can verify it.
export const TAX_ROUNDING_REFERENCE_URL =
  "https://www.nta.go.jp/taxes/shiraberu/zeimokubetsu/shohi/keigenzeiritsu/pdf/qa/57.pdf";

export default function TaxRuleNote({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs text-slate-500 ${className}`}>
      消費税額の端数処理は、請求書1枚につき税率ごとに1回（消令70の10、基通1-8-15）。方法（切上げ・切捨て・四捨五入）は任意。
      明細行ごとの税額は参考値です。{" "}
      <a href={TAX_ROUNDING_REFERENCE_URL} target="_blank" rel="noopener noreferrer" className="text-brand underline">
        国税庁 Q&amp;A（適格請求書等保存方式）
      </a>
    </p>
  );
}
