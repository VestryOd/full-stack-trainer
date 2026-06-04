import { highlight } from '@/lib/highlight';

interface ArticleRendererProps {
  content: string;
  theme?: 'github-dark' | 'github-light';
}

async function renderMarkdown(content: string, theme: 'github-dark' | 'github-light') {
  const codeBlockRegex = /```(\w+)?\n([\s\S]*?)```/g;
  const parts: Array<{ type: 'text' | 'code'; value: string; lang?: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = codeBlockRegex.exec(content)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ type: 'text', value: content.slice(lastIndex, match.index) });
    }
    parts.push({ type: 'code', lang: match[1] ?? 'text', value: match[2] });
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < content.length) {
    parts.push({ type: 'text', value: content.slice(lastIndex) });
  }

  const rendered = await Promise.all(
    parts.map(async (part) => {
      if (part.type === 'code') {
        return highlight(part.value, part.lang ?? 'text', theme);
      }
      return `<div class="prose-part">${escapeHtmlOutsideCode(part.value)}</div>`;
    }),
  );

  return rendered.join('');
}

function escapeHtmlOutsideCode(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br />');
}

export async function ArticleRenderer({ content, theme = 'github-dark' }: ArticleRendererProps) {
  const html = await renderMarkdown(content, theme);
  return (
    <div
      className="prose prose-slate dark:prose-invert max-w-none"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
