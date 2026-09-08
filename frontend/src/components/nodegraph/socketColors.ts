import type { NodeSocketType } from "../../types";

// Colors match the WLED-X socket legend (scalar=gold, field=cyan, color=magenta,
// vec3=violet); each socket type also gets a distinct handle shape in
// EffectNode.css, since "socket shape carries type" is a house rule -- shape
// should read even without color.
export const SOCKET_COLORS: Record<NodeSocketType, string> = {
  scalar: "#ffc93c",
  field: "#22e1ff",
  color: "#ff2e88",
  vec3: "#8b5cf6",
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
