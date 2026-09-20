'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { supabase } from '../../lib/supabase';
import { AUTH_LINK, AuthLayout } from '../../components/auth/AuthLayout';
import { Button } from '../../components/ui/Button';
import { FormField } from '../../components/ui/FormField';
import { Input, PasswordInput } from '../../components/ui/Input';
import { Notice } from '../../components/ui/Notice';
import { theme } from '../../theme/theme.config';

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
    <AuthLayout
      title="Welcome back"
      description={`Sign in to your ${theme.brand.name} account. Your role is assigned from your profile.`}
      footer={
        <>
          Don&apos;t have an account?{' '}
          <Link href="/register" className={AUTH_LINK}>
            Create one now
          </Link>
        </>
      }
    >
      <form onSubmit={handleLogin} className="flex flex-col gap-5">
        {error && (
          <Notice tone="danger" role="alert">
            {error}
          </Notice>
        )}

        <FormField label="Email address">
          {(field) => (
            <Input
              {...field}
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          )}
        </FormField>

        <FormField label="Password">
          {(field) => (
            <PasswordInput
              {...field}
              required
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </FormField>

        <div className="-mt-1 text-right">
          <Link href="/forgot-password" className="text-app text-fg-muted underline underline-offset-4 transition-colors hover:text-fg">
            Forgot password?
          </Link>
        </div>

        <Button type="submit" size="lg" disabled={loading} className="w-full">
          {loading ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>
    </AuthLayout>
  );
}
