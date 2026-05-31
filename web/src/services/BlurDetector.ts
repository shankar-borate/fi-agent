/**
 * Blur detection using the Laplacian edge-variance method.
 *
 * Algorithm:
 *   1. Draw the image on a small (320×240) canvas to keep computation fast.
 *   2. Convert to grayscale via luminance formula.
 *   3. Apply a discrete 3×3 Laplacian kernel to every interior pixel.
 *   4. Return the root-mean-square of all Laplacian values.
 *
 * Interpretation:
 *   - Score  >  80  → sharp
 *   - Score  40–80  → acceptable
 *   - Score  <  40  → blurry — request retake
 *
 * The threshold is configurable via the `threshold` parameter.
 */
export class BlurDetector {
  private static readonly SAMPLE_W = 320;
  private static readonly SAMPLE_H = 240;

  /** Returns the Laplacian RMS score for a Blob image. */
  static async score(blob: Blob): Promise<number> {
    const bmp = await createImageBitmap(blob);

    const canvas = document.createElement('canvas');
    canvas.width  = this.SAMPLE_W;
    canvas.height = this.SAMPLE_H;
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(bmp, 0, 0, this.SAMPLE_W, this.SAMPLE_H);
    bmp.close();

    const { data } = ctx.getImageData(0, 0, this.SAMPLE_W, this.SAMPLE_H);
    const W = this.SAMPLE_W;
    const H = this.SAMPLE_H;

    // Grayscale
    const gray = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) {
      const r = data[i * 4];
      const g = data[i * 4 + 1];
      const b = data[i * 4 + 2];
      gray[i] = 0.299 * r + 0.587 * g + 0.114 * b;
    }

    // Laplacian (4-neighbour discrete) variance
    let sumSq = 0;
    let count = 0;
    for (let y = 1; y < H - 1; y++) {
      for (let x = 1; x < W - 1; x++) {
        const c = gray[y * W + x];
        const lap =
          gray[(y - 1) * W + x] +
          gray[(y + 1) * W + x] +
          gray[y * W + (x - 1)] +
          gray[y * W + (x + 1)] -
          4 * c;
        sumSq += lap * lap;
        count++;
      }
    }
    return count > 0 ? Math.sqrt(sumSq / count) : 0;
  }

  /** Returns true when the image is too blurry to use. */
  static async isBlurry(blob: Blob, threshold: number): Promise<boolean> {
    const s = await this.score(blob);
    return s < threshold;
  }
}
