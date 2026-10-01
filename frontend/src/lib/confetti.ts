const COLORS = ["#5b5bf6", "#9a5cf5", "#c084fc", "#a5b4fc", "#f0abfc", "#34d399", "#fbbf24"];

/** A short burst of confetti (skipped when the user prefers reduced motion) */
export function celebrate(origin?: { x: number; y: number }) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const x = origin?.x ?? window.innerWidth / 2;
  const y = origin?.y ?? window.innerHeight / 3;
  const layer = document.createElement("div");
  layer.setAttribute("aria-hidden", "true");
  layer.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:100;overflow:hidden";
  document.body.appendChild(layer);

  for (let i = 0; i < 90; i++) {
    const piece = document.createElement("span");
    const width = 6 + Math.random() * 6;
    piece.style.cssText =
      `position:absolute;left:${x}px;top:${y}px;width:${width}px;height:${width * 0.45}px;` +
      `background:${COLORS[i % COLORS.length]};border-radius:2px;will-change:transform,opacity`;
    layer.appendChild(piece);
    const angle = Math.random() * Math.PI * 2;
    const speed = 160 + Math.random() * 320;
    const dx = Math.cos(angle) * speed;
    const dy = Math.sin(angle) * speed - 220;
    const spin = (Math.random() - 0.5) * 1080;
    piece.animate(
      [
        { transform: "translate(-50%, -50%) rotate(0deg)", opacity: 1 },
        { transform: `translate(${dx * 0.7}px, ${dy}px) rotate(${spin / 2}deg)`, opacity: 1, offset: 0.4 },
        { transform: `translate(${dx}px, ${dy + 560}px) rotate(${spin}deg)`, opacity: 0 },
      ],
      { duration: 1500 + Math.random() * 900, easing: "cubic-bezier(0.2, 0.6, 0.4, 1)", fill: "forwards" },
    );
  }
  window.setTimeout(() => layer.remove(), 2600);
}
