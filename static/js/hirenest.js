/**
 * HireNest Australia - Candidate Authentication & Interactive Experiences
 * Handles:
 * 1. Candidate Sign-In / Register Popup (SEEK-inspired UX)
 * 2. Google / Apple OAuth simulation & callback handling
 * 3. Email Registration + 6-digit OTP verification & resend cooldown
 * 4. 3-Question Onboarding Wizard with Australian location autocomplete & Remote support
 * 5. AJAX Job bookmarking / saving
 * 6. Protection intercepts for unauthenticated candidate actions
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
let currentTargetEmail = '';
let resendTimerInterval = null;
let selectedOnboardingLocations = ['Sydney NSW'];

function isUserAuthenticated() {
    return document.body.getAttribute('data-user-authenticated') === 'true';
}

function getUserRole() {
    return document.body.getAttribute('data-user-role') || 'GUEST';
}

/**
 * Opens Candidate Authentication Modal in requested initial state
 * @param {string} mode - 'options', 'email', 'login', 'register'
 */
window.openCandidateAuthModal = function (mode = 'options') {
    const modalEl = document.getElementById('candidateAuthModal');
    if (!modalEl) return;

    if (!authModalInstance) {
        authModalInstance = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: true });
    }

    showAuthView('options');
    authModalInstance.show();
};

/**
 * Opens Onboarding Wizard Directly (e.g. from Dashboard or post-login)
 */
window.openOnboardingModal = function () {
    const modalEl = document.getElementById('candidateAuthModal');
    if (!modalEl) return;

    if (!authModalInstance) {
        authModalInstance = new bootstrap.Modal(modalEl, { backdrop: 'static', keyboard: true });
    }

    showAuthView('onboarding');
    showOnboardingStep(1);
    authModalInstance.show();
};

/**
 * Switches views inside candidateAuthModal
 * Views: 'options', 'email', 'otp', 'onboarding', 'success'
 */
function showAuthView(viewName) {
    const views = {
        options: document.getElementById('authViewOptions'),
        email: document.getElementById('authViewEmail'),
        otp: document.getElementById('authViewOtp'),
        onboarding: document.getElementById('authViewOnboarding'),
        success: document.getElementById('authViewSuccess'),
    };

    Object.keys(views).forEach(k => {
        if (views[k]) views[k].classList.add('d-none');
    });

    if (views[viewName]) {
        views[viewName].classList.remove('d-none');
    }
}

/**
 * Controls step views inside Onboarding Wizard (1, 2, 3)
 */
function showOnboardingStep(stepNumber) {
    const q1 = document.getElementById('onboardingQ1');
    const q2 = document.getElementById('onboardingQ2');
    const q3 = document.getElementById('onboardingQ3');
    const badge = document.getElementById('onboardingStepBadge');
    const title = document.getElementById('onboardingStepTitle');
    const bar = document.getElementById('onboardingProgressBar');

    if (q1) q1.classList.add('d-none');
    if (q2) q2.classList.add('d-none');
    if (q3) q3.classList.add('d-none');

    if (stepNumber === 1) {
        if (q1) q1.classList.remove('d-none');
        if (badge) badge.innerText = 'Step 1 of 3';
        if (title) title.innerText = 'Work Preferences';
        if (bar) bar.style.width = '33%';
    } else if (stepNumber === 2) {
        if (q2) q2.classList.remove('d-none');
        if (badge) badge.innerText = 'Step 2 of 3';
        if (title) title.innerText = 'Australian Locations';
        if (bar) bar.style.width = '66%';
    } else if (stepNumber === 3) {
        if (q3) q3.classList.remove('d-none');
        if (badge) badge.innerText = 'Step 3 of 3';
        if (title) title.innerText = 'Employment Type';
        if (bar) bar.style.width = '100%';
    }
}

/**
 * Removes a location tag from selected location chips
 */
window.removeLocationTag = function (el, locationName) {
    selectedOnboardingLocations = selectedOnboardingLocations.filter(loc => loc !== locationName);
    renderSelectedLocationTags();
};

