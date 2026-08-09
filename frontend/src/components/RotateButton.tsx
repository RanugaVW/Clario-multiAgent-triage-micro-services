import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { RefreshCw, Loader2 } from 'lucide-react';

interface RotateButtonProps {
  onClick?: () => void;
  isLoading?: boolean;
}

export default function RotateButton({ onClick, isLoading }: RotateButtonProps) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.button
      onClick={onClick}
      disabled={isLoading}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.96 }}
      className="relative flex items-center justify-center text-white h-[36px] px-6 rounded-[40px] bg-white/[0.04] hover:bg-white/[0.06] border border-white/5 cursor-pointer transition-colors duration-150 disabled:opacity-50"
    >
      <div className="relative w-[16px] h-[16px] flex items-center justify-center shrink-0">
        <motion.div
          animate={{ rotate: isHovered || isLoading ? 180 : 0 }}
          transition={{ 
            type: isLoading ? "tween" : "spring", 
            stiffness: 400, 
            damping: 25,
            repeat: isLoading ? Infinity : 0,
            duration: isLoading ? 1 : undefined,
            ease: "linear"
          }}
        >
          {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
        </motion.div>
      </div>
      <span className="font-medium tracking-tight text-[13px] ml-2.5">Reload</span>
    </motion.button>
  );
}
