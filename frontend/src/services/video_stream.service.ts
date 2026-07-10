/**
 * Dịch vụ xử lý Luồng Stream Video (Realtime Streaming)
 * Hỗ trợ chế độ giả lập (Simulator) để kiểm thử giao diện Frontend trước khi Backend hoàn thành.
 */

import type { VideoAnalysisResult, DetectedPerson } from "@/types/video.type";

// Cấu hình chế độ giả lập (Bật để chạy thử giao diện ngay lập tức)
export const MOCK_STREAM = true;

// Kiểu dữ liệu cập nhật tiến độ từ Stream
export interface StreamProgressPayload {
  current_frame: number;
  total_frames: number;
  fps: number;
  progress_percent: number;
}

// Kiểu dữ liệu nhận diện khuôn mặt từng frame từ Stream
export interface StreamDetectionPayload {
  frame_index: number;
  track_id: number;
  anonymous_code: string;
  confidence: number;
  bbox: [number, number, number, number]; // Tọa độ tương đối [x1, y1, x2, y2]
  customer_id?: number | null;
  customer_name?: string | null;
  customer_avatar?: string | null;
}

interface StreamCallbacks {
  onProgress: (progress: StreamProgressPayload) => void;
  onDetection: (detection: StreamDetectionPayload) => void;
  onComplete: (result: VideoAnalysisResult) => void;
  onError: (error: string) => void;
}

/**
 * Kết nối luồng Stream xử lý video.
 * Nếu MOCK_STREAM = true, sẽ chạy bộ giả lập thời gian thực.
 */
