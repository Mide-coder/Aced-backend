/**
 * Aced API Client — Shared module for all frontend pages
 * Handles authentication, token management, and all API calls.
 */
const API_BASE = 'http://localhost:8001';

// ── Token Management ─────────────────────────────────────────────────────────

const TOKEN_KEYS = {
  access: 'aced_access_token',
  refresh: 'aced_refresh_token',
  user: 'aced_user',
};

function getAccessToken() {
  return localStorage.getItem(TOKEN_KEYS.access);
}

function getRefreshToken() {
  return localStorage.getItem(TOKEN_KEYS.refresh);
}

function getUser() {
  const raw = localStorage.getItem(TOKEN_KEYS.user);
  try { return raw ? JSON.parse(raw) : null; } catch { return null; }
}

function saveTokens(access, refresh) {
  localStorage.setItem(TOKEN_KEYS.access, access);
  localStorage.setItem(TOKEN_KEYS.refresh, refresh);
}

function saveUser(user) {
  localStorage.setItem(TOKEN_KEYS.user, JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEYS.access);
  localStorage.removeItem(TOKEN_KEYS.refresh);
  localStorage.removeItem(TOKEN_KEYS.user);
}

function isAuthenticated() {
  return !!getAccessToken() && !!getUser();
}

// ── Token Refresh (single-flight) ─────────────────────────────────────────────
// Prevents concurrent refresh storms when several 401s fire at once.

let refreshInFlight = null;

async function refreshAccessToken() {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const refresh = getRefreshToken();
    if (!refresh) throw new Error('No refresh token');

    const result = await apiRequest('/auth/refresh', {
      method: 'POST',
      body: { refresh_token: refresh },
      useAuth: false,
    });

    saveTokens(result.access_token, result.refresh_token);
    return true;
  })();

  try {
    return await refreshInFlight;
  } finally {
    refreshInFlight = null;
  }
}

// ── API Request Helper ────────────────────────────────────────────────────────

async function apiRequest(path, options = {}, _retried = false) {
  const { method = 'GET', body, useAuth = true, formData = false, params } = options;

  const headers = {};
  if (!formData) {
    headers['Content-Type'] = 'application/json';
  }
  if (useAuth && getAccessToken()) {
    headers['Authorization'] = `Bearer ${getAccessToken()}`;
  }

  let url = `${API_BASE}${path}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') searchParams.append(k, v);
    });
    const qs = searchParams.toString();
    if (qs) url += `?${qs}`;
  }

  const fetchOptions = { method, headers };
  if (body) {
    fetchOptions.body = formData ? body : JSON.stringify(body);
  }

  try {
    const res = await fetch(url, fetchOptions);
    const contentType = res.headers.get('content-type') || '';

    // Handle 204 No Content
    if (res.status === 204) return null;

    // ── 401 auto-refresh interceptor ──
    // On an expired access token, silently refresh once and retry the request.
    if (res.status === 401 && useAuth && !_retried && getRefreshToken()) {
      try {
        await refreshAccessToken();
        return await apiRequest(path, options, true);
      } catch (refreshErr) {
        clearAuth();
        const onAuthPage = ['auth.html', 'login.html'].some(p => window.location.pathname.endsWith(p));
        if (!onAuthPage) {
          window.location.href = 'auth.html?reason=session-expired';
        }
        throw new Error('Session expired. Please sign in again.');
      }
    }

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}`;
      try {
        const errBody = await res.json();
        errorDetail = errBody.detail || errorDetail;
      } catch {}
      throw new Error(errorDetail);
    }

    if (contentType.includes('application/json')) {
      return await res.json();
    }
    return await res.text();
  } catch (err) {
    if (err.name === 'TypeError' && err.message === 'Failed to fetch') {
      throw new Error('Cannot connect to server. Make sure the backend is running on port 8001.');
    }
    throw err;
  }
}

// ── Auth API ─────────────────────────────────────────────────────────────────

async function registerUser(data) {
  const user = await apiRequest('/auth/register', {
    method: 'POST',
    body: {
      email: data.email,
      password: data.password,
      full_name: data.full_name,
      role: data.role || 'student',
      phone: data.phone || '',
    },
    useAuth: false,
  });
  return user;
}

