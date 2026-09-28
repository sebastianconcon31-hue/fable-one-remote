// A texture atlas that is filled in two passes. The model is built once to
// learn what every panel, key cap and gauge needs (record), the requests are
// packed tallest first, and the model is built again with the packed places
// handed out in the same order (replay). The build is deterministic, so the
// two passes ask for the same things in the same order.

export class Atlas {
  constructor(name, { pad = 6, sizes = [512, 1024, 2048, 4096] } = {}) {
    this.name = name;
    this.pad = pad;
    this.sizes = sizes;
    this.mode = "record";
    this.wanted = [];
    this.items = [];
    this.cursor = 0;
    this.size = 0;
  }

  alloc(w, h, item) {
    w = Math.max(2, Math.ceil(w));
    h = Math.max(2, Math.ceil(h));
    if (this.mode === "record") {
      this.wanted.push([w, h]);
      return { uv: [0, 0, 1, 1], rect: [0, 0, w, h] };
    }
    const i = this.cursor++;
    const [ww, hh] = this.wanted[i] || [];
    if (ww !== w || hh !== h) throw new Error(`${this.name}: request ${i} changed between passes (${ww}x${hh} -> ${w}x${h})`);
    const rect = this.rects[i];
    this.items.push({ ...item, rect });
    const S = this.size;
    return { rect, uv: [(rect[0] + 0.5) / S, (rect[1] + 0.5) / S, (rect[0] + w - 0.5) / S, (rect[1] + h - 0.5) / S] };
  }

  // Shelf packing, tallest first; the smallest square that fits.
  pack() {
    const order = this.wanted.map((_, i) => i).sort((a, b) => this.wanted[b][1] - this.wanted[a][1] || this.wanted[b][0] - this.wanted[a][0]);
    for (const S of this.sizes) {
      const rects = [];
      let x = this.pad, y = this.pad, rowH = 0, ok = true;
      for (const i of order) {
        const [w, h] = this.wanted[i];
        if (x + w + this.pad > S) {
          x = this.pad;
          y += rowH + this.pad;
          rowH = 0;
        }
        if (w + 2 * this.pad > S || y + h + this.pad > S) {
          ok = false;
          break;
        }
        rects[i] = [x, y, w, h];
        x += w + this.pad;
        rowH = Math.max(rowH, h);
      }
      if (ok) {
        this.size = S;
        this.rects = rects;
        this.mode = "replay";
        this.cursor = 0;
        this.items = [];
        return S;
      }
    }
    throw new Error(`${this.name}: does not fit in ${this.sizes[this.sizes.length - 1]}px`);
  }

  // Hand out the same places again, for a second model built from the same requests.
  rewind() {
    this.cursor = 0;
    this.items = [];
  }

  used() {
    return this.wanted.reduce((a, [w, h]) => a + w * h, 0) / (this.size * this.size || 1);
  }
}
