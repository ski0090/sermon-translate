import { api } from "@/shared/api/index.js";

export const fetchYoutubeStatus = () => api("/api/youtube/status");
