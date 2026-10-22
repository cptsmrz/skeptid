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
    pendingName: ""
  };

  var els = {
    html: document.documentElement,
    mockChip: document.getElementById("mock-chip"),
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
    mediaName: document.getElementById("media-filename")
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
    if (/\.(mp4|webm)$/.test(name)) return "video";
    return "low";
  }

  function sleep(ms) {
    return new Promise(function (resolve) {
      setTimeout(resolve, ms);
    });
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

  async function liveAnalyze(text, file) {
    var res;
    try {
      if (file) {
        var form = new FormData();
        form.append("file", file, file.name);
        res = await fetch("/api/message/analyze", { method: "POST", body: form });
      } else {
        res = await fetch("/api/message/analyze", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: text })
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
      html += "<p class=\"muted\">" + (v.disagreement ? "Providers disagree" : "Providers agree") + ", spread " + spread.toFixed(2) + ".</p>";
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
        html += "<p class=\"muted\">Unavailable" + (p.error ? " — " + showField(p.error) : "") + "</p>";
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

  function renderResult(v, sourceText) {
    var mock = v.mock === true;
    els.mockChip.hidden = !(MOCK || mock);
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
    html += "<div class=\"stat\"><dt>Label</dt><dd>" + showField(v.level) + "</dd></div>";
    html += "</dl>";
    html += "<div class=\"risk-bar\" role=\"img\" aria-label=\"Risk score\"><span style=\"--risk:" + (typeof v.risk === "number" ? Math.max(0, Math.min(1, v.risk)) * 100 : 0) + "%\"></span><i class=\"tick tick-35\"></i><i class=\"tick tick-70\"></i></div>";
    if (v.limits_note) {
      html += "<p class=\"chip\">" + showField(v.limits_note) + "</p>";
    }
    html += "<div class=\"section evidence-section\"><h3>Highlighted spans</h3>" + highlight(sourceText, v.evidence) + "</div>";
    html += renderProviders(v);
    html += renderTables(v);
    els.msgResult.innerHTML = html;
    els.msgResult.querySelectorAll(".send-media").forEach(function (btn) {
      btn.addEventListener("click", function () {
        sendToMedia(btn.getAttribute("data-filename"));
      });
    });
    els.msgResult.querySelectorAll(".copy-id").forEach(function (btn) {
      btn.addEventListener("click", function () {
        if (navigator.clipboard && v.id) navigator.clipboard.writeText(v.id);
      });
    });
    tickRisk(v.risk);
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

  function sendToMedia(filename) {
    if (!filename) return;
    var file = new File([""], filename);
    media.file = file;
    media.pendingName = filename;
    els.mediaName.textContent = filename;
    els.mediaTray.classList.add("is-dragover");
    setTimeout(function () {
      els.mediaTray.classList.remove("is-dragover");
    }, 200);
  }

  async function analyze() {
    var text = els.msgInput.value;
    var file = message.file;
    if (file) {
      if (!text) {
        try {
          text = await file.text();
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
    message.history.unshift({ text: text, file: file, verdict: v });
    if (message.history.length > 8) message.history.length = 8;
    setLaneMode(els.msgLane, "result");
    renderResult(v, text);
    renderHistory();
  }

  function bindDrop(tray, onFile) {
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
      els.msgInput.value = t;
      message.text = t;
    }).catch(function () {
      /* keep filename only */
    });
  }

  function onMediaFile(file) {
    media.file = file;
    media.pendingName = file.name;
    els.mediaName.textContent = file.name;
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
  els.msgChoose.addEventListener("click", function () { els.msgFile.click(); });
  els.mediaChoose.addEventListener("click", function () { els.mediaFile.click(); });
  els.msgFile.addEventListener("change", function () {
    if (els.msgFile.files[0]) onMessageFile(els.msgFile.files[0]);
  });
  els.mediaFile.addEventListener("change", function () {
    if (els.mediaFile.files[0]) onMediaFile(els.mediaFile.files[0]);
  });
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
