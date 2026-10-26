// Generates the PWA icons (a target, since "alvo" means target) without any image library.
// Run once with `node scripts/make-icons.mjs`; the PNG files are committed.
import { writeFileSync } from "node:fs";
import { crc32, deflateSync } from "node:zlib";

const BACKGROUND = [15, 23, 42]; // slate-900
const RINGS = [
  { radius: 0.34, color: [226, 232, 240] }, // slate-200
  { radius: 0.24, color: [15, 23, 42] },
  { radius: 0.15, color: [56, 189, 248] }, // sky-400
  { radius: 0.06, color: [15, 23, 42] },
];

function chunk(type, data) {
  const body = Buffer.concat([Buffer.from(type), data]);
  const out = Buffer.alloc(8 + data.length + 4);
  out.writeUInt32BE(data.length, 0);
  body.copy(out, 4);
  out.writeUInt32BE(crc32(body), 8 + data.length);
  return out;
}

function png(size) {
  const rows = [];
  for (let y = 0; y < size; y++) {
    const row = Buffer.alloc(1 + size * 3); // filter type 0 + RGB
    for (let x = 0; x < size; x++) {
      const dx = (x + 0.5) / size - 0.5;
      const dy = (y + 0.5) / size - 0.5;
      const distance = Math.hypot(dx, dy);
      let color = BACKGROUND;
      for (const ring of RINGS) if (distance <= ring.radius) color = ring.color;
      row.set(color, 1 + x * 3);
    }
    rows.push(row);
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0);
  header.writeUInt32BE(size, 4);
  header[8] = 8; // bit depth
  header[9] = 2; // colour type: RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", header),
    chunk("IDAT", deflateSync(Buffer.concat(rows))),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

writeFileSync("public/icon-192.png", png(192));
writeFileSync("public/icon-512.png", png(512));
console.log("icons written");
