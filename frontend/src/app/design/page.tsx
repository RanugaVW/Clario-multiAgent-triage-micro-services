import { notFound } from 'next/navigation';
import { DesignShowcase } from './DesignShowcase';

export const metadata = { title: 'Design system', robots: { index: false } };

export default function DesignPage() {
  if (process.env.NODE_ENV === 'production') notFound();
  return <DesignShowcase />;
}
