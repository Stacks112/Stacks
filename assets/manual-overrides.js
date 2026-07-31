(function () {
  const slug = getSlug();
  if (!slug) return;

  fetch(`/assets/manual-overrides/${encodeURIComponent(slug)}.json`, {
    cache: "no-store",
    headers: { "accept": "application/json" },
  })
    .then((response) => response.ok ? response.json() : null)
    .then((data) => {
      const post = data && (data.post || data);
      if (!post || post.status === "archived") return;
      applyOverride(post);
    })
    .catch(() => {
      // Manual edits should never block article reading.
    });

  function applyOverride(post) {
    const title = document.querySelector("h1");
    if (title && post.title) {
      title.textContent = post.title;
      document.title = document.title.replace(/^.*?(?= · Stacks$)/, post.title);
    }

    const bodyHtml = sanitizeHtml(post.bodyHtml || "");
    if (!bodyHtml) return;

    const start = findBodyStart();
    if (!start) return;

    const end = findBodyEnd(start);
    const wrapper = document.createElement("div");
    wrapper.className = "stacks-manual-override";
    wrapper.innerHTML = bodyHtml;

    const parent = start.parentNode;
    let node = start;
    while (node && node !== end) {
      const next = node.nextSibling;
      parent.removeChild(node);
      node = next;
    }
    parent.insertBefore(wrapper, end || null);
  }

  function findBodyStart() {
    const h1 = document.querySelector("h1");
    if (!h1) return null;

    const selectors = [
      ".srcq",
      ".gist",
      ".gcardw",
      ".gref",
      ".chk",
      ".gimg",
      ".gsub",
    ];

    let node = h1.nextSibling;
    while (node) {
      if (node.nodeType === 1 && selectors.some((selector) => node.matches(selector))) {
        return node;
      }
      node = node.nextSibling;
    }
    return null;
  }

  function findBodyEnd(start) {
    const selectors = [".sum3", ".rec-s", ".ent-chips", "footer"];
    let node = start.nextSibling;
    while (node) {
      if (node.nodeType === 1 && selectors.some((selector) => node.matches(selector))) {
        return node;
      }
      node = node.nextSibling;
    }
    return null;
  }

  function getSlug() {
    const explicit = document.body.dataset.articleId || document.querySelector("[data-article-id]")?.dataset.articleId;
    if (explicit) return cleanSlug(explicit);

    const canonical = document.querySelector('link[rel="canonical"]')?.href || location.href;
    try {
      const url = new URL(canonical, location.href);
      const name = url.pathname.split("/").pop() || "";
      return cleanSlug(name.replace(/\.html$/i, ""));
    } catch {
      return "";
    }
  }

  function sanitizeHtml(value) {
    const template = document.createElement("template");
    template.innerHTML = String(value || "");

    for (const node of template.content.querySelectorAll("script,iframe,object,embed,link,meta")) {
      node.remove();
    }

    for (const node of template.content.querySelectorAll("*")) {
      for (const attr of [...node.attributes]) {
        const name = attr.name.toLowerCase();
        const text = String(attr.value || "").trim().toLowerCase();
        if (name.startsWith("on") || text.startsWith("javascript:")) {
          node.removeAttribute(attr.name);
        }
      }
    }

    return template.innerHTML.trim();
  }

  function cleanSlug(value) {
    return String(value || "")
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 120);
  }
})();
