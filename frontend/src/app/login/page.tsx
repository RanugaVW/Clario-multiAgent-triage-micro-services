'use client';

import { useState } from 'react';
import { supabase } from '../../lib/supabase';
import { useRouter } from 'next/navigation';
import { Shield, KeyRound, Mail, ArrowRight } from 'lucide-react';
import Link from 'next/link';
import { GlassPanel, GlassButton, GlassInput, PasswordInput } from '../../components/ui';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error: signInError, data } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (signInError) {
      // FR-043: a suspended/deactivated account is banned in Supabase Auth, whose message ("User is banned") is
      // unhelpful and reads like a fault - say what happened and what to do.
      setError(/banned/i.test(signInError.message)
        ? 'This account has been suspended or deactivated. Please contact an administrator.'
        : signInError.message);
    } else if (data?.user) {
      // Fetch the actual role from the DB
      const { data: userData } = await supabase
        .from('users')
        .select('role')
        .eq('id', data.user.id)
        .single();

      const role = userData?.role;

      if (role === 'admin') {
        router.push('/admin');
      } else if (role === 'agent') {
        router.push('/agent');
      } else {
        router.push('/dashboard');
      }
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* 3D Wave Background - purely decorative, hidden from assistive tech and keyboard focus */}
      <iframe
        src="/landing.html?bgOnly=true"
        className="absolute inset-0 w-full h-full border-none pointer-events-none"
        style={{ zIndex: 0 }}
        title="Decorative background animation"
        aria-hidden="true"
        tabIndex={-1}
      />

      <GlassPanel tier={1} className="relative z-10 w-full max-w-md p-8 sm:p-10 animate-fade-in overflow-hidden">
        {/* Background elements */}
        <div className="absolute -top-20 -right-20 p-8 opacity-10 pointer-events-none blur-3xl">
          <Shield className="w-64 h-64 text-[#E8A33D]" />
        </div>

        <div className="relative z-10">
          <div className="flex flex-col items-center mb-10 text-center">
            <div className="bg-white/5 p-4 rounded-3xl border border-white/10 mb-4 shadow-[0_0_20px_rgba(255,255,255,0.05)]">
              <Shield className="text-[#E8A33D] w-8 h-8" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Welcome back</h1>
            <p className="text-white/50 mt-2 text-sm">Please enter your details to sign in</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            {error && (
              <div className="bg-[#FB7185]/10 border border-[#FB7185]/20 text-[#FB7185] text-sm p-4 rounded-2xl flex items-center justify-center backdrop-blur-md">
                {error}
              </div>
            )}

            <div className="space-y-4">
              <div className="relative group">
                <label htmlFor="login-email" className="sr-only">Email address</label>
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-white/40 group-focus-within:text-[#E8A33D] transition-colors" />
                </div>
                <GlassInput
                  id="login-email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-12"
                  placeholder="Email address"
                />
              </div>

              <div className="relative group">
                <label htmlFor="login-password" className="sr-only">Password</label>
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <KeyRound className="h-5 w-5 text-white/40 group-focus-within:text-[#E8A33D] transition-colors" />
                </div>
                <PasswordInput
                  id="login-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="glass-input rounded-2xl px-4 py-3.5 text-sm placeholder-white/40 pl-12"
                  placeholder="Password"
                />
              </div>

              <div className="text-right -mt-1">
                <Link href="/forgot-password" className="text-sm text-white/60 hover:text-[#E8A33D] transition-colors underline underline-offset-4 decoration-white/20">
                  Forgot password?
                </Link>
              </div>
            </div>

            <div className="pt-2">
              <GlassButton type="submit" variant="primary" disabled={loading} className="w-full">
                <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </GlassButton>
            </div>
          </form>

          <div className="mt-8 text-center text-sm">
            <p className="text-white/40 mb-1">Role is automatically assigned from your profile.</p>
            <p className="text-white/60">
              Don&apos;t have an account?{' '}
              <a href="/register" className="text-white hover:text-[#E8A33D] font-medium transition-colors underline underline-offset-4 decoration-white/20">
                Create one now
              </a>
            </p>
          </div>
        </div>
      </GlassPanel>
    </main>
  );
}
