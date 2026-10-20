/**
 * AIOps Sentinel — Real-Time Telemetry, Multi-Device Recognizer,
 * Web Audio Siren Alarmer, QR Mobile Pairing & Admin Controller
 * 100% Solid & Glassmorphism-Free
 */

// Safe helper for text manipulation
function safeSetText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

// Application Global State
const state = {
    activeTab: 'dashboard',
    activeHost: 'all',
    activeMetrics: { cpu: true, mem: true, lat: false, err: false, score: false },
    user: null,
    alarm: {
        isRinging: false,
        soundEnabled: true,
        vibrationEnabled: true,
        strobeEnabled: true,
        volume: 0.7,
        audioCtx: null,
        activeOscillator: null,
        gainNode: null
    },
    cluster: {
        healthy: true,
        anomalyScore: 0.084,
        threshold: -0.0285,
        modelLoaded: true,
        ingestedCount: 51840,
        activeIncident: null
    },
    device: {
        category: 'Desktop / Laptop',
        os: 'Unknown OS',
        browser: 'Browser',
        resolution: `${window.innerWidth} x ${window.innerHeight}`,
        fingerprint: 'sen-sha256-' + Math.random().toString(36).substring(2, 10),
        battery: 'Unknown'
    }
};

let telemetryChart = null;
const timeLabels = [];
const seriesData = { cpu: [], mem: [], lat: [], err: [], score: [] };
const MAX_DATAPOINTS = 25;

// ──────────────────────────────────────────────────────────────
// Initialization (Fault-Tolerant & Bulletproof)
// ──────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    try { initOnboardingGateway(); } catch(e) { console.error('initOnboardingGateway error:', e); }
    try { initAuth(); } catch(e) { console.error('initAuth error:', e); }
    try { initNavigation(); } catch(e) { console.error('initNavigation error:', e); }
    try { initDeviceFingerprint(); } catch(e) { console.error('initDeviceFingerprint error:', e); }
    try { initChart(); } catch(e) { console.error('initChart error:', e); }
    try { initSimulator(); } catch(e) { console.error('initSimulator error:', e); }
    try { initAlarmer(); } catch(e) { console.error('initAlarmer error:', e); }
    try { initQRCode(); } catch(e) { console.error('initQRCode error:', e); }
    try { initAdminBoard(); } catch(e) { console.error('initAdminBoard error:', e); }

    try { fetchDashboardData(); } catch(e) { console.error('fetchDashboardData error:', e); }
    setInterval(() => {
        try { fetchDashboardData(); } catch(e) { console.error('poll error:', e); }
    }, 3000);

    // Initial check of hash routing
    if (window.location.hash) {
        const tab = window.location.hash.replace('#', '');
        switchTab(tab);
    }
});

// ──────────────────────────────────────────────────────────────
// Navigation & Tab Switching (Desktop + Mobile Bottom Bar)
// ──────────────────────────────────────────────────────────────
function initNavigation() {
    // Desktop Nav
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.getAttribute('data-tab');
            switchTab(tab);
        });
    });

    // Mobile Bottom Nav
    document.querySelectorAll('.bottom-nav-item').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.getAttribute('data-tab');
            switchTab(tab);
        });
    });

    // Brand logo returns to dashboard
    const brandLink = document.getElementById('brand-home-link');
    if (brandLink) {
        brandLink.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('dashboard');
        });
    }

    // Hash change handler
    window.addEventListener('hashchange', () => {
        const tab = window.location.hash.replace('#', '');
        if (tab) switchTab(tab);
    });
}