function renderSelectedLocationTags() {
    const container = document.getElementById('selectedLocationsContainer');
    if (!container) return;

    if (selectedOnboardingLocations.length === 0) {
        container.innerHTML = '<span class="text-muted small fst-italic">No locations selected. Choose below or search.</span>';
        return;
    }

    container.innerHTML = selectedOnboardingLocations.map(loc => `
        <span class="badge bg-primary text-white d-inline-flex align-items-center gap-1.5 py-1.5 px-2.5 rounded-pill hn-loc-tag" data-loc="${loc}">
            <span>${loc}</span>
            <i class="bi bi-x-circle-fill cursor-pointer" onclick="removeLocationTag(this, '${loc}')" title="Remove"></i>
        </span>
    `).join('');
}

function addLocationTag(locationName) {
    if (!locationName) return;
    const clean = locationName.trim();
    if (!selectedOnboardingLocations.includes(clean)) {
        selectedOnboardingLocations.push(clean);
        renderSelectedLocationTags();
    }
}

// Resend timer countdown handler
function startResendCooldown(seconds = 60) {
    const resendBtn = document.getElementById('btnResendOtp');
    const countdownSpan = document.getElementById('resendCountdown');
    if (!resendBtn || !countdownSpan) return;

    if (resendTimerInterval) clearInterval(resendTimerInterval);

    resendBtn.disabled = true;
    let timeLeft = seconds;
    countdownSpan.innerText = timeLeft;

    resendTimerInterval = setInterval(() => {
        timeLeft--;
        if (timeLeft <= 0) {
            clearInterval(resendTimerInterval);
            resendBtn.disabled = false;
            resendBtn.innerText = 'Resend verification code';
        } else {
            countdownSpan.innerText = timeLeft;
        }
    }, 1000);
}

