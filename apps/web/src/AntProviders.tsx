import { StyleProvider } from "@ant-design/cssinjs";
import { ConfigProvider, type ThemeConfig } from "antd";
import type { ReactNode } from "react";

// Colours are chosen for WCAG AA contrast on white (Ant Design's defaults, for example the
// blue primary and the light grey secondary text, are below 4.5:1). Contrast cannot be
// measured in jsdom, so a browser check (axe in Playwright) must confirm them later.
const baseTheme: ThemeConfig = {
  token: {
    colorPrimary: "#4338ca",
    colorLink: "#3730a3",
    colorText: "#0f172a",
    colorTextSecondary: "#334155",
    colorTextDescription: "#475569",
    colorTextPlaceholder: "#64748b",
    colorBorder: "#64748b",
    colorError: "#b91c1c",
    colorSuccess: "#166534",
    borderRadius: 6,
    fontFamily: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  },
  components: {
    Layout: { headerBg: "#0f172a", headerColor: "#ffffff", headerPadding: "0 16px" },
  },
};

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/**
 * Ant Design needs two settings from us:
 * - `layer`: its styles go into a CSS cascade layer that sits between Tailwind's reset and
 *   Tailwind's utilities (order declared in index.css), so neither overrides the other.
 * - `motion`: animations are switched off for people who asked for reduced motion.
 */
export function AntProviders({ children }: { children: ReactNode }) {
  const theme: ThemeConfig = {
    ...baseTheme,
    token: { ...baseTheme.token, motion: !prefersReducedMotion() },
  };
  return (
    <StyleProvider layer>
      <ConfigProvider theme={theme}>{children}</ConfigProvider>
    </StyleProvider>
  );
}
