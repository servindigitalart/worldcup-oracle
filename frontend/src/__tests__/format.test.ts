import { describe, it, expect } from 'vitest';
import {
  formatTeamName,
  formatPct,
  formatRps,
  formatOdds,
  formatDate,
  formatModelName,
  statusBadgeClass,
} from '../utils/format';

describe('formatTeamName', () => {
  it('capitalises simple slug', () => {
    expect(formatTeamName('argentina')).toBe('Argentina');
  });

  it('handles multi-word slug', () => {
    expect(formatTeamName('saudi_arabia')).toBe('Saudi Arabia');
  });

  it('uses override for united_states', () => {
    expect(formatTeamName('united_states')).toBe('United States');
  });

  it('uses override for cote_divoire', () => {
    expect(formatTeamName('cote_divoire')).toBe("Côte d'Ivoire");
  });

  it('uses override for south_korea', () => {
    expect(formatTeamName('south_korea')).toBe('South Korea');
  });

  it('returns empty string for empty input', () => {
    expect(formatTeamName('')).toBe('');
  });

  it('handles single-word slug', () => {
    expect(formatTeamName('brazil')).toBe('Brazil');
  });
});

describe('formatPct', () => {
  it('formats 0.5 as 50.0%', () => {
    expect(formatPct(0.5)).toBe('50.0%');
  });

  it('formats 1.0 as 100.0%', () => {
    expect(formatPct(1.0)).toBe('100.0%');
  });

  it('formats 0 as 0.0%', () => {
    expect(formatPct(0)).toBe('0.0%');
  });

  it('returns dash for null', () => {
    expect(formatPct(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatPct(undefined)).toBe('—');
  });

  it('returns dash for NaN', () => {
    expect(formatPct(NaN)).toBe('—');
  });

  it('respects decimals parameter', () => {
    expect(formatPct(0.123, 0)).toBe('12%');
    expect(formatPct(0.123, 2)).toBe('12.30%');
  });

  it('formats small probabilities correctly', () => {
    expect(formatPct(0.015)).toBe('1.5%');
  });
});

describe('formatRps', () => {
  it('formats to 4 decimal places', () => {
    expect(formatRps(0.2195)).toBe('0.2195');
  });

  it('returns dash for null', () => {
    expect(formatRps(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatRps(undefined)).toBe('—');
  });
});

describe('formatOdds', () => {
  it('converts probability to decimal odds', () => {
    expect(formatOdds(0.5)).toBe('2.00');
  });

  it('handles favourite', () => {
    const odds = parseFloat(formatOdds(0.7));
    expect(odds).toBeCloseTo(1.43, 1);
  });

  it('returns dash for null', () => {
    expect(formatOdds(null)).toBe('—');
  });

  it('returns dash for zero', () => {
    expect(formatOdds(0)).toBe('—');
  });

  it('returns dash for negative', () => {
    expect(formatOdds(-0.1)).toBe('—');
  });
});

describe('formatDate', () => {
  it('returns dash for null', () => {
    expect(formatDate(null)).toBe('—');
  });

  it('returns dash for undefined', () => {
    expect(formatDate(undefined)).toBe('—');
  });

  it('formats a valid ISO date', () => {
    const result = formatDate('2026-06-08');
    expect(result).toContain('2026');
  });

  it('handles ISO datetime', () => {
    const result = formatDate('2026-06-08T14:00:00Z');
    expect(result).toContain('2026');
  });
});

describe('formatModelName', () => {
  it('maps elo-baseline-v0.2 to Elo-full', () => {
    expect(formatModelName('elo-baseline-v0.2')).toBe('Elo-full');
  });

  it('maps elo-baseline-v0.2-recent to Elo-recent', () => {
    expect(formatModelName('elo-baseline-v0.2-recent')).toBe('Elo-recent');
  });

  it('maps dixon-coles-v0.3 to Dixon-Coles', () => {
    expect(formatModelName('dixon-coles-v0.3')).toBe('Dixon-Coles');
  });

  it('returns unknown slug unchanged', () => {
    expect(formatModelName('unknown-model')).toBe('unknown-model');
  });
});

describe('statusBadgeClass', () => {
  it('returns a non-empty string for all five statuses', () => {
    const statuses = [
      'closing_locked', 'closing_candidate', 'latest_available',
      'opening_only', 'no_market_data',
    ];
    for (const s of statuses) {
      expect(statusBadgeClass(s).length).toBeGreaterThan(0);
    }
  });

  it('closing_locked returns green styling', () => {
    expect(statusBadgeClass('closing_locked')).toContain('green');
  });

  it('no_market_data returns muted styling', () => {
    const cls = statusBadgeClass('no_market_data');
    expect(cls).toContain('slate');
  });

  it('returns fallback for unknown status', () => {
    expect(statusBadgeClass('unknown').length).toBeGreaterThan(0);
  });
});
