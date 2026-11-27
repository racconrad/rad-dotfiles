.pragma library

function move(origin, surface, key) {
  const horizontal = key === Qt.Key_Left || key === Qt.Key_Right;
  const sign = key === Qt.Key_Left || key === Qt.Key_Up ? -1 : 1;
  const here = origin.mapToItem(surface, origin.width / 2, origin.height / 2);
  let candidate = origin.nextItemInFocusChain();
  let best = null;
  let score = Infinity;
  const seen = new Set([origin]);

  while (candidate && !seen.has(candidate)) {
    seen.add(candidate);
    if (candidate.visible && candidate.enabled && candidate.activeFocusOnTab) {
      const there = candidate.mapToItem(surface, candidate.width / 2, candidate.height / 2);
      const dx = there.x - here.x;
      const dy = there.y - here.y;
      const along = sign * (horizontal ? dx : dy);
      const across = Math.abs(horizontal ? dy : dx);
      const distance = along + 4 * across;
      if (along > 1 && distance < score) {
        best = candidate;
        score = distance;
      }
    }
    candidate = candidate.nextItemInFocusChain();
  }

  if (!best)
    return false;
  best.forceActiveFocus(Qt.TabFocusReason);
  return true;
}
