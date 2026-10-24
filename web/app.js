(function () {
  "use strict";

  var params = new URLSearchParams(window.location.search);
  var MOCK = params.get("mock") === "1";
  var FIXTURE_OVERRIDE = params.get("fixture");
  var fixtures = window.SKEPTID_FIXTURES || {};
  var samples = window.SKEPTID_SAMPLES || {};

  var message = {
    text: "",
    file: null,
    verdict: null,
    history: []
  };
  var media = {
    file: null,
    pendingName: "",
    verdict: null,
    objectUrl: null,
    duration: null
  };

  var els = {
    html: document.documentElement,
    mockChip: document.getElementById("mock-chip"),
    includeExternal: document.getElementById("include-external"),
    msgPrivacy: document.getElementById("message-privacy"),
    mediaPrivacy: document.getElementById("media-privacy"),
    theme: document.getElementById("theme-toggle"),
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
    mediaTray: document.getElementById("media-tray"),
    mediaChoose: document.getElementById("media-choose"),
    mediaFile: document.getElementById("media-file"),
    mediaName: document.getElementById("media-filename"),
    mediaLane: document.getElementById("media-lane"),
    mediaStep: document.getElementById("media-step"),
    mediaFail: document.getElementById("media-fail"),
    mediaResult: document.getElementById("media-result"),
    mediaAnalyze: document.getElementById("media-analyze"),
    recordsLink: document.getElementById("records-link"),
    records: document.getElementById("records"),
    recordsContent: document.getElementById("records-content"),
    recordsBack: document.getElementById("records-back"),
    deskGrid: document.querySelector(".desk"),
    deskLink: document.querySelector(".nav a[href=\"#desk\"]")
  };

  var STEPS = [
    "Checking body text",
    "Checking headers",
    "Scoring spans",
    "Collecting provider results"
  ];

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
    els.theme.setAttribute("aria-label", "Switch to " + (theme === "dark" ? "Paper" : "Graphite") + " theme");
    try {
      localStorage.setItem("skeptid-theme", theme);
    } catch (e) {
      /* ignore quota */
    }
  }

  function initTheme() {
    var stored = null;
    try {
      stored = localStorage.getItem("skeptid-theme");
    } catch (e) {
      stored = null;
    }
    if (stored === "dark" || stored === "light") {
      applyTheme(stored);
      return;
    }
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
  }

  function setLaneMode(laneEl, mode) {
    laneEl.classList.toggle("is-empty", mode === "empty");
    laneEl.classList.toggle("is-loading", mode === "loading");
    laneEl.classList.toggle("is-fail", mode === "fail");
  }

  function pickFixtureKey(text, filename) {
    if (FIXTURE_OVERRIDE && fixtures[FIXTURE_OVERRIDE]) return FIXTURE_OVERRIDE;
    var name = (filename || "").toLowerCase();
    var body = (text || "").toLowerCase();
    if (name.indexOf("fail") !== -1 || body.indexOf("force_provider_failure") !== -1) return "fail";
    if (name.indexOf("invoice") !== -1 || /\.eml$/.test(name) || body.indexOf("attached invoice") !== -1) {
      return "email";
    }
    if (name.indexOf("partial") !== -1 || body.indexOf("header path is incomplete") !== -1) return "partial";
    if (name.indexOf("disagree") !== -1 || body.indexOf("second scan flagged") !== -1) return "disagree";
    if (name.indexOf("high") !== -1 || body.indexOf("confirm your password") !== -1) return "high";
    if (name.indexOf("medium") !== -1 || body.indexOf("reply stop") !== -1) return "medium";
    if (name.indexOf("low") !== -1 || body.indexOf("no password or account action") !== -1) return "low";
    if (/\.(png|jpe?g|webp)$/.test(name)) return "image";
    if (/\.(mp4|mov|avi|webm)$/.test(name)) return "video";
    return "low";
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
  }

  function privacyText(externalUsed) {
    if (externalUsed === true) return "Content was sent to an external provider for this analysis";
    if (externalUsed === false) return "Processed in memory, not stored";
    return "Privacy status unavailable";
  }

  function updatePrivacyChip(chip, externalUsed) {
    chip.textContent = privacyText(externalUsed);
  }

  async function mockAnalyze(text, filename) {
    await sleep(reduceMotion() ? 80 : 720);
    var key = pickFixtureKey(text, filename);
    var fixture = fixtures[key];
    if (!fixture) {
      return { ok: false, status: 500, body: { detail: "Mock fixture is missing." } };
    }
    if (fixture.status) {
      return { ok: false, status: fixture.status, body: { detail: fixture.detail } };
    }
    var body = JSON.parse(JSON.stringify(fixture));
    body.external_used = false;
    if (body.providers) body.providers.forEach(function (p) { p.validated = false; });
    if (body.evidence && (body.modality === "text" || body.modality === "email")) {
      body.evidence = body.evidence.filter(function (ev) { return ev.kind !== "span"; });
      var rules = body.level === "HIGH" ? /urgent|verify|password|account|payment|link|confirm/ig :
        body.level === "MEDIUM" ? /deals?|reply stop|limited stock|vendor/ig : null;
      if (rules) {
        var match;
        while ((match = rules.exec(text)) !== null) {
          var before = text.slice(0, match.index);
          var end = text.slice(0, match.index + match[0].length);
          body.evidence.push({ kind: "span", description: body.level === "HIGH" ? "Potentially risky instruction" : "Message pattern to review", payload: { start: Array.from(before).length, end: Array.from(end).length, weight: body.level === "HIGH" ? 0.28 : 0.18 } });
          if (body.evidence.filter(function (ev) { return ev.kind === "span"; }).length >= 3) break;
        }
      }
    }
    return { ok: true, status: 200, body: body };
  }

  async function mockMediaAnalyze(file) {
    await sleep(reduceMotion() ? 80 : 720);
    var fixture = fixtures[mediaKind(file)];
    if (!fixture) return { ok: false, status: 500, body: { detail: "Mock media fixture is missing." } };
    var body = JSON.parse(JSON.stringify(fixture));
    body.external_used = false;
    if (body.providers) body.providers.forEach(function (p) { p.validated = false; });
    return { ok: true, status: 200, body: body };
  }

  async function liveAnalyze(text, file) {
    var res;
    var useExternal = els.includeExternal.checked;
    try {
      if (file) {
        var form = new FormData();
        form.append("file", file, file.name);
        form.append("use_external", String(useExternal));
        res = await fetch("/api/message/analyze", { method: "POST", body: form });
      } else {
        res = await fetch("/api/message/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text, use_external: useExternal })
        });
      }
    } catch (err) {
      return {
        ok: false,
        status: 0,
        body: {
          detail: "Couldn't reach the analysis service. Serve this page from the SKEPTID server, then try again."
        }
      };
    }
    var body = {};
    try {
      body = await res.json();
    } catch (e) {
      body = { detail: "The server returned a non-JSON response." };
    }
    return { ok: res.ok, status: res.status, body: body };
  }

  async function liveAnalyzeMedia(file) {
    var form = new FormData();
    form.append("file", file, file.name);
    form.append("use_external", String(els.includeExternal.checked));
    try {
      var res = await fetch("/api/media/analyze", { method: "POST", body: form });
      var body = {};
      try { body = await res.json(); } catch (e) { body = {}; }
      return { ok: res.ok, status: res.status, body: body };
    } catch (e) {
      return { ok: false, status: 0, body: {} };
    }
  }

  function mediaKind(file) {
    var name = (file && file.name || "").toLowerCase();
    if (/\.(jpe?g|png|webp)$/.test(name)) return "image";
    if (/\.(mp4|mov|avi|webm)$/.test(name)) return "video";
    if (/\.(wav|mp3|ogg|flac|m4a)$/.test(name)) return "audio";
    return "";
  }

  function inspectVideo(file) {
    return new Promise(function (resolve) {
      var url = URL.createObjectURL(file);
      var video = document.createElement("video");
      video.preload = "metadata";
      video.muted = true;
      var settled = false;
      var done = function (duration) { if (settled) return; settled = true; video.removeAttribute("src"); video.load(); resolve({ duration: duration, url: url }); };
      video.onloadedmetadata = function () { done(Number.isFinite(video.duration) ? video.duration : null); };
      video.onerror = function () { done(null); };
      setTimeout(function () { if (!video.readyState) done(null); }, 5000);
      video.src = url;
    });
  }

  function feedbackMarkup(v, key) {
    var labels = v.modality === "image" || v.modality === "video" ?
      ["real", "ai_generated", "ai_edited", "deepfake", "manipulated"] :
      ["safe", "spam", "phishing", "threat", "bullying"];
    var html = "<div class=\"section feedback\" data-feedback=\"" + key + "\"><h3>Was this useful?</h3><div class=\"feedback-row\"><button type=\"button\" class=\"secondary feedback-correct\">Correct</button><button type=\"button\" class=\"ghost feedback-wrong\">Wrong, it was...</button><label class=\"feedback-label\" hidden>True label <select>";
    labels.forEach(function (label) { html += "<option value=\"" + label + "\">" + label.replace(/_/g, " ") + "</option>"; });
    html += "</select></label><button type=\"button\" class=\"primary feedback-send\" hidden>Send label</button></div><p class=\"muted feedback-status\" aria-live=\"polite\"></p></div>";
    return html;
  }

  function bindFeedback(root, v, key) {
    var box = root.querySelector("[data-feedback=\"" + key + "\"]");
    if (!box || !v.id) return;
    var correct = box.querySelector(".feedback-correct");
    var wrong = box.querySelector(".feedback-wrong");
    var label = box.querySelector(".feedback-label");
    var send = box.querySelector(".feedback-send");
    var status = box.querySelector(".feedback-status");
    async function submit(isCorrect, trueLabel) {
      correct.disabled = true; wrong.disabled = true; send.disabled = true;
      status.textContent = "Sending feedback…";
      try {
        var response = await fetch("/api/feedback", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ analysis_id: v.id, correct: isCorrect, true_label: trueLabel || undefined }) });
        var data = await response.json();
        if (!response.ok) throw new Error("Feedback could not be sent.");
        status.textContent = data.status === "recorded" ? "Feedback recorded." : "Feedback received.";
      } catch (e) {
        status.textContent = "Feedback could not be sent. Check the connection and try again.";
        correct.disabled = false; wrong.disabled = false; send.disabled = false;
      }
    }
    correct.addEventListener("click", function () { submit(true); });
    wrong.addEventListener("click", function () { label.hidden = false; send.hidden = false; });
    send.addEventListener("click", function () { submit(false, label.querySelector("select").value); });
  }

  function errorCopy(status, body) {
    var detail = "The analysis did not complete.";
    var next = "Paste another message, or try again.";
    if (status === 503) {
      detail = "The analysis service could not form a verdict.";
      next = "No verdict was formed. Wait a moment, then analyse again. Nothing on this page is a substitute score.";
    } else if (status === 429) {
      detail = "The analysis service is receiving too many requests.";
      next = "Wait until the rate window resets, then analyse again.";
    } else if (status === 400 || status === 415) {
      detail = "This file or message could not be analysed.";
      next = "Use pasted text, a .txt file, or a .eml file.";
    } else if (status === 0) {
      detail = "Couldn't reach the analysis service.";
      next = "Open ?mock=1 for fixtures, or run the API on the same origin.";
    } else if (body && body.detail && status >= 500) {
      detail = "The analysis service returned an error.";
      next = "Wait a moment, then try again.";
    }
    return { happened: detail, next: next };
  }

  function countOk(providers) {
    if (!Array.isArray(providers)) return { ok: 0, total: 0 };
    var ok = 0;
    providers.forEach(function (p) {
      if (p && p.ok === true) ok += 1;
    });
    return { ok: ok, total: providers.length };
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function codePointOffsetToUtf16(text, offset) {
    return Array.from(text).slice(0, Math.max(0, offset)).join("").length;
  }

  function highlight(text, evidence) {
    if (!text) return "<p class=\"muted\">No source text is held for this case.</p>";
    var spans = [];
    (evidence || []).forEach(function (ev) {
      if (!ev || ev.kind !== "span" || !ev.payload) return;
      var start = ev.payload.start;
      var end = ev.payload.end;
      if (typeof start !== "number" || typeof end !== "number") return;
      if (start < 0 || end > Array.from(text).length || start >= end) return;
      spans.push({ start: codePointOffsetToUtf16(text, start), end: codePointOffsetToUtf16(text, end), description: ev.description || "", weight: ev.payload.weight });
    });
    spans.sort(function (a, b) { return a.start - b.start; });
    var html = "";
    var cursor = 0;
    var why = "<ol class=\"why-flagged\">";
    spans.forEach(function (sp, idx) {
      if (sp.start < cursor) return;
      html += escapeHtml(text.slice(cursor, sp.start));
      html += "<mark class=\"hl\" id=\"span-" + (idx + 1) + "\" title=\"" + escapeHtml(sp.description) + "\"><sup>" + (idx + 1) + "</sup> " +
        escapeHtml(text.slice(sp.start, sp.end)) + "</mark>";
      why += "<li><a href=\"#span-" + (idx + 1) + "\">" + (idx + 1) + ". " + escapeHtml(sp.description) + "</a> <span class=\"muted\">weight " + showField(sp.weight) + "</span></li>";
      cursor = sp.end;
    });
    html += escapeHtml(text.slice(cursor));
    why += "</ol>";
    return "<div class=\"evidence-text\">" + (why === "<ol class=\"why-flagged\"></ol>" ? "<p class=\"muted\">No strong indicators.</p>" : "<h4>Why flagged</h4>" + why) + "<p>" + html + "</p></div>";
  }

  function urlsFrom(evidence) {
    return (evidence || []).filter(function (ev) {
      return ev && ev.payload && ev.payload.check === "url";
    });
  }

  function headersFrom(evidence) {
    return (evidence || []).filter(function (ev) {
      return ev && ev.payload && ev.payload.check === "header";
    });
  }

  function attachmentsFrom(evidence) {
    return (evidence || []).filter(function (ev) {
      return ev && ev.payload && ev.payload.check === "attachment";
    });
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

  function renderModelVersion(version) {
    var html = "<p class=\"provider-version\"><span class=\"muted\">Model</span> ";
    html += "<span class=\"mono\">" + showField(version) + "</span>";
    html += "</p>";
    return html;
  }

  function renderRiskStrip(items) {
    var html = "<div class=\"risk-strip\" role=\"img\" aria-label=\"Provider risk scores on a zero to one scale\"><span class=\"strip-tick tick-35\"></span><span class=\"strip-tick tick-70\"></span>";
    items.forEach(function (p) {
      if (p.ok !== true || typeof p.risk !== "number") return;
      html += "<i title=\"" + escapeHtml(String(p.id)) + ": " + p.risk + "\" style=\"--position:" + Math.max(0, Math.min(1, p.risk)) * 100 + "%\"></i>";
    });
    return html + "<span class=\"strip-labels\"><i>0</i><i>0.35</i><i>0.70</i><i>1.0</i></span></div>";
  }

  function renderProviders(v) {
    var items = Array.isArray(v.providers) ? v.providers : [];
    if (!items.length) return "";
    var html = "<div class=\"section provider-section\"><h3>Providers</h3>";
    var risks = items.filter(function (p) { return p.ok === true && typeof p.risk === "number"; }).map(function (p) { return p.risk; });
    if (risks.length > 1) {
      var spread = Math.max.apply(null, risks) - Math.min.apply(null, risks);
      var agreement = v.disagreement ? "Providers disagree" : risks.length === 3 ? "All three agree" : "Answered providers agree";
      html += "<p class=\"muted\">" + agreement + ", spread " + spread.toFixed(2) + ".</p>";
      html += renderRiskStrip(items);
    }
    var counts = countOk(items);
    html += "<p class=\"muted\">" + counts.ok + " of " + counts.total + " providers answered.</p>";
    html += "<div class=\"providers\">";
    items.forEach(function (p) {
      var unavailable = p.ok !== true;
      html += "<div class=\"provider" + (unavailable ? " unavailable" : "") + "\">";
      var names = { own: "SKEPTID model", opensource: "Open-source model", external: "External service" };
      html += "<div class=\"id\">" + showField(names[p.id] || p.id) + (v.primary_provider === p.id ? " <span class=\"shown-result\">Shown result</span>" : "") + "</div>";
      if (unavailable) {
        var issue = String(p.error || "").toLowerCase();
        html += "<p class=\"muted\">Unavailable" + (issue === "timeout" ? " · Timed out" : issue === "blocked" ? " · Request blocked" : "") + "</p>";
      } else if (typeof p.risk === "number") {
        html += "<p class=\"num\">" + p.risk + "</p>";
      }
      if (p.validated === false || isUnvalidatedVersion(p.model_version)) html += "<span class=\"chip tag-plain\">not validated</span>";
      html += renderModelVersion(p.model_version);
      if (typeof p.latency_ms === "number") {
        html += "<p class=\"muted num\">" + p.latency_ms + " ms</p>";
      }
      html += "</div>";
    });
    html += "</div></div>";
    return html;
  }

  function renderTables(v) {
    var html = "";
    var urls = urlsFrom(v.evidence);
    if (urls.length) {
      html += "<div class=\"section\"><h3>URL checks</h3><table><thead><tr>" +
        "<th>Display</th><th>Href</th><th>Issue</th></tr></thead><tbody>";
      urls.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td>" + showField(p.display) + "</td><td class=\"mono\">" +
          showField(p.href) + "</td><td>" + showField(p.issue || ev.description) + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    var headers = headersFrom(v.evidence);
    if (headers.length) {
      html += "<div class=\"section\"><h3>Header checks</h3><table><thead><tr>" +
        "<th>Field</th><th>Issue</th></tr></thead><tbody>";
      headers.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td class=\"mono\">" + showField(p.field) + "</td><td>" +
          showField(p.issue || ev.description) + "</td></tr>";
      });
      html += "</tbody></table></div>";
    }
    var atts = attachmentsFrom(v.evidence);
    if (atts.length) {
      html += "<div class=\"section\"><h3>Attachments</h3><table><thead><tr>" +
        "<th>File</th><th>Type</th><th class=\"num\">Size</th><th class=\"num\">Risk</th><th></th></tr></thead><tbody>";
      atts.forEach(function (ev) {
        var p = ev.payload;
        html += "<tr><td class=\"mono\">" + showField(p.filename) + "</td><td>" +
          showField(p.type) + "</td><td class=\"num\">" +
          (typeof p.size === "number" ? p.size : "") + "</td><td class=\"num\">" +
          (typeof p.risk === "number" ? p.risk : "") + "</td><td>" +
          "<button type=\"button\" class=\"ghost send-media\" data-filename=\"" +
          escapeHtml(p.filename || "") + "\">Send to Media intake</button></td></tr>";
      });
      html += "</tbody></table></div>";
    }
    return html;
  }

  function applyThreatAmbiance(level) {
    document.body.classList.remove("ambiance-threat", "ambiance-warning", "ambiance-legit");
    if (level === "HIGH") document.body.classList.add("ambiance-threat");
    else if (level === "MEDIUM") document.body.classList.add("ambiance-warning");
    else if (level === "LOW") document.body.classList.add("ambiance-legit");
  }

  function renderResult(v, sourceText) {
    var mock = v.mock === true;
    els.mockChip.hidden = !(MOCK || mock);
    applyThreatAmbiance(v.level);
    var html = "<div class=\"result-head\">";
    html += "<div><span class=\"verdict\" data-level=\"" + showField(v.level) + "\">" +
      showField(v.level) + "</span>";
    if (mock) html += " <span class=\"chip mock\">MOCK</span>";
    html += "<p class=\"muted\" style=\"margin-top:12px\">" + showField(v.label) +
      " · " + showField(v.modality) + " · " + showField(v.primary_provider) + "</p></div>";
    html += "<div class=\"meta\"><div class=\"caps\">" + caseRef(v.id) + "</div>";
    html += "<button class=\"copy-id ghost\" type=\"button\" data-id=\"" + showField(v.id) + "\">Copy ID</button></div></div>";
    html += "<dl class=\"stats\">";
    html += "<div class=\"stat\"><dt>Risk</dt><dd id=\"risk-value\" class=\"num\">" +
      (typeof v.risk === "number" ? v.risk : "") + "</dd></div>";
    html += "<div class=\"stat\"><dt>Confidence</dt><dd class=\"num\">" +
      (typeof v.confidence === "number" ? v.confidence : "") + "</dd></div>";
    html += "<div class=\"stat\"><dt>Label</dt><dd>" + showField(v.label) + "</dd></div>";
    html += "</dl>";
    html += "<div class=\"risk-bar\" role=\"img\" aria-label=\"Risk " + (typeof v.risk === "number" ? v.risk : "not available") + "\"><span style=\"--risk:" + (typeof v.risk === "number" ? Math.max(0, Math.min(1, v.risk)) * 100 : 0) + "%\"></span><i class=\"tick tick-35\"></i><i class=\"tick tick-70\"></i></div>";
    html += "<p class=\"chip privacy\">" + privacyText(v.external_used) + "</p>";
    if (v.limits_note) {
      html += "<p class=\"chip\">" + showField(v.limits_note) + "</p>";
    }
    html += "<div class=\"section evidence-section\"><h3>Highlighted spans</h3>" + highlight(sourceText, v.evidence) + "</div>";
    html += renderProviders(v);
    html += renderTables(v);
    html += feedbackMarkup(v, "message");
    els.msgResult.innerHTML = html;
    els.msgResult.querySelectorAll(".send-media").forEach(function (btn) {
      btn.addEventListener("click", function () {
        sendToMedia(btn.getAttribute("data-filename"));
      });
    });
    els.msgResult.querySelectorAll(".copy-id").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (navigator.clipboard && v.id) navigator.clipboard.writeText(v.id).catch(function () { btn.textContent = "Copy unavailable"; });
      });
    });
    bindFeedback(els.msgResult, v, "message");
    tickRisk(v.risk);
  }

  function renderMediaResult(v, file) {
    var mock = v.mock === true;
    els.mockChip.hidden = !(MOCK || mock);
    applyThreatAmbiance(v.level);
    var html = "<div class=\"result-head\"><div><span class=\"verdict\" data-level=\"" + showField(v.level) + "\">" + showField(v.level) + "</span>";
    if (mock) html += " <span class=\"chip mock\">MOCK</span>";
    html += "<p class=\"muted\">" + showField(v.label) + " · " + showField(v.modality) + "</p></div><div class=\"meta\"><div class=\"caps\">" + caseRef(v.id) + "</div><button class=\"copy-id ghost\" type=\"button\" data-id=\"" + showField(v.id) + "\">Copy ID</button></div></div>";
    html += "<dl class=\"stats\"><div class=\"stat\"><dt>Risk</dt><dd class=\"num\">" + (typeof v.risk === "number" ? v.risk : "") + "</dd></div><div class=\"stat\"><dt>Confidence</dt><dd class=\"num\">" + (typeof v.confidence === "number" ? v.confidence : "") + "</dd></div><div class=\"stat\"><dt>Label</dt><dd>" + showField(v.label) + "</dd></div></dl>";
    html += "<div class=\"risk-bar\" role=\"img\" aria-label=\"Risk " + (typeof v.risk === "number" ? v.risk : "not available") + "\"><span style=\"--risk:" + (typeof v.risk === "number" ? Math.max(0, Math.min(1, v.risk)) * 100 : 0) + "%\"></span><i class=\"tick tick-35\"></i><i class=\"tick tick-70\"></i></div>";
    html += "<p class=\"chip privacy\">" + privacyText(v.external_used) + "</p>";
    var evidence = Array.isArray(v.evidence) ? v.evidence : [];
    var heat = evidence.find(function (ev) { return ev.kind === "heatmap" && ev.payload && ev.payload.png_b64; });
    var kind = mediaKind(file);

    if (kind === "image") {
      var src = media.objectUrl || URL.createObjectURL(file);
      var mapRaw = heat ? String(heat.payload.png_b64) : "";
      var mapSrc = mapRaw.length < 4000000 && /^data:image\/png;base64,[A-Za-z0-9+/=]+$/.test(mapRaw) ? mapRaw : mapRaw.length < 4000000 && /^[A-Za-z0-9+/=]+$/.test(mapRaw) ? "data:image/png;base64," + mapRaw : "";
      html += "<div class=\"section media-visual\"><h3>Visual change map</h3><div class=\"anomaly-wrap\"><img class=\"media-preview\" src=\"" + src + "\" alt=\"Uploaded image\">" + (mapSrc ? "<img class=\"anomaly-layer\" src=\"" + mapSrc + "\" alt=\"Visual change overlay\" style=\"opacity:.55\">" : "") + "</div>";
      if (mapSrc) html += "<label class=\"opacity-control\">Map opacity <input type=\"range\" min=\"0\" max=\"1\" step=\"0.05\" value=\"0.55\"></label>";
      else html += "<p class=\"muted\">No visual change map was needed for this file.</p>";
      html += "<p class=\"media-caption\">" + escapeHtml(file.name) + " · " + file.size + " bytes</p></div>";
    } else if (kind === "audio") {
      var audioUrl = media.objectUrl || URL.createObjectURL(file);
      var specEv = evidence.find(function (ev) { return ev.kind === "spectrum"; });
      var bands = specEv && specEv.payload && specEv.payload.band_energies || [];
      html += "<div class=\"section media-visual audio-visual\"><h3>Voice sound analysis</h3>";
      html += "<audio class=\"audio-player-control\" controls src=\"" + audioUrl + "\"></audio>";
      if (bands.length) {
        html += "<p class=\"muted\" style=\"margin-top:8px\">16-band Mel power distribution</p><div class=\"spectrogram-bars\" role=\"img\" aria-label=\"Audio frequency distribution\">";
        var maxB = Math.max.apply(null, bands.concat([0.01]));
        bands.forEach(function (b, bIdx) {
          var hPct = Math.round((b / maxB) * 100);
          html += "<div class=\"spec-bar\" style=\"height:" + Math.max(8, hPct) + "%\" title=\"Band " + (bIdx + 1) + ": " + b + "\"></div>";
        });
        html += "</div>";
      }
      var flags = evidence.filter(function (ev) { return ev.kind === "flag"; });
      if (flags.length) {
        html += "<div class=\"why-flagged-section\"><h4 style=\"margin-top:10px\">Acoustic indicators</h4><ul class=\"why-flagged\">";
        flags.forEach(function (fl) {
          html += "<li>" + escapeHtml(fl.description) + "</li>";
        });
        html += "</ul></div>";
      }
      html += "<p class=\"media-caption\">" + escapeHtml(file.name) + " · " + file.size + " bytes</p></div>";
    } else {
      var videoUrl = media.objectUrl || URL.createObjectURL(file);
      html += "<div class=\"section media-visual\"><h3>Video frames</h3><video class=\"media-preview video-preview\" src=\"" + videoUrl + "\" controls preload=\"metadata\"></video><div class=\"frame-strip-wrap\"><div class=\"frame-strip\" aria-label=\"Video frame thumbnails\"></div></div><h3>Risk over time</h3><div class=\"frame-chart-wrap\"><svg class=\"frame-chart\" viewBox=\"0 0 1000 110\" role=\"img\" aria-label=\"Frame risk over time\"></svg></div></div>";
    }
    html += renderProviders(v);
    html += feedbackMarkup(v, "media");
    els.mediaResult.innerHTML = html;
    els.mediaResult.querySelectorAll(".copy-id").forEach(function (btn) { btn.addEventListener("click", function () { if (navigator.clipboard) navigator.clipboard.writeText(v.id).catch(function () { btn.textContent = "Copy unavailable"; }); }); });
    var opacity = els.mediaResult.querySelector(".opacity-control input");
    if (opacity) opacity.addEventListener("input", function () { var layer = els.mediaResult.querySelector(".anomaly-layer"); if (layer) layer.style.opacity = opacity.value; });
    bindFeedback(els.mediaResult, v, "media");
    if (mediaKind(file) === "video") renderVideoTimeline(els.mediaResult, file, evidence);
  }

  async function renderVideoTimeline(root, file, evidence) {
    var scores = evidence.filter(function (ev) { return ev.kind === "frame_score" && ev.payload && typeof ev.payload.t === "number" && typeof ev.payload.score === "number"; });
    var strip = root.querySelector(".frame-strip");
    var chart = root.querySelector(".frame-chart");
    if (!scores.length) { strip.textContent = "No frame thumbnails were returned."; var missing = document.createElement("p"); missing.className = "muted"; missing.textContent = "No frame timeline was returned."; chart.replaceWith(missing); return; }
    var maxTime = Math.max.apply(null, scores.map(function (ev) { return ev.payload.t; })) || 1;
    var url = media.objectUrl || URL.createObjectURL(file);
    var player = document.createElement("video");
    player.muted = true; player.preload = "metadata"; player.src = url;
    await new Promise(function (resolve) { player.onloadedmetadata = resolve; player.onerror = resolve; setTimeout(resolve, 5000); });
    var points = [];
    var canvas = document.createElement("canvas"); canvas.width = 192; canvas.height = 108;
    var context = canvas.getContext("2d");
    for (var idx = 0; idx < scores.length; idx += 1) {
      var t = Math.max(0, scores[idx].payload.t);
      var thumbnail = "";
      try {
        if (Number.isFinite(player.duration) && player.duration > 0) {
          player.currentTime = Math.min(t, player.duration);
          await new Promise(function (resolve) { player.onseeked = resolve; setTimeout(resolve, 1200); });
          context.drawImage(player, 0, 0, canvas.width, canvas.height);
          thumbnail = canvas.toDataURL("image/jpeg", 0.65);
        }
      } catch (e) { thumbnail = ""; }
      var button = document.createElement("button"); button.type = "button";
      button.style.left = (5 + (t / maxTime) * 90) + "%";
      button.setAttribute("aria-label", "Show frame at " + t.toFixed(2) + " seconds, risk " + scores[idx].payload.score);
      if (thumbnail) { var img = document.createElement("img"); img.src = thumbnail; img.alt = "Frame at " + t.toFixed(2) + " seconds"; button.appendChild(img); }
      var caption = document.createElement("span"); caption.textContent = t.toFixed(1) + "s · " + scores[idx].payload.score; button.appendChild(caption);
      button.addEventListener("click", function (time) { return function () { var preview = root.querySelector("video"); if (preview && Number.isFinite(preview.duration)) preview.currentTime = Math.min(time, preview.duration); }; }(t));
      strip.appendChild(button);
      var x = 50 + (t / maxTime) * 900;
      var y = 100 - Math.max(0, Math.min(1, scores[idx].payload.score)) * 90;
      points.push(x.toFixed(1) + "," + y.toFixed(1));
    }
    player.removeAttribute("src"); player.load();
    var poly = document.createElementNS("http://www.w3.org/2000/svg", "polyline");
    poly.setAttribute("points", points.join(" ")); poly.setAttribute("fill", "none"); poly.setAttribute("stroke", "currentColor"); poly.setAttribute("stroke-width", "2"); chart.appendChild(poly);
    [0.35, 0.70].forEach(function (value) { var y = 100 - value * 90; var line = document.createElementNS("http://www.w3.org/2000/svg", "line"); line.setAttribute("x1", "24"); line.setAttribute("x2", "980"); line.setAttribute("y1", String(y)); line.setAttribute("y2", String(y)); line.setAttribute("stroke", "currentColor"); line.setAttribute("stroke-dasharray", "4 5"); line.setAttribute("opacity", ".45"); chart.appendChild(line); });
    scores.forEach(function (ev, idx) { var circle = document.createElementNS("http://www.w3.org/2000/svg", "circle"); circle.setAttribute("cx", String(50 + (ev.payload.t / maxTime) * 900)); circle.setAttribute("cy", String(100 - Math.max(0, Math.min(1, ev.payload.score)) * 90)); circle.setAttribute("r", "5"); circle.setAttribute("tabindex", "0"); circle.setAttribute("role", "button"); circle.setAttribute("aria-label", "Frame " + (idx + 1) + ", " + ev.payload.t + " seconds, risk " + ev.payload.score); circle.addEventListener("click", function () { var preview = root.querySelector("video"); if (preview && Number.isFinite(preview.duration)) preview.currentTime = Math.min(ev.payload.t, preview.duration); }); circle.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); circle.click(); } }); chart.appendChild(circle); });
  }

  function showRecords() {
    els.deskGrid.hidden = true;
    els.records.hidden = false;
    els.recordsLink.setAttribute("aria-current", "page");
  }

  function showDesk() {
    els.records.hidden = true;
    els.deskGrid.hidden = false;
    els.recordsLink.removeAttribute("aria-current");
    els.deskLink.setAttribute("aria-current", "page");
  }

  function renderConfusion(matrix) {
    if (!matrix || typeof matrix !== "object" || !Object.keys(matrix).length) return "<p class=\"muted\">Not evaluated.</p>";
    var labels = Object.keys(matrix);
    var html = "<div class=\"records-table\"><table><thead><tr><th>Actual \\ Predicted</th>";
    labels.forEach(function (label) { html += "<th>" + escapeHtml(label) + "</th>"; });
    html += "</tr></thead><tbody>";
    labels.forEach(function (actual) {
      html += "<tr><th>" + escapeHtml(actual) + "</th>";
      labels.forEach(function (predicted) {
        var value = matrix[actual] && matrix[actual][predicted];
        html += "<td class=\"num\">" + (typeof value === "number" ? value : "—") + "</td>";
      });
      html += "</tr>";
    });
    return html + "</tbody></table></div>";
  }

  function activePrimary(data, modality) {
    var sources = [data.active_primary, data.primary_by_modality, data.primaries];
    for (var i = 0; i < sources.length; i += 1) {
      var source = sources[i];
      if (source && typeof source === "object" && source[modality]) {
        var item = source[modality];
        return typeof item === "string" ? item : item.version || item.model_version || item.provider || "";
      }
    }
    var promos = Array.isArray(data.promotions) ? data.promotions : [];
    var selected = promos.slice().reverse().find(function (p) { return p && p.modality === modality && (p.active === true || p.status === "promoted"); });
    return selected && (selected.version || selected.model_version || selected.primary_provider) || "";
  }

  function renderRecords(data) {
    var models = data && data.models && typeof data.models === "object" ? data.models : {};
    var modalities = ["text", "email", "image", "video"];
    var html = "<section class=\"section\"><h3>Active primary by modality</h3><div class=\"records-table\"><table><thead><tr><th>Modality</th><th>Primary</th></tr></thead><tbody>";
    modalities.forEach(function (modality) {
      html += "<tr><th>" + modality + "</th><td>" + (activePrimary(data, modality) ? escapeHtml(activePrimary(data, modality)) : "<span class=\"muted\">Not recorded</span>") + "</td></tr>";
    });
    html += "</tbody></table></div></section>";
    var versions = Object.keys(models).sort();
    html += "<section class=\"section\"><h3>Model evaluations</h3>";
    if (!versions.length) html += "<p class=\"muted\">Not evaluated.</p>";
    versions.forEach(function (version) {
      var item = models[version] || {};
      var metrics = item.metrics || {};
      var perClass = metrics.per_class || {};
      html += "<article class=\"record-model\"><h4>" + escapeHtml(version) + " · " + escapeHtml(item.modality || "unknown modality") + "</h4>";
      if (typeof metrics.accuracy !== "number" && typeof metrics.macro_f1 !== "number") html += "<p class=\"muted\">Not evaluated.</p>";
      else {
        html += "<dl class=\"record-stats\">";
        html += "<div><dt>Accuracy</dt><dd>" + (typeof metrics.accuracy === "number" ? metrics.accuracy : "Not evaluated") + "</dd></div>";
        html += "<div><dt>Macro F1</dt><dd>" + (typeof metrics.macro_f1 === "number" ? metrics.macro_f1 : "Not evaluated") + "</dd></div>";
        html += "<div><dt>Holdout</dt><dd>" + escapeHtml(item.holdout_version || "Not recorded") + "</dd></div></dl>";
        if (Object.keys(perClass).length) {
          html += "<div class=\"records-table\"><table><thead><tr><th>Class</th><th>Precision</th><th>Recall</th><th>F1</th></tr></thead><tbody>";
          Object.keys(perClass).sort().forEach(function (label) { var score = perClass[label]; html += "<tr><th>" + escapeHtml(label) + "</th><td class=\"num\">" + (typeof score.precision === "number" ? score.precision : "—") + "</td><td class=\"num\">" + (typeof score.recall === "number" ? score.recall : "—") + "</td><td class=\"num\">" + (typeof score.f1_score === "number" ? score.f1_score : "—") + "</td></tr>"; });
          html += "</tbody></table></div>";
        }
        html += "<details><summary>Confusion matrix</summary>" + renderConfusion(metrics.confusion_matrix) + "</details>";
      }
      html += "</article>";
    });
    els.recordsContent.innerHTML = html + "</section>";
  }

  async function loadRecords() {
    showRecords();
    els.deskLink.removeAttribute("aria-current");
    els.recordsContent.innerHTML = "<p class=\"muted\">Loading model records…</p>";
    try {
      var response = await fetch("/api/metrics");
      if (!response.ok) throw new Error("Metrics unavailable");
      renderRecords(await response.json());
    } catch (e) {
      els.recordsContent.innerHTML = "<div class=\"glass panel-fail\"><p>Couldn't load model records.</p><p>Check the connection, then open Records again.</p></div>";
    }
  }

  function tickRisk(target) {
    var node = document.getElementById("risk-value");
    if (!node || typeof target !== "number" || reduceMotion()) {
      if (node && typeof target === "number") node.textContent = String(target);
      return;
    }
    var start = performance.now();
    var from = 0;
    function frame(now) {
      var t = Math.min(1, (now - start) / 200);
      var value = from + (target - from) * t;
      node.textContent = value.toFixed(2);
      if (t < 1) {
        requestAnimationFrame(frame);
      } else {
        node.textContent = String(target);
      }
    }
    requestAnimationFrame(frame);
  }

  function renderFail(status, body, providers) {
    var copy = errorCopy(status, body);
    var html = "<p>" + escapeHtml(copy.happened) + "</p>";
    var counts = countOk(providers);
    if (counts.total) {
      html += "<p class=\"muted\">" + counts.ok + " of " + counts.total + " providers answered.</p>";
    } else if (status === 503) {
      html += "<p class=\"muted\">0 of the configured providers answered. No score is shown.</p>";
    }
    html += "<p>" + escapeHtml(copy.next) + "</p>";
    els.msgFail.innerHTML = html;
    setLaneMode(els.msgLane, "fail");
  }

  function renderHistory() {
    if (!message.history.length) {
      els.msgHistoryWrap.hidden = true;
      return;
    }
    els.msgHistoryWrap.hidden = false;
    els.msgHistory.innerHTML = "";
    message.history.forEach(function (item, idx) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      var v = item.verdict;
      btn.innerHTML = "<span class=\"caps\">" + escapeHtml(caseRef(v.id)) + "</span> · " +
        escapeHtml(v.level || "") + " · " + escapeHtml(v.label || "");
      btn.addEventListener("click", function () {
        message.text = item.text;
        message.file = item.file;
        message.verdict = v;
        els.msgInput.value = item.text;
        els.msgName.textContent = item.file ? item.file.name : "";
        setLaneMode(els.msgLane, "result");
        renderResult(v, item.text);
      });
      li.appendChild(btn);
      els.msgHistory.appendChild(li);
      if (idx >= 7) return;
    });
  }

  function decodeMimePart(raw, filename) {
    var lines = raw.replace(/\r\n/g, "\n").split("\n");
    var boundaryMatch = raw.match(/boundary\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
    if (!boundaryMatch) return null;
    var boundary = "--" + (boundaryMatch[1] || boundaryMatch[2]);
    var blocks = raw.split(boundary);
    for (var i = 1; i < blocks.length; i += 1) {
      var block = blocks[i].replace(/^\r?\n/, "").replace(/\r?\n--\s*$/, "");
      var split = block.search(/\r?\n\r?\n/);
      if (split < 0) continue;
      var headers = block.slice(0, split);
      var content = block.slice(split).replace(/^\r?\n\r?\n/, "").replace(/\r?\n$/, "");
      var nameMatch = headers.match(/filename\*?\s*=\s*(?:UTF-8''([^;\r\n]+)|"([^"]+)"|([^;\r\n]+))/i);
      var name = nameMatch && decodeURIComponent(nameMatch[1] || nameMatch[2] || nameMatch[3]).replace(/^.*[\\/]/, "");
      var nestedType = headers.match(/content-type\s*:\s*([^;\r\n]+)/i);
      var nestedBoundary = headers.match(/boundary\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
      if (nestedBoundary && content.indexOf("--" + (nestedBoundary[1] || nestedBoundary[2])) !== -1) {
        var nested = decodeMimePart("Content-Type: " + nestedType[1] + "; boundary=\"" + (nestedBoundary[1] || nestedBoundary[2]) + "\"\r\n\r\n" + content, filename);
        if (nested) return nested;
      }
      if (name !== filename) continue;
      var encoding = (headers.match(/content-transfer-encoding\s*:\s*([^\r\n]+)/i) || ["", ""])[1].trim().toLowerCase();
      var mime = (nestedType || ["", "application/octet-stream"])[1].trim();
      try {
        if (encoding === "base64") {
          var binary = atob(content.replace(/\s/g, ""));
          var bytes = new Uint8Array(binary.length);
          for (var b = 0; b < binary.length; b += 1) bytes[b] = binary.charCodeAt(b);
          return new File([bytes], filename, { type: mime });
        }
        if (encoding === "quoted-printable") content = content.replace(/=\n/g, "").replace(/=([0-9A-F]{2})/gi, function (_, hex) { return String.fromCharCode(parseInt(hex, 16)); });
        return new File([content], filename, { type: mime });
      } catch (e) { return null; }
    }
    return null;
  }

  function decodeEmailBody(raw) {
    var boundaryMatch = raw.match(/boundary\s*=\s*(?:"([^"]+)"|([^;\s]+))/i);
    if (!boundaryMatch) {
      var bodyStart = raw.search(/\r?\n\r?\n/);
      return bodyStart < 0 ? raw : raw.slice(bodyStart).replace(/^\r?\n\r?\n/, "");
    }
    var boundary = "--" + (boundaryMatch[1] || boundaryMatch[2]);
    var blocks = raw.split(boundary);
    var fallback = "";
    for (var i = 1; i < blocks.length; i += 1) {
      var block = blocks[i].replace(/^\r?\n/, "");
      var split = block.search(/\r?\n\r?\n/);
      if (split < 0) continue;
      var headers = block.slice(0, split);
      var content = block.slice(split).replace(/^\r?\n\r?\n/, "").replace(/\r?\n--\s*$/, "").replace(/\r?\n$/, "");
      if (/content-disposition\s*:\s*attachment/i.test(headers)) continue;
      if (!/content-type\s*:\s*text\/(plain|html)/i.test(headers)) continue;
      if (!fallback) fallback = content;
      if (!/content-type\s*:\s*text\/plain/i.test(headers)) continue;
      var encoding = (headers.match(/content-transfer-encoding\s*:\s*([^\r\n]+)/i) || ["", ""])[1].trim().toLowerCase();
      if (encoding === "base64") {
        try { var binary = atob(content.replace(/\s/g, "")); var bytes = new Uint8Array(binary.length); for (var j = 0; j < binary.length; j += 1) bytes[j] = binary.charCodeAt(j); return new TextDecoder().decode(bytes); } catch (e) { return content; }
      }
      if (encoding === "quoted-printable") return content.replace(/=\n/g, "").replace(/=([0-9A-F]{2})/gi, function (_, hex) { return String.fromCharCode(parseInt(hex, 16)); });
      return content;
    }
    return fallback || raw;
  }

  async function sendToMedia(filename) {
    if (!filename) return;
    var copied = null;
    var attachment = attachmentsFrom(message.verdict && message.verdict.evidence).find(function (ev) {
      return ev.payload && ev.payload.filename === filename;
    });
    if (attachment && attachment.payload.content_b64) {
      try {
        var bin = atob(attachment.payload.content_b64);
        var bytes = new Uint8Array(bin.length);
        for (var i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        copied = new File([bytes], filename, { type: attachment.payload.type || "application/octet-stream" });
      } catch (e) { copied = null; }
    }
    if (!copied && message.file && /\.eml$/i.test(message.file.name)) {
      try { copied = decodeMimePart(await message.file.text(), filename); } catch (e) { copied = null; }
    }
    if (!copied) {
      els.msgFail.textContent = "This attachment's file data is not available in the email. Choose the original file from the Media tray.";
      setLaneMode(els.msgLane, "fail");
      return;
    }
    await onMediaFile(copied);
    els.mediaTray.classList.add("is-dragover");
    setTimeout(function () { els.mediaTray.classList.remove("is-dragover"); }, 200);
  }

  async function analyze() {
    var text = els.msgInput.value;
    var file = message.file;
    if (file) {
      if (!text) {
        try {
          text = await file.text();
          if (/\.eml$/i.test(file.name)) text = decodeEmailBody(text);
        } catch (e) {
          text = "";
        }
      }
    }
    message.text = text;
    if (!file && !String(text).trim()) {
      renderFail(400, { detail: "Paste a message or choose a .txt or .eml file." }, []);
      return;
    }

    setLaneMode(els.msgLane, "loading");
    els.msgTray.classList.add("is-loading");
    var step = 0;
    els.msgStep.textContent = STEPS[0];
    var timer = setInterval(function () {
      step = (step + 1) % STEPS.length;
      els.msgStep.textContent = STEPS[step];
    }, 180);

    var result;
    if (MOCK) {
      result = await mockAnalyze(text, file ? file.name : "");
    } else {
      result = await liveAnalyze(text, file);
    }
    clearInterval(timer);
    els.msgTray.classList.remove("is-loading");

    if (!result.ok) {
      renderFail(result.status, result.body, result.body && result.body.providers);
      return;
    }
    var v = result.body;
    if (!v || typeof v !== "object" || !v.id) {
      renderFail(500, { detail: "The response did not include a verdict id." }, []);
      return;
    }
    message.verdict = v;
    updatePrivacyChip(els.msgPrivacy, v.external_used);
    message.history.unshift({ text: text, file: file, verdict: v });
    if (message.history.length > 8) message.history.length = 8;
    setLaneMode(els.msgLane, "result");
    renderResult(v, text);
    renderHistory();
  }

  function mediaFailure(message) {
    els.mediaFail.innerHTML = "<p>" + escapeHtml(message) + "</p><p>Choose a supported file or try again.</p>";
    setLaneMode(els.mediaLane, "fail");
  }

  async function analyzeMedia() {
    var file = media.file;
    if (!file) { mediaFailure("Choose an image or video first."); return; }
    var kind = mediaKind(file);
    if (!kind) { mediaFailure("This file type is not supported."); return; }
    if (kind === "image" && file.size > 10 * 1024 * 1024) { mediaFailure("This image is larger than 10 MB."); return; }
    if (kind === "video" && file.size > 50 * 1024 * 1024) { mediaFailure("This video is larger than 50 MB."); return; }
    if (kind === "video" && media.duration !== null && media.duration > 60) { mediaFailure("This video is longer than 60 seconds."); return; }
    setLaneMode(els.mediaLane, "loading");
    els.mediaTray.classList.add("is-loading");
    var result = MOCK ? await mockMediaAnalyze(file) : await liveAnalyzeMedia(file);
    els.mediaTray.classList.remove("is-loading");
    if (!result.ok) {
      var detail = result.status === 404 ? "Media analysis is not available on this server yet." :
        result.status === 0 ? "Couldn't reach the analysis service." :
        result.status === 413 ? "This media file exceeds the server's size limit." :
        result.status === 415 || result.status === 400 ? "This media file could not be analysed." :
        "The media analysis service returned an error.";
      els.mediaFail.innerHTML = "<p>" + detail + "</p><p>Try again later or choose another supported file.</p>";
      setLaneMode(els.mediaLane, "fail");
      return;
    }
    var verdict = result.body;
    if (!verdict || !verdict.id || typeof verdict.risk !== "number") { mediaFailure("The response did not contain a complete media verdict."); return; }
    media.verdict = verdict;
    updatePrivacyChip(els.mediaPrivacy, verdict.external_used);
    setLaneMode(els.mediaLane, "result");
    renderMediaResult(verdict, file);
  }

  function bindDrop(tray, onFile) {
    tray.addEventListener("keydown", function (ev) {
      if (ev.target !== tray) return;
      if (ev.key === "Enter" || ev.key === " ") {
        ev.preventDefault();
        var chooser = tray.id === "message-tray" ? els.msgFile : els.mediaFile;
        chooser.click();
      }
    });
    tray.addEventListener("dragover", function (ev) {
      ev.preventDefault();
      tray.classList.add("is-dragover");
    });
    tray.addEventListener("dragleave", function () {
      tray.classList.remove("is-dragover");
    });
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
    var okExt = /\.(txt|eml)$/i.test(file.name);
    if (!okExt) {
      renderFail(400, { detail: "Unsupported file. Use .txt or .eml." }, []);
      return;
    }
    file.text().then(function (t) {
      if (/\.eml$/i.test(file.name)) t = decodeEmailBody(t);
      els.msgInput.value = t;
      message.text = t;
    }).catch(function () {
      /* keep filename only */
    });
  }

  async function onMediaFile(file) {
    if (media.objectUrl) URL.revokeObjectURL(media.objectUrl);
    media.objectUrl = null;
    media.file = null;
    els.mediaName.textContent = "";
    var kind = mediaKind(file);
    if (!kind) { mediaFailure("Use a JPG, PNG, WebP, MP4, MOV, AVI, WAV, or MP3 file."); return; }
    if (kind === "image" && file.size > 10 * 1024 * 1024) { mediaFailure("This image is larger than 10 MB."); return; }
    if (kind === "video" && file.size > 50 * 1024 * 1024) { mediaFailure("This video is larger than 50 MB."); return; }
    if (kind === "audio" && file.size > 50 * 1024 * 1024) { mediaFailure("This audio file is larger than 50 MB."); return; }
    media.file = file;
    media.pendingName = file.name;
    media.duration = null;
    if (kind === "video") {
      var info = await inspectVideo(file);
      media.duration = info.duration;
      media.objectUrl = info.url;
      if (info.duration !== null && info.duration > 60) { mediaFailure("This video is longer than 60 seconds."); return; }
    } else {
      media.objectUrl = URL.createObjectURL(file);
    }
    els.mediaName.textContent = file.name;
    media.verdict = null;
    setLaneMode(els.mediaLane, "empty");
  }

  function mountExamples() {
    if (!MOCK) return;
    els.msgExamples.hidden = false;
    var keys = ["low", "email", "high", "disagree", "partial", "fail"];
    keys.forEach(function (key) {
      if (!fixtures[key]) return;
      var btn = document.createElement("button");
      btn.type = "button";
      var labels = { low: "Safe message", email: "Phishing email", high: "Threat", disagree: "Providers disagree", partial: "One provider down", fail: "All providers down" };
      btn.textContent = labels[key] || key;
      btn.addEventListener("click", function () {
        if (key === "email") {
          var blob = new File([samples.email || ""], "invoice.eml");
          onMessageFile(blob);
          els.msgInput.value = samples.email || "";
        } else {
          message.file = null;
          els.msgName.textContent = "";
          els.msgInput.value = samples[key] || "";
        }
        analyze();
      });
      els.msgExamples.appendChild(btn);
    });
  }

  els.theme.addEventListener("click", function () {
    var next = els.html.getAttribute("data-theme") === "dark" ? "light" : "dark";
    applyTheme(next);
  });
  els.recordsLink.addEventListener("click", function (ev) { ev.preventDefault(); loadRecords(); });
  els.recordsBack.addEventListener("click", showDesk);
  els.deskLink.addEventListener("click", function (ev) { ev.preventDefault(); showDesk(); });
  els.msgChoose.addEventListener("click", function () { els.msgFile.click(); });
  els.mediaChoose.addEventListener("click", function () { els.mediaFile.click(); });
  els.msgFile.addEventListener("change", function () {
    if (els.msgFile.files[0]) onMessageFile(els.msgFile.files[0]);
  });
  els.mediaFile.addEventListener("change", function () {
    if (els.mediaFile.files[0]) onMediaFile(els.mediaFile.files[0]);
  });
  els.mediaAnalyze.addEventListener("click", analyzeMedia);
  els.msgAnalyze.addEventListener("click", function () { analyze(); });
  els.msgInput.addEventListener("keydown", function (ev) {
    if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) {
      ev.preventDefault();
      analyze();
    }
  });
  bindDrop(els.msgTray, onMessageFile);
  bindDrop(els.mediaTray, onMediaFile);

  if (MOCK) {
    els.mockChip.hidden = false;
  }
  initTheme();
  mountExamples();
})();
