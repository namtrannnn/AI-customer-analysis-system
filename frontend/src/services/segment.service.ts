/**
 * Dịch vụ mock dữ liệu Phân nhóm khách hàng AI (PB08)
 * Giúp Frontend hoạt động độc lập không cần API Backend.
 */

// ─── Types ──────────────────────────────────────────────

import { http } from "@/lib/http";

export interface SegmentItem {
  id: number;
  segment_name: string;
  description: string | null;
  member_count: number;
  avg_visits: number;
  avg_duration: number;
  avg_spent: number;
  created_at: string;
}

export interface SegmentMember {
  person_profile_id: number;
  anonymous_code: string;
  person_type: string;
  customer_name: string | null;
  customer_code: string | null;
  total_visits: number;
  avg_duration_seconds: number;
  total_spent: number;
  score: number | null;
  assigned_at: string;
}

export interface ClusteringResult {
  status?: string;
  segments_created: number;
  total_customers_processed: number;
  features_used: string[];
  message: string;
}

// ─── Mock Database ──────────────────────────────────────

let mockSegments: SegmentItem[] = [
  {
    id: 1,
    segment_name: "Khách VIP - Giá trị cao",
    description: "Nhóm khách hàng trung thành, tần suất ghé thăm cao và có mức chi tiêu mua sắm lớn nhất.",
    member_count: 8,
    avg_visits: 12.5,
    avg_duration: 840,
    avg_spent: 4200000,
    created_at: new Date().toISOString(),
  },
  {
    id: 2,
    segment_name: "Khách tiềm năng - Duyệt nhiều",
    description: "Ghé thăm cửa hàng thường xuyên, đi qua nhiều khu vực nhưng mức chi tiêu còn hạn chế.",
    member_count: 15,
    avg_visits: 8.2,
    avg_duration: 620,
    avg_spent: 850000,
    created_at: new Date().toISOString(),
  },
  {
    id: 3,
    segment_name: "Khách vãng lai - Ít tương tác",
    description: "Nhóm khách vãng lai ghé thăm ít, thời gian ở lại ngắn và chưa phát sinh giao dịch lớn.",
    member_count: 22,
    avg_visits: 1.8,
    avg_duration: 110,
    avg_spent: 50000,
    created_at: new Date().toISOString(),
  }
];