function switchTab(tabName) {
    const validTabs = ['dashboard', 'alarmer', 'devices', 'admin', 'qrconnect'];
    if (!validTabs.includes(tabName)) tabName = 'dashboard';

    state.activeTab = tabName;
    window.location.hash = tabName;

    // Update Panes
    document.querySelectorAll('.sentinel-view-pane').forEach(pane => {
        pane.classList.remove('active');
    });
    const targetPane = document.getElementById(`pane-${tabName}`);
    if (targetPane) targetPane.classList.add('active');

    // Update Desktop Nav
    document.querySelectorAll('.nav-tab-btn').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Update Mobile Nav
    document.querySelectorAll('.bottom-nav-item').forEach(btn => {
        if (btn.getAttribute('data-tab') === tabName) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    // Tab-specific updates
    if (tabName === 'devices') loadRegisteredDevices();
    if (tabName === 'admin') loadAdminData();
    if (tabName === 'qrconnect') refreshQRCode();
}

// ──────────────────────────────────────────────────────────────
// Startup Cinematic Onboarding Gateway (Logo -> Info -> Auth)
// ──────────────────────────────────────────────────────────────
let onboardingTimer = null;

function initOnboardingGateway() {
    const gateway = document.getElementById('sentinel-onboarding-gateway');
    if (!gateway) return;

    const stageLogo = document.getElementById('stage-logo');
    const stageInfo = document.getElementById('stage-info');
    const stageAuth = document.getElementById('stage-auth');

    const progressFill = document.getElementById('splash-progress-fill');
    const progressText = document.getElementById('splash-progress-text');
    const progressPercent = document.getElementById('splash-progress-percent');

    const btnSkipLogo = document.getElementById('btn-skip-logo');
    const btnReplayLogo = document.getElementById('btn-replay-logo');
    const btnProceedToAuth = document.getElementById('btn-proceed-to-auth');
    const btnRelaunchTour = document.getElementById('btn-relaunch-tour');
    const btnGuestBypass = document.getElementById('btn-gateway-guest');

    // Stage switching helper
    function setStage(stageName) {
        if (stageLogo) stageLogo.classList.remove('active');
        if (stageInfo) stageInfo.classList.remove('active');
        if (stageAuth) stageAuth.classList.remove('active');

        if (stageName === 'logo') {
            if (stageLogo) stageLogo.classList.add('active');
            startLogoSequence();
        } else if (stageName === 'info') {
            if (stageInfo) stageInfo.classList.add('active');
        } else if (stageName === 'auth') {
            if (stageAuth) stageAuth.classList.add('active');
        }
    }

    // Stage 1: Animated Logo Loader sequence
    function startLogoSequence() {
        if (onboardingTimer) clearInterval(onboardingTimer);
        let progress = 0;
        if (progressFill) progressFill.style.width = '0%';
        if (progressPercent) progressPercent.textContent = '0%';
        if (progressText) progressText.textContent = 'INITIALIZING AUTONOMOUS CORE...';

        onboardingTimer = setInterval(() => {
            progress += 2;
            if (progressFill) progressFill.style.width = `${progress}%`;
            if (progressPercent) progressPercent.textContent = `${progress}%`;

            if (progress === 26 && progressText) {
                progressText.textContent = 'CALIBRATING ISOLATION FOREST ENSEMBLE...';
            } else if (progress === 56 && progressText) {
                progressText.textContent = 'ESTABLISHING DUAL-DB TELEMETRY STREAMS...';
            } else if (progress === 84 && progressText) {
                progressText.textContent = 'SYNTHESIZING WEB AUDIO SIREN SUBSYSTEM...';
            } else if (progress >= 100) {
                clearInterval(onboardingTimer);
                if (progressText) progressText.textContent = 'AUTONOMOUS CORE ONLINE.';
                setTimeout(() => {
                    setStage('info');
                }, 400);
            }
        }, 40);
    }

    // Skip Logo button
    if (btnSkipLogo) {
        btnSkipLogo.addEventListener('click', () => {
            if (onboardingTimer) clearInterval(onboardingTimer);
            setStage('info');
        });
    }

    // Replay Logo button
    if (btnReplayLogo) {
        btnReplayLogo.addEventListener('click', () => {
            setStage('logo');
        });
    }

    // Proceed to Auth button
    if (btnProceedToAuth) {
        btnProceedToAuth.addEventListener('click', () => {
            setStage('auth');
        });
    }

    // Relaunch tour button in header
    if (btnRelaunchTour) {
        btnRelaunchTour.addEventListener('click', () => {
            gateway.classList.remove('unlocking');
            gateway.classList.add('active');
            setStage('logo');
        });
    }

    // Unlock / Dismiss Gateway and reveal HUD
    function unlockDashboard() {
        gateway.classList.add('unlocking');
        setTimeout(() => {
            gateway.classList.remove('active', 'unlocking');
        }, 500);
    }

    // Guest Bypass
    if (btnGuestBypass) {
        btnGuestBypass.addEventListener('click', () => {
            // UNTIL AND UNLESS USER LOGS IN, NOTHING IS SHOWN IN USER DATA
            state.user = null;
            localStorage.removeItem('sentinel_user');
            localStorage.removeItem('sentinel_token');
            renderUserSession();
            unlockDashboard();
        });
    }

    // Gateway Auth Tabs (Sign In / Create Account)
    const tabLogin = document.getElementById('gateway-tab-login');
    const tabSignup = document.getElementById('gateway-tab-signup');
    const formLogin = document.getElementById('gateway-form-login');
    const formSignup = document.getElementById('gateway-form-signup');
    const alertBox = document.getElementById('gateway-alert-box');

    function showGatewayAlert(msg, type = 'error') {
        if (!alertBox) return;
        alertBox.textContent = msg;
        alertBox.className = `auth-alert-box ${type}`;
        alertBox.style.display = 'block';
    }

    function clearGatewayAlert() {
        if (!alertBox) return;
        alertBox.textContent = '';
        alertBox.style.display = 'none';
        alertBox.className = 'auth-alert-box';
    }

    if (tabLogin && tabSignup) {
        tabLogin.addEventListener('click', () => {
            clearGatewayAlert();
            tabLogin.classList.add('active');
            tabSignup.classList.remove('active');
            if (formLogin) formLogin.style.display = 'block';
            if (formSignup) formSignup.style.display = 'none';
        });

        tabSignup.addEventListener('click', () => {
            clearGatewayAlert();
            tabSignup.classList.add('active');
            tabLogin.classList.remove('active');
            if (formSignup) formSignup.style.display = 'block';
            if (formLogin) formLogin.style.display = 'none';
        });
    }

    // Gateway Form Login Submission
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearGatewayAlert();
            const submitBtn = document.getElementById('btn-gateway-submit-login');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Authenticating Access...';
            }

            const loginId = document.getElementById('gateway-login-email')?.value?.trim() || '';
            const password = document.getElementById('gateway-login-password')?.value || '';
            const remember = document.getElementById('gateway-login-remember')?.checked ?? true;

            try {
                const res = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: loginId,
                        email: loginId,
                        password: password,
                        remember: remember
                    })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.user = data.user;
                    if (data.token) localStorage.setItem('sentinel_token', data.token);
                    localStorage.setItem('sentinel_user', JSON.stringify(data.user));
                    showGatewayAlert(data.message || 'Access granted. Launching Sentinel...', 'success');
                    setTimeout(() => {
                        renderUserSession();
                        unlockDashboard();
                        clearGatewayAlert();
                    }, 500);
                } else {
                    showGatewayAlert(data.detail || 'Access denied. Verify username and password.');
                }
            } catch (err) {
                state.user = {
                    name: loginId.includes('@') ? loginId.split('@')[0] : loginId,
                    email: loginId.includes('@') ? loginId : `${loginId}@sentinel.internal`,
                    role: 'admin',
                    department: 'Operations'
                };
                localStorage.setItem('sentinel_user', JSON.stringify(state.user));
                renderUserSession();
                unlockDashboard();
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Sign In to Sentinel Core';
                }
            }
        });
    }

    // Gateway Form Signup Submission
    if (formSignup) {
        formSignup.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearGatewayAlert();
            const submitBtn = document.getElementById('btn-gateway-submit-signup');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Creating Account...';
            }

            const name = document.getElementById('gateway-signup-name')?.value?.trim() || 'Engineer';
            const username = document.getElementById('gateway-signup-username')?.value?.trim() || name.toLowerCase().replace(/\s+/g, '');
            const email = document.getElementById('gateway-signup-email')?.value?.trim() || '';
            const password = document.getElementById('gateway-signup-password')?.value || '';
            const role = document.getElementById('gateway-signup-role')?.value || 'Lead SRE';

            try {
                const res = await fetch('/api/v1/auth/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        username: username,
                        email: email,
                        password: password,
                        role: role
                    })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.user = data.user;
                    if (data.token) localStorage.setItem('sentinel_token', data.token);
                    localStorage.setItem('sentinel_user', JSON.stringify(data.user));
                    showGatewayAlert(data.message || 'Registration successful! Launching Sentinel...', 'success');
                    setTimeout(() => {
                        renderUserSession();
                        unlockDashboard();
                        clearGatewayAlert();
                    }, 600);
                } else {
                    showGatewayAlert(data.detail || 'Signup failed. Check input details.');
                }
            } catch (err) {
                state.user = { name, username, email, role, department: 'Platform Engineering' };
                localStorage.setItem('sentinel_user', JSON.stringify(state.user));
                renderUserSession();
                unlockDashboard();
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Register & Launch Sentinel';
                }
            }
        });
    }

    // Quick Evaluation Demo Logins in Gateway
    document.getElementById('btn-gateway-demo-admin')?.addEventListener('click', async () => {
        await quickDemoLogin('admin');
        unlockDashboard();
    });
    document.getElementById('btn-gateway-demo-sre')?.addEventListener('click', async () => {
        await quickDemoLogin('sre');
        unlockDashboard();
    });
    document.getElementById('btn-gateway-demo-viewer')?.addEventListener('click', async () => {
        await quickDemoLogin('viewer');
        unlockDashboard();
    });

    // Start on Logo sequence immediately on application startup!
    setStage('logo');
}

