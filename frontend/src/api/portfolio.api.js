import axios from 'axios';
import { API_BASE_URL } from './client';

/**
 * Axios instance for public portfolio routes — no JWT / Authorization header.
 */
const publicPortfolioHttp = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: false,
});

/**
 * Fetch a student's public portfolio (employer-facing, unauthenticated).
 * @param {string} username
 * @returns {Promise<{ profile: object, top_projects: object[] }>}
 */
export async function getPublicPortfolio(username) {
  const { data } = await publicPortfolioHttp.get(`/portfolio/${encodeURIComponent(username)}/`);
  return data;
}
