'use client';

import { useState } from 'react';
import { supabase } from '../../lib/supabase';
import { Mail, KeyRound, ArrowRight, UserPlus } from 'lucide-react';
import Link from 'next/link';
import { GlassPanel, GlassButton, GlassInput } from '../../components/ui';

export default function Register() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { data, error: signUpError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: `${window.location.origin}/login`,
      }
    });

    if (signUpError) {
      setError(signUpError.message);
    } else {
      setSuccess(true);
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4">
      <GlassPanel tier={1} className="p-8 sm:p-12 w-full max-w-md animate-fade-in relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <UserPlus className="w-48 h-48" />
        </div>

        <div className="relative z-10">
          <div className="flex items-center space-x-3 mb-8">
            <div className="bg-[#2DD4BF]/15 p-3 rounded-2xl border border-[#2DD4BF]/25">
              <UserPlus className="text-[#2DD4BF] w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold text-[#ECECEC]">Create an account</h1>
          </div>

          {success ? (
            <div className="bg-[#2DD4BF]/10 border border-[#2DD4BF]/30 text-[#2DD4BF] p-6 rounded-2xl text-center">
              <h2 className="text-lg font-semibold mb-2">Check your email</h2>
              <p className="text-sm mb-6">We sent you a confirmation link. Confirm your address, then sign in.</p>
              <Link href="/login" className="text-[#2DD4BF] hover:text-[#5eead4] font-medium underline">
                Return to sign in
              </Link>
            </div>
          ) : (
            <form onSubmit={handleRegister} className="space-y-6">
              {error && (
                <div className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">
                  {error}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-[#8A8F98] mb-2">Email address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <GlassInput
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-10"
                    placeholder="agent@clario.com"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-[#8A8F98] mb-2">Password (min 6 characters)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <GlassInput
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-10"
                    placeholder="••••••••"
                  />
                </div>
              </div>

              <GlassButton type="submit" variant="primary" disabled={loading} className="w-full">
                <span>{loading ? 'Creating account…' : 'Create account'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </GlassButton>

              <div className="text-center mt-4">
                <Link href="/login" className="text-sm text-[#8A8F98] hover:text-[#ECECEC] transition-colors">
                  Already have an account? Sign in
                </Link>
              </div>
            </form>
          )}
        </div>
      </GlassPanel>
    </main>
  );
}
