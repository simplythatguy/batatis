/** Crop transparent canvas pixels without retaining the full signing pad. */
export function inkBounds(data: Uint8ClampedArray, width: number, height: number): { x: number; y: number; width: number; height: number } | null {
  let left = width, right = -1, top = height, bottom = -1;
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if (data[(y * width + x) * 4 + 3] === 0) continue;
    left = Math.min(left, x); right = Math.max(right, x); top = Math.min(top, y); bottom = Math.max(bottom, y);
  }
  return right < left ? null : { x: left, y: top, width: right - left + 1, height: bottom - top + 1 };
}
export function signatureImage(canvas: HTMLCanvasElement): string {
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("The signing pad isn’t available. Try typing your signature.");
  const bounds = inkBounds(ctx.getImageData(0, 0, canvas.width, canvas.height).data, canvas.width, canvas.height);
  if (!bounds) throw new Error("Draw or type your signature first.");
  const crop = document.createElement("canvas");
  crop.width = bounds.width + 12; crop.height = bounds.height + 12;
  crop.getContext("2d")?.drawImage(canvas, bounds.x, bounds.y, bounds.width, bounds.height, 6, 6, bounds.width, bounds.height);
  let png = crop.toDataURL("image/png");
  while ((png.length - png.indexOf(",") - 1) * 3 / 4 > 200 * 1024 && crop.width > 64) {
    const smaller = document.createElement("canvas");
    smaller.width = Math.max(1, Math.floor(crop.width * .75)); smaller.height = Math.max(1, Math.floor(crop.height * .75));
    smaller.getContext("2d")?.drawImage(crop, 0, 0, smaller.width, smaller.height);
    crop.width = smaller.width; crop.height = smaller.height;
    crop.getContext("2d")?.drawImage(smaller, 0, 0);
    png = crop.toDataURL("image/png");
  }
  if ((png.length - png.indexOf(",") - 1) * 3 / 4 > 200 * 1024) throw new Error("This signature is too large. Clear it and sign again.");
  return png;
}
export function albertaDate(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/Edmonton", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
}
