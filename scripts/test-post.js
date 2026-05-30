#!/usr/bin/env node
/** End-to-end API test (run inside n8n container): node /tmp/test-post.js */
const https = require("https");

function fetch(url, options = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url);
    const req = https.request(
      {
        hostname: u.hostname,
        path: u.pathname + u.search,
        method: options.method || "GET",
        headers: options.headers || {},
      },
      (res) => {
        let data = "";
        res.on("data", (chunk) => (data += chunk));
        res.on("end", () => {
          try {
            resolve(JSON.parse(data));
          } catch {
            resolve({ raw: data });
          }
        });
      }
    );
    req.on("error", reject);
    if (options.body) req.write(options.body);
    req.end();
  });
}

const NEWS_HEADERS = {
  "X-Api-Key": process.env.NEWSAPI_KEY,
  "User-Agent": "FacebookUSNewsBot/1.0 (test-script; contact=bigdevelopers6@gmail.com)",
};

async function llmCaption(title, description) {
  const system =
    "Write a short Facebook caption with 2 hashtags and 1 emoji. Output only the caption.";
  const user = `Title: ${title}\nDescription: ${description || ""}`;
  const providers = [
    async () => {
      const key = process.env.ANTHROPIC_API_KEY;
      if (!key) throw new Error("no anthropic key");
      return fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": key,
          "anthropic-version": "2023-06-01",
          "content-type": "application/json",
        },
        body: JSON.stringify({
          model: "claude-haiku-4-5-20251001",
          max_tokens: 300,
          system,
          messages: [{ role: "user", content: user }],
        }),
      }).then((r) => {
        if (r.content?.[0]?.text) return { provider: "anthropic", text: r.content[0].text };
        throw new Error(JSON.stringify(r).slice(0, 200));
      });
    },
    async () => {
      const key = process.env.GROQ_API_KEY;
      const model = (process.env.GROQ_MODEL || "llama-3.1-8b-instant").trim();
      if (!key) throw new Error("no groq key");
      return fetch("https://api.groq.com/openai/v1/chat/completions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${key}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          max_tokens: 300,
          messages: [
            { role: "system", content: system },
            { role: "user", content: user },
          ],
        }),
      }).then((r) => {
        const t = r.choices?.[0]?.message?.content;
        if (t) return { provider: "groq", text: t };
        throw new Error(JSON.stringify(r).slice(0, 200));
      });
    },
    async () => {
      const key = process.env.GEMINI_API_KEY;
      const model = (process.env.GEMINI_MODEL || "gemini-1.5-flash").split(",")[0].trim();
      if (!key) throw new Error("no gemini key");
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${key}`;
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          systemInstruction: { parts: [{ text: system }] },
          contents: [{ role: "user", parts: [{ text: user }] }],
          generationConfig: { maxOutputTokens: 300 },
        }),
      }).then((r) => {
        const t = r.candidates?.[0]?.content?.parts?.[0]?.text;
        if (t) return { provider: "gemini", text: t };
        throw new Error(JSON.stringify(r).slice(0, 200));
      });
    },
  ];
  const errors = [];
  for (const fn of providers) {
    try {
      return await fn();
    } catch (e) {
      errors.push(e.message);
    }
  }
  throw new Error("All LLMs failed: " + errors.join("; "));
}

async function main() {
  const FB_TOKEN = process.env.FB_ACCESS_TOKEN;
  const FB_PAGE = process.env.FB_PAGE_ID;

  console.log("=== Step 1: NewsAPI ===");
  const news = await fetch(
    "https://newsapi.org/v2/top-headlines?country=us&category=entertainment&pageSize=5",
    { headers: NEWS_HEADERS }
  );
  if (news.status !== "ok") {
    console.log("FAILED:", JSON.stringify(news).slice(0, 500));
    process.exit(1);
  }
  console.log("OK —", news.articles?.length, "articles");

  const article = news.articles.find(
    (a) => a.title && a.urlToImage && a.title !== "[Removed]"
  );
  if (!article) {
    console.log("FAILED: no article with image");
    process.exit(1);
  }
  console.log("Selected:", article.title);

  console.log("\n=== Step 2: Caption (Claude → Groq → Gemini) ===");
  let caption, provider;
  try {
    const cap = await llmCaption(article.title, article.description);
    caption = cap.text;
    provider = cap.provider;
  } catch (e) {
    console.log("FAILED:", e.message);
    console.log("STOP: All caption providers failed — run: docker compose down");
    process.exit(1);
  }
  console.log(`OK (${provider}) —`, caption);

  console.log("\n=== Step 3: Facebook post ===");
  const postBody =
    "url=" +
    encodeURIComponent(article.urlToImage) +
    "&message=" +
    encodeURIComponent(caption) +
    "&access_token=" +
    FB_TOKEN;

  const fbResp = await fetch(
    "https://graph.facebook.com/v19.0/" + FB_PAGE + "/photos",
    {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: postBody,
    }
  );

  if (fbResp.id || fbResp.post_id) {
    console.log("\n=== SUCCESS ===");
    console.log("Post ID:", fbResp.id || fbResp.post_id);
    console.log("Page: https://www.facebook.com/" + FB_PAGE);
  } else {
    console.log("FAILED:", JSON.stringify(fbResp).slice(0, 500));
    process.exit(1);
  }
}

main().catch((e) => {
  console.error("CRASH:", e.message);
  process.exit(1);
});
