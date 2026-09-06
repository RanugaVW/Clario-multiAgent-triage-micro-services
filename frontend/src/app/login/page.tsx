'use client';

import { useState } from 'react';
import { supabase } from '../../lib/supabase';
import { useRouter } from 'next/navigation';
import { Shield, KeyRound, Mail, ArrowRight } from 'lucide-react';

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
      setError(signInError.message);
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
      {/* 3D Wave Background */}
      <iframe
        src="/landing.html?bgOnly=true"
        className="absolute inset-0 w-full h-full border-none pointer-events-none"
        style={{ zIndex: 0 }}
      />

      <div className="relative z-10 w-full max-w-md p-8 sm:p-10 rounded-[2.5rem] bg-white/[0.03] backdrop-blur-2xl border border-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.3)] animate-fade-in">
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
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-white/40 group-focus-within:text-[#E8A33D] transition-colors" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-2xl text-white placeholder-white/40 focus:bg-white/10 focus:border-[#E8A33D]/50 focus:ring-1 focus:ring-[#E8A33D]/50 transition-all outline-none backdrop-blur-sm"
                  placeholder="Email address"
                />
              </div>

              <div className="relative group">
                <div className="absolute inset-y-0 left-0 pl-4 flex items-center pointer-events-none">
                  <KeyRound className="h-5 w-5 text-white/40 group-focus-within:text-[#E8A33D] transition-colors" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-12 pr-4 py-3.5 bg-white/5 border border-white/10 rounded-2xl text-white placeholder-white/40 focus:bg-white/10 focus:border-[#E8A33D]/50 focus:ring-1 focus:ring-[#E8A33D]/50 transition-all outline-none backdrop-blur-sm"
                  placeholder="Password"
                />
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-white text-black hover:bg-gray-100 font-semibold py-3.5 px-6 rounded-2xl transition-all duration-300 flex items-center justify-center space-x-2 disabled:opacity-70 shadow-[0_0_20px_rgba(255,255,255,0.1)] hover:shadow-[0_0_30px_rgba(255,255,255,0.2)]"
              >
                <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
                {!loading && <ArrowRight className="w-5 h-5 ml-1" />}
              </button>
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
      </div>
    </main>
  );
}
