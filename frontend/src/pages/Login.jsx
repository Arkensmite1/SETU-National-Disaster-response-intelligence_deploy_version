import React, { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ShieldAlert, Smartphone, LogIn } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ROLE_HOME, ROLE_LABEL, useAuth } from "@/context/AuthContext";
import { apiError } from "@/lib/setuApi";

export default function Login() {
  const { requestOtp, verifyOtp, staffLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [tab, setTab] = useState("citizen");
  const [busy, setBusy] = useState(false);

  const [mobile, setMobile] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [demoOtp, setDemoOtp] = useState("");
  const [code, setCode] = useState("");
  const [profile, setProfile] = useState({
    name: "", ageGroup: "26-45", preferredLanguage: "en",
    emergencyContactName: "", emergencyContactPhone: "", groupSize: 1,
    accessibility: "",
  });

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const go = (user) => {
    const target = location.state?.from || ROLE_HOME[user.role] || "/";
    toast.success(`Signed in as ${ROLE_LABEL[user.role] || user.role}`);
    navigate(target, { replace: true });
  };

  const sendOtp = async () => {
    if (!/^\d{10}$/.test(mobile)) return toast.error("Enter a valid 10-digit mobile number");
    setBusy(true);
    try {
      const data = await requestOtp(mobile);
      setOtpSent(true);
      setDemoOtp(data.devOtp || "");
      toast.success("OTP generated (delivery is mocked in this build)");
    } catch (e) {
      toast.error(apiError(e, "Could not generate OTP"));
    } finally {
      setBusy(false);
    }
  };

  const verify = async () => {
    if (!code) return toast.error("Enter the OTP");
    setBusy(true);
    try {
      const user = await verifyOtp({
        mobile, code,
        name: profile.name || undefined,
        ageGroup: profile.ageGroup,
        preferredLanguage: profile.preferredLanguage,
        emergencyContactName: profile.emergencyContactName || undefined,
        emergencyContactPhone: profile.emergencyContactPhone || undefined,
        groupSize: Number(profile.groupSize) || 1,
        accessibilityRequirements: profile.accessibility
          ? profile.accessibility.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
      });
      go(user);
    } catch (e) {
      toast.error(apiError(e, "OTP verification failed"));
    } finally {
      setBusy(false);
    }
  };

  const doStaffLogin = async () => {
    if (!email || !password) return toast.error("Enter your official email and password");
    setBusy(true);
    try {
      go(await staffLogin(email.trim(), password));
    } catch (e) {
      toast.error(apiError(e, "Sign-in failed"));
    } finally {
      setBusy(false);
    }
  };

  const field = "w-full px-3 py-2 border border-slate-200 rounded-md text-sm focus:outline-none focus:border-national";

  return (
    <div className="max-w-[1100px] mx-auto px-4 py-10 grid lg:grid-cols-2 gap-8">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-widest text-saffron mb-1">
          Secure sign-in
        </div>
        <h1 className="font-heading font-extrabold text-national text-3xl leading-tight">
          SETU coordination platform
        </h1>
        <p className="text-sm text-slate-600 mt-3 leading-relaxed">
          SETU is a last-mile disaster response and coordination layer. Authoritative disaster
          information is consumed from an NDEM / authorized disaster-information integration —
          SETU does not itself predict or declare disasters.
        </p>
        <ul className="mt-5 space-y-2 text-sm text-slate-700">
          {Object.entries(ROLE_LABEL).map(([role, label]) => (
            <li key={role} className="flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-national inline-block" />
              <strong className="text-national">{label}</strong>
              <span className="text-slate-500 text-xs">— role-scoped data access (Section 21.1)</span>
            </li>
          ))}
        </ul>
        <div className="mt-6 p-3 rounded-md border border-slate-200 bg-white text-xs text-slate-600">
          Citizens sign in with mobile + OTP. OTP delivery is <strong>mocked</strong> in this build
          (no SMS provider is configured), so the generated code is shown on screen after you
          request it.
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-md p-6">
        <div className="flex gap-2 mb-5">
          <button
            data-testid="login-tab-citizen"
            onClick={() => setTab("citizen")}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-semibold border ${
              tab === "citizen" ? "bg-national text-white border-national" : "border-slate-200 text-slate-600"
            }`}
          >
            <Smartphone size={15} /> Citizen
          </button>
          <button
            data-testid="login-tab-staff"
            onClick={() => setTab("staff")}
            className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-sm font-semibold border ${
              tab === "staff" ? "bg-national text-white border-national" : "border-slate-200 text-slate-600"
            }`}
          >
            <ShieldAlert size={15} /> Rescue / Shelter / NGO / Authority
          </button>
        </div>

        {tab === "citizen" ? (
          <div className="space-y-3">
            <label className="block text-xs font-bold uppercase tracking-widest text-slate-500">
              Mobile number
            </label>
            <input
              data-testid="login-mobile-input"
              className={field}
              value={mobile}
              maxLength={10}
              onChange={(e) => setMobile(e.target.value.replace(/\D/g, ""))}
              placeholder="10-digit mobile number"
            />
            {!otpSent ? (
              <Button
                data-testid="login-send-otp-button"
                disabled={busy}
                onClick={sendOtp}
                className="w-full bg-national text-white font-semibold"
              >
                {busy ? "Generating…" : "Send OTP"}
              </Button>
            ) : (
              <>
                {demoOtp && (
                  <div
                    className="p-3 rounded-md border border-amber-200 bg-amber-50 text-sm"
                    data-testid="login-demo-otp"
                  >
                    OTP delivery is mocked. Your code is <strong>{demoOtp}</strong>
                  </div>
                )}
                <label className="block text-xs font-bold uppercase tracking-widest text-slate-500">
                  Enter OTP
                </label>
                <input
                  data-testid="login-otp-input"
                  className={field}
                  value={code}
                  maxLength={6}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
                  placeholder="6-digit code"
                />
                <details className="text-xs text-slate-600">
                  <summary className="cursor-pointer font-semibold text-national py-1">
                    Optional profile details (helps rescue teams reach you)
                  </summary>
                  <div className="grid sm:grid-cols-2 gap-2 mt-2">
                    <input className={field} placeholder="Full name" data-testid="login-name-input"
                      value={profile.name} onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
                    <select className={field} value={profile.ageGroup}
                      onChange={(e) => setProfile({ ...profile, ageGroup: e.target.value })}>
                      {["0-17", "18-25", "26-45", "46-60", "60+"].map((a) => <option key={a} value={a}>{a}</option>)}
                    </select>
                    <select className={field} value={profile.preferredLanguage}
                      data-testid="login-language-select"
                      onChange={(e) => setProfile({ ...profile, preferredLanguage: e.target.value })}>
                      <option value="en">English</option>
                      <option value="hi">हिन्दी</option>
                      <option value="as">অसমীয়া</option>
                      <option value="bn">বাংলা</option>
                      <option value="ta">தமிழ்</option>
                    </select>
                    <input className={field} type="number" min={1} placeholder="People in your group"
                      value={profile.groupSize}
                      onChange={(e) => setProfile({ ...profile, groupSize: e.target.value })} />
                    <input className={field} placeholder="Emergency contact name"
                      value={profile.emergencyContactName}
                      onChange={(e) => setProfile({ ...profile, emergencyContactName: e.target.value })} />
                    <input className={field} placeholder="Emergency contact phone"
                      value={profile.emergencyContactPhone}
                      onChange={(e) => setProfile({ ...profile, emergencyContactPhone: e.target.value })} />
                    <input className={`${field} sm:col-span-2`}
                      placeholder="Accessibility requirements (comma separated)"
                      value={profile.accessibility}
                      onChange={(e) => setProfile({ ...profile, accessibility: e.target.value })} />
                  </div>
                </details>
                <Button
                  data-testid="login-verify-otp-button"
                  disabled={busy}
                  onClick={verify}
                  className="w-full bg-national text-white font-semibold"
                >
                  {busy ? "Verifying…" : "Verify & continue"}
                </Button>
                <button
                  className="text-xs text-slate-500 underline"
                  onClick={() => { setOtpSent(false); setCode(""); setDemoOtp(""); }}
                >
                  Change mobile number
                </button>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            <label className="block text-xs font-bold uppercase tracking-widest text-slate-500">
              Official email
            </label>
            <input
              data-testid="login-email-input"
              className={field}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@setu.gov.in"
            />
            <label className="block text-xs font-bold uppercase tracking-widest text-slate-500">
              Password
            </label>
            <input
              data-testid="login-password-input"
              className={field}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && doStaffLogin()}
              placeholder="••••••••"
            />
            <Button
              data-testid="login-submit-button"
              disabled={busy}
              onClick={doStaffLogin}
              className="w-full bg-national text-white font-semibold gap-2"
            >
              <LogIn size={15} /> {busy ? "Signing in…" : "Sign in"}
            </Button>
            <p className="text-xs text-slate-500">
              Accounts are issued by your controlling authority. Access is role-scoped and every
              action is written to the SETU audit log.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
