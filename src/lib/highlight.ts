import { getSingletonHighlighter } from 'shiki';

// Every language a content fence actually declares, so nothing silently falls back to
// plain text. `ts`, `js`, `tsx` and `jsx` need no entry — shiki resolves them as aliases
// of typescript/javascript. `txt` and `text` are meant to be unhighlighted.
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
  'python',
  'toml',
  'yaml',
  'http',
  'java',
  'csharp',
  'c',
  'prisma',
  'nginx',
  'jsonc',
  'markdown',
  'protobuf',
  'glsl',
  'gherkin',
  'hcl',
  'lua',
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
