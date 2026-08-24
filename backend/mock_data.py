"""Static mock data covering major flood-prone regions of India."""
from datetime import datetime, timezone, timedelta

REGIONS = [
    {"id": "assam-dhemaji", "name": "Dhemaji, Assam", "state": "Assam", "lat": 27.4830, "lng": 94.5820, "river": "Brahmaputra", "population": 686133},
    {"id": "bihar-darbhanga", "name": "Darbhanga, Bihar", "state": "Bihar", "lat": 26.1520, "lng": 85.8970, "river": "Kosi", "population": 3937385},
    {"id": "kerala-alappuzha", "name": "Alappuzha, Kerala", "state": "Kerala", "lat": 9.4981, "lng": 76.3388, "river": "Pamba", "population": 2127789},
    {"id": "up-varanasi", "name": "Varanasi, Uttar Pradesh", "state": "UP", "lat": 25.3176, "lng": 82.9739, "river": "Ganga", "population": 3676841},
    {"id": "up-noida", "name": "Noida, Uttar Pradesh", "state": "UP", "lat": 28.5355, "lng": 77.3910, "river": "Yamuna", "population": 642381},
    {"id": "wb-kolkata", "name": "Kolkata, West Bengal", "state": "WB", "lat": 22.5726, "lng": 88.3639, "river": "Hooghly", "population": 14850000},
    {"id": "odisha-puri", "name": "Puri, Odisha", "state": "Odisha", "lat": 19.8135, "lng": 85.8312, "river": "Mahanadi", "population": 1697983},
    {"id": "uttarakhand-haridwar", "name": "Haridwar, Uttarakhand", "state": "Uttarakhand", "lat": 29.9457, "lng": 78.1642, "river": "Ganga", "population": 1890422},
    {"id": "mumbai", "name": "Mumbai, Maharashtra", "state": "Maharashtra", "lat": 19.0760, "lng": 72.8777, "river": "Mithi", "population": 20411000},
    {"id": "chennai", "name": "Chennai, Tamil Nadu", "state": "TN", "lat": 13.0827, "lng": 80.2707, "river": "Adyar", "population": 11324000},
]

VILLAGES = [
    {"id": "v1", "name": "Majuli Island", "district": "Jorhat", "lat": 26.9500, "lng": 94.1667, "status": "critical", "flood_depth": 2.1, "population": 167304, "trapped": 245},
    {"id": "v2", "name": "Bahadurpur", "district": "Darbhanga", "lat": 26.1670, "lng": 85.9020, "status": "warning", "flood_depth": 1.4, "population": 12400, "trapped": 87},
    {"id": "v3", "name": "Kuttanad", "district": "Alappuzha", "lat": 9.5350, "lng": 76.4000, "status": "warning", "flood_depth": 1.1, "population": 45000, "trapped": 34},
    {"id": "v4", "name": "Sector 62", "district": "Noida", "lat": 28.6270, "lng": 77.3720, "status": "watch", "flood_depth": 0.4, "population": 82000, "trapped": 0},
    {"id": "v5", "name": "Rishikesh Ghat", "district": "Haridwar", "lat": 30.0869, "lng": 78.2676, "status": "warning", "flood_depth": 1.7, "population": 18200, "trapped": 12},
    {"id": "v6", "name": "Sundarbans - Gosaba", "district": "S 24 Parganas", "lat": 22.1667, "lng": 88.8000, "status": "critical", "flood_depth": 2.4, "population": 34500, "trapped": 156},
    {"id": "v7", "name": "Puri Coastal Belt", "district": "Puri", "lat": 19.7900, "lng": 85.8300, "status": "safe", "flood_depth": 0.0, "population": 22000, "trapped": 0},
    {"id": "v8", "name": "Mithi Riverside", "district": "Mumbai Suburban", "lat": 19.0680, "lng": 72.8940, "status": "watch", "flood_depth": 0.6, "population": 68000, "trapped": 0},
]

