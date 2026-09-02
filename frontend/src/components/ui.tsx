'use client';

import { ReactNode } from 'react';
import { X } from 'lucide-react';

type Tier = 1 | 2;

const TIER_STYLES: Record<Tier, string> = {
  1: 'rounded-[28px] backdrop-blur-xl bg-white/[0.04] border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.35)]',
  2: 'rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08]',
};

export function GlassPanel({
  tier = 1,
  className = '',
  children,
  ...rest
}: {
  tier?: Tier;
  className?: string;
  children: ReactNode;
} & React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`${TIER_STYLES[tier]} ${className}`} {...rest}>
      {children}
    </div>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'destructive' | 'ghost';

const BUTTON_STYLES: Record<ButtonVariant, string> = {
  primary:
    'bg-gradient-to-r from-[#E8A33D] to-[#F4B856] text-[#08090D] shadow-[0_0_24px_rgba(232,163,61,0.35)] hover:shadow-[0_0_32px_rgba(232,163,61,0.5)]',
  secondary:
    'bg-white/[0.04] hover:bg-white/[0.08] text-[#ECECEC] border border-white/10',
  destructive:
    'bg-[#FB7185]/10 hover:bg-[#FB7185]/20 text-[#FB7185] border border-[#FB7185]/30',
  ghost:
    'bg-transparent hover:bg-white/[0.06] text-[#8A8F98] hover:text-[#ECECEC]',
};

export function GlassButton({
  variant = 'primary',
  className = '',
  children,
  ...rest
}: {
  variant?: ButtonVariant;
  className?: string;
  children: ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`inline-flex items-center justify-center gap-2 rounded-2xl px-6 py-3.5 font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed ${BUTTON_STYLES[variant]} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export function GlassInput({
  className = '',
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { className?: string }) {
  return (
    <input
      className={`glass-input w-full rounded-2xl px-4 py-3.5 text-sm placeholder-white/40 ${className}`}
      {...rest}
    />
  );
}

export function GlassTextarea({
  className = '',
  ...rest
}: React.TextareaHTMLAttributes<HTMLTextAreaElement> & { className?: string }) {
  return (
    <textarea
      className={`glass-input w-full rounded-2xl px-4 py-3.5 text-sm placeholder-white/40 resize-y ${className}`}
      {...rest}
    />
  );
}

type StatusTone = 'success' | 'warning' | 'danger' | 'neutral' | 'info';

const STATUS_STYLES: Record<StatusTone, string> = {
  success: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
  warning: 'bg-[#FB923C]/15 text-[#FB923C] border-[#FB923C]/25',
  danger: 'bg-[#FB7185]/15 text-[#FB7185] border-[#FB7185]/25',
  neutral: 'bg-white/[0.06] text-[#8A8F98] border-white/10',
  info: 'bg-[#2DD4BF]/15 text-[#2DD4BF] border-[#2DD4BF]/25',
};

export function StatusBadge({
  label,
  tone = 'neutral',
}: {
  label: string;
  tone?: StatusTone;
}) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${STATUS_STYLES[tone]}`}
    >
      {label}
    </span>
  );
}

export function Modal({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md rounded-[28px] backdrop-blur-xl bg-white/[0.05] border border-white/10 shadow-[0_8px_40px_rgba(0,0,0,0.5)] p-8 animate-fade-in">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-[#8A8F98] hover:text-[#ECECEC] transition-colors"
          aria-label="Close"
        >
          <X className="w-5 h-5" />
        </button>
        {children}
      </div>
    </div>
  );
}
