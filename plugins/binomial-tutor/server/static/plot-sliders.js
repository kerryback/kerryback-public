// Sliders under a plot.  A tutor's make_plot may return a figure with
//   sliders: [{label, values, labels, index}, ...]   one range input each
//   frames:  {"i,j": {data, title}}                   one precomputed picture per combination
// The board draws the sliders and, as the student moves them, redraws the plot
// with the frame for the current combination.  Every number still comes from
// the tutor's tool, which computed all the frames; nothing is computed here.

// The frames key for slider positions, such as "3,6".
export function frameKey(indices) {
  return indices.join(',');
}

// What a slider shows next to its label at position i.
export function sliderText(slider, i) {
  return slider.labels ? slider.labels[i] : String(slider.values[i]);
}

// The starting positions: each slider's index, kept within its values.
export function startIndices(sliders) {
  return sliders.map((s) => Math.min(Math.max(0, s.index | 0), s.values.length - 1));
}

// Draw the sliders into box, below the plot in area.  layout is the plot's layout;
// P is Plotly.  Returns the positions object, for tests and callers.
export function addSliders(box, area, fig, layout, P) {
  const pos = startIndices(fig.sliders);
  const wrap = document.createElement('div');
  wrap.className = 'sliders';
  const redraw = () => {
    const f = fig.frames[frameKey(pos)];
    if (!f) return;
    const lay = f.title ? Object.assign({}, layout, { title: Object.assign({}, layout.title, { text: f.title }) }) : layout;
    P.react(area, f.data, lay, { displayModeBar: false, responsive: true });
  };
  fig.sliders.forEach((s, k) => {
    const row = document.createElement('label');
    row.className = 'slider';
    const name = document.createElement('span');
    name.className = 'slider-name';
    name.textContent = s.label;
    const input = document.createElement('input');
    input.type = 'range'; input.min = '0'; input.max = String(s.values.length - 1); input.step = '1';
    input.value = String(pos[k]);
    input.setAttribute('aria-label', s.label);
    const value = document.createElement('span');
    value.className = 'slider-value';
    value.textContent = sliderText(s, pos[k]);
    input.addEventListener('input', () => {
      pos[k] = Number(input.value);
      value.textContent = sliderText(s, pos[k]);
      redraw();
    });
    row.append(name, input, value);
    wrap.appendChild(row);
  });
  box.appendChild(wrap);
  return pos;
}
