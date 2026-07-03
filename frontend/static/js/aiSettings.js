/* ============================================================
   DS Generator — aiSettings.js
   Dashboard Settings & AI Interpretation functionality
   ============================================================ */

/* ─── DASHBOARD SETTINGS MODAL ────────────────────────────── */

function openSettingsModal() {
    var modal = document.getElementById('settingsModal');
    if (modal) {
        modal.classList.add('open');
        loadDashboardSettings();
    }
}

function closeSettingsModal() {
    var modal = document.getElementById('settingsModal');
    if (modal) modal.classList.remove('open');
}

function loadDashboardSettings() {
    var lang = localStorage.getItem('ds-lang') || 'en';
    var theme = localStorage.getItem('ds-theme') || 'system';

    var langSelect = document.getElementById('settings-language');
    var themeSelect = document.getElementById('settings-theme');

    if (langSelect) langSelect.value = lang;
    if (themeSelect) themeSelect.value = theme;
}

function saveDashboardSettings() {
    var langSelect = document.getElementById('settings-language');
    var themeSelect = document.getElementById('settings-theme');

    var lang = langSelect ? langSelect.value : 'en';
    var theme = themeSelect ? themeSelect.value : 'system';

    localStorage.setItem('ds-lang', lang);
    localStorage.setItem('ds-theme', theme);

    applyThemeSetting(theme);
    applyLanguageSetting(lang);

    if (typeof showToast === 'function') {
        var msg = typeof I18N !== 'undefined' ? I18N.t('settings_save_btn') : 'Dashboard settings saved.';
        showToast(msg, 'success');
    }
    closeSettingsModal();
}

function applyThemeSetting(theme) {
    var isDark;
    if (theme === 'dark') {
        isDark = true;
    } else if (theme === 'light') {
        isDark = false;
    } else {
        isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    }
    document.body.classList.toggle('dark-theme', isDark);
    document.body.classList.toggle('light-theme', !isDark);
    document.body.setAttribute('data-theme', isDark ? 'dark' : 'light');
    var icon = document.getElementById('theme-icon');
    if (icon) {
        icon.className = isDark ? 'fas fa-sun' : 'fas fa-moon';
        var langTheme2 = typeof I18N !== 'undefined' ? I18N.t : function(k) { return k; };
        icon.setAttribute('title', isDark ? langTheme2('theme_light') : langTheme2('theme_dark'));
    }
    /* Re-theme Plotly charts */
    setTimeout(function () {
        if (typeof Plotly === 'undefined') return;
        var fontColor = isDark ? 'var(--text-secondary)' : 'var(--text)';
        var gridColor = isDark ? 'rgba(255,255,255,0.06)' : 'var(--border)';
        document.querySelectorAll('[id^="plot-"],[id^="ov-"]').forEach(function (el) {
            if (el._fullData) {
                Plotly.relayout(el, {
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor : 'rgba(0,0,0,0)',
                    'font.color' : fontColor,
                    'xaxis.gridcolor'    : gridColor,
                    'yaxis.gridcolor'    : gridColor,
                    'xaxis.zerolinecolor': gridColor,
                    'yaxis.zerolinecolor': gridColor,
                });
            }
        });
    }, 80);
}

function applyLanguageSetting(lang) {
    if (typeof I18N !== 'undefined' && I18N.setLanguage) {
        I18N.setLanguage(lang);
    }
    document.documentElement.lang = lang;
}

/* Close modal on overlay click & Escape */
document.addEventListener('DOMContentLoaded', function () {
    var modal = document.getElementById('settingsModal');
    if (modal) {
        modal.addEventListener('click', function (e) {
            if (e.target === modal) closeSettingsModal();
        });
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && modal.classList.contains('open')) {
                closeSettingsModal();
            }
        });
    }
});

/* ─── INTERPRETATION AUTO-GENERATE ───────────────────────── */

var _interpretationGenerated = false;

function autoGenerateInterpretation() {
    var filename = getFileName();
    if (!filename) return;
    var resultEl = document.getElementById('interpretation-result');
    if (resultEl && resultEl.style.display === 'block') return;

    var hasAiKey = typeof vizMeta !== 'undefined' && vizMeta.has_ai_key;
    if (!hasAiKey) return;

    var cached = loadInterpretationCache(filename);
    if (cached) {
        renderInterpretationResult(cached);
        if (resultEl) resultEl.style.display = 'block';
        if (document.getElementById('interpretation-empty')) document.getElementById('interpretation-empty').style.display = 'none';
        if (document.getElementById('interpretation-loading')) document.getElementById('interpretation-loading').style.display = 'none';
        if (document.getElementById('interpretation-quota')) document.getElementById('interpretation-quota').style.display = 'none';
        _interpretationGenerated = true;
        return;
    }

    generateInterpretation();
}

function saveInterpretationCache(filename, data) {
    try {
        sessionStorage.setItem('ds_interp_' + filename, JSON.stringify(data));
    } catch (e) {}
}

function loadInterpretationCache(filename) {
    try {
        var raw = sessionStorage.getItem('ds_interp_' + filename);
        return raw ? JSON.parse(raw) : null;
    } catch (e) {
        return null;
    }
}

