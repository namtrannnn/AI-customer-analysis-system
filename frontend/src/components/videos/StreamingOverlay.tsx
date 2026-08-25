"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import type { StreamDetectionPayload } from "@/services/video_stream.service";

interface StreamingOverlayProps {
  detections: StreamDetectionPayload[];
  videoElement: HTMLVideoElement | null;
}

interface DisplayDetection extends StreamDetectionPayload {
  receivedAtMs: number;
}

interface OverlayScale {
  width: number;
  height: number;
  left: number;
  top: number;
}

const BOX_CONFIG = {
  // Không xóa bbox chỉ vì một vài event WebSocket bị thưa.
  // Bbox chỉ bị xóa khi timeline video đã đi xa detection cuối.
  sourceTimelineTtlSeconds: 2.0,

  // Fallback nếu payload không có source_timestamp_seconds.
  wallClockTtlMs: 3000,

  // Chặn bbox lỗi/siêu nhỏ.
  minimumBoxSizePx: 4,
} as const;

function isValidBBox(
  bbox: StreamDetectionPayload["bbox"],
): bbox is [number, number, number, number] {
  if (!Array.isArray(bbox) || bbox.length !== 4) {
    return false;
  }

  if (!bbox.every((value) => Number.isFinite(value))) {
    return false;
  }

  const [x1, y1, x2, y2] = bbox;
  return x2 > x1 && y2 > y1;
}

function normalizeBBox(
  detection: StreamDetectionPayload,
): [number, number, number, number] | null {
  if (!isValidBBox(detection.bbox)) {
    return null;
  }

  const [x1, y1, x2, y2] = detection.bbox;

  // Backend đã trả bbox normalized.
  if (
    x1 >= 0 &&
    y1 >= 0 &&
    x2 <= 1 &&
    y2 <= 1
  ) {
    return [
      Math.max(0, Math.min(1, x1)),
      Math.max(0, Math.min(1, y1)),
      Math.max(0, Math.min(1, x2)),
      Math.max(0, Math.min(1, y2)),
    ];
  }

  // Fallback cho bbox pixel nếu payload có kích thước frame nguồn.
  const payload = detection as StreamDetectionPayload & {
    frame_width?: number;
    frame_height?: number;
    source_width?: number;
    source_height?: number;
  };

  const frameWidth = Number(
    payload.frame_width ?? payload.source_width ?? 0,
  );
  const frameHeight = Number(
    payload.frame_height ?? payload.source_height ?? 0,
  );

  if (
    !Number.isFinite(frameWidth) ||
    !Number.isFinite(frameHeight) ||
    frameWidth <= 0 ||
    frameHeight <= 0
  ) {
    return null;
  }

  return [
    Math.max(0, Math.min(1, x1 / frameWidth)),
    Math.max(0, Math.min(1, y1 / frameHeight)),
    Math.max(0, Math.min(1, x2 / frameWidth)),
    Math.max(0, Math.min(1, y2 / frameHeight)),
  ];
}

function getBoxClasses(trackId: number): {
  border: string;
  background: string;
  label: string;
} {
  const styles = [
    {
      border: "border-emerald-500",
      background: "bg-emerald-500/10",
      label: "bg-emerald-500",
    },
    {
      border: "border-indigo-500",
      background: "bg-indigo-500/10",
      label: "bg-indigo-500",
    },
    {
      border: "border-amber-500",
      background: "bg-amber-500/10",
      label: "bg-amber-500",
    },
    {
      border: "border-rose-500",
      background: "bg-rose-500/10",
      label: "bg-rose-500",
    },
    {
      border: "border-cyan-500",
      background: "bg-cyan-500/10",
      label: "bg-cyan-500",
    },
    {
      border: "border-violet-500",
      background: "bg-violet-500/10",
      label: "bg-violet-500",
    },
  ];

  const safeTrackId = Math.abs(
    Number.isFinite(trackId) ? trackId : 0,
  );

  return styles[safeTrackId % styles.length];
}


function normalizeIdentityStatus(value: unknown): string {
  return String(value ?? "")
    .trim()
    .toUpperCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");
}

function isStableProfile(
  detection: StreamDetectionPayload,
): boolean {
  const status = normalizeIdentityStatus(
    detection.identity_status,
  );

  if (
    [
      "TEMP",
      "PENDING",
      "TENTATIVE",
      "RECHECK",
      "ANALYZING",
      "UNKNOWN",
    ].includes(status)
  ) {
    return false;
  }

  const profileId = String(
    detection.session_profile_id ??
      detection.anonymous_code ??
      "",
  );

  return (
    /^P_\d+$/i.test(profileId) ||
    detection.person_profile_id != null
  );
}