let mockMembersMap: Record<number, SegmentMember[]> = {
  1: [
    { person_profile_id: 101, anonymous_code: "ANON-F839", person_type: "identified", customer_name: "Trần Nhật Nam", customer_code: "KH0001", total_visits: 15, avg_duration_seconds: 900, total_spent: 5200000, score: 0.98, assigned_at: new Date().toISOString() },
    { person_profile_id: 102, anonymous_code: "ANON-A293", person_type: "identified", customer_name: "Nguyễn Văn Hùng", customer_code: "KH0002", total_visits: 12, avg_duration_seconds: 780, total_spent: 4500000, score: 0.95, assigned_at: new Date().toISOString() },
    { person_profile_id: 103, anonymous_code: "ANON-Z912", person_type: "identified", customer_name: "Trần Thị Thanh", customer_code: "KH0003", total_visits: 14, avg_duration_seconds: 880, total_spent: 4800000, score: 0.96, assigned_at: new Date().toISOString() },
    { person_profile_id: 104, anonymous_code: "ANON-C581", person_type: "identified", customer_name: "Lê Hoàng Long", customer_code: "KH0004", total_visits: 10, avg_duration_seconds: 810, total_spent: 3900000, score: 0.92, assigned_at: new Date().toISOString() },
    { person_profile_id: 105, anonymous_code: "ANON-K190", person_type: "identified", customer_name: "Hoàng Minh Tuấn", customer_code: "KH0005", total_visits: 11, avg_duration_seconds: 830, total_spent: 3800000, score: 0.94, assigned_at: new Date().toISOString() },
    { person_profile_id: 106, anonymous_code: "ANON-E773", person_type: "identified", customer_name: "Vũ Phương Thảo", customer_code: "KH0006", total_visits: 13, avg_duration_seconds: 850, total_spent: 4100000, score: 0.97, assigned_at: new Date().toISOString() },
    { person_profile_id: 107, anonymous_code: "ANON-Q901", person_type: "identified", customer_name: "Đỗ Gia Bảo", customer_code: "KH0007", total_visits: 9, avg_duration_seconds: 750, total_spent: 3200000, score: 0.89, assigned_at: new Date().toISOString() },
    { person_profile_id: 108, anonymous_code: "ANON-H552", person_type: "identified", customer_name: "Ngô Quốc Khánh", customer_code: "KH0008", total_visits: 16, avg_duration_seconds: 920, total_spent: 4100000, score: 0.99, assigned_at: new Date().toISOString() },
  ],
  2: [
    { person_profile_id: 201, anonymous_code: "ANON-J984", person_type: "identified", customer_name: "Bùi Thị Mai", customer_code: "KH0009", total_visits: 9, avg_duration_seconds: 680, total_spent: 1200000, score: 0.88, assigned_at: new Date().toISOString() },
    { person_profile_id: 202, anonymous_code: "ANON-W223", person_type: "identified", customer_name: "Phan Anh Đức", customer_code: "KH0010", total_visits: 8, avg_duration_seconds: 590, total_spent: 980000, score: 0.85, assigned_at: new Date().toISOString() },
    { person_profile_id: 203, anonymous_code: "ANON-X495", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 10, avg_duration_seconds: 650, total_spent: 0, score: 0.79, assigned_at: new Date().toISOString() },
    { person_profile_id: 204, anonymous_code: "ANON-Y111", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 7, avg_duration_seconds: 610, total_spent: 0, score: 0.81, assigned_at: new Date().toISOString() },
    { person_profile_id: 205, anonymous_code: "ANON-M904", person_type: "identified", customer_name: "Đặng Hồng Nhung", customer_code: "KH0011", total_visits: 9, avg_duration_seconds: 640, total_spent: 1100000, score: 0.87, assigned_at: new Date().toISOString() },
    { person_profile_id: 206, anonymous_code: "ANON-P812", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 8, avg_duration_seconds: 580, total_spent: 0, score: 0.74, assigned_at: new Date().toISOString() },
    { person_profile_id: 207, anonymous_code: "ANON-U343", person_type: "identified", customer_name: "Trịnh Tấn Đạt", customer_code: "KH0012", total_visits: 8, avg_duration_seconds: 600, total_spent: 750000, score: 0.82, assigned_at: new Date().toISOString() },
    { person_profile_id: 208, anonymous_code: "ANON-L093", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 10, avg_duration_seconds: 670, total_spent: 0, score: 0.76, assigned_at: new Date().toISOString() },
    { person_profile_id: 209, anonymous_code: "ANON-R234", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 7, avg_duration_seconds: 550, total_spent: 0, score: 0.72, assigned_at: new Date().toISOString() },
    { person_profile_id: 210, anonymous_code: "ANON-T665", person_type: "identified", customer_name: "Mai Tiến Dũng", customer_code: "KH0013", total_visits: 9, avg_duration_seconds: 620, total_spent: 910000, score: 0.84, assigned_at: new Date().toISOString() },
    { person_profile_id: 211, anonymous_code: "ANON-O981", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 8, avg_duration_seconds: 570, total_spent: 0, score: 0.71, assigned_at: new Date().toISOString() },
    { person_profile_id: 212, anonymous_code: "ANON-S102", person_type: "identified", customer_name: "Nguyễn Hải Yến", customer_code: "KH0014", total_visits: 7, avg_duration_seconds: 560, total_spent: 800000, score: 0.80, assigned_at: new Date().toISOString() },
    { person_profile_id: 213, anonymous_code: "ANON-V433", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 9, avg_duration_seconds: 630, total_spent: 0, score: 0.75, assigned_at: new Date().toISOString() },
    { person_profile_id: 214, anonymous_code: "ANON-W819", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 8, avg_duration_seconds: 590, total_spent: 0, score: 0.73, assigned_at: new Date().toISOString() },
    { person_profile_id: 215, anonymous_code: "ANON-N993", person_type: "identified", customer_name: "Lâm Chí Thành", customer_code: "KH0015", total_visits: 9, avg_duration_seconds: 660, total_spent: 1300000, score: 0.86, assigned_at: new Date().toISOString() },
  ],
  3: [
    { person_profile_id: 301, anonymous_code: "ANON-G111", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 2, avg_duration_seconds: 90, total_spent: 0, score: 0.65, assigned_at: new Date().toISOString() },
    { person_profile_id: 302, anonymous_code: "ANON-H222", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 1, avg_duration_seconds: 45, total_spent: 0, score: 0.61, assigned_at: new Date().toISOString() },
    { person_profile_id: 303, anonymous_code: "ANON-I333", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 3, avg_duration_seconds: 180, total_spent: 0, score: 0.68, assigned_at: new Date().toISOString() },
    { person_profile_id: 304, anonymous_code: "ANON-J444", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 2, avg_duration_seconds: 120, total_spent: 0, score: 0.64, assigned_at: new Date().toISOString() },
    { person_profile_id: 305, anonymous_code: "ANON-K555", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 1, avg_duration_seconds: 70, total_spent: 0, score: 0.62, assigned_at: new Date().toISOString() },
    { person_profile_id: 306, anonymous_code: "ANON-L666", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 2, avg_duration_seconds: 110, total_spent: 0, score: 0.63, assigned_at: new Date().toISOString() },
    { person_profile_id: 307, anonymous_code: "ANON-M777", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 1, avg_duration_seconds: 50, total_spent: 0, score: 0.60, assigned_at: new Date().toISOString() },
    { person_profile_id: 308, anonymous_code: "ANON-N888", person_type: "anonymous", customer_name: null, customer_code: null, total_visits: 3, avg_duration_seconds: 150, total_spent: 0, score: 0.67, assigned_at: new Date().toISOString() },
  ]
};

