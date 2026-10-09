/**
 * MeetMind - Client-side application logic
 * Handles real-time polling, video synchronization, tab switching, and local RAG chat.
 */

/* ==========================================================================
   Toast Notification System (shadcn-style)
   ========================================================================== */
window.showToast = function(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const variants = {
        success: { icon: 'check-circle-2', accent: 'text-emerald-400', ring: 'border-emerald-500/20', bg: 'bg-emerald-500/10' },
        error:   { icon: 'alert-triangle', accent: 'text-rose-400',    ring: 'border-rose-500/20',    bg: 'bg-rose-500/10' },
        warning: { icon: 'alert-triangle', accent: 'text-amber-400',   ring: 'border-amber-500/20',   bg: 'bg-amber-500/10' },
        info:    { icon: 'info',           accent: 'text-indigo-400',  ring: 'border-indigo-500/20',  bg: 'bg-indigo-500/10' },
    };
    const v = variants[type] || variants.info;

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto flex w-[340px] max-w-[90vw] items-start gap-3 rounded-xl border ${v.ring} bg-card/95 p-3.5 shadow-lg backdrop-blur transition-all duration-300 ease-out translate-x-full opacity-0`;
    toast.innerHTML = `
        <div class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full ${v.bg} ${v.accent}">
            <i data-lucide="${v.icon}" class="h-4 w-4"></i>
        </div>
        <p class="flex-1 pt-0.5 text-xs sm:text-sm leading-relaxed text-foreground">${escapeHtml(message)}</p>
        <button type="button" class="toast-close shrink-0 rounded-md p-1 text-muted-foreground transition hover:bg-secondary hover:text-foreground" aria-label="Dismiss">
            <i data-lucide="x" class="h-3.5 w-3.5"></i>
        </button>
    `;

    container.appendChild(toast);
    if (window.lucide) window.lucide.createIcons();

    // Slide in from the right
    requestAnimationFrame(() => {
        toast.classList.remove('translate-x-full', 'opacity-0');
    });

    const dismiss = () => {
        toast.classList.add('translate-x-full', 'opacity-0');
        setTimeout(() => toast.remove(), 300);
    };

    toast.querySelector('.toast-close').addEventListener('click', dismiss);
    setTimeout(dismiss, duration);
};

/* ==========================================================================
   Confirmation Modal (shadcn-style alert dialog)
   Returns a Promise<boolean> — true on confirm, false on cancel/dismiss.
   ========================================================================== */
window.showConfirm = function({
    title = 'Are you sure?',
    message = '',
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    destructive = true,
} = {}) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'fixed inset-0 z-[110] flex items-center justify-center p-4 bg-background/80 backdrop-blur-sm opacity-0 transition-opacity duration-200';
        overlay.innerHTML = `
            <div class="confirm-card w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl transition-all duration-200 scale-95 opacity-0" role="alertdialog" aria-modal="true">
                <div class="flex items-start gap-4">
                    <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${destructive ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'}">
                        <i data-lucide="${destructive ? 'trash-2' : 'alert-triangle'}" class="h-5 w-5"></i>
                    </div>
                    <div class="flex-1 space-y-1.5">
                        <h2 class="text-base font-semibold text-foreground">${escapeHtml(title)}</h2>
                        <p class="text-sm text-muted-foreground leading-relaxed">${escapeHtml(message)}</p>
                    </div>
                </div>
                <div class="mt-6 flex justify-end gap-2">
                    <button type="button" class="confirm-cancel inline-flex items-center rounded-md border border-input bg-background px-3.5 py-1.5 text-xs font-medium text-foreground shadow-sm transition hover:bg-secondary">${escapeHtml(cancelText)}</button>
                    <button type="button" class="confirm-ok inline-flex items-center rounded-md px-3.5 py-1.5 text-xs font-medium shadow-sm transition ${destructive ? 'bg-rose-600 text-white hover:bg-rose-500' : 'bg-primary text-primary-foreground hover:bg-primary/90'}">${escapeHtml(confirmText)}</button>
                </div>
            </div>
        `;

        document.body.appendChild(overlay);
        document.body.style.overflow = 'hidden';
        if (window.lucide) window.lucide.createIcons();

        // Animate in
        requestAnimationFrame(() => {
            overlay.classList.remove('opacity-0');
            const card = overlay.querySelector('.confirm-card');
            card.classList.remove('scale-95', 'opacity-0');
        });

        let settled = false;
        const settle = (result) => {
            if (settled) return;
            settled = true;
            document.removeEventListener('keydown', onKeyDown);
            overlay.classList.add('opacity-0');
            overlay.querySelector('.confirm-card').classList.add('scale-95', 'opacity-0');
            setTimeout(() => {
                overlay.remove();
                document.body.style.overflow = '';
                resolve(result);
            }, 200);
        };

        const onKeyDown = (e) => {
            if (e.key === 'Escape') settle(false);
        };

        overlay.querySelector('.confirm-cancel').addEventListener('click', () => settle(false));
        overlay.querySelector('.confirm-ok').addEventListener('click', () => settle(true));
        overlay.addEventListener('mousedown', (e) => {
            if (e.target === overlay) settle(false);
        });
        document.addEventListener('keydown', onKeyDown);

        // Focus cancel by default so a stray Enter doesn't confirm a destructive action
        overlay.querySelector('.confirm-cancel').focus();
    });
};

document.addEventListener('DOMContentLoaded', () => {
    // 1. Re-render icons if Lucide is available
    if (window.lucide) {
        window.lucide.createIcons();
    }

    // 2. Initialize file upload drag & drop if on upload page
    initUploadDropzone();

    // 3. Initialize tabs on meeting detail page
    initTabs();

    // 4. Initialize video-transcript sync
    initVideoSync();

    // 5. Initialize live processing status polling
    initStatusPolling();

    // 6. Initialize meeting comparison selection mode
    initCompareMode();
});

/* ==========================================================================
   Upload Dropzone Logic
   ========================================================================== */
function initUploadDropzone() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('video_file');
    const fileInfo = document.getElementById('fileSelectedInfo');
    const fileNameSpan = document.getElementById('fileName');

    if (!dropZone || !fileInput) return;

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.add('border-primary', 'bg-secondary/40');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropZone.classList.remove('border-primary', 'bg-secondary/40');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            fileInput.files = files;
            showSelectedFile(files[0].name);
        }
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            showSelectedFile(fileInput.files[0].name);
        }
    });

    function showSelectedFile(name) {
        if (fileNameSpan && fileInfo) {
            fileNameSpan.textContent = name;
            fileInfo.classList.remove('hidden');
            fileInfo.classList.add('flex');
            if (window.lucide) window.lucide.createIcons();
        }
    }
}

/* ==========================================================================
   Tabs Navigation (shadcn Tab Pattern)
   ========================================================================== */
function initTabs() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    if (!tabButtons.length) return;

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-tab');

            // Deactivate all
            tabButtons.forEach(b => {
                b.classList.remove('bg-background', 'text-foreground', 'shadow-sm');
                b.classList.add('text-muted-foreground');
            });
            tabPanes.forEach(p => {
                p.classList.add('hidden');
                p.classList.remove('block');
            });

            // Activate current
            btn.classList.add('bg-background', 'text-foreground', 'shadow-sm');
            btn.classList.remove('text-muted-foreground');

            const targetPane = document.getElementById(targetId);
            if (targetPane) {
                targetPane.classList.remove('hidden');
                targetPane.classList.add('block');
            }

            if (window.lucide) window.lucide.createIcons();
        });
    });
}

/* ==========================================================================
   Interactive Video & Transcript Synchronization
   ========================================================================== */
window.seekVideo = function(seconds) {
    const video = document.getElementById('meetingVideo');
    if (video) {
        // Switch to the timeline tab if not already on it
        const timelineBtn = document.querySelector('[data-tab="tab-timeline"]');
        if (timelineBtn && !timelineBtn.classList.contains('bg-background')) {
            timelineBtn.click();
        }

        video.currentTime = Math.max(0, seconds);
        video.play().catch(() => {});
        video.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
};

function initVideoSync() {
    const video = document.getElementById('meetingVideo');
    const turns = document.querySelectorAll('.transcript-turn');
    const container = document.getElementById('transcriptStream');

    if (!video || !turns.length) return;

    // Auto-follow pauses when the user scrolls up, resumes at the bottom
    let followActive = true;
    let lastActiveTurn = null;

    if (container) {
        const pauseFollow = () => { followActive = false; };
        container.addEventListener('wheel', pauseFollow, { passive: true });
        container.addEventListener('touchmove', pauseFollow, { passive: true });

        container.addEventListener('scroll', () => {
            const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 40;
            if (nearBottom) followActive = true;
        }, { passive: true });
    }

    video.addEventListener('timeupdate', () => {
        const currentTime = video.currentTime;
        let activeTurn = null;

        turns.forEach(turn => {
            const start = parseFloat(turn.getAttribute('data-start'));
            if (currentTime >= start) {
                activeTurn = turn;
            }
        });

        turns.forEach(t => t.classList.remove('bg-secondary/80', 'border-l-2', 'border-primary'));

        if (activeTurn) {
            activeTurn.classList.add('bg-secondary/80', 'border-l-2', 'border-primary');
            // Only auto-scroll when the active segment changes, and only while following
            if (followActive && activeTurn !== lastActiveTurn) {
                activeTurn.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
        lastActiveTurn = activeTurn;
    });
}

/* ==========================================================================
   Real-Time Processing Polling
   ========================================================================== */
function initStatusPolling() {
    const container = document.getElementById('meetingDetailContainer');
    if (!container) return;

    const meetingId = container.getAttribute('data-meeting-id');
    let currentStatus = container.getAttribute('data-status');

    if (currentStatus === 'completed' || currentStatus === 'failed') {
        return; // No need to poll
    }

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/meeting/${meetingId}/status/`);
            if (!res.ok) return;

            const data = await res.json();

            // Update UI elements
            const statusLabel = document.getElementById('statusLabel');
            const statusDetail = document.getElementById('statusDetail');
            const progressPercentage = document.getElementById('progressPercentage');
            const progressBarFill = document.getElementById('progressBarFill');

            if (statusLabel) statusLabel.textContent = data.status_label;
            if (statusDetail) statusDetail.textContent = data.status_detail;
            if (progressPercentage) progressPercentage.textContent = `${data.progress}%`;
            if (progressBarFill) progressBarFill.style.width = `${data.progress}%`;

            if (data.completed || data.failed) {
                clearInterval(interval);
                // Reload page to display completed views
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 2500);
}

