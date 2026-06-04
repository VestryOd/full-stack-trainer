import { highlight } from '@/lib/highlight';

interface CodeBlockProps {
  code: string;
  lang?: string;
  theme?: 'github-dark' | 'github-light';
}

export async function CodeBlock({ code, lang = 'typescript', theme = 'github-dark' }: CodeBlockProps) {
  const html = await highlight(code, lang, theme);
  return (
    <div
      className="rounded-md overflow-hidden text-sm"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
