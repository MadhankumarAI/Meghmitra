/**
 * Mungaru brand: the cloud-leaf-rain mark from the logo (public/brand, cut from act_1/dp.png)
 * on its cream tile, and the wordmark. One place, so every surface shows the same identity.
 */
/* eslint-disable @next/next/no-img-element -- small static brand assets */

export const BRAND = {
  name: "Mungaru",
  tagline: "Rain · Resilient · Rural",
  promise: "Forecast. Advise. Farm better.",
  cream: "#f7efe0",
  green: "#1f4a33",
};

export function BrandMark({ size = 36, className = "" }: { size?: number; className?: string }) {
  return (
    <span className={`inline-grid shrink-0 place-items-center rounded-[28%] bg-[#f7efe0] shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] ${className}`}
      style={{ width: size, height: size }}>
      <img src="/brand/mark.png" alt="" width={size * 0.8} height={size * 0.8} draggable={false} />
    </span>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return <span className={`font-brand font-semibold tracking-[-0.01em] ${className}`}>{BRAND.name}</span>;
}