SHELTERS = [
    {"id": "s1", "name": "Dhemaji Community Hall", "lat": 27.4820, "lng": 94.5800, "capacity": 800, "occupied": 612, "food": True, "medical": True, "electricity": True},
    {"id": "s2", "name": "Darbhanga District School", "lat": 26.1500, "lng": 85.8950, "capacity": 1200, "occupied": 940, "food": True, "medical": True, "electricity": True},
    {"id": "s3", "name": "Alappuzha Panchayat Bhavan", "lat": 9.5020, "lng": 76.3450, "capacity": 500, "occupied": 210, "food": True, "medical": False, "electricity": True},
    {"id": "s4", "name": "Noida Stadium Relief Camp", "lat": 28.5400, "lng": 77.3900, "capacity": 2000, "occupied": 340, "food": True, "medical": True, "electricity": True},
    {"id": "s5", "name": "Haridwar Ashram Complex", "lat": 29.9500, "lng": 78.1700, "capacity": 1500, "occupied": 780, "food": True, "medical": True, "electricity": True},
    {"id": "s6", "name": "Gosaba Cyclone Shelter", "lat": 22.1700, "lng": 88.8050, "capacity": 600, "occupied": 588, "food": True, "medical": True, "electricity": False},
    {"id": "s7", "name": "Puri Beach Rescue Post", "lat": 19.8000, "lng": 85.8250, "capacity": 400, "occupied": 45, "food": True, "medical": False, "electricity": True},
]

ROAD_CLOSURES = [
    {"id": "r1", "name": "NH-27 Assam", "lat": 27.4500, "lng": 94.5500, "reason": "Submerged 1.2m", "since": "6h"},
    {"id": "r2", "name": "SH-56 Darbhanga", "lat": 26.1600, "lng": 85.9100, "reason": "Bridge damaged", "since": "12h"},
    {"id": "r3", "name": "Kuttanad Link Road", "lat": 9.5400, "lng": 76.3900, "reason": "Waterlogged", "since": "3h"},
    {"id": "r4", "name": "NH-24 Bypass Noida", "lat": 28.6100, "lng": 77.3600, "reason": "Rising water", "since": "1h"},
    {"id": "r5", "name": "Sundarban Ferry Road", "lat": 22.1500, "lng": 88.7900, "reason": "Broken embankment", "since": "18h"},
]

RESERVOIRS = [
    {"id": "res1", "name": "Bhakra Dam", "state": "Punjab", "level_pct": 78, "capacity_bcm": 9.62, "outflow": "Moderate", "status": "watch"},
    {"id": "res2", "name": "Hirakud Reservoir", "state": "Odisha", "level_pct": 92, "capacity_bcm": 5.90, "outflow": "High", "status": "warning"},
    {"id": "res3", "name": "Krishna Raja Sagara", "state": "Karnataka", "level_pct": 65, "capacity_bcm": 1.40, "outflow": "Low", "status": "safe"},
    {"id": "res4", "name": "Tehri Dam", "state": "Uttarakhand", "level_pct": 88, "capacity_bcm": 4.00, "outflow": "High", "status": "warning"},
    {"id": "res5", "name": "Sardar Sarovar", "state": "Gujarat", "level_pct": 71, "capacity_bcm": 9.50, "outflow": "Moderate", "status": "watch"},
    {"id": "res6", "name": "Farakka Barrage", "state": "West Bengal", "level_pct": 96, "capacity_bcm": 3.20, "outflow": "Critical", "status": "critical"},
]

RESOURCES = {
    "boats": {"total": 50, "deployed": 38, "available": 12},
    "ambulances": {"total": 12, "deployed": 9, "available": 3},
    "food_kits": {"total": 3000, "deployed": 2140, "available": 860},
    "blankets": {"total": 5000, "deployed": 3200, "available": 1800},
    "medical_teams": {"total": 8, "deployed": 6, "available": 2},
    "helicopters": {"total": 4, "deployed": 2, "available": 2},
    "drones": {"total": 15, "deployed": 11, "available": 4},
}

ALLOCATIONS = [
    {"village": "Majuli Island", "boats": 6, "ambulances": 1, "food_kits": 300, "medical_teams": 1, "priority": "critical"},
    {"village": "Bahadurpur", "boats": 3, "ambulances": 1, "food_kits": 180, "medical_teams": 0, "priority": "warning"},
    {"village": "Kuttanad", "boats": 4, "ambulances": 0, "food_kits": 220, "medical_teams": 1, "priority": "warning"},
    {"village": "Gosaba", "boats": 5, "ambulances": 1, "food_kits": 260, "medical_teams": 1, "priority": "critical"},
    {"village": "Rishikesh Ghat", "boats": 2, "ambulances": 0, "food_kits": 120, "medical_teams": 0, "priority": "warning"},
    {"village": "Mithi Riverside", "boats": 1, "ambulances": 0, "food_kits": 90, "medical_teams": 0, "priority": "watch"},
]

