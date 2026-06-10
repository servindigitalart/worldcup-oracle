import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const DATA_DIR = resolve(process.cwd(), 'src', 'data');

export function loadJson<T>(filename: string, fallback: T): T {
  const path = resolve(DATA_DIR, filename);
  if (!existsSync(path)) return fallback;
  try {
    const parsed = JSON.parse(readFileSync(path, 'utf-8'));
    return parsed ?? fallback;
  } catch {
    return fallback;
  }
}
