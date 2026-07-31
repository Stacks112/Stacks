import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const sections = [
  {
    id: "ticker-samsung-electronics",
    title: "삼성전자 최신 글",
    items: [
      ["사상 최대 실적을 낸 삼성전자가 메모리 생산능력의 60~70%를 5년 계약에 묶는 이유는?", "2026-07-30"],
      ["삼성전자가 새 공장 없이 화성 재배치만으로 D램 15%를 늘리는 속사정", "2026-07-27"],
      ["HBM 선두는 SK하이닉스인데, 삼성은 왜 2나노 파운드리 공정을 승부수로 꺼냈을까?", "2026-07-27"],
    ],
  },
  {
    id: "ticker-broadcom",
    title: "브로드컴 최신 글",
    items: [
      ["연 매출의 2%도 안 되는 사업의 전망을 올린 것이 왜 광통신 전환의 신호로 읽힐까?", "2026-07-30"],
      ["Broadcom AI ASIC 매출을 NVIDIA와 같이 봐야 하는 이유", "2026-07-28"],
      ["브로드컴의 맞춤형 칩 매출을 데이터센터 사이클과 같이 봐야 하는 이유", "2026-07-24"],
    ],
  },
];

function App() {
  return (
    <>
      <header className="topbar">
        <a className="brand" href="/">Stacks</a>
        <span>추천 기능 임시 데모</span>
      </header>

      <main>
        <article className="article">
          <p className="eyebrow">AI Infrastructure</p>
          <h1>NVIDIA 데이터센터 수요가 다시 투자자의 기준점이 되는 이유</h1>
          <p className="dek">
            이 페이지는 운영 사이트가 아니라, 글 하단 추천 영역이 어떻게 보이는지 확인하기 위한 임시 데모입니다.
          </p>

          <div className="meta">
            <span>NVIDIA</span>
            <span>AI 인프라</span>
            <time dateTime="2026-07-31">2026.07.31</time>
          </div>

          <section className="article-body">
            <p>
              AI 인프라 투자의 핵심은 단일 칩 판매량보다 데이터센터 증설 속도, 전력 병목,
              네트워크 장비 투자, 그리고 주요 클라우드 사업자의 자본 지출 흐름을 함께 보는 데 있습니다.
            </p>
            <p>
              NVIDIA를 읽은 사용자는 자연스럽게 AMD, TSMC, HBM, 전력 인프라, 데이터센터 리츠 같은 주변 주제로 이동합니다.
              추천 기능은 이 흐름을 글 하단에서 바로 이어주기 위해 설계했습니다.
            </p>
            <p>
              아래 추천 영역은 실제 구현 목표와 같은 구조입니다. 글에 붙은 종목을 기준으로
              삼성전자와 브로드컴 최신 글을 나눠 보여줍니다.
            </p>
          </section>

          <aside className="recommendations" aria-label="추천 글">
            {sections.map((section) => (
              <RecommendationSection key={section.id} section={section} />
            ))}
          </aside>
        </article>
      </main>
    </>
  );
}

function RecommendationSection({ section }) {
  return (
    <section className="recommendation-section" aria-labelledby={`rec-${section.id}`}>
      <h2 id={`rec-${section.id}`}>{section.title}</h2>
      <ol className="recommendation-list">
        {section.items.map(([title, date]) => (
          <li key={title}>
            <a href="/">
              <span>{title}</span>
              <time dateTime={date}>{formatDate(date)}</time>
            </a>
          </li>
        ))}
      </ol>
    </section>
  );
}

function formatDate(value) {
  return new Date(value).toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
}

createRoot(document.getElementById("root")).render(<App />);
