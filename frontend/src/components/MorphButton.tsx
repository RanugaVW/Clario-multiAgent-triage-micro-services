import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Copy, Check } from 'lucide-react';

export default function MorphButton({ textToCopy, label = "Copy Hash" }: { textToCopy: string, label?: string }) {
  const [hasCopied, setHasCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    navigator.clipboard.writeText(textToCopy);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2000);
  };

  return (
    <motion.button
      type="button"
      onClick={handleCopy}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.96 }}
      className="relative flex h-9 cursor-pointer items-center justify-center rounded-pill border border-border bg-surface px-6 text-fg transition-colors duration-150 hover:bg-surface-raised"
    >
      <div className="relative w-[16px] h-[16px] flex items-center justify-center shrink-0">
        <AnimatePresence mode="popLayout" initial={false}>
          {!hasCopied ? (
            <motion.div
              key="icon1"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: "spring", stiffness: 600, damping: 25 }}
              className="absolute inset-0 flex items-center justify-center"
            >
              <Copy className="w-4 h-4" />
            </motion.div>
          ) : (
            <motion.div
              key="icon2"
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.5, opacity: 0 }}
              transition={{ type: "spring", stiffness: 600, damping: 25 }}
              className="absolute inset-0 flex items-center justify-center text-success"
            >
              <Check className="w-4 h-4" />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      <span className="ml-2.5 text-small font-medium tracking-tight">
        {hasCopied ? "Copied" : label}
      </span>
    </motion.button>
  );
}
