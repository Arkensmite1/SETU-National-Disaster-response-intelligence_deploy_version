import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API, timeout: 60000 });

export const endpoints = {
  overview: "/overview/stats",
  ticker: "/alerts/ticker",
  regions: "/regions",
  map: "/monitoring/map-data",
  prediction: (id) => `/prediction/${id}`,
  predictionsAll: "/predictions/all",
  explain: "/prediction/explain",
  resources: "/resources",
  optimize: "/resources/optimize",
  shelterRecommend: "/shelter/recommend",
  damage: "/damage/estimate",
  waterDepth: "/water-depth/estimate",
  classify: "/image/classify",
  fakeNews: "/fakenews/check",
  chatMessage: "/chat/message",
  chatStream: "/chat/stream",
  incidents: "/incidents",
  sosCreate: "/incidents/sos",
  sosList: "/incidents/sos",
  volunteers: "/volunteers",
  social: "/social/monitor",
  weather: "/weather",
  simulation: "/simulation/flood",
  rescueRoute: "/rescue/route",
  medical: "/medical/outbreak",
  economic: "/economic-loss",
  prepare: "/preparedness",
  contacts: "/emergency-contacts",
  drones: "/drones",
  familyRegistry: "/family-registry",
  warning: "/warning/generate",
};
