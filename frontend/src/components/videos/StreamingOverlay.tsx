/**
 * Component lớp phủ Bounding Box (StreamingOverlay)
 * Nhiệm vụ: Tự động điều chỉnh kích thước theo Video Player hiển thị thực tế
 * và vẽ các ô vuông nhận dạng kèm mã ID của từng người đang di chuyển.
 */

"use client";

import { useEffect, useRef, useState } from "react";
import type { StreamDetectionPayload } from "@/services/video_stream.service";

interface StreamingOverlayProps {
  detections: StreamDetectionPayload[]; // Nhận các detections ở frame hiện tại
  videoElement: HTMLVideoElement | null; // Cần phần tử HTMLVideoElement để lấy kích thước thật
}

export default function StreamingOverlay({ detections, videoElement }: StreamingOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState({ x: 1, y: 1 });
  const [offset, setOffset] = useState({ left: 0, top: 0 });

  // Theo dõi kích thước hiển thị thực tế của video để scale tỉ lệ tọa độ
  useEffect(() => {
    if (!videoElement) return;

    const updateScale = () => {
      const container = containerRef.current;
      if (!container) return;

      const videoWidth = videoElement.videoWidth || 640;
      const videoHeight = videoElement.videoHeight || 360;

      // Đo kích thước hiển thị của video trên trình duyệt
      const rect = videoElement.getBoundingClientRect();
      
      // Tính toán vùng chứa tỉ lệ co dãn (letterbox/pillarbox)
      const videoAspect = videoWidth / videoHeight;
      const elementAspect = rect.width / rect.height;

      let displayWidth = rect.width;
      let displayHeight = rect.height;
      let left = 0;
      let top = 0;

      if (elementAspect > videoAspect) {
        // Có viền đen 2 bên (Pillarbox)
        displayWidth = rect.height * videoAspect;
        left = (rect.width - displayWidth) / 2;
      } else {
        // Có viền đen trên dưới (Letterbox)
        displayHeight = rect.width / videoAspect;
        top = (rect.height - displayHeight) / 2;
      }

      setScale({
        x: displayWidth,
        y: displayHeight,
      });

      setOffset({
        left,
        top,
      });
    };

    // Khởi tạo và đăng ký lắng nghe sự kiện thay đổi kích thước
    updateScale();
    const resizeObserver = new ResizeObserver(updateScale);
    resizeObserver.observe(videoElement);

    return () => {
      resizeObserver.disconnect();
    };
  }, [videoElement]);

  // Bộ bảng màu sắc riêng biệt cho từng ID để dễ phân biệt
  const getBoxColor = (trackId: number) => {
    const colors = [
      "border-emerald-500 text-emerald-500 bg-emerald-500/10",
      "border-indigo-500 text-indigo-500 bg-indigo-500/10",
      "border-amber-500 text-amber-500 bg-amber-500/10",
      "border-rose-500 text-rose-500 bg-rose-500/10",
      "border-cyan-500 text-cyan-500 bg-cyan-500/10",
      "border-violet-500 text-violet-500 bg-violet-500/10",
    ];
    return colors[trackId % colors.length];
  };

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none z-10 overflow-hidden"
    >
      {/* Vùng vẽ các khung Bounding Box lồng khớp với phần hiển thị của Video */}
      <div
        className="absolute"
        style={{
          left: `${offset.left}px`,
          top: `${offset.top}px`,
          width: `${scale.x}px`,
          height: `${scale.y}px`,
        }}
      >
        {detections.map((d) => {
          const [x1, y1, x2, y2] = d.bbox;
          
          // Chuyển đổi tỉ lệ relative (0..1) sang pixels
          const left = x1 * scale.x;
          const top = y1 * scale.y;
          const width = (x2 - x1) * scale.x;
          const height = (y2 - y1) * scale.y;

          const boxStyle = getBoxColor(d.track_id);

          return (
            <div
              key={`${d.track_id}-${d.frame_index}`}
              className={`absolute border-2 rounded-lg transition-all duration-75 ease-out ${boxStyle.split(" ")[0]} ${boxStyle.split(" ")[2]}`}
              style={{
                left: `${left}px`,
                top: `${top}px`,
                width: `${width}px`,
                height: `${height}px`,
              }}
            >
              {/* Nhãn dán ID / Tên khách hàng ở góc trên hộp bao */}
              <div
                className={`absolute -top-6 left-0 px-2 py-0.5 rounded text-[10px] font-extrabold uppercase tracking-wide flex items-center gap-1 shadow-sm ${boxStyle.split(" ")[0].replace("border-", "bg-")} text-white`}
              >
                <span>{d.customer_name || d.anonymous_code}</span>
                <span className="opacity-80">({Math.round(d.confidence * 100)}%)</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
