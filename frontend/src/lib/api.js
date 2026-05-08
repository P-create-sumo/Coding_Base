import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const LEGACY_USER_KEY = "ai_app_builder_user_id";

export function getLegacyUserId() {
  return localStorage.getItem(LEGACY_USER_KEY);
}

export function clearLegacyUserId() {
  localStorage.removeItem(LEGACY_USER_KEY);
}

const apiClient = axios.create({
  baseURL: API,
  withCredentials: true,
});

export default apiClient;
