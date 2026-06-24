"use client";

import { useCallback, useState } from "react";
import { Camera, ChevronDown, Info, Monitor, Upload } from "lucide-react";

import LiveCameraPanel from "@/components/videos/LiveCameraPanel";
import VideoAnalysisResultComponent from "@/components/videos/VideoAnalysisResult";
import VideoPreview from "@/components/videos/VideoPreview";
import VideoUploadError from "@/components/videos/VideoUploadError";
import VideoUploader from "@/components/videos/VideoUploader";
import {
  extractVideoMeta,
  uploadAndAnalyzeVideo,
  validateVideoFile,
} from "@/services/video.service";
import type {
  UploadStatus,
  VideoAnalysisResult,
  VideoError,
  VideoFileMeta,
} from "@/types/video.type";

type VideoMode = "upload" | "live";

function GuideAccordion() {
  const [open, setOpen] = useState(false);

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-800">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between px-5 py-4 text-left transition hover:bg-slate-50 dark:hover:bg-slate-700/50"
      >
        <div className="flex items-center gap-2.5">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-100 dark:bg-violet-900/40">
            <Info className="h-4 w-4 text-violet-600 dark:text-violet-400" />
          </div>

          <span className="text-base font-semibold text-slate-700 dark:text-slate-200">
            Huong dan su dung
          </span>

          <span className="hidden rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600 sm:inline dark:bg-slate-700 dark:text-slate-200">
            Cach hoat dong · Yeu cau · Ket qua
          </span>
        </div>

        <ChevronDown
          className={`h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      <div
        className={`overflow-hidden transition-all duration-300 ease-in-out ${
          open ? "max-h-[600px] opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <div className="grid gap-5 border-t border-slate-100 px-5 py-5 dark:border-slate-700 sm:grid-cols-3">
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
              Cach hoat dong
            </p>

            <div className="space-y-2.5">
              {[
                {
                  step: "1",
                  text: "Upload video tu camera",
                  desc: "MP4, AVI, MOV, MKV · max 50MB",
                  color: "from-violet-500 to-purple-600",
                },
                {
                  step: "2",
                  text: "AI phan tich tung frame",
                  desc: "Nhan dien va theo doi khach hang",
                  color: "from-blue-500 to-indigo-600",
                },
                {
                  step: "3",
                  text: "Thong ke va phan loai",
                  desc: "Moi / quay lai / ROI event",
                  color: "from-emerald-500 to-teal-600",
                },
                {
                  step: "4",
                  text: "Nhan bao cao ket qua",
                  desc: "Count, track, khu vuc, thoi diem",
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
                    <p className="text-xs text-slate-400 dark:text-slate-300">
                      {desc}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
              Yeu cau video
            </p>

            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 dark:border-slate-600 dark:bg-slate-700/70">
              <ul className="space-y-2">
                {[
                  {
                    icon: "FILE",
                    label: "Dinh dang",
                    value: "MP4, AVI, MOV, MKV",
                  },
                  { icon: "SIZE", label: "Kich thuoc", value: "Toi da 50MB" },
                  { icon: "TIME", label: "Thoi luong", value: "Toi thieu 3 giay" },
                  {
                    icon: "RES",
                    label: "Phan giai",
                    value: "Khuyen nghi 720p+",
                  },
                  { icon: "LIGHT", label: "Anh sang", value: "Du sang, khong mo" },
                ].map(({ icon, label, value }) => (
                  <li
                    key={label}
                    className="flex items-center justify-between gap-3 text-sm"
                  >
                    <span className="flex items-center gap-2 text-amber-800 dark:text-slate-300">
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-900 dark:bg-slate-600 dark:text-slate-100">
                        {icon}
                      </span>
                      {label}
                    </span>

                    <span className="font-semibold text-amber-900 dark:text-slate-100">
                      {value}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <div className="space-y-3">
            <div>
              <p className="mb-2 text-xs font-bold uppercase tracking-widest text-slate-600 dark:text-slate-200">
                Ket qua nhan duoc
              </p>

              <div className="rounded-xl bg-gradient-to-br from-violet-600 to-purple-700 p-3 text-white">
                {[
                  "Tong so khach phat hien",
                  "Count theo ROI va movement",
                  "Track dang hoat dong",
                  "Debug frame khi bat inspection",
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

function UploadProgress({
  status,
  progress,
}: {
  status: UploadStatus;
  progress: number;
}) {
  return (
    <div className="flex flex-col items-center gap-8 py-16">
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
          Dang upload va phan tich video...
        </p>
        <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
          Server dang xu ly video, vui long khong dong trang.
        </p>
      </div>

      {status === "uploading" && (
        <div className="w-full max-w-sm">
          <div className="mb-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
            <span>Tien do upload</span>
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
      )}

      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-full bg-violet-600 text-xs font-bold text-white shadow-lg shadow-violet-500/30">
          1
        </div>
        <span className="text-xs font-medium text-violet-600 dark:text-violet-400">
          Upload va phan tich AI
        </span>
      </div>
    </div>
  );
}

export default function VideosPage() {
  const [mode, setMode] = useState<VideoMode>("upload");
  const [status, setStatus] = useState<UploadStatus>("idle");
  const [fileMeta, setFileMeta] = useState<VideoFileMeta | null>(null);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [result, setResult] = useState<VideoAnalysisResult | null>(null);
  const [error, setError] = useState<VideoError | null>(null);

  const isProcessing = status === "uploading" || status === "analyzing";

  const handleFileSelected = useCallback(async (file: File) => {
    setError(null);
    setResult(null);
    setStatus("validating");

    const validationError = validateVideoFile(file);
    if (validationError) {
      setError({
        type:
          file.size > 50 * 1024 * 1024 ? "file_too_large" : "invalid_format",
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
        message: "Khong the doc thong tin video. Vui long thu file khac.",
      });
      setStatus("error");
    }
  }, []);

  const handleUpload = useCallback(async () => {
    if (!fileMeta || !rawFile) return;

    try {
      setStatus("uploading");
      setUploadProgress(0);

      const analysisResult = await uploadAndAnalyzeVideo(
        rawFile,
        setUploadProgress,
      );

      setResult(analysisResult);
      setStatus("done");
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Co loi xay ra";
      const type =
        message === "FILE_TOO_LARGE"
          ? "file_too_large"
          : message === "INVALID_FORMAT"
            ? "invalid_format"
            : message === "NO_PERSON_FOUND"
              ? "no_person_found"
              : "analysis_failed";

      setError({
        type,
        message:
          type === "file_too_large"
            ? "File qua lon. Backend chi nhan toi da 50MB."
            : type === "invalid_format"
              ? "Dinh dang khong hop le."
              : message,
      });
      setStatus("error");
    }
  }, [fileMeta, rawFile]);

  const handleReset = useCallback(() => {
    setStatus("idle");
    setFileMeta(null);
    setRawFile(null);
    setResult(null);
    setError(null);
    setUploadProgress(0);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <div className="mb-2 inline-flex items-center gap-1.5 rounded-full bg-violet-100 px-3 py-1 text-xs font-semibold text-violet-700 dark:bg-violet-900/30 dark:text-violet-400">
          <svg className="h-3 w-3" fill="currentColor" viewBox="0 0 8 8">
            <circle cx="4" cy="4" r="4" />
          </svg>
          Phan tich AI
        </div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-slate-100">
          Video Analytics
        </h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-300">
          Dung chung mot man hinh cho demo upload video va xu ly realtime tu
          webcam browser.
        </p>
      </div>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setMode("upload")}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            mode === "upload"
              ? "bg-violet-600 text-white shadow-lg shadow-violet-500/25"
              : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700 dark:hover:bg-slate-700/70"
          }`}
        >
          <Monitor className="h-4 w-4" />
          Upload Video
        </button>

        <button
          type="button"
          onClick={() => setMode("live")}
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold transition ${
            mode === "live"
              ? "bg-blue-600 text-white shadow-lg shadow-blue-500/25"
              : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50 dark:bg-slate-800 dark:text-slate-300 dark:ring-slate-700 dark:hover:bg-slate-700/70"
          }`}
        >
          <Camera className="h-4 w-4" />
          Live Camera
        </button>
      </div>

      {mode === "live" ? (
        <LiveCameraPanel />
      ) : status === "done" && result ? (
        <VideoAnalysisResultComponent result={result} onReset={handleReset} />
      ) : (
        <div className="space-y-4">
          <div className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 dark:bg-slate-800 dark:ring-slate-700/60">
            <div className="h-1 bg-gradient-to-r from-violet-500 via-purple-500 to-indigo-500" />
            <div className="p-6">
              {isProcessing ? (
                <UploadProgress status={status} progress={uploadProgress} />
              ) : status === "error" && error ? (
                <VideoUploadError error={error} onRetry={handleReset} />
              ) : fileMeta && rawFile ? (
                <div className="mx-auto max-w-2xl">
                  <VideoPreview
                    meta={fileMeta}
                    file={rawFile}
                    onRemove={handleReset}
                    disabled={isProcessing}
                  />
                  <button
                    type="button"
                    onClick={handleUpload}
                    className="mt-5 flex w-full items-center justify-center gap-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-3.5 text-base font-bold text-white shadow-lg shadow-violet-500/25 transition hover:from-violet-700 hover:to-purple-700 active:scale-[0.98]"
                  >
                    <Monitor className="h-5 w-5" />
                    Bat dau phan tich AI
                  </button>
                </div>
              ) : (
                <VideoUploader
                  onFileSelected={handleFileSelected}
                  disabled={isProcessing}
                />
              )}
            </div>
          </div>

          {!isProcessing && <GuideAccordion />}
        </div>
      )}
    </div>
  );
}
