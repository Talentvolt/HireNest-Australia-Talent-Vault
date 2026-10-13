/**
 * HireNest Australia - Candidate Authentication & Interactive Experiences
 * Handles:
 * 1. Candidate "Continue with Google" sign-in / register modal
 * 2. AJAX job bookmarking / saving
 * 3. Protection intercepts for unauthenticated candidate actions
 */

// Helper to get CSRF token from cookies
function getCsrfToken() {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, 10) === 'csrftoken=') {
                cookieValue = decodeURIComponent(cookie.substring(10));
                break;
            }
        }
    }
    return cookieValue || '';
}

// Global modal reference
let authModalInstance = null;

function isUserAuthenticated() {
    return document.body.getAttribute('data-user-authenticated') === 'true';
}

function getUserRole() {
    return document.body.getAttribute('data-user-role') || 'GUEST';
}

function showHireNestToast(message, tone) {
    let container = document.getElementById('hn-toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'hn-toast-container';
        container.className = 'position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1080';
        document.body.appendChild(container);
    }

    const bgClass = (tone === 'danger' || tone === 'error') ? 'bg-danger' : 'bg-success';
    const icon = (tone === 'danger' || tone === 'error') ? 'bi-exclamation-triangle-fill' : 'bi-check-circle-fill';

    const toastEl = document.createElement('div');
    toastEl.className = `toast align-items-center text-white ${bgClass} border-0 show shadow-lg mb-2`;
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body d-flex align-items-center gap-2 fw-semibold">
                <i class="bi ${icon} fs-5"></i>
                <span>${message}</span>
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" aria-label="Close" onclick="this.closest('.toast').remove()"></button>
        </div>
    `;
    container.appendChild(toastEl);
    setTimeout(function () {
        toastEl.classList.remove('show');
        setTimeout(function () { toastEl.remove(); }, 400);
    }, 4000);
}

function hnCopyToClipboard(text) {
    return new Promise(function (resolve, reject) {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(function () { resolve(true); }).catch(function () {
                hnLegacyCopy(text, resolve, reject);
            });
        } else {
            hnLegacyCopy(text, resolve, reject);
        }
    });
}

function hnLegacyCopy(text, resolve, reject) {
    try {
        const input = document.createElement('textarea');
        input.value = text;
        input.setAttribute('readonly', '');
        input.style.position = 'fixed';
        input.style.top = '-1000px';
        document.body.appendChild(input);
        input.select();
        input.setSelectionRange(0, input.value.length);
        document.execCommand('copy');
        document.body.removeChild(input);
        resolve(true);
    } catch (err) {
        reject(err);
    }
}

window.hnShareJob = function (url, title) {
    if (navigator.share) {
        navigator.share({ title: title || 'Job opening', url: url }).catch(function () {});
        return;
    }
    hnCopyToClipboard(url).then(function () {
        showHireNestToast('Link copied to clipboard', 'success');
    }).catch(function () {
        showHireNestToast('Unable to copy link', 'danger');
    });
};

window.hnCopyJobLink = function (url) {
    hnCopyToClipboard(url).then(function () {
        showHireNestToast('Link copied to clipboard', 'success');
    }).catch(function () {
        showHireNestToast('Unable to copy link', 'danger');
    });
};

window.hnShareWhatsApp = function (url, title) {
    const text = title ? `${title}\n${url}` : url;
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank', 'noopener,noreferrer');
};

/**
 * Opens the candidate "Continue with Google" authentication modal.
 * @param {string} mode - kept for backwards compatibility ('login', 'register', 'options')
 */
window.openCandidateAuthModal = function (mode = 'options') {
    const modalEl = document.getElementById('candidateAuthModal');
    if (!modalEl) {
        // Fallback: navigate directly to the Google OAuth start endpoint.
        window.location.href = '/accounts/google/login/';
        return;
    }

    if (!authModalInstance) {
        authModalInstance = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: true });
    }
    authModalInstance.show();
};

document.addEventListener('DOMContentLoaded', function () {
    // --------------------------------------------------------------------------
    // 1. Unauthenticated Candidate Action Interceptors (Save Job, Apply)
    // --------------------------------------------------------------------------
    document.querySelectorAll('.hn-btn-save-job').forEach(btn => {
        btn.addEventListener('click', async function (e) {
            e.preventDefault();
            e.stopPropagation();

            if (!isUserAuthenticated()) {
                openCandidateAuthModal('login');
                return;
            }

            const jobId = btn.getAttribute('data-job-id');
            if (!jobId) return;

            try {
                const response = await fetch('/jobs/saved/toggle/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ job_id: jobId })
                });

                const res = await response.json();
                if (res.status === 'saved') {
                    btn.classList.add('active', 'text-danger');
                    btn.innerHTML = '<i class="bi bi-bookmark-heart-fill text-danger"></i>';
                } else {
                    btn.classList.remove('active', 'text-danger');
                    btn.innerHTML = '<i class="bi bi-bookmark"></i>';
                }
            } catch (err) {
                console.error('Error saving job:', err);
            }
        });
    });

    // Intercept Quick Apply for unauthenticated users
    document.querySelectorAll('a[href*="/apply/"]').forEach(link => {
        link.addEventListener('click', function (e) {
            if (!isUserAuthenticated()) {
                e.preventDefault();
                openCandidateAuthModal('login');
            }
        });
    });

    // --------------------------------------------------------------------------
    // 3. Mobile drawer: close it first, then open the auth modal
    // --------------------------------------------------------------------------
    const mobileMenuEl = document.getElementById('hnMobileMenu');
    document.querySelectorAll('#hnMobileMenu [data-auth-modal]').forEach(btn => {
        btn.addEventListener('click', function () {
            const mode = this.getAttribute('data-auth-modal') || 'options';

            if (!mobileMenuEl || !window.bootstrap) {
                openCandidateAuthModal(mode);
                return;
            }

            const instance = bootstrap.Offcanvas.getInstance(mobileMenuEl);
            if (!instance) {
                openCandidateAuthModal(mode);
                return;
            }

            mobileMenuEl.addEventListener('hidden.bs.offcanvas', function () {
                openCandidateAuthModal(mode);
            }, { once: true });
            instance.hide();
        });
    });

    // --------------------------------------------------------------------------
    // 4. Job Sharing & Copy Link (Share Job / Copy Link / WhatsApp)
    // --------------------------------------------------------------------------
    document.addEventListener('click', function (e) {
        const shareBtn = e.target.closest('.hn-share-job');
        if (shareBtn) {
            e.preventDefault();
            const url = shareBtn.getAttribute('data-share-url') || window.location.href;
            const title = shareBtn.getAttribute('data-share-title') || document.title;
            window.hnShareJob(url, title);
            return;
        }

        const copyBtn = e.target.closest('.hn-copy-job-link');
        if (copyBtn) {
            e.preventDefault();
            const url = copyBtn.getAttribute('data-share-url') || window.location.href;
            window.hnCopyJobLink(url);
            return;
        }

        const whatsappBtn = e.target.closest('.hn-whatsapp-job');
        if (whatsappBtn) {
            e.preventDefault();
            const url = whatsappBtn.getAttribute('data-share-url') || window.location.href;
            const title = whatsappBtn.getAttribute('data-share-title') || document.title;
            window.hnShareWhatsApp(url, title);
            return;
        }
    });
});