INCIDENTS = [
    {"id": "i1", "type": "Trapped family", "location": "Majuli Island", "priority": "critical", "reporter": "Village Head", "eta_min": 22, "status": "assigned", "details": "5 members on rooftop, 2 children"},
    {"id": "i2", "type": "Pregnant woman", "location": "Bahadurpur", "priority": "critical", "reporter": "ASHA worker", "eta_min": 14, "status": "in-progress", "details": "Labour expected in 4 hours"},
    {"id": "i3", "type": "Elderly stranded", "location": "Kuttanad", "priority": "high", "reporter": "Neighbour", "eta_min": 35, "status": "assigned", "details": "Diabetic, no medication"},
    {"id": "i4", "type": "Food shortage", "location": "Gosaba", "priority": "medium", "reporter": "Sarpanch", "eta_min": 90, "status": "queued", "details": "40 families, 3 days without rations"},
    {"id": "i5", "type": "Bridge collapse", "location": "SH-56 Darbhanga", "priority": "high", "reporter": "PWD", "eta_min": 0, "status": "reported", "details": "Cuts off 4 villages"},
    {"id": "i6", "type": "Boat needed", "location": "Sundarbans - Ferry Point", "priority": "high", "reporter": "Local NGO", "eta_min": 48, "status": "assigned", "details": "12 people to evacuate"},
    {"id": "i7", "type": "Road damage report", "location": "Noida Sector 62", "priority": "low", "reporter": "Citizen", "eta_min": 240, "status": "queued", "details": "Sinkhole forming"},
]

VOLUNTEERS = [
    {"id": "vol1", "name": "Dr. Anjali Sharma", "skill": "Doctor", "location": "Darbhanga", "lat": 26.1520, "lng": 85.8970, "available": True, "assigned_to": None},
    {"id": "vol2", "name": "Ravi Baruah", "skill": "Boat Operator", "location": "Dhemaji", "lat": 27.4830, "lng": 94.5820, "available": True, "assigned_to": "Majuli Island"},
    {"id": "vol3", "name": "Sister Mary Thomas", "skill": "Nurse", "location": "Alappuzha", "lat": 9.4981, "lng": 76.3388, "available": True, "assigned_to": None},
    {"id": "vol4", "name": "Vikram Singh", "skill": "Cook", "location": "Haridwar", "lat": 29.9457, "lng": 78.1642, "available": True, "assigned_to": None},
    {"id": "vol5", "name": "Meera Das", "skill": "Driver", "location": "Kolkata", "lat": 22.5726, "lng": 88.3639, "available": False, "assigned_to": "Gosaba"},
    {"id": "vol6", "name": "Dr. Prakash Rao", "skill": "Doctor", "location": "Chennai", "lat": 13.0827, "lng": 80.2707, "available": True, "assigned_to": None},
]

SOCIAL_POSTS = [
    {"id": "sp1", "source": "Twitter/X", "handle": "@rescue_assam", "text": "Boat urgently needed near Majuli north bank. 6 people including infants stranded.", "location": "Majuli Island", "priority": "critical", "verified": True, "time": "8 min ago"},
    {"id": "sp2", "source": "Twitter/X", "handle": "@localnews_dbg", "text": "SH-56 bridge partially collapsed. Traffic diverted via link road.", "location": "Darbhanga", "priority": "high", "verified": True, "time": "22 min ago"},
    {"id": "sp3", "source": "Facebook", "handle": "Kuttanad Help Group", "text": "Volunteers with food supplies pls contact 9847XXXXXX", "location": "Kuttanad", "priority": "medium", "verified": True, "time": "45 min ago"},
    {"id": "sp4", "source": "Twitter/X", "handle": "@viral_fake", "text": "Dam broken in Tehri! Everyone evacuate NOW!", "location": "Tehri", "priority": "high", "verified": False, "time": "1 hr ago"},
    {"id": "sp5", "source": "News RSS", "handle": "PTI", "text": "NDRF deploys 4 additional teams to Assam floods.", "location": "Assam", "priority": "info", "verified": True, "time": "1 hr ago"},
    {"id": "sp6", "source": "Twitter/X", "handle": "@drone_footage", "text": "Aerial view shows water level rising in Sundarbans. Embankment weak.", "location": "Sundarbans", "priority": "high", "verified": True, "time": "2 hr ago"},
]

