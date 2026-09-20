import type { Metadata } from "next";
import Science from "@/components/science/Science";

export const metadata: Metadata = {
  title: "Evidence — Mungaru",
  description: "How good the outlook is, scored only on years the model never saw.",
};

export default function Page() {
  return <Science />;
}
