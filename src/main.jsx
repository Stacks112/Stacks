import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

const sections = [
  {
    id: "same-ticker",
    title: "NVIDIA 관련 최신 글 12개",
    items: [
      ["NVIDIA Blackwell 공급 지연보다 중요한 데이터센터 발주 흐름", "2026-07-30"],
      ["NVDA 실적에서 확인해야 할 세 가지 숫자", "2026-07-29"],
      ["클라우드 3사의 GPU 투자 경쟁은 언제까지 이어질까", "2026-07-28"],
      ["NVIDIA 마진보다 전력 인프라가 먼저 흔들릴 수 있다", "2026-07-27"],
    ],
  },
  {
    id: "same-theme",
    title: "AI 인프라 테마에서 많이 읽은 글",
    items: [
      ["TSMC CoWoS 증설이 AI 서버 공급망에 주는 신호", "2026-07-30"],
      ["HBM 가격이 메모리 업황을 다시 바꾸는 방식", "2026-07-26"],
      ["데이터센터 전력 병목과 전력기기주의 연결고리", "2026-07-25"],
      ["AI 서버 랙 밀도가 높아질수록 커지는 냉각 투자", "2026-07-24"],
    ],
  },
  {
    id: "co-read",
    title: "이 글을 읽은 사람들이 함께 본 글",
    items: [
      ["함께 많이 읽은 AMD 글: MI 시리즈가 가져갈 수 있는 시장", "2026-07-29"],
      ["Broadcom AI ASIC 매출을 NVIDIA와 같이 봐야 하는 이유", "2026-07-28"],
      ["Arista Networks가 AI 네트워크 투자에서 받는 수혜", "2026-07-23"],
      ["전력망 증설 사이클에서 봐야 할 미국 인프라 기업", "2026-07-22"],
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
              아래 추천 영역은 실제 구현 목표와 같은 구조입니다. 첫 번째는 같은 종목 최신 글,
              두 번째는 같은 테마 인기 글, 세 번째는 함께 읽은 글입니다.
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
