import Image from "next/image";
import { AnonymousChatBox } from "@/components/website/AnonymousChatBox";
import { RandomProductsSection } from "@/components/website/RandomProductsSection";
import AnimatedBackground from "@/components/website/AnimatedBackground";

export default function WebsiteHomePage() {
  return (
    <AnimatedBackground>
      <section className="flex flex-col items-center justify-center gap-6 py-4 text-center">
        <Image
          src="/main-page-logo.svg"
          alt="AskTea.ai"
          width={880}
          height={445}
          priority
          className="h-auto w-full max-w-md"
        />
      </section>
      <section className="py-10">
        <AnonymousChatBox />
      </section>
      <RandomProductsSection />
    </AnimatedBackground>
  );
}
