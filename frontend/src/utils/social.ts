function pct(v: number): string {
  return Math.round(v * 100) + '%';
}

export interface MatchSummaryParams {
  homeLabel: string;
  awayLabel: string;
  group: string;
  pHome: number;
  pDraw: number;
  pAway: number;
  signalLevel: string;
  kickoffFormatted: string | null;
}

export function generateMatchSummary(p: MatchSummaryParams): string {
  const domProb = Math.max(p.pHome, p.pDraw, p.pAway);
  const dominant =
    p.pHome >= p.pDraw && p.pHome >= p.pAway ? p.homeLabel
    : p.pAway > p.pHome && p.pAway >= p.pDraw ? p.awayLabel
    : 'Draw';

  const signalLine =
    p.signalLevel === 'model_gap_detected' ? 'Market gap detected'
    : p.signalLevel === 'watch'             ? 'Watch signal'
    : p.signalLevel === 'avoid'             ? 'Avoid signal'
    : p.signalLevel === 'model_only'        ? 'Strong model edge'
    : 'Model probability only';

  return [
    `${p.homeLabel} vs ${p.awayLabel}${p.kickoffFormatted ? ` · ${p.kickoffFormatted}` : ''}`,
    `Group ${p.group}`,
    '',
    'World Cup Oracle Forecast',
    `${p.homeLabel}: ${pct(p.pHome)}`,
    `Draw: ${pct(p.pDraw)}`,
    `${p.awayLabel}: ${pct(p.pAway)}`,
    '',
    `Model favors ${dominant} at ${pct(domProb)}`,
    `Signal: ${signalLine}`,
    '',
    'Educational only — not betting advice',
  ].join('\n');
}

export interface TournamentSummaryParams {
  topTeams: Array<{ name: string; champion: number }>;
  nSims: number;
}

export function generateTournamentSummary(p: TournamentSummaryParams): string {
  return [
    '2026 World Cup Championship Forecast',
    `World Cup Oracle · ${p.nSims.toLocaleString()} simulations`,
    '',
    ...p.topTeams.slice(0, 5).map((t, i) =>
      `${i + 1}. ${t.name}  ${(t.champion * 100).toFixed(1)}%`
    ),
    '',
    'Educational only — not betting advice',
  ].join('\n');
}
