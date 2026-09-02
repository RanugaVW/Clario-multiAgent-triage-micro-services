'use client';

import { motion } from 'framer-motion';
import { useMemo } from 'react';

export function WavePhysicsLoader() {
  const numBars = 15;
  const barWidth = 12; 
  const barGap = 8; 
  const barTotalWidth = barWidth + barGap;
  
  const numFrames = 201;
  const B = 4; 
  const maxBounce = 60; 
  const baseBarH = 16;
  const wavePeakH = 48; 

  const { bars, ballX, ballY, ballScaleX, ballScaleY, times } = useMemo(() => {
    const barsData = Array.from({ length: numBars }).map(() => ({ 
      heights: [] as string[],
      colors: [] as string[],
    }));
    const bX: string[] = [];
    const bY: string[] = [];
    const bScaleX: number[] = [];
    const bScaleY: number[] = [];
    const tArr: number[] = [];
    
    for (let k = 0; k < numFrames; k++) {
      const t = k / (numFrames - 1);
      tArr.push(t);
      
      const x_frac = t < 0.5 ? t / 0.5 : (1 - t) / 0.5;
      const ball_idx = x_frac * (numBars - 1);
      
      bX.push(`${ball_idx * barTotalWidth}px`);
      
      let bounce_f = (x_frac * B) % 1.0;
      if (x_frac === 1 || x_frac === 0) bounce_f = 0;
      
      const bounce_h = 4 * bounce_f * (1 - bounce_f);
      const height_factor = Math.max(0, 1 - bounce_h * 2);
      
      const ball_indent = height_factor * 20; 
      const ball_y = (baseBarH + wavePeakH - ball_indent) + bounce_h * maxBounce;
      bY.push(`-${ball_y}px`);
      
      const squish = height_factor; 
      bScaleY.push(1 - squish * 0.3);
      bScaleX.push(1 + squish * 0.25);
      
      for (let i = 0; i < numBars; i++) {
        const dist = Math.abs(i - ball_idx);
        
        let wave_val = 0;
        if (dist < 3) {
          wave_val = Math.cos((dist / 3) * (Math.PI / 2));
        }
        
        let indent = 0;
        if (dist < 1.5) {
          const indent_dist = Math.cos((dist / 1.5) * (Math.PI / 2));
          indent = indent_dist * height_factor * 20;
        }
        
        const bar_h = baseBarH + wave_val * wavePeakH - indent;
        barsData[i].heights.push(`${Math.max(4, bar_h)}px`);

        // Idle bars sit as faint glass; the wave crest lights up gold.
        const r = Math.round(255 - wave_val * (255 - 232));
        const g = Math.round(255 - wave_val * (255 - 163));
        const b = Math.round(255 - wave_val * (255 - 61));
        const alpha = 0.12 + wave_val * 0.88;
        barsData[i].colors.push(`rgba(${r}, ${g}, ${b}, ${alpha})`);
      }
    }

    return { bars: barsData, ballX: bX, ballY: bY, ballScaleX: bScaleX, ballScaleY: bScaleY, times: tArr };
  }, []);

  return (
    <div className="relative flex flex-col items-center justify-center w-full scale-[0.6] sm:scale-75 md:scale-100">
      <div className="relative flex items-end justify-start h-48 space-x-2 w-[292px]">
        {bars.map((bar, i) => (
          <motion.div
            key={i}
            className="w-3 rounded-full origin-bottom"
            style={{ height: '16px', backgroundColor: 'rgba(255, 255, 255, 0.12)' }}
            animate={{
              height: bar.heights,
              backgroundColor: bar.colors,
            }}
            transition={{
              duration: 4,
              repeat: Infinity,
              times: times,
              ease: 'linear',
            }}
          />
        ))}
        
        <motion.div
          className="absolute w-3 h-3 rounded-full z-10"
          style={{
            bottom: 0,
            left: 0,
            transformOrigin: 'bottom center',
            background: 'linear-gradient(135deg, #E8A33D, #F4B856)',
            boxShadow: '0 0 12px rgba(232, 163, 61, 0.6)',
          }}
          animate={{
            x: ballX,
            y: ballY,
            scaleX: ballScaleX,
            scaleY: ballScaleY,
          }}
          transition={{
            duration: 4,
            repeat: Infinity,
            times: times,
            ease: 'linear',
          }}
        />
      </div>
    </div>
  );
}
