import { render, screen, within, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect } from 'vitest';
import { ChartCard, LegendKey } from './ChartCard';
import { StatTile, Sparkline } from './StatTile';
import { Meter } from './Meter';
import { ShareBar } from './ShareBar';
import { Heatmap, heatColor } from './Heatmap';
import { EMPTY_CELL, SEQUENTIAL, LIFECYCLE, STATUS, SERIES } from './tokens';

const table = { columns: ['Category', 'Tickets'], rows: [['Refunds', 1234], ['Billing', null]] as (string | number | null)[][] };

describe('ChartCard', () => {
  it('is a labelled region with its title and subtitle', () => {
    render(<ChartCard title="Ticket volume" subtitle="Per day"><p>plot</p></ChartCard>);
    const region = screen.getByRole('region', { name: 'Ticket volume' });
    expect(within(region).getByText('Per day')).toBeInTheDocument();
    expect(within(region).getByText('plot')).toBeInTheDocument();
  });

  it('offers a Chart / Table toggle and the table twin carries every value, numbers formatted', async () => {
    const user = userEvent.setup();
    render(<ChartCard title="By category" table={table}><p>plot</p></ChartCard>);
    const chartBtn = screen.getByRole('button', { name: 'chart' });
    const tableBtn = screen.getByRole('button', { name: 'table' });
    expect(chartBtn).toHaveAttribute('aria-pressed', 'true');
    expect(tableBtn).toHaveAttribute('aria-pressed', 'false');

    await user.click(tableBtn);

    expect(screen.queryByText('plot')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: /By category.*scrollable table/ })).toHaveAttribute('tabindex', '0'); // keyboard users can scroll it
    const grid = screen.getByRole('table', { name: /By category/ });
    expect(within(grid).getByRole('columnheader', { name: 'Category' })).toBeInTheDocument();
    expect(within(grid).getByText('1,234')).toBeInTheDocument(); // thousands separator
    expect(within(grid).getByText('—')).toBeInTheDocument(); // missing value is a dash, not "null"
    expect(tableBtn).toHaveAttribute('aria-pressed', 'true');

    await user.click(chartBtn);
    expect(screen.getByText('plot')).toBeInTheDocument();
  });

  it('shows the legend and the takeaway only in the chart view', async () => {
    const user = userEvent.setup();
    render(
      <ChartCard title="T" table={table} legend={<LegendKey color="#fff" label="Received" />} footer="155 tickets are waiting.">
        <p>plot</p>
      </ChartCard>
    );
    expect(screen.getByText('Received')).toBeInTheDocument();
    expect(screen.getByText('155 tickets are waiting.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'table' }));
    expect(screen.queryByText('Received')).not.toBeInTheDocument();
    expect(screen.queryByText('155 tickets are waiting.')).not.toBeInTheDocument();
  });

  it('shows the empty message instead of the chart and hides the toggle when there is nothing to plot', () => {
    render(<ChartCard title="T" table={table} empty emptyText="Nothing here." footer="ignored"><p>plot</p></ChartCard>);
    expect(screen.getByText('Nothing here.')).toBeInTheDocument();
    expect(screen.queryByText('plot')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'table' })).not.toBeInTheDocument();
    expect(screen.queryByText('ignored')).not.toBeInTheDocument();
  });

  it('renders untrusted labels as text, never as markup', async () => {
    const user = userEvent.setup();
    const evil = { columns: ['Label', 'n'], rows: [['<img src=x onerror=alert(1)>', 1]] as (string | number | null)[][] };
    const { container } = render(<ChartCard title="T" table={evil}><p>plot</p></ChartCard>);
    await user.click(screen.getByRole('button', { name: 'table' }));
    expect(screen.getByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(container.querySelector('img')).toBeNull();
  });
});