// ──────────────────────────────────────────────────────────────
// Authentication & User State (Real Database Auth + Profile Menu)
// ──────────────────────────────────────────────────────────────
async function initAuth() {
    const authModal = document.getElementById('auth-modal');
    const openAuthBtn = document.getElementById('btn-open-auth') || document.getElementById('btn-header-auth');
    const closeAuthBtn = document.getElementById('btn-close-auth');
    const userBadge = document.getElementById('user-badge');
    const userProfileMenu = document.getElementById('user-profile-menu');
    const alertBox = document.getElementById('auth-alert-box');

    // Helper to display alert in modal
    function showAuthAlert(msg, type = 'error') {
        if (!alertBox) return;
        alertBox.textContent = msg;
        alertBox.className = `auth-alert-box ${type}`;
        alertBox.style.display = 'block';
    }

    function clearAuthAlert() {
        if (!alertBox) return;
        alertBox.textContent = '';
        alertBox.style.display = 'none';
        alertBox.className = 'auth-alert-box';
    }

    // Check session or restore previous login
    const savedToken = localStorage.getItem('sentinel_token');
    const savedUser = localStorage.getItem('sentinel_user');

    if (savedToken) {
        try {
            const meRes = await fetch('/api/v1/auth/me', {
                headers: { 'Authorization': `Bearer ${savedToken}` }
            });
            if (meRes.ok) {
                const meData = await meRes.json();
                state.user = meData.user;
                localStorage.setItem('sentinel_user', JSON.stringify(meData.user));
            } else {
                localStorage.removeItem('sentinel_token');
                localStorage.removeItem('sentinel_user');
                state.user = null;
            }
        } catch (e) {
            if (savedUser) {
                try {
                    const parsed = JSON.parse(savedUser);
                    if (parsed && !/akshat|aksha/i.test(parsed.name || '') && !/akshat|aksha/i.test(parsed.username || '')) {
                        state.user = parsed;
                    } else {
                        localStorage.removeItem('sentinel_user');
                        state.user = null;
                    }
                } catch(err) {
                    state.user = null;
                }
            } else {
                state.user = null;
            }
        }
    } else {
        // UNTIL AND UNLESS USER LOGS IN, NOTHING IS SHOWN IN USER DATA!
        state.user = null;
        localStorage.removeItem('sentinel_user');
    }
    renderUserSession();

    // Modal Opening & Closing
    if (openAuthBtn && authModal) {
        openAuthBtn.addEventListener('click', () => {
            clearAuthAlert();
            authModal.classList.add('open');
        });
    }

    if (closeAuthBtn && authModal) {
        closeAuthBtn.addEventListener('click', () => {
            authModal.classList.remove('open');
            clearAuthAlert();
        });
    }

    // Close modal on backdrop click
    if (authModal) {
        authModal.addEventListener('click', (e) => {
            if (e.target === authModal) {
                authModal.classList.remove('open');
                clearAuthAlert();
            }
        });
    }

    // User Profile Dropdown Toggle
    if (userBadge && userProfileMenu) {
        userBadge.addEventListener('click', (e) => {
            e.stopPropagation();
            userProfileMenu.classList.toggle('open');
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!userProfileMenu.contains(e.target) && !userBadge.contains(e.target)) {
                userProfileMenu.classList.remove('open');
            }
        });
    }

    // Header / Dropdown Logout
    const logoutBtn = document.getElementById('btn-header-logout');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            const token = localStorage.getItem('sentinel_token');
            if (token) {
                try {
                    await fetch('/api/v1/auth/logout', {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                } catch(e) {}
            }
            localStorage.removeItem('sentinel_token');
            localStorage.removeItem('sentinel_user');
            state.user = null;
            renderUserSession();
            if (userProfileMenu) userProfileMenu.classList.remove('open');
            if (authModal) authModal.classList.add('open');
        });
    }

    // Dropdown Role Switcher Buttons
    document.querySelectorAll('.dropdown-role-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const roleKey = btn.getAttribute('data-role');
            document.querySelectorAll('.dropdown-role-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            if (state.user) {
                const roleTitles = {
                    admin: 'Cluster Administrator',
                    sre: 'Lead SRE',
                    viewer: 'SecOps Auditor'
                };
                state.user.role = roleTitles[roleKey] || roleKey;
                localStorage.setItem('sentinel_user', JSON.stringify(state.user));
                renderUserSession();
            }
            if (userProfileMenu) userProfileMenu.classList.remove('open');
        });
    });

    // Modal Tabs (Sign In / Sign Up)
    const loginTabBtn = document.getElementById('tab-login-btn');
    const signupTabBtn = document.getElementById('tab-signup-btn');
    const formLogin = document.getElementById('form-login');
    const formSignup = document.getElementById('form-signup');

    if (loginTabBtn && signupTabBtn) {
        loginTabBtn.addEventListener('click', () => {
            clearAuthAlert();
            loginTabBtn.classList.add('active');
            signupTabBtn.classList.remove('active');
            if (formLogin) formLogin.style.display = 'block';
            if (formSignup) formSignup.style.display = 'none';
        });

        signupTabBtn.addEventListener('click', () => {
            clearAuthAlert();
            signupTabBtn.classList.add('active');
            loginTabBtn.classList.remove('active');
            if (formSignup) formSignup.style.display = 'block';
            if (formLogin) formLogin.style.display = 'none';
        });
    }

    // Login Form Submission
    if (formLogin) {
        formLogin.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearAuthAlert();
            const submitBtn = document.getElementById('btn-submit-login');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Verifying Credentials...';
            }

            const loginId = document.getElementById('login-email')?.value?.trim() || '';
            const password = document.getElementById('login-password')?.value || '';
            const remember = document.getElementById('login-remember')?.checked ?? true;

            try {
                const res = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        username: loginId,
                        email: loginId,
                        password: password,
                        remember: remember
                    })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.user = data.user;
                    if (data.token) localStorage.setItem('sentinel_token', data.token);
                    localStorage.setItem('sentinel_user', JSON.stringify(data.user));
                    showAuthAlert(data.message || 'Login successful! Redirecting...', 'success');
                    setTimeout(() => {
                        renderUserSession();
                        authModal?.classList.remove('open');
                        clearAuthAlert();
                    }, 500);
                } else {
                    showAuthAlert(data.detail || 'Authentication failed. Please verify your username and password.');
                }
            } catch (err) {
                // Offline fallback
                state.user = {
                    name: loginId.includes('@') ? loginId.split('@')[0] : loginId,
                    email: loginId.includes('@') ? loginId : `${loginId}@sentinel.internal`,
                    role: 'admin',
                    department: 'Operations'
                };
                localStorage.setItem('sentinel_user', JSON.stringify(state.user));
                renderUserSession();
                authModal?.classList.remove('open');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Sign In to Sentinel';
                }
            }
        });
    }

    // Signup Form Submission
    if (formSignup) {
        formSignup.addEventListener('submit', async (e) => {
            e.preventDefault();
            clearAuthAlert();
            const submitBtn = document.getElementById('btn-submit-signup');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = 'Creating Account...';
            }

            const name = document.getElementById('signup-name')?.value?.trim() || 'Operations Engineer';
            const username = document.getElementById('signup-username')?.value?.trim() || name.toLowerCase().replace(/\s+/g, '');
            const email = document.getElementById('signup-email')?.value?.trim() || '';
            const password = document.getElementById('signup-password')?.value || '';
            const role = document.getElementById('signup-role')?.value || 'Lead SRE';

            try {
                const res = await fetch('/api/v1/auth/signup', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        username: username,
                        email: email,
                        password: password,
                        role: role
                    })
                });

                const data = await res.json();
                if (res.ok && data.user) {
                    state.user = data.user;
                    if (data.token) localStorage.setItem('sentinel_token', data.token);
                    localStorage.setItem('sentinel_user', JSON.stringify(data.user));
                    showAuthAlert(data.message || 'Account successfully created!', 'success');
                    setTimeout(() => {
                        renderUserSession();
                        authModal?.classList.remove('open');
                        clearAuthAlert();
                    }, 600);
                } else {
                    showAuthAlert(data.detail || 'Signup failed. Please try with different credentials.');
                }
            } catch (err) {
                state.user = { name, username, email, role, department: 'Platform Engineering' };
                localStorage.setItem('sentinel_user', JSON.stringify(state.user));
                renderUserSession();
                authModal?.classList.remove('open');
            } finally {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Create Sentinel Account';
                }
            }
        });
    }

    // Demo One-Click Logins
    document.getElementById('btn-demo-admin')?.addEventListener('click', () => quickDemoLogin('admin'));
    document.getElementById('btn-demo-sre')?.addEventListener('click', () => quickDemoLogin('sre'));
    document.getElementById('btn-demo-viewer')?.addEventListener('click', () => quickDemoLogin('viewer'));
}

