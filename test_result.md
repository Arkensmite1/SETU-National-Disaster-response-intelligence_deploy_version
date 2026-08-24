#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================
user_problem_statement: |
  Implement the SETU_Complete_System_Specification.pdf + SETU_Emergent_Implementation_Prompt.md
  against the existing SETU demo codebase. This run covers PHASES 1-4 (of 13):
  Phase 1 data model + Section 23 state machines + audit log + seed,
  Phase 2 actors/auth/RBAC + role-scoped portals,
  Phase 3 SOS system end-to-end (Section 11),
  Phase 4 rescue coordination (Section 12).
  User decisions: OTP is MOCKED (no SMS provider), Claude Sonnet 4.5 via Emergent LLM key for
  ADVISORY-only AI, existing 20 AI pages kept and reframed as advisory, demo accounts seeded
  but not displayed on the login screen.

backend:
  - task: "Phase 1: Section 22 data model + Section 23 state machines + audit log + seed"
    implemented: true
    working: "NA"
    file: "backend/setu/models.py, backend/setu/state_machines.py, backend/setu/audit.py, backend/setu/seed.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "New Mongo collections (disaster_events, sos_records, teams, shelters, resource_requests, audit_log, users). Location always {latitude,longitude,accuracy,timestamp,source}. Shelter available derived on read. ResourceRequest keeps requested/approved/allocated/sent/received separate. 5 explicit state machines with illegal-transition rejection (409). Every write goes through the audit helper. Idempotent seed runs on startup. GET /api/state-machines exposes the machines. 10 pytest unit tests pass (backend/tests/test_setu_state_machines.py)."
  - task: "Phase 2: auth (mocked mobile OTP + staff email/password) and RBAC"
    implemented: true
    working: "NA"
    file: "backend/setu/auth.py, backend/setu/routers/auth_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "JWT + bcrypt. POST /api/auth/otp/request (returns devOtp, MOCKED delivery), /api/auth/otp/verify (citizen register/login with Section 8.2 onboarding fields), /api/auth/login (staff), GET /api/auth/me, PATCH /api/auth/profile, POST /api/auth/location, POST /api/auth/staff (admin only), GET /api/auth/roles. require_roles() enforces Section 21.1 visibility server-side."
  - task: "Phase 3: SOS system end to end (Section 11)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/sos_routes.py, backend/setu/priority.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/sos (CREATED->RECEIVED->VERIFIED->PENDING, server-side P1/P2/P3 triage, auto event match by polygon, duplicate merge with retryCount, never claims a team was notified), /api/sos/sync (offline queue with clientCreatedAt + uploadedAt), /api/sos/mine, /api/sos/queue (leader), /api/sos/assigned-to-me (member), /api/sos/{id}, /{id}/timeline, /{id}/cancel (CANCELLED_BY_USER, audit retained), PATCH /{id}/location (origin vs lastKnown), /{id}/assign (atomic team claim), /timeout-scan, /{id}/accept, /{id}/reject (5 reasons -> back to PENDING), /{id}/status (team-settable states only), /{id}/complete (structured report, stops live location sharing)."
  - task: "Phase 4: rescue coordination (Section 12)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/rescue_routes.py, backend/setu/advisory.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/rescue/dashboard (P1/P2/P3, assigned/unassigned, team availability, map markers), /api/rescue/teams (+create, location, status), /api/rescue/recommendations/{sosId} (ranked, advisory, autoApplied false), /api/rescue/clusters (2km greedy clustering, optional AI advisory), /api/rescue/ai-summary (Claude advisory with deterministic fallback), /api/rescue/blocked-road + /blocked-roads."
  - task: "DisasterEvent routes: tiers, affected-area matching, role-scoped alerts"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/event_routes.py, backend/setu/geo.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/events (+tier legend, staleness notices), GET /api/events/{id}, POST /api/events/{id}/transition (AUTHORITY only, children never cascade-closed), POST /api/events/check-location (Affected/Near-boundary/Outside, never says 'safe'), GET /api/events/alerts/for-me (different content per role)."

  - task: "Phase 5: Search & verification (Section 13)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/search_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "SOS status USER_NOT_FOUND/SEARCHING auto-opens a grid search operation. POST /api/search/operations, GET /api/search/operations(+/{id}), POST /{id}/cells/{cellId} (NOT_SEARCHED/NOTHING_FOUND/PEOPLE_FOUND/SIGNS_FOUND/INACCESSIBLE with coverage %), POST /{id}/close (FOUND/NOT_FOUND/SUSPENDED -> opens missing-person register entry, never 'safe'), GET/POST /api/search/missing-register(+/{id}/resolve, leader only), POST/GET /api/search/incidents (people found with no SOS), GET /api/search/summary."
  - task: "Phase 6: Shelter management (Section 14)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/shelter_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/shelters/list (derived available + staleness + distance), GET /{id} (+alternatives when full), POST /{id}/arrivals (atomic capacity-guarded increment: last slot cannot be double allocated; 409 with alternatives when full; allowOverflow for explicit over-capacity), /{id}/departures, expectedOccupancy optimistic concurrency -> 409 + conflict recorded (never overwritten), POST /{id}/sync-offline (original timestamps), POST /{id}/status (CLOSED requires reason, returns alternatives), POST /{id}/requirements + GET, POST /{id}/transfer (atomic both sides), PATCH /{id}."
  - task: "Phase 7: NGO & relief management (Section 15)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/relief_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/relief/requirements (demand vs committedByOthers, duplicate-commitment warning), /requests(+/{id}), approve (AUTHORITY, partial approval keeps requested figure), reject, commit (NGO, over-commit needs acknowledgeDuplicate), dispatch (sent stored separately), in-transit, delay (reason + new ETA + notifies shelter), deliver, receive (SHELTER_ADMIN; sent != received -> DISCREPANCY + conflict), resolve-discrepancy (AUTHORITY only), distribute, inventory GET/POST with committed vs uncommitted, GET /pipeline."
  - task: "Phase 8: Data integrity & conflicts (Section 16)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/integrity_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST/GET /api/integrity/field-reports (contradictory values kept side by side with reporter, role, confidence, time), GET /api/integrity/conflicts (report conflicts + shelter occupancy conflicts + resource discrepancies), POST /conflicts/{id}/resolve (AUTHORITY only, discarded values retained, optional applyToRecord), GET /api/integrity/data-quality (stale records, teams without location, approximate-location SOS, explicit known-unknowns)."
  - task: "Phase 9: Ingestion pipeline + notification system (Sections 6, 9, 10)"
    implemented: true
    working: "NA"
    file: "backend/setu/ingestion.py, backend/setu/routers/ingestion_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "POST /api/ingestion/poll (create/update-with-version-history/contradiction-held-as-conflict/illegal-jump-rejected; empty poll reported as a data gap), GET /api/ingestion/status (source health + silence warning), POST /api/ingestion/simulate (DEMO feed: NEW_EVENT, UPDATE_SEVERITY, CONTRADICTORY_UPDATE, ILLEGAL_JUMP, SOURCE_SILENCE). Notifications: POST /api/notifications/dispatch (priority 1/2/3, role-specific content, optional location scoping), GET /notifications/mine (P1 first, marks delivered), POST /{id}/ack (own only), GET /notifications/monitor, POST /notifications/escalate-scan (unacknowledged P1 escalates to authority)."
  - task: "Phase 10: Authority controls & reporting (Section 17)"
    implemented: true
    working: "NA"
    file: "backend/setu/routers/authority_routes.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "GET /api/authority/situation-report (rescue + search + shelter + relief rollup and an explicit dataGaps list; persisted), GET /situation-reports, POST /reallocate (cannot exceed unshipped allocation; creates new audited allocation + notifies shelter), GET /cross-district (regional rollup + advisory mutual-aid suggestions), POST /escalate (DISTRICT/STATE/NATIONAL), GET /decision-log (human decisions only). All AUTHORITY/SUPER_ADMIN gated."
