'use client';

import { useState } from 'react';
import { supabase } from '../../lib/supabase';
<<<<<<< HEAD
import { Mail, KeyRound, ArrowRight, UserPlus } from 'lucide-react';
import Link from 'next/link';
import { GlassPanel, GlassButton, GlassInput } from '../../components/ui';
=======
import { useRouter } from 'next/navigation';
import { Shield, KeyRound, Mail, ArrowRight, UserPlus } from 'lucide-react';
import Link from 'next/link';
>>>>>>> origin/add/voice-to-text-service

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

<<<<<<< HEAD
    const { error: signUpError } = await supabase.auth.signUp({
=======
    const { data, error: signUpError } = await supabase.auth.signUp({
>>>>>>> origin/add/voice-to-text-service
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
<<<<<<< HEAD
      <GlassPanel tier={1} className="p-8 sm:p-12 w-full max-w-md animate-fade-in relative overflow-hidden">
=======
      <div className="glass-panel p-8 sm:p-12 rounded-3xl w-full max-w-md animate-fade-in relative overflow-hidden">
>>>>>>> origin/add/voice-to-text-service
        <div className="absolute top-0 right-0 p-8 opacity-5">
          <UserPlus className="w-48 h-48" />
        </div>

        <div className="relative z-10">
          <div className="flex items-center space-x-3 mb-8">
<<<<<<< HEAD
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
=======
            <div className="bg-emerald-500/20 p-3 rounded-2xl border border-emerald-500/30">
              <UserPlus className="text-emerald-400 w-6 h-6" />
            </div>
            <h1 className="text-3xl font-bold text-white">Create an Account</h1>
          </div>

          {success ? (
            <div className="bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 p-6 rounded-2xl text-center">
              <h2 className="text-lg font-semibold mb-2">Registration Successful!</h2>
              <p className="text-sm mb-6">Please check your email to confirm your account before logging in.</p>
              <Link href="/login" className="text-emerald-300 hover:text-emerald-200 font-medium underline">
                Return to Login
>>>>>>> origin/add/voice-to-text-service
              </Link>
            </div>
          ) : (
            <form onSubmit={handleRegister} className="space-y-6">
              {error && (
<<<<<<< HEAD
                <div className="bg-[#FB7185]/10 border border-[#FB7185]/30 text-[#FB7185] text-sm p-3 rounded-xl">
=======
                <div className="bg-red-500/10 border border-red-500/30 text-red-400 text-sm p-3 rounded-xl">
>>>>>>> origin/add/voice-to-text-service
                  {error}
                </div>
              )}

              <div>
<<<<<<< HEAD
                <label className="block text-sm font-medium text-[#8A8F98] mb-2">Email address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <GlassInput
=======
                <label className="block text-sm font-medium text-slate-300 mb-2">Email Address</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <Mail className="h-5 w-5 text-slate-400" />
                  </div>
                  <input
>>>>>>> origin/add/voice-to-text-service
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
<<<<<<< HEAD
                    className="pl-10"
=======
                    className="glass-input w-full pl-10 pr-4 py-3 rounded-xl text-sm"
>>>>>>> origin/add/voice-to-text-service
                    placeholder="agent@clario.com"
                  />
                </div>
              </div>

              <div>
<<<<<<< HEAD
                <label className="block text-sm font-medium text-[#8A8F98] mb-2">Password (min 6 characters)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="h-5 w-5 text-[#8A8F98]" />
                  </div>
                  <GlassInput
=======
                <label className="block text-sm font-medium text-slate-300 mb-2">Password (Min 6 chars)</label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="h-5 w-5 text-slate-400" />
                  </div>
                  <input
>>>>>>> origin/add/voice-to-text-service
                    type="password"
                    required
                    minLength={6}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
<<<<<<< HEAD
                    className="pl-10"
=======
                    className="glass-input w-full pl-10 pr-4 py-3 rounded-xl text-sm"
>>>>>>> origin/add/voice-to-text-service
                    placeholder="••••••••"
                  />
                </div>
              </div>

<<<<<<< HEAD
              <GlassButton type="submit" variant="primary" disabled={loading} className="w-full">
                <span>{loading ? 'Creating account…' : 'Create account'}</span>
                {!loading && <ArrowRight className="w-4 h-4" />}
              </GlassButton>

              <div className="text-center mt-4">
                <Link href="/login" className="text-sm text-[#8A8F98] hover:text-[#ECECEC] transition-colors">
                  Already have an account? Sign in
=======
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-300 shadow-[0_0_20px_rgba(16,185,129,0.3)] hover:shadow-[0_0_30px_rgba(16,185,129,0.5)] flex items-center justify-center space-x-2 disabled:opacity-50"
              >
                <span>{loading ? 'Registering...' : 'Create Account'}</span>
                {!loading && <ArrowRight className="w-4 h-4 ml-2" />}
              </button>

              <div className="text-center mt-4">
                <Link href="/login" className="text-sm text-slate-400 hover:text-white transition-colors">
                  Already have an account? Sign In
>>>>>>> origin/add/voice-to-text-service
                </Link>
              </div>
            </form>
          )}
        </div>
<<<<<<< HEAD
      </GlassPanel>
=======
      </div>
>>>>>>> origin/add/voice-to-text-service
    </main>
  );
}
