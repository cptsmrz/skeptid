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

  // --- DAY & NIGHT OPS THEME CONTROLLER ---
  const THEME_KEY = 'skeptid_ops_theme';
  const DEFAULT_THEME = 'theme-night'; // 'theme-night' or 'theme-day'

  function initTheme() {
    detectMobileOS();
    const saved = localStorage.getItem(THEME_KEY) || DEFAULT_THEME;
    applyTheme(saved);

    const opsBtn = document.getElementById('ops-theme-toggle');
    if (opsBtn) {
      opsBtn.addEventListener('click', () => {
        const current = document.body.classList.contains('theme-day') ? 'theme-night' : 'theme-day';
        applyTheme(current);
      });
    }

    // Legacy fallback buttons if present
    const btnGlass = document.getElementById('theme-btn-glass');
    const btnFrozen = document.getElementById('theme-btn-frozen');
    if (btnGlass && btnFrozen) {
      btnGlass.addEventListener('click', () => applyTheme('theme-night'));
      btnFrozen.addEventListener('click', () => applyTheme('theme-day'));
    }
  }

  function applyTheme(theme) {
    const isDay = theme === 'theme-day' || theme === 'theme-frozen-glass';
    document.body.classList.remove('theme-night', 'theme-day', 'theme-glassmorphism', 'theme-frozen-glass');
    document.body.classList.add(isDay ? 'theme-day' : 'theme-night');
    localStorage.setItem(THEME_KEY, isDay ? 'theme-day' : 'theme-night');

    const opsIcon = document.getElementById('ops-theme-icon');
    const opsText = document.getElementById('ops-theme-text');
    if (opsIcon && opsText) {
      opsIcon.textContent = isDay ? '☀️' : '🌙';
      opsText.textContent = isDay ? 'DAY OPS' : 'NIGHT OPS';
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

  // --- MODALITY HELPERS ---
  function getIncludeExternal() {
    const el = document.getElementById('hub-external-toggle');
    return el ? el.checked : true;
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
            const modality = config.modality;

            if (modality === 'text') {
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
            } else if (modality === 'binary') {
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
              // Media: Audio / Image / Video / Omni
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
                window.SkeptidDesk.renderResult(data, currentFile, config);
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
      const label = data.label || 'ANALYSIS COMPLETE';
      const riskPct = Math.round((data.risk || 0) * 100);
      const confPct = Math.round((data.confidence || 0) * 100);

      let mediaPreviewHtml = '';
      if (file && config.modality === 'audio') {
        const fileUrl = URL.createObjectURL(file);
        mediaPreviewHtml = `
          <div class="media-preview-box">
            <audio controls src="${fileUrl}" class="audio-player-custom"></audio>
            <div class="metric-label" style="margin-bottom: 6px;">16-Band Mel Power Spectrogram</div>
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
      } else if (file && config.modality === 'image') {
        const imgUrl = URL.createObjectURL(file);
        mediaPreviewHtml = `
          <div class="media-preview-box" style="text-align: center;">
            <img src="${imgUrl}" alt="Analysis Target" style="max-height: 240px; border-radius: 8px; border: 1px solid var(--glass-border); max-width: 100%;">
          </div>
        `;
      }

      // Format Evidence items
      const evidenceItems = (data.evidence || [])
        .map(
          (ev) => `
        <div class="evidence-card">
          <div class="evidence-title">${ev.kind ? ev.kind.toUpperCase() : 'SIGNAL'}: ${ev.description || 'Forensic indicator'}</div>
          ${ev.details ? `<div class="evidence-desc"><code>${JSON.stringify(ev.details)}</code></div>` : ''}
        </div>
      `
        )
        .join('');

      resultPanel.innerHTML = `
        <div class="result-verdict-header">
          <div>
            <span class="verdict-badge ${badgeClass}">${level} RISK // ${label}</span>
          </div>
          <div class="risk-metrics-row">
            <div class="metric-item">
              <span class="metric-label">Risk Score</span>
              <span class="metric-val">${riskPct}%</span>
            </div>
            <div class="metric-item">
              <span class="metric-label">Confidence</span>
              <span class="metric-val">${confPct}%</span>
            </div>
          </div>
        </div>

        ${mediaPreviewHtml}

        <div style="margin-top: 1.25rem;">
          <h3 style="font-size: 0.95rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase; font-family: var(--font-mono); color: var(--text-muted);">
            Forensic Evidence Trail
          </h3>
          <div class="evidence-list">
            ${evidenceItems || '<div class="evidence-card"><div class="evidence-desc">No high-risk anomalies detected. Signature matches benign baseline.</div></div>'}
          </div>
        </div>
      `;
    },
  };
})();
