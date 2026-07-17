/**
 * Service xử lý Luồng Stream Video (Realtime Streaming)
 */
import { http } from "@/lib/http";
import type { DetectedPerson, VideoAnalysisResult } from "@/types/video.type";

// Cấu hình chế độ giả lập (Bật để chạy thử giao diện ngay lập tức)
export const MOCK_STREAM = false;

// Kiểu dữ liệu cập nhật tiến độ từ Stream
export interface StreamProgressPayload {
  current_frame: number;
  total_frames: number;
  fps: number;
  progress_percent: number;

  // Timestamp/frame của video nguồn, cập nhật ở mọi frame AI,
  // kể cả khi frame không có detection.
  source_frame_index?: number;
  source_timestamp_seconds?: number;
  source_fps?: number;
}

// Kiểu dữ liệu nhận diện khuôn mặt từng frame từ Stream
export interface StreamDetectionPayload {
  track_id: number;
  frame_index: number;
  source_frame_index?: number;
  source_timestamp_seconds: number;
  source_fps?: number;
  bbox: [number, number, number, number];
  confidence: number;

  identity_status?: string | null;

  session_profile_id?: string | null;
  person_profile_id?: number | null;

  anonymous_code: string;
  customer_type?: "new" | "returning" | string;

  customer_id?: number | null;
  customer_name?: string | null;

  customer_avatar?: string | null;
  current_video_avatar?: string | null;
  stored_profile_avatar?: string | null;
  identified_customer_avatar?: string | null;

  total_visits?: number | null;
}


export interface GlobalIdentityItem {
  person_profile_id: number;
  anonymous_code: string;
  customer_type: "new" | "returning" | string;
  total_visits: number;
  matched_similarity?: number;
  customer_id?: number | null;
  customer_name?: string | null;
  current_video_avatar?: string | null;
}

export interface GlobalIdentityResultPayload {
  session_profile_mapping?: Record<string, GlobalIdentityItem>;
  track_identity_mapping?: Record<
    string,
    GlobalIdentityItem & {
      session_profile_id?: string;
    }
  >;
  final_customer_count?: number;
}

