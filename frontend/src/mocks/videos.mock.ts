import type { VideoAnalysisResult } from "@/types/video.type";

export function generateMockAnalysisResult(
  videoName: string,
  duration: number
): VideoAnalysisResult {
  const totalCustomers = Math.floor(Math.random() * 15) + 5;
  const newCustomers = Math.floor(totalCustomers * 0.4);
  const returningCustomers = totalCustomers - newCustomers;
  const identifiedCustomers = Math.floor(totalCustomers * 0.6);

  const zones = ["Khu vực A", "Khu vực B", "Quầy thanh toán", "Lối vào", "Khu trưng bày"];

  const persons = Array.from({ length: totalCustomers }, (_, i) => {
    const isIdentified = i < identifiedCustomers;
    const confidence = isIdentified
      ? 0.82 + Math.random() * 0.17
      : 0.55 + Math.random() * 0.25;

    const appearMinutes = Math.floor((Math.random() * duration) / 60);
    const appearSeconds = Math.floor(Math.random() * 60);
    const timeStr = `${String(appearMinutes).padStart(2, "0")}:${String(appearSeconds).padStart(2, "0")}`;

    return {
      id: i + 1,
      anonymous_id: isIdentified
        ? `KH-${String(Math.floor(Math.random() * 9000) + 1000).padStart(6, "0")}`
        : `ANON-${String(i + 1).padStart(5, "0")}`,
      person_type: (isIdentified ? "identified" : "anonymous") as "identified" | "anonymous",
      confidence: parseFloat(confidence.toFixed(3)),
      first_detected_at: timeStr,
      appearances: Math.floor(Math.random() * 8) + 1,
      zone: zones[Math.floor(Math.random() * zones.length)],
      thumbnail_url: `https://api.dicebear.com/7.x/personas/svg?seed=person${i + 1}`,
    };
  });

  // Sort: confidence cao nhất trước
  persons.sort((a, b) => b.confidence - a.confidence);

  const avgConfidence =
    persons.reduce((sum, p) => sum + p.confidence, 0) / persons.length;

  return {
    video_id: Math.floor(Math.random() * 10000),
    video_name: videoName,
    duration,
    processed_at: new Date().toISOString(),
    stats: {
      total_customers: totalCustomers,
      new_customers: newCustomers,
      returning_customers: returningCustomers,
      identified_customers: identifiedCustomers,
      avg_confidence: parseFloat(avgConfidence.toFixed(3)),
      processing_time_ms: Math.floor(duration * 1000 * 0.3 + Math.random() * 2000),
    },
    detected_persons: persons,
  };
}
