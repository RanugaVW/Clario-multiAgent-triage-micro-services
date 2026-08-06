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
        router.push('/');
      }
    }
    setLoading(false);
  };

  return (
    <main className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      {/* 3D Wave Background */}
      <iframe 
        src="/landing.html?bgOnly=true" 
        className="absolute inset-0 w-full h-full border-none pointer-events-auto"
        style={{ zIndex: 0 }}
      />
      
      <div className="glass-panel p-8 sm:p-12 rounded-3xl w-full max-w-md animate-fade-in relative overflow-hidden" style={{ zIndex: 10 }}>
        {/* Background elements */}
        <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none">
          <Shield className="w-48 h-48" />
        </div>

        <div className="relative z-10">
          <div className="flex items-center space-x-3 mb-8">
            <div className="bg-indigo-500/20 p-3 rounded-2xl border border-indigo-500/30">
              <Shield className="text-indigo-400 w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold text-white">Sign In to Clario</h1>
          </div>

          <form onSubmit={handleLogin} className="space-y-6">
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm p-3 rounded-xl">
                {error}
              </div>
            )}

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Email Address</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <Mail className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="glass-input w-full pl-10 pr-4 py-3 rounded-xl text-sm"
                  placeholder="agent@clario.com"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Password</label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                  <KeyRound className="h-5 w-5 text-slate-400" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="glass-input w-full pl-10 pr-4 py-3 rounded-xl text-sm"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-indigo-500 to-sky-500 hover:from-indigo-400 hover:to-sky-400 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(99,102,241,0.3)] hover:shadow-[0_0_30px_rgba(99,102,241,0.5)] flex items-center justify-center space-x-2 disabled:opacity-50"
            >
              <span>{loading ? 'Authenticating...' : 'Sign In'}</span>
              {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
            </button>
          </form>

          <div className="mt-8 text-center text-sm text-slate-400">
            <p className="mb-2">Role is automatically assigned from your database profile.</p>
            <p>
              Need an account?{' '}
              <a href="/register" className="text-indigo-400 hover:text-indigo-300 transition-colors">
                Register here
              </a>
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
