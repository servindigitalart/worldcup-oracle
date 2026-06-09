const TEAM_NAMES: Record<string, string> = {
  united_states:     'United States',
  cote_divoire:      "Côte d'Ivoire",
  south_korea:       'South Korea',
  saudi_arabia:      'Saudi Arabia',
  new_zealand:       'New Zealand',
  costa_rica:        'Costa Rica',
  south_africa:      'South Africa',
  czech_republic:    'Czech Republic',
  bosnia_herzegovina:'Bosnia & Herzegovina',
  cape_verde:        'Cape Verde',
  dr_congo:          'DR Congo',
  curacao:           'Curaçao',
};

export function formatTeamName(slug: string): string {
  if (!slug) return '';
  return TEAM_NAMES[slug] ?? slug.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatPct(value: number | null | undefined, decimals = 1): string {
  if (value == null || !isFinite(value)) return '—';
  return (value * 100).toFixed(decimals) + '%';
}

export function formatRps(value: number | null | undefined): string {
  if (value == null || !isFinite(value)) return '—';
  return value.toFixed(4);
}

export function formatOdds(prob: number | null | undefined): string {
  if (prob == null || prob <= 0 || !isFinite(prob)) return '—';
  return (1 / prob).toFixed(2);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

export function formatKickoff(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString('en-GB', {
      day: 'numeric', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
      timeZone: 'UTC', timeZoneName: 'short',
    });
  } catch {
    return iso;
  }
}

export function formatModelName(slug: string): string {
  const map: Record<string, string> = {
    'elo-baseline-v0.2': 'Elo-full',
    'elo-baseline-v0.2-recent': 'Elo-recent',
    'dixon-coles-v0.3': 'Dixon-Coles',
  };
  return map[slug] ?? slug;
}

export function statusBadgeClass(status: string): string {
  const map: Record<string, string> = {
    closing_locked:    'bg-green-900/50 text-green-300 border-green-700/50',
    closing_candidate: 'bg-blue-900/50 text-blue-300 border-blue-700/50',
    latest_available:  'bg-slate-800 text-slate-300 border-slate-700',
    opening_only:      'bg-amber-900/30 text-amber-300 border-amber-700/50',
    no_market_data:    'bg-slate-900 text-slate-500 border-slate-800',
  };
  return map[status] ?? 'bg-slate-800 text-slate-300 border-slate-700';
}
