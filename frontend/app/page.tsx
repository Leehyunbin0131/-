import { StartTrialButton } from "@/components/landing/StartTrialButton";

export default function HomePage() {
  return (
    <main className="landingShell">
      <section className="landingPanel">
        <div className="landingEyebrow">Admissions Recommendation</div>
        <h1 className="landingTitle">
          성적과 조건에 맞는
          <br />
          대학 · 학과 · 전형 추천
        </h1>
        <p className="landingBody">
          관심 분야, 내신/수능, 희망 지역, 기숙사 여부를 입력하면 실제 모집결과를
          우선 읽고 합격 가능성이 더 높아 보이는 대학·학과·전형 조합을 정리합니다.
          기숙사와 등록금 같은 생활 정보는 공식 안내 기준으로 함께 보강합니다.
        </p>
        <div className="landingMeta">
          <span className="metaPill">모집결과 file inputs</span>
          <span className="metaPill">전형 추천 포함</span>
          <span className="metaPill">기숙사/등록금 웹 보강</span>
        </div>
        <StartTrialButton />
      </section>
    </main>
  );
}
