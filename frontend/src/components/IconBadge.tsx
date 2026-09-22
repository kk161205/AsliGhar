import type { ReactNode } from "react";

interface IconBadgeProps {
  children: ReactNode;
  tone?: "terracotta" | "rust" | "moss";
}

// A single shared "icon in a colored rounded square" treatment, used
// everywhere a Lucide icon stands for a feature or a stat, so every page
// that does this looks the same rather than each screen styling its own.
export default function IconBadge({ children, tone = "terracotta" }: IconBadgeProps) {
  const toneClass = tone === "terracotta" ? "" : ` icon-badge--${tone}`;
  return <span className={`icon-badge${toneClass}`}>{children}</span>;
}
