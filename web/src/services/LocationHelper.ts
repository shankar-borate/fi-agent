import { FiLog } from './FiLog';
import { GeoPoint } from '../domain/models';

/**
 * Wraps the browser Geolocation API with a two-phase fallback strategy:
 *
 *  Phase 1 — high-accuracy (GPS / WiFi, 8 s timeout)
 *  Phase 2 — network / IP fallback (15 s timeout, cached position allowed)
 *
 * Returns null when:
 *  - The API is unavailable (older browser)
 *  - The page is served over plain HTTP on a non-localhost origin
 *    (browsers block geolocation on insecure origins)
 *  - The user denied the location permission prompt
 *  - Both phases timed out
 */
export class LocationHelper {

  async getLocation(): Promise<GeoPoint | null> {
    if (!navigator.geolocation) {
      FiLog.w('Location', 'Geolocation API not available in this browser');
      return null;
    }

    // Phase 1: try high-accuracy (GPS / WiFi triangulation)
    const highAccuracy = await this._request(true, 8_000);
    if (highAccuracy) return highAccuracy;

    FiLog.w('Location', 'High-accuracy failed — trying network/IP fallback');

    // Phase 2: accept lower accuracy and a cached position (up to 30 s old)
    return this._request(false, 15_000, 30_000);
  }

  // ── Private ──────────────────────────────────────────────────────────────

  private _request(
    highAccuracy: boolean,
    timeoutMs:    number,
    maxAgeMs:     number = 0,
  ): Promise<GeoPoint | null> {
    return new Promise((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const gp: GeoPoint = {
            latitude:  pos.coords.latitude,
            longitude: pos.coords.longitude,
            timestamp: new Date(pos.timestamp).toISOString(),
          };
          FiLog.i('Location',
            `GPS OK — ${gp.latitude.toFixed(5)}, ${gp.longitude.toFixed(5)}` +
            `  acc=${pos.coords.accuracy?.toFixed(0) ?? '?'}m  highAcc=${highAccuracy}`);
          resolve(gp);
        },
        (err) => {
          const reasons: Record<number, string> = {
            1: 'Permission denied by user',
            2: 'Position unavailable (no GPS / network signal)',
            3: `Timed out after ${timeoutMs / 1000}s`,
          };
          FiLog.w('Location',
            `GPS error (highAcc=${highAccuracy}): ${reasons[err.code] ?? err.message}`);
          resolve(null);
        },
        {
          enableHighAccuracy: highAccuracy,
          timeout:            timeoutMs,
          maximumAge:         maxAgeMs,
        },
      );
    });
  }
}