WEATHER = [
    {"region": "Assam", "rainfall_mm": 187, "forecast": "Very Heavy", "wind_kmph": 42, "humidity": 94},
    {"region": "Bihar", "rainfall_mm": 142, "forecast": "Heavy", "wind_kmph": 28, "humidity": 88},
    {"region": "Kerala", "rainfall_mm": 156, "forecast": "Very Heavy", "wind_kmph": 35, "humidity": 92},
    {"region": "Uttarakhand", "rainfall_mm": 98, "forecast": "Heavy", "wind_kmph": 22, "humidity": 78},
    {"region": "West Bengal", "rainfall_mm": 174, "forecast": "Extremely Heavy", "wind_kmph": 48, "humidity": 95},
    {"region": "Maharashtra", "rainfall_mm": 62, "forecast": "Moderate", "wind_kmph": 18, "humidity": 82},
]

PREDICTIONS = {
    "assam-dhemaji": {"probability": 92, "expected_depth_m": 2.1, "time_remaining_hr": 18, "population_at_risk": 34200, "affected_villages": 12},
    "bihar-darbhanga": {"probability": 78, "expected_depth_m": 1.4, "time_remaining_hr": 30, "population_at_risk": 21800, "affected_villages": 8},
    "kerala-alappuzha": {"probability": 71, "expected_depth_m": 1.1, "time_remaining_hr": 24, "population_at_risk": 18500, "affected_villages": 6},
    "up-varanasi": {"probability": 44, "expected_depth_m": 0.6, "time_remaining_hr": 48, "population_at_risk": 9200, "affected_villages": 3},
    "up-noida": {"probability": 38, "expected_depth_m": 0.4, "time_remaining_hr": 60, "population_at_risk": 6400, "affected_villages": 2},
    "wb-kolkata": {"probability": 84, "expected_depth_m": 1.8, "time_remaining_hr": 12, "population_at_risk": 41200, "affected_villages": 15},
    "odisha-puri": {"probability": 22, "expected_depth_m": 0.0, "time_remaining_hr": 96, "population_at_risk": 0, "affected_villages": 0},
    "uttarakhand-haridwar": {"probability": 66, "expected_depth_m": 1.7, "time_remaining_hr": 20, "population_at_risk": 15400, "affected_villages": 5},
    "mumbai": {"probability": 51, "expected_depth_m": 0.6, "time_remaining_hr": 36, "population_at_risk": 12300, "affected_villages": 4},
    "chennai": {"probability": 29, "expected_depth_m": 0.2, "time_remaining_hr": 72, "population_at_risk": 3200, "affected_villages": 1},
}

XAI_FACTORS = {
    "assam-dhemaji": [
        {"factor": "Rainfall increased 160% vs monthly avg", "impact": 0.32},
        {"factor": "Brahmaputra discharge rising rapidly", "impact": 0.28},
        {"factor": "Kurichhu Dam release expected", "impact": 0.18},
        {"factor": "Soil moisture 96% (saturated)", "impact": 0.12},
        {"factor": "Pattern matches 2013 flood signature", "impact": 0.10},
    ],
    "default": [
        {"factor": "Rainfall above seasonal normal", "impact": 0.30},
        {"factor": "River level trending upward", "impact": 0.25},
        {"factor": "Reservoir capacity near threshold", "impact": 0.20},
        {"factor": "Terrain elevation & drainage", "impact": 0.15},
        {"factor": "Historical flood pattern match", "impact": 0.10},
    ],
}

ALERTS = [
    {"level": "critical", "text": "CRITICAL: Farakka Barrage water level at 96%. Downstream evacuation advised."},
    {"level": "warning", "text": "WARNING: Brahmaputra crossing danger mark near Dhemaji. NDRF deployed."},
    {"level": "warning", "text": "WARNING: Tehri Dam release scheduled at 18:00 IST. Ganga levels expected to rise."},
    {"level": "info", "text": "INFO: 4 additional NDRF battalions mobilised across Bihar & Assam."},
    {"level": "info", "text": "INFO: Helpline 1078 (NDMA) — Free 24x7. SMS 'FLOOD' to 51969 for local alerts."},
]

