import Link from "next/link";

export default function CheckoutCancelPage() {
  return (
    <main className="pageShell">
      <div className="centerColumn">
        <div className="summarySection">
          <div className="summaryTitle">결제 취소</div>
          <h1 className="summaryBlockTitle">원할 때 다시 이어갈 수 있습니다.</h1>
          <p style={{ lineHeight: 1.8 }}>
            지금까지의 상담 맥락은 유지됩니다. 준비가 되면 다시 결제를 진행해
            계속 상담받을 수 있어요.
          </p>
          <div className="inlineRow" style={{ marginTop: 18 }}>
            <Link className="secondaryButton" href="/">
              홈으로
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
