'use client';

import { useState } from 'react';
import { supabase } from '../../lib/supabase';
import { Mail, ArrowRight, KeyRound } from 'lucide-react';
import Link from 'next/link';
import { GlassPanel, GlassButton, GlassInput } from '../../components/ui';

// SRS 3.9.1 (Authentication Interface): "Forgot Password option". Sends a
// Supabase recovery email whose link lands on /reset-password.
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    if (resetError) {
      setError(resetError.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <GlassPanel tier={1} className="p-8 sm:p-12 w-full max-w-md animate-fade-in relative overflow-hidden">
        <div className="relative z-10">
          <div className="flex items-center space-x-3 mb-8">
            <div className="bg-[#2DD4BF]/15 p-3 rounded-2xl border border-[#2DD4BF]/25">
              <KeyRound className="text-[#2DD4BF] w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold text-[#ECECEC]">Reset password</h1>
          </div>

          {sent ? (
            <div role="status" className="bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 text-[#2DD4BF] p-6 rounded-2xl text-center">
              <h2 className="text-lg font-semibold mb-2">Check your email</h2>
              {/* Deliberately identical whether or not the address has an account,
                  so this form can't be used to discover who is registered. */}
              <p className="text-sm mb-6">
                If an account exists for that address, we&apos;ve sent a link to reset your password.
              </p>
              <Link href="/login" className="text-[#2DD4BF] hover:text-[#5eead4] font-medium underline">
                Return to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-6">
              <p className="text-sm text-[#8A8F98]">
                Enter the email address for your account and we&apos;ll send you a link to choose a new password.
              </p>

              {error && (
                <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="forgot-email" className="block text-sm font-medium text-[#8A8F98] mb-2">Email address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <GlassInput
                    id="forgot-email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10"
                    placeholder="you@example.com"
                  />
                </div>
              </div>

              <GlassButton type="submit" variant="primary" disabled={loading} className="w-full">
                <span>{loading ? 'Sending…' : 'Send reset link'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </GlassButton>

              <div className="text-center mt-4">
                <Link href="/login" className="text-sm text-[#8A8F98] hover:text-[#ECECEC] transition-colors">
                  Back to sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </GlassPanel>
    </main>
  );
}
