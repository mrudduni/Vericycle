import qrcode from 'qrcode-generator';

/** QR as an SVG string. QR codes only ever encode a URL (CONTRACT §4), never data. */
export function qrSvg(url: string, cell = 4): string {
  const q = qrcode(0, 'M');
  q.addData(url);
  q.make();
  return q.createSvgTag({ cellSize: cell, margin: 2, scalable: true });
}