describe('StatTile', () => {
  it('shows label, value and a delta whose wording carries the direction (never colour alone)', () => {
    render(<StatTile label="Resolved" value="440" delta={{ text: '▲ 12.2%', direction: 'up', tone: 'good' }} deltaCaption="vs last week" />);
    expect(screen.getByLabelText('Resolved: 440')).toBeInTheDocument();
    const delta = screen.getByText('▲ 12.2%');
    expect(delta).toHaveAttribute('data-tone', 'good');
    expect(screen.getByText('vs last week')).toBeInTheDocument();
  });

  it('uses status colours only for good/bad, and a neutral ink for everything else', () => {
    const { rerender } = render(<StatTile label="L" value="1" delta={{ text: '▲ 1%', direction: 'up', tone: 'good' }} />);
    expect(screen.getByText('▲ 1%')).toHaveStyle({ color: STATUS.good });
    rerender(<StatTile label="L" value="1" delta={{ text: '▼ 1%', direction: 'down', tone: 'bad' }} />);
    expect(screen.getByText('▼ 1%')).toHaveStyle({ color: STATUS.serious });
    rerender(<StatTile label="L" value="1" delta={{ text: '▲ 1%', direction: 'up', tone: 'neutral' }} />);
    expect(screen.getByText('▲ 1%').style.color).not.toBe('');
    expect(screen.getByText('▲ 1%')).not.toHaveStyle({ color: STATUS.good });
  });

  it('shows the hint on its own when there is no delta', () => {
    render(<StatTile label="L" value="1" hint="Pick a date range" delta={null} />);
    expect(screen.getByText('Pick a date range')).toBeInTheDocument();
  });

  it('keeps the hint visible next to the delta - context is not replaced by the change', () => {
    render(<StatTile label="L" value="1" hint="95th percentile 12 s" delta={{ text: '▼ 5%', direction: 'down', tone: 'good' }} deltaCaption="vs last week" />);
    expect(screen.getByText('▼ 5%')).toBeInTheDocument();
    expect(screen.getByText('95th percentile 12 s')).toBeInTheDocument();
  });

  it('the hero figure is the largest, and only when asked', () => {
    const { rerender } = render(<StatTile label="L" value="715" hero />);
    expect(screen.getByLabelText('L: 715')).toHaveClass('text-5xl');
    rerender(<StatTile label="L" value="715" />);
    expect(screen.getByLabelText('L: 715')).toHaveClass('text-3xl');
  });

  it('the sparkline is decorative (hidden from assistive tech) and needs at least two points', () => {
    const { container, rerender } = render(<StatTile label="L" value="1" spark={[1, 3, 2, 5]} />);
    const svg = container.querySelector('svg')!;
    expect(svg).toHaveAttribute('aria-hidden', 'true');
    expect(svg.querySelectorAll('path')).toHaveLength(2);
    rerender(<StatTile label="L" value="1" spark={[4]} />);
    expect(container.querySelector('svg')).toBeNull();
  });

  it('Sparkline copes with all-zero data without producing NaN geometry', () => {
    const { container } = render(<Sparkline values={[0, 0, 0]} />);
    expect(container.innerHTML).not.toMatch(/NaN/);
  });
});

