import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  FileText,
  Wifi,
  Monitor,
  TriangleAlert,
  Clock3,
  Pause,
  Play,
  RotateCcw,
  Download,
  Info,
  Upload,
} from "lucide-react";
import "./style.css";

type Model = "rules-0.2" | "rules-0.1";
type Part = {
  feature: string;
  points: number | null;
  max: number;
  value: string | null;
  note: string;
};
type LegacyResult = {
  score: number | null;
  status: string;
  reasons: string[];
  features: {
    packets: number;
    active_ratio: number;
    large_ratio: number;
    bytes_per_s: number;
    throughput_cv: number;
  };
};
type Device = {
  id: string;
  score: number | null;
  status: string;
  series: number[];
  rssi_dbm: number | null;
  reasons: string[];
  parts: Part[];
  abstain_reasons: string[];
  partial_score?: number;
  direction: {
    available: boolean;
    tx_frames: number | null;
    rx_frames: number | null;
  };
  comparison: Record<string, LegacyResult>;
  features: {
    packets: number;
    duration_s: number;
    uplink_ratio: number | null;
    periodicity_score: number | null;
    period_s: number | null;
    burst_interval_cv: number | null;
    size_bimodality: number;
    active_ratio: number;
    session_shape: string;
    bytes_per_s: number;
  };
};
type Metrics = {
  confusion_matrix: { tp: number; fp: number; tn: number; fn: number };
  precision: number | null;
  recall: number | null;
  false_positive_rate: number | null;
  abstention_rate: number | null;
};
type Evaluation = {
  disclaimer: string;
  rule_fingerprint: string;
  splits: Record<
    string,
    { sessions: number; seeds: string; variant: string } & Record<
      Model,
      Metrics
    >
  >;
};
type Report = {
  provenance: string;
  provenance_notice: string;
  model_version: string;
  thresholds: Record<string, number>;
  ground_truth: string;
  duration_s: number;
  packet_count: number;
  threshold: number;
  devices: Device[];
  timeline: { second: number; bytes: number }[];
  limitations: string[];
  diagnostics: Record<string, unknown>;
};
const labels: Record<string, string> = {
  candidate: "Candidate",
  low_evidence: "Low evidence",
  insufficient: "Insufficient",
  insufficient_direction: "Direction needed",
};
const abstainText: Record<string, string> = {
  insufficient_observation: "Fewer than 100 frames or 10 seconds observed.",
  insufficient_direction:
    "Transmit/receive direction is unavailable, so uplink features are withheld rather than set to zero.",
};
const models: Model[] = ["rules-0.2", "rules-0.1"];
const splitNames: Record<string, string> = {
  dev: "Development",
  test: "Locked test",
  shift: "Held-out shift",
};
const pct = (v: number | null) => (v === null ? "—" : `${(v * 100).toFixed(0)}%`);
function result(d: Device, model: Model) {
  return model === "rules-0.2"
    ? { score: d.score, status: d.status }
    : {
        score: d.comparison["rules-0.1"].score,
        status: d.comparison["rules-0.1"].status,
      };
}
const provenance: Record<string, string> = {
  synthetic_demo: "SIMULATED DATA — No wireless capture is running.",
  synthetic_file: "SYNTHETIC FILE — No physical measurement.",
  user_declared_authorized_capture:
    "IMPORTED CAPTURE — Origin declared by you; not independently verified.",
  unverified_file: "UNVERIFIED FILE — Data origin is unknown.",
};

