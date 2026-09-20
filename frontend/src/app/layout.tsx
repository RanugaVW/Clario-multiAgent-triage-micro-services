import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '../contexts/AuthContext';
import StoreProvider from '../components/StoreProvider';
import { monoFont, sansFont } from '../theme/fonts';
import { theme } from '../theme/theme.config';
import { ThemeProvider } from '../theme/ThemeProvider';
import { ThemeScript } from '../theme/ThemeScript';
import { ThemeStyle } from '../theme/ThemeStyle';

export const metadata: Metadata = {
  title: `${theme.brand.name} - AI Support Triage`,
  description: 'Submit and track support tickets with AI-powered triage.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // suppressHydrationWarning: ThemeScript sets data-theme before React hydrates, on purpose.
    // The font variables sit on <html> so the :root rule in ThemeStyle can reference them.
    <html lang="en" suppressHydrationWarning className={`${sansFont.variable} ${monoFont.variable}`}>
      <head>
        <ThemeStyle />
        <ThemeScript />
      </head>
      <body className="font-sans antialiased">
        <ThemeProvider>
          <StoreProvider>
            <AuthProvider>
              {children}
            </AuthProvider>
          </StoreProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
