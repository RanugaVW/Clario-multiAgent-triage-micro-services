import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Trash2 } from 'lucide-react';

export default function ShakeButton({ onDelete }: { onDelete: (e: React.MouseEvent) => void }) {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <motion.button
      type="button"
      onClick={onDelete}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.96 }}
      className="relative flex h-9 cursor-pointer items-center justify-center rounded-pill border border-border bg-surface px-6 text-fg transition-colors duration-150 hover:bg-surface-raised"
    >
      <div className="relative w-[16px] h-[16px] flex items-center justify-center shrink-0">
        <motion.div
          animate={{
            y: isHovered ? [0, -2, 0, -2, 0] : 0,
            rotate: isHovered ? [0, -10, 10, -10, 0] : 0
          }}
          transition={{ duration: 0.4 }}
        >
          <Trash2 className="h-4 w-4 text-danger" />
        </motion.div>
      </div>
      <span className="ml-2.5 text-small font-medium tracking-tight text-danger">Delete</span>
    </motion.button>
  );
}
