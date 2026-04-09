import Link from "next/link";

export default function CheckoutSuccessPage() {
  return (
    <main className="pageShell">
      <div className="centerColumn">
        <div className="summarySection">
          <div className="summaryTitle">결제 완료</div>
          <h1 className="summaryBlockTitle">이제 상담을 계속 이어갈 수 있습니다.</h1>
          <p style={{ lineHeight: 1.8 }}>
            결제가 확인되면 추가 30턴이 반영됩니다. 아래 버튼으로 다시 상담
            화면으로 돌아가 주세요.
          </p>
          <div className="inlineRow" style={{ marginTop: 18 }}>
            <Link className="primaryButton" href="/">
              홈으로
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
