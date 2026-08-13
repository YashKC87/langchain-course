import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import {
  AlignmentType,
  Document,
  HeadingLevel,
  ImageRun,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  WidthType,
  BorderStyle,
} from 'docx';
import { saveAs } from 'file-saver';
import type { ReportSnapshot } from './reportData';
import { formatReportValue } from './reportData';

const BRAND = 'Sigma Orion';
const SUBTITLE = 'Agent Metering & Observability Control Center';
const RED = '#E31C23';
const INK = '#152033';
const MUTED = '#4b5c73';

async function fetchLogoPngBytes(): Promise<Uint8Array> {
  // Prefer crisp SVG rendered to canvas so PDF/Word get a clean brand mark.
  const svg = await (await fetch('/sigma-logo.svg')).text();
  const blob = new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  try {
    const img = await loadImage(url);
    const canvas = document.createElement('canvas');
    canvas.width = 256;
    canvas.height = 256;
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('Canvas unavailable');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, 256, 256);
    ctx.drawImage(img, 0, 0, 256, 256);
    const pngBlob = await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('PNG encode failed'))), 'image/png');
    });
    return new Uint8Array(await pngBlob.arrayBuffer());
  } finally {
    URL.revokeObjectURL(url);
  }
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Failed to load logo'));
    img.src = src;
  });
}

function stampFilename(ext: string): string {
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  return `Sigma-Orion-Agent-Report-${stamp}.${ext}`;
}

function kpiRows(data: ReportSnapshot): Array<[string, string]> {
  if (!data.kpis) {
    return [['Status', data.emptyMessage ?? 'No live telemetry available']];
  }
  const k = data.kpis;
  return [
    ['Active Agents', formatReportValue(k.active_agents?.value)],
    ['Executions', formatReportValue(k.executions?.value)],
    ['Total Tokens', formatReportValue(k.total_tokens?.value)],
    ['Success Rate', formatReportValue(k.success_rate?.value, '%')],
    ['Average Latency (ms)', formatReportValue(k.average_latency?.value)],
    ['Needs Attention', formatReportValue(k.needs_attention?.value)],
  ];
}

