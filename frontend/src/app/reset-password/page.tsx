'use client';

import { useEffect, useState } from 'react';
import { supabase } from '../../lib/supabase';
import { KeyRound, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { GlassPanel, GlassButton, PasswordInput } from '../../components/ui';

const MIN_LENGTH = 6;
const INPUT_CLASS = 'glass-input rounded-2xl px-4 py-3.5 text-sm placeholder-white/40 pl-10';

type Status = 'checking' | 'ready' | 'invalid' | 'done';

// Landing page for the link in the recovery email. Supabase turns that link into a
// short-lived session (event PASSWORD_RECOVERY); without one there is nothing this
// page is allowed to do, so it says so instead of showing a form that cannot work.
export default function ResetPassword() {
  const [status, setStatus] = useState<Status>('checking');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || (event === 'INITIAL_SESSION' && session)) {
        setStatus('ready');
      } else if (event === 'INITIAL_SESSION' && !session) {
        // Only "invalid" if a recovery event hasn't already made the form ready.
        setStatus((current) => (current === 'ready' ? current : 'invalid'));
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < MIN_LENGTH) {
      setError(`Password must be at least ${MIN_LENGTH} characters.`);
      return;
    }
    if (password !== confirm) {
      setError('The two passwords do not match.');
      return;
    }

    setLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    if (updateError) {
      setError(updateError.message);
      setLoading(false);
      return;
    }
    // The recovery session was only meant for this one change.
    await supabase.auth.signOut();
    setStatus('done');
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
            <h1 className="text-3xl font-bold text-[#ECECEC]">Choose a new password</h1>
          </div>

          {status === 'checking' && (
            <p role="status" className="text-sm text-[#8A8F98]">Verifying your reset link…</p>
          )}

          {status === 'invalid' && (
            <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] p-6 rounded-2xl text-center">
              <h2 className="text-lg font-semibold mb-2">This link is invalid or has expired</h2>
              <p className="text-sm mb-6">Reset links can only be used once and expire quickly. Request a new one to continue.</p>
              <Link href="/forgot-password" className="font-medium underline">Request a new link</Link>
            </div>
          )}

          {status === 'done' && (
            <div role="status" className="bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 text-[#2DD4BF] p-6 rounded-2xl text-center">
              <h2 className="text-lg font-semibold mb-2">Password updated</h2>
              <p className="text-sm mb-6">You can now sign in with your new password.</p>
              <Link href="/login" className="text-[#2DD4BF] hover:text-[#5eead4] font-medium underline">Go to sign in</Link>
            </div>
          )}

          {status === 'ready' && (
            <form onSubmit={handleSubmit} className="space-y-6">
              {error && (
                <div role="alert" className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="new-password" className="block text-sm font-medium text-[#8A8F98] mb-2">New password (min {MIN_LENGTH} characters)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <PasswordInput
                    id="new-password"
                    required
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className={INPUT_CLASS}
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="confirm-password" className="block text-sm font-medium text-[#8A8F98] mb-2">Confirm new password</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <PasswordInput
                    id="confirm-password"
                    required
                    autoComplete="new-password"
                    value={confirm}
                    onChange={(e) => setConfirm(e.target.value)}
                    className={INPUT_CLASS}
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <GlassButton type="submit" variant="primary" disabled={loading} className="w-full">
                <span>{loading ? 'Updating…' : 'Update password'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </GlassButton>
            </form>
          )}
        </div>
      </GlassPanel>
    </main>
  );
}
