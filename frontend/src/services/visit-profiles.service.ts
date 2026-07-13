/**
 * Dịch vụ mock dữ liệu Danh sách khách ghé thăm lọt camera AI (PB04)
 * Hỗ trợ phân loại khách cũ (Returning) và khách mới (New)
 */

export interface VisitHistoryItem {
  id: number;
  entry_time: string;
  exit_time: string | null;
  duration_seconds: number | null;
  camera_name: string;
}

export interface VisitorProfile {
  id: number;
  anonymous_code: string;
  person_type: "anonymous" | "identified";
  face_image_url: string;
  total_visits: number;
  first_seen_at: string;
  last_seen_at: string;
  customer_name: string | null;
  customer_code: string | null;
  customer_phone: string | null;
  customer_email: string | null;
  customer_gender: string | null;
  customer_spent: number;
  recent_visits: VisitHistoryItem[];
}

export interface VisitorFilters {
  search?: string;
  visitor_type?: "all" | "new" | "returning";
  start_date?: string;
  end_date?: string;
}

// ─── Mock Database ──────────────────────────────────────

const now = new Date();
const formatOffsetDate = (daysAgo: number, hoursOffset: number) => {
  const d = new Date(now.getTime() - daysAgo * 24 * 60 * 60 * 1000 - hoursOffset * 60 * 60 * 1000);
  return d.toISOString();
};

const mockVisitorProfiles: VisitorProfile[] = [
  {
    id: 1,
    anonymous_code: "ANON-Y718",
    person_type: "identified",
    face_image_url: "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 12,
    first_seen_at: formatOffsetDate(30, 4),
    last_seen_at: formatOffsetDate(0, 1), // 1h trước
    customer_name: "Trần Nhật Nam",
    customer_code: "KH0001",
    customer_phone: "0912345678",
    customer_email: "oanhpng@hqsolutions.vn",
    customer_gender: "female",
    customer_spent: 4200000,
    recent_visits: [
      { id: 11, entry_time: formatOffsetDate(0, 1.5), exit_time: formatOffsetDate(0, 1), duration_seconds: 1800, camera_name: "Camera Cổng vào" },
      { id: 12, entry_time: formatOffsetDate(2, 3), exit_time: formatOffsetDate(2, 2.2), duration_seconds: 2880, camera_name: "Camera Quầy thanh toán" },
      { id: 13, entry_time: formatOffsetDate(5, 5), exit_time: formatOffsetDate(5, 4.5), duration_seconds: 1800, camera_name: "Camera Cổng vào" }
    ]
  },
  {
    id: 2,
    anonymous_code: "ANON-X502",
    person_type: "anonymous",
    face_image_url: "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 1,
    first_seen_at: formatOffsetDate(0, 2), // 2h trước
    last_seen_at: formatOffsetDate(0, 2),
    customer_name: null,
    customer_code: null,
    customer_phone: null,
    customer_email: null,
    customer_gender: null,
    customer_spent: 0,
    recent_visits: [
      { id: 21, entry_time: formatOffsetDate(0, 2.5), exit_time: formatOffsetDate(0, 2), duration_seconds: 3000, camera_name: "Camera Lối đi A" }
    ]
  },
  {
    id: 3,
    anonymous_code: "ANON-K928",
    person_type: "identified",
    face_image_url: "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 7,
    first_seen_at: formatOffsetDate(15, 2),
    last_seen_at: formatOffsetDate(0, 3), // 3h trước
    customer_name: "Nguyễn Văn Hùng",
    customer_code: "KH0002",
    customer_phone: "0987654321",
    customer_email: "hungnv@hqsolutions.vn",
    customer_gender: "male",
    customer_spent: 2500000,
    recent_visits: [
      { id: 31, entry_time: formatOffsetDate(0, 3.5), exit_time: formatOffsetDate(0, 3), duration_seconds: 1800, camera_name: "Camera Cổng vào" },
      { id: 32, entry_time: formatOffsetDate(3, 1), exit_time: formatOffsetDate(3, 0.5), duration_seconds: 3000, camera_name: "Camera Quầy Trưng bày" }
    ]
  },
  {
    id: 4,
    anonymous_code: "ANON-B882",
    person_type: "anonymous",
    face_image_url: "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 4,
    first_seen_at: formatOffsetDate(6, 1),
    last_seen_at: formatOffsetDate(1, 5), // 1 ngày trước
    customer_name: null,
    customer_code: null,
    customer_phone: null,
    customer_email: null,
    customer_gender: null,
    customer_spent: 0,
    recent_visits: [
      { id: 41, entry_time: formatOffsetDate(1, 6), exit_time: formatOffsetDate(1, 5), duration_seconds: 3600, camera_name: "Camera Lối đi B" },
      { id: 42, entry_time: formatOffsetDate(4, 2), exit_time: formatOffsetDate(4, 1.5), duration_seconds: 1800, camera_name: "Camera Cổng vào" }
    ]
  },
  {
    id: 5,
    anonymous_code: "ANON-J019",
    person_type: "identified",
    face_image_url: "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 9,
    first_seen_at: formatOffsetDate(20, 8),
    last_seen_at: formatOffsetDate(2, 6), // 2 ngày trước
    customer_name: "Trần Thị Thanh",
    customer_code: "KH0003",
    customer_phone: "0905556677",
    customer_email: "thanhtt@hqsolutions.vn",
    customer_gender: "female",
    customer_spent: 3100000,
    recent_visits: [
      { id: 51, entry_time: formatOffsetDate(2, 7), exit_time: formatOffsetDate(2, 6), duration_seconds: 3600, camera_name: "Camera Quầy thanh toán" },
      { id: 52, entry_time: formatOffsetDate(8, 4), exit_time: formatOffsetDate(8, 3.2), duration_seconds: 2880, camera_name: "Camera Cổng vào" }
    ]
  },
  {
    id: 6,
    anonymous_code: "ANON-L991",
    person_type: "anonymous",
    face_image_url: "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?auto=format&fit=crop&q=80&w=150&h=150",
    total_visits: 1,
    first_seen_at: formatOffsetDate(3, 4), // 3 ngày trước
    last_seen_at: formatOffsetDate(3, 4),
    customer_name: null,
    customer_code: null,
    customer_phone: null,
    customer_email: null,
    customer_gender: null,
    customer_spent: 0,
    recent_visits: [
      { id: 61, entry_time: formatOffsetDate(3, 4.5), exit_time: formatOffsetDate(3, 4), duration_seconds: 1800, camera_name: "Camera Cổng vào" }
    ]
  }
];

