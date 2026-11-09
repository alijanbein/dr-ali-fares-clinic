import axios from 'axios';

export const API_BASE = import.meta.env.VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8002`;

const api = axios.create({ baseURL: API_BASE });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('clinic_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && localStorage.getItem('clinic_token')) {
      localStorage.removeItem('clinic_token');
      localStorage.removeItem('clinic_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  },
);

// For URLs opened directly by <audio>/<img>/<a>, which can't send a header.
export function withToken(path) {
  const token = localStorage.getItem('clinic_token') || '';
  return `${API_BASE}${path}${path.includes('?') ? '&' : '?'}token=${encodeURIComponent(token)}`;
}

export function errorMessage(err, fallback = 'Something went wrong') {
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (err?.message === 'Network Error') return 'Cannot reach the clinic server';
  return fallback;
}

export default api;
