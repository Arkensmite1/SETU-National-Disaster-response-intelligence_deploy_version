import React, { useRef, useState } from "react";
import { api, endpoints } from "@/lib/api";
import { SectionHeading, Panel } from "@/components/common/GovUI";
import { Button } from "@/components/ui/button";
import { Camera, Loader2, Upload, Ruler, ShieldQuestion } from "lucide-react";
import { toast } from "sonner";

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function ImageTool({ title, icon: Icon, endpoint, prompt, testId }) {
  const inputRef = useRef();
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  const analyze = async () => {
    const f = inputRef.current?.files?.[0];
    if (!f) return toast.error("Please choose an image first.");
    setBusy(true); setResult("");
    try {
      const b64 = await fileToBase64(f);
      const r = await api.post(endpoint, { image_base64: b64, context: prompt });
      setResult(r.data.raw);
    } catch (e) {
      toast.error("Vision AI failed. Try a JPEG/PNG under 4MB.");
    } finally { setBusy(false); }
  };

  return (
    <Panel title={title}>
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className="text-national" />
        <span className="text-sm text-slate-600">{prompt}</span>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg,image/webp"
        onChange={(e) => {
          const f = e.target.files?.[0];
          setPreview(f ? URL.createObjectURL(f) : null);
          setResult("");
        }}
        data-testid={`${testId}-file`}
        className="text-sm file:mr-3 file:py-2 file:px-3 file:rounded-md file:border file:border-slate-200 file:bg-slate-50 file:text-sm file:text-national file:font-semibold hover:file:bg-slate-100"
      />

      {preview && (
        <img src={preview} alt="preview" className="mt-3 max-h-56 rounded-md border border-slate-200" />
      )}

      <div className="mt-3">
        <Button onClick={analyze} disabled={busy} className="bg-national text-white gap-1" data-testid={`${testId}-btn`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />} Analyse with AI Vision
        </Button>
      </div>

      {result && (
        <pre className="mt-3 text-xs bg-slate-50 border border-slate-200 rounded p-3 whitespace-pre-wrap font-mono max-h-72 overflow-y-auto" data-testid={`${testId}-output`}>
          {result}
        </pre>
      )}
    </Panel>
  );
}

export default function Damage() {
  return (
    <div className="max-w-[1600px] mx-auto px-4 py-6">
      <SectionHeading eyebrow="Modules 06 · 07 · 08" title="AI Damage, Depth & Image Classification" description="Upload satellite / drone / mobile photos. AI vision estimates damage, water depth and classifies incident types." />

      <div className="grid lg:grid-cols-3 gap-4">
        <ImageTool
          title="Damage Estimation (satellite / drone)"
          icon={Camera}
          endpoint={endpoints.damage}
          prompt="Estimate submerged buildings, damaged roads and crop loss."
          testId="damage"
        />
        <ImageTool
          title="Water Depth from Photo"
          icon={Ruler}
          endpoint={endpoints.waterDepth}
          prompt="Estimate visible water depth using references."
          testId="depth"
        />
        <ImageTool
          title="Image Classifier (roads, bridges, people)"
          icon={ShieldQuestion}
          endpoint={endpoints.classify}
          prompt="Detect blocked roads, bridges collapsed, stranded people."
          testId="classify"
        />
      </div>

      <div className="mt-6">
        <FakeNews />
      </div>
    </div>
  );
}

function FakeNews() {
  const [text, setText] = useState("Dam has been broken in Tehri! Everyone evacuate NOW!");
  const [source, setSource] = useState("Twitter/X");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  const check = async () => {
    setBusy(true); setResult("");
    try {
      const r = await api.post(endpoints.fakeNews, { text, source });
      setResult(r.data.raw);
    } finally { setBusy(false); }
  };

  return (
    <Panel title="Rumor & Fake News Detection (AI Feature 11)">
      <div className="grid md:grid-cols-2 gap-3">
        <textarea
          data-testid="fakenews-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={4}
          className="w-full border border-slate-200 rounded-md p-2 text-sm"
        />
        <div>
          <label className="text-xs font-bold uppercase tracking-widest text-slate-500 mb-1 block">Source</label>
          <input value={source} onChange={(e) => setSource(e.target.value)} className="w-full border border-slate-200 rounded-md px-3 py-2 text-sm mb-3" data-testid="fakenews-source" />
          <Button onClick={check} disabled={busy} className="bg-national text-white gap-1" data-testid="btn-fakenews-check">
            {busy ? <Loader2 size={14} className="animate-spin" /> : "Verify with AI"}
          </Button>
        </div>
      </div>
      {result && (
        <pre className="mt-3 text-xs bg-slate-50 border border-slate-200 rounded p-3 whitespace-pre-wrap font-mono" data-testid="fakenews-output">{result}</pre>
      )}
    </Panel>
  );
}