describe('Meter', () => {
  it('is an accessible meter with its value and severity in words', () => {
    render(<Meter label="Validation pass rate" value={0.84} severity="warning" detail="501 passed" />);
    const meter = screen.getByRole('meter', { name: 'Validation pass rate' });
    expect(meter).toHaveAttribute('aria-valuenow', '84');
    expect(meter).toHaveAttribute('aria-valuemin', '0');
    expect(meter).toHaveAttribute('aria-valuemax', '100');
    expect(meter).toHaveAttribute('aria-valuetext', '84%, needs attention');
    expect(screen.getByText('Needs attention')).toBeInTheDocument(); // severity is text too, not only a colour
    expect(screen.getByText('501 passed')).toBeInTheDocument();
  });

  it('draws the fill to the value, clamps it into the track, and never claims a value it does not have', () => {
    const { rerender } = render(<Meter label="R" value={0.26} />);
    expect(screen.getByRole('meter').firstElementChild).toHaveStyle({ width: '26%' });
    rerender(<Meter label="R" value={1.7} />);
    expect(screen.getByRole('meter').firstElementChild).toHaveStyle({ width: '100%' });
    rerender(<Meter label="R" value={null} />);
    const m = screen.getByRole('meter');
    expect(m).not.toHaveAttribute('aria-valuenow');
    expect(m).toHaveAttribute('aria-valuetext', 'No data');
    expect(m.firstElementChild).toHaveStyle({ width: '0%' });
  });

  it('the fill takes the severity colour: accent, warning, danger', () => {
    const { rerender } = render(<Meter label="R" value={0.5} />);
    expect(screen.getByRole('meter').firstElementChild).toHaveStyle({ background: SERIES.blue });
    rerender(<Meter label="R" value={0.5} severity="warning" />);
    expect(screen.getByRole('meter').firstElementChild).toHaveStyle({ background: STATUS.warning });
    rerender(<Meter label="R" value={0.5} severity="danger" />);
    expect(screen.getByRole('meter').firstElementChild).toHaveStyle({ background: STATUS.critical });
    expect(screen.getByText('Critical')).toBeInTheDocument();
  });
});

describe('ShareBar', () => {
  const segments = [
    { label: 'Resolved', count: 440, color: LIFECYCLE.resolved },
    { label: 'Awaiting human review', count: 155, color: LIFECYCLE.awaitingHuman },
    { label: 'In progress', count: 0, color: LIFECYCLE.inProgress },
  ];

  it('is a labelled group of images (focusable children need a permitted role), and the legend lists every state with count and share', () => {
    render(<ShareBar segments={segments} ariaLabel="Ticket states: Resolved 440" />);
    expect(screen.getByRole('group', { name: 'Ticket states: Resolved 440' })).toBeInTheDocument();
    const legend = screen.getByRole('list');
    expect(within(legend).getAllByRole('listitem')).toHaveLength(3); // a zero state stays in the legend
    expect(within(legend).getByText('440')).toBeInTheDocument();
    expect(within(legend).getByText('74%')).toBeInTheDocument();
    expect(within(legend).getByText('0%')).toBeInTheDocument();
  });

  it('draws only non-empty segments, each keyboard-focusable with its own label', () => {
    render(<ShareBar segments={segments} ariaLabel="x" />);
    const bar = screen.getByRole('group');
    const drawn = within(bar).getAllByRole('img');
    expect(drawn).toHaveLength(2);
    expect(drawn[0]).toHaveAttribute('tabindex', '0');
    expect(drawn[0]).toHaveAttribute('aria-label', 'Resolved: 440 (73.9%)');
  });

  it('shows the same tooltip on keyboard focus as on hover, and hides it on blur', () => {
    render(<ShareBar segments={segments} ariaLabel="x" />);
    const seg = screen.getByLabelText('Awaiting human review: 155 (26.1%)');
    fireEvent.focus(seg);
    expect(screen.getByRole('tooltip')).toHaveTextContent('155 · 26.1%');
    expect(screen.getByRole('tooltip')).toHaveTextContent('Awaiting human review');
    fireEvent.blur(seg);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });

  it('an all-zero bar renders an empty track, not NaN widths', () => {
    const { container } = render(<ShareBar segments={segments.map((s) => ({ ...s, count: 0 }))} ariaLabel="x" />);
    expect(container.innerHTML).not.toMatch(/NaN/);
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });
});

