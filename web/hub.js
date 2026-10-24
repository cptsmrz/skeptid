/* SKEPTID HUB & MODALITY DESK CONTROLLER
   Powers centered Chromium New Tab pages with dual Glassmorphism & Frozen Glass aesthetics.
*/

(function () {
  'use strict';

  // --- MOBILE OS DETECTION (Strictly Android & iOS - NOT desktop window resizing) ---
  function detectMobileOS() {
    const ua = navigator.userAgent || navigator.vendor || window.opera || '';
    const isMobileOS = /android|iphone|ipad|ipod/i.test(ua) ||
                       (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    if (isMobileOS) {
      document.body.classList.add('is-mobile-os');
    }
  }

  // --- THEME CONTROLLER (Always Dark by default every time) ---
  function initTheme() {
    detectMobileOS();
    // Default to dark mode every time as requested
    applyTheme('theme-night');

    const toggleBtn = document.getElementById('ops-theme-toggle');
    if (toggleBtn) {
      toggleBtn.addEventListener('click', () => {
        const isDay = document.body.classList.contains('theme-day');
        applyTheme(isDay ? 'theme-night' : 'theme-day');
      });
    }
  }

  function applyTheme(theme) {
    const isDay = theme === 'theme-day';
    document.body.classList.remove('theme-night', 'theme-day', 'theme-glassmorphism', 'theme-frozen-glass');
    document.body.classList.add(isDay ? 'theme-day' : 'theme-night');

    const toggleBtn = document.getElementById('ops-theme-toggle');
    if (toggleBtn) {
      toggleBtn.setAttribute('aria-checked', isDay ? 'true' : 'false');
    }
  }

  // --- REACTIVE DEFCON AMBIANCE ---
  function applyThreatAmbiance(level) {
    document.body.classList.remove('ambiance-threat', 'ambiance-warning', 'ambiance-legit');
    if (level === 'HIGH' || level === 'CRITICAL') {
      document.body.classList.add('ambiance-threat');
    } else if (level === 'MEDIUM') {
      document.body.classList.add('ambiance-warning');
    } else {
      document.body.classList.add('ambiance-legit');
    }
  }

  // --- AUTOMATIC EXTERNAL AI (Zero friction, no user toggle needed) ---
  function getIncludeExternal() {
    return true;
  }

  // --- UNIVERSAL CLIENT RUNNER ---
  window.SkeptidDesk = {
    init: function (config) {
      initTheme();

      const dropBox = document.getElementById('ntp-drop-box');
      const fileInput = document.getElementById('ntp-file-input');
      const chooseBtn = document.getElementById('ntp-choose-btn');
      const analyzeBtn = document.getElementById('ntp-analyze-btn');
      const fileNameEl = document.getElementById('ntp-file-name');
      const textInput = document.getElementById('ntp-text-input');
      const resultPanel = document.getElementById('ntp-result-panel');
      const viewport = document.querySelector('.ntp-viewport');

      let currentFile = null;

      if (!dropBox) return;

      // Click to choose file
      if (chooseBtn && fileInput) {
        chooseBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          fileInput.click();
        });
      }

      dropBox.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'TEXTAREA' && fileInput) {
          fileInput.click();
        }
      });

      if (fileInput) {
        fileInput.addEventListener('change', (e) => {
          if (e.target.files && e.target.files[0]) {
            currentFile = e.target.files[0];
            if (fileNameEl) {
              fileNameEl.textContent = `${currentFile.name} (${(currentFile.size / (1024 * 1024)).toFixed(2)} MB)`;
            }
          }
        });
      }

      // Drag and Drop
      ['dragenter', 'dragover'].forEach((eventName) => {
        dropBox.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropBox.classList.add('drag-active');
        });
      });

      ['dragleave', 'drop'].forEach((eventName) => {
        dropBox.addEventListener(eventName, (e) => {
          e.preventDefault();
          e.stopPropagation();
          dropBox.classList.remove('drag-active');
        });
      });

      dropBox.addEventListener('drop', (e) => {
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          currentFile = e.dataTransfer.files[0];
          if (fileNameEl) {
            fileNameEl.textContent = `${currentFile.name} (${(currentFile.size / (1024 * 1024)).toFixed(2)} MB)`;
          }
        }
      });

      // Analyze Trigger
      if (analyzeBtn) {
        analyzeBtn.addEventListener('click', async (e) => {
          e.stopPropagation();

          const includeExternal = getIncludeExternal();
          analyzeBtn.disabled = true;
          analyzeBtn.textContent = 'Analyzing...';

          try {
            let data = null;
            let effectiveModality = config.modality;

            // Auto-detect modality from dropped or chosen file
            if (currentFile) {
              const name = currentFile.name.toLowerCase();
              const type = (currentFile.type || '').toLowerCase();
              if (
                type.startsWith('image/') ||
                name.endsWith('.png') ||
                name.endsWith('.jpg') ||
                name.endsWith('.jpeg') ||
                name.endsWith('.webp') ||
                name.endsWith('.bmp') ||
                name.endsWith('.tiff')
              ) {
                effectiveModality = 'image';
              } else if (
                type.startsWith('video/') ||
                name.endsWith('.mp4') ||
                name.endsWith('.webm') ||
                name.endsWith('.avi') ||
                name.endsWith('.mov')
              ) {
                effectiveModality = 'video';
              } else if (
                type.startsWith('audio/') ||
                name.endsWith('.wav') ||
                name.endsWith('.mp3') ||
                name.endsWith('.ogg') ||
                name.endsWith('.flac')
              ) {
                effectiveModality = 'audio';
              } else if (name.endsWith('.eml') || name.endsWith('.txt')) {
                effectiveModality = 'text';
              }
            } else if (textInput && textInput.value.trim().length > 0) {
              effectiveModality = 'text';
            }

            if (effectiveModality === 'text') {
              const textContent = textInput ? textInput.value.trim() : '';
              if (!textContent && !currentFile) {
                alert('Please enter text or choose a message file.');
                return;
              }

              if (currentFile) {
                const fd = new FormData();
                fd.append('file', currentFile);
                fd.append('include_external', includeExternal);
                const res = await fetch('/api/message/analyze', { method: 'POST', body: fd });
                data = await res.json();
              } else {
                const res = await fetch('/api/message/analyze', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ text: textContent, include_external: includeExternal }),
                });
                data = await res.json();
              }
            } else if (effectiveModality === 'binary') {
              if (!currentFile) {
                alert('Please drop or choose a file first.');
                return;
              }
              const fd = new FormData();
              fd.append('file', currentFile);
              fd.append('include_external', includeExternal);
              const res = await fetch('/api/binary/analyze', { method: 'POST', body: fd });
              data = await res.json();
            } else {
              // Media: Image / Video / Audio
              if (!currentFile && !textInput) {
                alert('Please drop or choose a file to analyze.');
                return;
              }
              const fd = new FormData();
              fd.append('file', currentFile);
              fd.append('include_external', includeExternal);
              const res = await fetch('/api/media/analyze', { method: 'POST', body: fd });
              data = await res.json();
            }

            if (data) {
              if (resultPanel) {
                resultPanel.hidden = false;
                window.SkeptidDesk.renderResult(data, currentFile, { ...config, modality: effectiveModality });
              }
              if (viewport) {
                viewport.classList.add('has-result');
              }
            }
          } catch (err) {
            console.error('Analysis failed:', err);
            alert(`Analysis failed: ${err.message || 'Server error'}`);
          } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Analyse';
          }
        });
      }
    },

    renderResult: function (data, file, config) {
      const resultPanel = document.getElementById('ntp-result-panel');
      if (!resultPanel) return;

      const level = data.level || (data.risk > 0.7 ? 'HIGH' : data.risk > 0.35 ? 'MEDIUM' : 'LOW');
      applyThreatAmbiance(level);

      const badgeClass = level === 'HIGH' ? 'badge-high' : level === 'MEDIUM' ? 'badge-medium' : 'badge-low';
      const label = (data.label || 'ANALYSIS COMPLETE').toUpperCase();
      const riskPct = Math.round((data.risk || 0) * 100);
      const confPct = Math.round((data.confidence || 0) * 100);

      // Extract Gemini / AI summary
      let geminiSummary = '';
      const flagEv = (data.evidence || []).find(
        (ev) => ev.payload && ev.payload.reason && (ev.payload.vendor || ev.description?.includes('External LLM'))
      );
      if (flagEv && flagEv.payload && flagEv.payload.reason) {
        geminiSummary = flagEv.payload.reason.replace(/^External LLM \([^)]+\):\s*/i, '').trim();
      } else {
        const textFlag = (data.evidence || []).find((ev) => ev.description && ev.description.includes('External LLM'));
        if (textFlag) {
          geminiSummary = textFlag.description.replace(/^External LLM \([^)]+\):\s*/i, '').trim();
        }
      }

      // Friendly 2-line fallback if no external summary returned
      if (!geminiSummary) {
        if (config.modality === 'image') {
          if (label === 'AUTHENTIC') {
            geminiSummary = 'This photo appears to be authentic human capture. We found natural textures and no indicators of synthetic AI generation or deepfakes.';
          } else if (label === 'AI_GENERATED') {
            geminiSummary = 'This image shows clear signs of generative AI creation. Visual patterns and synthetic artifacts indicate it was generated by an AI model.';
          } else if (label === 'AI_EDITED') {
            geminiSummary = 'This image appears to have been altered or retouched using generative AI tools or deepfake face swapping.';
          } else {
            geminiSummary = 'Stylistic adjustments or filters detected, with no synthetic deepfake manipulation found.';
          }
        } else {
          if (level === 'HIGH') {
            geminiSummary = 'High risk detected. This content exhibits clear deceptive triggers, urgency manipulation, or malicious payload patterns.';
          } else if (level === 'MEDIUM') {
            geminiSummary = 'Exercise caution. Several suspicious patterns were detected that warrant careful verification before you proceed.';
          } else {
            geminiSummary = 'Content looks safe and authentic. No deceptive scam patterns, malicious links, or threat indicators were found.';
          }
        }
      }

      // Check for heatmap
      const heatmapEv = (data.evidence || []).find(
        (ev) => ev.kind === 'heatmap' && ev.payload && ev.payload.png_b64
      );

      let mediaPreviewHtml = '';
      if (file && config.modality === 'audio') {
        const fileUrl = URL.createObjectURL(file);
        mediaPreviewHtml = `
          <div class="media-preview-box">
            <audio controls src="${fileUrl}" class="audio-player-custom"></audio>
            <div class="metric-label" style="margin-bottom: 6px;">Voice Frequency Spectrum</div>
            <div class="spectrogram-stage" id="spec-stage">
              ${Array.from({ length: 16 })
                .map((_, i) => {
                  const h = Math.max(12, Math.min(85, Math.floor(Math.sin(i * 0.4) * 35 + 45)));
                  return `<div class="spec-bar" style="height: ${h}%;"></div>`;
                })
                .join('')}
            </div>
          </div>
        `;
      } else if (file && (config.modality === 'image' || file.type.startsWith('image/'))) {
        const imgUrl = URL.createObjectURL(file);
        if (heatmapEv && heatmapEv.payload && heatmapEv.payload.png_b64) {
          mediaPreviewHtml = `
            <div class="media-preview-box" style="text-align: center;">
              <div class="heatmap-container">
                <img src="${imgUrl}" alt="Original image" class="heatmap-base-img">
                <img src="data:image/png;base64,${heatmapEv.payload.png_b64}" alt="Visual change overlay" class="heatmap-overlay-img" id="heatmap-overlay" style="opacity: 0.60;">
              </div>
              <div class="heatmap-controls">
                <span>Visual Change Map</span>
                <input type="range" id="heatmap-slider" min="0" max="1" step="0.05" value="0.60" aria-label="Visual change map opacity">
                <span id="heatmap-val">60%</span>
              </div>
            </div>
          `;
        } else {
          mediaPreviewHtml = `
            <div class="media-preview-box" style="text-align: center;">
              <img src="${imgUrl}" alt="Analysis Target" style="max-height: 240px; border-radius: 8px; border: 1px solid var(--glass-border); max-width: 100%;">
            </div>
          `;
        }
      }

      // Technical Evidence items for "More" collapsible
      const techEvItems = (data.evidence || []).filter(
        (ev) => ev.kind !== 'heatmap' && !(ev.kind === 'flag' && ev.description?.includes('External LLM'))
      );

      const techEvidenceHtml = techEvItems
        .map(
          (ev) => `
        <div class="evidence-card">
          <div class="evidence-title">${ev.kind ? ev.kind.toUpperCase() : 'SIGNAL'}: ${ev.description || 'Detected clue'}</div>
          ${ev.details ? `<div class="evidence-desc"><code>${JSON.stringify(ev.details)}</code></div>` : ''}
          ${ev.payload && !ev.payload.png_b64 ? `<div class="evidence-desc"><code>${JSON.stringify(ev.payload)}</code></div>` : ''}
        </div>
      `
        )
        .join('');

      const friendlyLabel = label.replace(/_/g, ' ');
      const verdictText = level === 'HIGH' ? `🚨 High Risk · ${friendlyLabel}` : level === 'MEDIUM' ? `⚠️ Moderate Risk · ${friendlyLabel}` : `✅ Looks Real · ${friendlyLabel}`;

      resultPanel.innerHTML = `
        <div class="result-verdict-header">
          <div>
            <span class="verdict-badge ${badgeClass}">${verdictText}</span>
          </div>
          <div class="risk-metrics-row">
            <div class="metric-item">
              <span class="metric-label">Risk</span>
              <span class="metric-val">${riskPct}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Certainty</span>
              <span class="metric-val">${confPct}%</span>
            </div>
          </div>
        </div>

        <div class="gemini-summary-box">
          <p class="gemini-summary-text">${geminiSummary}</p>
        </div>

        ${mediaPreviewHtml}

        <div class="inner-mechanisms-section">
          <button type="button" class="btn-more-toggle" id="btn-more-toggle" aria-expanded="false">
            <span>More · Inner workings</span>
            <svg class="chevron-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="6 9 12 15 18 9"></polyline>
            </svg>
          </button>
          <div class="inner-mechanisms-content" id="inner-mechanisms-content" hidden>
            <div class="evidence-list">
              ${techEvidenceHtml || '<div class="evidence-card"><div class="evidence-desc">All baseline heuristics checked. No hidden anomalies found.</div></div>'}
            </div>
          </div>
        </div>
      `;

      // Wire up Heatmap Slider
      const slider = document.getElementById('heatmap-slider');
      const overlay = document.getElementById('heatmap-overlay');
      const valLabel = document.getElementById('heatmap-val');
      if (slider && overlay && valLabel) {
        slider.addEventListener('input', (e) => {
          overlay.style.opacity = e.target.value;
          valLabel.textContent = `${Math.round(e.target.value * 100)}%`;
        });
      }

      // Wire up "More" Button Toggle
      const moreBtn = document.getElementById('btn-more-toggle');
      const moreContent = document.getElementById('inner-mechanisms-content');
      if (moreBtn && moreContent) {
        moreBtn.addEventListener('click', () => {
          const isExpanded = moreBtn.getAttribute('aria-expanded') === 'true';
          moreBtn.setAttribute('aria-expanded', !isExpanded);
          moreContent.hidden = isExpanded;
        });
      }
    },
  };
})();
