export type ApiResponse<T> = {
  status?: "success" | "error";
  success?: boolean;
  message: string;
  data: T;
  error_code?: string | null;
  details?: unknown;

  total?: number;
  skip?: number;
  limit?: number;

  meta?: {
    total?: number;
    skip?: number;
    limit?: number;
    page?: number;
    total_pages?: number;
  };
};
