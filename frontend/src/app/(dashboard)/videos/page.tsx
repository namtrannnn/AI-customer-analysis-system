"use client";

import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import { Info, Monitor, Upload, ChevronDown } from "lucide-react";

import VideoUploader from "@/components/videos/VideoUploader";
import VideoPreview from "@/components/videos/VideoPreview";
import VideoAnalysisResultComponent from "@/components/videos/VideoAnalysisResult";
import VideoUploadError from "@/components/videos/VideoUploadError";
import StreamingOverlay from "@/components/videos/StreamingOverlay";
import StreamingProgress from "@/components/videos/StreamingProgress";
import LiveDetectionsList from "@/components/videos/LiveDetectionsList";

import {
  validateVideoFile,
  extractVideoMeta,
} from "@/services/video.service";

import {
  connectJobStream,
  type StreamDetectionPayload,
  type StreamProgressPayload,
} from "@/services/video_stream.service";

import type {
  UploadStatus,
  VideoAnalysisResult,
  VideoError,
  VideoFileMeta,
} from "@/types/video.type";

const STREAM_CONFIG = {
  normalPlaybackRate: 0.8,
  slowPlaybackRate: 0.7,
  emergencyPlaybackRate: 0.5,

  // Chỉ chờ buffer một lần trước khi bắt đầu.
  startBufferSeconds: 15,

  // Sau khi đã bắt đầu thì không pause nữa; chỉ giảm playbackRate.
  slowLeadSeconds: 1.2,
  emergencyLeadSeconds: 0.35,

  bboxLookAheadSeconds: 0.10,
  interpolationMaxGapSeconds: 0.80,
  extrapolationMaxSeconds: 0.22,
  maximumExtrapolationRatio: 1.35,
  holdLastDetectionSeconds: 1.2,

  // Khi video đang nằm trước detection đầu tiên, cho phép dùng mẫu tương lai
  // gần nhất để bbox không biến mất lúc playbackRate thay đổi.
  futureSampleToleranceSeconds: 0.35,

  // Không xóa overlay ngay khi một lần tra timestamp không tìm thấy mẫu.
  overlayEmptyGraceSeconds: 0.8,

  maxSamplesPerTrack: 2000,
  overlayUpdateIntervalMs: 33,
} as const;

type PlaybackState = "waiting" | "playing" | "buffering";

