import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;
export const TOKEN_KEY = "setu.token";

export const setuApi = axios.create({ baseURL: API, timeout: 60000 });

setuApi.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let onUnauthorized = null;
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

setuApi.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response?.status === 401 && onUnauthorized) onUnauthorized();
    return Promise.reject(error);
  }
);

export const setuEndpoints = {
  otpRequest: "/auth/otp/request",
  otpVerify: "/auth/otp/verify",
  login: "/auth/login",
  me: "/auth/me",
  profile: "/auth/profile",
  myLocation: "/auth/location",
  events: "/events",
  checkLocation: "/events/check-location",
  myAlerts: "/events/alerts/for-me",
  eventTransition: (id) => `/events/${id}/transition`,
  stateMachines: "/state-machines",
  sos: "/sos",
  sosSync: "/sos/sync",
  mySos: "/sos/mine",
  sosQueue: "/sos/queue",
  assignedToMe: "/sos/assigned-to-me",
  sosOne: (id) => `/sos/${id}`,
  sosTimeline: (id) => `/sos/${id}/timeline`,
  sosCancel: (id) => `/sos/${id}/cancel`,
  sosLocation: (id) => `/sos/${id}/location`,
  sosAssign: (id) => `/sos/${id}/assign`,
  sosAccept: (id) => `/sos/${id}/accept`,
  sosReject: (id) => `/sos/${id}/reject`,
  sosStatus: (id) => `/sos/${id}/status`,
  sosComplete: (id) => `/sos/${id}/complete`,
  timeoutScan: "/sos/timeout-scan",
  rescueDashboard: "/rescue/dashboard",
  rescueTeams: "/rescue/teams",
  teamLocation: (id) => `/rescue/teams/${id}/location`,
  recommendations: (id) => `/rescue/recommendations/${id}`,
  clusters: "/rescue/clusters",
  aiSummary: "/rescue/ai-summary",
  blockedRoad: "/rescue/blocked-road",
  blockedRoads: "/rescue/blocked-roads",
};

export const apiError = (e, fallback = "Something went wrong") =>
  e?.response?.data?.detail || e?.message || fallback;
