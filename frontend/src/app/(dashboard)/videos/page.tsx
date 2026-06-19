"use client";

import { useState, useCallback } from "react";
import VideoUploader from "@/components/videos/VideoUploader";
import VideoPreview from "@/components/videos/VideoPreview";
import VideoAnalysisResultComponent from "@/components/videos/VideoAnalysisResult";
import VideoUploadError from "@/components/videos/VideoUploadError";
import {
  validateVideoFile,
  extractVideoMeta,
  uploadVideo,
  analyzeVideo,
} from "@/services/video.service";
import type {
  UploadStatus,
  VideoFileMeta,
  VideoAnalysisResult,
  VideoError,
} from "@/types/video.type";

// ─── Guide Drawer ─────────────────────────────────────────────────────────────
function GuideDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
          onClick={onClose}
        />
      )}

      {/* Drawer panel */}
      <div
        className={`fixed right-0 top-0 z-50 flex h-full w-full max-w-sm flex-col bg-white shadow-2xl transition-transform duration-300 ease-in-out dark:bg-slate-900 ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-100 px-6 py-4 dark:border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900/40">
              <svg className="h-4 w-4 text-violet-600 dark:text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-slate-100">Hướng dẫn sử dụng</h2>
          </div>
          <button
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-800 dark:hover:text-slate-300"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">

          {/* How it works */}
          <section>
            <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Cách hoạt động
            </h3>
            <div className="space-y-3">
              {[
                { step: "1", text: "Upload video từ camera cửa hàng", color: "from-violet-500 to-purple-600", desc: "Hỗ trợ MP4, AVI, MOV, MKV tối đa 500MB" },
                { step: "2", text: "AI phân tích từng frame", color: "from-blue-500 to-indigo-600", desc: "Nhận diện khuôn mặt và theo dõi chuyển động" },
                { step: "3", text: "Phân loại khách hàng", color: "from-emerald-500 to-teal-600", desc: "Xác định khách mới, khách quay lại, VIP" },
                { step: "4", text: "Xuất báo cáo thống kê", color: "from-amber-500 to-orange-500", desc: "Confidence score, khu vực, thời điểm xuất hiện" },
              ].map(({ step, text, color, desc }) => (
                <div key={step} className="flex items-start gap-3">
                  <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br ${color} text-sm font-bold text-white shadow-sm`}>
                    {step}
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800 dark:text-slate-200">{text}</p>
                    <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Requirements */}
          <section>
            <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Yêu cầu video
            </h3>
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 dark:border-amber-800/30 dark:bg-amber-900/10">
              <ul className="space-y-2.5">
                {[
                  { icon: "📁", label: "Định dạng", value: "MP4, AVI, MOV, MKV" },
                  { icon: "📦", label: "Kích thước", value: "Tối đa 500MB" },
                  { icon: "⏱", label: "Thời lượng", value: "Tối thiểu 3 giây" },
                  { icon: "🖥", label: "Độ phân giải", value: "Khuyến nghị 720p+" },
                  { icon: "💡", label: "Ánh sáng", value: "Đủ sáng, không mờ" },
                ].map(({ icon, label, value }) => (
                  <li key={label} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-amber-800 dark:text-amber-300">
                      <span>{icon}</span>
                      {label}
                    </span>
                    <span className="font-semibold text-amber-900 dark:text-amber-200">{value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>

          {/* What you'll get */}
          <section>
            <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Kết quả phân tích
            </h3>
            <div className="rounded-2xl bg-gradient-to-br from-violet-600 to-purple-700 p-4 text-white">
              <div className="space-y-2">
                {[
                  "Tổng số khách phát hiện",
                  "Phân loại mới / quay lại",
                  "Độ chính xác AI (confidence)",
                  "Khu vực xuất hiện",
                  "Thời điểm phát hiện trong video",
                  "Số lần xuất hiện mỗi khách",
                ].map((item) => (
                  <div key={item} className="flex items-center gap-2 text-xs text-violet-100">
                    <svg className="h-3.5 w-3.5 shrink-0 text-violet-300" viewBox="0 0 16 16" fill="currentColor">
                      <path d="M13.78 4.22a.75.75 0 010 1.06l-7.25 7.25a.75.75 0 01-1.06 0L2.22 9.28a.75.75 0 011.06-1.06L6 10.94l6.72-6.72a.75.75 0 011.06 0z" />
                    </svg>
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Tips */}
          <section>
            <h3 className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400 dark:text-slate-500">
              Mẹo để kết quả tốt hơn
            </h3>
            <div className="space-y-2">
              {[
                "Dùng video từ camera cố định, không rung",
                "Đảm bảo khuôn mặt nhìn thẳng vào camera",
                "Ánh sáng đồng đều, tránh ngược sáng",
                "Video không quá mờ hoặc nén quá nhiều",
              ].map((tip) => (
                <div key={tip} className="flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                  <span className="mt-0.5 text-blue-500">✦</span>
                  {tip}
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Footer */}
        <div className="border-t border-slate-100 px-6 py-4 dark:border-slate-800">
          <button
            onClick={onClose}
            className="w-full rounded-xl bg-slate-100 px-4 py-2.5 text-sm font-semibold text-slate-700 transition hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700"
          >
            Đóng
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Loading progress ─────────────────────────────────────────────────────────
function UploadProgress({ status, progress }: { status: UploadStatus; progress: number }) {
  const steps = [
    { key: "uploading",  label: "Đang tải lên"      },
    { key: "analyzing",  label: "AI phân tích"       },
  ];

  return (
    <div className="flex flex-col items-center gap-8 py-16">
      {/* Spinner */}
      <div className="relative flex h-28 w-28 items-center justify-center">
        <div className="absolute inset-0 animate-spin rounded-full border-[5px] border-transparent border-t-violet-500" />
        <div
          className="absolute inset-3 animate-spin rounded-full border-[4px] border-transparent border-t-purple-400"
          style={{ animationDirection: "reverse", animationDuration: "1.4s" }}
        />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-violet-500 to-purple-600 shadow-xl shadow-violet-500/40">
          {status === "uploading" ? (
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
            </svg>
          ) : (
            <svg className="h-6 w-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          )}
        </div>
      </div>

      {/* Text */}
      <div className="text-center">
        <p className="text-lg font-bold text-slate-900 dark:text-slate-100">
          {status === "uploading" ? "Đang tải video lên..." : "AI đang phân tích video..."}
        </p>
        <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
          {status === "uploading"
            ? "Vui lòng không đóng trang này"
            : "Đang nhận diện khuôn mặt và phân loại khách hàng"}
        </p>
      </div>

      {/* Progress bar */}
      {status === "uploading" && (
        <div className="w-full max-w-sm">
          <div className="mb-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Tiến độ upload</span>
            <span className="font-bold text-violet-600 dark:text-violet-400">{progress}%</span>
          </div>
          <div className="h-2.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-700">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-500 to-purple-500 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Steps */}
      <div className="flex items-center gap-4">
        {steps.map((step, idx) => {
          const isDone = step.key === "uploading" && status === "analyzing";
          const isActive = step.key === status;
          return (
            <div key={step.key} className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold transition-all ${
                  isDone ? "bg-emerald-500 text-white" :
                  isActive ? "bg-violet-600 text-white shadow-lg shadow-violet-500/30" :
                  "bg-slate-200 text-slate-500 dark:bg-slate-700"
                }`}>
                  {isDone ? "✓" : idx + 1}
                </div>
                <span className={`text-xs font-medium ${
                  isActive ? "text-violet-600 dark:text-violet-400" :
                  isDone ? "text-emerald-600 dark:text-emerald-400" :
                  "text-slate-400"
                }`}>
                  {step.label}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <div className={`h-px w-10 ${isDone ? "bg-emerald-300" : "bg-slate-200 dark:bg-slate-700"}`} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────
export default function VideosPage() {
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [fileMeta, setFileMeta] = useState<VideoFileMeta | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result, setResult] = useState<VideoAnalysisResult | null>(null);
  const [error, setError] = useState<VideoError | null>(null);
  const [guideOpen, setGuideOpen] = useState(false);

  const isProcessing = status === "uploading" || status === "analyzing";

  const handleFileSelected = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setStatus("validating");

    const validationError = validateVideoFile(file);
    if (validationError) {
      setError({
        type: file.size > 500 * 1024 * 1024 ? "file_too_large" : "invalid_format",
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
      setError({ type: "upload_failed", message: "Không thể đọc thông tin video. Vui lòng thử file khác." });
      setStatus("error");
    }
  }, []);

  const handleUpload = useCallback(async () => {
    if (!fileMeta) return;
    try {
      setStatus("uploading");
      setUploadProgress(0);
      const { video_id } = await uploadVideo(
        new File([], fileMeta.name, { type: fileMeta.type }),
        setUploadProgress
      );
      setStatus("analyzing");
      const analysisResult = await analyzeVideo(video_id, fileMeta);
      setResult(analysisResult);
      setStatus("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Có lỗi xảy ra";
      setError({
        type: msg === "NO_PERSON_FOUND" ? "no_person_found" : "analysis_failed",
        message: msg === "NO_PERSON_FOUND"
          ? "Không phát hiện người trong video. Hãy thử video có người xuất hiện rõ ràng."
          : msg,
      });
      setStatus("error");
    }
  }, [fileMeta]);

  const handleReset = useCallback(() => {
    setStatus("idle");
    setFileMeta(null);
    setRawFile(null);
    setResult(null);
    setError(null);
    setUploadProgress(0);
  }, []);

  return (
    <>
      {/* ── Page header ── */}
      <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 dark:bg-violet-900/30 dark:text-violet-400">
            <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 8 8">
              <circle cx="4" cy="4" r="4" />
            </svg>
            Phân tích AI
          </div>
          <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
            Upload & Phân tích Video
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Tải lên video camera để AI nhận diện và phân loại khách hàng tự động.
          </p>
        </div>

        {/* Guide button */}
        <button
          onClick={() => setGuideOpen(true)}
          className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:hover:border-violet-600 dark:hover:bg-violet-900/20 dark:hover:text-violet-400"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Hướng dẫn
        </button>
      </div>

      {/* ── Result view ── */}
      {status === "done" && result && (
        <VideoAnalysisResultComponent result={result} onReset={handleReset} />
      )}

      {/* ── Upload / Processing view ── */}
      {status !== "done" && (
        <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
          {/* Top accent gradient */}
          <div className="h-1 bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500" />

          <div className="p-6">
            {isProcessing ? (
              <UploadProgress status={status} progress={uploadProgress} />
            ) : status === "error" && error ? (
              <VideoUploadError error={error} onRetry={handleReset} />
            ) : fileMeta ? (
              <div className="mx-auto max-w-2xl">
                <VideoPreview meta={fileMeta} file={rawFile!} onRemove={handleReset} disabled={isProcessing} />
                <button
                  onClick={handleUpload}
                  className="mt-5 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-3.5 text-base font-bold text-white shadow-lg shadow-violet-500/25 transition hover:from-violet-700 hover:to-purple-700 hover:shadow-xl hover:shadow-violet-500/30 active:scale-[0.98]"
                >
                  <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  Bắt đầu phân tích AI
                </button>
              </div>
            ) : (
              <VideoUploader onFileSelected={handleFileSelected} disabled={isProcessing} />
            )}
          </div>
        </div>
      )}

      {/* ── Guide drawer ── */}
      <GuideDrawer open={guideOpen} onClose={() => setGuideOpen(false)} />
    </>
  );
}