MEDICAL_OUTBREAK = [
    {"disease": "Diarrhea / Cholera", "risk_pct": 78, "reason": "Contaminated water sources near displacement camps", "regions": ["Assam", "Bihar"]},
    {"disease": "Dengue", "risk_pct": 64, "reason": "Stagnant water; increased Aedes breeding", "regions": ["Kerala", "West Bengal"]},
    {"disease": "Malaria", "risk_pct": 55, "reason": "Standing pools of water; mosquito density up 3x", "regions": ["Odisha", "Assam"]},
    {"disease": "Leptospirosis", "risk_pct": 48, "reason": "Rodent contact in flood water; rescue worker exposure", "regions": ["Mumbai", "Kerala"]},
    {"disease": "Skin Infections", "risk_pct": 82, "reason": "Prolonged wet clothing / limited sanitation", "regions": ["All flood zones"]},
]

ECONOMIC_LOSS = {
    "crop_damage_cr": 42.6,
    "road_damage_cr": 18.4,
    "house_damage_cr": 86.2,
    "livestock_loss_cr": 12.1,
    "commercial_loss_cr": 27.8,
    "total_cr": 187.1,
}

PREPAREDNESS = {
    "before": [
        "Keep an emergency kit: torch, batteries, first-aid, water (3L/person/day), non-perishable food for 72 hours",
        "Store important documents in waterproof pouch",
        "Save emergency numbers: NDMA 1078, Police 100, Ambulance 108, Disha 181",
        "Identify the nearest cyclone/flood shelter",
        "Charge phones and power banks",
    ],
    "during": [
        "Move to higher ground immediately; do not walk through moving water",
        "Turn off electricity at the main switch",
        "Avoid using elevators",
        "Drink only boiled or bottled water",
        "Listen to All India Radio / DD News for official updates",
    ],
    "after": [
        "Return home only after authorities declare it safe",
        "Wear rubber boots, avoid contact with flood water",
        "Discard perishable food that has been in flood water",
        "Report damage to your Panchayat / Municipal office",
        "Get vaccinated for water-borne diseases",
    ],
}

EMERGENCY_CONTACTS = [
    {"name": "NDMA Helpline", "number": "1078", "category": "National"},
    {"name": "NDRF Control Room", "number": "011-24363260", "category": "National"},
    {"name": "Ambulance", "number": "108", "category": "Medical"},
    {"name": "Police", "number": "100", "category": "Police"},
    {"name": "Fire", "number": "101", "category": "Fire"},
    {"name": "Women Helpline", "number": "181", "category": "Support"},
    {"name": "Child Helpline", "number": "1098", "category": "Support"},
    {"name": "Disaster Management Assam", "number": "1079", "category": "State"},
    {"name": "Disaster Management Bihar", "number": "0612-2217305", "category": "State"},
    {"name": "Disaster Management Kerala", "number": "1077", "category": "State"},
]

DRONES = [
    {"id": "d1", "name": "Dhemaji-A", "battery": 72, "altitude_m": 120, "status": "surveying", "region": "Majuli Island", "feed": "live"},
    {"id": "d2", "name": "Darbhanga-B", "battery": 41, "altitude_m": 90, "status": "surveying", "region": "Bahadurpur", "feed": "live"},
    {"id": "d3", "name": "Kuttanad-C", "battery": 88, "altitude_m": 150, "status": "idle", "region": "Alappuzha", "feed": "standby"},
    {"id": "d4", "name": "Gosaba-D", "battery": 33, "altitude_m": 70, "status": "returning", "region": "Sundarbans", "feed": "recording"},
]

FAMILY_REGISTRY = [
    {"id": "f1", "name": "Ravi Kumar", "age": 34, "last_seen": "Majuli Island", "status": "safe", "shelter": "Dhemaji Community Hall", "contact": "9876XXXXXX"},
    {"id": "f2", "name": "Sunita Devi", "age": 58, "last_seen": "Bahadurpur", "status": "missing", "shelter": None, "contact": None},
    {"id": "f3", "name": "Aarav Sharma", "age": 8, "last_seen": "Rishikesh Ghat", "status": "found", "shelter": "Haridwar Ashram Complex", "contact": "9812XXXXXX"},
    {"id": "f4", "name": "Meena Iyer", "age": 42, "last_seen": "Kuttanad", "status": "safe", "shelter": "Alappuzha Panchayat Bhavan", "contact": "9847XXXXXX"},
]

OVERVIEW_STATS = {
    "people_evacuated": 42817,
    "shelters_active": 128,
    "rescue_teams_deployed": 47,
    "villages_affected": 213,
    "boats_operational": 38,
    "helicopters_operational": 2,
    "predictions_generated": 1284,
    "alerts_broadcast": 342,
}
