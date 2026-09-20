import type { Metadata, Viewport } from "next";
import { Inter, Poppins, Anek_Kannada, Anek_Devanagari } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"], display: "swap" });
// the logo's geometric wordmark
const poppins = Poppins({ variable: "--font-poppins", subsets: ["latin"], weight: ["600"], display: "swap" });
const anekKn = Anek_Kannada({ variable: "--font-anek-kn", subsets: ["kannada"], display: "swap" });
const anekDv = Anek_Devanagari({ variable: "--font-anek-dv", subsets: ["devanagari"], display: "swap" });

const description =
  "Block-level 1–4 week monsoon outlook for India: onset, dry spells and heavy rain, turned into crop advice farmers receive on WhatsApp in their own language.";

export const metadata: Metadata = {
  metadataBase: new URL("https://mungaru.vercel.app"),
  title: { default: "Mungaru — Monsoon Risk Observatory", template: "%s · Mungaru" },
  description,
  applicationName: "Mungaru",
  openGraph: { title: "Mungaru — Rain · Resilient · Rural", description, images: ["/brand/badge-640.png"], type: "website" },
  twitter: { card: "summary", title: "Mungaru — Monsoon Risk Observatory", description, images: ["/brand/badge-640.png"] },
};

export const viewport: Viewport = {
  themeColor: "#060a12",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${poppins.variable} ${anekKn.variable} ${anekDv.variable} h-full`}>
      <body className="h-full overflow-hidden">{children}</body>
    </html>
  );
}
