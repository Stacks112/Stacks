(function () {
  const root = document.querySelector("[data-recommendations]");
  if (!root) return;

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
