import type { Metadata, Viewport } from "next";
import FarmerView from "@/components/farmer/FarmerView";
import type { Lang } from "@/lib/i18n";

export const metadata: Metadata = { title: "Meghmitra — advice for your field" };
export const viewport: Viewport = { themeColor: "#ffffff" };

// The page a WhatsApp/SMS advisory links to: /f/<block_id>?lang=kn&crop=ragi&date=2023-06-22
export default async function Page(props: PageProps<"/f/[block]">) {
  const { block } = await props.params;
  const q = await props.searchParams;
  const one = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v);
  const lang = (["en", "kn", "hi"].includes(one(q.lang) ?? "") ? one(q.lang) : "kn") as Lang;
  return <FarmerView blockId={block} lang={lang} crop={one(q.crop)} date={one(q.date) ?? "2023-06-22"} />;
}
