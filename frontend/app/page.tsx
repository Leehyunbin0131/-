import { StartTrialButton } from "@/components/landing/StartTrialButton";

export default function HomePage() {
  return (
    <main className="landingShell">
      <section className="landingPanel">
        <div className="landingEyebrow">Career Counsel</div>
        <h1 className="landingTitle">
          진학과 취업 고민에
          <br />
          조용히 집중하는 상담 화면
        </h1>
        <p className="landingBody">
          복잡한 대시보드 대신, 지금 당신의 고민을 차분히 묻고 정리하는 상담
          경험에 집중했습니다. 무료 체험으로 먼저 상담을 시작하고, 필요할 때만
          이어서 결제할 수 있습니다.
        </p>
        <div className="landingMeta">
          <span className="metaPill">무료 체험 5회</span>
          <span className="metaPill">결제 후 30회 추가</span>
          <span className="metaPill">통계 근거 기반</span>
        </div>
        <StartTrialButton />
      </section>
    </main>
  );
}