// ─── API Requests ──────────────────────────────────────

/**
 * Lấy danh sách tất cả nhóm khách hàng
 */
async function getMockSegments(): Promise<SegmentItem[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve([...mockSegments]);
    }, 400);
  });
}

/**
 * Lấy danh sách khách hàng thuộc một nhóm
 */
async function getMockSegmentMembers(
  segmentId: number,
  skip = 0,
  limit = 50
): Promise<SegmentMember[]> {
  return new Promise((resolve) => {
    setTimeout(() => {
      const list = mockMembersMap[segmentId] || [];
      resolve(list.slice(skip, skip + limit));
    }, 300);
  });
}

/**
 * Kích hoạt chạy thuật toán phân cụm AI (Giả lập ở Client)
 */
async function runMockClustering(
  nClusters = 3
): Promise<ClusteringResult> {
  return new Promise((resolve) => {
    setTimeout(() => {
      if (nClusters === 2) {
        mockSegments = [
          {
            id: 1,
            segment_name: "Khách hàng Giá trị cao",
            description: "Nhóm khách hàng có chi tiêu nhiều hoặc ghé thăm thường xuyên.",
            member_count: 23,
            avg_visits: 9.7,
            avg_duration: 690,
            avg_spent: 2015000,
            created_at: new Date().toISOString(),
          },
          {
            id: 2,
            segment_name: "Khách vãng lai",
            description: "Các khách hàng ghé thăm ít, hành vi duyệt ngắn.",
            member_count: 22,
            avg_visits: 1.8,
            avg_duration: 110,
            avg_spent: 50000,
            created_at: new Date().toISOString(),
          }
        ];
      } else {
        mockSegments = [
          {
            id: 1,
            segment_name: "Khách VIP - Giá trị cao",
            description: "Nhóm khách hàng trung thành, tần suất ghé thăm cao và có mức chi tiêu mua sắm lớn nhất.",
            member_count: 8,
            avg_visits: 12.5,
            avg_duration: 840,
            avg_spent: 4200000,
            created_at: new Date().toISOString(),
          },
          {
            id: 2,
            segment_name: "Khách tiềm năng - Duyệt nhiều",
            description: "Ghé thăm cửa hàng thường xuyên, đi qua nhiều khu vực nhưng mức chi tiêu còn hạn chế.",
            member_count: 15,
            avg_visits: 8.2,
            avg_duration: 620,
            avg_spent: 850000,
            created_at: new Date().toISOString(),
          },
          {
            id: 3,
            segment_name: "Khách vãng lai - Ít tương tác",
            description: "Nhóm khách vãng lai ghé thăm ít, thời gian ở lại ngắn và chưa phát sinh giao dịch lớn.",
            member_count: 22,
            avg_visits: 1.8,
            avg_duration: 110,
            avg_spent: 50000,
            created_at: new Date().toISOString(),
          }
        ];
      }

      resolve({
        segments_created: nClusters,
        total_customers_processed: 45,
        features_used: [
          "total_visits",
          "avg_duration",
          "max_duration",
          "total_orders",
          "total_spent"
        ],
        message: `Đã giả lập phân cụm K-Means thành công cho 45 khách hàng thành ${nClusters} nhóm.`
      });
    }, 1500);
  });
}

export async function getSegments(): Promise<SegmentItem[]> {
  return http.get<SegmentItem[]>("/segments/");
}

export async function getSegmentMembers(
  segmentId: number,
  skip = 0,
  limit = 50
): Promise<SegmentMember[]> {
  const members = await http.get<SegmentMember[]>(`/segments/${segmentId}/members`);
  return members.slice(skip, skip + limit);
}

export async function runClustering(
  nClusters = 3
): Promise<ClusteringResult> {
  return http.post<ClusteringResult>("/segments/run-clustering", {
    n_clusters: nClusters,
  });
}
