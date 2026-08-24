import "@/App.css";
import React from "react";
import { BrowserRouter, Navigate, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import AppShell from "@/components/layout/AppShell";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import { AuthProvider } from "@/context/AuthContext";

import Home from "@/pages/Home";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import LiveMap from "@/pages/LiveMap";
import Prediction from "@/pages/Prediction";
import Resources from "@/pages/Resources";
import Shelters from "@/pages/Shelters";
import Rescue from "@/pages/Rescue";
import Damage from "@/pages/Damage";
import Simulation from "@/pages/Simulation";
import Incidents from "@/pages/Incidents";
import Volunteers from "@/pages/Volunteers";
import Social from "@/pages/Social";
import Medical from "@/pages/Medical";
import Economic from "@/pages/Economic";
import Preparedness from "@/pages/Preparedness";
import Chatbot from "@/pages/Chatbot";
import Drones from "@/pages/Drones";

import CitizenHome from "@/pages/citizen/CitizenHome";
import CitizenSOS from "@/pages/citizen/CitizenSOS";
import LeaderDashboard from "@/pages/rescue/LeaderDashboard";
import MemberDashboard from "@/pages/rescue/MemberDashboard";
import AdminPortal from "@/pages/admin/AdminPortal";
import ShelterAdminPortal from "@/pages/shelter/ShelterAdminPortal";
import NgoPortal from "@/pages/ngo/NgoPortal";
import SearchOperations from "@/pages/rescue/SearchOperations";
import ConflictsPage from "@/pages/admin/ConflictsPage";
import IngestionConsole from "@/pages/admin/IngestionConsole";
import SituationReport from "@/pages/admin/SituationReport";
import Notifications from "@/pages/Notifications";
import ShelterFinder from "@/pages/citizen/ShelterFinder";

const OPS = ["RESCUE_LEADER", "AUTHORITY", "SUPER_ADMIN"];
const ADMIN = ["AUTHORITY", "SUPER_ADMIN"];

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              {/* Public */}
              <Route path="/" element={<Home />} />
              <Route path="/login" element={<Login />} />
              <Route path="/preparedness" element={<Preparedness />} />
              <Route path="/chatbot" element={<Chatbot />} />
              <Route path="/shelters" element={<Shelters />} />

              {/* Citizen portal */}
              <Route path="/citizen" element={
                <ProtectedRoute roles={["USER"]}><CitizenHome /></ProtectedRoute>} />
              <Route path="/citizen/sos" element={
                <ProtectedRoute roles={["USER"]}><CitizenSOS /></ProtectedRoute>} />
              <Route path="/citizen/shelters" element={
                <ProtectedRoute roles={["USER"]}><ShelterFinder /></ProtectedRoute>} />
              <Route path="/sos" element={<Navigate to="/citizen/sos" replace />} />
              <Route path="/notifications" element={
                <ProtectedRoute><Notifications /></ProtectedRoute>} />

              {/* Rescue portals */}
              <Route path="/rescue/leader" element={
                <ProtectedRoute roles={OPS}><LeaderDashboard /></ProtectedRoute>} />
              <Route path="/rescue/member" element={
                <ProtectedRoute roles={["RESCUE_MEMBER", "RESCUE_LEADER", "AUTHORITY", "SUPER_ADMIN"]}>
                  <MemberDashboard />
                </ProtectedRoute>} />
              <Route path="/rescue/search" element={
                <ProtectedRoute roles={["RESCUE_MEMBER", "RESCUE_LEADER", "AUTHORITY", "SUPER_ADMIN"]}>
                  <SearchOperations />
                </ProtectedRoute>} />
              <Route path="/rescue" element={<Navigate to="/rescue/leader" replace />} />

              {/* Shelter admin portal (Phase 6) */}
              <Route path="/shelter-admin" element={
                <ProtectedRoute roles={["SHELTER_ADMIN", ...ADMIN]}><ShelterAdminPortal /></ProtectedRoute>} />

              {/* NGO portal (Phase 7) */}
              <Route path="/ngo" element={
                <ProtectedRoute roles={["NGO_ADMIN", ...ADMIN]}><NgoPortal /></ProtectedRoute>} />

              {/* Authority / Admin */}
              <Route path="/admin" element={
                <ProtectedRoute roles={ADMIN}><AdminPortal /></ProtectedRoute>} />
              <Route path="/admin/conflicts" element={
                <ProtectedRoute roles={ADMIN}><ConflictsPage /></ProtectedRoute>} />
              <Route path="/admin/ingestion" element={
                <ProtectedRoute roles={ADMIN}><IngestionConsole /></ProtectedRoute>} />
              <Route path="/admin/situation-report" element={
                <ProtectedRoute roles={ADMIN}><SituationReport /></ProtectedRoute>} />

              {/* Advisory analytics modules (Authority + Rescue Leader) */}
              <Route path="/dashboard" element={
                <ProtectedRoute roles={OPS}><Dashboard /></ProtectedRoute>} />
              <Route path="/map" element={
                <ProtectedRoute roles={["RESCUE_LEADER", "RESCUE_MEMBER", ...ADMIN]}><LiveMap /></ProtectedRoute>} />
              <Route path="/prediction" element={
                <ProtectedRoute roles={OPS}><Prediction /></ProtectedRoute>} />
              <Route path="/rescue-routes" element={
                <ProtectedRoute roles={["RESCUE_LEADER", "RESCUE_MEMBER", ...ADMIN]}><Rescue /></ProtectedRoute>} />
              <Route path="/resources" element={
                <ProtectedRoute roles={["NGO_ADMIN", ...OPS]}><Resources /></ProtectedRoute>} />
              <Route path="/damage" element={
                <ProtectedRoute roles={OPS}><Damage /></ProtectedRoute>} />
              <Route path="/simulation" element={
                <ProtectedRoute roles={OPS}><Simulation /></ProtectedRoute>} />
              <Route path="/incidents" element={
                <ProtectedRoute roles={OPS}><Incidents /></ProtectedRoute>} />
              <Route path="/volunteers" element={
                <ProtectedRoute roles={OPS}><Volunteers /></ProtectedRoute>} />
              <Route path="/social" element={
                <ProtectedRoute roles={OPS}><Social /></ProtectedRoute>} />
              <Route path="/medical" element={
                <ProtectedRoute roles={OPS}><Medical /></ProtectedRoute>} />
              <Route path="/economic" element={
                <ProtectedRoute roles={OPS}><Economic /></ProtectedRoute>} />
              <Route path="/drones" element={
                <ProtectedRoute roles={OPS}><Drones /></ProtectedRoute>} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
      <Toaster position="top-right" richColors />
    </div>
  );
}

export default App;