function getPendingLabel(
  detection: StreamDetectionPayload,
): string {
  const status = normalizeIdentityStatus(
    detection.identity_status,
  );

  if (status === "RECHECK") {
    return "Đang kiểm tra lại";
  }

  if (
    status === "PENDING" ||
    status === "TENTATIVE"
  ) {
    return "Đang xác minh";
  }

  return "Đang phát hiện";
}

export default function StreamingOverlay({
  detections,
  videoElement,
}: StreamingOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const [scale, setScale] = useState<OverlayScale>({
    width: 1,
    height: 1,
    left: 0,
    top: 0,
  });

  // Một track chỉ có một bbox trong DOM.
  // detection prop rỗng không làm xóa box ngay.
  const [displayByTrack, setDisplayByTrack] = useState<
    Map<number, DisplayDetection>
  >(new Map());

  useEffect(() => {
    if (!videoElement) {
      return;
    }

    const updateScale = () => {
      const rect = videoElement.getBoundingClientRect();

      if (rect.width <= 0 || rect.height <= 0) {
        return;
      }

      const sourceWidth =
        videoElement.videoWidth || 640;
      const sourceHeight =
        videoElement.videoHeight || 360;

      const sourceAspect =
        sourceWidth / sourceHeight;
      const elementAspect =
        rect.width / rect.height;

      let displayWidth = rect.width;
      let displayHeight = rect.height;
      let left = 0;
      let top = 0;

      if (elementAspect > sourceAspect) {
        displayWidth =
          rect.height * sourceAspect;
        left =
          (rect.width - displayWidth) / 2;
      } else {
        displayHeight =
          rect.width / sourceAspect;
        top =
          (rect.height - displayHeight) / 2;
      }

      setScale({
        width: displayWidth,
        height: displayHeight,
        left,
        top,
      });
    };

    updateScale();

    const resizeObserver =
      new ResizeObserver(updateScale);

    resizeObserver.observe(videoElement);

    videoElement.addEventListener(
      "loadedmetadata",
      updateScale,
    );

    return () => {
      resizeObserver.disconnect();
      videoElement.removeEventListener(
        "loadedmetadata",
        updateScale,
      );
    };
  }, [videoElement]);

  useEffect(() => {
    if (detections.length === 0) {
      // Cố ý không clear. Overlay sẽ tự cleanup theo timeline video.
      return;
    }

    const nowMs = performance.now();

    setDisplayByTrack((previous) => {
      const next = new Map(previous);

      for (const detection of detections) {
        if (!isValidBBox(detection.bbox)) {
          continue;
        }

        const old = next.get(detection.track_id);

        // Không cho event cũ ghi đè event mới, trừ khi nó là
        // global identity update có cùng bbox.
        if (
          old &&
          detection.frame_index < old.frame_index
        ) {
          next.set(detection.track_id, {
            ...old,
            person_profile_id:
              detection.person_profile_id ??
              old.person_profile_id,
            session_profile_id:
              detection.session_profile_id ??
              old.session_profile_id,
            anonymous_code:
              detection.anonymous_code ??
              old.anonymous_code,
            customer_type:
              detection.customer_type ??
              old.customer_type,
            total_visits:
              detection.total_visits ??
              old.total_visits,
            customer_id:
              detection.customer_id ??
              old.customer_id,
            customer_name:
              detection.customer_name ??
              old.customer_name,
            current_video_avatar:
              detection.current_video_avatar ??
              old.current_video_avatar,
          });

          continue;
        }

        next.set(detection.track_id, {
          ...old,
          ...detection,
          receivedAtMs: nowMs,
        });
      }

      return next;
    });
  }, [detections]);

  useEffect(() => {
    if (!videoElement) {
      return;
    }

    const cleanupTimer = window.setInterval(() => {
      const videoTime = videoElement.currentTime;
      const nowMs = performance.now();

      setDisplayByTrack((previous) => {
        let changed = false;
        const next = new Map(previous);

        for (const [trackId, detection] of next) {
          const sourceTime = Number(
            detection.source_timestamp_seconds,
          );

          let shouldRemove = false;

          if (
            Number.isFinite(sourceTime) &&
            sourceTime >= 0
          ) {
            // Khi video giảm tốc, videoTime vẫn nhỏ hơn sourceTime,
            // nên bbox không bị xóa.
            shouldRemove =
              videoTime - sourceTime >
              BOX_CONFIG.sourceTimelineTtlSeconds;
          } else {
            shouldRemove =
              nowMs - detection.receivedAtMs >
              BOX_CONFIG.wallClockTtlMs;
          }

          if (shouldRemove) {
            next.delete(trackId);
            changed = true;
          }
        }

        return changed ? next : previous;
      });
    }, 150);

    return () => {
      window.clearInterval(cleanupTimer);
    };
  }, [videoElement]);

  const displayDetections = useMemo(
    () =>
      Array.from(displayByTrack.values()).sort(
        (first, second) =>
          first.track_id - second.track_id,
      ),
    [displayByTrack],
  );

  return (
    <div
      ref={containerRef}
      className="pointer-events-none absolute inset-0 z-10 overflow-hidden"
    >
      <div
        className="absolute"
        style={{
          left: `${scale.left}px`,
          top: `${scale.top}px`,
          width: `${scale.width}px`,
          height: `${scale.height}px`,
        }}
      >
        {detections.map((detection) => {
          // --- SỬA ĐOẠN NÀY ---
          // Dùng hàm normalizeBBox để đảm bảo an toàn và tính ra width/height chuẩn
          const normBbox = normalizeBBox(detection);
          if (!normBbox) return null;

          const [x1, y1, x2, y2] = normBbox;
          const boxWidth = x2 - x1;
          const boxHeight = y2 - y1;
          // --------------------

          const status = detection.identity_status || "CONFIRMED";
          const isConfirmed = status === "CONFIRMED";

          // Cấu hình màu sắc theo trạng thái định danh
          let themeColor = "border-slate-400 bg-slate-500/10";
          let labelBg = "bg-slate-500";
          let labelText = "TRACKING";

          if (status === "PENDING") {
            themeColor = "border-amber-400 bg-amber-500/10 shadow-[0_0_10px_rgba(251,191,36,0.3)]";
            labelBg = "bg-amber-500";
            labelText = "ANALYZING";
          } else if (status === "TENTATIVE") {
            themeColor = "border-sky-400 bg-sky-500/10 shadow-[0_0_10px_rgba(56,189,248,0.3)]";
            labelBg = "bg-sky-500";
            labelText = "CANDIDATE";
          } else if (status === "RECHECK") {
            themeColor = "border-rose-400 bg-rose-500/10 shadow-[0_0_10px_rgba(251,113,133,0.3)]";
            labelBg = "bg-rose-500";
            labelText = "RE-SYNC";
          } else if (status === "CONFIRMED") {
            themeColor = "border-indigo-500 bg-indigo-500/10 shadow-[0_0_15px_rgba(99,102,241,0.3)]";
            labelBg = "bg-indigo-500";
            labelText = detection.session_profile_id || `P-ID PENDING`;
          }

          const displayLabel = isConfirmed 
            ? (detection.customer_name || detection.session_profile_id || `TRK-${detection.track_id}`)
            : `${labelText} [${detection.track_id}]`;

          return (
            <div
              key={detection.track_id}
              className="absolute transition-all duration-75 pointer-events-none"
              style={{
                // --- CẬP NHẬT BIẾN Ở ĐÂY ---
                left: `${x1 * 100}%`,
                top: `${y1 * 100}%`,
                width: `${boxWidth * 100}%`,
                height: `${boxHeight * 100}%`,
              }}
            >
              <div className={`absolute inset-0 border-[1.5px] ${themeColor}`}></div>

              {isConfirmed && (
                <>
                  <div className="absolute top-[-1px] left-[-1px] h-3 w-3 border-t-2 border-l-2 border-indigo-500"></div>
                  <div className="absolute top-[-1px] right-[-1px] h-3 w-3 border-t-2 border-r-2 border-indigo-500"></div>
                  <div className="absolute bottom-[-1px] left-[-1px] h-3 w-3 border-b-2 border-l-2 border-indigo-500"></div>
                  <div className="absolute bottom-[-1px] right-[-1px] h-3 w-3 border-b-2 border-r-2 border-indigo-500"></div>
                </>
              )}

              <div className={`absolute -top-6 left-[-1.5px] flex items-center px-2 py-0.5 shadow-sm transition-colors ${labelBg}`}>
                <span className="text-[10px] font-bold uppercase tracking-wider text-white">
                  {displayLabel}
                </span>
                <span className="ml-2 font-mono text-[9px] text-white/80">
                  {Math.round(detection.confidence * 100)}%
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}