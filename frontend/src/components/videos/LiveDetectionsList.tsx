"use client";

import { useEffect, useMemo, useRef } from "react";
import Link from "next/link";
import {
  Users,
  User,
  ShieldCheck,
  UserRoundCheck,
  LoaderCircle,
  UserPlus,
} from "lucide-react";

import type { StreamDetectionPayload } from "@/services/video_stream.service";

interface LiveDetectionsListProps {
  detections: StreamDetectionPayload[];
}

function getDetectionIdentityKey(
  detection: StreamDetectionPayload,
): string {
  // Giữ key ổn định trong suốt quá trình stream.
  // session_profile_id được ưu tiên vì P_000X tồn tại xuyên suốt session.
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
  // Đảo thứ tự: Ưu tiên ảnh định danh và ảnh trong DB trước ảnh live stream
  return (
    detection.identified_customer_avatar || // 1. Khách hàng đã định danh VIP/Đăng ký
    detection.customer_avatar ||            // 2. Khách hàng đã có thông tin
    detection.stored_profile_avatar ||      // 3. Khách quay lại (có profile ẩn danh trong DB)
    detection.current_video_avatar ||       // 4. Khách mới (dùng ảnh mặt cắt từ video)
    null
  );
}

function normalizeCustomerType(
  value: unknown,
): string {
  return String(value ?? "")
    .trim()
    .toLowerCase()
    .replaceAll("-", "_")
    .replaceAll(" ", "_");
}

function isFinalIdentityResolved(
  detection: StreamDetectionPayload,
): boolean {
  const normalizedType = normalizeCustomerType(
    detection.customer_type,
  );

  // Global identity đã xử lý khi có PersonProfile toàn cục
  // và customer_type đã mang kết luận new/returning.
  return (
    detection.person_profile_id != null &&
    [
      "new",
      "new_customer",
      "returning",
      "returning_customer",
    ].includes(normalizedType)
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
      const anonCode = String(detection.anonymous_code || "").toUpperCase();
      const sessionCode = String(detection.session_profile_id || "").toUpperCase();
      const statusCode = String(detection.identity_status || "").toUpperCase();
      
      const isTrash = 
        anonCode.includes("TEMP") || sessionCode.includes("TEMP") ||
        anonCode.includes("PENDING") || sessionCode.includes("PENDING") ||
        anonCode.includes("TENTATIVE") || sessionCode.includes("TENTATIVE") ||
        statusCode === "NEW_TRACK" || statusCode === "PENDING" || statusCode === "RECHECK";

      // Nếu chứa mã tạm, lập tức bỏ qua, không render thẻ này
      if (isTrash && statusCode !== "CONFIRMED") {
        continue;
      }
      
      const key = getDetectionIdentityKey(detection);
      const existing = uniqueDetections.get(key);

      if (!existing) {
        uniqueDetections.set(key, detection);
        continue;
      }

      const incomingResolved =
        isFinalIdentityResolved(detection);
      const existingResolved =
        isFinalIdentityResolved(existing);

      // Global identity update có thể mang frame_index cũ hơn detection live.
      // Vẫn phải cho phép nó cập nhật New/Returning.
      const shouldReplace =
        incomingResolved ||
        !existingResolved ||
        detection.frame_index >= existing.frame_index;

      if (!shouldReplace) {
        continue;
      }

      uniqueDetections.set(key, {
        ...existing,
        ...detection,

        // Không làm mất avatar video hiện tại khi global identity event
        // không gửi lại ảnh.
        current_video_avatar:
          detection.current_video_avatar ||
          existing.current_video_avatar ||
          null,

        customer_avatar:
          detection.customer_avatar ||
          existing.customer_avatar ||
          null,

        identified_customer_avatar:
          detection.identified_customer_avatar ||
          existing.identified_customer_avatar ||
          null,

        stored_profile_avatar:
          detection.stored_profile_avatar ||
          existing.stored_profile_avatar ||
          null,
      });
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
              const key =
                getDetectionIdentityKey(detection);
              const avatar =
                getCurrentAvatar(detection);

              const isIdentified = Boolean(
                detection.customer_id,
              );

              const normalizedCustomerType =
                normalizeCustomerType(
                  detection.customer_type,
                );

              const identityResolved =
                isFinalIdentityResolved(detection);

              const isReturning =
                identityResolved &&
                [
                  "returning",
                  "returning_customer",
                ].includes(normalizedCustomerType);

              const isNew =
                identityResolved &&
                [
                  "new",
                  "new_customer",
                ].includes(normalizedCustomerType);

              const isPending =
                !isIdentified &&
                !identityResolved;

              const confidence = Number.isFinite(
                detection.confidence,
              )
                ? Math.max(
                    0,
                    Math.min(
                      1,
                      detection.confidence,
                    ),
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
                            : isNew
                              ? "Khách ẩn danh mới"
                              : "Đang đối chiếu hồ sơ khách hàng"}
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
                    ) : isNew ? (
                      <span className="inline-flex items-center gap-0.5 rounded border border-sky-100 bg-sky-50 px-2 py-0.5 text-[9px] font-bold text-sky-600 dark:border-sky-900 dark:bg-sky-950/40 dark:text-sky-400">
                        <UserPlus className="h-3 w-3" />
                        New ANON
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded border border-amber-100 bg-amber-50 px-2 py-0.5 text-[9px] font-bold text-amber-600 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-400">
                        <LoaderCircle className="h-3 w-3 animate-spin" />
                        Verifying
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