function clearInterpretationCache(filename) {
    try {
        sessionStorage.removeItem('ds_interp_' + filename);
    } catch (e) {}
}

var _quotaCountdownInterval = null;

function _startQuotaCountdown(resetSeconds) {
    if (_quotaCountdownInterval) clearInterval(_quotaCountdownInterval);
    var countdownEl = document.getElementById('interpretation-quota-countdown');
    if (!countdownEl || !resetSeconds) return;

    var langIT = typeof I18N !== 'undefined' ? I18N.t : function(k) { return k; };
    var remaining = resetSeconds;
    function tick() {
        if (remaining <= 0) {
            countdownEl.textContent = '';
            clearInterval(_quotaCountdownInterval);
            return;
        }
        var h = Math.floor(remaining / 3600);
        var m = Math.floor((remaining % 3600) / 60);
        var s = remaining % 60;
        var parts = [];
        if (h > 0) parts.push(h + ' ' + langIT('interp_quota_hour'));
        if (m > 0) parts.push(m + ' ' + langIT('interp_quota_min'));
        parts.push(s + ' ' + langIT('interp_quota_sec'));
        countdownEl.textContent = parts.join(' ');
        remaining--;
    }
    tick();
    _quotaCountdownInterval = setInterval(tick, 1000);
}

function generateInterpretation() {
    var filename = getFileName();
    var langIT = typeof I18N !== 'undefined' ? I18N.t : function(k) { return k; };
    if (!filename) {
        if (typeof showToast === 'function') showToast(langIT('interp_no_dataset'), 'error');
        return;
    }

    clearInterpretationCache(filename);

    var emptyState = document.getElementById('interpretation-empty');
    var loadingState = document.getElementById('interpretation-loading');
    var resultState = document.getElementById('interpretation-result');
    var quotaState = document.getElementById('interpretation-quota');

    if (emptyState) emptyState.style.display = 'none';
    if (resultState) resultState.style.display = 'none';
    if (quotaState) quotaState.style.display = 'none';
    if (loadingState) loadingState.style.display = 'block';

    var lang = localStorage.getItem('ds-lang') || 'en';

    fetch('/api/interpretation/' + encodeURIComponent(filename) + '?lang=' + lang, {
        method: 'POST',
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (loadingState) loadingState.style.display = 'none';

            if (data.ok && data.data) {
                renderInterpretationResult(data.data);
                saveInterpretationCache(filename, data.data);
                if (resultState) resultState.style.display = 'block';
                _interpretationGenerated = true;
            } else if (data.error === 'no_api_key') {
                if (emptyState) emptyState.style.display = 'flex';
                if (typeof showToast === 'function') {
                    showToast(langIT('interp_no_key'), 'warning');
                }
            } else if (data.error === 'quota_exceeded') {
                if (quotaState) {
                    var msgEl = document.getElementById('interpretation-quota-message');
                    var keysEl = document.getElementById('interpretation-quota-keys');
                    var resetEl = document.getElementById('interpretation-quota-reset');
                    if (msgEl) msgEl.textContent = data.message || langIT('interp_quota_msg');
                    if (keysEl && data.keys_exhausted && data.total_keys) {
                        if (data.keys_exhausted >= data.total_keys) {
                            keysEl.textContent = data.keys_exhausted + ' / ' + data.total_keys + ' API key sudah habis kuota.';
                        } else {
                            keysEl.textContent = data.keys_exhausted + ' / ' + data.total_keys + ' API key habis kuota. Mencoba key berikutnya...';
                        }
                    }
                    if (resetEl && data.reset_in_seconds) {
                        var hours = Math.floor(data.reset_in_seconds / 3600);
                        var minutes = Math.floor((data.reset_in_seconds % 3600) / 60);
                        resetEl.textContent = langIT('interp_quota_reset') + ' ' + hours + ' ' + langIT('interp_quota_hour') + ' ' + minutes + ' ' + langIT('interp_quota_min');
                    }
                    _startQuotaCountdown(data.reset_in_seconds || 0);
                    quotaState.style.display = 'block';
                }
                if (typeof showToast === 'function') {
                    showToast(langIT('interp_quota_gemini'), 'warning');
                }
            } else {
                if (emptyState) emptyState.style.display = 'flex';
                if (typeof showToast === 'function') {
                    showToast(data.error || langIT('interp_failed'), 'error');
                }
            }
        })
        .catch(function (err) {
            if (loadingState) loadingState.style.display = 'none';
            if (emptyState) emptyState.style.display = 'flex';
            if (typeof showToast === 'function') {
                showToast(langIT('interp_network') + ' ' + err.message, 'error');
            }
        });
}

function renderMarkdown(text) {
    if (!text) return '';
    var escaped = text
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
    escaped = escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
}

