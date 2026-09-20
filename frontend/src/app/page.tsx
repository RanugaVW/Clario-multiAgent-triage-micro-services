import type { Metadata } from 'next';
import { Agents } from '../components/landing/Agents';
import { Cta } from '../components/landing/Cta';
import { Footer } from '../components/landing/Footer';
import { Hero } from '../components/landing/Hero';
import { HowItWorks } from '../components/landing/HowItWorks';
import { HumanReview } from '../components/landing/HumanReview';
import { LandingMotion } from '../components/landing/LandingMotion';
import { Nav } from '../components/landing/Nav';
import { Privacy } from '../components/landing/Privacy';
import { theme } from '../theme/theme.config';

export const metadata: Metadata = {
  title: `${theme.brand.name}: specialist AI agents for support tickets`,
  description: theme.brand.description,
};

export default function Home() {
  return (
    <LandingMotion>
      <a
        href="#main"
        className="sr-only rounded-md bg-surface px-4 py-2 text-app text-fg focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      <Nav />
      <main id="main">
        <Hero />
        <Agents />
        <HowItWorks />
        <HumanReview />
        <Privacy />
        <Cta />
      </main>
      <Footer />
    </LandingMotion>
  );
}