function UploadProgress({ progress }: { progress: number }) {
  return (
    <div className="flex flex-col items-center gap-6 py-16">
      <div className="relative flex h-24 w-24 items-center justify-center">
        <div className="absolute inset-0 animate-spin rounded-full border-4 border-transparent border-t-violet-500" />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600">
          <Upload className="h-6 w-6 text-white" />
        </div>
      </div>

      <div className="text-center">
        <p className="font-bold text-slate-900 dark:text-slate-100">
          Đang tải video lên máy chủ...
        </p>
        <p className="mt-1 text-sm text-slate-500">
          Hệ thống đang chuẩn bị luồng phân tích.
        </p>
      </div>

      <div className="w-full max-w-sm">
        <div className="mb-2 flex justify-between text-xs text-slate-500">
          <span>Tiến độ upload</span>
          <span className="font-bold text-violet-600">{progress}%</span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Guide Accordion (Hướng dẫn sử dụng) ──────────────────────────────────────
function GuideAccordion() {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
      {/* Toggle header */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-700/50"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900/40">
            <Info className="h-4 w-4 text-violet-600 dark:text-violet-400" />
          </div>

          <span className="text-base font-semibold text-slate-700 dark:text-slate-200">
            Hướng dẫn sử dụng
          </span>

          <span className="hidden rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 sm:inline dark:bg-slate-700 dark:text-slate-200">
            Cách hoạt động · Yêu cầu · Kết quả
          </span>
        </div>

        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Accordion content */}
      <div
        className={`transition-all duration-300 ease-in-out ${
          open ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"
        } overflow-hidden`}
      >
        <div className="grid gap-5 border-t border-slate-100 px-5 py-5 dark:border-slate-700 sm:grid-cols-3">
          {/* Cách hoạt động */}
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
              Cách hoạt động
            </p>

            <div className="space-y-2.5">
              {[
                {
                  step: "1",
                  text: "Upload video từ camera",
                  desc: "MP4, AVI, MOV, MKV · max 50MB",
                  color: "from-violet-500 to-purple-600",
                },
                {
                  step: "2",
                  text: "AI phân tích từng frame",
                  desc: "Nhận diện & theo dõi khuôn mặt",
                  color: "from-blue-500 to-indigo-600",
                },
                {
                  step: "3",
                  text: "Phân loại khách hàng",
                  desc: "Mới / quay lại / VIP",
                  color: "from-emerald-500 to-teal-600",
                },
                {
                  step: "4",
                  text: "Nhận báo cáo thống kê",
                  desc: "Confidence, khu vực, thời điểm",
                  color: "from-amber-500 to-orange-500",
                },
              ].map(({ step, text, desc, color }) => (
                <div key={step} className="flex items-start gap-2.5">
                  <div
                    className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br ${color} text-xs font-bold text-white`}
                  >
                    {step}
                  </div>

                  <div>
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-100">
                      {text}
                    </p>

                    <p className="text-xs text-slate-400 dark:text-slate-350">
                      {desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Yêu cầu video */}
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
              Yêu cầu video
            </p>

            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-slate-600 dark:bg-slate-700/70">
              <ul className="space-y-2">
                {[
                  {
                    icon: "📁",
                    label: "Định dạng",
                    value: "MP4, AVI, MOV, MKV",
                  },
                  { icon: "📦", label: "Kích thước", value: "Tối đa 50MB" },
                  { icon: "⏱", label: "Thời lượng", value: "Tối thiểu 3 giây" },
                  {
                    icon: "🖥",
                    label: "Phân giải",
                    value: "Khuyến nghị 720p+",
                  },
                  { icon: "💡", label: "Ánh sáng", value: "Đủ sáng, không mờ" },
                ].map(({ icon, label, value }) => (
                  <li
                    key={label}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="flex items-center gap-1 text-amber-800 dark:text-slate-300">
                      <span>{icon}</span> {label}
                    </span>

                    <span className="font-semibold text-amber-900 dark:text-slate-100">
                      {value}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          {/* Kết quả + tips */}
          <div className="space-y-3">
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
                Kết quả bạn nhận được
              </p>

              <div className="rounded-xl bg-gradient-to-br from-violet-600 to-purple-700 p-3 text-white">
                {[
                  "Tổng số khách phát hiện",
                  "Phân loại mới / quay lại",
                  "Độ chính xác AI",
                  "Khu vực & thời điểm xuất hiện",
                ].map((item) => (
                  <div
                    key={item}
                    className="flex items-center gap-1.5 py-0.5 text-sm text-violet-100"
                  >
                    <svg
                      className="h-3 w-3 shrink-0 text-violet-300"
                      viewBox="0 0 16 16"
                      fill="currentColor"
                    >
                      <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
                    </svg>

                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function VideosPage() {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [fileMeta, setFileMeta] = useState<VideoFileMeta | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result, setResult] = useState<VideoAnalysisResult | null>(null);
  const [error, setError] = useState<VideoError | null>(null);

  const [streamProgress, setStreamProgress] =
    useState<StreamProgressPayload | null>(null);
  const [allDetections, setAllDetections] =
    useState<StreamDetectionPayload[]>([]);
  const [currentDetections, setCurrentDetections] =
    useState<StreamDetectionPayload[]>([]);
  const [playbackState, setPlaybackState] =
    useState<PlaybackState>("waiting");

  // State theo dõi thời gian video
  const [videoTime, setVideoTime] = useState(0);

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [videoElement, setVideoElement] =
    useState<HTMLVideoElement | null>(null);
  const [videoObjectUrl, setVideoObjectUrl] = useState("");

  const disconnectStreamRef = useRef<(() => void) | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  const detectionTimelineRef = useRef<
    Map<number, StreamDetectionPayload[]>
  >(new Map());

  const latestAiTimestampRef = useRef(0);
  const latestAiFrameRef = useRef(0);
  const totalAiFramesRef = useRef(0);
  const streamStartedRef = useRef(false);
  const aiCompletedRef = useRef(false);
  const pendingResultRef = useRef<VideoAnalysisResult | null>(null);
  const lastOverlayUpdateMsRef = useRef(0);
  const lastNonEmptyOverlayRef = useRef<StreamDetectionPayload[]>([]);
  const lastNonEmptyOverlayAtRef = useRef(0);
  
  // Ref để throttle cập nhật UI video time
  const lastListUpdateMsRef = useRef(0);
  const firstAppearanceMapRef = useRef<Map<number, number>>(new Map());

  const setVideoNode = useCallback((node: HTMLVideoElement | null) => {
    videoRef.current = node;
    setVideoElement(node);
  }, []);

  useEffect(() => {
    if (!rawFile) {
      setVideoObjectUrl("");
      return;
    }

    const objectUrl = URL.createObjectURL(rawFile);
    setVideoObjectUrl(objectUrl);

    return () => URL.revokeObjectURL(objectUrl);
  }, [rawFile]);

  useEffect(() => {
    return () => {
      disconnectStreamRef.current?.();

      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, []);

  const resetStreaming = useCallback(() => {
    detectionTimelineRef.current.clear();
    latestAiTimestampRef.current = 0;
    latestAiFrameRef.current = 0;
    totalAiFramesRef.current = 0;
    streamStartedRef.current = false;
    aiCompletedRef.current = false;
    pendingResultRef.current = null;
    lastOverlayUpdateMsRef.current = 0;
    lastNonEmptyOverlayRef.current = [];
    lastNonEmptyOverlayAtRef.current = 0;
    
    lastListUpdateMsRef.current = 0;
    setVideoTime(0);

    firstAppearanceMapRef.current.clear();

    if (animationFrameRef.current !== null) {
      cancelAnimationFrame(animationFrameRef.current);
      animationFrameRef.current = null;
    }
  }, []);

  const handleFileSelected = useCallback(async (file: File) => {
    setStatus("validating");
    setError(null);
    setResult(null);

    const validationError = validateVideoFile(file);
    if (validationError) {
      setError({
        type:
          file.size > 50 * 1024 * 1024
            ? "file_too_large"
            : "invalid_format",
        message: validationError,
      });
      setStatus("error");
      return;
    }

    try {
      const metadata = await extractVideoMeta(file);
      setRawFile(file);
      setFileMeta(metadata);
      setStatus("ready");
    } catch {
      setError({
        type: "upload_failed",
        message: "Không thể đọc thông tin video.",
      });
      setStatus("error");
    }
  }, []);

  const startVideoWhenBuffered = useCallback(() => {
    const video = videoRef.current;
    if (!video || streamStartedRef.current) return;

    const leadSeconds = latestAiTimestampRef.current - video.currentTime;
    if (leadSeconds < STREAM_CONFIG.startBufferSeconds) {
      setPlaybackState("waiting");
      return;
    }

    streamStartedRef.current = true;
    video.pause();
    video.currentTime = 0;
    video.playbackRate = STREAM_CONFIG.normalPlaybackRate;
    setPlaybackState("playing");

    void video.play().catch(() => {
      streamStartedRef.current = false;
      setPlaybackState("waiting");
    });
  }, []);

  const interpolateBBox = useCallback((
    first: StreamDetectionPayload,
    second: StreamDetectionPayload,
    timeSeconds: number,
  ): StreamDetectionPayload => {
    const firstTime = first.source_timestamp_seconds;
    const secondTime = second.source_timestamp_seconds;
    const duration = secondTime - firstTime;

    if (
      duration <= 0 ||
      duration > STREAM_CONFIG.interpolationMaxGapSeconds
    ) {
      return first;
    }

    const linearRatio = Math.max(
      0,
      Math.min(1, (timeSeconds - firstTime) / duration),
    );

    // Linear interpolation bám người sát hơn smoothstep.
    const bbox = first.bbox.map(
      (value, index) =>
        value +
        (second.bbox[index] - value) * linearRatio,
    ) as [number, number, number, number];

    return {
      ...first,
      bbox,
      confidence:
        first.confidence +
        (second.confidence - first.confidence) * linearRatio,
    };
  }, []);

  const extrapolateBBox = useCallback((
    previous: StreamDetectionPayload,
    latest: StreamDetectionPayload,
    timeSeconds: number,
  ): StreamDetectionPayload => {
    const sampleDuration =
      latest.source_timestamp_seconds -
      previous.source_timestamp_seconds;

    const aheadSeconds =
      timeSeconds - latest.source_timestamp_seconds;

    if (
      sampleDuration <= 0 ||
      aheadSeconds <= 0 ||
      aheadSeconds > STREAM_CONFIG.extrapolationMaxSeconds
    ) {
      return latest;
    }

    const ratio = Math.min(
      STREAM_CONFIG.maximumExtrapolationRatio,
      aheadSeconds / sampleDuration,
    );

    const bbox = latest.bbox.map((value, index) => {
      const velocity =
        latest.bbox[index] - previous.bbox[index];

      return Math.max(
        0,
        Math.min(1, value + velocity * ratio),
      );
    }) as [number, number, number, number];

    return {
      ...latest,
      bbox,
    };
  }, []);

  const findDetectionsForTime = useCallback((
    videoTimeSeconds: number,
  ): StreamDetectionPayload[] => {
    const targetTime =
      videoTimeSeconds + STREAM_CONFIG.bboxLookAheadSeconds;

    const aiEdgeTime = latestAiTimestampRef.current;

    const visible: StreamDetectionPayload[] = [];

    for (const samples of detectionTimelineRef.current.values()) {
      if (samples.length === 0) continue;

      let left = 0;
      let right = samples.length - 1;
      let previousIndex = -1;

      while (left <= right) {
        const middle = Math.floor((left + right) / 2);

        if (
          samples[middle].source_timestamp_seconds <= targetTime
        ) {
          previousIndex = middle;
          left = middle + 1;
        } else {
          right = middle - 1;
        }
      }

      // Video có thể đang chạy chậm hơn AI và nằm trước detection đầu tiên.
      // Dùng mẫu tương lai gần nhất thay vì trả [] và làm mất bbox.
      if (previousIndex < 0) {
        const first = samples[0];
        const untilFirst =
          first.source_timestamp_seconds - targetTime;

        if (
          untilFirst >= 0 &&
          untilFirst <=
            STREAM_CONFIG.futureSampleToleranceSeconds
        ) {
          visible.push(first);
        }

        continue;
      }

      const previous = samples[previousIndex];
      const next = samples[previousIndex + 1];

      if (next) {
        const gap =
          next.source_timestamp_seconds -
          previous.source_timestamp_seconds;

        if (
          gap > 0 &&
          gap <= STREAM_CONFIG.interpolationMaxGapSeconds
        ) {
          visible.push(
            interpolateBBox(previous, next, targetTime),
          );
        } else {
          // Khoảng detection quá xa: giữ mẫu gần nhất, không xóa bbox.
          const distanceToPrevious = Math.abs(
            targetTime - previous.source_timestamp_seconds,
          );
          const distanceToNext = Math.abs(
            next.source_timestamp_seconds - targetTime,
          );

          visible.push(
            distanceToNext < distanceToPrevious
              ? next
              : previous,
          );
        }

        continue;
      }

      const age =
        targetTime - previous.source_timestamp_seconds;

      // Kiểm tra xem vị trí mẫu này có đang nằm sát với mốc cuối AI phân tích không
      const isTrackAtAiEdge = (aiEdgeTime - previous.source_timestamp_seconds) <= 1.5;

      if (
        previousIndex > 0 &&
        age > 0 &&
        age <= STREAM_CONFIG.extrapolationMaxSeconds
      ) {
        visible.push(
          extrapolateBBox(
            samples[previousIndex - 1],
            previous,
            targetTime,
          ),
        );
      } else if (
        age <= STREAM_CONFIG.holdLastDetectionSeconds ||
        isTrackAtAiEdge
      ) {
        visible.push(previous);
      }
    }

    return visible;
  }, [interpolateBBox, extrapolateBBox]);

  useEffect(() => {
    if (status !== "analyzing" || !fileMeta) return;

    const tick = () => {
      const video = videoRef.current;

      if (video) {
        const nowMs = performance.now();

        // Đồng bộ thời gian video để cập nhật UI danh sách/tiến độ
        if (nowMs - lastListUpdateMsRef.current >= 250) {
          lastListUpdateMsRef.current = nowMs;
          setVideoTime(video.currentTime);
        }

        if (
          nowMs - lastOverlayUpdateMsRef.current >=
          STREAM_CONFIG.overlayUpdateIntervalMs
        ) {
          lastOverlayUpdateMsRef.current = nowMs;
          const nextOverlay =
            findDetectionsForTime(video.currentTime);

          if (nextOverlay.length > 0) {
            lastNonEmptyOverlayRef.current = nextOverlay;
            lastNonEmptyOverlayAtRef.current = nowMs;
            setCurrentDetections(nextOverlay);
          } else {
            const emptyDurationMs =
              nowMs - lastNonEmptyOverlayAtRef.current;

            if (
              lastNonEmptyOverlayRef.current.length > 0 &&
              emptyDurationMs <=
                STREAM_CONFIG.overlayEmptyGraceSeconds * 1000
            ) {
              // Giữ overlay trước đó trong khoảng ngắn khi timestamp/event
              // bị thưa. Không để thay đổi playbackRate làm bbox biến mất.
              setCurrentDetections(
                lastNonEmptyOverlayRef.current,
              );
            } else {
              setCurrentDetections([]);
            }
          }
        }

        const aiLeadSeconds =
          latestAiTimestampRef.current - video.currentTime;

        if (
          !aiCompletedRef.current &&
          streamStartedRef.current &&
          !video.ended
        ) {
          let targetRate: number = STREAM_CONFIG.normalPlaybackRate;

          if (aiLeadSeconds <= STREAM_CONFIG.emergencyLeadSeconds) {
            targetRate = STREAM_CONFIG.emergencyPlaybackRate;
          } else if (aiLeadSeconds <= STREAM_CONFIG.slowLeadSeconds) {
            targetRate = STREAM_CONFIG.slowPlaybackRate;
          }

          if (Math.abs(video.playbackRate - targetRate) > 0.01) {
            video.playbackRate = targetRate;
          }

          // Sau khi bắt đầu tuyệt đối không pause vì buffer.
          if (video.paused) {
            void video.play().catch(() => undefined);
          }

          setPlaybackState("playing");
        }
      }

      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);

    return () => {
      if (animationFrameRef.current !== null) {
        cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
    };
  }, [status, fileMeta, findDetectionsForTime]);

  const finalizeAfterPlayback = useCallback(() => {
    const completedResult = pendingResultRef.current;
    if (!completedResult) return;

    setCurrentDetections([]);
    setResult(completedResult);
    setStatus("done");
  }, []);

  const handleUpload = useCallback(async () => {
    if (!rawFile || !fileMeta) return;

    disconnectStreamRef.current?.();
    resetStreaming();

    setStreamProgress(null);
    setAllDetections([]);
    setCurrentDetections([]);
    setPlaybackState("waiting");
    setUploadProgress(0);
    setStatus("uploading");

    let simulatedUpload = 0;

    const uploadTimer = window.setInterval(() => {
      simulatedUpload = Math.min(100, simulatedUpload + 10);
      setUploadProgress(simulatedUpload);

      if (simulatedUpload < 100) return;

      window.clearInterval(uploadTimer);
      setStatus("analyzing");

      disconnectStreamRef.current = connectJobStream(
        rawFile,
        fileMeta.duration,
        {
          onProgress: (progress) => {
            latestAiFrameRef.current = Math.max(
              latestAiFrameRef.current,
              progress.current_frame,
            );
            totalAiFramesRef.current = Math.max(
              totalAiFramesRef.current,
              progress.total_frames,
            );

            const progressTimestamp = Number(
              progress.source_timestamp_seconds,
            );

            if (
              Number.isFinite(progressTimestamp) &&
              progressTimestamp >= 0
            ) {
              latestAiTimestampRef.current = Math.max(
                latestAiTimestampRef.current,
                progressTimestamp,
              );
            }

            setStreamProgress(progress);
            startVideoWhenBuffered();
          },

          onDetection: (detection) => {
            const timestamp = Number(detection.source_timestamp_seconds);
            if (!Number.isFinite(timestamp) || timestamp < 0) return;

            latestAiTimestampRef.current = Math.max(
              latestAiTimestampRef.current,
              timestamp,
            );

            // Lưu lại giây đầu tiên người này xuất hiện để hiện UI ngay lập tức
            if (!firstAppearanceMapRef.current.has(detection.track_id)) {
              firstAppearanceMapRef.current.set(detection.track_id, timestamp);
            }

            const samples =
              detectionTimelineRef.current.get(detection.track_id) ?? [];

            const existingSampleIndex = samples.findIndex(
              (sample) =>
                Math.abs(sample.source_timestamp_seconds - timestamp) < 0.0001,
            );

            if (existingSampleIndex >= 0) {
              samples[existingSampleIndex] = {
                ...samples[existingSampleIndex],
                ...detection,
              };
            } else {
              samples.push(detection);
              samples.sort(
                (a, b) =>
                  a.source_timestamp_seconds - b.source_timestamp_seconds,
              );
            }

            if (samples.length > STREAM_CONFIG.maxSamplesPerTrack) {
              samples.splice(0, samples.length - STREAM_CONFIG.maxSamplesPerTrack);
            }

            detectionTimelineRef.current.set(detection.track_id, samples);

            setAllDetections((previous) => {
              // Trong giai đoạn online, track_id là khóa ổn định nhất.
              // P_id có thể bị đổi/gộp nên không dùng làm khóa tích lũy.
              const existingIndex = previous.findIndex(
                (item) => item.track_id === detection.track_id,
              );

              if (existingIndex < 0) {
                return [...previous, detection];
              }

              const existing = previous[existingIndex];
              const normalizedType = String(
                detection.customer_type ?? "",
              )
                .trim()
                .toLowerCase();

              const isIdentityUpdate =
                detection.person_profile_id != null ||
                normalizedType === "returning" ||
                normalizedType === "returning_customer";

              if (
                detection.frame_index < existing.frame_index &&
                !isIdentityUpdate
              ) {
                return previous;
              }

              const next = [...previous];
              next[existingIndex] = {
                ...existing,
                ...detection,
                current_video_avatar:
                  detection.current_video_avatar ||
                  existing.current_video_avatar ||
                  null,
              };

              return next;
            });
          },

          onGlobalIdentity: (identityPayload) => {
            const trackMapping =
              identityPayload.track_identity_mapping ?? {};

            // Gom tất cả raw track theo PersonProfile toàn cục.
            // Một người dù có nhiều track/P_id online chỉ còn đúng một card.
            setAllDetections((previous) => {
              const latestByTrack = new Map<number, StreamDetectionPayload>();

              for (const item of previous) {
                const current = latestByTrack.get(item.track_id);
                if (
                  !current ||
                  item.frame_index >= current.frame_index
                ) {
                  latestByTrack.set(item.track_id, item);
                }
              }

              const grouped = new Map<number, StreamDetectionPayload>();

              for (const [trackIdText, identity] of Object.entries(
                trackMapping,
              )) {
                const trackId = Number(trackIdText);
                if (!Number.isFinite(trackId)) continue;

                const previousDetection = latestByTrack.get(trackId);
                if (!previousDetection) continue;

                const updated: StreamDetectionPayload = {
                  ...previousDetection,
                  track_id: trackId,
                  session_profile_id:
                    identity.session_profile_id ??
                    previousDetection.session_profile_id,
                  person_profile_id: identity.person_profile_id,
                  anonymous_code: identity.anonymous_code,
                  customer_type: identity.customer_type,
                  total_visits: identity.total_visits,
                  customer_id:
                    identity.customer_id ??
                    previousDetection.customer_id ??
                    null,
                  customer_name:
                    identity.customer_name ??
                    previousDetection.customer_name ??
                    null,
                  current_video_avatar:
                    identity.current_video_avatar ??
                    previousDetection.current_video_avatar ??
                    null,
                };

                const existing = grouped.get(
                  identity.person_profile_id,
                );

                if (
                  !existing ||
                  updated.frame_index >= existing.frame_index
                ) {
                  grouped.set(identity.person_profile_id, updated);
                }
              }

              // Nếu backend chưa map được track nào thì giữ danh sách cũ.
              if (grouped.size === 0) {
                return previous;
              }

              return Array.from(grouped.values());
            });
          },

          onComplete: (analysisResult) => {
            aiCompletedRef.current = true;
            pendingResultRef.current = analysisResult;

            const video = videoRef.current;

            if (
              !video ||
              video.ended ||
              video.currentTime >= video.duration - 0.1
            ) {
              finalizeAfterPlayback();
              return;
            }

            video.playbackRate = STREAM_CONFIG.normalPlaybackRate;

            if (video.paused) {
              setPlaybackState("playing");
              void video.play().catch(() => undefined);
            }
          },

          onError: (message) => {
            setError({
              type: "analysis_failed",
              message,
            });
            setStatus("error");
          },
        },
      );
    }, 150);
  }, [
    rawFile,
    fileMeta,
    resetStreaming,
    startVideoWhenBuffered,
    finalizeAfterPlayback,
  ]);

  const handleReset = useCallback(() => {
    disconnectStreamRef.current?.();
    disconnectStreamRef.current = null;

    videoRef.current?.pause();
    resetStreaming();

    setStatus("idle");
    setFileMeta(null);
    setRawFile(null);
    setResult(null);
    setError(null);
    setUploadProgress(0);
    setStreamProgress(null);
    setAllDetections([]);
    setCurrentDetections([]);
    setPlaybackState("waiting");
  }, [resetStreaming]);

  /// 1. Chỉ đưa người vào danh sách khi video đã phát tới timestamp đầu tiên của họ
  const visibleDetections = useMemo(() => {
    return allDetections.filter((detection) => {
      // Lấy thời điểm xuất hiện đầu tiên của track này
      const firstAppearance = firstAppearanceMapRef.current.get(detection.track_id);
      
      // Nếu chưa có trong map (lỗi đồng bộ hiếm), fallback về timestamp hiện tại
      const appearTime = firstAppearance !== undefined 
        ? firstAppearance 
        : detection.source_timestamp_seconds;
        
      return appearTime <= videoTime;
    });
  }, [allDetections, videoTime]);

  // 2. Chỉnh % tiến trình phân tích và số frame dựa theo độ dài video thực tế
  const displayStreamProgress = useMemo(() => {
    if (!streamProgress || !fileMeta?.duration) return streamProgress;
    
    // Tính tỷ lệ % dựa trên thời gian video đã phát / tổng thời lượng
    const ratio = Math.min(1, Math.max(0, videoTime / fileMeta.duration));
    const progress_percent = Math.round(ratio * 100);
    
    // Đồng bộ số frame đã xử lý hiển thị tương ứng với video
    const current_frame = Math.round(ratio * streamProgress.total_frames);

    return {
      ...streamProgress,
      progress_percent,
      current_frame,
    };
  }, [streamProgress, videoTime, fileMeta]);

  return (
    <>
      <div className="mb-6">
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
          <span className="h-2 w-2 animate-ping rounded-full bg-indigo-500" />
          Nhận diện & Theo dõi Realtime
        </div>

        <h1 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100">
          Phân tích Video Thời gian thực
        </h1>
      </div>

      {status === "done" && result && (
        <VideoAnalysisResultComponent
          result={result}
          onReset={handleReset}
        />
      )}

      {status === "analyzing" && fileMeta && rawFile && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <div className="relative aspect-video overflow-hidden rounded-2xl border border-slate-200 bg-black shadow-lg">
              {videoObjectUrl && (
                <video
                  ref={setVideoNode}
                  src={videoObjectUrl}
                  className="h-full w-full object-contain"
                  muted
                  playsInline
                  preload="auto"
                  onLoadedMetadata={(event) => {
                    const video = event.currentTarget;
                    video.pause();
                    video.currentTime = 0;
                    video.playbackRate = STREAM_CONFIG.normalPlaybackRate;
                  }}
                  onEnded={finalizeAfterPlayback}
                />
              )}

              <StreamingOverlay
                detections={currentDetections}
                videoElement={videoElement}
              />

              {playbackState === "waiting" && (
                <div className="absolute inset-0 z-20 flex items-center justify-center bg-black/55">
                  <div className="text-center text-white">
                    <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-white/30 border-t-white" />
                    <p className="text-sm font-bold">
                      Đang chờ AI...
                    </p>
                    <p className="mt-1 text-xs text-white/75">
                      Video chỉ chờ một lần trước khi bắt đầu phát.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {displayStreamProgress && (
              <StreamingProgress progress={displayStreamProgress} />
            )}
          </div>

          <div>
            <LiveDetectionsList detections={visibleDetections} />
          </div>
        </div>
      )}

      {status !== "done" && status !== "analyzing" && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800">
            <div className="h-1 bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500" />

            <div className="p-6">
              {status === "uploading" ? (
                <UploadProgress progress={uploadProgress} />
              ) : status === "error" && error ? (
                <VideoUploadError
                  error={error}
                  onRetry={handleReset}
                />
              ) : fileMeta && rawFile ? (
                <div className="mx-auto max-w-2xl">
                  <VideoPreview
                    meta={fileMeta}
                    file={rawFile}
                    onRemove={handleReset}
                    disabled={status === "validating"}
                  />

                  <button
                    type="button"
                    onClick={handleUpload}
                    className="mt-5 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3.5 font-bold text-white"
                  >
                    <Monitor className="h-5 w-5" />
                    Bắt đầu phân tích AI trực tiếp
                  </button>
                </div>
              ) : (
                <VideoUploader
                  onFileSelected={handleFileSelected}
                  disabled={status === "validating"}
                />
              )}
            </div>
          </div>

          <GuideAccordion/>
        </div>
      )}
    </>
  );
}