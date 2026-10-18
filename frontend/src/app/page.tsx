import { Navbar } from "@/components/landing/Navbar";
import { HeroSection } from "@/components/landing/HeroSection";
import { VerifiedMetrics } from "@/components/landing/VerifiedMetrics";
import { ArchitectureExplorer } from "@/components/landing/ArchitectureExplorer";
import { BenchmarkComparison } from "@/components/landing/BenchmarkComparison";
import { ContactSection } from "@/components/landing/ContactSection";
import { Footer } from "@/components/landing/Footer";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-charcoal text-slate-100 flex flex-col selection:bg-brand-orange selection:text-white">
      <Navbar />
      <main className="flex-1">
        <HeroSection />
        <VerifiedMetrics />
        <ArchitectureExplorer />
        <BenchmarkComparison />
        <ContactSection />
      </main>
      <Footer />
    </div>
  );
}
