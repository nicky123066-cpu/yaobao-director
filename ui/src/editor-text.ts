/** Textareas normalize CRLF to LF; keep source formatting and map selections back to it. */
export function rawSelectionIndex(raw: string, textareaOffset: number): number {
  let index = 0, visible = 0;
  while (index < raw.length && visible < textareaOffset) {
    index += raw[index] === '\r' && raw[index + 1] === '\n' ? 2 : 1;
    visible++;
  }
  return index;
}

export function preserveEndings(previous: string, edited: string): string {
  const before = previous.split(/\r\n|\r|\n/);
  const after = edited.replace(/\r\n|\r/g, '\n').split('\n');
  const endings = [...previous.matchAll(/\r\n|\r|\n/g)].map(match => match[0]);
  const fallback = endings[0] || '\n';
  let prefix = 0, suffix = 0;
  while (prefix < before.length && prefix < after.length && before[prefix] === after[prefix]) prefix++;
  while (suffix < before.length - prefix && suffix < after.length - prefix && before[before.length - suffix - 1] === after[after.length - suffix - 1]) suffix++;
  const equalBlock = before.length - prefix - suffix === after.length - prefix - suffix;
  return after.map((line, i) => {
    if (i === after.length - 1) return line;
    const oldIndex = i >= after.length - suffix ? before.length - after.length + i : i;
    const ending = i < prefix || i >= after.length - suffix || equalBlock ? endings[oldIndex] || fallback : fallback;
    return line + ending;
  }).join('');
}
