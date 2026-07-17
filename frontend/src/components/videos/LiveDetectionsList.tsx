"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import {
  Users,
  User,
  ShieldCheck,
  UserRoundCheck,
} from "lucide-react";

import type { StreamDetectionPayload } from "@/services/video_stream.service";

interface LiveDetectionsListProps {
  detections: StreamDetectionPayload[];
}

function getDetectionIdentityKey(
  detection: StreamDetectionPayload,
): string {
  // Giữ key ổn định từ lúc live P_000X đến khi có global identity.
  // Nếu ưu tiên person_profile_id, cùng một người sẽ bị tách thành 2 dòng.
  if (detection.session_profile_id) {
    return `session-${detection.session_profile_id}`;
  }

  if (detection.track_id != null) {
    return `track-${detection.track_id}`;
  }

  if (detection.person_profile_id != null) {
    return `global-${detection.person_profile_id}`;
  }

  return `anonymous-${detection.anonymous_code}`;
}

function getCurrentAvatar(
  detection: StreamDetectionPayload,
): string | null {
  return (
    detection.current_video_avatar ||
    detection.customer_avatar ||
    detection.identified_customer_avatar ||
    detection.stored_profile_avatar ||
    null
  );
}

export default function LiveDetectionsList({
  detections,
}: LiveDetectionsListProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  const sortedDetections = useMemo(() => {
    const uniqueDetections = new Map<
      string,
      StreamDetectionPayload
    >();

    for (const detection of detections) {
      const key = getDetectionIdentityKey(detection);
      const existing = uniqueDetections.get(key);

      if (
        !existing ||
        detection.frame_index >= existing.frame_index
      ) {
        uniqueDetections.set(key, detection);
      }
    }

    return Array.from(uniqueDetections.values()).sort(
      (a, b) => b.frame_index - a.frame_index,
    );
  }, [detections]);

  useEffect(() => {
    containerRef.current?.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }, [sortedDetections.length]);

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-2xs dark:border-slate-800 dark:bg-slate-900">
      <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4 dark:border-slate-800">
        <h3 className="flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-slate-800 dark:text-slate-200">
          <Users className="h-4.5 w-4.5 text-indigo-500" />
          Khách hàng nhận diện ({sortedDetections.length})
        </h3>

        {sortedDetections.length > 0 && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-extrabold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 animate-ping rounded-full bg-emerald-500" />
            Live Feed
          </span>
        )}
      </div>

      <div
        ref={containerRef}
        className="max-h-[460px] min-h-[300px] flex-1 space-y-2.5 overflow-y-auto p-4"
      >
        {sortedDetections.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center text-slate-400 dark:text-slate-500">
            <User className="mb-2 h-10 w-10 animate-bounce stroke-1" />

            <p className="text-xs font-semibold">
              Đang chờ quét video...
            </p>

            <p className="mt-0.5 text-[10px] opacity-75">
              Khách hàng sẽ xuất hiện ngay khi AI nhận dạng
            </p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {sortedDetections.map((detection) => {
              const key = getDetectionIdentityKey(detection);
              const avatar = getCurrentAvatar(detection);

              const isIdentified = Boolean(
                detection.customer_id,
              );

              const normalizedCustomerType = String(
                detection.customer_type ?? "",
              ).trim().toLowerCase();

              const isReturning =
                normalizedCustomerType === "returning" ||
                normalizedCustomerType === "returning_customer";

              const confidence = Number.isFinite(
                detection.confidence,
              )
                ? Math.max(
                    0,
                    Math.min(1, detection.confidence),
                  )
                : 0;

              const displayCode =
                detection.anonymous_code ||
                detection.session_profile_id ||
                `Track ${detection.track_id}`;

              return (
                <div
                  key={key}
                  className="animate-fade-in flex items-center justify-between rounded-xl border border-slate-50 bg-white p-3 shadow-2xs transition duration-200 hover:border-slate-200 dark:border-slate-800 dark:bg-slate-900/60 dark:hover:border-slate-700"
                >
                  <div className="flex min-w-0 items-center gap-3">
                    <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border border-slate-100 bg-slate-50 dark:border-slate-800 dark:bg-slate-800">
                      {avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={avatar}
                          alt={`Avatar ${displayCode}`}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <User className="h-5 w-5 text-slate-400 dark:text-slate-500" />
                      )}
                    </div>

                    <div className="min-w-0">
                      {isIdentified &&
                      detection.customer_id != null ? (
                        <Link
                          href={`/customers/${detection.customer_id}`}
                          className="block truncate text-xs font-bold text-indigo-600 transition hover:text-indigo-800 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300"
                          title="Xem thông tin chi tiết khách hàng"
                        >
                          {detection.customer_name ||
                            displayCode}
                        </Link>
                      ) : (
                        <span className="block truncate text-xs font-bold text-slate-800 dark:text-slate-200">
                          {displayCode}
                        </span>
                      )}

                      <span className="mt-0.5 block font-mono text-[9px] uppercase text-slate-400 dark:text-slate-500">
                        {isIdentified
                          ? `Đã định danh: ${displayCode}`
                          : isReturning
                            ? `Khách quay lại · ${
                                detection.total_visits ?? 2
                              } lượt`
                            : "Khách ẩn danh mới"}
                      </span>
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-col items-end gap-1 text-right">
                    {isIdentified ? (
                      <span className="inline-flex items-center gap-0.5 rounded border border-indigo-100/55 bg-indigo-50 px-2 py-0.5 text-[9px] font-bold text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400">
                        <ShieldCheck className="h-3 w-3" />
                        Identified
                      </span>
                    ) : isReturning ? (
                      <span className="inline-flex items-center gap-0.5 rounded border border-emerald-100 bg-emerald-50 px-2 py-0.5 text-[9px] font-bold text-emerald-600 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-400">
                        <UserRoundCheck className="h-3 w-3" />
                        Returning
                      </span>
                    ) : (
                      <span className="inline-flex items-center rounded bg-slate-100 px-2 py-0.5 text-[9px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                        New ANON
                      </span>
                    )}

                    <span className="font-mono text-[10px] text-slate-500 dark:text-slate-400">
                      Conf: {Math.round(confidence * 100)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}