export const APP_CONFIG = {
  name: "AI Customer Analysis",
  version: "1.0.0",
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  pagination: {
    defaultLimit: 10,
    limitOptions: [10, 20, 50],
  },
  upload: {
    maxSizeMB: 5,
    acceptedImageTypes: ["image/jpeg", "image/png", "image/webp"],
  },
} as const;
