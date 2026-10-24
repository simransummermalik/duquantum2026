import fs from "node:fs";

const sourcePath = process.argv[2];
const outputPath = process.argv[3];

if (!sourcePath || !outputPath) {
  console.error("Usage: node scripts/build_watchcat_idle_gif.mjs SOURCE.html OUTPUT.gif");
  process.exit(1);
}

const html = fs.readFileSync(sourcePath, "utf8");
const scriptStart = html.indexOf("<script>") + "<script>".length;
const scriptEnd = html.indexOf("</script>", scriptStart);
const source = html.slice(scriptStart, scriptEnd);

let now = 0;
let pixels = [];
const colors = [
  "#fbfbf8",
  "#2e1f17",
  "#f4a259",
  "#d9772b",
  "#fff3e0",
  "#2b2b2b",
  "#ffffff",
  "#f49ab0",
  "#a8743f",
  "#5a3a1e",
  "#8a5a2c",
  "#8f969c",
  "#dff1ff",
  "#6b4423",
  "#bfe6ff",
  "#e5e8ec",
];
const colorIndex = new Map(colors.map((color, index) => [color, index]));

const ctx = {
  fillStyle: "#fbfbf8",
  fillRect(x, y, width, height) {
    if (width !== 14 || height !== 14) return;
    const px = Math.round(x / 14);
    const py = Math.round(y / 14);
    if (px < 0 || px >= 32 || py < 0 || py >= 34) return;
    const color = this.fillStyle === "rgba(140,200,255,0.28)" ? "#bfe6ff" : this.fillStyle;
    pixels[py][px] = color;
  },
  beginPath() {},
  moveTo() {},
  lineTo() {},
  stroke() {},
};

const canvas = {
  set width(value) {},
  set height(value) {},
  getContext() {
    return ctx;
  },
};

globalThis.document = { getElementById: () => canvas };
globalThis.performance = { now: () => now };
globalThis.setInterval = () => 0;

const runnableSource = source.replace("setInterval(frame,100);frame();", "") +
  "\nglobalThis.__watchcatFrame = frame;";
eval(runnableSource);

const width = 256;
const height = 272;
const scale = 8;
const gridIndex = colorIndex.get("#e5e8ec");

function renderFrame(time) {
  now = time;
  pixels = Array.from({ length: 34 }, () => Array(32).fill(null));
  globalThis.__watchcatFrame();

  const indices = new Uint8Array(width * height);
  indices.fill(0);
  for (let y = 0; y < 34; y += 1) {
    for (let x = 0; x < 32; x += 1) {
      const index = colorIndex.get(pixels[y][x] ?? "#fbfbf8");
      for (let yy = y * scale; yy < (y + 1) * scale; yy += 1) {
        for (let xx = x * scale; xx < (x + 1) * scale; xx += 1) {
          indices[yy * width + xx] = index;
        }
      }
    }
  }
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (x % scale === 0 || y % scale === 0) indices[y * width + x] = gridIndex;
    }
  }
  return indices;
}

function lzwEncode(indices, minimumCodeSize = 4) {
  const clearCode = 1 << minimumCodeSize;
  const endCode = clearCode + 1;
  const codeSize = minimumCodeSize + 1;
  const output = [];
  let bitBuffer = 0;
  let bitCount = 0;
  const writeCode = (code) => {
    bitBuffer |= code << bitCount;
    bitCount += codeSize;
    while (bitCount >= 8) {
      output.push(bitBuffer & 0xff);
      bitBuffer >>= 8;
      bitCount -= 8;
    }
  };

  // Emit a clear code before every pixel. This is intentionally simple and
  // keeps the code width fixed, making the generated GIF widely compatible.
  for (const value of indices) {
    writeCode(clearCode);
    writeCode(value);
  }
  writeCode(endCode);
  if (bitCount > 0) output.push(bitBuffer & 0xff);

  const blocks = [];
  for (let i = 0; i < output.length; i += 255) {
    const block = output.slice(i, i + 255);
    blocks.push(block.length, ...block);
  }
  blocks.push(0);
  return Buffer.from([minimumCodeSize, ...blocks]);
}

const bytes = [];
const push = (...values) => {
  for (const value of values) bytes.push(value);
};
const pushText = (value) => push(...Buffer.from(value, "ascii"));
const le16 = (value) => push(value & 0xff, (value >> 8) & 0xff);

pushText("GIF89a");
le16(width);
le16(height);
push(0xf3, 0, 0);
for (const color of colors) {
  const hex = color.slice(1);
  push(Number.parseInt(hex.slice(0, 2), 16), Number.parseInt(hex.slice(2, 4), 16), Number.parseInt(hex.slice(4, 6), 16));
}
push(0x21, 0xff, 0x0b);
pushText("NETSCAPE2.0");
push(0x03, 0x01, 0x00, 0x00, 0x00);

for (let frame = 0; frame < 60; frame += 1) {
  push(0x21, 0xf9, 0x04, 0x00, 0x14, 0x00, 0x00, 0x00);
  push(0x2c);
  le16(0);
  le16(0);
  le16(width);
  le16(height);
  push(0x00);
  push(...lzwEncode(renderFrame(frame * 200)));
}
push(0x3b);

fs.writeFileSync(outputPath, Buffer.from(bytes));
console.log(`Wrote ${outputPath}`);
