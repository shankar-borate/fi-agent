/** Parses navigator.userAgent into structured device information. */
export interface DeviceInfo {
  userAgent:      string;
  browser:        string;   // e.g. "Chrome 124"
  os:             string;   // e.g. "Android 14", "iOS 17.4", "Windows 11"
  deviceType:     string;   // Mobile | Tablet | Desktop
  screenSize:     string;   // e.g. "390×844"
  language:       string;   // e.g. "en-IN"
}

export class DeviceDetector {
  static detect(): DeviceInfo {
    const ua  = navigator.userAgent;
    const raw = ua;

    return {
      userAgent:  raw,
      browser:    DeviceDetector._browser(ua),
      os:         DeviceDetector._os(ua),
      deviceType: DeviceDetector._type(ua),
      screenSize: `${screen.width}×${screen.height}`,
      language:   navigator.language || '',
    };
  }

  private static _browser(ua: string): string {
    // Order matters — check specific browsers before generic Chrome/Safari
    if (/EdgA?\/(\S+)/i.test(ua))   return `Edge ${RegExp.$1.split('.')[0]}`;
    if (/OPR\/(\S+)/i.test(ua))     return `Opera ${RegExp.$1.split('.')[0]}`;
    if (/SamsungBrowser\/(\S+)/i.test(ua)) return `Samsung Browser ${RegExp.$1.split('.')[0]}`;
    if (/CriOS\/(\S+)/i.test(ua))   return `Chrome iOS ${RegExp.$1.split('.')[0]}`;
    if (/FxiOS\/(\S+)/i.test(ua))   return `Firefox iOS ${RegExp.$1.split('.')[0]}`;
    if (/Chrome\/(\S+)/i.test(ua))  return `Chrome ${RegExp.$1.split('.')[0]}`;
    if (/Firefox\/(\S+)/i.test(ua)) return `Firefox ${RegExp.$1.split('.')[0]}`;
    if (/Version\/(\S+).*Safari/i.test(ua)) return `Safari ${RegExp.$1.split('.')[0]}`;
    if (/Safari/i.test(ua))         return 'Safari';
    return 'Unknown Browser';
  }

  private static _os(ua: string): string {
    if (/Android (\d+[\.\d]*)/i.test(ua))          return `Android ${RegExp.$1}`;
    if (/iPhone.*OS (\d+_\d+)/i.test(ua))           return `iOS ${RegExp.$1.replace('_', '.')}`;
    if (/iPad.*OS (\d+_\d+)/i.test(ua))             return `iPadOS ${RegExp.$1.replace('_', '.')}`;
    if (/Windows NT 10\.0/i.test(ua))               return 'Windows 10/11';
    if (/Windows NT (\d+\.\d+)/i.test(ua))          return `Windows ${RegExp.$1}`;
    if (/Mac OS X (\d+[_\.\d]*)/i.test(ua))         return `macOS ${RegExp.$1.replace(/_/g, '.')}`;
    if (/Linux/i.test(ua))                           return 'Linux';
    return 'Unknown OS';
  }

  private static _type(ua: string): string {
    if (/Tablet|iPad|PlayBook|Silk/i.test(ua))         return 'Tablet';
    if (/Mobi|Android|iPhone|iPod|IEMobile/i.test(ua)) return 'Mobile';
    return 'Desktop';
  }
}
