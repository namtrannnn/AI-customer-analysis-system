/**
 * Component hiển thị danh sách khách hàng nhận dạng trực tiếp (LiveFeed Detections)
 * Nhiệm vụ: Tự động sắp xếp khách hàng mới phát hiện lên đầu bảng, có hiệu ứng động và hiển thị ảnh cắt thật.
 */

"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { Users, User, ShieldCheck } from "lucide-react";
import type { StreamDetectionPayload } from "@/services/video_stream.service";

interface LiveDetectionsListProps {
  detections: StreamDetectionPayload[];
}

export default function LiveDetectionsList({ detections }: LiveDetectionsListProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Lọc lấy danh sách các mã định danh duy nhất (Unique) đã xuất hiện trong danh sách detections
  const uniqueDetectionsMap = new Map<string, StreamDetectionPayload>();
  detections.forEach((d) => {
    // Luôn giữ phiên bản nhận diện mới nhất (có thể có confidence hoặc thông tin cập nhật hơn)
    uniqueDetectionsMap.set(d.anonymous_code, d);
  });

  // Chuyển Map thành Array và sắp xếp theo thứ tự xuất hiện mới nhất lên đầu bảng
  const sortedDetections = Array.from(uniqueDetectionsMap.values()).sort(
    (a, b) => b.frame_index - a.frame_index
  );

  // Tự động cuộn danh sách lên đầu khi có khách hàng mới xuất hiện
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTo({ top: 0, behavior: "smooth" });
    }
  }, [sortedDetections.length]);

  return (
    <div className="flex h-full flex-col border border-slate-100 bg-white shadow-2xs dark:border-slate-800 dark:bg-slate-900 rounded-2xl overflow-hidden">
      {/* Header Panel */}
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 px-5 py-4">
        <h3 className="text-sm font-bold text-slate-800 dark:text-slate-200 flex items-center gap-2 uppercase tracking-wide">
          <Users className="h-4.5 w-4.5 text-indigo-500" />
          Khách hàng nhận diện ({sortedDetections.length})
        </h3>
        
        {sortedDetections.length > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-50 text-[10px] font-extrabold text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-ping" />
            Live Feed
          </span>
        )}
      </div>

      {/* List Body */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto p-4 space-y-2.5 max-h-[460px] min-h-[300px]"
      >
        {sortedDetections.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center text-slate-400 dark:text-slate-500">
            <User className="h-10 w-10 stroke-1 mb-2 animate-bounce" />
            <p className="text-xs font-semibold">Đang chờ quét video...</p>
            <p className="text-[10px] opacity-75 mt-0.5">Khách hàng sẽ xuất hiện ngay khi AI nhận dạng</p>
          </div>
        ) : (
          <div className="space-y-2.5">
            {sortedDetections.map((d) => {
              const isIdentified = !!d.customer_id;
              
              return (
                <div
                  key={d.anonymous_code}
                  className="flex items-center justify-between p-3 rounded-xl border border-slate-50 hover:border-slate-200 bg-white dark:border-slate-800 dark:bg-slate-900/60 dark:hover:border-slate-700 transition duration-200 animate-fade-in shadow-2xs"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    {/* Avatar hiển thị hình chụp hoặc silhouette */}
                    <div className="relative h-10 w-10 shrink-0 overflow-hidden rounded-full border border-slate-100 bg-slate-50 dark:border-slate-850 dark:bg-slate-800 flex items-center justify-center">
                      {d.customer_avatar ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={d.customer_avatar}
                          alt="Avatar"
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        <User className="h-5 w-5 text-slate-400 dark:text-slate-500" />
                      )}
                    </div>

                    {/* Metadata thông tin khách hàng */}
                    <div className="min-w-0">
                      {isIdentified ? (
                        <Link
                          href={`/customers/${d.customer_id}`}
                          className="block truncate text-xs font-bold text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300 hover:underline transition"
                          title="Xem thông tin chi tiết khách hàng"
                        >
                          {d.customer_name}
                        </Link>
                      ) : (
                        <span className="block truncate text-xs font-bold text-slate-800 dark:text-slate-200">
                          {d.anonymous_code}
                        </span>
                      )}
                      
                      <span className="block font-mono text-[9px] text-slate-400 dark:text-slate-500 mt-0.5 uppercase">
                        {isIdentified ? `Đã định danh: ${d.anonymous_code}` : "Khách ẩn danh"}
                      </span>
                    </div>
                  </div>

                  {/* Cột hiển thị loại khách và độ chính xác nhận dạng */}
                  <div className="text-right shrink-0 flex flex-col items-end gap-1">
                    {isIdentified ? (
                      <span className="inline-flex items-center gap-0.5 px-2 py-0.5 rounded bg-indigo-50 text-[9px] font-bold text-indigo-600 dark:bg-indigo-950/40 dark:text-indigo-400 border border-indigo-100/55">
                        <ShieldCheck className="h-3 w-3" />
                        Returning
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-[9px] font-bold text-slate-500 dark:bg-slate-800 dark:text-slate-400">
                        New ANON
                      </span>
                    )}
                    
                    <span className="text-[10px] font-mono text-slate-500 dark:text-slate-400">
                      Conf: {Math.round(d.confidence * 100)}%
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
