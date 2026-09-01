import type { ComponentPropsWithoutRef, ReactNode } from 'react';

/** Apply directly to any element for the frosted glass effect. */
export const CRYSTAL_CLASS = 'crystal';
export const CRYSTAL_DARK_CLASS = 'crystal-dark';
export const CRYSTAL_DARK_STRONG_CLASS = 'crystal-dark-strong';

type CrystalVariant = 'light' | 'dark';
type CrystalShape = 'pill' | 'rounded' | 'circle';
type CrystalSize = 'sm' | 'md' | 'lg' | 'auto';

interface CrystalProps extends ComponentPropsWithoutRef<'div'> {
  children: ReactNode;
  variant?: CrystalVariant;
  shape?: CrystalShape;
  size?: CrystalSize;
}

const shapeClasses: Record<CrystalShape, string> = {
  pill: 'rounded-full',
  rounded: 'rounded-sm',
  circle: 'aspect-square rounded-full',
};

const sizeClasses: Record<CrystalSize, string> = {
  sm: 'inline-flex h-9 min-w-9 items-center justify-center p-2',
  md: 'inline-flex h-11 min-w-11 items-center justify-center p-2.5',
  lg: 'inline-flex h-14 min-w-14 items-center justify-center p-3',
  auto: 'inline-flex items-center justify-center p-3',
};

export function Crystal({
  children,
  variant = 'light',
  shape = 'pill',
  size = 'md',
  className = '',
  ...props
}: CrystalProps) {
  const baseClass = variant === 'dark' ? CRYSTAL_DARK_CLASS : CRYSTAL_CLASS;

  return (
    <div
      className={`${baseClass} ${shapeClasses[shape]} ${sizeClasses[size]} ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}