frontend:
  - task: "Phase 2-4 frontend: login, role portals, citizen SOS, rescue dashboards"
    implemented: false
    working: "NA"
    file: "frontend/src"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "Implemented: AuthContext + ProtectedRoute + role-scoped AppShell nav, Login (citizen mocked OTP + staff password), CitizenHome (area check, my SOS with state tracker, offline queue banner), CitizenSOS (location fallback chain, offline queue, 30s cancel), LeaderDashboard (queue, ranked recommendations, assign/override, clusters, AI advisory, timeout scan, blocked roads), MemberDashboard (accept/reject, status progression, completion report), AdminPortal (event lifecycle, audit feed, false-alarm review)."
  - task: "Phase 5-10 frontend portals"
    implemented: true
    working: "NA"
    file: "frontend/src/pages"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
        -working: "NA"
        -agent: "main"
        -comment: "New pages: rescue/SearchOperations (grid search, missing register, field incidents), shelter/ShelterAdminPortal (occupancy with conflict + overflow handling, status, transfers, requirements, offline logs), ngo/NgoPortal (requirement board with committedByOthers, commit/dispatch/transit/delay/deliver, inventory, pipeline), admin/ConflictsPage, admin/IngestionConsole, admin/SituationReport, Notifications (all roles), citizen/ShelterFinder. Routes + role navigation updated."

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 1
  run_ui: false