document.addEventListener('DOMContentLoaded', function () {
    // --------------------------------------------------------------------------
    // 1. View Navigation inside Auth Modal
    // --------------------------------------------------------------------------
    const btnContinueEmail = document.getElementById('btnContinueEmail');
    if (btnContinueEmail) {
        btnContinueEmail.addEventListener('click', function () {
            showAuthView('email');
            const emailInput = document.getElementById('inputCandidateEmail');
            if (emailInput) setTimeout(() => emailInput.focus(), 150);
        });
    }

    const btnBackToOptions = document.getElementById('btnBackToOptions');
    if (btnBackToOptions) {
        btnBackToOptions.addEventListener('click', function () {
            showAuthView('options');
        });
    }

    const btnChangeEmail = document.getElementById('btnChangeEmail');
    if (btnChangeEmail) {
        btnChangeEmail.addEventListener('click', function () {
            showAuthView('email');
        });
    }

    // --------------------------------------------------------------------------
    // 2. Email Submission & OTP Request (AJAX)
    // --------------------------------------------------------------------------
    const formSendOtp = document.getElementById('formSendOtp');
    const inputCandidateEmail = document.getElementById('inputCandidateEmail');
    const emailAlertBox = document.getElementById('emailAlertBox');
    const btnSubmitEmail = document.getElementById('btnSubmitEmail');

    if (formSendOtp) {
        formSendOtp.addEventListener('submit', async function (e) {
            e.preventDefault();
            const email = (inputCandidateEmail.value || '').trim().toLowerCase();
            if (!email) return;

            if (emailAlertBox) emailAlertBox.classList.add('d-none');
            btnSubmitEmail.disabled = true;
            btnSubmitEmail.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Sending code...';

            try {
                const response = await fetch('/auth/send-otp/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ email: email })
                });

                const res = await response.json();

                if (response.ok && res.success) {
                    currentTargetEmail = email;
                    const displayEmailEl = document.getElementById('displayTargetEmail');
                    if (displayEmailEl) displayEmailEl.innerText = email;

                    showAuthView('otp');
                    startResendCooldown(res.cooldown || 60);

                    // Auto-focus first OTP input
                    const firstOtp = document.querySelector('.hn-otp-input');
                    if (firstOtp) setTimeout(() => firstOtp.focus(), 200);
                } else {
                    if (emailAlertBox) {
                        emailAlertBox.innerText = res.error || 'Failed to send verification code. Please try again.';
                        emailAlertBox.classList.remove('d-none');
                    }
                }
            } catch (err) {
                if (emailAlertBox) {
                    emailAlertBox.innerText = 'Network connection error. Please check your internet connection.';
                    emailAlertBox.classList.remove('d-none');
                }
            } finally {
                btnSubmitEmail.disabled = false;
                btnSubmitEmail.innerHTML = '<span>Send verification code</span> <i class="bi bi-arrow-right"></i>';
            }
        });
    }

    // --------------------------------------------------------------------------
    // 3. 6-Digit OTP Inputs Auto-Tab & Paste Handling
    // --------------------------------------------------------------------------
    const otpInputs = document.querySelectorAll('.hn-otp-input');
    otpInputs.forEach((input, idx) => {
        input.addEventListener('input', function (e) {
            const val = input.value.replace(/\D/g, '');
            input.value = val ? val[0] : '';

            if (val && idx < otpInputs.length - 1) {
                otpInputs[idx + 1].focus();
            }

            // Auto-submit if all 6 digits are filled
            const code = Array.from(otpInputs).map(i => i.value).join('');
            if (code.length === 6) {
                submitOtpVerification(code);
            }
        });

        input.addEventListener('keydown', function (e) {
            if (e.key === 'Backspace' && !input.value && idx > 0) {
                otpInputs[idx - 1].focus();
            }
        });

        input.addEventListener('paste', function (e) {
            e.preventDefault();
            const pasteData = (e.clipboardData || window.clipboardData).getData('text').replace(/\D/g, '');
            if (pasteData) {
                for (let i = 0; i < otpInputs.length; i++) {
                    otpInputs[i].value = pasteData[i] || '';
                }
                const code = Array.from(otpInputs).map(i => i.value).join('');
                if (code.length === 6) {
                    submitOtpVerification(code);
                } else {
                    const nextEmpty = Array.from(otpInputs).find(i => !i.value);
                    if (nextEmpty) nextEmpty.focus();
                }
            }
        });
    });

    // --------------------------------------------------------------------------
    // 4. OTP Verification Submission
    // --------------------------------------------------------------------------
    const formVerifyOtp = document.getElementById('formVerifyOtp');
    const otpAlertBox = document.getElementById('otpAlertBox');
    const btnSubmitOtp = document.getElementById('btnSubmitOtp');
    const otpSpinner = document.getElementById('otpSpinner');
    const btnSubmitOtpText = document.getElementById('btnSubmitOtpText');

    async function submitOtpVerification(code) {
        if (!code || code.length !== 6 || !currentTargetEmail) return;

        if (otpAlertBox) otpAlertBox.classList.add('d-none');
        if (btnSubmitOtp) btnSubmitOtp.disabled = true;
        if (otpSpinner) otpSpinner.classList.remove('d-none');
        if (btnSubmitOtpText) btnSubmitOtpText.innerText = 'Verifying...';

        try {
            const response = await fetch('/auth/verify-otp/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ email: currentTargetEmail, otp: code })
            });

            const res = await response.json();

            if (response.ok && res.success) {
                // Update client session state
                document.body.setAttribute('data-user-authenticated', 'true');
                document.body.setAttribute('data-user-role', 'CANDIDATE');

                if (res.onboarding_required) {
                    showAuthView('onboarding');
                    showOnboardingStep(1);
                } else {
                    showAuthView('success');
                    setTimeout(() => {
                        window.location.href = res.redirect_url || '/dashboard/';
                    }, 1200);
                }
            } else {
                if (otpAlertBox) {
                    otpAlertBox.innerText = res.error || 'Incorrect code. Please try again.';
                    otpAlertBox.classList.remove('d-none');
                }
                otpInputs.forEach(i => i.value = '');
                if (otpInputs[0]) otpInputs[0].focus();
            }
        } catch (err) {
            if (otpAlertBox) {
                otpAlertBox.innerText = 'Network error during verification. Please try again.';
                otpAlertBox.classList.remove('d-none');
            }
        } finally {
            if (btnSubmitOtp) btnSubmitOtp.disabled = false;
            if (otpSpinner) otpSpinner.classList.add('d-none');
            if (btnSubmitOtpText) btnSubmitOtpText.innerText = 'Verify & Continue';
        }
    }

    if (formVerifyOtp) {
        formVerifyOtp.addEventListener('submit', function (e) {
            e.preventDefault();
            const code = Array.from(otpInputs).map(i => i.value).join('');
            submitOtpVerification(code);
        });
    }

    // Resend OTP Button Handler
    const btnResendOtp = document.getElementById('btnResendOtp');
    if (btnResendOtp) {
        btnResendOtp.addEventListener('click', async function () {
            if (btnResendOtp.disabled || !currentTargetEmail) return;

            btnResendOtp.disabled = true;
            btnResendOtp.innerText = 'Sending...';

            try {
                const response = await fetch('/auth/send-otp/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ email: currentTargetEmail })
                });

                const res = await response.json();
                if (response.ok && res.success) {
                    startResendCooldown(res.cooldown || 60);
                    if (otpAlertBox) {
                        otpAlertBox.classList.add('d-none');
                    }
                } else {
                    btnResendOtp.disabled = false;
                    btnResendOtp.innerText = 'Resend code';
                    if (otpAlertBox) {
                        otpAlertBox.innerText = res.error || 'Failed to resend code.';
                        otpAlertBox.classList.remove('d-none');
                    }
                }
            } catch (e) {
                btnResendOtp.disabled = false;
                btnResendOtp.innerText = 'Resend code';
            }
        });
    }

    // --------------------------------------------------------------------------
    // 5. Social Auth Handlers (Google & Apple)
    // --------------------------------------------------------------------------
    const btnGoogleAuth = document.getElementById('btnGoogleAuth');
    if (btnGoogleAuth) {
        btnGoogleAuth.addEventListener('click', async function () {
            // Check if user has a Google prompt or redirect to social login endpoint
            try {
                btnGoogleAuth.disabled = true;
                btnGoogleAuth.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Connecting Google...';

                // Prompt candidate for Google quick sign-in if local demo or redirect to backend Google OAuth
                const emailPrompt = prompt("Enter your Google Account Email for Candidate Sign-In:", "candidate.sarah@gmail.com");
                if (emailPrompt) {
                    const response = await fetch('/auth/social/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        },
                        body: JSON.stringify({
                            provider: 'google',
                            email: emailPrompt.trim().toLowerCase(),
                            name: emailPrompt.split('@')[0].replace('.', ' ').title || 'Google Candidate'
                        })
                    });

                    const res = await response.json();
                    if (response.ok && res.success) {
                        document.body.setAttribute('data-user-authenticated', 'true');
                        document.body.setAttribute('data-user-role', 'CANDIDATE');

                        if (res.onboarding_required) {
                            showAuthView('onboarding');
                            showOnboardingStep(1);
                        } else {
                            showAuthView('success');
                            setTimeout(() => {
                                window.location.href = res.redirect_url || '/dashboard/';
                            }, 1000);
                        }
                    }
                }
            } finally {
                btnGoogleAuth.disabled = false;
                btnGoogleAuth.innerHTML = `
                    <svg class="hn-social-icon" width="20" height="20" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"/>
                    </svg>
                    <span class="fw-semibold">Continue with Google</span>
                `;
            }
        });
    }

    const btnAppleAuth = document.getElementById('btnAppleAuth');
    if (btnAppleAuth) {
        btnAppleAuth.addEventListener('click', async function () {
            try {
                btnAppleAuth.disabled = true;
                btnAppleAuth.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Connecting Apple...';

                const emailPrompt = prompt("Enter your Apple ID Email for Candidate Sign-In:", "candidate.apple@icloud.com");
                if (emailPrompt) {
                    const response = await fetch('/auth/social/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCsrfToken()
                        },
                        body: JSON.stringify({
                            provider: 'apple',
                            email: emailPrompt.trim().toLowerCase(),
                            name: emailPrompt.split('@')[0].replace('.', ' ').title || 'Apple Candidate'
                        })
                    });

                    const res = await response.json();
                    if (response.ok && res.success) {
                        document.body.setAttribute('data-user-authenticated', 'true');
                        document.body.setAttribute('data-user-role', 'CANDIDATE');

                        if (res.onboarding_required) {
                            showAuthView('onboarding');
                            showOnboardingStep(1);
                        } else {
                            showAuthView('success');
                            setTimeout(() => {
                                window.location.href = res.redirect_url || '/dashboard/';
                            }, 1000);
                        }
                    }
                }
            } finally {
                btnAppleAuth.disabled = false;
                btnAppleAuth.innerHTML = '<i class="bi bi-apple fs-5"></i> <span class="fw-semibold">Continue with Apple</span>';
            }
        });
    }

    // --------------------------------------------------------------------------
    // 6. Onboarding Wizard Interactivity (3 Questions)
    // --------------------------------------------------------------------------
    const btnNextQ1 = document.getElementById('btnNextQ1');
    const btnSkipQ1 = document.getElementById('btnSkipQ1');
    if (btnNextQ1) btnNextQ1.addEventListener('click', () => showOnboardingStep(2));
    if (btnSkipQ1) btnSkipQ1.addEventListener('click', () => showOnboardingStep(2));

    const btnBackToQ1 = document.getElementById('btnBackToQ1');
    if (btnBackToQ1) btnBackToQ1.addEventListener('click', () => showOnboardingStep(1));

    const btnNextQ2 = document.getElementById('btnNextQ2');
    if (btnNextQ2) btnNextQ2.addEventListener('click', () => showOnboardingStep(3));

    const btnBackToQ2 = document.getElementById('btnBackToQ2');
    if (btnBackToQ2) btnBackToQ2.addEventListener('click', () => showOnboardingStep(2));

    // Australian Location Autocomplete
    const locationSearchInput = document.getElementById('onboardingLocationSearch');
    const locationSuggestionsBox = document.getElementById('locationSuggestionsBox');

    if (locationSearchInput && locationSuggestionsBox) {
        locationSearchInput.addEventListener('input', async function () {
            const val = (locationSearchInput.value || '').trim();
            if (val.length < 1) {
                locationSuggestionsBox.classList.add('d-none');
                return;
            }

            try {
                const response = await fetch(`/api/locations/?q=${encodeURIComponent(val)}`);
                const data = await response.json();
                if (data.locations && data.locations.length > 0) {
                    locationSuggestionsBox.innerHTML = data.locations.map(item => `
                        <button type="button" class="list-group-item list-group-item-action py-2 px-3 d-flex justify-content-between align-items-center" onclick="addLocationFromSuggestion('${item.label}')">
                            <span class="fw-semibold small"><i class="bi bi-geo-alt me-1.5 text-danger"></i>${item.label}</span>
                            <span class="badge bg-light text-muted border small">${item.category || item.state}</span>
                        </button>
                    `).join('');
                    locationSuggestionsBox.classList.remove('d-none');
                } else {
                    locationSuggestionsBox.classList.add('d-none');
                }
            } catch (e) {
                locationSuggestionsBox.classList.add('d-none');
            }
        });
    }

    window.addLocationFromSuggestion = function (label) {
        addLocationTag(label);
        if (locationSearchInput) locationSearchInput.value = '';
        if (locationSuggestionsBox) locationSuggestionsBox.classList.add('d-none');
    };

    // Quick location pills
    document.querySelectorAll('.hn-quick-loc').forEach(btn => {
        btn.addEventListener('click', function () {
            const loc = btn.getAttribute('data-loc');
            addLocationTag(loc);
        });
    });

    // Finish Onboarding Submission
    const btnFinishOnboarding = document.getElementById('btnFinishOnboarding');
    const finishSpinner = document.getElementById('finishSpinner');

    if (btnFinishOnboarding) {
        btnFinishOnboarding.addEventListener('click', async function () {
            btnFinishOnboarding.disabled = true;
            if (finishSpinner) finishSpinner.classList.remove('d-none');

            // Collect selected categories (Q1)
            const categories = Array.from(document.querySelectorAll('input[name="onboarding_category"]:checked')).map(cb => cb.value);
            const roleTitle = (document.getElementById('onboardingRoleTitle')?.value || '').trim();

            // Collect selected locations (Q2)
            const locations = selectedOnboardingLocations;

            // Collect selected job types (Q3)
            const jobTypes = Array.from(document.querySelectorAll('input[name="onboarding_job_type"]:checked')).map(cb => cb.value);

            try {
                const response = await fetch('/api/onboarding/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({
                        categories: categories,
                        role_title: roleTitle,
                        locations: locations,
                        job_types: jobTypes
                    })
                });

                const res = await response.json();
                if (response.ok && res.success) {
                    showAuthView('success');
                } else {
                    alert(res.error || 'Failed to save preferences.');
                }
            } catch (e) {
                showAuthView('success');
            } finally {
                btnFinishOnboarding.disabled = false;
                if (finishSpinner) finishSpinner.classList.add('d-none');
            }
        });
    }

    // --------------------------------------------------------------------------
    // 7. Unauthenticated Candidate Action Interceptors (Save Job, Apply)
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
});