interface StreamCallbacks {
  onProgress: (progress: StreamProgressPayload) => void;
  onDetection: (detection: StreamDetectionPayload) => void;
  onGlobalIdentity?: (payload: GlobalIdentityResultPayload) => void;
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
  callbacks: StreamCallbacks,
): () => void {
  let isCancelled = false;

  // Hủy kết nối / Dọn dẹp
  const disconnect = () => {
    isCancelled = true;
    console.log("[video_stream] Đã hủy luồng stream.");
  };

  if (MOCK_STREAM) {
    return connectMockStream(file, videoDuration, callbacks, () => isCancelled, disconnect);
  } else {
    let socket: WebSocket | null = null;

    // Lưu detection mới nhất theo track để khi backend gửi
    // global_identity_result có thể cập nhật lại New/Returning.
    const latestDetectionByTrack = new Map<number, StreamDetectionPayload>();

    void (async () => {
      try {
        const form = new FormData();
        form.append("file", file);

        const res = await http.raw.post<{
          status: string;
          data: { job_id: string; status: string };
        }>("/videos/jobs", form, {
          timeout: 60 * 1000,
          headers: {
            "Content-Type": undefined,
          },
        });

        if (isCancelled) return;

        const jobId = res.data.data.job_id;
        socket = new WebSocket(`ws://localhost:8000/api/videos/jobs/${jobId}/stream`);

        socket.onopen = () => {
          console.log("[video_stream] WebSocket connected", jobId);
        };

        socket.onmessage = (event) => {
          if (isCancelled) return;
          try {
            const msg = JSON.parse(event.data);
            if (msg.type === "progress") {
              callbacks.onProgress(msg.data);
            } else if (msg.type === "detection") {
              const detection = msg.data as StreamDetectionPayload;
              latestDetectionByTrack.set(detection.track_id, detection);
              callbacks.onDetection(detection);
            } else if (msg.type === "global_identity_result") {
              const payload = msg as GlobalIdentityResultPayload & {
                data?: GlobalIdentityResultPayload;
              };

              const identityData = payload.data ?? payload;
              const trackMapping =
                identityData.track_identity_mapping ?? {};

              callbacks.onGlobalIdentity?.(identityData);

              Object.entries(trackMapping).forEach(
                ([trackIdText, identity]) => {
                  const trackId = Number(trackIdText);
                  const previous = latestDetectionByTrack.get(trackId);

                  if (!previous || !Number.isFinite(trackId)) {
                    return;
                  }

                  const updated: StreamDetectionPayload = {
                    ...previous,
                    track_id: trackId,
                    session_profile_id:
                      identity.session_profile_id ??
                      previous.session_profile_id ??
                      previous.anonymous_code,
                    person_profile_id:
                      identity.person_profile_id,
                    anonymous_code:
                      identity.anonymous_code ??
                      previous.anonymous_code,
                    customer_type:
                      identity.customer_type,
                    total_visits:
                      identity.total_visits,
                    customer_id:
                      identity.customer_id ??
                      previous.customer_id ??
                      null,
                    customer_name:
                      identity.customer_name ??
                      previous.customer_name ??
                      null,
                    current_video_avatar:
                      identity.current_video_avatar ??
                      previous.current_video_avatar ??
                      null,
                  };

                  latestDetectionByTrack.set(trackId, updated);
                  callbacks.onDetection(updated);
                },
              );
            } else if (msg.type === "complete") {
              callbacks.onComplete(msg.data);
              socket?.close();
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
      } catch (err) {
        if (!isCancelled) {
          callbacks.onError(
            err instanceof Error ? err.message : "Không thể khởi tạo job xử lý.",
          );
        }
      }
    })();

    return () => {
      socket?.close();
      disconnect();
    };
  }
}

function connectMockStream(
  file: File,
  videoDuration: number,
  callbacks: StreamCallbacks,
  isCancelled: () => boolean,
  disconnect: () => void,
): () => void {
  const fps = 15;
  const totalFrames = Math.max(90, Math.round(videoDuration * fps));
  let currentFrame = 0;

  const simulatedTracks = [
    {
      trackId: 1,
      anonymousCode: "P_0001",
      startFrame: 15,
      endFrame: totalFrames - 20,
      baseX: 0.15,
      baseY: 0.3,
      speedX: 0.002,
      speedY: 0.001,
      boxWidth: 0.08,
      boxHeight: 0.18,
      confidence: 0.94,
      customer_id: 1,
      customer_name: "Nguyen Van A",
      customer_avatar: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
    },
    {
      trackId: 3,
      anonymousCode: "P_0003",
      startFrame: 45,
      endFrame: totalFrames - 5,
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
    },
  ];

  const detectedPersonsMap = new Map<string, DetectedPerson>();

  const interval = setInterval(() => {
    if (isCancelled()) {
      clearInterval(interval);
      return;
    }

    currentFrame += 1;
    callbacks.onProgress({
      current_frame: currentFrame,
      total_frames: totalFrames,
      fps,
      progress_percent: Math.min(100, Math.round((currentFrame / totalFrames) * 100)),
    });

    simulatedTracks.forEach((track) => {
      if (currentFrame < track.startFrame || currentFrame > track.endFrame) return;

      const step = currentFrame - track.startFrame;
      const x1 = Math.max(0, Math.min(0.9, track.baseX + step * track.speedX));
      const y1 = Math.max(0, Math.min(0.8, track.baseY + step * track.speedY));
      const x2 = x1 + track.boxWidth;
      const y2 = y1 + track.boxHeight;

      callbacks.onDetection({
        frame_index: currentFrame,
        source_frame_index: currentFrame,
        source_timestamp_seconds: currentFrame / fps,
        source_fps: fps,
        track_id: track.trackId,
        anonymous_code: track.anonymousCode,
        confidence: track.confidence,
        bbox: [x1, y1, x2, y2],
        customer_id: track.customer_id,
        customer_name: track.customer_name,
        customer_avatar: track.customer_avatar,
      });

      if (!detectedPersonsMap.has(track.anonymousCode)) {
        detectedPersonsMap.set(track.anonymousCode, {
          id: track.trackId,
          anonymous_id: track.anonymousCode,
          person_type: track.customer_id ? "identified" : "anonymous",
          confidence: track.confidence,
          first_detected_at: "00:02",
          appearances: 1,
          zone: null,
          thumbnail_url: track.customer_avatar || `https://api.dicebear.com/7.x/personas/svg?seed=${track.anonymousCode}`,
          customer_id: track.customer_id,
          customer_name: track.customer_name,
        });
      }
    });

    if (currentFrame >= totalFrames) {
      clearInterval(interval);
      const detectedList = Array.from(detectedPersonsMap.values());
      const total = detectedList.length;
      const returning = detectedList.filter((person) => person.person_type === "identified").length;

      callbacks.onComplete({
        video_id: Date.now(),
        video_name: file.name,
        duration: videoDuration,
        processed_at: new Date().toISOString(),
        stats: {
          total_customers: total,
          new_customers: total - returning,
          returning_customers: returning,
          identified_customers: returning,
          avg_confidence: parseFloat(
            (detectedList.reduce((sum, person) => sum + person.confidence, 0) / (total || 1)).toFixed(3),
          ),
          processing_time_ms: Math.round(videoDuration * 800),
        },
        detected_persons: detectedList,
      });
    }
  }, 1000 / fps);

  return () => {
    clearInterval(interval);
    disconnect();
  };
}