test_plan:
  current_focus:
    - "Phase 1: Section 22 data model + Section 23 state machines + audit log + seed"
    - "Phase 2: auth (mocked mobile OTP + staff email/password) and RBAC"
    - "Phase 3: SOS system end to end (Section 11)"
    - "Phase 4: rescue coordination (Section 12)"
    - "DisasterEvent routes: tiers, affected-area matching, role-scoped alerts"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
    -agent: "main"
    -message: "Phases 1-4 backend implemented. Credentials in memory/test_credentials.md (staff password Setu@1234; citizens 9000000001/9000000002 via mocked OTP where POST /api/auth/otp/request returns devOtp). Please verify: (1) illegal state transitions return 409 for all 5 machines, (2) RBAC - citizen blocked from /api/sos/queue and cross-citizen SOS access, unauthenticated 401, leader blocked from event transition, (3) SOS create reaches PENDING with correct P1/P2/P3 and auto-matches NDEM-EVENT-2026-00011 for lat 27.48 lng 94.58, (4) duplicate SOS merges into the existing case and increments retryCount instead of creating a new one, (5) atomic team claim - assigning an already-ASSIGNED team returns 409, (6) full team lifecycle accept -> EN_ROUTE -> ARRIVED -> RESCUING -> RESCUED -> complete, with liveLocationSharing false after completion, (7) offline /api/sos/sync stores both clientCreatedAt and uploadedAt, (8) closing/transitioning an event does not change child SOS statuses, (9) audit timeline for an SOS is complete and reconstructable. Legacy endpoints (/api/overview/stats etc.) must still work."

    -agent: "main"
    -message: "Phases 5-10 backend implemented; my own smoke suite (/app/tests/smoke_phase5_10.py) passes 70/70 and phases 1-4 (/app/tests/smoke_phase1_4.py) pass 40/40. Please independently verify with curl: (1) SOS -> ARRIVED -> USER_NOT_FOUND auto-opens a search operation and the response never implies safety; closing a NOT_FOUND search creates a missing-register entry. (2) Shelter atomicity: SH-S3 is full so arrivals must 409 WITH alternatives; allowOverflow=true must succeed as OVER_CAPACITY; a stale expectedOccupancy must 409 and record a conflict instead of overwriting. (3) Relief: sent 1500 vs received 1350 must become DISCREPANCY (both figures kept) and only AUTHORITY can resolve it; NGO cannot approve; shelter admin cannot resolve. (4) Integrity: two different field reports for the same field create a conflict listing both values; only AUTHORITY resolves. (5) Ingestion: simulate NEW_EVENT then poll -> created; UPDATE_SEVERITY -> version++ and history retained; CONTRADICTORY_UPDATE and ILLEGAL_JUMP -> held as conflicts, NOT applied; empty poll wording must not imply all-clear; non-admin poll -> 403. (6) Notifications: dispatch P1 to several roles gives different text per role, ack only by the addressee, monitor separates delivered vs acknowledged. (7) Authority: situation-report dataGaps is non-empty, reallocate beyond unshipped allocation -> 409, decision-log is AUTHORITY-only. Credentials in memory/test_credentials.md (staff Setu@1234). Legacy endpoints and phases 1-4 must still work."