// ─── API Requests ──────────────────────────────────────

/**
 * Lấy danh sách khách ghé thăm có bộ lọc và phân trang giả lập
 */
export async function getVisitorProfiles(
  filters: VisitorFilters,
  skip = 0,
  limit = 20
): Promise<VisitorProfile[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      let result = [...mockVisitorProfiles];

      // Lọc theo từ khóa tìm kiếm (Mã ẩn danh hoặc tên thành viên liên kết)
      if (filters.search) {
        const s = filters.search.toLowerCase();
        result = result.filter(
          (item) =>
            item.anonymous_code.toLowerCase().includes(s) ||
            (item.customer_name && item.customer_name.toLowerCase().includes(s))
        );
      }

      // Lọc theo loại khách (New vs Returning)
      if (filters.visitor_type && filters.visitor_type !== "all") {
        if (filters.visitor_type === "new") {
          result = result.filter((item) => item.total_visits === 1);
        } else if (filters.visitor_type === "returning") {
          result = result.filter((item) => item.total_visits > 1);
        }
      }

      // Lọc theo khoảng ngày (Last seen date)
      if (filters.start_date) {
        const start = new Date(filters.start_date);
        result = result.filter((item) => new Date(item.last_seen_at) >= start);
      }
      if (filters.end_date) {
        const end = new Date(filters.end_date + "T23:59:59");
        result = result.filter((item) => new Date(item.last_seen_at) <= end);
      }

      resolve(result.slice(skip, skip + limit));
    }, 300);
  });
}

/**
 * Lấy thống kê số lượng khách Mới vs Khách Quay Lại
 */
export async function getVisitorStats(): Promise<{ new_count: number; returning_count: number; total_count: number }> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const new_count = mockVisitorProfiles.filter((v) => v.total_visits === 1).length;
      const returning_count = mockVisitorProfiles.filter((v) => v.total_visits > 1).length;
      resolve({
        new_count,
        returning_count,
        total_count: mockVisitorProfiles.length
      });
    }, 200);
  });
}
