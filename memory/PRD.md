# SETU — National Disaster Response Intelligence Platform

## Original Problem Statement
PS3: Disaster Response Intelligence Platform for flood prediction, emergency
planning, and resource allocation. Hackathon (Smart India Hackathon) demo.
Must feel like a modern MyGov / Digital India / PM Gati Shakti / India Stack
portal — trust, transparency, authority, accessibility, professionalism,
national development. Avoid startup/flashy design. Include all features from
the provided Core Features document (20 AI features + non-AI features).

## User Choices
- Build ALL features with realistic mock data + 4-5 fully AI-integrated flagship features
- Claude Sonnet 4.5 via Emergent Universal LLM key
- Leaflet + OpenStreetMap (free)
- No authentication (public demo)
- Pan-India (region selectable)

## Personas
- Citizens (SOS, shelter finder, family check-in, chatbot)
- Volunteers / NGOs (registration, matching, roster)
- District officials / NDRF (dashboard, incidents, allocation, warnings)

## Architecture
- Backend: FastAPI on 8001 (routes prefixed /api), MongoDB via motor, Claude Sonnet 4.5 via emergentintegrations
- Frontend: React 19 + Tailwind + shadcn/ui, Leaflet, recharts, sonner, react-router v7
- AI features stream SSE; vision endpoints accept base64 JPEG/PNG/WEBP
- Government-style visual system: National Blue #0A2B4E, Saffron #FF9933, India Green #138808, structured Bento layout, no glassmorphism

## What's Implemented (Feb 2026)
- Government-styled shell with tricolour strip, meta bar, brand, main nav, mobile menu, live alert ticker, footer with helplines
- Home page with hero, feature grid, stat band, trust band
- Command Dashboard: 8 stat cards + live map + priority incidents + top-risk predictions + quick-access grid
- Live Flood Map (Leaflet + OSM) with layers for villages, shelters, road closures + reservoir side-panel
- AI Flood Prediction with Explainable-AI factor bars + AI-generated explanation + bilingual SMS warning generation
- AI Resource Allocation with inventory cards + village-level allocation table + AI optimiser
- AI Shelter Recommendation (haversine-ranked + score based on capacity/medical/distance)
- AI Rescue Route Planner with polyline visualisation + boat/vehicle mode + waypoints + AI avoided list
- AI Damage Estimation + Water Depth + Image Classifier (all vision endpoints)
- AI Rumor / Fake News detection
- AI Flood Simulation with rainfall slider + Digital Twin district map
- Incident Prioritisation queue + live citizen SOS
- Volunteer registration + AI matching roster
- Social Media Monitoring feed with verified/unverified badges
- Post-flood Medical Outbreak Prediction (dengue/cholera/malaria/lepto/skin)
- Economic Loss dashboard with Recharts
- Preparedness Learning Centre + Emergency Contact directory (with tel: links)
- SOS button flow with GPS + ticket confirmation
- Drone Ops Centre with mock live feeds
- AI Emergency Chatbot (streaming SSE) with voice input (browser SpeechRecognition), quick-suggestion chips, multilingual

## Backend Endpoints
All under /api: /overview/stats, /alerts/ticker, /regions, /monitoring/map-data,
/prediction/{id}, /predictions/all, /prediction/explain (AI), /resources,
/resources/optimize (AI), /shelter/recommend, /rescue/route, /simulation/flood,
/warning/generate (AI), /incidents, /incidents/sos [GET,POST], /volunteers [GET,POST],
/social/monitor, /weather, /medical/outbreak, /economic-loss, /preparedness,
/emergency-contacts, /drones, /family-registry [GET,POST], /damage/estimate (AI vision),
/water-depth/estimate (AI vision), /image/classify (AI vision), /fakenews/check (AI),
/chat/stream (SSE), /chat/message (fallback)

## Testing
- Backend: 31/31 tests passed (pytest suite at /app/backend/tests/backend_test.py)
- Frontend: All 17 routes render without errors

## Prioritised Backlog
- P1: Offline mode / PWA install prompt + service worker for offline caching
- P1: QR-based relief distribution verification flow
- P2: Auth roles (citizen / volunteer / officer) if needed for production
- P2: Real integrations — IMD API, CWC river gauges, NDMA alerts feed
- P2: Recharts /economic init-width warning (cosmetic)
- P3: Missing-person registry search + photo upload
- P3: WhatsApp Business API broadcast integration
