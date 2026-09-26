import { AnimatePresence, animate, motion, useMotionValue, useReducedMotion, useTransform, type Variants } from "motion/react";
import { useEffect, type ReactNode } from "react";

/** Smooth "ease out quint" used across the app */
export const EASE = [0.22, 1, 0.36, 1] as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE } },
};

export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

/** Fades and lifts its content into place when it first renders */
export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: EASE, delay }}
    >
      {children}
    </motion.div>
  );
}

/** Container whose <StaggerItem> children appear one after another */
export function Stagger({ children, className, as = "div" }: { children: ReactNode; className?: string; as?: "div" | "ul" | "ol" }) {
  const Component = motion[as];
  return (
    <Component className={className} variants={staggerContainer} initial="hidden" animate="show">
      {children}
    </Component>
  );
}

export function StaggerItem({ children, className, as = "div" }: { children: ReactNode; className?: string; as?: "div" | "li" }) {
  const Component = motion[as];
  return (
    <Component className={className} variants={fadeUp}>
      {children}
    </Component>
  );
}

/** A number that counts up to its value (and animates when it changes) */
export function AnimatedNumber({ value }: { value: number }) {
  const reduced = useReducedMotion();
  const count = useMotionValue(reduced ? value : 0);
  const rounded = useTransform(count, (v) => Math.round(v).toLocaleString());
  useEffect(() => {
    if (reduced) {
      count.set(value);
      return;
    }
    const controls = animate(count, value, { duration: 0.9, ease: EASE });
    return () => controls.stop();
  }, [value, count, reduced]);
  return <motion.span>{rounded}</motion.span>;
}

/** Height + fade animation for content that opens and closes */
export function Collapse({ open, children }: { open: boolean; children: ReactNode }) {
  return (
    <AnimatePresence initial={false}>
      {open && (
        <motion.div
          key="content"
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ duration: 0.3, ease: EASE }}
          style={{ overflow: "hidden" }}
        >
          {children}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
