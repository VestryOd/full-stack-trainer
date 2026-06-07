import { getSingletonHighlighter } from 'shiki';

const LANGS = [
  'typescript',
  'javascript',
  'sql',
  'bash',
  'json',
  'css',
  'html',
  'graphql',
  'dockerfile',
] as const;

export async function highlight(code: string, lang: string): Promise<string> {
  const h = await getSingletonHighlighter({
    themes: ['github-dark'],
    langs: [...LANGS],
  });
  const loadedLangs = h.getLoadedLanguages();
  const safeLang = loadedLangs.includes(lang as never) ? lang : 'text';
  return h.codeToHtml(code, { lang: safeLang, theme: 'github-dark' });
}
