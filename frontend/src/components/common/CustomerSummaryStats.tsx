/**
 * FE-10: CustomerSummaryStats
 * Hiển thị 3 chỉ số: Total / New / Returning
 * Tái dụng ở: Dashboard, VideoAnalysisResult, trang Customers
 */
import { Users, UserPlus, RefreshCw } from "lucide-react";
import StatCard from "./StatCard";

export interface CustomerStats {
  total_customers: number;
  new_customers: number;
  returning_customers: number;
}

interface CustomerSummaryStatsProps {
  stats: CustomerStats;
  /** Hiển thị thêm % breakdown hay không */
  showPercent?: boolean;
  /** Thêm slot card thứ 4 tùy chỉnh */
  extraCard?: React.ReactNode;
}

export default function CustomerSummaryStats({
  stats,
  showPercent = true,
  extraCard,
}: CustomerSummaryStatsProps) {
  const { total_customers: total, new_customers: newC, returning_customers: returning } = stats;

  const newPct  = total > 0 ? Math.round((newC / total) * 100) : 0;
  const retPct  = total > 0 ? Math.round((returning / total) * 100) : 0;

  return (
    <div className={`grid gap-3 ${extraCard ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-1 sm:grid-cols-3"}`}>
      <StatCard
        label="Tổng khách phát hiện"
        value={total}
        gradient="from-violet-500 to-purple-600"
        icon={<Users className="h-5 w-5 text-white" />}
      />
      <StatCard
        label="Khách mới"
        value={newC}
        sub={showPercent ? `${newPct}% tổng số` : undefined}
        gradient="from-emerald-500 to-teal-500"
        icon={<UserPlus className="h-5 w-5 text-white" />}
      />
      <StatCard
        label="Khách quay lại"
        value={returning}
        sub={showPercent ? `${retPct}% tổng số` : undefined}
        gradient="from-blue-500 to-indigo-500"
        icon={<RefreshCw className="h-5 w-5 text-white" />}
      />
      {extraCard && <div>{extraCard}</div>}
    </div>
  );
}
