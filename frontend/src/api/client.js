import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

export const client = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token');
    if (token) config.headers.Authorization = `Bearer ${token}`;
    if (config.data instanceof FormData && config.headers) {
      delete config.headers['Content-Type'];
    }
    return config;
  },
  (err) => Promise.reject(err)
);

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status !== 401 || originalRequest._retry) {
      return Promise.reject(error);
    }
    originalRequest._retry = true;
    try {
      const refreshToken = localStorage.getItem('refresh_token');
      const { data } = await axios.post(
        `${API_BASE_URL}/auth/token/refresh/`,
        { refresh: refreshToken }
      );
      localStorage.setItem('access_token', data.access);
      originalRequest.headers.Authorization = `Bearer ${data.access}`;
      return client(originalRequest);
    } catch {
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/';
      return Promise.reject(error);
    }
  }
);

export const ADMIN_LOGIN_URL = API_BASE_URL.replace(/\/api\/?$/, '') + '/admin/';
export { API_BASE_URL };
