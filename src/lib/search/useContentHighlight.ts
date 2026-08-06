'use client';

import { useEffect, type RefObject } from 'react';
import { queryTerms } from './highlight';

const SKIP_TAGS = new Set(['PRE', 'CODE', 'MARK', 'SCRIPT', 'STYLE']);

/**
 * After mount, reads the `?hl=` query param and highlights matching terms inside
 * pre-rendered HTML content (theory / task / course bodies), then scrolls the
 * first match into view. Skips code blocks so Shiki markup is left untouched.
 * Unwraps its marks on cleanup so locale switches re-highlight cleanly.
 *
 * `deps` should include whatever causes the content HTML to change (e.g. locale).
 */
interface HighlightOptions {
  /** When false, the hook does nothing (used to scope highlighting to a target). */
  enabled?: boolean;
  /** When false, matches are highlighted but not scrolled to (caller scrolls instead). */
  scroll?: boolean;
}

export function useContentHighlight(
  ref: RefObject<HTMLElement>,
  deps: unknown[] = [],
  { enabled = true, scroll = true }: HighlightOptions = {},
): void {
  useEffect(() => {
    const root = ref.current;
    if (!enabled || !root || typeof window === 'undefined') return;

    const query = new URLSearchParams(window.location.search).get('hl')?.trim() ?? '';
    const terms = queryTerms(query);
    if (!terms.length) return;

    const testRe = new RegExp(terms.join('|'), 'i');
    const splitRe = new RegExp(`(${terms.join('|')})`, 'ig');

    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode(node) {
        const value = node.nodeValue;
        if (!value || !value.trim() || !testRe.test(value)) return NodeFilter.FILTER_REJECT;
        for (let el = node.parentElement; el && el !== root; el = el.parentElement) {
          if (SKIP_TAGS.has(el.tagName)) return NodeFilter.FILTER_REJECT;
        }
        return NodeFilter.FILTER_ACCEPT;
      },
    });

    const targets: Text[] = [];
    let cur: Node | null;
    while ((cur = walker.nextNode())) targets.push(cur as Text);
    if (!targets.length) return;

    const marks: HTMLElement[] = [];
    for (const node of targets) {
      const source = node.nodeValue ?? '';
      splitRe.lastIndex = 0;
      const frag = document.createDocumentFragment();
      let last = 0;
      let m: RegExpExecArray | null;
      while ((m = splitRe.exec(source))) {
        if (m.index > last) frag.appendChild(document.createTextNode(source.slice(last, m.index)));
        const mark = document.createElement('mark');
        mark.className = 'search-hl';
        mark.textContent = m[0];
        frag.appendChild(mark);
        marks.push(mark);
        last = m.index + m[0].length;
        if (m.index === splitRe.lastIndex) splitRe.lastIndex++; // guard against zero-width
      }
      if (last < source.length) frag.appendChild(document.createTextNode(source.slice(last)));
      node.parentNode?.replaceChild(frag, node);
    }

    if (scroll) marks[0]?.scrollIntoView({ block: 'center' });

    return () => {
      for (const mark of marks) {
        const parent = mark.parentNode;
        if (!parent) continue;
        parent.replaceChild(document.createTextNode(mark.textContent ?? ''), mark);
        parent.normalize();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