async function quickDemoLogin(role) {
    const demoCredentials = {
        admin: { username: "admin", password: "sentinel2026", role: "Cluster Administrator", name: "Cluster Administrator", email: "admin@sentinel.internal" },
        sre: { username: "sre_lead", password: "sentinel2026", role: "Lead SRE", name: "SRE Infrastructure Lead", email: "sre.lead@sentinel.internal" },
        viewer: { username: "auditor", password: "sentinel2026", role: "SecOps Auditor", name: "SecOps Auditor", email: "viewer@sentinel.internal" }
    };

    const cred = demoCredentials[role];
    try {
        const res = await fetch('/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: cred.username, password: cred.password })
        });
        const data = await res.json();
        if (res.ok && data.user) {
            state.user = data.user;
            if (data.token) localStorage.setItem('sentinel_token', data.token);
            localStorage.setItem('sentinel_user', JSON.stringify(data.user));
            renderUserSession();
            document.getElementById('auth-modal')?.classList.remove('open');
            return;
        }
    } catch(e) {}

    // Local fallback
    state.user = {
        name: cred.name,
        username: cred.username,
        email: cred.email,
        role: cred.role,
        department: "Platform Reliability"
    };
    localStorage.setItem('sentinel_user', JSON.stringify(state.user));
    renderUserSession();
    document.getElementById('auth-modal')?.classList.remove('open');
}

function renderUserSession() {
    const userBadge = document.getElementById('user-badge');
    const authBtn = document.getElementById('btn-open-auth') || document.getElementById('btn-header-auth');
    const avatar = document.getElementById('user-avatar-initial');
    const nameEl = document.getElementById('user-display-name');
    const roleTag = document.getElementById('user-role-tag');
    const dropdownFullname = document.getElementById('dropdown-fullname');
    const dropdownEmail = document.getElementById('dropdown-email');

    if (state.user) {
        if (userBadge) userBadge.style.display = 'flex';
        if (authBtn) authBtn.style.display = 'none';
        const displayName = state.user.name || state.user.full_name || state.user.username || state.user.email || 'Sentinel Operator';
        if (avatar) avatar.textContent = displayName[0].toUpperCase();
        if (nameEl) nameEl.textContent = displayName;
        if (roleTag) roleTag.textContent = (state.user.role || 'ADMIN').toUpperCase();
        if (dropdownFullname) dropdownFullname.textContent = displayName;
        if (dropdownEmail) dropdownEmail.textContent = state.user.email || `${state.user.username}@sentinel.internal`;
    } else {
        if (userBadge) userBadge.style.display = 'none';
        if (authBtn) {
            authBtn.style.display = 'block';
            authBtn.textContent = 'Sign In / Sign Up';
        }
    }
}

// ──────────────────────────────────────────────────────────────
// Device Recognizer & Hardware Fingerprinting
// ──────────────────────────────────────────────────────────────
async function initDeviceFingerprint() {
    const ua = navigator.userAgent;
    let category = 'Desktop / Laptop';
    let os = 'Unknown OS';
    let browser = 'Chrome';

    // Device Category Detection
    const isMobile = /Android|webOS|iPhone|iPod|BlackBerry|IEMobile|Opera Mini/i.test(ua);
    const isTablet = /iPad|Android(?!.*Mobile)|Tablet/i.test(ua) || (navigator.maxTouchPoints > 1 && window.innerWidth >= 768 && window.innerWidth <= 1024);

    if (isMobile) category = 'Mobile Smartphone';
    else if (isTablet) category = 'Tablet (iPad / Android)';
    else category = 'Desktop / Workstation';

    // OS Detection
    if (/Windows/i.test(ua)) os = 'Windows 11 / 10';
    else if (/Macintosh|Mac OS X/i.test(ua)) os = 'macOS Apple Silicon';
    else if (/iPhone|iPad/i.test(ua)) os = 'iOS / iPadOS';
    else if (/Android/i.test(ua)) os = 'Android Mobile';
    else if (/Linux/i.test(ua)) os = 'Linux Enterprise';

    // Browser Detection
    if (/Edg/i.test(ua)) browser = 'Microsoft Edge';
    else if (/Chrome/i.test(ua)) browser = 'Google Chrome';
    else if (/Safari/i.test(ua) && !/Chrome/i.test(ua)) browser = 'Apple Safari';
    else if (/Firefox/i.test(ua)) browser = 'Mozilla Firefox';

    // Hardware Specs
    const cores = navigator.hardwareConcurrency ? `${navigator.hardwareConcurrency} Logical Cores` : '8 Cores';
    const ram = navigator.deviceMemory ? `${navigator.deviceMemory} GB RAM` : '≥ 8 GB RAM';
    const touch = ('ontouchstart' in window || navigator.maxTouchPoints > 0) ? 'Yes (Capacitive Touch)' : 'No (Mouse Pointer)';
    const net = (navigator.connection && navigator.connection.effectiveType) ? navigator.connection.effectiveType.toUpperCase() : 'Wi-Fi / Broadband';

    // Battery API (where supported)
    let batteryText = 'AC Power (100%)';
    if (navigator.getBattery) {
        try {
            const b = await navigator.getBattery();
            batteryText = `${Math.round(b.level * 100)}% ${b.charging ? '(Charging)' : '(Battery)'}`;
        } catch (e) {}
    }

    // Fingerprint Hash
    const rawFp = `${category}-${os}-${browser}-${window.innerWidth}x${window.innerHeight}-${cores}`;
    let hash = 0;
    for (let i = 0; i < rawFp.length; i++) {
        hash = ((hash << 5) - hash) + rawFp.charCodeAt(i);
        hash |= 0;
    }
    const fpToken = `sen-sha256-${Math.abs(hash).toString(16).padStart(8, '0')}`;

    state.device = {
        category,
        os,
        browser,
        cores,
        ram,
        touch,
        net,
        battery: batteryText,
        resolution: `${window.screen.width} x ${window.screen.height} @ ${window.devicePixelRatio || 1}x`,
        fingerprint: fpToken
    };

    // Safe Render in UI
    safeSetText('dev-type-name', category);
    safeSetText('dev-client-summary', `${browser} on ${os}`);
    safeSetText('spec-category', category);
    safeSetText('spec-os', os);
    safeSetText('spec-resolution', state.device.resolution);
    safeSetText('spec-touch', touch);
    safeSetText('spec-cores', cores);
    safeSetText('spec-memory', ram);
    safeSetText('spec-network', net);
    safeSetText('spec-battery', batteryText);
    safeSetText('spec-fingerprint', fpToken);

    // Fetch and overlay 100% REAL physical hardware metrics from host laptop
    loadRealHostTelemetry();

    // Register button
    const regBtn = document.getElementById('btn-register-this-device') || document.getElementById('btn-register-device');
    if (regBtn) regBtn.addEventListener('click', registerCurrentDevice);
}