export async function exportReportPdf(data: ReportSnapshot): Promise<void> {
  const logo = await fetchLogoPngBytes();
  const doc = new jsPDF({ unit: 'pt', format: 'a4' });
  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 48;

  doc.setFillColor(255, 255, 255);
  doc.rect(0, 0, pageWidth, doc.internal.pageSize.getHeight(), 'F');

  doc.addImage(logo, 'PNG', margin, 36, 42, 42);
  doc.setTextColor(RED);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(18);
  doc.text(BRAND, margin + 54, 54);
  doc.setTextColor(MUTED);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.text(SUBTITLE, margin + 54, 70);

  doc.setDrawColor(227, 28, 35);
  doc.setLineWidth(1.2);
  doc.line(margin, 92, pageWidth - margin, 92);

  doc.setTextColor(INK);
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(14);
  doc.text('Operational Agent Report', margin, 118);
  doc.setFont('helvetica', 'normal');
  doc.setFontSize(10);
  doc.setTextColor(MUTED);
  doc.text(`Generated: ${new Date(data.generatedAt).toLocaleString()}`, margin, 134);
  doc.text(
    `Telemetry live: ${data.status.telemetry_live ? 'Yes' : 'No'} · Agents: ${data.status.agents} · Executions: ${data.status.executions}`,
    margin,
    148,
  );

  autoTable(doc, {
    startY: 168,
    head: [['Metric', 'Value']],
    body: kpiRows(data),
    theme: 'grid',
    headStyles: { fillColor: [227, 28, 35], textColor: 255, fontStyle: 'bold' },
    styles: { fontSize: 9, cellPadding: 6, textColor: [21, 32, 51] },
    margin: { left: margin, right: margin },
  });

  let y = ((doc as unknown as { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? 180) + 24;
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.setTextColor(INK);
  doc.text('Agent Metering', margin, y);
  y += 8;

  autoTable(doc, {
    startY: y,
    head: [['Agent', 'Cloud', 'Executions', 'Tokens', 'Success %', 'Health']],
    body: data.metering.slice(0, 25).map((row) => [
      row.agent_name,
      row.cloud ?? '—',
      formatReportValue(row.executions),
      formatReportValue(row.tokens),
      formatReportValue(row.success_rate, '%'),
      row.health ?? '—',
    ]),
    theme: 'striped',
    headStyles: { fillColor: [21, 32, 51], textColor: 255 },
    styles: { fontSize: 8, cellPadding: 5 },
    margin: { left: margin, right: margin },
  });

  y = ((doc as unknown as { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? y) + 24;
  if (y > 680) {
    doc.addPage();
    y = 48;
  }
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.setTextColor(INK);
  doc.text('Live & Recent Executions', margin, y);
  y += 8;

  autoTable(doc, {
    startY: y,
    head: [['Execution', 'Agent', 'Status', 'Tokens', 'Started']],
    body: data.executions.slice(0, 20).map((e) => [
      e.execution_id.slice(0, 18),
      e.agent_name ?? '—',
      e.status,
      formatReportValue(e.total_tokens),
      e.start_time ? new Date(e.start_time).toLocaleString() : '—',
    ]),
    theme: 'striped',
    headStyles: { fillColor: [21, 32, 51], textColor: 255 },
    styles: { fontSize: 8, cellPadding: 5 },
    margin: { left: margin, right: margin },
  });

  y = ((doc as unknown as { lastAutoTable?: { finalY: number } }).lastAutoTable?.finalY ?? y) + 24;
  if (data.attention.length) {
    if (y > 700) {
      doc.addPage();
      y = 48;
    }
    doc.setFont('helvetica', 'bold');
    doc.setFontSize(12);
    doc.text('Needs Attention', margin, y);
    y += 8;
    autoTable(doc, {
      startY: y,
      head: [['Condition', 'Severity', 'Agent', 'Evidence']],
      body: data.attention.slice(0, 15).map((a) => [
        a.condition,
        a.severity,
        a.agent_name ?? '—',
        a.evidence ?? '—',
      ]),
      theme: 'grid',
      headStyles: { fillColor: [196, 132, 26], textColor: 255 },
      styles: { fontSize: 8, cellPadding: 5 },
      margin: { left: margin, right: margin },
    });
  }

  const pageCount = doc.getNumberOfPages();
  for (let i = 1; i <= pageCount; i += 1) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(MUTED);
    doc.text(
      `${BRAND} · Confidential operational report · Page ${i} of ${pageCount}`,
      margin,
      doc.internal.pageSize.getHeight() - 24,
    );
  }

  doc.save(stampFilename('pdf'));
}

function cell(text: string, bold = false): TableCell {
  return new TableCell({
    children: [
      new Paragraph({
        children: [new TextRun({ text, bold, size: 18, font: 'Calibri', color: '152033' })],
      }),
    ],
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: 'D5DDE7' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: 'D5DDE7' },
      left: { style: BorderStyle.SINGLE, size: 4, color: 'D5DDE7' },
      right: { style: BorderStyle.SINGLE, size: 4, color: 'D5DDE7' },
    },
    width: { size: 2500, type: WidthType.DXA },
  });
}

function headerCell(text: string): TableCell {
  return new TableCell({
    children: [
      new Paragraph({
        children: [new TextRun({ text, bold: true, size: 18, font: 'Calibri', color: 'FFFFFF' })],
      }),
    ],
    shading: { type: 'clear', fill: 'E31C23' },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: 'E31C23' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: 'E31C23' },
      left: { style: BorderStyle.SINGLE, size: 4, color: 'E31C23' },
      right: { style: BorderStyle.SINGLE, size: 4, color: 'E31C23' },
    },
    width: { size: 2500, type: WidthType.DXA },
  });
}