async function loginUser(email, password) {
  const formData = new URLSearchParams();
  formData.append('username', email);
  formData.append('password', password);

  const result = await apiRequest('/auth/login', {
    method: 'POST',
    body: formData,
    formData: true,
    useAuth: false,
  });

  if (result.access_token) {
    saveTokens(result.access_token, result.refresh_token);
    // Fetch user profile
    const user = await getMe();
    saveUser(user);
    return user;
  }
  throw new Error('Login failed — no token returned');
}

async function googleSignIn(credential, role = 'student') {
  const result = await apiRequest('/auth/google', {
    method: 'POST',
    body: { credential, role },
    useAuth: false,
  });

  if (result.access_token) {
    saveTokens(result.access_token, result.refresh_token);
    const user = await getMe();
    saveUser(user);
    return user;
  }
  throw new Error('Google sign-in failed — no token returned');
}

async function logoutUser() {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await apiRequest('/auth/logout', {
        method: 'POST',
        body: { refresh_token: refresh },
      });
    }
  } catch {}
  clearAuth();
  window.location.href = 'auth.html';
}

async function getMe() {
  return await apiRequest('/auth/me');
}

// ── Courses API ───────────────────────────────────────────────────────────────

async function getCourses() {
  return await apiRequest('/courses', { useAuth: false });
}

// ── Tutors API ────────────────────────────────────────────────────────────────

async function searchTutors(filters = {}) {
  return await apiRequest('/tutors/search', { useAuth: false, params: filters });
}

async function getTutor(tutorId) {
  return await apiRequest(`/tutors/${tutorId}`, { useAuth: false });
}

async function getTutorReviews(tutorId) {
  return await apiRequest(`/tutors/${tutorId}/reviews`, { useAuth: false });
}

async function getMyTutorProfile() {
  return await apiRequest('/tutors/me');
}

async function createTutorProfile(data) {
  const formData = new FormData();
  if (data.bio) formData.append('bio', data.bio);
  formData.append('hourly_rate', String(data.hourly_rate || 2500));

  return await apiRequest('/tutors/profile', {
    method: 'POST',
    body: formData,
    formData: true,
  });
}

// ── Bookings API ──────────────────────────────────────────────────────────────

async function createBooking(data) {
  return await apiRequest('/bookings/', {
    method: 'POST',
    body: data,
  });
}

async function getMyBookings() {
  return await apiRequest('/bookings/my-bookings');
}

async function getBookingByReference(reference) {
  return await apiRequest(`/bookings/by-reference/${encodeURIComponent(reference)}`);
}

async function updateBookingStatus(bookingId, targetStatus) {
  return await apiRequest(`/bookings/${bookingId}/status`, {
    method: 'PATCH',
    params: { target_status: targetStatus },
  });
}

async function cancelBooking(bookingId) {
  return await apiRequest(`/bookings/${bookingId}/cancel`, {
    method: 'POST',
  });
}

async function createAvailabilitySlot(data) {
  return await apiRequest('/bookings/availability', {
    method: 'POST',
    body: data,
  });
}

async function getTutorAvailability(tutorId) {
  return await apiRequest(`/bookings/availability/${tutorId}`, { useAuth: false });
}

// ── Payments API ──────────────────────────────────────────────────────────────

async function initializePayment(bookingId) {
  return await apiRequest('/payments/initialize', {
    method: 'POST',
    params: { booking_id: bookingId },
  });
}

// ── Admin API ─────────────────────────────────────────────────────────────────

async function getVerificationRequests(statusFilter) {
  return await apiRequest('/admin/verification-requests', {
    params: statusFilter ? { status_filter: statusFilter } : {},
  });
}

async function reviewVerificationRequest(requestId, data) {
  return await apiRequest(`/admin/verification-requests/${requestId}`, {
    method: 'PATCH',
    body: data,
  });
}

async function toggleGradeVerification(tutorId, data) {
  return await apiRequest(`/admin/tutors/${tutorId}/grade-verify`, {
    method: 'PATCH',
    body: data,
  });
}

async function getPayoutLedger(tutorPaid) {
  return await apiRequest('/admin/payout-ledger', {
    params: tutorPaid !== undefined ? { tutor_paid: tutorPaid } : {},
  });
}

async function recordPayout(bookingId) {
  return await apiRequest(`/admin/payout-ledger/${bookingId}/record-payout`, {
    method: 'POST',
  });
}