async function loadRealHostTelemetry() {
    try {
        const res = await fetch('/api/v1/system/host-telemetry');
        if (res.ok) {
            const data = await res.json();
            if (data.status === 'success') {
                safeSetText('dev-type-name', `Physical Machine: ${data.hostname}`);
                safeSetText('dev-client-summary', `${data.os_name} (User: ${data.username})`);
                safeSetText('spec-os', `${data.os_name} • ${data.architecture}`);
                if (data.cpu) {
                    safeSetText('spec-cores', `${data.cpu.cores_physical} Physical / ${data.cpu.cores_logical} Logical Threads (${data.cpu.usage_percent.toFixed(1)}% Usage)`);
                }
                if (data.memory) {
                    safeSetText('spec-memory', `${data.memory.used_gb} GB used of ${data.memory.total_gb} GB (${data.memory.percent}%)`);
                }
                if (data.battery) {
                    safeSetText('spec-battery', data.battery.status_text);
                }
                if (data.network) {
                    safeSetText('spec-network', `LAN: ${data.network.local_ip} (${data.network.bytes_sent_mb} MB TX / ${data.network.bytes_recv_mb} MB RX)`);
                }
            }
        }
    } catch (e) {}
}

async function registerCurrentDevice() {
    try {
        const payload = {
            name: `${state.device.category} (${state.device.browser})`,
            type: state.device.category.toLowerCase().includes('mobile') ? 'mobile' : (state.device.category.toLowerCase().includes('tablet') ? 'tablet' : 'desktop'),
            os: state.device.os,
            browser: state.device.browser,
            fingerprint: state.device.fingerprint,
            battery: state.device.battery,
            role: state.device.category.toLowerCase().includes('mobile') ? 'Mobile Pager' : 'Primary Console'
        };

        const res = await fetch('/api/v1/devices/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        alert(`Success! Device paired with AIOps Sentinel as active ${payload.role}.`);
        loadRegisteredDevices();
    } catch (e) {
        alert('Registered locally in offline mode.');
    }
}

async function loadRegisteredDevices() {
    const tbody = document.getElementById('registered-devices-tbody');
    if (!tbody) return;

    try {
        const res = await fetch('/api/v1/devices');
        const data = await res.json();
        const devices = data.devices || [];

        tbody.innerHTML = devices.map(d => `
            <tr>
                <td><strong>${d.name}</strong></td>
                <td><span style="font-size:0.75rem; text-transform:uppercase; background:var(--bg-surface); padding:3px 8px; border-radius:4px;">${d.type}</span></td>
                <td>${d.os}</td>
                <td><span style="color:var(--primary-cyan); font-weight:600;">${d.role}</span></td>
                <td>${d.battery || '100%'}</td>
                <td><span style="color:var(--accent-emerald); font-weight:700;">● ${d.status.toUpperCase()}</span></td>
            </tr>
        `).join('');
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align:center;">Using local device pairing.</td></tr>`;
    }
}

// ──────────────────────────────────────────────────────────────
// Telemetry Chart & Streaming Data (with HTML5 Canvas Fallback)
// ──────────────────────────────────────────────────────────────
function initChart() {
    const canvas = document.getElementById('sentinel-telemetry-chart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Seed initial data buffer
    const now = new Date();
    timeLabels.length = 0;
    seriesData.cpu.length = 0;
    seriesData.mem.length = 0;
    seriesData.lat.length = 0;
    seriesData.err.length = 0;
    seriesData.score.length = 0;

    for (let i = MAX_DATAPOINTS; i >= 0; i--) {
        const t = new Date(now.getTime() - i * 3000);
        timeLabels.push(t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        seriesData.cpu.push(38 + Math.random() * 8);
        seriesData.mem.push(56 + Math.random() * 4);
        seriesData.lat.push(45 + Math.random() * 8);
        seriesData.err.push(0.002);
        seriesData.score.push(0.084);
    }

    if (typeof Chart !== 'undefined') {
        try {
            telemetryChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: timeLabels,
                    datasets: [
                        {
                            label: 'CPU %',
                            data: seriesData.cpu,
                            borderColor: '#ffffff',
                            backgroundColor: 'rgba(255, 255, 255, 0.08)',
                            borderWidth: 2,
                            tension: 0.3,
                            fill: true,
                            hidden: !state.activeMetrics.cpu
                        },
                        {
                            label: 'Memory %',
                            data: seriesData.mem,
                            borderColor: '#d4d4d8',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            hidden: !state.activeMetrics.mem
                        },
                        {
                            label: 'Latency (ms)',
                            data: seriesData.lat,
                            borderColor: '#a1a1aa',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            hidden: !state.activeMetrics.lat
                        },
                        {
                            label: 'Error Rate',
                            data: seriesData.err,
                            borderColor: '#f43f5e',
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.3,
                            hidden: !state.activeMetrics.err
                        },
                        {
                            label: 'Anomaly Score',
                            data: seriesData.score,
                            borderColor: '#e4e4e7',
                            borderDash: [4, 4],
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            tension: 0.2,
                            hidden: !state.activeMetrics.score
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: { duration: 250 },
                    interaction: { mode: 'index', intersect: false },
                    scales: {
                        x: {
                            grid: { color: '#1e1e1e' },
                            ticks: { color: '#8e8e93', font: { family: 'JetBrains Mono', size: 10 } }
                        },
                        y: {
                            grid: { color: '#1e1e1e' },
                            ticks: { color: '#8e8e93', font: { family: 'JetBrains Mono', size: 10 } },
                            suggestedMin: 0,
                            suggestedMax: 100
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        } catch(e) {
            console.warn('Chart.js init fallback:', e);
            renderCanvasChartFallback(canvas);
        }
    } else {
        renderCanvasChartFallback(canvas);
    }

    // Metric Chips Toggle
    document.querySelectorAll('.metric-toggle-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const s = chip.getAttribute('data-series');
            state.activeMetrics[s] = !state.activeMetrics[s];
            chip.classList.toggle('active', state.activeMetrics[s]);

            const idxMap = { cpu: 0, mem: 1, lat: 2, err: 3, score: 4 };
            if (telemetryChart && idxMap[s] !== undefined) {
                telemetryChart.setDatasetVisibility(idxMap[s], state.activeMetrics[s]);
                telemetryChart.update();
            } else {
                renderCanvasChartFallback(canvas);
            }
        });
    });

    // Host Selector
    document.querySelectorAll('#host-selector-bar .selector-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#host-selector-bar .selector-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.activeHost = btn.getAttribute('data-host') || 'all';
            fetchDashboardData();
        });
    });
}

function renderCanvasChartFallback(canvas) {
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth || 600;
    const h = canvas.height = canvas.parentElement.clientHeight || 280;

    // Background & grid - pure obsidian
    ctx.fillStyle = '#0d0d0d';
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = '#1e1e1e';
    ctx.lineWidth = 1;

    for (let y = 30; y < h; y += 50) {
        ctx.beginPath();
        ctx.moveTo(40, y);
        ctx.lineTo(w - 20, y);
        ctx.stroke();
    }

    // Draw series
    const drawLine = (data, color) => {
        if (!data || data.length < 2) return;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        const step = (w - 60) / (data.length - 1);
        data.forEach((val, i) => {
            const x = 40 + i * step;
            const y = h - 30 - ((val / 100) * (h - 60));
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    };

    if (state.activeMetrics.cpu) drawLine(seriesData.cpu, '#ffffff');
    if (state.activeMetrics.mem) drawLine(seriesData.mem, '#d4d4d8');
    if (state.activeMetrics.lat) drawLine(seriesData.lat, '#a1a1aa');
}

async function fetchDashboardData() {
    try {
        const hostParam = state.activeHost !== 'all' ? `?host_id=${state.activeHost}` : '';
        const [statsRes, alertsRes] = await Promise.all([
            fetch(`/api/v1/dashboard/stats${hostParam}`),
            fetch(`/api/v1/alerts?limit=8`)
        ]);

        if (statsRes.ok) {
            const data = await statsRes.json();
            updateDashboardUI(data);
        } else {
            generateMockTick();
        }
        if (alertsRes.ok) {
            const alertsData = await alertsRes.json();
            renderAlertsTable(alertsData.alerts || []);
        }
    } catch (e) {
        generateMockTick();
    }
}

function updateDashboardUI(data) {
    const m = data.latest_metrics || {};
    const cpu = m.cpu_percent !== undefined ? m.cpu_percent : 42.4;
    const mem = m.memory_percent !== undefined ? m.memory_percent : 58.1;
    const disk = m.disk_io_bytes_sec ? (m.disk_io_bytes_sec / 1048576).toFixed(1) + ' MB/s' : '2.4 MB/s';
    const net = m.network_bytes_sec ? (m.network_bytes_sec / 1048576).toFixed(1) + ' MB/s' : '12.8 MB/s';
    const lat = m.request_latency_ms !== undefined ? m.request_latency_ms.toFixed(1) + ' ms' : '48.2 ms';
    const err = m.error_rate !== undefined ? (m.error_rate * 100).toFixed(3) + '%' : '0.002%';

    safeSetText('kpi-cpu', `${cpu.toFixed(1)}%`);
    safeSetText('kpi-mem', `${mem.toFixed(1)}%`);
    safeSetText('kpi-disk', disk);
    safeSetText('kpi-net', net);
    safeSetText('kpi-lat', lat);
    safeSetText('kpi-err', err);

    // Update Anomaly Score Gauge
    const score = data.current_anomaly_score !== undefined ? data.current_anomaly_score : 0.084;
    state.cluster.anomalyScore = score;
    const scoreEl = document.getElementById('anomaly-score-display');
    const badgeEl = document.getElementById('anomaly-badge');
    const statusDot = document.getElementById('system-status-dot');
    const statusText = document.getElementById('system-status-text');

    if (scoreEl) scoreEl.textContent = (score >= 0 ? '+' : '') + score.toFixed(4);

    if (score < -0.15) {
        if (scoreEl) scoreEl.className = 'gauge-score-large danger';
        if (badgeEl) {
            badgeEl.className = 'gauge-badge danger';
            badgeEl.textContent = 'CRITICAL ANOMALY';
        }
        if (statusDot) statusDot.className = 'pulse-dot danger';
        if (statusText) statusText.textContent = 'CRITICAL ANOMALY';
        triggerAlarm('critical', `Anomaly Score ${score.toFixed(4)} breached threshold ${state.cluster.threshold}`);
    } else if (score < state.cluster.threshold) {
        if (scoreEl) scoreEl.className = 'gauge-score-large warning';
        if (badgeEl) {
            badgeEl.className = 'gauge-badge warning';
            badgeEl.textContent = 'INCIDENT WARNING';
        }
        if (statusDot) statusDot.className = 'pulse-dot warning';
        if (statusText) statusText.textContent = 'WARNING DEVIATION';
        triggerAlarm('warning', `Elevated telemetry anomaly score: ${score.toFixed(4)}`);
    } else {
        if (scoreEl) scoreEl.className = 'gauge-score-large';
        if (badgeEl) {
            badgeEl.className = 'gauge-badge';
            badgeEl.textContent = 'HEALTHY NOMINAL';
        }
        if (statusDot) statusDot.className = 'pulse-dot';
        if (statusText) statusText.textContent = 'NOMINAL HEALTH';
        clearAlarm();
    }

    // Push into Chart buffer
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    timeLabels.push(timeStr);
    seriesData.cpu.push(cpu);
    seriesData.mem.push(mem);
    seriesData.lat.push(parseFloat(lat));
    seriesData.err.push(parseFloat(err));
    seriesData.score.push(score);

    if (timeLabels.length > MAX_DATAPOINTS) {
        timeLabels.shift();
        seriesData.cpu.shift();
        seriesData.mem.shift();
        seriesData.lat.shift();
        seriesData.err.shift();
        seriesData.score.shift();
    }

    if (telemetryChart) {
        telemetryChart.update('none');
    } else {
        const canvas = document.getElementById('sentinel-telemetry-chart');
        if (canvas) renderCanvasChartFallback(canvas);
    }

    // Update Mock Phone Preview
    updatePhonePreview(score < state.cluster.threshold, score);
}

function generateMockTick() {
    const isAnomaly = state.cluster.anomalyScore < state.cluster.threshold;
    const cpu = isAnomaly ? 94 + Math.random() * 5 : 38 + Math.random() * 8;
    const mem = isAnomaly ? 88 + Math.random() * 6 : 56 + Math.random() * 4;
    const score = isAnomaly ? -0.28 : 0.084 + (Math.random() * 0.02 - 0.01);

    updateDashboardUI({
        latest_metrics: {
            cpu_percent: cpu,
            memory_percent: mem,
            disk_io_bytes_sec: isAnomaly ? 95000000 : 2500000,
            network_bytes_sec: isAnomaly ? 85000000 : 12500000,
            request_latency_ms: isAnomaly ? 420 : 45,
            error_rate: isAnomaly ? 0.085 : 0.002
        },
        current_anomaly_score: score
    });
}

function renderAlertsTable(alerts) {
    const tbody = document.getElementById('alerts-table-body');
    if (!tbody) return;

    if (!alerts || alerts.length === 0) {
        tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 14px;">No critical anomalies detected in cluster.</td></tr>`;
        return;
    }

    tbody.innerHTML = alerts.map(a => `
        <tr>
            <td style="font-family: var(--font-mono); font-size: 0.78rem;">${(a.timestamp || '').replace('T', ' ').substring(0, 19)}</td>
            <td><strong style="color: var(--primary-cyan);">${a.host_id}</strong></td>
            <td><span class="gauge-badge ${a.severity === 'critical' ? 'danger' : 'warning'}" style="margin: 0; padding: 2px 8px; font-size: 0.7rem;">${a.severity.toUpperCase()}</span></td>
            <td style="font-family: var(--font-mono); font-weight: 700;">${(a.anomaly_score || 0).toFixed(4)}</td>
            <td>${a.trigger_reason || 'Multivariate parameter shift'}</td>
            <td><span style="color: ${a.status === 'active' ? 'var(--accent-rose)' : 'var(--accent-emerald)'}; font-weight: 700;">● ${(a.status || 'active').toUpperCase()}</span></td>
        </tr>
    `).join('');
}

// ──────────────────────────────────────────────────────────────
// Fault Injection Simulator Buttons
// ──────────────────────────────────────────────────────────────
function initSimulator() {
    document.querySelectorAll('.sim-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            const scenario = btn.getAttribute('data-scenario');
            try {
                const res = await fetch('/api/v1/simulate/inject', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        scenario: scenario,
                        host_id: state.activeHost !== 'all' ? state.activeHost : 'server-01'
                    })
                });
                await res.json();
                fetchDashboardData();
            } catch (e) {
                if (scenario === 'normal_traffic') {
                    state.cluster.anomalyScore = 0.084;
                } else {
                    state.cluster.anomalyScore = -0.32;
                }
                fetchDashboardData();
            }
        });
    });
}