export function connectJobStream(
  file: File,
  videoDuration: number, // dùng để tính số lượng frame giả lập
  callbacks: StreamCallbacks
): () => void {
  let isCancelled = false;

  // Hủy kết nối / Dọn dẹp
  const disconnect = () => {
    isCancelled = true;
    console.log("[video_stream] Đã hủy luồng stream.");
  };

  if (MOCK_STREAM) {
    // ─── CHẾ ĐỘ GIẢ LẬP (MOCK STREAM SIMULATOR) ───
    const fps = 15; // Tốc độ xử lý giả lập (15 khung hình / giây)
    const totalFrames = Math.max(90, Math.round(videoDuration * fps));
    let currentFrame = 0;
    
    // Danh sách giả lập hành trình của 3 người khác nhau xuất hiện trong video
    const simulatedTracks = [
      {
        trackId: 1,
        anonymousCode: "P_0001",
        startFrame: 15,
        endFrame: totalFrames - 20,
        // Chuyển động xéo từ trái qua phải
        baseX: 0.15,
        baseY: 0.3,
        speedX: 0.002,
        speedY: 0.001,
        boxWidth: 0.08,
        boxHeight: 0.18,
        confidence: 0.94,
        customer_id: 1,
        customer_name: "Nguyễn Văn A",
        customer_avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
      },
      {
        trackId: 3,
        anonymousCode: "P_0003",
        startFrame: 45,
        endFrame: totalFrames - 5,
        // Đứng yên ở khu quầy tính tiền rồi đi ra
        baseX: 0.45,
        baseY: 0.4,
        speedX: 0.0005,
        speedY: -0.001,
        boxWidth: 0.09,
        boxHeight: 0.2,
        confidence: 0.88,
        customer_id: null,
        customer_name: null,
        customer_avatar: null,
      },
      {
        trackId: 5,
        anonymousCode: "P_0005",
        startFrame: 75,
        endFrame: Math.min(totalFrames, 180),
        // Chạy qua nhanh ở lối vào
        baseX: 0.7,
        baseY: 0.15,
        speedX: -0.004,
        speedY: 0.002,
        boxWidth: 0.07,
        boxHeight: 0.16,
        confidence: 0.75,
        customer_id: null,
        customer_name: null,
        customer_avatar: null,
      }
    ];

    const detectedPersonsMap = new Map<string, DetectedPerson>();

    console.log(`[video_stream] Khởi động giả lập: Total Frames=${totalFrames}, FPS=${fps}`);

    const interval = setInterval(() => {
      if (isCancelled) {
        clearInterval(interval);
        return;
      }

      currentFrame++;

      // 1. Gửi tiến độ (Progress)
      const progressPercent = Math.min(100, Math.round((currentFrame / totalFrames) * 100));
      callbacks.onProgress({
        current_frame: currentFrame,
        total_frames: totalFrames,
        fps: fps,
        progress_percent: progressPercent,
      });

      // 2. Gửi dữ liệu nhận diện của Frame này (Detections)
      simulatedTracks.forEach((t) => {
        if (currentFrame >= t.startFrame && currentFrame <= t.endFrame) {
          // Tính toán vị trí bbox dịch chuyển động theo frame
          const step = currentFrame - t.startFrame;
          const x1 = Math.max(0, Math.min(0.9, t.baseX + step * t.speedX));
          const y1 = Math.max(0, Math.min(0.8, t.baseY + step * t.speedY));
          const x2 = x1 + t.boxWidth;
          const y2 = y1 + t.boxHeight;

          // Phát sự kiện nhận diện của frame hiện tại
          callbacks.onDetection({
            frame_index: currentFrame,
            track_id: t.trackId,
            anonymous_code: t.anonymousCode,
            confidence: t.confidence,
            bbox: [x1, y1, x2, y2],
            customer_id: t.customer_id,
            customer_name: t.customer_name,
            customer_avatar: t.customer_avatar,
          });

          // Ghi nhớ danh tính khách hàng để tổng hợp kết quả cuối cùng
          if (!detectedPersonsMap.has(t.anonymousCode)) {
            detectedPersonsMap.set(t.anonymousCode, {
              id: t.trackId,
              anonymous_id: t.anonymousCode,
              person_type: t.customer_id ? "identified" : "anonymous",
              confidence: t.confidence,
              first_detected_at: "00:02",
              appearances: 1,
              zone: null,
              thumbnail_url: t.customer_avatar || `https://api.dicebear.com/7.x/personas/svg?seed=${t.anonymousCode}`,
              customer_id: t.customer_id,
              customer_name: t.customer_name,
            });
          }
        }
      });

      // 3. Hoàn tất stream (Complete)
      if (currentFrame >= totalFrames) {
        clearInterval(interval);

        const detectedList = Array.from(detectedPersonsMap.values());
        const total = detectedList.length;
        const returning = detectedList.filter((p) => p.person_type === "identified").length;
        const newCust = total - returning;

        const result: VideoAnalysisResult = {
          video_id: Date.now(),
          video_name: file.name,
          duration: videoDuration,
          processed_at: new Date().toISOString(),
          stats: {
            total_customers: total,
            new_customers: newCust,
            returning_customers: returning,
            identified_customers: returning,
            avg_confidence: parseFloat((detectedList.reduce((s, p) => s + p.confidence, 0) / (total || 1)).toFixed(3)),
            processing_time_ms: Math.round(videoDuration * 800),
          },
          detected_persons: detectedList,
        };

        callbacks.onComplete(result);
      }
    }, 1000 / fps);

    return () => {
      clearInterval(interval);
      disconnect();
    };
  } else {
    // ─── CHẾ ĐỘ THỰC TẾ (SOCKET CONNECTION) ───
    // Dành cho tương lai khi Backend đã dựng WebSocket
    const wsUrl = `ws://localhost:8000/api/videos/jobs/stream`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => {
      console.log("[video_stream] WebSocket connected.");
      // Gửi tín hiệu khởi tạo nếu cần
      socket.send(JSON.stringify({ action: "start", file_name: file.name }));
    };

    socket.onmessage = (event) => {
      if (isCancelled) return;
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "progress") {
          callbacks.onProgress(msg.data);
        } else if (msg.type === "detection") {
          callbacks.onDetection(msg.data);
        } else if (msg.type === "complete") {
          callbacks.onComplete(msg.data);
          socket.close();
        } else if (msg.type === "error") {
          callbacks.onError(msg.message);
        }
      } catch (err) {
        console.error("[video_stream] Error parsing message:", err);
      }
    };

    socket.onerror = () => {
      callbacks.onError("Lỗi kết nối Socket đến Server.");
    };

    socket.onclose = () => {
      console.log("[video_stream] WebSocket closed.");
    };

    return () => {
      socket.close();
      disconnect();
    };
  }
}
