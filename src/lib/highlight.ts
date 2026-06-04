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

export async function highlight(
  code: string,
  lang: string,
  theme: 'github-dark' | 'github-light' = 'github-dark',
): Promise<string> {
  const h = await getSingletonHighlighter({
    themes: ['github-dark', 'github-light'],
    langs: [...LANGS],
  });
  const loadedLangs = h.getLoadedLanguages();
  const safeLang = loadedLangs.includes(lang as never) ? lang : 'text';
  return h.codeToHtml(code, { lang: safeLang, theme });
}
