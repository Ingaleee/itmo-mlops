"use strict";
const $ = (id) => document.getElementById(id);
const state = { path: null, controller: null };
function element(tag, text, className) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (className) el.className = className;
  return el;
}
function docURL(doc, anchor) {
  return `/docs/${encodeURIComponent(doc.id)}/${encodeURIComponent(doc.version)}${anchor ? "#" + encodeURIComponent(anchor) : ""}`;
}
async function api(path, body, signal) {
  const response = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });
  if (response.status === 401) {
    $("workspace").hidden = true;
    $("login-panel").hidden = false;
    throw Error("Введите токен доступа");
  }
  const data = await response.json();
  if (!response.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Не удалось выполнить запрос",
    );
  return data;
}
function statuses() {
  const result = ["Действует"];
  if ($("archive").checked) result.push("Архив");
  if ($("draft").checked) result.push("Черновик");
  return result;
}
function sourceLink(doc, anchor, text) {
  const link = element("a", text, "source-link");
  link.href = docURL(doc, anchor);
  return link;
}
function cards(snapshot) {
  $("results").replaceChildren();
  $("empty-state").hidden = true;
  $("results-heading").hidden = false;
  $("result-count").textContent = `${snapshot.cards.length} / 5`;
  for (const card of snapshot.cards) {
    const box = element("section", undefined, "card");
    box.append(
      element(
        "div",
        `${card.id} / ${card.version}   ·   ${card.status}   ·   ${card.path.join(" / ")}`,
        "card-meta",
      ),
    );
    const title = element("h3");
    const link = element("a", card.title);
    link.href = docURL(card, card.fragments[0]?.anchor);
    title.append(link);
    box.append(title);
    for (const fragment of card.fragments.slice(0, 2))
      box.append(element("p", fragment.text));
    $("results").append(box);
  }
  if (!snapshot.cards.length)
    $("results").append(
      element(
        "p",
        "По выбранным условиям документы не найдены. Измените вопрос или фильтры.",
      ),
    );
}
async function run(ask) {
  if (!$("search-form").reportValidity()) return;
  state.controller?.abort();
  state.controller = new AbortController();
  $("status").textContent = ask
    ? "Ищем источники и готовим ответ…"
    : "Ищем документы…";
  $("answer-panel").hidden = true;
  try {
    const body = {
      query: $("question").value,
      limit: 5,
      statuses: statuses(),
      private: $("private").checked,
    };
    if (state.path) body.path = state.path;
    const data = await api(
      ask ? "/api/ask" : "/api/search",
      body,
      state.controller.signal,
    );
    cards(data);
    $("status").textContent = "";
    if (ask) {
      $("answer-panel").hidden = false;
      $("mode").textContent = {
        cloud: "Облачная модель",
        local: "Локальная модель",
        search_only: "Только документы",
      }[data.mode];
      $("answer").textContent =
        data.answer ||
        "Проверенный ответ модели недоступен. Используйте найденные документы и выдержки ниже.";
      $("source-map").replaceChildren(
        ...data.sources.map((s) =>
          sourceLink(
            s,
            s.anchor,
            `[${s.number}] ${s.id} · ${s.version} · ${s.status}`,
          ),
        ),
      );
      $("diagnostics").textContent = JSON.stringify(
        {
          request_id: data.request_id,
          route: data.mode,
          reason: data.reason,
          generation: data.generation,
          context_sha256: data.context_sha256,
          prompt_tokens: data.prompt_tokens,
          latency_ms: data.latency_ms,
        },
        null,
        2,
      );
    }
  } catch (error) {
    if (error.name !== "AbortError") $("status").textContent = error.message;
  }
}
async function load() {
  try {
    const tree = await api("/api/tree");
    $("login-panel").hidden = true;
    $("workspace").hidden = false;
    $("status").textContent = "";
    let count = 0;
    $("tree").replaceChildren();
    for (const section of tree.sections) {
      const detail = element("details");
      detail.append(element("summary", section.title));
      for (const sub of section.subsections) {
        const group = element("div", undefined, "subsection");
        const filter = element("button", sub.title);
        filter.onclick = () => {
          state.path = [section.id, sub.id];
          $("path-filter").textContent = state.path.join(" / ");
        };
        group.append(filter);
        for (const doc of sub.documents) {
          count++;
          const a = element(
            "a",
            `${doc.id} · ${doc.version} — ${doc.title}${doc.status === "Действует" ? "" : " [" + doc.status + "]"}`,
          );
          a.href = docURL(doc);
          group.append(a);
        }
        detail.append(group);
      }
      $("tree").append(detail);
    }
    $("document-count").textContent = count;
    const match = location.pathname.match(/^\/docs\/([^/]+)\/([^/]+)$/);
    if (match) {
      const doc = await api(`/api/docs/${match[1]}/${match[2]}`);
      $("search-view").hidden = true;
      $("document-view").hidden = false;
      $("document-title").textContent = doc.title;
      $("document-meta").textContent =
        `${doc.id} / ${doc.version} · ${doc.status} · ${doc.path.join(" / ")}`;
      for (const sec of doc.sections) {
        const block = element("section");
        block.id = sec.anchor;
        block.append(
          element("h2", sec.title),
          ...sec.body.map((p) => element("p", p)),
        );
        $("document-body").append(block);
      }
      if (doc.links.length) {
        $("document-links").append(element("h2", "Связанные документы"));
        for (const pair of doc.links) {
          const m = pair.match(/^([A-Z]-\d{2})@(\d+\.\d+)(?:#(s\d{2}))?$/);
          if (m)
            $("document-links").append(
              sourceLink({ id: m[1], version: m[2] }, m[3], pair),
            );
        }
      }
      if (location.hash)
        document
          .getElementById(decodeURIComponent(location.hash.slice(1)))
          ?.scrollIntoView();
    }
  } catch (error) {
    $("status").textContent = error.message;
  }
}
$("login-form").onsubmit = async (event) => {
  event.preventDefault();
  try {
    await api("/api/login", { token: $("token").value });
    $("token").value = "";
    await load();
  } catch (error) {
    alert(error.message);
  }
};
$("search-form").onsubmit = (event) => {
  event.preventDefault();
  run(false);
};
$("ask").onclick = () => run(true);
$("all-documents").onclick = () => {
  state.path = null;
  $("path-filter").textContent = "Все разделы";
};
$("logout").onclick = async () => {
  await api("/api/logout", {});
  location.assign("/");
};
for (const button of document.querySelectorAll("[data-question]"))
  button.onclick = () => {
    $("question").value = button.dataset.question;
    run(false);
  };
load();
