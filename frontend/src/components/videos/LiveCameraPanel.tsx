"use client";

import { useEffect, useRef, useState } from "react";
import {
  Activity,
  Camera,
  ListTree,
  Radar,
  RefreshCw,
  ScanLine,
  Square,
  StopCircle,
} from "lucide-react";

import Button from "@/components/ui/Button";
import {
  buildCameraSessionWsUrl,
  createCameraSession,
  createDefaultCenterRoi,
  startCameraSession,
  stopCameraSession,
} from "@/services/camera-session.service";
import type {
  CameraSessionResponse,
  RealtimeEventEnvelope,
  RealtimeStateSnapshotPayload,
  RealtimeTrackSnapshot,
  RoiPolygonConfig,
} from "@/types/camera-session.type";

type LiveRunStatus = "idle" | "starting" | "running" | "stopping" | "error";

function StatCard({
  label,
  value,
  sub,
  icon,
  gradient,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ReactNode;
  gradient: string;
}) {
  return (
    <div className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
      <div
        className={`absolute -right-3 -top-3 h-16 w-16 rounded-full opacity-10 ${gradient}`}
      />
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-300">
            {label}
          </p>
          <p className="mt-1.5 text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            {value}
          </p>
          {sub && (
            <p className="mt-0.5 text-xs text-slate-400 dark:text-slate-400">
              {sub}
            </p>
          )}
        </div>
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-sm`}
        >
          {icon}
        </div>
      </div>
    </div>
  );
}

function formatClock(isoString: string | null | undefined): string {
  if (!isoString) return "—";

  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return "—";

  return date.toLocaleTimeString("vi-VN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

export default function LiveCameraPanel() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const ingestWsRef = useRef<WebSocket | null>(null);
  const eventsWsRef = useRef<WebSocket | null>(null);
  const debugWsRef = useRef<WebSocket | null>(null);
  const currentSessionIdRef = useRef<string | null>(null);
  const captureInFlightRef = useRef(false);
  const frameCounterRef = useRef(0);
  const debugUrlRef = useRef<string | null>(null);

  const [runStatus, setRunStatus] = useState<LiveRunStatus>("idle");
  const [session, setSession] = useState<CameraSessionResponse | null>(null);
  const [sessionState, setSessionState] = useState<string>("CREATED");
  const [currentCount, setCurrentCount] = useState(0);
  const [tracks, setTracks] = useState<RealtimeTrackSnapshot[]>([]);
  const [recentEvents, setRecentEvents] = useState<RealtimeEventEnvelope[]>([]);
  const [debugFrameUrl, setDebugFrameUrl] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [previewSize, setPreviewSize] = useState({ width: 0, height: 0 });
  const [roiConfig, setRoiConfig] = useState<RoiPolygonConfig[]>([]);
  const [debugEnabled, setDebugEnabled] = useState(true);

  const isBusy = runStatus === "starting" || runStatus === "stopping";
  const isRunning = runStatus === "running";
  const showStopButton = runStatus === "running" || runStatus === "stopping";

  async function teardownLocalRuntime(resetState: boolean) {
    ingestWsRef.current?.close();
    eventsWsRef.current?.close();
    debugWsRef.current?.close();
    ingestWsRef.current = null;
    eventsWsRef.current = null;
    debugWsRef.current = null;

    mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    mediaStreamRef.current = null;

    const video = videoRef.current;
    if (video) {
      video.pause();
      video.srcObject = null;
    }

    captureInFlightRef.current = false;
    currentSessionIdRef.current = null;
    frameCounterRef.current = 0;

    if (debugUrlRef.current) {
      URL.revokeObjectURL(debugUrlRef.current);
      debugUrlRef.current = null;
    }

    if (resetState) {
      setSession(null);
      setTracks([]);
      setCurrentCount(0);
      setDebugFrameUrl(null);
    }
  }

  useEffect(() => {
    return () => {
      void teardownLocalRuntime(false);
    };
  }, []);

  useEffect(() => {
    if (runStatus !== "running") return;

    const intervalId = window.setInterval(() => {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ingestWs = ingestWsRef.current;

      if (!video || !canvas || !ingestWs) return;
      if (ingestWs.readyState !== WebSocket.OPEN) return;
      if (captureInFlightRef.current) return;
      if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      if (!video.videoWidth || !video.videoHeight) return;

      const ctx = canvas.getContext("2d");
      if (!ctx) return;

      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      captureInFlightRef.current = true;

      canvas.toBlob((blob) => {
        try {
          if (!blob) return;
          const activeWs = ingestWsRef.current;
          const activeSessionId = currentSessionIdRef.current;

          if (!activeWs || activeWs.readyState !== WebSocket.OPEN || !activeSessionId) {
            return;
          }

          frameCounterRef.current += 1;
          activeWs.send(
            JSON.stringify({
              frame_id: frameCounterRef.current,
              timestamp: new Date().toISOString(),
              width: canvas.width,
              height: canvas.height,
            }),
          );
          activeWs.send(blob);
        } finally {
          captureInFlightRef.current = false;
        }
      }, "image/jpeg", 0.72);
    }, 120);

    return () => {
      window.clearInterval(intervalId);
    };
  }, [runStatus]);

  function appendRecentEvent(event: RealtimeEventEnvelope) {
    setRecentEvents((prev) => [event, ...prev].slice(0, 16));
  }

  async function prepareLocalWebcam(): Promise<{
    stream: MediaStream;
    width: number;
    height: number;
  }> {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        facingMode: "user",
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
      audio: false,
    });

    mediaStreamRef.current = stream;

    const video = videoRef.current;
    if (!video) {
      throw new Error("Khong tim thay video preview de gan webcam.");
    }

    video.srcObject = stream;
    await video.play();

    await new Promise<void>((resolve) => {
      if (video.videoWidth > 0 && video.videoHeight > 0) {
        resolve();
        return;
      }

      const handleLoaded = () => {
        video.removeEventListener("loadedmetadata", handleLoaded);
        resolve();
      };

      video.addEventListener("loadedmetadata", handleLoaded);
    });

    const width = video.videoWidth || 1280;
    const height = video.videoHeight || 720;

    setPreviewSize({ width, height });
    return { stream, width, height };
  }

  async function handleStartLive() {
    setErrorMessage(null);
    setRecentEvents([]);
    setTracks([]);
    setCurrentCount(0);
    setDebugFrameUrl(null);
    setRunStatus("starting");

    let createdSession: CameraSessionResponse | null = null;

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Trinh duyet hien tai khong ho tro webcam.");
      }

      const { width, height } = await prepareLocalWebcam();
      const defaultRoi = createDefaultCenterRoi(width, height);
      setRoiConfig(defaultRoi);

      createdSession = await createCameraSession({
        camera_id: 1,
        source_type: "browser_webcam",
        target_fps: 6,
        debug_enabled: debugEnabled,
        debug_interval_ms: 500,
        roi_config: defaultRoi,
      });

      currentSessionIdRef.current = createdSession.stream_session_id;
      setSession(createdSession);

      const startedSession = await startCameraSession(createdSession.stream_session_id);
      setSession(startedSession);
      setSessionState(startedSession.status);

      openEventsSocket(startedSession);
      openIngestSocket(startedSession);

      if (startedSession.debug_enabled) {
        openDebugSocket(startedSession);
      }

      appendRecentEvent({
        event_type: "session_bootstrap",
        event_timestamp: new Date().toISOString(),
        session_id: startedSession.stream_session_id,
        payload: {
          session_state: startedSession.status,
          current_count: 0,
        },
      });

      frameCounterRef.current = 0;
      setRunStatus("running");
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : "Khong the khoi dong Live Camera.";

      setErrorMessage(message);
      setRunStatus("error");

      if (createdSession?.stream_session_id) {
        try {
          await stopCameraSession(createdSession.stream_session_id);
        } catch {
          // ignore cleanup stop failure
        }
      }

      await teardownLocalRuntime(false);
    }
  }

  async function handleStopLive() {
    setRunStatus("stopping");

    const sessionId = currentSessionIdRef.current;
    if (sessionId) {
      try {
        const stoppedSession = await stopCameraSession(sessionId);
        setSession(stoppedSession);
        setSessionState(stoppedSession.status);
      } catch (error) {
        setErrorMessage(
          error instanceof Error
            ? error.message
            : "Khong the dung Live Camera an toan.",
        );
      }
    }

    await teardownLocalRuntime(true);
    setRunStatus("idle");
  }

  function openIngestSocket(activeSession: CameraSessionResponse) {
    const ws = new WebSocket(
      buildCameraSessionWsUrl(activeSession.ws_endpoints.ingest),
    );
    ingestWsRef.current = ws;
  }

  function openEventsSocket(activeSession: CameraSessionResponse) {
    const ws = new WebSocket(
      buildCameraSessionWsUrl(activeSession.ws_endpoints.events),
    );

    ws.onmessage = (event) => {
      try {
        const envelope = JSON.parse(event.data) as RealtimeEventEnvelope<unknown>;

        if (envelope.event_type === "state_snapshot") {
          const payload = envelope.payload as RealtimeStateSnapshotPayload;

          setSessionState(payload.session_state);
          setCurrentCount(payload.current_count);
          setTracks(payload.tracks);

          for (const roiEvent of payload.roi_events) {
            appendRecentEvent(roiEvent);
          }

          for (const trackEvent of payload.track_events) {
            appendRecentEvent(trackEvent);
          }
          return;
        }

        if (envelope.event_type === "session_state_change") {
          const payload =
            envelope.payload && typeof envelope.payload === "object"
              ? (envelope.payload as Record<string, unknown>)
              : {};
          const nextState = String(
            payload.session_state || "RUNNING",
          );
          setSessionState(nextState);

          if (nextState === "FAILED") {
            setErrorMessage(
              String(
                payload.failure_reason || "Camera session da that bai.",
              ),
            );
            setRunStatus("error");
          }
        }

        appendRecentEvent(envelope);
      } catch {
        // ignore malformed realtime event
      }
    };

    eventsWsRef.current = ws;
  }

  function openDebugSocket(activeSession: CameraSessionResponse) {
    const ws = new WebSocket(
      buildCameraSessionWsUrl(activeSession.ws_endpoints.debug_frame),
    );
    ws.binaryType = "blob";

    ws.onmessage = (event) => {
      const blob =
        event.data instanceof Blob
          ? event.data
          : new Blob([event.data], { type: "image/jpeg" });

      const objectUrl = URL.createObjectURL(blob);
      if (debugUrlRef.current) {
        URL.revokeObjectURL(debugUrlRef.current);
      }

      debugUrlRef.current = objectUrl;
      setDebugFrameUrl(objectUrl);
    };

    debugWsRef.current = ws;
  }

  return (
    <div className="space-y-5">
      <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
        <div className="border-b border-slate-100 px-5 py-4 dark:border-slate-700">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="mb-1 inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                <Camera className="h-3.5 w-3.5" />
                Live Camera
              </div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                Realtime Analytics với webcam browser
              </h2>
              <p className="mt-1 text-sm text-slate-500 dark:text-slate-300">
                Browser gửi frame JPEG qua WebSocket, backend xử lý realtime và trả metadata/debug frame.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <label className="flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-600 dark:border-slate-700 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={debugEnabled}
                  onChange={(e) => setDebugEnabled(e.target.checked)}
                  disabled={isRunning || isBusy}
                  className="h-4 w-4 rounded border-slate-300 text-blue-600"
                />
                Bat debug frame
              </label>

              {!showStopButton ? (
                <Button
                  onClick={handleStartLive}
                  loading={runStatus === "starting"}
                  icon={<Radar className="h-4 w-4" />}
                >
                  Bat dau Live Camera
                </Button>
              ) : (
                <Button
                  variant="danger"
                  onClick={handleStopLive}
                  loading={runStatus === "stopping"}
                  icon={<StopCircle className="h-4 w-4" />}
                >
                  Dung stream
                </Button>
              )}
            </div>
          </div>
        </div>

        <div className="grid gap-5 p-5 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-4">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-950 shadow-inner dark:border-slate-700">
              <div className="flex items-center justify-between border-b border-white/10 px-4 py-3 text-xs text-slate-300">
                <div className="flex items-center gap-2">
                  <span
                    className={`h-2.5 w-2.5 rounded-full ${
                      isRunning
                        ? "bg-emerald-400 shadow-[0_0_0_4px_rgba(74,222,128,0.15)]"
                        : "bg-slate-500"
                    }`}
                  />
                  <span className="font-semibold">Preview webcam local</span>
                </div>
                <span className="rounded-full bg-white/10 px-2 py-1 font-mono">
                  {previewSize.width > 0
                    ? `${previewSize.width}x${previewSize.height}`
                    : "No signal"}
                </span>
              </div>

              <div className="relative aspect-video bg-black">
                <video
                  ref={videoRef}
                  playsInline
                  muted
                  className="h-full w-full object-contain"
                />

                {previewSize.width > 0 && roiConfig.length > 0 && (
                  <svg
                    viewBox={`0 0 ${previewSize.width} ${previewSize.height}`}
                    className="pointer-events-none absolute inset-0 h-full w-full"
                    preserveAspectRatio="xMidYMid meet"
                  >
                    {roiConfig.map((roi) => (
                      <g key={roi.zone_key}>
                        <polygon
                          points={roi.points.map((point) => `${point.x},${point.y}`).join(" ")}
                          fill="rgba(59,130,246,0.10)"
                          stroke="rgba(96,165,250,0.9)"
                          strokeWidth="4"
                        />
                        <text
                          x={roi.points[0]?.x ?? 0}
                          y={(roi.points[0]?.y ?? 0) - 10}
                          fill="white"
                          fontSize="28"
                          fontWeight="700"
                        >
                          {roi.zone_name || roi.zone_key}
                        </text>
                      </g>
                    ))}
                  </svg>
                )}

                {!isRunning && (
                  <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/40 text-center text-slate-200">
                    <ScanLine className="h-10 w-10 text-blue-300" />
                    <div>
                      <p className="text-base font-semibold">Chua co stream realtime</p>
                      <p className="mt-1 text-sm text-slate-300">
                        Bam &quot;Bat dau Live Camera&quot; de cap webcam va gui
                        frame vao backend.
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {debugEnabled && (
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
                <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
                  <div className="flex items-center gap-2 text-sm font-semibold text-slate-800 dark:text-slate-100">
                    <Activity className="h-4 w-4 text-orange-500" />
                    Debug frame annotate
                  </div>
                  <span className="rounded-full bg-orange-100 px-2 py-1 text-[11px] font-semibold text-orange-700 dark:bg-orange-900/30 dark:text-orange-300">
                    1-3 FPS
                  </span>
                </div>
                <div className="relative aspect-video bg-slate-950">
                  {debugFrameUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={debugFrameUrl}
                      alt="Debug realtime frame"
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
                      Chua nhan duoc debug frame tu backend.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                label="Current Count"
                value={currentCount}
                sub="So nguoi dang duoc tracking"
                gradient="from-blue-500 to-indigo-600"
                icon={<Radar className="h-5 w-5 text-white" />}
              />
              <StatCard
                label="Active Tracks"
                value={tracks.length}
                sub="Mutable in-memory cache"
                gradient="from-emerald-500 to-teal-600"
                icon={<ListTree className="h-5 w-5 text-white" />}
              />
              <StatCard
                label="Session State"
                value={sessionState}
                sub={session?.stream_session_id ? session.stream_session_id.slice(0, 8) : "No session"}
                gradient="from-violet-500 to-purple-600"
                icon={<Activity className="h-5 w-5 text-white" />}
              />
              <StatCard
                label="ROI Zones"
                value={roiConfig.length}
                sub="ROI mac dinh de demo"
                gradient="from-amber-500 to-orange-600"
                icon={<Square className="h-5 w-5 text-white" />}
              />
            </div>

            {errorMessage && (
              <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
                {errorMessage}
              </div>
            )}

            <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
              <div className="border-b border-slate-100 px-4 py-3 dark:border-slate-700">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Session metadata
                </h3>
              </div>
              <div className="grid grid-cols-2 gap-3 px-4 py-4 text-sm">
                <MetaLine label="Camera ID" value={session?.camera_id ?? 1} />
                <MetaLine label="Target FPS" value={session?.target_fps ?? 6} />
                <MetaLine
                  label="Started At"
                  value={formatClock(session?.started_at)}
                />
                <MetaLine
                  label="Debug"
                  value={session?.debug_enabled ? "Enabled" : "Disabled"}
                />
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Active tracks
                </h3>
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 dark:bg-slate-700 dark:text-slate-200">
                  {tracks.length}
                </span>
              </div>

              <div className="max-h-[260px] overflow-auto">
                {tracks.length === 0 ? (
                  <div className="px-4 py-10 text-center text-sm text-slate-400">
                    Chua co track nao trong state hien tai.
                  </div>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-100 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:border-slate-700 dark:text-slate-300">
                        <th className="px-4 py-2.5">Track</th>
                        <th className="px-4 py-2.5">ROI</th>
                        <th className="px-4 py-2.5">Confidence</th>
                        <th className="px-4 py-2.5">Last Seen</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50 dark:divide-slate-700/50">
                      {tracks.map((track) => (
                        <tr key={track.track_id}>
                          <td className="px-4 py-3 font-mono text-xs font-semibold text-slate-800 dark:text-slate-100">
                            Trk {track.track_id}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                            {track.active_roi_ids.length > 0
                              ? track.active_roi_ids.join(", ")
                              : "—"}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                            {track.confidence !== null
                              ? `${Math.round(track.confidence * 100)}%`
                              : "—"}
                          </td>
                          <td className="px-4 py-3 text-xs text-slate-500 dark:text-slate-400">
                            {formatClock(track.last_seen_at)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
              <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-700">
                <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Realtime events
                </h3>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setRecentEvents([])}
                  icon={<RefreshCw className="h-3.5 w-3.5" />}
                >
                  Clear
                </Button>
              </div>

              <div className="max-h-[300px] overflow-auto px-4 py-3">
                {recentEvents.length === 0 ? (
                  <div className="py-8 text-center text-sm text-slate-400">
                    Chua co event nao tu stream realtime.
                  </div>
                ) : (
                  <div className="space-y-2">
                    {recentEvents.map((event, index) => (
                      <div
                        key={`${event.event_type}-${event.event_timestamp}-${index}`}
                        className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 dark:border-slate-700 dark:bg-slate-900/40"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-mono text-xs font-semibold text-slate-800 dark:text-slate-100">
                            {event.event_type}
                          </span>
                          <span className="text-[11px] text-slate-400">
                            {formatClock(event.event_timestamp)}
                          </span>
                        </div>
                        <pre className="mt-1 overflow-auto whitespace-pre-wrap break-all text-[11px] text-slate-500 dark:text-slate-300">
                          {JSON.stringify(event.payload, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <canvas ref={canvasRef} className="hidden" />
    </div>
  );
}

function MetaLine({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-sm font-medium text-slate-800 dark:text-slate-100">
        {value}
      </p>
    </div>
  );
}
