import type { NodeSocketType } from "../../types";

export const SOCKET_COLORS: Record<NodeSocketType, string> = {
  scalar: "#f2b84b",
  field: "#4dd6b0",
  color: "#ff6ec7",
};

// Categories are whatever the backend node registry reports, so pick a deterministic
// accent color from the string itself rather than hardcoding a fixed category list.
export function categoryColor(category: string): string {
  let hash = 0;
  for (let i = 0; i < category.length; i++) {
    hash = (hash * 31 + category.charCodeAt(i)) >>> 0;
  }
  const hue = hash % 360;
  return `hsl(${hue}, 65%, 60%)`;
}
