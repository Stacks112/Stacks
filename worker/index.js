import { handleManualEditRequest } from "./manual-edits.js";
import { handleRecommendationRequest } from "./recommendations.js";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api/manual-post") {
      return handleManualEditRequest(request, env);
    }

    if (url.pathname === "/api/article-view" || url.pathname === "/api/recommendations") {
      return handleRecommendationRequest(request, env);
    }

    return new Response("Not found", { status: 404 });
  },
};