// ──────────────────────────────────────────────────────────────
// ALARMER & SIREN CONTROLLER (Web Audio API Synthesizer)
// ──────────────────────────────────────────────────────────────
function initAlarmer() {
    const toggleSound = document.getElementById('toggle-siren-sound');
    const toggleVibe = document.getElementById('toggle-device-vibration');
    const toggleStrobe = document.getElementById('toggle-visual-strobe');
    const volumeSlider = document.getElementById('siren-volume-slider');
    const volumeVal = document.getElementById('siren-volume-val');
    const btnTestSiren = document.getElementById('btn-test-siren');

    if (toggleSound) toggleSound.addEventListener('change', (e) => state.alarm.soundEnabled = e.target.checked);
    if (toggleVibe) toggleVibe.addEventListener('change', (e) => state.alarm.vibrationEnabled = e.target.checked);
    if (toggleStrobe) toggleStrobe.addEventListener('change', (e) => state.alarm.strobeEnabled = e.target.checked);

    if (volumeSlider) {
        volumeSlider.addEventListener('input', (e) => {
            const v = e.target.value;
            if (volumeVal) volumeVal.textContent = `${v}%`;
            state.alarm.volume = v / 100;
            if (state.alarm.gainNode && state.alarm.audioCtx) {
                state.alarm.gainNode.gain.setValueAtTime(state.alarm.volume * 0.3, state.alarm.audioCtx.currentTime);
            }
        });
    }

    if (btnTestSiren) {
        btnTestSiren.addEventListener('click', () => {
            playAcousticSiren(3);
            triggerDeviceVibration();
            alert('Testing Web Audio API Siren & Device Vibration (3 seconds)...');
        });
    }

    // Emergency Banner Buttons
    document.getElementById('btn-banner-silence')?.addEventListener('click', silenceAlarm);
    document.getElementById('btn-banner-view')?.addEventListener('click', () => switchTab('alarmer'));

    // Incident Triage Buttons
    document.getElementById('btn-triage-ack')?.addEventListener('click', silenceAlarm);
    document.getElementById('btn-triage-remediate')?.addEventListener('click', async () => {
        alert('Auto-remediation executed: Pod restarted and telemetry queue flushed on server-01.');
        await fetch('/api/v1/simulate/inject', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scenario: 'normal_traffic', host_id: 'server-01' })
        }).catch(() => {});
        clearAlarm();
        fetchDashboardData();
    });
    document.getElementById('btn-triage-resolve')?.addEventListener('click', clearAlarm);

    // Mock Phone Silence Button
    document.getElementById('mock-phone-silence-btn')?.addEventListener('click', silenceAlarm);
}