export async function exportReportDocx(data: ReportSnapshot): Promise<void> {
  const logo = await fetchLogoPngBytes();

  const kpiTable = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({ children: [headerCell('Metric'), headerCell('Value')] }),
      ...kpiRows(data).map(
        ([metric, value]) => new TableRow({ children: [cell(metric, true), cell(value)] }),
      ),
    ],
  });

  const meteringTable = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({
        children: [
          headerCell('Agent'),
          headerCell('Cloud'),
          headerCell('Executions'),
          headerCell('Tokens'),
          headerCell('Success %'),
        ],
      }),
      ...data.metering.slice(0, 25).map(
        (row) =>
          new TableRow({
            children: [
              cell(row.agent_name),
              cell(row.cloud ?? '—'),
              cell(formatReportValue(row.executions)),
              cell(formatReportValue(row.tokens)),
              cell(formatReportValue(row.success_rate, '%')),
            ],
          }),
      ),
    ],
  });

  const execTable = new Table({
    width: { size: 100, type: WidthType.PERCENTAGE },
    rows: [
      new TableRow({
        children: [
          headerCell('Execution'),
          headerCell('Agent'),
          headerCell('Status'),
          headerCell('Tokens'),
          headerCell('Started'),
        ],
      }),
      ...data.executions.slice(0, 20).map(
        (e) =>
          new TableRow({
            children: [
              cell(e.execution_id.slice(0, 18)),
              cell(e.agent_name ?? '—'),
              cell(e.status),
              cell(formatReportValue(e.total_tokens)),
              cell(e.start_time ? new Date(e.start_time).toLocaleString() : '—'),
            ],
          }),
      ),
    ],
  });

  const children = [
    new Paragraph({
      children: [
        new ImageRun({
          data: logo,
          transformation: { width: 56, height: 56 },
          type: 'png',
        }),
      ],
    }),
    new Paragraph({
      spacing: { before: 120 },
      children: [
        new TextRun({ text: BRAND, bold: true, size: 36, color: 'E31C23', font: 'Calibri' }),
      ],
    }),
    new Paragraph({
      children: [new TextRun({ text: SUBTITLE, size: 20, color: '4B5C73', font: 'Calibri' })],
    }),
    new Paragraph({
      spacing: { before: 200, after: 120 },
      border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: 'E31C23', space: 8 } },
      children: [],
    }),
    new Paragraph({
      heading: HeadingLevel.HEADING_1,
      children: [new TextRun({ text: 'Operational Agent Report', bold: true, color: '152033' })],
    }),
    new Paragraph({
      spacing: { after: 200 },
      children: [
        new TextRun({
          text: `Generated: ${new Date(data.generatedAt).toLocaleString()}  ·  Telemetry live: ${data.status.telemetry_live ? 'Yes' : 'No'}`,
          size: 20,
          color: '4B5C73',
        }),
      ],
    }),
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      children: [new TextRun({ text: 'Key Metrics', bold: true })],
    }),
    kpiTable,
    new Paragraph({ spacing: { before: 280 }, children: [] }),
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      children: [new TextRun({ text: 'Agent Metering', bold: true })],
    }),
    meteringTable,
    new Paragraph({ spacing: { before: 280 }, children: [] }),
    new Paragraph({
      heading: HeadingLevel.HEADING_2,
      children: [new TextRun({ text: 'Live & Recent Executions', bold: true })],
    }),
    execTable,
  ];

  if (data.attention.length) {
    children.push(
      new Paragraph({ spacing: { before: 280 }, children: [] }),
      new Paragraph({
        heading: HeadingLevel.HEADING_2,
        children: [new TextRun({ text: 'Needs Attention', bold: true })],
      }),
      new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
          new TableRow({
            children: [headerCell('Condition'), headerCell('Severity'), headerCell('Agent'), headerCell('Evidence')],
          }),
          ...data.attention.slice(0, 15).map(
            (a) =>
              new TableRow({
                children: [
                  cell(a.condition),
                  cell(a.severity),
                  cell(a.agent_name ?? '—'),
                  cell(a.evidence ?? '—'),
                ],
              }),
          ),
        ],
      }),
    );
  }

  children.push(
    new Paragraph({
      spacing: { before: 360 },
      alignment: AlignmentType.LEFT,
      children: [
        new TextRun({
          text: `${BRAND} · Confidential operational report`,
          italics: true,
          size: 16,
          color: '7A8A9E',
        }),
      ],
    }),
  );

  const doc = new Document({
    creator: BRAND,
    title: `${BRAND} Operational Agent Report`,
    description: SUBTITLE,
    sections: [{ children }],
  });

  const blob = await Packer.toBlob(doc);
  saveAs(blob, stampFilename('docx'));
}
