const ROOT = 'FiAgent';

export const FiLog = {
  v: (tag: string, msg: string)              => console.debug(`[${ROOT}/${tag}]`, msg),
  d: (tag: string, msg: string)              => console.debug(`[${ROOT}/${tag}]`, msg),
  i: (tag: string, msg: string)              => console.info (`[${ROOT}/${tag}]`, msg),
  w: (tag: string, msg: string)              => console.warn (`[${ROOT}/${tag}]`, msg),
  e: (tag: string, msg: string, err?: unknown) => console.error(`[${ROOT}/${tag}]`, msg, err ?? ''),
};