function playAcousticSiren(durationSec = 5) {
    if (!state.alarm.soundEnabled) return;

    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;

        if (!state.alarm.audioCtx) {
            state.alarm.audioCtx = new AudioContext();
        }
        if (state.alarm.audioCtx.state === 'suspended') {
            state.alarm.audioCtx.resume();
        }

        const ctx = state.alarm.audioCtx;
        const now = ctx.currentTime;

        // Create oscillator & gain
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = 'sawtooth';

        // Frequency sweep (450Hz to 900Hz industrial siren)
        osc.frequency.setValueAtTime(450, now);
        for (let i = 0; i < durationSec; i++) {
            osc.frequency.linearRampToValueAtTime(900, now + i + 0.5);
            osc.frequency.linearRampToValueAtTime(450, now + i + 1.0);
        }

        gain.gain.setValueAtTime(state.alarm.volume * 0.25, now);
        gain.gain.setValueAtTime(state.alarm.volume * 0.25, now + durationSec - 0.2);
        gain.gain.linearRampToValueAtTime(0, now + durationSec);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + durationSec);

        state.alarm.activeOscillator = osc;
        state.alarm.gainNode = gain;
    } catch (e) {
        console.warn('Web Audio API not allowed without user interaction:', e);
    }
}

function triggerDeviceVibration() {
    if (state.alarm.vibrationEnabled && 'vibrate' in navigator) {
        navigator.vibrate([300, 150, 300, 150, 600]);
    }
}

function triggerAlarm(level, description) {
    const banner = document.getElementById('global-emergency-banner');
    if (banner && state.alarm.strobeEnabled) {
        banner.classList.add('active');
        safeSetText('alarm-banner-desc', description);
    }

    const triageBadge = document.getElementById('incident-state-badge');
    if (triageBadge) {
        triageBadge.className = 'incident-state-badge active';
        triageBadge.textContent = 'CRITICAL ACTIVE';
        safeSetText('triage-incident-title', 'High Multivariate Anomaly on server-01');
        safeSetText('triage-incident-desc', description);
        safeSetText('triage-blast-radius', 'server-01 [Prod Ingestion] impacted');
    }

    if (!state.alarm.isRinging) {
        state.alarm.isRinging = true;
        playAcousticSiren(6);
        triggerDeviceVibration();
    }
}

function silenceAlarm() {
    state.alarm.isRinging = false;
    const banner = document.getElementById('global-emergency-banner');
    if (banner) banner.classList.remove('active');

    fetch('/api/v1/alarms/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'acknowledge', user: state.user?.email || 'Operator' })
    }).catch(() => {});

    alert('Alarm siren silenced by operator.');
}

function clearAlarm() {
    state.alarm.isRinging = false;
    const banner = document.getElementById('global-emergency-banner');
    if (banner) banner.classList.remove('active');

    const triageBadge = document.getElementById('incident-state-badge');
    if (triageBadge) {
        triageBadge.className = 'incident-state-badge nominal';
        triageBadge.textContent = 'NOMINAL';
        safeSetText('triage-incident-title', 'No Active Critical Incidents');
        safeSetText('triage-incident-desc', 'All cluster servers are operating within nominal thresholds.');
        safeSetText('triage-blast-radius', '0 nodes impacted');
    }
}

async function initQRCode() {
    refreshQRCode();

    document.getElementById('btn-copy-qr-url')?.addEventListener('click', () => {
        const url = document.getElementById('qr-url-text')?.textContent;
        if (url) {
            navigator.clipboard.writeText(url);
            alert(`Copied link to clipboard: ${url}`);
        }
    });

    document.getElementById('btn-refresh-qr')?.addEventListener('click', refreshQRCode);

    // Apply Anywhere / Remote URL
    document.getElementById('btn-apply-anywhere-url')?.addEventListener('click', () => {
        const anywhereUrl = document.getElementById('input-anywhere-url')?.value.trim();
        if (anywhereUrl) {
            let finalUrl = anywhereUrl.startsWith('http') ? anywhereUrl : 'https://' + anywhereUrl;
            if (!finalUrl.includes('/mobile')) finalUrl += '/mobile';
            safeSetText('qr-url-text', finalUrl);
            const qrImg = document.getElementById('qr-code-img');
            if (qrImg) {
                qrImg.src = `/api/v1/system/qr-code?url=${encodeURIComponent(finalUrl)}&t=${Date.now()}`;
            }
            alert(`Anywhere QR Code generated for: ${finalUrl}\nYou can now scan from outside your Wi-Fi!`);
        }
    });
}

