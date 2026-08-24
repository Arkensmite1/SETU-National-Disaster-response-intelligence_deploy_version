import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ROLE_HOME, useAuth } from "@/context/AuthContext";

export default function ProtectedRoute({ roles, children }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="max-w-[1600px] mx-auto px-4 py-16 text-slate-500" data-testid="auth-loading">
        Verifying your session…
      </div>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  const allowed = !roles || roles.includes(user.role) || user.role === "SUPER_ADMIN";
  if (!allowed) {
    return (
      <div className="max-w-[1600px] mx-auto px-4 py-12" data-testid="role-denied">
        <div className="bg-white border border-slate-200 rounded-md p-6">
          <div className="text-[11px] font-bold uppercase tracking-widest text-status-critical" style={{ color: "#C62828" }}>
            Access restricted
          </div>
          <h2 className="font-heading font-extrabold text-national text-xl mt-1">
            This area is not available for your role
          </h2>
          <p className="text-sm text-slate-600 mt-2">
            You are signed in as <strong>{user.role}</strong>. Section 21.1 of the SETU specification
            scopes data by role, and this is enforced by the API as well as the interface.
          </p>
          <a
            href={ROLE_HOME[user.role] || "/"}
            data-testid="role-denied-home-link"
            className="inline-block mt-4 px-4 py-2 rounded-md bg-national text-white text-sm font-semibold"
          >
            Go to my dashboard
          </a>
        </div>
      </div>
    );
  }
  return children;
}