function renderInterpretationResult(data) {
    var summaryEl = document.getElementById('interpretation-summary-text');
    var findingsEl = document.getElementById('interpretation-findings-list');
    var recommendationsEl = document.getElementById('interpretation-recommendations-list');
    var conclusionEl = document.getElementById('interpretation-conclusion-text');

    if (summaryEl) summaryEl.innerHTML = renderMarkdown(data.summary || '');
    if (conclusionEl) conclusionEl.innerHTML = renderMarkdown(data.conclusion || '');

    if (findingsEl) {
        findingsEl.innerHTML = '';
        if (data.key_findings && data.key_findings.length > 0) {
            data.key_findings.forEach(function (f) {
                var li = document.createElement('li');
                li.innerHTML = renderMarkdown(f);
                findingsEl.appendChild(li);
            });
        }
    }

    if (recommendationsEl) {
        recommendationsEl.innerHTML = '';
        if (data.recommendations && data.recommendations.length > 0) {
            data.recommendations.forEach(function (r) {
                var li = document.createElement('li');
                li.innerHTML = renderMarkdown(r);
                recommendationsEl.appendChild(li);
            });
        }
    }
}

function getFileName() {
    if (typeof vizMeta !== 'undefined' && vizMeta.filename) return vizMeta.filename;
    return null;
}

/* ─── AI CHAT ──────────────────────────────────────────────────── */

var _chatCollapsed = false;

function toggleChatPanel() {
    var body = document.getElementById('ai-chat-body');
    var inputArea = document.querySelector('.ai-chat-input-area');
    var icon = document.querySelector('#ai-chat-toggle i');
    if (!body) return;
    _chatCollapsed = !_chatCollapsed;
    body.style.display = _chatCollapsed ? 'none' : 'flex';
    if (inputArea) inputArea.style.display = _chatCollapsed ? 'none' : 'flex';
    if (icon) icon.className = _chatCollapsed ? 'fas fa-chevron-up' : 'fas fa-chevron-down';
}

function sendChatMessage() {
    var input = document.getElementById('ai-chat-input');
    var messagesEl = document.getElementById('ai-chat-messages');
    var typingEl = document.getElementById('ai-chat-typing');
    var sendBtn = document.getElementById('ai-chat-send');
    var langIT = typeof I18N !== 'undefined' ? I18N.t : function(k) { return k; };

    if (!input || !messagesEl) return;
    var msg = input.value.trim();
    if (!msg) return;

    var filename = getFileName();
    if (!filename) {
        if (typeof showToast === 'function') showToast(langIT('interp_no_dataset'), 'error');
        return;
    }

    input.value = '';
    input.disabled = true;
    if (sendBtn) sendBtn.disabled = true;

    var userDiv = document.createElement('div');
    userDiv.className = 'ai-chat-msg ai-chat-msg-user';
    userDiv.innerHTML = '<div class="ai-chat-bubble">' + renderMarkdown(msg) + '</div>';
    messagesEl.appendChild(userDiv);
    _scrollChatBottom();

    if (typingEl) typingEl.style.display = 'flex';
    _scrollChatBottom();

    fetch('/api/ai-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, filename: filename }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (typingEl) typingEl.style.display = 'none';
            input.disabled = false;
            if (sendBtn) sendBtn.disabled = false;

            var botDiv = document.createElement('div');
            botDiv.className = 'ai-chat-msg ai-chat-msg-bot';
            var avatar = '<div class="ai-chat-avatar"><i class="fas fa-robot"></i></div>';

            if (data.error === 'quota_exceeded') {
                botDiv.innerHTML = avatar + '<div class="ai-chat-bubble ai-chat-bubble-error">' + renderMarkdown(data.reply || langIT('ai_chat_quota')) + '</div>';
                if (data.reset_in_seconds) {
                    var h = Math.floor(data.reset_in_seconds / 3600);
                    var m = Math.floor((data.reset_in_seconds % 3600) / 60);
                    var info = document.createElement('div');
                    info.className = 'ai-chat-msg ai-chat-msg-system';
                    info.innerHTML = '<em>' + langIT('interp_quota_reset') + ': ' + h + ' ' + langIT('interp_quota_hour') + ' ' + m + ' ' + langIT('interp_quota_min') + '</em>';
                    messagesEl.appendChild(info);
                }
            } else if (data.reply) {
                botDiv.innerHTML = avatar + '<div class="ai-chat-bubble">' + renderMarkdown(data.reply) + '</div>';
            } else {
                botDiv.innerHTML = avatar + '<div class="ai-chat-bubble">' + langIT('ai_chat_error') + '</div>';
            }
            messagesEl.appendChild(botDiv);
            _scrollChatBottom();
        })
        .catch(function (err) {
            if (typingEl) typingEl.style.display = 'none';
            input.disabled = false;
            if (sendBtn) sendBtn.disabled = false;

            var errDiv = document.createElement('div');
            errDiv.className = 'ai-chat-msg ai-chat-msg-bot';
            errDiv.innerHTML = '<div class="ai-chat-avatar"><i class="fas fa-robot"></i></div><div class="ai-chat-bubble ai-chat-bubble-error">' + langIT('ai_chat_error') + ' ' + err.message + '</div>';
            messagesEl.appendChild(errDiv);
            _scrollChatBottom();
        });
}

function _scrollChatBottom() {
    var body = document.getElementById('ai-chat-body');
    if (body) setTimeout(function () { body.scrollTop = body.scrollHeight; }, 50);
}
