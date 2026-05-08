import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

const USER_KEY = "ai_app_builder_user_id";

export function getUserId() {
  let id = localStorage.getItem(USER_KEY);
  if (!id) {
    id = "user_" + Math.random().toString(36).slice(2, 12) + Date.now().toString(36);
    localStorage.setItem(USER_KEY, id);
  }
  return id;
}

const apiClient = axios.create({
  baseURL: API,
});

apiClient.interceptors.request.use((config) => {
  config.headers["X-User-Id"] = getUserId();
  return config;
});

export default apiClient;
