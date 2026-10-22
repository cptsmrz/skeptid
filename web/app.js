(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var MOCK = params.get("mock") === "1";
  var FIXTURE_OVERRIDE = params.get("fixture");
  var fixtures = window.SKEPTID_FIXTURES || {};
  var samples = window.SKEPTID_SAMPLES || {};
  var offsets = window.SKEPTID_OFFSETS || {};

  var NAMES = {
    own: "SKEPTID model",
    opensource: "Open-source model",
    external: "External service"
  };

  var MSG_EXAMPLES = [
    { key: "low", label: "Safe message" },
    { key: "email", label: "Phishing email" },
    { key: "high", label: "Threat" },
    { key: "disagree", label: "Providers disagree" },
    { key: "partial", label: "One provider down" },
    { key: "fail", label: "All providers down" }
  ];

  var SPAN_PHRASES = {
    high: [
      { needle: "Urgent: verify your account now", description: "Urgency + credential request", weight: 0.31 },
      { needle: "confirm your password", description: "Password confirmation request", weight: 0.28 }
    ],
    medium: [
      { needle: "Reply STOP", description: "Opt-out mailing language", weight: 0.22 }
    ],
    disagree: [
      { needle: "payment link", description: "Credential-trap payment link", weight: 0.29 }
    ],
    email: [
      { needle: "attached invoice", description: "Urgency around an attached invoice", weight: 0.24 },
      { needle: "payment page", description: "Payment-page instruction", weight: 0.19 }
    ]
  };

  var message = { text: "", file: null, verdict: null, history: [], objectUrl: "" };
  var media = { file: null, pendingName: "", verdict: null, history: [], objectUrl: "" };

  var els = {
    html: document.documentElement,
    mockChip: document.getElementById("mock-chip"),
    theme: document.getElementById("theme-toggle"),
    navDesk: document.getElementById("nav-desk"),
    navRecords: document.getElementById("nav-records"),
    viewDesk: document.getElementById("view-desk"),
    viewRecords: document.getElementById("view-records"),
    recordsBody: document.getElementById("records-body"),
    msgLane: document.getElementById("message-lane"),
    msgTray: document.getElementById("message-tray"),
    msgInput: document.getElementById("message-input"),
    msgChoose: document.getElementById("message-choose"),
    msgFile: document.getElementById("message-file"),
    msgName: document.getElementById("message-filename"),
    msgAnalyze: document.getElementById("message-analyze"),
    msgExamples: document.getElementById("message-examples"),
    msgStep: document.getElementById("message-step"),
    msgFail: document.getElementById("message-fail"),
    msgResult: document.getElementById("message-result"),
    msgHistory: document.getElementById("message-history"),
    msgHistoryWrap: document.getElementById("message-history-wrap"),
    mediaLane: document.getElementById("media-lane"),
    mediaTray: document.getElementById("media-tray"),
    mediaChoose: document.getElementById("media-choose"),
    mediaFile: document.getElementById("media-file"),
    mediaName: document.getElementById("media-filename"),
    mediaAnalyze: document.getElementById("media-analyze"),
    mediaExamples: document.getElementById("media-examples"),
    mediaStep: document.getElementById("media-step"),
    mediaFail: document.getElementById("media-fail"),
    mediaResult: document.getElementById("media-result"),
    mediaHistory: document.getElementById("media-history"),
    mediaHistoryWrap: document.getElementById("media-history-wrap")
  };

  var MSG_STEPS = ["Checking body text", "Checking headers", "Scoring spans", "Collecting provider results"];
  var MEDIA_STEPS = ["Reading file", "Scoring frames", "Building forensic anomaly map", "Collecting provider results"];

  function caseRef(id) {
    if (!id) return "";
    return "SKP-" + String(id).replace(/-/g, "").slice(0, 6);
  }

  function reduceMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function applyTheme(theme) {
    els.html.setAttribute("data-theme", theme);
    document.body.classList.toggle("theme-dark", theme === "dark");
    els.theme.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
    els.theme.textContent = theme === "dark" ? "Paper" : "Graphite";
    try { localStorage.setItem("skeptid-theme", theme); } catch (e) { /* ignore */ }
  }

  function initTheme() {
    var stored = null;
    try { stored = localStorage.getItem("skeptid-theme"); } catch (e) { stored = null; }
    if (stored === "dark" || stored === "light") {
      applyTheme(stored);
      return;
    }
    applyTheme(window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }

  function setLaneMode(laneEl, resultEl, mode) {
    laneEl.classList.toggle("is-empty", mode === "empty");
    laneEl.classList.toggle("is-loading", mode === "loading");
    laneEl.classList.toggle("is-fail", mode === "fail");
    if (resultEl) resultEl.classList.toggle("is-open", mode === "result");
  }

  function clone(obj) {
    return JSON.parse(JSON.stringify(obj));
  }

  function pickFixtureKey(text, filename, lane) {
    if (FIXTURE_OVERRIDE && fixtures[FIXTURE_OVERRIDE]) return FIXTURE_OVERRIDE;
    var name = (filename || "").toLowerCase();
    var body = (text || "").toLowerCase();
    if (lane === "media") {
      if (/\.(mp4|webm|mov)$/.test(name) || name.indexOf("video") !== -1) return "video";
      return "image";
    }
    if (name.indexOf("fail") !== -1 || body.indexOf("force_provider_failure") !== -1) return "fail";
    if (name.indexOf("invoice") !== -1 || /\.eml$/.test(name) || body.indexOf("attached invoice") !== -1) return "email";
    if (name.indexOf("partial") !== -1 || body.indexOf("header path is incomplete") !== -1) return "partial";
    if (name.indexOf("disagree") !== -1 || body.indexOf("second scan flagged") !== -1) return "disagree";
    if (name.indexOf("high") !== -1 || body.indexOf("confirm your password") !== -1) return "high";
    if (name.indexOf("medium") !== -1 || body.indexOf("reply stop") !== -1) return "medium";
    if (name.indexOf("low") !== -1 || body.indexOf("no password or account action") !== -1) return "low";
    return "low";
  }

  function alignMockSpans(verdict, text, key) {
    if (!verdict || !verdict.evidence) return verdict;
    if (verdict.level === "LOW") {
      verdict.evidence = verdict.evidence.filter(function (ev) { return ev.kind !== "span"; });
      return verdict;
    }
    var phrases = SPAN_PHRASES[key] || [];
    var kept = verdict.evidence.filter(function (ev) { return ev.kind !== "span"; });
    phrases.forEach(function (ph) {
      var found = offsets.findCodePointSpan ? offsets.findCodePointSpan(text, ph.needle) : null;
      if (!found) {
        found = offsets.findCodePointSpan ? offsets.findCodePointSpan(text, ph.needle.toLowerCase()) : null;
      }
      if (!found) return;
      kept.unshift({
        kind: "span",
        description: ph.description,
        payload: { start: found.start, end: found.end, weight: ph.weight }
      });
    });
    verdict.evidence = kept;
    return verdict;
  }

  function sleep(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  async function mockAnalyze(text, filename, lane) {
    await sleep(reduceMotion() ? 80 : 720);
    var key = pickFixtureKey(text, filename, lane);
    var fixture = fixtures[key];
    if (!fixture) return { ok: false, status: 500, body: { detail: "Mock fixture is missing." } };
    if (fixture.status) return { ok: false, status: fixture.status, body: { detail: fixture.detail } };
    var body = clone(fixture);
    if (lane !== "media") alignMockSpans(body, text, key);
    return { ok: true, status: 200, body: body };
  }

  async function liveAnalyze(path, options) {
    var res;
    try {
      res = await fetch(path, options);
    } catch (err) {
      return {
        ok: false,
        status: 0,
        body: {
          detail: "The desk could not reach the API. Serve this page from the SKEPTID server, or open it with ?mock=1."
        }
      };
    }
    var body = {};
    try { body = await res.json(); } catch (e) { body = { detail: "The server returned a non-JSON response." }; }
    return { ok: res.ok, status: res.status, body: body };
  }

  function errorCopy(status, body, kind) {
    var detail = body && body.detail ? String(body.detail) : "The analysis did not complete.";
    var next = kind === "media" ? "Choose another image or video, then analyse again." : "Paste another message, or try again.";
    if (status === 503) next = "No verdict was formed. Wait a moment, then analyse again. Nothing on this page is a substitute score.";
    else if (status === 429) next = "Wait until the rate window resets, then analyse again.";
    else if (status === 400 || status === 415) {
      next = kind === "media" ? "Use a JPEG, PNG, WebP image or an MP4/WebM video." : "Use pasted text, a .txt file, or a .eml file.";
    } else if (status === 0) next = "Open ?mock=1 for fixtures, or run the API on the same origin.";
    return { happened: detail, next: next };
  }

  function countOk(providers) {
    if (!Array.isArray(providers)) return { ok: 0, total: 0 };
    var ok = 0;
    providers.forEach(function (p) { if (p && p.ok === true) ok += 1; });
    return { ok: ok, total: providers.length };
  }

  function okRisks(providers) {
    return (providers || []).filter(function (p) {
      return p && p.ok === true && typeof p.risk === "number";
    });
  }

  function spreadOf(providers) {
    var risks = okRisks(providers).map(function (p) { return p.risk; });
    if (risks.length < 2) return null;
    var max = Math.max.apply(null, risks);
    var min = Math.min.apply(null, risks);
    return Math.round((max - min) * 100) / 100;
  }

  function agreementCopy(v) {
    var items = Array.isArray(v.providers) ? v.providers : [];
    var n = okRisks(items).length;
    var spread = spreadOf(items);
    var spreadBit = spread == null ? "" : ", spread " + spread;
    if (v.disagreement === true) {
      return (n === 1 ? "One provider answered" : n + " providers disagree") + spreadBit + ".";
    }
    if (n === 3) return "All three agree" + spreadBit + ".";
    if (n === 2) return "Two agree" + spreadBit + ".";
    if (n === 1) return "One provider answered.";
    return "No providers answered.";
  }

  function humanName(id) {
    return NAMES[id] || id || "";
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function showField(value) {
    if (value === null || value === undefined || value === "") return "";
    return escapeHtml(String(value));
  }

  function isUnvalidatedVersion(version) {
    if (version === null || version === undefined) return false;
    var lower = String(version).toLowerCase();
    return lower.indexOf("mock") !== -1 || lower.indexOf("heuristic") !== -1;
  }

  function collectSpans(text, evidence) {
    var spans = [];
    (evidence || []).forEach(function (ev) {
      if (!ev || ev.kind !== "span" || !ev.payload) return;
      var mapped = offsets.utf16RangeFromCodePoints
        ? offsets.utf16RangeFromCodePoints(text, ev.payload.start, ev.payload.end)
        : null;
      if (!mapped) return;
      spans.push({
        start: mapped.start,
        end: mapped.end,
        excerpt: mapped.excerpt,
        description: ev.description || "",
        weight: typeof ev.payload.weight === "number" ? ev.payload.weight : null
      });
    });
    spans.sort(function (a, b) { return a.start - b.start; });
    return spans;
  }

  function highlight(text, evidence, level) {
    if (!text) return "<p class=\"muted\">No source text is held for this case.</p>";
    if (level === "LOW") return "<p class=\"muted\">No strong indicators.</p>";
    var spans = collectSpans(text, evidence);
    if (!spans.length) return "<p class=\"muted\">No strong indicators.</p>";
    var html = "";
    var cursor = 0;
    var n = 1;
    spans.forEach(function (sp) {
      if (sp.start < cursor) return;
      html += escapeHtml(text.slice(cursor, sp.start));
      html += "<mark class=\"hl\" id=\"span-" + n + "\"><span class=\"span-mark\">" + n + "</span>" +
        escapeHtml(text.slice(sp.start, sp.end)) + "</mark>";
      cursor = sp.end;
      n += 1;
    });
    html += escapeHtml(text.slice(cursor));
    return "<p class=\"evidence-text\">" + html + "</p>";
  }

  function whyList(text, evidence, level) {
    if (level === "LOW") return "";
    var spans = collectSpans(text, evidence);
    if (!spans.length) return "";
    var html = "<h3>Why flagged</h3><ol class=\"why-list\">";
    spans.forEach(function (sp, i) {
      html += "<li><a href=\"#span-" + (i + 1) + "\" class=\"span-mark\">" + (i + 1) + "</a>";
      html += "<span>" + showField(sp.description) + "</span>";
      html += "<span class=\"num\">" + (sp.weight == null ? "" : sp.weight) + "</span></li>";
    });
    html += "</ol>";
    return html;
  }

  function urlsFrom(evidence) {
    return (evidence || []).filter(function (ev) { return ev && ev.payload && ev.payload.check === "url"; });
  }
  function headersFrom(evidence) {
    return (evidence || []).filter(function (ev) { return ev && ev.payload && ev.payload.check === "header"; });
  }
  function attachmentsFrom(evidence) {
    return (evidence || []).filter(function (ev) { return ev && ev.payload && ev.payload.check === "attachment"; });
  }
  function frameScores(evidence) {
    return (evidence || []).filter(function (ev) { return ev && ev.kind === "frame_score" && ev.payload; });
  }

  function renderModel(version) {
    var html = "<p class=\"provider-version\"><span class=\"muted\">Model</span> ";
    html += "<span class=\"mono\">" + showField(version) + "</span>";
    if (isUnvalidatedVersion(version)) html += " <span class=\"chip tag-plain\">not validated</span>";
    html += "</p>";
    return html;
  }

  function stripPlot(providers) {
    var ok = okRisks(providers);
    if (!ok.length) return "";
    var w = 320;
    var h = 56;
    var left = 12;
    var right = 12;
    var axisY = 28;
    var inner = w - left - right;
    function x(r) { return left + Math.max(0, Math.min(1, r)) * inner; }
    var svg = "<svg class=\"strip\" viewBox=\"0 0 " + w + " " + h + "\" role=\"img\" aria-label=\"Provider risks on a 0 to 1 axis\">";
    svg += "<line x1=\"" + left + "\" y1=\"" + axisY + "\" x2=\"" + (w - right) + "\" y2=\"" + axisY + "\" stroke=\"currentColor\" stroke-width=\"1\"/>";
    [0, 0.35, 0.7, 1].forEach(function (t) {
      var tx = x(t);
      svg += "<line x1=\"" + tx + "\" y1=\"" + (axisY - 6) + "\" x2=\"" + tx + "\" y2=\"" + (axisY + 6) + "\" stroke=\"currentColor\" stroke-width=\"1\"/>";
      svg += "<text x=\"" + tx + "\" y=\"" + (h - 6) + "\" text-anchor=\"middle\" font-size=\"10\" font-family=\"IBM Plex Mono, monospace\" fill=\"currentColor\">" + t + "</text>";
    });
    ok.forEach(function (p, i) {
      var cy = axisY - 10 + (i % 3) * 2;
      svg += "<circle cx=\"" + x(p.risk) + "\" cy=\"" + cy + "\" r=\"5\" fill=\"currentColor\"/>";
    });
    svg += "</svg>";
    return svg;
  }

  function renderProviders(v) {
    var items = Array.isArray(v.providers) ? v.providers : [];
    if (!items.length) return "";
    var html = "<div class=\"section\"><h3>Providers</h3>";
    html += "<p class=\"muted\">" + escapeHtml(agreementCopy(v)) + "</p>";
    html += stripPlot(items);
    html += "<div class=\"providers\">";
    items.forEach(function (p) {
      var unavailable = p.ok !== true;
      var shown = p.id === v.primary_provider;
      html += "<div class=\"provider" + (unavailable ? " unavailable" : "") + (shown ? " is-shown" : "") + "\">";
      html += "<div class=\"id\">" + showField(humanName(p.id)) + "</div>";
      if (shown) html += "<p class=\"caps\">Shown result</p>";
      if (unavailable) {
        html += "<p class=\"muted\">Unavailable" + (p.error ? " — " + showField(p.error) : "") + "</p>";
      } else if (typeof p.risk === "number") {
        html += "<p class=\"num\">" + p.risk + "</p>";
      }
      html += renderModel(p.model_version);
      if (typeof p.latency_ms === "number") html += "<p class=\"muted num\">" + p.latency_ms + " ms</p>";
      html += "</div>";
    });
    html += "</div></div>";
    return html;
  }

  function renderTables(v) {
    var html = "";
    var urls = urlsFrom(v.evidence);
    if (urls.length) {
      html += "<div class=\"section\"><h3>URL checks</h3><table><thead><tr><th>Display</th><th>Href</th><th>Issue</th></tr></thead><tbody>";
      urls.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td>" + showField(p.display) + "</td><td class=\"mono\">" + showField(p.href) + "</td><td>" + showField(p.issue || ev.description) + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    var headers = headersFrom(v.evidence);
    if (headers.length) {
      html += "<div class=\"section\"><h3>Header checks</h3><table><thead><tr><th>Field</th><th>Issue</th></tr></thead><tbody>";
      headers.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td class=\"mono\">" + showField(p.field) + "</td><td>" + showField(p.issue || ev.description) + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    var atts = attachmentsFrom(v.evidence);
    if (atts.length) {
      html += "<div class=\"section\"><h3>Attachments</h3><table><thead><tr><th>File</th><th>Type</th><th class=\"num\">Size</th><th class=\"num\">Risk</th><th></th></tr></thead><tbody>";
      atts.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td class=\"mono\">" + showField(p.filename) + "</td><td>" + showField(p.type) + "</td><td class=\"num\">" +
          (typeof p.size === "number" ? p.size : "") + "</td><td class=\"num\">" +
          (typeof p.risk === "number" ? p.risk : "") + "</td><td>" +
          "<button type=\"button\" class=\"ghost send-media\" data-filename=\"" + escapeHtml(p.filename || "") + "\">Send to Media intake</button></td></tr>";
      });
      html += "</tbody></table></div>";
    }
    return html;
  }

  function riskBar(v) {
    if (typeof v.risk !== "number") return "";
    var pct = Math.max(0, Math.min(100, v.risk * 100));
    return "<div class=\"risk-bar\" data-level=\"" + showField(v.level) + "\" aria-label=\"Risk " + v.risk + "\">" +
      "<div class=\"fill\" style=\"width:" + pct + "%\"></div>" +
      "<span class=\"tick\" style=\"left:35%\"></span><span class=\"tick-label\" style=\"left:35%\">0.35</span>" +
      "<span class=\"tick\" style=\"left:70%\"></span><span class=\"tick-label\" style=\"left:70%\">0.70</span></div>";
  }

  function feedbackBlock(lane, analysisId) {
    return "<div class=\"section feedback\" data-lane=\"" + lane + "\" data-id=\"" + escapeHtml(analysisId || "") + "\">" +
      "<h3>Feedback</h3>" +
      "<div class=\"row\">" +
      "<button type=\"button\" class=\"fb-ok\">Correct</button>" +
      "<button type=\"button\" class=\"fb-wrong ghost\">Wrong, it was…</button>" +
      "<label class=\"muted fb-label\" hidden>True label <input class=\"fb-true\" maxlength=\"40\"></label>" +
      "</div><p class=\"muted fb-status\" hidden></p></div>";
  }

  function summaryHead(v) {
    var html = "<div class=\"result-head\">";
    html += "<div><span class=\"verdict\" data-level=\"" + showField(v.level) + "\">" + showField(v.level) + "</span>";
    if (v.mock === true) html += " <span class=\"chip mock\">Mock</span>";
    html += "</div>";
    html += "<div class=\"meta\"><div class=\"caps\">" + caseRef(v.id) + "</div>";
    html += "<button type=\"button\" class=\"ghost copy-id\" data-id=\"" + escapeHtml(v.id || "") + "\">Copy id</button></div></div>";
    html += "<dl class=\"stats\">";
    html += "<div class=\"stat\"><dt>Risk</dt><dd class=\"num risk-value\">" + (typeof v.risk === "number" ? v.risk : "") + "</dd></div>";
    html += "<div class=\"stat\"><dt>Confidence</dt><dd class=\"num\">" + (typeof v.confidence === "number" ? v.confidence : "") + "</dd></div>";
    html += "<div class=\"stat\"><dt>Label</dt><dd>" + showField(v.label) + "</dd></div>";
    html += "</dl>";
    html += riskBar(v);
    if (v.limits_note) html += "<p class=\"chip\">" + showField(v.limits_note) + "</p>";
    return html;
  }

  function bindResultChrome(root, lane) {
    var copy = root.querySelector(".copy-id");
    if (copy) {
      copy.addEventListener("click", function () {
        var id = copy.getAttribute("data-id") || "";
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(id).then(function () {
            copy.textContent = "Copied";
            setTimeout(function () { copy.textContent = "Copy id"; }, 1200);
          });
        }
      });
    }
    root.querySelectorAll(".send-media").forEach(function (btn) {
      btn.addEventListener("click", function () {
        sendToMedia(btn.getAttribute("data-filename"));
      });
    });
    var fb = root.querySelector(".feedback");
    if (fb) bindFeedback(fb, lane);
  }

  function bindFeedback(node, lane) {
    var wrong = node.querySelector(".fb-wrong");
    var ok = node.querySelector(".fb-ok");
    var label = node.querySelector(".fb-label");
    var input = node.querySelector(".fb-true");
    var status = node.querySelector(".fb-status");
    function send(correct) {
      var payload = { analysis_id: node.getAttribute("data-id"), correct: correct };
      var trueLabel = input && input.value ? input.value.trim() : "";
      if (!correct && trueLabel) payload.true_label = trueLabel;
      postFeedback(payload, status);
    }
    ok.addEventListener("click", function () { send(true); });
    wrong.addEventListener("click", function () {
      if (label.hidden) {
        label.hidden = false;
        input.focus();
        return;
      }
      send(false);
    });
  }

  async function postFeedback(payload, statusEl) {
    statusEl.hidden = false;
    if (MOCK) {
      statusEl.textContent = "Recorded in this session. Mock mode does not write a registry.";
      return;
    }
    var res = await liveAnalyze("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok && res.body && res.body.status) {
      statusEl.textContent = showField(res.body.status);
    } else {
      statusEl.textContent = (res.body && res.body.detail) ? String(res.body.detail) : "Feedback was not stored.";
    }
  }

  function renderMessageResult(v, sourceText) {
    var html = "<div class=\"result-layout\">";
    html += "<div class=\"result-evidence\">";
    html += "<h3>Evidence</h3>" + highlight(sourceText, v.evidence, v.level);
    html += whyList(sourceText, v.evidence, v.level);
    html += renderTables(v);
    html += "</div>";
    html += "<div class=\"result-summary\">" + summaryHead(v) + renderProviders(v) + feedbackBlock("message", v.id) + "</div>";
    html += "</div>";
    els.msgResult.innerHTML = html;
    bindResultChrome(els.msgResult, "message");
    tickRisk(els.msgResult, v.risk);
  }

  function hashSeed(s) {
    var h = 2166136261;
    var str = String(s || "");
    for (var i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function drawHeatmap(canvas, seed) {
    var ctx = canvas.getContext("2d");
    var w = canvas.width;
    var h = canvas.height;
    var cols = 16;
    var rows = 12;
    var cw = w / cols;
    var ch = h / rows;
    var rnd = seed || 1;
    function next() {
      rnd = (rnd * 1664525 + 1013904223) >>> 0;
      return rnd / 4294967296;
    }
    ctx.clearRect(0, 0, w, h);
    for (var y = 0; y < rows; y++) {
      for (var x = 0; x < cols; x++) {
        var v = next();
        var a = v > 0.62 ? 0.55 : v > 0.4 ? 0.22 : 0.04;
        ctx.fillStyle = "rgba(179,54,30," + a + ")";
        ctx.fillRect(x * cw, y * ch, cw, ch);
      }
    }
  }

  function drawFrameThumb(canvas, index, score) {
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#d5cfc2";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#1b1a17";
    ctx.font = "12px IBM Plex Mono, monospace";
    ctx.fillText(String(index + 1), 8, 18);
    if (typeof score === "number") ctx.fillText(String(score), 8, 36);
    var bar = Math.max(0, Math.min(1, score || 0));
    ctx.fillStyle = "#b3361e";
    ctx.fillRect(0, canvas.height - 4, canvas.width * bar, 4);
  }

  function renderAnomalyMap(container, v, file) {
    var html = "<div class=\"section\"><h3>Forensic anomaly map</h3>";
    html += "<figure class=\"print\"><div class=\"print-stage\">";
    html += "<canvas class=\"base-canvas\" width=\"480\" height=\"320\"></canvas>";
    html += "<canvas class=\"overlay\" width=\"480\" height=\"320\"></canvas>";
    html += "</div><figcaption class=\"print-cap\"></figcaption></figure>";
    html += "<div class=\"opacity-row\"><label class=\"muted\" for=\"heat-opacity\">Overlay opacity</label>";
    html += "<input id=\"heat-opacity\" type=\"range\" min=\"0\" max=\"1\" step=\"0.05\" value=\"0.7\"></div></div>";
    container.insertAdjacentHTML("beforeend", html);
    var base = container.querySelector(".base-canvas");
    var overlay = container.querySelector(".overlay");
    var cap = container.querySelector(".print-cap");
    var range = container.querySelector("#heat-opacity");
    var seed = hashSeed(v.id);
    var bctx = base.getContext("2d");
    bctx.fillStyle = "#efebe3";
    bctx.fillRect(0, 0, base.width, base.height);
    function paintOverlay() {
      overlay.style.opacity = range.value;
    }
    range.addEventListener("input", paintOverlay);
    paintOverlay();
    drawHeatmap(overlay, seed);
    var name = file && file.name ? file.name : "media";
    var bits = [name];
    if (file && file.size) bits.push(String(file.size) + " bytes");
    cap.textContent = bits.join(" · ");
    if (file && /^image\//.test(file.type)) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () {
        bctx.fillStyle = "#1b1a17";
        bctx.fillRect(0, 0, base.width, base.height);
        var scale = Math.min(base.width / img.width, base.height / img.height);
        var dw = img.width * scale;
        var dh = img.height * scale;
        bctx.drawImage(img, (base.width - dw) / 2, (base.height - dh) / 2, dw, dh);
        URL.revokeObjectURL(url);
      };
      img.src = url;
    }
  }

  function renderVideoTimeline(container, v) {
    var frames = frameScores(v.evidence);
    if (!frames.length) return;
    var html = "<div class=\"section\"><h3>Frame strip</h3><div class=\"film\"></div>";
    html += "<h3>Risk timeline</h3><svg class=\"timeline\" viewBox=\"0 0 320 64\" role=\"img\" aria-label=\"Frame risk timeline\"></svg></div>";
    container.insertAdjacentHTML("beforeend", html);
    var film = container.querySelector(".film");
    frames.forEach(function (ev, i) {
      var btn = document.createElement("button");
      btn.type = "button";
      var c = document.createElement("canvas");
      c.width = 72;
      c.height = 48;
      drawFrameThumb(c, i, ev.payload.score);
      btn.appendChild(c);
      film.appendChild(btn);
    });
    var svg = container.querySelector(".timeline");
    var w = 320;
    var h = 64;
    var pad = 16;
    var inner = w - pad * 2;
    var times = frames.map(function (f) { return typeof f.payload.t === "number" ? f.payload.t : 0; });
    var tMin = Math.min.apply(null, times);
    var tMax = Math.max.apply(null, times);
    if (tMax === tMin) tMax = tMin + 1;
    function x(t) { return pad + ((t - tMin) / (tMax - tMin)) * inner; }
    function y(s) { return h - 12 - Math.max(0, Math.min(1, s || 0)) * (h - 28); }
    var ns = "http://www.w3.org/2000/svg";
    function el(name, attrs) {
      var node = document.createElementNS(ns, name);
      Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
      return node;
    }
    svg.appendChild(el("line", { x1: pad, y1: h - 12, x2: w - pad, y2: h - 12, stroke: "currentColor", "stroke-width": "1" }));
    var d = "";
    frames.forEach(function (ev, i) {
      var px = x(ev.payload.t);
      var py = y(ev.payload.score);
      d += (i ? "L" : "M") + px + " " + py + " ";
      svg.appendChild(el("circle", { cx: String(px), cy: String(py), r: "3", fill: "currentColor" }));
    });
    var path = el("path", { d: d, fill: "none", stroke: "currentColor", "stroke-width": "1" });
    svg.insertBefore(path, svg.firstChild);
  }

  function renderMediaResult(v, file) {
    var html = "<div class=\"result-layout\">";
    html += "<div class=\"result-evidence\" id=\"media-evidence\"></div>";
    html += "<div class=\"result-summary\">" + summaryHead(v) + renderProviders(v) + feedbackBlock("media", v.id) + "</div>";
    html += "</div>";
    els.mediaResult.innerHTML = html;
    var evidence = els.mediaResult.querySelector("#media-evidence");
    evidence.innerHTML = "<h3>Evidence</h3>";
    renderAnomalyMap(evidence, v, file);
    renderVideoTimeline(evidence, v);
    bindResultChrome(els.mediaResult, "media");
    tickRisk(els.mediaResult, v.risk);
  }

  function tickRisk(root, target) {
    var node = root.querySelector(".risk-value");
    if (!node || typeof target !== "number" || reduceMotion()) {
      if (node && typeof target === "number") node.textContent = String(target);
      return;
    }
    var start = performance.now();
    function frame(now) {
      var t = Math.min(1, (now - start) / 200);
      node.textContent = (target * t).toFixed(2);
      if (t < 1) requestAnimationFrame(frame);
      else node.textContent = String(target);
    }
    requestAnimationFrame(frame);
  }

  function renderFail(lane, status, body) {
    var copy = errorCopy(status, body, lane);
    var html = "<p>" + escapeHtml(copy.happened) + "</p>";
    var counts = countOk(body && body.providers);
    if (counts.total) html += "<p class=\"muted\">" + counts.ok + " of " + counts.total + " providers answered.</p>";
    else if (status === 503) html += "<p class=\"muted\">0 of the configured providers answered. No score is shown.</p>";
    html += "<p>" + escapeHtml(copy.next) + "</p>";
    if (lane === "media") {
      els.mediaFail.innerHTML = html;
      setLaneMode(els.mediaLane, els.mediaResult, "fail");
    } else {
      els.msgFail.innerHTML = html;
      setLaneMode(els.msgLane, els.msgResult, "fail");
    }
  }

  function renderHistory(lane) {
    var state = lane === "media" ? media : message;
    var wrap = lane === "media" ? els.mediaHistoryWrap : els.msgHistoryWrap;
    var list = lane === "media" ? els.mediaHistory : els.msgHistory;
    if (!state.history.length) {
      wrap.hidden = true;
      return;
    }
    wrap.hidden = false;
    list.innerHTML = "";
    state.history.forEach(function (item) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      var v = item.verdict;
      btn.innerHTML = "<span class=\"caps\">" + escapeHtml(caseRef(v.id)) + "</span> · " +
        escapeHtml(v.level || "") + " · " + escapeHtml(v.label || "");
      btn.addEventListener("click", function () {
        if (lane === "media") {
          media.file = item.file;
          media.verdict = v;
          els.mediaName.textContent = item.file ? item.file.name : "";
          setLaneMode(els.mediaLane, els.mediaResult, "result");
          renderMediaResult(v, item.file);
        } else {
          message.text = item.text;
          message.file = item.file;
          message.verdict = v;
          els.msgInput.value = item.text || "";
          els.msgName.textContent = item.file ? item.file.name : "";
          setLaneMode(els.msgLane, els.msgResult, "result");
          renderMessageResult(v, item.text);
        }
      });
      li.appendChild(btn);
      list.appendChild(li);
    });
  }

  function sendToMedia(filename) {
    if (!filename) return;
    var type = /\.png$/i.test(filename) ? "image/png" : "application/octet-stream";
    var file = new File([new Uint8Array([137, 80, 78, 71])], filename, { type: type });
    media.file = file;
    media.pendingName = filename;
    els.mediaName.textContent = filename;
    els.mediaTray.classList.add("is-dragover");
    setTimeout(function () { els.mediaTray.classList.remove("is-dragover"); }, 200);
    analyzeMedia();
  }

  async function analyzeMessage() {
    var text = els.msgInput.value;
    var file = message.file;
    if (file && !text) {
      try { text = await file.text(); } catch (e) { text = ""; }
    }
    message.text = text;
    if (!file && !String(text).trim()) {
      renderFail("message", 400, { detail: "Paste a message or choose a .txt or .eml file." });
      return;
    }
    setLaneMode(els.msgLane, els.msgResult, "loading");
    els.msgTray.classList.add("is-loading");
    var step = 0;
    els.msgStep.textContent = MSG_STEPS[0];
    var timer = setInterval(function () {
      step = (step + 1) % MSG_STEPS.length;
      els.msgStep.textContent = MSG_STEPS[step];
    }, 180);
    var result = MOCK
      ? await mockAnalyze(text, file ? file.name : "", "message")
      : await liveAnalyze("/api/message/analyze", file
        ? { method: "POST", body: (function () { var f = new FormData(); f.append("file", file, file.name); return f; })() }
        : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: text }) });
    clearInterval(timer);
    els.msgTray.classList.remove("is-loading");
    if (!result.ok) {
      renderFail("message", result.status, result.body);
      return;
    }
    var v = result.body;
    if (!v || !v.id) {
      renderFail("message", 500, { detail: "The response did not include a verdict id." });
      return;
    }
    message.verdict = v;
    message.history.unshift({ text: text, file: file, verdict: v });
    if (message.history.length > 8) message.history.length = 8;
    setLaneMode(els.msgLane, els.msgResult, "result");
    renderMessageResult(v, text);
    renderHistory("message");
  }

  async function analyzeMedia() {
    var file = media.file;
    if (!file) {
      renderFail("media", 400, { detail: "Choose an image or video file." });
      return;
    }
    setLaneMode(els.mediaLane, els.mediaResult, "loading");
    els.mediaTray.classList.add("is-loading");
    var step = 0;
    els.mediaStep.textContent = MEDIA_STEPS[0];
    var timer = setInterval(function () {
      step = (step + 1) % MEDIA_STEPS.length;
      els.mediaStep.textContent = MEDIA_STEPS[step];
    }, 180);
    var result;
    if (MOCK) {
      result = await mockAnalyze("", file.name, "media");
    } else {
      var form = new FormData();
      form.append("file", file, file.name);
      result = await liveAnalyze("/api/media/analyze", { method: "POST", body: form });
    }
    clearInterval(timer);
    els.mediaTray.classList.remove("is-loading");
    if (!result.ok) {
      renderFail("media", result.status, result.body);
      return;
    }
    var v = result.body;
    if (!v || !v.id) {
      renderFail("media", 500, { detail: "The response did not include a verdict id." });
      return;
    }
    media.verdict = v;
    media.history.unshift({ file: file, verdict: v });
    if (media.history.length > 8) media.history.length = 8;
    setLaneMode(els.mediaLane, els.mediaResult, "result");
    renderMediaResult(v, file);
    renderHistory("media");
  }

  function bindDrop(tray, onFile) {
    tray.addEventListener("dragover", function (ev) {
      ev.preventDefault();
      tray.classList.add("is-dragover");
    });
    tray.addEventListener("dragleave", function () { tray.classList.remove("is-dragover"); });
    tray.addEventListener("drop", function (ev) {
      ev.preventDefault();
      tray.classList.remove("is-dragover");
      var f = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
      if (f) onFile(f);
    });
  }

  function onMessageFile(file) {
    message.file = file;
    els.msgName.textContent = file.name;
    if (!/\.(txt|eml)$/i.test(file.name)) {
      renderFail("message", 400, { detail: "Unsupported file. Use .txt or .eml." });
      return;
    }
    file.text().then(function (t) {
      els.msgInput.value = t;
      message.text = t;
    }).catch(function () { /* filename only */ });
  }

  function onMediaFile(file) {
    media.file = file;
    media.pendingName = file.name;
    els.mediaName.textContent = file.name;
  }

  function mockImageFile() {
    var canvas = document.createElement("canvas");
    canvas.width = 64;
    canvas.height = 48;
    var ctx = canvas.getContext("2d");
    ctx.fillStyle = "#5b574f";
    ctx.fillRect(0, 0, 64, 48);
    return new Promise(function (resolve) {
      canvas.toBlob(function (blob) {
        resolve(new File([blob], "sample.png", { type: "image/png" }));
      }, "image/png");
    });
  }

  function mockVideoFile() {
    return new File([new Uint8Array([0, 0, 0, 24, 102, 116, 121, 112])], "sample.mp4", { type: "video/mp4" });
  }

  function mountExamples() {
    if (!MOCK) return;
    els.msgExamples.hidden = false;
    MSG_EXAMPLES.forEach(function (ex) {
      if (!fixtures[ex.key] && ex.key !== "fail") return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = ex.label;
      btn.addEventListener("click", function () {
        if (ex.key === "email") {
          onMessageFile(new File([samples.email || ""], "invoice.eml"));
          els.msgInput.value = samples.email || "";
        } else {
          message.file = null;
          els.msgName.textContent = "";
          els.msgInput.value = samples[ex.key] || "";
        }
        analyzeMessage();
      });
      els.msgExamples.appendChild(btn);
    });
    els.mediaExamples.hidden = false;
    var imgBtn = document.createElement("button");
    imgBtn.type = "button";
    imgBtn.textContent = "Sample image";
    imgBtn.addEventListener("click", function () {
      mockImageFile().then(function (f) {
        onMediaFile(f);
        analyzeMedia();
      });
    });
    var vidBtn = document.createElement("button");
    vidBtn.type = "button";
    vidBtn.textContent = "Sample video";
    vidBtn.addEventListener("click", function () {
      onMediaFile(mockVideoFile());
      analyzeMedia();
    });
    els.mediaExamples.appendChild(imgBtn);
    els.mediaExamples.appendChild(vidBtn);
  }

  function showView() {
    var rec = (window.location.hash || "") === "#records";
    els.viewDesk.hidden = rec;
    els.viewRecords.hidden = !rec;
    els.navDesk.setAttribute("aria-current", rec ? "false" : "page");
    els.navRecords.setAttribute("aria-current", rec ? "page" : "false");
    if (rec) loadRecords();
  }

  function formatMetric(v) {
    if (typeof v !== "number") return "";
    return String(v);
  }

  async function loadRecords() {
    var body = els.recordsBody;
    body.innerHTML = "<h2>Records</h2><p class=\"muted\">Reading /api/metrics.</p>";
    var data = null;
    var res = await liveAnalyze("/api/metrics", { method: "GET" });
    if (res.ok) data = res.body;
    if (!data || typeof data !== "object" || !data.models || !Object.keys(data.models).length) {
      body.innerHTML = "<h2>Records</h2><p>Not evaluated.</p>" +
        "<p class=\"muted\">No registry metrics are available yet. Run the evaluation script, then refresh.</p>";
      return;
    }
    var html = "<h2>Records</h2>";
    html += "<p class=\"chip\">Risk score with evidence, not proof.</p>";
    Object.keys(data.models).forEach(function (ver) {
      var m = data.models[ver];
      html += "<div class=\"section\"><h3 class=\"mono\">" + showField(ver) + "</h3>";
      html += "<p class=\"muted\">" + showField(m.modality) +
        (m.holdout_version ? " · " + showField(m.holdout_version) : "") + "</p>";
      if (m.metrics) {
        html += "<dl class=\"stats\">";
        if (typeof m.metrics.accuracy === "number") html += "<div class=\"stat\"><dt>Accuracy</dt><dd class=\"num\">" + formatMetric(m.metrics.accuracy) + "</dd></div>";
        if (typeof m.metrics.macro_f1 === "number") html += "<div class=\"stat\"><dt>Macro-F1</dt><dd class=\"num\">" + formatMetric(m.metrics.macro_f1) + "</dd></div>";
        html += "</dl>";
        if (m.metrics.confusion_matrix) {
          var labels = Object.keys(m.metrics.confusion_matrix);
          html += "<table class=\"matrix\"><thead><tr><th></th>";
          labels.forEach(function (l) { html += "<th>" + showField(l) + "</th>"; });
          html += "</tr></thead><tbody>";
          labels.forEach(function (row) {
            html += "<tr><th>" + showField(row) + "</th>";
            labels.forEach(function (col) {
              var cell = m.metrics.confusion_matrix[row] && m.metrics.confusion_matrix[row][col];
              html += "<td class=\"num\">" + (typeof cell === "number" ? cell : "") + "</td>";
            });
            html += "</tr>";
          });
          html += "</tbody></table>";
        }
      } else {
        html += "<p class=\"muted\">Not evaluated.</p>";
      }
      html += "</div>";
    });
    if (Array.isArray(data.promotions)) {
      html += "<div class=\"section\"><h3>Promotions</h3>";
      if (!data.promotions.length) html += "<p class=\"muted\">None recorded.</p>";
      html += "</div>";
    }
    html += "<div class=\"section\"><button type=\"button\" id=\"retrain-btn\" class=\"ghost\">Retrain</button>";
    html += "<p class=\"muted\" id=\"retrain-status\">Retrain is a training-loop command. This button does not invent a score.</p></div>";
    body.innerHTML = html;
  }

  els.theme.addEventListener("click", function () {
    applyTheme(els.html.getAttribute("data-theme") === "dark" ? "light" : "dark");
  });
  els.msgChoose.addEventListener("click", function () { els.msgFile.click(); });
  els.mediaChoose.addEventListener("click", function () { els.mediaFile.click(); });
  els.msgFile.addEventListener("change", function () {
    if (els.msgFile.files[0]) onMessageFile(els.msgFile.files[0]);
  });
  els.mediaFile.addEventListener("change", function () {
    if (els.mediaFile.files[0]) onMediaFile(els.mediaFile.files[0]);
  });
  els.msgAnalyze.addEventListener("click", function () { analyzeMessage(); });
  els.mediaAnalyze.addEventListener("click", function () { analyzeMedia(); });
  els.msgInput.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      analyzeMessage();
    }
  });
  bindDrop(els.msgTray, onMessageFile);
  bindDrop(els.mediaTray, onMediaFile);
  window.addEventListener("hashchange", showView);

  if (MOCK) els.mockChip.hidden = false;
  initTheme();
  mountExamples();
  showView();
})();
