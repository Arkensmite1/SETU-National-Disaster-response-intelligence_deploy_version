import React from "react";
import { Link } from "react-router-dom";
import { Panel, SectionHeading } from "@/components/common/GovUI";
import { SafetyNote } from "@/components/setu/SetuBits";
import { useAuth } from "@/context/AuthContext";

export default function PhasePlaceholder({ title, eyebrow, description, phase, capabilities, link, linkLabel }) {
  const { user } = useAuth();
  return (
    <div className="max-w-[1100px] mx-auto px-4 py-8 space-y-6">
      <SectionHeading eyebrow={eyebrow} title={title} description={description} />
      <Panel title={`Planned for ${phase}`}>
        <SafetyNote>
          This portal is scoped by role — signed in as <strong>{user?.role}</strong> you will only
          ever see your own operational data, enforced by the API.
        </SafetyNote>
        <ul className="list-disc ml-5 mt-3 text-sm text-slate-700 space-y-1">
          {capabilities.map((c) => <li key={c}>{c}</li>)}
        </ul>
        {link && (
          <Link to={link} data-testid="placeholder-existing-link"
                className="inline-block mt-4 px-4 py-2 rounded-md bg-national text-white text-sm font-semibold">
            {linkLabel}
          </Link>
        )}
      </Panel>
    </div>
  );
}
