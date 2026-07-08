"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { Info, ChevronDown, Upload, Monitor } from "lucide-react";
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
  type StreamProgressPayload,
  type StreamDetectionPayload,
} from "@/services/video_stream.service";
import type {
  UploadStatus,
  VideoFileMeta,
  VideoAnalysisResult,
  VideoError,
} from "@/types/video.type";

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

// ─── Loading progress (Dùng lúc tải tệp video lên) ───────────────────────────
function UploadProgress({
  progress,
}: {
  progress: number;
}) {
  return (
    <div className="flex flex-col items-center gap-8 py-16 animate-fade-in">
      <div className="relative flex h-28 w-28 items-center justify-center">
        <div className="absolute inset-0 animate-spin rounded-full border-[5px] border-transparent border-t-violet-500" />
        <div
          className="absolute inset-3 animate-spin rounded-full border-[4px] border-transparent border-t-purple-400"
          style={{ animationDirection: "reverse", animationDuration: "1.4s" }}
        />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600 shadow-xl shadow-violet-500/40">
          <Upload className="h-6 w-6 text-white" />
        </div>
      </div>

      <div className="text-center">
        <p className="text-lg font-bold text-slate-900 dark:text-slate-100">
          Đang tải video lên máy chủ...
        </p>
        <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
          Hệ thống đang chuẩn bị tệp cho luồng phân tích thời gian thực.
        </p>
      </div>

      <div className="w-full max-w-sm">
        <div className="mb-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
          <span>Tiến độ upload</span>
          <span className="font-bold text-violet-600 dark:text-violet-400">
            {progress}%
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

// ─── Main VideosPage Component ────────────────────────────────────────────────
export default function VideosPage() {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [fileMeta, setFileMeta] = useState<VideoFileMeta | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result, setResult] = useState<VideoAnalysisResult | null>(null);
  const [error, setError] = useState<VideoError | null>(null);

  // States quản lý dữ liệu luồng xử lý thời gian thực
  const [streamProgress, setStreamProgress] = useState<StreamProgressPayload | null>(null);
  const [allDetections, setAllDetections] = useState<StreamDetectionPayload[]>([]);
  const [currentDetections, setCurrentDetections] = useState<StreamDetectionPayload[]>([]);
  
  const videoRef = useRef<HTMLVideoElement>(null);
  const videoObjectUrl = useRef<string>("");
  const disconnectStream = useRef<(() => void) | null>(null);
  const lastFrameIndex = useRef<number>(-1);

  // Tạo và dọn dẹp Object URL từ file video nội bộ
  useEffect(() => {
    if (rawFile) {
      videoObjectUrl.current = URL.createObjectURL(rawFile);
    }
    return () => {
      if (videoObjectUrl.current) {
        URL.revokeObjectURL(videoObjectUrl.current);
        videoObjectUrl.current = "";
      }
    };
  }, [rawFile]);

  // Hủy kết nối stream khi đóng component
  useEffect(() => {
    return () => {
      if (disconnectStream.current) {
        disconnectStream.current();
      }
    };
  }, []);

  // Xử lý khi chọn file video mới
  const handleFileSelected = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setStatus("validating");

    const validationError = validateVideoFile(file);
    if (validationError) {
      setError({
        type: file.size > 50 * 1024 * 1024 ? "file_too_large" : "invalid_format",
        message: validationError,
      });
      setStatus("error");
      return;
    }

    try {
      const meta = await extractVideoMeta(file);
      setFileMeta(meta);
      setRawFile(file);
      setStatus("ready");
    } catch {
      setError({
        type: "upload_failed",
        message: "Không thể đọc thông tin video. Vui lòng thử file khác.",
      });
      setStatus("error");
    }
  }, []);

  // Bắt đầu upload và stream xử lý thời gian thực
  const handleUpload = useCallback(async () => {
    if (!fileMeta || !rawFile) return;
    
    try {
      setStatus("uploading");
      setUploadProgress(0);

      // Bước 1: Giả lập quá trình upload video ban đầu (chạy nhanh lên 100%)
      let progress = 0;
      const uploadInterval = setInterval(() => {
        progress += 10;
        setUploadProgress(progress);
        if (progress >= 100) {
          clearInterval(uploadInterval);
          
          // Bước 2: Chuyển sang trạng thái "analyzing" và khởi động luồng WebSocket/Simulator
          setStatus("analyzing");
          
          // Phát video cục bộ đồng thời
          setTimeout(() => {
            if (videoRef.current) {
              videoRef.current.currentTime = 0;
              videoRef.current.play().catch(() => {
                console.log("Auto-play bị chặn, chờ tương tác người dùng.");
              });
            }
          }, 100);

          // Tạo kết nối WebSocket / Simulator
          disconnectStream.current = connectJobStream(
            rawFile,
            fileMeta.duration,
            {
              onProgress: (payload) => {
                setStreamProgress(payload);
                
                // Đồng bộ mốc thời gian phát video với tiến độ AI đang phân tích
                if (videoRef.current && fileMeta.duration > 0) {
                  const targetTime = (payload.current_frame / payload.total_frames) * fileMeta.duration;
                  videoRef.current.currentTime = targetTime;
                }
              },
              onDetection: (det) => {
                // Thêm vào danh sách live feed tổng hợp (bảng bên phải)
                setAllDetections((prev) => {
                  const exists = prev.some(
                    (p) => p.anonymous_code === det.anonymous_code && p.frame_index === det.frame_index
                  );
                  return exists ? prev : [...prev, det];
                });

                // Cập nhật danh sách vẽ khung của khung hình hiện tại (canvas overlay)
                if (det.frame_index !== lastFrameIndex.current) {
                  lastFrameIndex.current = det.frame_index;
                  setCurrentDetections([det]);
                } else {
                  setCurrentDetections((prev) => [...prev, det]);
                }
              },
              onComplete: (analysisResult) => {
                setResult(analysisResult);
                setStatus("done");
              },
              onError: (errMsg) => {
                setError({
                  type: "analysis_failed",
                  message: errMsg,
                });
                setStatus("error");
              }
            }
          );
        }
      }, 150);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Có lỗi xảy ra";
      setError({
        type: "analysis_failed",
        message: msg,
      });
      setStatus("error");
    }
  }, [fileMeta, rawFile]);

  // Reset toàn bộ trạng thái để làm lại từ đầu
  const handleReset = useCallback(() => {
    if (disconnectStream.current) {
      disconnectStream.current();
      disconnectStream.current = null;
    }
    setStatus("idle");
    setFileMeta(null);
    setRawFile(null);
    setResult(null);
    setError(null);
    setUploadProgress(0);
    setStreamProgress(null);
    setAllDetections([]);
    setCurrentDetections([]);
    lastFrameIndex.current = -1;
  }, []);

  return (
    <>
      {/* ── Page Header (Tiêu đề trang) ── */}
      <div className="mb-6">
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-indigo-100 px-3 py-1 text-xs font-semibold text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400">
          <span className="h-2 w-2 rounded-full bg-indigo-500 animate-ping" />
          Nhận diện & Theo dõi Realtime
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
          Phân tích Video Thời gian thực
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-350">
          Trực quan hóa hộp nhận diện (Bounding Box) và danh sách khách hàng cập nhật trực tiếp (Live Feed).
        </p>
      </div>

      {/* ── 1. Kết quả phân tích (Done State) ── */}
      {status === "done" && result && (
        <VideoAnalysisResultComponent result={result} onReset={handleReset} />
      )}

      {/* ── 2. Đang phân tích Stream (Analyzing State) ── */}
      {status === "analyzing" && fileMeta && rawFile && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 animate-fade-in">
          {/* Cột trái: Trình phát video cục bộ và tiến độ xử lý */}
          <div className="lg:col-span-2 space-y-4">
            <div className="overflow-hidden rounded-2xl border border-slate-200 bg-black shadow-lg relative aspect-video dark:border-slate-800">
              <video
                ref={videoRef}
                src={videoObjectUrl.current}
                className="h-full w-full object-contain"
                muted
                playsInline
              />

              {/* Bounding Box Canvas Overlay vẽ đè lên trình phát */}
              <StreamingOverlay
                detections={currentDetections}
                videoElement={videoRef.current}
              />
            </div>

            {/* Thanh tiến độ FPS/ETA */}
            {streamProgress && <StreamingProgress progress={streamProgress} />}
          </div>

          {/* Cột phải: Feed nhận diện khách hàng nhảy trực tiếp */}
          <div className="lg:col-span-1">
            <LiveDetectionsList detections={allDetections} />
          </div>
        </div>
      )}

      {/* ── 3. Trạng thái tải lên/Chọn file (Idle/Uploading/Ready/Error) ── */}
      {status !== "done" && status !== "analyzing" && (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
            <div className="h-1 bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500" />
            <div className="p-6">
              {status === "uploading" ? (
                <UploadProgress progress={uploadProgress} />
              ) : status === "error" && error ? (
                <VideoUploadError error={error} onRetry={handleReset} />
              ) : fileMeta ? (
                <div className="mx-auto max-w-2xl">
                  <VideoPreview
                    meta={fileMeta}
                    file={rawFile!}
                    onRemove={handleReset}
                    disabled={status === "validating"}
                  />
                  <button
                    onClick={handleUpload}
                    className="mt-5 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 px-5 py-3.5 text-base font-bold text-white shadow-lg shadow-indigo-500/25 transition hover:from-indigo-700 hover:to-violet-700 active:scale-[0.98]"
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

          <GuideAccordion />
        </div>
      )}
    </>
  );
}
