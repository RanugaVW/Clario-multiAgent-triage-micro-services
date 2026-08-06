import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { AuthProvider } from '../contexts/AuthContext';
import StoreProvider from '../components/StoreProvider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Clario - AI Support Triage',
  description: 'Submit and track support tickets with AI-powered triage.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} antialiased`}>
        <StoreProvider>
          <AuthProvider>
            {children}
          </AuthProvider>
        </StoreProvider>
      </body>
    </html>
  );
}