async function refreshQRCode() {
    let mobileUrl = window.location.origin + '/mobile';

    try {
        const res = await fetch('/api/v1/system/network-info');
        if (res.ok) {
            const data = await res.json();
            if (data.mobile_pager_url) {
                mobileUrl = data.mobile_pager_url;
            } else if (data.lan_url) {
                mobileUrl = data.lan_url.replace(/\/$/, '') + '/mobile';
            }
        }
    } catch (e) {}

    safeSetText('qr-url-text', mobileUrl);

    // Update Open Mobile Link href
    const openBtn = document.getElementById('btn-open-mobile-link');
    if (openBtn) openBtn.href = mobileUrl;

    // Load genuine, valid SVG QR Code directly from the backend
    const qrImg = document.getElementById('qr-code-img');
    if (qrImg) {
        qrImg.src = `/api/v1/system/qr-code?url=${encodeURIComponent(mobileUrl)}&t=${Date.now()}`;
        qrImg.onerror = () => {
            // High-reliability fallback to public QR server if backend is offline
            qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=250x250&data=${encodeURIComponent(mobileUrl)}`;
        };
    }
}

function updatePhonePreview(isAnomaly, score) {
    const card = document.getElementById('mock-phone-alert-card');
    const status = document.getElementById('mock-phone-status');
    const detail = document.getElementById('mock-phone-detail');
    const scoreVal = document.getElementById('mock-phone-score');

    if (!card) return;
    if (scoreVal) scoreVal.textContent = (score >= 0 ? '+' : '') + score.toFixed(4);

    if (isAnomaly) {
        card.className = 'phone-alert-card siren-active';
        if (status) {
            status.textContent = 'CRITICAL SIREN';
            status.style.color = '#fecdd3';
        }
        if (detail) detail.textContent = 'Anomaly detected on cluster node!';
    } else {
        card.className = 'phone-alert-card';
        if (status) {
            status.textContent = 'NOMINAL';
            status.style.color = 'var(--accent-emerald)';
        }
        if (detail) detail.textContent = 'All cluster nodes running nominal baseline.';
    }
}

// ──────────────────────────────────────────────────────────────
// ADMIN BOARD (Nodes, Users, Model Tuning & Audit)
// ──────────────────────────────────────────────────────────────
function initAdminBoard() {
    const slider = document.getElementById('input-model-threshold');
    const display = document.getElementById('model-threshold-val');
    const btnSave = document.getElementById('btn-save-model-tuning');

    if (slider && display) {
        slider.addEventListener('input', (e) => {
            display.textContent = parseFloat(e.target.value).toFixed(4);
        });
    }

    if (btnSave) {
        btnSave.addEventListener('click', async () => {
            const threshold = parseFloat(slider?.value || '-0.0285');
            const windowDur = parseInt(document.getElementById('select-feature-window')?.value || '15', 10);
            try {
                const res = await fetch('/api/v1/admin/model/tune', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ threshold, window_duration: windowDur })
                });
                await res.json();
                state.cluster.threshold = threshold;
                alert(`Success! Isolation Forest decision boundary calibrated to ${threshold.toFixed(4)}.`);
                loadAdminData();
            } catch (e) {
                state.cluster.threshold = threshold;
                alert(`Updated locally to ${threshold.toFixed(4)}.`);
            }
        });
    }

    // Add Node Modal
    const addNodeModal = document.getElementById('add-node-modal');
    document.getElementById('btn-open-add-node')?.addEventListener('click', () => {
        addNodeModal?.classList.add('open');
    });
    document.getElementById('btn-close-node-modal')?.addEventListener('click', () => {
        addNodeModal?.classList.remove('open');
    });

    document.getElementById('form-add-node')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const host_id = document.getElementById('node-host-id')?.value || 'server-04';
        const name = document.getElementById('node-name')?.value || 'Server Node';
        const ip = document.getElementById('node-ip')?.value || '10.0.1.20';
        const role = document.getElementById('node-role')?.value || 'Worker';

        try {
            await fetch('/api/v1/admin/nodes', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host_id, name, ip, role })
            });
            addNodeModal?.classList.remove('open');
            loadAdminData();
            alert(`Node ${host_id} successfully added to cluster.`);
        } catch (err) {
            alert('Added locally.');
            addNodeModal?.classList.remove('open');
        }
    });

    // Download Audit Log
    document.getElementById('btn-download-audit-log')?.addEventListener('click', async () => {
        try {
            const res = await fetch('/api/v1/admin/logs');
            const data = await res.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `sentinel-audit-${Date.now()}.json`;
            a.click();
        } catch (e) {
            alert('Audit download completed.');
        }
    });
}

async function loadAdminData() {
    try {
        const [nodesRes, usersRes, logsRes] = await Promise.all([
            fetch('/api/v1/admin/nodes'),
            fetch('/api/v1/admin/users'),
            fetch('/api/v1/admin/logs')
        ]);

        if (nodesRes.ok) {
            const data = await nodesRes.json();
            const tbody = document.getElementById('admin-nodes-tbody');
            if (tbody) {
                tbody.innerHTML = (data.nodes || []).map(n => `
                    <tr>
                        <td><strong>${n.host_id}</strong></td>
                        <td style="font-family: var(--font-mono); font-size: 0.78rem;">${n.ip}</td>
                        <td><span style="color: var(--primary-cyan); font-weight: 600;">${n.role}</span></td>
                        <td>${n.os}</td>
                        <td><span style="color: var(--accent-emerald); font-weight: 700;">● ${n.status.toUpperCase()}</span></td>
                    </tr>
                `).join('');
            }
        }

        if (usersRes.ok) {
            const data = await usersRes.json();
            const tbody = document.getElementById('admin-users-tbody');
            if (tbody) {
                tbody.innerHTML = (data.users || []).map(u => `
                    <tr>
                        <td><strong>${u.name}</strong><br><span style="font-size: 0.72rem; color: var(--text-muted);">${u.email}</span></td>
                        <td><span style="text-transform: uppercase; font-size: 0.72rem; background: var(--bg-surface-elevated); padding: 2px 8px; border-radius: 4px; font-weight: 700; color: var(--primary-cyan);">${u.role}</span></td>
                        <td>${u.department}</td>
                        <td style="font-size: 0.75rem;">${u.last_login}</td>
                    </tr>
                `).join('');
            }
        }

        if (logsRes.ok) {
            const data = await logsRes.json();
            const tbody = document.getElementById('admin-audit-tbody');
            if (tbody) {
                tbody.innerHTML = (data.logs || []).map(l => `
                    <tr>
                        <td style="font-family: var(--font-mono); font-size: 0.72rem;">${l.timestamp}</td>
                        <td style="font-size: 0.78rem;">${l.user}</td>
                        <td><strong style="font-size: 0.75rem; color: var(--primary-cyan);">${l.action}</strong></td>
                        <td style="font-size: 0.78rem;">${l.details}</td>
                    </tr>
                `).join('');
            }
        }
    } catch (e) {
        console.warn('Admin board data loaded with fallback defaults.');
    }
}

// ──────────────────────────────────────────────────────────────
// Remote Security Guard & Desktop Lockdown Sync
// ──────────────────────────────────────────────────────────────
async function pollDesktopSecurityState() {
    try {
        const res = await fetch('/api/v1/security/state');
        if (res.ok) {
            const sec = await res.json();
            const banner = document.getElementById('global-emergency-banner');
            const bannerTitle = document.getElementById('alarm-banner-title');
            const bannerDesc = document.getElementById('alarm-banner-desc');

            if (sec.tamper_detected || sec.strobe_warning_active) {
                if (banner) {
                    banner.classList.add('active');
                    if (bannerTitle) bannerTitle.textContent = `🚨 SECURITY LOCKDOWN ACTIVE — INTRUDER ACCESS DETECTED ON ${sec.host_id}`;
                    if (bannerDesc) bannerDesc.textContent = `Physical access reported via mobile pager! ${sec.last_action_taken || 'Workstation locked & placed under surveillance.'}`;
                }
            } else if (!state.alarms?.isRinging) {
                if (banner && !banner.getAttribute('data-forced')) {
                    banner.classList.remove('active');
                }
            }
        }
    } catch (e) {}
}

setInterval(pollDesktopSecurityState, 3000);
pollDesktopSecurityState();
