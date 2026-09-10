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
});
