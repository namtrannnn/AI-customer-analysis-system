// ─── Mock data cho Dashboard tổng hợp ─────────────────────────────────────────
// Khi BE sẵn sàng, thay bằng API call thực tế

export type RangeKey = "7d" | "30d" | "3m";

export interface DailyStatPoint {
  date: string;       // "DD/MM"
  total: number;
  new_customers: number;
  returning: number;
  avg_duration: number; // phút
}

export interface DashboardStats {
  total_customers: number;
  new_customers: number;
  returning_customers: number;
  avg_duration_minutes: number;
  // % thay đổi so với kỳ trước
  total_change: number;
  new_change: number;
  returning_change: number;
  duration_change: number;
}

export interface ZoneVisitStat {
  zone: string;
  visits: number;
  color: string;
}

// ─── Generator ────────────────────────────────────────────────────────────────
function randomInt(min: number, max: number) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function generateDailyPoints(days: number): DailyStatPoint[] {
  const points: DailyStatPoint[] = [];
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const label = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    const total = randomInt(40, 140);
    const newC = randomInt(10, Math.floor(total * 0.5));
    points.push({
      date: label,
      total,
      new_customers: newC,
      returning: total - newC,
      avg_duration: randomInt(18, 65),
    });
  }
  return points;
}

// ─── Static mock per range (seed cố định cho stable render) ───────────────────
const MOCK_7D: DailyStatPoint[] = [
  { date: "10/07", total: 72,  new_customers: 28, returning: 44, avg_duration: 34 },
  { date: "11/07", total: 88,  new_customers: 35, returning: 53, avg_duration: 41 },
  { date: "12/07", total: 61,  new_customers: 20, returning: 41, avg_duration: 29 },
  { date: "13/07", total: 105, new_customers: 42, returning: 63, avg_duration: 52 },
  { date: "14/07", total: 93,  new_customers: 31, returning: 62, avg_duration: 47 },
  { date: "15/07", total: 118, new_customers: 50, returning: 68, avg_duration: 58 },
  { date: "16/07", total: 97,  new_customers: 38, returning: 59, avg_duration: 44 },
];

const MOCK_30D: DailyStatPoint[] = Array.from({ length: 30 }, (_, i) => {
  const d = new Date("2026-06-17");
  d.setDate(d.getDate() + i);
  const label = `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
  const seeds = [68,74,55,90,102,88,76,65,80,95,110,98,72,85,91,
                 78,84,67,93,107,99,88,74,81,96,103,90,77,86,97];
  const total = seeds[i];
  const newC = Math.floor(total * 0.35);
  return { date: label, total, new_customers: newC, returning: total - newC, avg_duration: 30 + (i % 20) };
});

// 3 tháng — group theo tuần (12 điểm)
const MOCK_3M: DailyStatPoint[] = [
  { date: "T1/W1", total: 420, new_customers: 160, returning: 260, avg_duration: 38 },
  { date: "T1/W2", total: 385, new_customers: 140, returning: 245, avg_duration: 35 },
  { date: "T1/W3", total: 510, new_customers: 195, returning: 315, avg_duration: 44 },
  { date: "T1/W4", total: 475, new_customers: 175, returning: 300, avg_duration: 42 },
  { date: "T2/W1", total: 490, new_customers: 185, returning: 305, avg_duration: 40 },
  { date: "T2/W2", total: 530, new_customers: 210, returning: 320, avg_duration: 46 },
  { date: "T2/W3", total: 460, new_customers: 165, returning: 295, avg_duration: 39 },
  { date: "T2/W4", total: 505, new_customers: 195, returning: 310, avg_duration: 43 },
  { date: "T3/W1", total: 555, new_customers: 225, returning: 330, avg_duration: 48 },
  { date: "T3/W2", total: 520, new_customers: 200, returning: 320, avg_duration: 45 },
  { date: "T3/W3", total: 580, new_customers: 240, returning: 340, avg_duration: 51 },
  { date: "T3/W4", total: 610, new_customers: 250, returning: 360, avg_duration: 54 },
];

export const MOCK_ZONE_VISITS: ZoneVisitStat[] = [
  { zone: "Khu trưng bày",    visits: 342, color: "#6366f1" },
  { zone: "Khu thanh toán",   visits: 218, color: "#22c55e" },
  { zone: "Khu khuyến mãi",   visits: 189, color: "#f59e0b" },
  { zone: "Phòng thử đồ",     visits: 134, color: "#ec4899" },
  { zone: "Lối vào",          visits: 97,  color: "#14b8a6" },
];

export const MOCK_DATA: Record<RangeKey, DailyStatPoint[]> = {
  "7d":  MOCK_7D,
  "30d": MOCK_30D,
  "3m":  MOCK_3M,
};

export function computeStats(points: DailyStatPoint[], prevPoints: DailyStatPoint[]): DashboardStats {
  const sum = (arr: DailyStatPoint[], key: keyof DailyStatPoint) =>
    arr.reduce((s, p) => s + (p[key] as number), 0);

  const total     = sum(points, "total");
  const newC      = sum(points, "new_customers");
  const ret       = sum(points, "returning");
  const avgDur    = Math.round(sum(points, "avg_duration") / (points.length || 1));

  const prevTotal = sum(prevPoints, "total") || 1;
  const prevNew   = sum(prevPoints, "new_customers") || 1;
  const prevRet   = sum(prevPoints, "returning") || 1;
  const prevDur   = Math.round(sum(prevPoints, "avg_duration") / (prevPoints.length || 1)) || 1;

  const pct = (curr: number, prev: number) =>
    Math.round(((curr - prev) / prev) * 100);

  return {
    total_customers:      total,
    new_customers:        newC,
    returning_customers:  ret,
    avg_duration_minutes: avgDur,
    total_change:         pct(total, prevTotal),
    new_change:           pct(newC, prevNew),
    returning_change:     pct(ret, prevRet),
    duration_change:      pct(avgDur, prevDur),
  };
}

// Tạo "kỳ trước" bằng cách shift + noise
export function getPrevPoints(points: DailyStatPoint[]): DailyStatPoint[] {
  return points.map((p) => ({
    ...p,
    total:         Math.max(1, Math.round(p.total * 0.88)),
    new_customers: Math.max(1, Math.round(p.new_customers * 0.85)),
    returning:     Math.max(1, Math.round(p.returning * 0.90)),
    avg_duration:  Math.max(1, Math.round(p.avg_duration * 0.93)),
  }));
}
