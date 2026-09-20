'use client';

import { useState } from 'react';
import Link from 'next/link';
import { supabase } from '../../lib/supabase';
import { AUTH_LINK, AuthLayout } from '../../components/auth/AuthLayout';
import { Button } from '../../components/ui/Button';
import { FormField } from '../../components/ui/FormField';
import { Input, PasswordInput } from '../../components/ui/Input';
import { Notice } from '../../components/ui/Notice';
import { theme } from '../../theme/theme.config';

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

    const { error: signUpError } = await supabase.auth.signUp({
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
    <AuthLayout
      title="Create an account"
      description={`Start using ${theme.brand.name}. We will email you a link to confirm your address.`}
      footer={
        <>
          Already have an account?{' '}
          <Link href="/login" className={AUTH_LINK}>
            Sign in
          </Link>
        </>
      }
    >
      {success ? (
        <Notice tone="success" role="status" title="Check your email">
          We sent you a confirmation link. Confirm your address, then sign in.
          <div className="mt-4">
            <Link href="/login" className={AUTH_LINK}>
              Return to sign in
            </Link>
          </div>
        </Notice>
      ) : (
        <form onSubmit={handleRegister} className="flex flex-col gap-5">
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

          <FormField label="Password (min 6 characters)">
            {(field) => (
              <PasswordInput
                {...field}
                required
                minLength={6}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </FormField>

          <Button type="submit" size="lg" disabled={loading} className="w-full">
            {loading ? 'Creating account…' : 'Create account'}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