function Chart({ report, cursor }: { report: Report | null; cursor: number }) {
  const points = report?.timeline.slice(0, cursor) ?? [];
  const max = Math.max(
    1,
    ...(report?.timeline.map((p) => p.bytes / 1000) ?? [1]),
  );
  const ceil = Math.ceil(max / 50) * 50;
  const svgRef = useRef<SVGSVGElement>(null);
  const [width, setWidth] = useState(1000);
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const observer = new ResizeObserver((entries) =>
      setWidth(Math.max(320, entries[0].contentRect.width)),
    );
    observer.observe(svg);
    return () => observer.disconnect();
  }, []);
  const height = 210,
    left = 48,
    right = 18,
    top = 16,
    bottom = 32;
  const x = (i: number) =>
    left +
    (i / Math.max(1, (report?.timeline.length ?? 60) - 1)) *
      (width - left - right);
  const y = (n: number) =>
    height - bottom - (n / ceil) * (height - top - bottom);
  const path = points
    .map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.bytes / 1000)}`)
    .join(" ");
  return (
    <svg
      ref={svgRef}
      className="chart"
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label="Observed transmission volume per second in kilobytes"
    >
      {[0, 1, 2, 3, 4].map((i) => (
        <g key={i}>
          <line
            x1={left}
            x2={width - right}
            y1={y((ceil * i) / 4)}
            y2={y((ceil * i) / 4)}
          />
          <text x={left - 10} y={y((ceil * i) / 4) + 4} textAnchor="end">
            {Math.round((ceil * i) / 4)}
          </text>
        </g>
      ))}
      {[0, 1, 2, 3, 4, 5, 6].map((i) => {
        const sec = Math.round((((report?.timeline.length ?? 60) - 1) * i) / 6);
        return (
          <g key={i}>
            <line x1={x(sec)} x2={x(sec)} y1={top} y2={height - bottom} />
            <text x={x(sec)} y={height - 12} textAnchor="middle">
              {sec}
            </text>
          </g>
        );
      })}
      <text x="13" y="103" transform="rotate(-90 13 103)" textAnchor="middle">
        kB/s
      </text>
      <path d={path} className="trace" />
    </svg>
  );
}

function App() {
  const [mode, setMode] = useState<"demo" | "pcap">("demo");
  const [page, setPage] = useState("overview");
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState("");
  const [cursor, setCursor] = useState(60);
  const [playing, setPlaying] = useState(false);
  const [simulating, setSimulating] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [allowlist, setAllowlist] = useState("");
  const [authorized, setAuthorized] = useState(false);
  const [source, setSource] = useState("unverified_file");
  const [model, setModel] = useState<Model>("rules-0.2");
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);
  const generation = useRef(0);
  useEffect(() => {
    if (page !== "research" || evaluation) return;
    fetch("/api/evaluation")
      .then((r) => (r.ok ? r.json() : null))
      .then(setEvaluation)
      .catch(() => setEvaluation(null));
  }, [page, evaluation]);
  const install = (r: Report) => {
    setReport(r);
    setSelected(r.devices[0]?.id ?? "");
    setCursor(r.timeline.length);
    setPlaying(false);
  };
  async function loadDemo() {
    const id = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/demo");
      if (!response.ok)
        throw new Error("Local analysis engine is unavailable.");
      const r = await response.json();
      if (id === generation.current) install(r);
    } catch (e) {
      if (id === generation.current) setError((e as Error).message);
    } finally {
      if (id === generation.current) setLoading(false);
    }
  }
  useEffect(() => {
    void loadDemo();
    return () => {
      generation.current++;
    };
  }, []);
  useEffect(() => {
    if (!playing || !report) return;
    const timer = window.setInterval(
      () =>
        setCursor((c) => {
          if (c >= report.timeline.length) {
            setPlaying(false);
            return c;
          }
          return c + 1;
        }),
      250,
    );
    return () => clearInterval(timer);
  }, [playing, report]);
  useEffect(() => {
    if (!simulating) return;
    const id = ++generation.current;
    let stopped = false,
      second = 10,
      timer = 0;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setPlaying(false);
    setReport(null);
    async function tick() {
      try {
        const response = await fetch(`/api/demo?seconds=${second}`, {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Simulation update failed.");
        const result = await response.json();
        if (stopped || id !== generation.current) return;
        install(result);
        setLoading(false);
        if (second >= 60) {
          setSimulating(false);
          return;
        }
        second++;
        timer = window.setTimeout(() => void tick(), 1000);
      } catch (e) {
        if (!stopped) {
          setError((e as Error).message);
          setLoading(false);
          setSimulating(false);
        }
      }
    }
    void tick();
    return () => {
      stopped = true;
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [simulating]);
  function changeMode(next: "demo" | "pcap") {
    generation.current++;
    setSimulating(false);
    setMode(next);
    setReport(null);
    setError("");
    setPlaying(false);
    setLoading(false);
    if (next === "demo") void loadDemo();
  }
  async function upload(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    const id = ++generation.current;
    setLoading(true);
    setError("");
    setReport(null);
    setPlaying(false);
    try {
      if (file.size > 32 * 1024 * 1024)
        throw new Error("Maximum capture size is 32 MiB.");
      const response = await fetch("/api/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/octet-stream",
          "X-Lens-Guard": "local-analysis",
          "X-Authorized": authorized ? "yes" : "no",
          "X-Device-Allowlist": allowlist,
          "X-Source-Kind": source,
        },
        body: file,
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail ?? "Analysis failed.");
      if (id === generation.current) install(result);
    } catch (e) {
      if (id === generation.current) setError((e as Error).message);
    } finally {
      if (id === generation.current) setLoading(false);
    }
  }
  function exportReport() {
    if (!report) return;
    const url = URL.createObjectURL(
      new Blob(
        [JSON.stringify({ ...report, dashboard_view: model }, null, 2)],
        { type: "application/json" },
      ),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = `lens-guard-${report.provenance}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  const device = report?.devices.find((d) => d.id === selected);
  const candidates =
    report?.devices.filter((d) => result(d, model).status === "candidate")
      .length ?? 0;
  const shown = device ? result(device, model) : null;
  const legacy = device?.comparison["rules-0.1"];
  return (
    <div className="shell">
      <aside>
        <div className="wordmark">LENS—GUARD</div>
        <nav aria-label="Main navigation">
          <button
            className={page === "overview" ? "active" : ""}
            onClick={() => setPage("overview")}
          >
            <Activity size={20} />
            Overview
          </button>
          <button
            className={page === "research" ? "active" : ""}
            onClick={() => setPage("research")}
          >
            <FileText size={20} />
            Research notes
          </button>
        </nav>
        <div className="local">
          <Wifi size={26} />
          <div>
            <strong>Local only</strong>
            <small>
              No cloud analysis.
              <br />
              No live collection.
            </small>
          </div>
        </div>
      </aside>
      <main>
        <header>
          <div>
            <h1>
              {page === "overview" ? "Traffic observatory" : "Research notes"}
            </h1>
            <p>Patterns are leads. They are not proof of a camera.</p>
          </div>
          {page === "overview" && (
            <div className="modes" aria-label="Data mode">
              <span>Mode</span>
              <button
                aria-pressed={mode === "demo"}
                onClick={() => changeMode("demo")}
              >
                Demo
              </button>
              <button
                aria-pressed={mode === "pcap"}
                onClick={() => changeMode("pcap")}
              >
                PCAP file
              </button>
            </div>
          )}
        </header>
        {page === "research" ? (
          <section className="research">
            <div className="provenance" role="status">
              <TriangleAlert size={22} />
              <strong>
                SYNTHETIC EVALUATION — Generator behavior, not real-world
                detection accuracy.
              </strong>
              <span>No physical devices.</span>
            </div>
            <h2>What this prototype can tell you</h2>
            <p>
              LENS-GUARD ranks traffic patterns for further investigation. It
              cannot establish that a device is a camera, that recording is
              happening, or that a room is safe.
            </p>
            <h2>Explainable baseline</h2>
            <p>
              rules-0.2 scores six parts: uplink share of bytes (30 points),
              periodic large bursts from 100 ms autocorrelation (25), burst
              interval regularity (15), a mix of small and full-size packets
              (10), sustained presence (10) and session shape (10). A score of
              55 starts a candidate review. Without transmit/receive direction
              it abstains instead of filling uplink features with zero.
              rules-0.1 (activity, large packets, rate, stable throughput;
              threshold 70) is kept for comparison. Thresholds were set on
              synthetic development data and preregistered; they are not
              calibrated on physical devices.
            </p>
            <h2>Synthetic evaluation</h2>
            {evaluation ? (
              <div className="table-wrap">
                <table aria-label="Synthetic evaluation by split and model">
                  <thead>
                    <tr>
                      <th>Split</th>
                      <th>Model</th>
                      <th>TP / FP / TN / FN</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>FPR</th>
                      <th>Abstained</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(evaluation.splits).flatMap(([name, split]) =>
                      models.map((m) => {
                        const x = split[m];
                        const c = x.confusion_matrix;
                        return (
                          <tr key={name + m}>
                            <td>
                              {splitNames[name] ?? name}
                              <small className="sub">
                                {split.sessions} sessions · seeds {split.seeds}
                              </small>
                            </td>
                            <td>{m}</td>
                            <td>
                              {c.tp} / {c.fp} / {c.tn} / {c.fn}
                            </td>
                            <td>{pct(x.precision)}</td>
                            <td>{pct(x.recall)}</td>
                            <td>{pct(x.false_positive_rate)}</td>
                            <td>{pct(x.abstention_rate)}</td>
                          </tr>
                        );
                      }),
                    )}
                  </tbody>
                </table>
                <p className="caveat">
                  <Info size={18} />
                  {evaluation.disclaimer} Rule fingerprint{" "}
                  {evaluation.rule_fingerprint}.
                </p>
              </div>
            ) : (
              <p className="empty">Evaluation summary is unavailable.</p>
            )}
            <h2>Research foundations</h2>
            <p>
              <a
                href="https://www.usenix.org/conference/usenixsecurity22/presentation/sharma-rahul"
                target="_blank"
                rel="noreferrer"
              >
                Lumos
              </a>{" "}
              explores wireless metadata and device identification.{" "}
              <a
                href="https://www.acsac.org/2022/program/papers/"
                target="_blank"
                rel="noreferrer"
              >
                SCamF
              </a>{" "}
              explores video traffic behavior and user motion. This prototype
              does not reproduce either system. See the repository research
              audit for artifact checks and hardware requirements.
            </p>
            <h2>Evidence boundaries</h2>
            <p>
              Demo and generated PCAP fixtures are synthetic. Imported files
              retain your source declaration; their origin and device identities
              are not independently verified. The included evaluation measures
              simulated scenarios only.
            </p>
            <h2>Privacy and collection</h2>
            <p>
              Capture files are processed in local memory. Only allowed source
              MACs contribute to analysis; results use per-analysis pseudonyms.
              Contents are not decrypted or displayed. No scanning, probe
              traffic, authentication bypass, or automatic capture is
              implemented.
            </p>
            <h2>Known confounders</h2>
            <p>
              Live-stream uploads look like camera streams and remain
              candidates. In the held-out synthetic shift, presenter-style
              video calls and chatty one-second sensors also became candidates.
              Quiet and low-rate cameras may be missed. Ethernet captures do not establish
              Wi-Fi visibility. Radio signal strength is not a reliable distance
              measurement.
            </p>
          </section>
        ) : (
          <>
            <div
              className={`provenance ${mode === "pcap" ? "imported" : ""}`}
              role="status"
            >
              <TriangleAlert size={22} />
              <strong>
                {report
                  ? provenance[report.provenance]
                  : mode === "demo"
                    ? "SIMULATED DATA — Loading local demo."
                    : "OFFLINE ANALYSIS — Select an authorized capture."}
              </strong>
              <span>
                {mode === "demo"
                  ? "Research demonstration only."
                  : "No wireless capture is running."}
              </span>
            </div>
            {mode === "pcap" && (
              <form className="upload" onSubmit={upload}>
                <div className="form-row">
                  <label>
                    PCAP / PCAPNG file
                    <input
                      type="file"
                      accept=".pcap,.pcapng,.cap"
                      required
                      onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    />
                  </label>
                  <label>
                    Authorized source MAC addresses
                    <input
                      value={allowlist}
                      required
                      placeholder="02:00:00:00:00:01"
                      onChange={(e) => setAllowlist(e.target.value)}
                    />
                  </label>
                  <label>
                    Data origin
                    <select
                      value={source}
                      onChange={(e) => setSource(e.target.value)}
                    >
                      <option value="unverified_file">
                        Unknown / unverified
                      </option>
                      <option value="synthetic_file">
                        Synthetic test file
                      </option>
                      <option value="user_declared_authorized_capture">
                        My authorized physical capture
                      </option>
                    </select>
                  </label>
                </div>
                <div className="form-bottom">
                  <label className="consent">
                    <input
                      type="checkbox"
                      checked={authorized}
                      onChange={(e) => setAuthorized(e.target.checked)}
                    />
                    I own these devices or have explicit permission to analyze
                    them.
                  </label>
                  <button
                    className="primary"
                    disabled={!authorized || !file || loading}
                  >
                    <Upload size={16} />
                    {loading ? "Analyzing…" : "Analyze locally"}
                  </button>
                </div>
                <small>
                  32 MiB maximum · Ethernet, 802.11 and Radiotap · files are not
                  stored by the server
                </small>
              </form>
            )}
            {error && (
              <div className="error" role="alert">
                {error}
                {mode === "demo" && (
                  <button onClick={() => void loadDemo()}>Retry</button>
                )}
              </div>
            )}
            <section className="stats" aria-label="Analysis summary">
              <div>
                <span className="metric-icon green">
                  <Monitor />
                </span>
                <div>
                  <small>Observed sources</small>
                  <strong>{report?.devices.length ?? "—"}</strong>
                </div>
              </div>
              <div>
                <span className="metric-icon amber">
                  <TriangleAlert />
                </span>
                <div>
                  <small>Candidates</small>
                  <strong>{report ? candidates : "—"}</strong>
                </div>
              </div>
              <div>
                <span className="metric-icon">
                  <Clock3 />
                </span>
                <div>
                  <small>Observation</small>
                  <strong>
                    {report ? Math.round(report.duration_s) + " s" : "—"}
                  </strong>
                </div>
              </div>
            </section>
            <section className="panel traffic">
              <div className="panel-title">
                <h2>Traffic over time</h2>
                <div className="playback">
                  <small>
                    {simulating
                      ? "Simulation · updates every second"
                      : report
                        ? "Replay · 4× · full-window scores"
                        : ""}
                  </small>
                  {mode === "demo" && (
                    <button onClick={() => setSimulating((v) => !v)}>
                      {simulating ? "Stop simulation" : "Run simulation"}
                    </button>
                  )}
                  <button
                    className="primary"
                    disabled={!report || simulating}
                    onClick={() => {
                      if (!playing && cursor >= (report?.timeline.length ?? 0))
                        setCursor(1);
                      setPlaying(!playing);
                    }}
                  >
                    {playing ? <Pause size={16} /> : <Play size={16} />}{" "}
                    {playing ? "Pause" : "Replay"}
                  </button>
                  <button
                    disabled={!report || simulating}
                    onClick={() => {
                      setCursor(report?.timeline.length ?? 0);
                      setPlaying(false);
                    }}
                  >
                    <RotateCcw size={16} />
                    Reset
                  </button>
                </div>
              </div>
              <Chart report={report} cursor={cursor} />
              <div className="axis-label">
                Time (seconds) ·{" "}
                {report
                  ? `${Math.min(cursor, report.timeline.length)} / ${report.timeline.length} bins`
                  : "Awaiting data"}
              </div>
            </section>
            <div className="results">
              <section className="panel devices">
                <div className="panel-title">
                  <h2>Sources ({report?.devices.length ?? 0})</h2>
                  <div className="modes compact" aria-label="Scoring model">
                    {models.map((m) => (
                      <button
                        key={m}
                        aria-pressed={model === m}
                        onClick={() => setModel(m)}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="table-wrap">
                  <table aria-label="Observed sources">
                    <thead>
                      <tr>
                        <th>Source</th>
                        <th>Pattern score · {model}</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report?.devices.map((d, i) => {
                        const r = result(d, model);
                        return (
                        <tr
                          key={d.id}
                          className={selected === d.id ? "selected" : ""}
                        >
                          <td>
                            <button
                              className="device-button"
                              aria-label={`Select source ${i + 1}`}
                              onClick={() => setSelected(d.id)}
                            >
                              <Monitor size={17} />
                              <span>
                                Source {String(i + 1).padStart(2, "0")}
                                <small>{d.id}</small>
                              </span>
                            </button>
                          </td>
                          <td>
                            <div className="score">
                              <span>{r.score ?? "—"}</span>
                              <meter
                                min={0}
                                max={100}
                                value={r.score ?? 0}
                                aria-label={`Pattern score for source ${i + 1}`}
                              />
                            </div>
                          </td>
                          <td>
                            <span className={`status ${r.status}`}>
                              {labels[r.status] ?? r.status}
                            </span>
                          </td>
                        </tr>
                        );
                      })}
                    </tbody>
                  </table>
                  {!report?.devices.length && (
                    <div className="empty">
                      {loading
                        ? "Analyzing metadata…"
                        : report
                          ? "No eligible sources matched. Check the allowlist and capture type."
                          : "Import a capture to inspect authorized sources."}
                    </div>
                  )}
                </div>
              </section>
              <section className="panel detail">
                <h2>Selected source</h2>
                {device ? (
                  <>
                    <div className="identity">
                      <span className="metric-icon">
                        <Monitor />
                      </span>
                      <div>
                        <strong>{device.id}</strong>
                        <small>
                          {device.features.packets.toLocaleString()} packets ·{" "}
                          {device.rssi_dbm === null
                            ? "RSSI unavailable"
                            : `${device.rssi_dbm} dBm (not distance)`}
                        </small>
                      </div>
                    </div>
                    <h3>Experimental score · not a probability · {model}</h3>
                    <div className="big-score">
                      <strong>{shown?.score ?? "—"}</strong>
                      <meter min={0} max={100} value={shown?.score ?? 0} />
                    </div>
                    <table className="compare" aria-label="Model comparison">
                      <thead>
                        <tr>
                          <th>Model</th>
                          <th>Score</th>
                          <th>Threshold</th>
                          <th>Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {models.map((m) => {
                          const r = result(device, m);
                          return (
                            <tr key={m}>
                              <td>{m}</td>
                              <td>{r.score ?? "—"}</td>
                              <td>{report?.thresholds?.[m] ?? "—"}</td>
                              <td>{labels[r.status] ?? r.status}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <h3>Direction</h3>
                    <p className="direction" aria-label="Direction availability">
                      {device.direction.available
                        ? `Available · ${device.direction.tx_frames?.toLocaleString()} sent / ${device.direction.rx_frames?.toLocaleString()} received frames · uplink share ${pct(device.features.uplink_ratio)}`
                        : "Unavailable · uplink features withheld"}
                    </p>
                    {device.abstain_reasons.length > 0 && (
                      <div className="abstain" role="note">
                        <strong>Abstained</strong>
                        <ul>
                          {device.abstain_reasons.map((r) => (
                            <li key={r}>{abstainText[r] ?? r}</li>
                          ))}
                        </ul>
                        {device.partial_score !== undefined && (
                          <small>
                            Partial score without uplink features:{" "}
                            {device.partial_score} of 70
                          </small>
                        )}
                      </div>
                    )}
                    {model === "rules-0.2" ? (
                      <>
                        <h3>Score contributions</h3>
                        <ul className="parts" aria-label="Score contributions">
                          {device.parts.map((p) => (
                            <li key={p.feature}>
                              <div>
                                <span>{p.feature}</span>
                                <strong>
                                  {p.points === null ? "not scored" : p.points}{" "}
                                  / {p.max}
                                </strong>
                              </div>
                              <meter
                                min={0}
                                max={p.max}
                                value={p.points ?? 0}
                                aria-label={`${p.feature} points`}
                              />
                              <small>{p.value ?? p.note}</small>
                              {p.value && p.note && <small>{p.note}</small>}
                            </li>
                          ))}
                        </ul>
                      </>
                    ) : (
                      legacy && (
                        <>
                          <h3>rules-0.1 features · transmit side</h3>
                          <dl>
                            <div>
                              <dt>Sustained activity</dt>
                              <dd>{pct(legacy.features.active_ratio)}</dd>
                            </div>
                            <div>
                              <dt>Large packets ≥ 1,000 B</dt>
                              <dd>{pct(legacy.features.large_ratio)}</dd>
                            </div>
                            <div>
                              <dt>Throughput variation (CV)</dt>
                              <dd>{legacy.features.throughput_cv.toFixed(2)}</dd>
                            </div>
                            <div>
                              <dt>Mean transmission rate</dt>
                              <dd>
                                {(legacy.features.bytes_per_s / 1000).toFixed(1)}{" "}
                                kB/s
                              </dd>
                            </div>
                          </dl>
                        </>
                      )
                    )}
                    <details>
                      <summary>Why this score?</summary>
                      <ul>
                        {(model === "rules-0.2"
                          ? device.reasons
                          : (legacy?.reasons ?? [])
                        ).map((r) => (
                          <li key={r}>{r}</li>
                        ))}
                      </ul>
                    </details>
                  </>
                ) : (
                  <p className="empty">Select a source to see the evidence.</p>
                )}
                <p className="caveat">
                  <Info size={18} />
                  Live-stream uploads and some calls can look similar.
                </p>
              </section>
            </div>
            {report && (
              <details className="limits">
                <summary>Visibility, data origin and limitations</summary>
                <p>
                  Source: {report.provenance}. {report.provenance_notice}{" "}
                  Ground truth: not verified.
                </p>
                <ul>
                  {report.limitations.map((l) => (
                    <li key={l}>{l}</li>
                  ))}
                </ul>
                <p>
                  Visibility: {String(report.diagnostics.visibility ?? "synthetic")}
                  . Accepted: {report.packet_count}; skipped outside allowlist:{" "}
                  {String(report.diagnostics.outside_allowlist ?? 0)}; retries
                  skipped: {String(report.diagnostics.retry_frames ?? 0)}.
                </p>
              </details>
            )}
            <footer>
              <button
                className="primary"
                disabled={!report}
                onClick={exportReport}
              >
                <Download size={17} />
                Export report
              </button>
              <span>
                Research prototype · {report?.model_version ?? "rules-0.2"} ·
                candidates require independent review
              </span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
