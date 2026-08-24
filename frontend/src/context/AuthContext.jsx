import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { setuApi, setuEndpoints, TOKEN_KEY, setUnauthorizedHandler } from "@/lib/setuApi";

const AuthContext = createContext(null);

export const ROLE_LABEL = {
  USER: "Citizen",
  RESCUE_LEADER: "Rescue Team Leader",
  RESCUE_MEMBER: "Rescue Team Member",
  SHELTER_ADMIN: "Shelter Admin",
  NGO_ADMIN: "NGO Admin",
  AUTHORITY: "Admin / Authority",
  SUPER_ADMIN: "Super Admin",
};

export const ROLE_HOME = {
  USER: "/citizen",
  RESCUE_LEADER: "/rescue/leader",
  RESCUE_MEMBER: "/rescue/member",
  SHELTER_ADMIN: "/shelter-admin",
  NGO_ADMIN: "/ngo",
  AUTHORITY: "/admin",
  SUPER_ADMIN: "/admin",
};

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY) || null);
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(!!localStorage.getItem(TOKEN_KEY));

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => logout());
  }, [logout]);

  useEffect(() => {
    let cancelled = false;
    if (!token) {
      setUser(null);
      setLoading(false);
      return () => { cancelled = true; };
    }
    setLoading(true);
    setuApi
      .get(setuEndpoints.me)
      .then(({ data }) => { if (!cancelled) setUser(data); })
      .catch(() => { if (!cancelled) logout(); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [token, logout]);

  const persist = (data) => {
    localStorage.setItem(TOKEN_KEY, data.token);
    setToken(data.token);
    setUser(data.user);
    return data.user;
  };

  const requestOtp = async (mobile) => {
    const { data } = await setuApi.post(setuEndpoints.otpRequest, { mobile });
    return data;
  };

  const verifyOtp = async (payload) => {
    const { data } = await setuApi.post(setuEndpoints.otpVerify, payload);
    return persist(data);
  };

  const staffLogin = async (email, password) => {
    const { data } = await setuApi.post(setuEndpoints.login, { email, password });
    return persist(data);
  };

  const refresh = async () => {
    const { data } = await setuApi.get(setuEndpoints.me);
    setUser(data);
    return data;
  };

  const value = useMemo(
    () => ({
      user, token, loading, logout, requestOtp, verifyOtp, staffLogin, refresh,
      role: user?.role || null,
      isCitizen: user?.role === "USER",
      isAdmin: ["AUTHORITY", "SUPER_ADMIN"].includes(user?.role),
    }),
    [user, token, loading, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
