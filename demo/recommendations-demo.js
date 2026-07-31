(function () {
  const root = document.querySelector("[data-recommendations]");
  if (!root) return;

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

  root.innerHTML = sections.map(renderSection).join("");

  function renderSection(section) {
    return `
      <section class="recommendation-section" aria-labelledby="rec-${section.id}">
        <h2 id="rec-${section.id}">${section.title}</h2>
        <ol class="recommendation-list">
          ${section.items.map(renderItem).join("")}
        </ol>
      </section>
    `;
  }

  function renderItem(item) {
    return `
      <li>
        <a href="#">
          <span>${item[0]}</span>
          <time datetime="${item[1]}">${formatDate(item[1])}</time>
        </a>
      </li>
    `;
  }

  function formatDate(value) {
    const date = new Date(value);
    return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  }
})();