describe('Heatmap', () => {
  const grid = Array.from({ length: 7 }, (_, r) => Array.from({ length: 24 }, (_, c) => (r === 2 && c === 10 ? 9 : r === 0 && c === 8 ? 3 : 0)));

  it('heatColor: zero is an empty cell (not the darkest step), and the maximum reaches the brightest step', () => {
    expect(heatColor(0, 9)).toBe(EMPTY_CELL);
    expect(heatColor(-1, 9)).toBe(EMPTY_CELL);
    expect(heatColor(9, 9)).toBe(SEQUENTIAL[SEQUENTIAL.length - 1]);
    expect(heatColor(1, 1000)).toBe(SEQUENTIAL[0]); // small but non-zero is still visible as data
    const steps = [1, 3, 5, 7, 9].map((n) => SEQUENTIAL.indexOf(heatColor(n, 9) as (typeof SEQUENTIAL)[number]));
    expect([...steps].sort((a, b) => a - b)).toEqual(steps); // more tickets never gets a darker colour
  });

  it('is a grid of 7 x 24 cells, each with a spoken label', () => {
    render(<Heatmap grid={grid} />);
    expect(screen.getAllByRole('gridcell')).toHaveLength(168);
    expect(screen.getByRole('grid')).toHaveAccessibleName(/12 tickets in total/);
    expect(screen.getByLabelText('Wednesday 10:00–10:59 UTC: 9 tickets')).toBeInTheDocument();
    expect(screen.getByLabelText('Monday 00:00–00:59 UTC: 0 tickets')).toBeInTheDocument();
    expect(screen.getByLabelText('Monday 08:00–08:59 UTC: 3 tickets')).toBeInTheDocument();
  });

  it('is ONE tab stop for the whole grid, starting on the busiest cell', () => {
    render(<Heatmap grid={grid} />);
    const stops = screen.getAllByRole('gridcell').filter((c) => c.getAttribute('tabindex') === '0');
    expect(stops).toHaveLength(1);
    expect(stops[0]).toHaveAccessibleName('Wednesday 10:00–10:59 UTC: 9 tickets');
  });

  it('arrow keys move between cells, clamp at the edges, and focus shows the tooltip', () => {
    render(<Heatmap grid={grid} />);
    const start = screen.getByLabelText('Wednesday 10:00–10:59 UTC: 9 tickets');
    start.focus();
    fireEvent.keyDown(start, { key: 'ArrowRight' });
    expect(screen.getByLabelText('Wednesday 11:00–11:59 UTC: 0 tickets')).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' });
    expect(screen.getByLabelText('Tuesday 11:00–11:59 UTC: 0 tickets')).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: 'Home' });
    expect(screen.getByLabelText('Tuesday 00:00–00:59 UTC: 0 tickets')).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowLeft' }); // already at the left edge
    expect(screen.getByLabelText('Tuesday 00:00–00:59 UTC: 0 tickets')).toHaveFocus();
    fireEvent.keyDown(document.activeElement!, { key: 'End' });
    expect(screen.getByLabelText('Tuesday 23:00–23:59 UTC: 0 tickets')).toHaveFocus();
    expect(screen.getByRole('tooltip')).toHaveTextContent('Tuesday, 23:00 UTC');
  });

  it('the roving tab stop follows focus', () => {
    render(<Heatmap grid={grid} />);
    const start = screen.getByLabelText('Wednesday 10:00–10:59 UTC: 9 tickets');
    start.focus();
    fireEvent.keyDown(start, { key: 'ArrowDown' });
    const stops = screen.getAllByRole('gridcell').filter((c) => c.getAttribute('tabindex') === '0');
    expect(stops).toHaveLength(1);
    expect(stops[0]).toHaveAccessibleName('Thursday 10:00–10:59 UTC: 0 tickets');
  });

  it('an empty grid renders without NaN and starts on the first cell', () => {
    const { container } = render(<Heatmap grid={Array.from({ length: 7 }, () => new Array(24).fill(0))} />);
    expect(container.innerHTML).not.toMatch(/NaN/);
    expect(screen.getByLabelText('Monday 00:00–00:59 UTC: 0 tickets')).toHaveAttribute('tabindex', '0');
  });
});
