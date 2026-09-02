import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { animate, motion, useDragControls, useMotionValue, useTransform } from 'motion/react';
import { useKeyboardInset } from '../hooks/use-keyboard-inset';

type SnapSheetProps = {
  /** Visible-height fractions of the frame, ascending (e.g. [0.34, 0.62, 1]). */
  snaps: number[];
  activeIndex: number;
  onActiveIndexChange: (index: number) => void;
  /** Accessible name for the sheet region. */
  label: string;
  /** Day label shown in the drag header (e.g. "Hoy"). Replaces the default handle bar. */
  headerLabel?: string;
  /**
   * Layer behind the sheet that fills exactly the space the sheet leaves
   * free (the video base). Its height tracks the sheet's live position,
   * including while dragging.
   */
  above?: ReactNode;
  className?: string;
  children: ReactNode;
};

/**
 * Bottom sheet with drag-to-snap built on Motion. The sheet is a full-height
 * layer translated down by `frameHeight * (1 - snap)`; only the top `snap`
 * fraction is visible, so the video base layer shows through the rest.
 *
 * Dragging starts from the handle only (dragControls), which keeps the inner
 * scrollable transcript free of gesture conflicts. Settling projects the
 * release velocity onto the nearest snap point.
 *
 * (Replaced a vaul drawer: its initial snap effect raced on mount and left
 * the sheet hidden at the CSS initial transform.)
 */
const SHEET_CORNER_RADIUS_PX = 32;
export function SnapSheet({
  snaps,
  activeIndex,
  onActiveIndexChange,
  label,
  headerLabel,
  above,
  className = '',
  children,
}: SnapSheetProps) {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const readyRef = useRef(false);
  const dragControls = useDragControls();
  const [frameHeight, setFrameHeight] = useState(0);
  const [ready, setReady] = useState(false);
  const keyboardInset = useKeyboardInset();

  const offsets = useMemo(
    () => snaps.map((snap) => frameHeight * (1 - snap)),
    [snaps, frameHeight],
  );

  useEffect(() => {
    const parent = wrapperRef.current?.parentElement;
    if (!parent) return;
    const measure = () => setFrameHeight(parent.clientHeight);
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(parent);
    return () => observer.disconnect();
  }, []);

  const y = useMotionValue(0);
  // Extend past the sheet top by the corner radius so video fills the curved
  // cutouts in the sheet's rounded border (otherwise the frame bg shows through).
  const aboveHeight = useTransform(y, (value) => Math.max(0, value + SHEET_CORNER_RADIUS_PX));

  // First measurement: start hidden below the fold, then slide in.
  useEffect(() => {
    if (frameHeight <= 0 || readyRef.current) return;
    readyRef.current = true;
    y.set(frameHeight);
    setReady(true);
  }, [frameHeight, y]);

  useEffect(() => {
    if (!ready || frameHeight <= 0) return;
    const controls = animate(y, offsets[activeIndex] ?? 0, {
      type: 'spring',
      stiffness: 350,
      damping: 38,
    });
    return () => controls.stop();
  }, [ready, activeIndex, frameHeight, offsets, y]);

  const handleDragEnd = () => {
    const projected = y.get() + y.getVelocity() * 0.15;
    let best = 0;
    let bestDistance = Infinity;
    offsets.forEach((offset, index) => {
      const distance = Math.abs(offset - projected);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = index;
      }
    });
    onActiveIndexChange(best);
  };

  return (
    <motion.div
      ref={wrapperRef}
      className="absolute inset-x-0 bottom-0 z-20 h-full"
      initial={false}
      animate={ready ? { y: -keyboardInset } : { y: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 40 }}
    >
      {above && (
        <motion.div
          style={{ height: aboveHeight }}
          className="absolute -inset-x-8 top-0 overflow-hidden bg-black [&_video]:object-top"
        >
          {above}
        </motion.div>
      )}
      {ready && (
        <motion.div
          role="region"
          aria-label={label}
          style={{ y }}
          drag="y"
          dragListener={false}
          dragControls={dragControls}
          dragConstraints={{ top: 0, bottom: offsets[0] ?? 0 }}
          dragElastic={0.12}
          dragMomentum={false}
          onDragEnd={handleDragEnd}
          className={`text-content flex h-full w-full flex-col overflow-hidden rounded-t-[32px] border-t bg-white shadow-2xl sm:rounded-[32px] ${className}`}
        >
          <div
            onPointerDown={(event) => dragControls.start(event)}
            className="shrink-0 cursor-grab touch-none pt-3 pb-1 active:cursor-grabbing"
          >
            {headerLabel ? (
              <p className="font-heading text-content-small text-center text-xs font-semibold">
                {headerLabel}
              </p>
            ) : (
              <div className="bg-outline mx-auto h-1.5 w-12 rounded-full" aria-hidden="true" />
            )}
          </div>
          {children}
        </motion.div>
      )}
    </motion.div>
  );
}