/* ==========================================================================
   Local RAG Chat Copilot
   ========================================================================== */
window.handleChatSubmit = async function(event) {
    event.preventDefault();
    const container = document.getElementById('meetingDetailContainer');
    if (!container) return;

    const meetingId = container.getAttribute('data-meeting-id');
    const input = document.getElementById('chatInput');
    const submitBtn = document.getElementById('chatSubmitBtn');
    const messagesContainer = document.getElementById('chatMessages');

    const question = input.value.trim();
    if (!question) return;

    // 1. Append user message
    input.value = '';
    appendMessage('user', question);
    submitBtn.disabled = true;

    // 2. Append thinking bubble
    const loadingId = 'loading-' + Date.now();
    appendLoadingBubble(loadingId);

    try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
        const res = await fetch(`/meeting/${meetingId}/chat/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify({ question }),
        });

        const data = await res.json();
        removeLoadingBubble(loadingId);

        if (res.ok && data.answer) {
            appendMessage('ai', data.answer);
        } else {
            appendMessage('ai', data.error || 'Failed to retrieve answer from local model.');
        }
    } catch (e) {
        removeLoadingBubble(loadingId);
        appendMessage('ai', 'Connection error to local AI server.');
    } finally {
        submitBtn.disabled = false;
        if (window.lucide) window.lucide.createIcons();
    }
};

function appendMessage(sender, text) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    const msgDiv = document.createElement('div');
    if (sender === 'user') {
        msgDiv.className = 'flex items-start gap-3 justify-end';
        msgDiv.innerHTML = `
            <div class="rounded-lg bg-primary p-3 text-xs sm:text-sm text-primary-foreground max-w-[85%] leading-relaxed shadow-sm">
                <p>${escapeHtml(text)}</p>
            </div>
            <div class="flex h-7 w-7 items-center justify-center rounded-full bg-secondary text-xs shrink-0 mt-0.5 border border-border">
                <i data-lucide="user" class="h-3.5 w-3.5"></i>
            </div>
        `;
    } else {
        msgDiv.className = 'flex items-start gap-3';
        msgDiv.innerHTML = `
            <div class="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 text-xs shrink-0 mt-0.5 border border-emerald-500/20">
                <i data-lucide="brain" class="h-3.5 w-3.5"></i>
            </div>
            <div class="rounded-lg bg-secondary/80 p-3 text-xs sm:text-sm text-foreground max-w-[85%] leading-relaxed shadow-sm space-y-1">
                <p class="whitespace-pre-line">${escapeHtml(text)}</p>
            </div>
        `;
    }

    messagesContainer.appendChild(msgDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    if (window.lucide) window.lucide.createIcons();
}

function appendLoadingBubble(id) {
    const messagesContainer = document.getElementById('chatMessages');
    if (!messagesContainer) return;

    const loadDiv = document.createElement('div');
    loadDiv.id = id;
    loadDiv.className = 'flex items-start gap-3';
    loadDiv.innerHTML = `
        <div class="flex h-7 w-7 items-center justify-center rounded-full bg-emerald-500/10 text-emerald-400 text-xs shrink-0 mt-0.5 border border-emerald-500/20">
            <i data-lucide="loader-2" class="h-3.5 w-3.5 animate-spin"></i>
        </div>
        <div class="rounded-lg bg-secondary/50 p-3 text-xs text-muted-foreground flex items-center gap-2">
            <span>Querying ChromaDB & reasoning with Phi-3 locally...</span>
        </div>
    `;
    messagesContainer.appendChild(loadDiv);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    if (window.lucide) window.lucide.createIcons();
}

function removeLoadingBubble(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function escapeHtml(string) {
    return String(string)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

/* ==========================================================================
   Meeting Comparison Selection Mode (Dashboard)
   ========================================================================== */
function initCompareMode() {
    const toggleBtn = document.getElementById('compareToggle');
    const grid = document.getElementById('meetingsGrid');
    const bar = document.getElementById('compareBar');
    if (!toggleBtn || !grid || !bar) return;

    const countEl = document.getElementById('compareCount');
    const goBtn = document.getElementById('compareGo');
    const cancelBtn = document.getElementById('compareCancel');

    let active = false;
    const selected = new Set(); // meeting IDs in click order

    const refreshCard = (card) => {
        const on = selected.has(card.dataset.meetingId);
        card.classList.toggle('border-indigo-500', on);
        card.classList.toggle('ring-1', on);
        card.classList.toggle('ring-indigo-500/50', on);
        const checkedIcon = card.querySelector('.compare-checked-icon');
        const uncheckedIcon = card.querySelector('.compare-unchecked-icon');
        if (checkedIcon) checkedIcon.classList.toggle('hidden', !on);
        if (uncheckedIcon) uncheckedIcon.classList.toggle('hidden', on);
    };

    const updateBar = () => {
        countEl.textContent = selected.size;
        goBtn.disabled = selected.size < 2;
        bar.classList.toggle('hidden', selected.size === 0);
        bar.classList.toggle('flex', selected.size > 0);
        if (window.lucide) window.lucide.createIcons();
    };

    const setMode = (on) => {
        active = on;
        selected.clear();
        grid.querySelectorAll('.meeting-card').forEach(refreshCard);
        document.querySelectorAll('.compare-only').forEach(el => {
            el.classList.toggle('hidden', !on);
            el.classList.toggle('inline-flex', on);
        });
        toggleBtn.classList.toggle('bg-indigo-500/10', on);
        toggleBtn.classList.toggle('border-indigo-500/40', on);
        toggleBtn.classList.toggle('text-indigo-300', on);
        updateBar();
    };

    toggleBtn.addEventListener('click', () => setMode(!active));

    grid.addEventListener('click', (e) => {
        if (!active) return;
        const card = e.target.closest('.meeting-card');
        if (!card || card.dataset.status !== 'completed') return;
        // Let buttons inside the card (e.g. Delete) handle their own clicks
        if (e.target.closest('button')) return;

        e.preventDefault(); // suppress the card's detail-page navigation
        const id = card.dataset.meetingId;
        if (selected.has(id)) {
            selected.delete(id);
        } else {
            if (selected.size >= 3) {
                showToast('You can compare up to 3 meetings.', 'warning');
                return;
            }
            selected.add(id);
        }
        refreshCard(card);
        updateBar();
    });

    goBtn.addEventListener('click', () => {
        if (selected.size < 2) return;
        window.location.href = `/compare/?ids=${[...selected].join(',')}`;
    });

    cancelBtn.addEventListener('click', () => setMode(false));
}

/* ==========================================================================
   Meeting Delete (Dashboard + Detail Page)
   ========================================================================== */
window.deleteMeeting = async function(meetingId, buttonEl) {
    const confirmed = await showConfirm({
        title: 'Delete this meeting?',
        message: 'This will permanently remove the video, all extracted data, transcripts, and AI analysis. This cannot be undone.',
        confirmText: 'Delete',
        cancelText: 'Cancel',
        destructive: true,
    });
    if (!confirmed) return;

    // Visual feedback — disable button
    if (buttonEl) {
        buttonEl.disabled = true;
        buttonEl.innerHTML = '<span class="animate-spin inline-block h-3 w-3 border-2 border-rose-400 border-t-transparent rounded-full"></span>';
    }

    try {
        const res = await fetch(`/meeting/${meetingId}/delete/`, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
        });

        const data = await res.json();

        if (res.ok && data.success) {
            // Animate card removal on dashboard
            const card = buttonEl ? buttonEl.closest('.group') : null;
            if (card) {
                card.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => {
                    card.remove();
                    showToast('Meeting deleted successfully', 'success');
                    // Update stat counters if they exist
                    updateDashboardCounters();
                    // Show empty state if no cards left
                    const grid = document.querySelector('.grid.grid-cols-1.md\\:grid-cols-2.lg\\:grid-cols-3');
                    if (grid && grid.children.length === 0) {
                        window.location.reload();
                    }
                }, 300);
            } else {
                // On meeting detail page, redirect to dashboard
                window.location.href = '/';
            }
        } else {
            showToast(data.error || 'Failed to delete meeting.', 'error');
            if (buttonEl) {
                buttonEl.disabled = false;
                buttonEl.innerHTML = '<i data-lucide="trash-2" class="h-3 w-3"></i><span class="hidden sm:inline">Delete</span>';
                if (window.lucide) window.lucide.createIcons();
            }
        }
    } catch (e) {
        console.error('Delete error:', e);
        showToast('Failed to connect to server.', 'error');
        if (buttonEl) {
            buttonEl.disabled = false;
            buttonEl.innerHTML = '<i data-lucide="trash-2" class="h-3 w-3"></i><span class="hidden sm:inline">Delete</span>';
            if (window.lucide) window.lucide.createIcons();
        }
    }
};

function updateDashboardCounters() {
    // Recalculate visible card counts after deletion
    const allCards = document.querySelectorAll('.group.relative.flex.flex-col');
    const totalEl = document.querySelector('.text-2xl.font-bold.tracking-tight:not(.text-emerald-400):not(.text-amber-400):not(.text-indigo-300)');
    if (totalEl) {
        totalEl.textContent = allCards.length;
    }
}
