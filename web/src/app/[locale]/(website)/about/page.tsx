import { useTranslations } from "next-intl";
import AnimatedBackground from "@/components/website/AnimatedBackground";

export default function AboutUsPage() {
  const t = useTranslations("website");

  return (
    <AnimatedBackground>
      <section className="mx-auto flex max-w-3xl flex-col gap-6 py-8">
        <h1 className="text-3xl font-bold">{t("aboutTitle")}</h1>
        <p className="text-muted-foreground text-lg">{t("aboutText")}</p>
        <div className="border-border bg-card text-card-foreground mt-4 rounded-xl border p-6">
          <h2 className="mb-2 text-xl font-semibold">{t("aboutMission")}</h2>
          <p className="text-muted-foreground">{t("aboutMissionText")}</p>
        </div>
      </section>
    </AnimatedBackground>
  );
}
