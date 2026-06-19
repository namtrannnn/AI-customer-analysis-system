"use client";

import { useRef, useState, useCallback } from "react";
import { Video } from "lucide-react";
import { VIDEO_CONSTRAINTS } from "@/types/video.type";

interface VideoUploaderProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export default function VideoUploader({ onFileSelected, disabled }: VideoUploaderProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFile = useCallback(
    (file: File) => {
      if (disabled) return;
      onFileSelected(file);
    },
    [disabled, onFileSelected]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const onDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setDragOver(true);
  };

  const onDragLeave = () => setDragOver(false);

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`group relative flex cursor-pointer flex-col items-center justify-center overflow-hidden rounded-2xl border-2 border-dashed px-8 py-16 text-center transition-all duration-200 select-none
        ${disabled ? "cursor-not-allowed opacity-50" : ""}
        ${
          dragOver
            ? "border-violet-500 bg-violet-50 dark:bg-violet-900/20"
            : "border-slate-200 bg-slate-50/50 hover:border-violet-400 hover:bg-violet-50/40 dark:border-slate-700 dark:bg-slate-800/40 dark:hover:border-violet-500 dark:hover:bg-violet-900/10"
        }
      `}
    >
      {/* Background glow on drag */}
      {dragOver && (
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(139,92,246,0.15),transparent_70%)]" />
      )}

      {/* Icon */}
      <div
        className={`relative mb-5 flex h-20 w-20 items-center justify-center rounded-2xl transition-transform duration-200 ${
          dragOver ? "scale-110" : "group-hover:scale-105"
        } bg-gradient-to-br from-violet-500 to-purple-600 shadow-lg shadow-violet-500/30`}
      >
        <Video className="h-9 w-9 text-white" />
        {/* Pulse ring */}
        <div className="absolute inset-0 animate-ping rounded-2xl bg-violet-400/20" />
      </div>

      {/* Text */}
      <p className={`mb-1 text-lg font-bold transition-colors ${dragOver ? "text-violet-600 dark:text-violet-400" : "text-slate-700 dark:text-slate-200"}`}>
        {dragOver ? "Thả file vào đây" : "Kéo & thả video vào đây"}
      </p>
      <p className="mb-5 text-sm text-slate-500 dark:text-slate-400">
        hoặc <span className="font-semibold text-violet-600 dark:text-violet-400">click để chọn file</span>
      </p>

      {/* Supported formats */}
      <div className="flex flex-wrap items-center justify-center gap-2">
        {VIDEO_CONSTRAINTS.acceptedExtensions.map((ext) => (
          <span
            key={ext}
            className="rounded-lg bg-white px-2.5 py-1 text-xs font-semibold text-slate-600 shadow-sm ring-1 ring-slate-200 dark:bg-slate-700 dark:text-slate-300 dark:ring-slate-600"
          >
            {ext.toUpperCase()}
          </span>
        ))}
        <span className="text-xs text-slate-400 dark:text-slate-500">
          · Tối đa {VIDEO_CONSTRAINTS.maxSizeMB}MB
        </span>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={VIDEO_CONSTRAINTS.acceptedExtensions.join(",")}
        onChange={onInputChange}
        className="hidden"
        disabled={disabled}
      />
    </div>
  );
}
