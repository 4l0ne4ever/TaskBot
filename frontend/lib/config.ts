export const API_BASE_URL =
  typeof window !== "undefined"
    ? process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000"
    : process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
