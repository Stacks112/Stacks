(function () {
  const root = document.querySelector("[data-recommendations]");
  if (!root) return;

  const article = {
    articleId: root.dataset.articleId || document.body.dataset.articleId || location.pathname,
    title: root.dataset.title || document.title,
    url: root.dataset.url || location.pathname,
    tickers: split(root.dataset.tickers || document.body.dataset.tickers || ""),
    tags: split(root.dataset.tags || document.body.dataset.tags || ""),
    publishedAt: root.dataset.publishedAt || document.body.dataset.publishedAt || "",
  };

  const previousArticleId = localStorage.getItem("stacks:lastArticleId") || "";
  localStorage.setItem("stacks:lastArticleId", article.articleId);

  recordView(article, previousArticleId);
  loadRecommendations(root, article);

  async function recordView(currentArticle, refArticleId) {
    try {
      await fetch("/api/article-view", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...currentArticle, refArticleId }),
        keepalive: true,
      });
    } catch {
      // Recommendation tracking should never block article reading.
    }
  }

  async function loadRecommendations(container, currentArticle) {
    const params = new URLSearchParams({
      articleId: currentArticle.articleId,
      tickers: currentArticle.tickers.join(","),
      tags: currentArticle.tags.join(","),
      limit: "12",
    });

    try {
      const response = await fetch(`/api/recommendations?${params.toString()}`);
      if (!response.ok) return;

      const data = await response.json();
      const sections = Array.isArray(data.sections) ? data.sections : [];
      if (sections.length === 0) return;

      container.innerHTML = sections.map(renderSection).join("");
      container.hidden = false;
    } catch {
      container.hidden = true;
    }
  }

  function renderSection(section) {
    return `
      <section class="recommendation-section" aria-labelledby="rec-${escapeAttr(section.id)}">
        <h2 id="rec-${escapeAttr(section.id)}">${escapeHtml(section.title)}</h2>
        <ol class="recommendation-list">
          ${section.items.map(renderItem).join("")}
        </ol>
      </section>
    `;
  }

  function renderItem(item) {
    return `
      <li>
        <a href="${escapeAttr(item.url)}">
          <span>${escapeHtml(item.title)}</span>
          ${item.publishedAt ? `<time datetime="${escapeAttr(item.publishedAt)}">${formatDate(item.publishedAt)}</time>` : ""}
        </a>
      </li>
    `;
  }

  function split(value) {
    return String(value)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function formatDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleDateString("ko-KR", { month: "short", day: "numeric" });
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttr(value) {
    return escapeHtml(value).replace(/`/g, "&#096;");
  }
})();
