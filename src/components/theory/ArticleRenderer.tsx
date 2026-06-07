import { marked, Renderer } from 'marked';
import { highlight } from '@/lib/highlight';

interface ArticleRendererProps {
  html: string;
}

/** Renders pre-built HTML from renderArticleHtml(). */
export function ArticleRenderer({ html }: ArticleRendererProps) {
  return (
    <div
      className="article-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}

/** Remove the <!-- verified: ... --> comment that starts every article. */
function stripVerifiedComment(content: string): string {
  return content.replace(/^<!--[\s\S]*?-->\s*/m, '');
}

/** Server-side: parse markdown + highlight code blocks. Returns HTML string. */
export async function renderArticleHtml(content: string): Promise<string> {
  const cleaned = stripVerifiedComment(content);
  return renderMarkdownWithShiki(cleaned);
}

async function renderMarkdownWithShiki(source: string): Promise<string> {
  // Pass 1: extract code blocks → placeholders
  const blocks: Array<{ lang: string; code: string }> = [];
  const withPlaceholders = source.replace(
    /```(\w+)?\n?([\s\S]*?)```/g,
    (_, lang: string | undefined, code: string) => {
      const idx = blocks.push({ lang: lang ?? 'text', code: code.trim() }) - 1;
      return `CODEBLOCK_PLACEHOLDER_${idx}`;
    },
  );

  // Pass 2: render remaining markdown with marked
  const renderer = new Renderer();
  renderer.heading = function ({ text, depth }) {
    const id = text
      .toLowerCase()
      .replace(/<[^>]+>/g, '')
      .replace(/[^\w\s-]/g, '')
      .replace(/\s+/g, '-')
      .replace(/-+/g, '-')
      .trim();
    return `<h${depth} id="${id}">${text}</h${depth}>\n`;
  };

  marked.setOptions({ gfm: true, breaks: false });
  let html = await marked(withPlaceholders, { renderer, async: false }) as string;

  // Pass 3: highlight code blocks
  const highlighted = await Promise.all(
    blocks.map(({ lang, code }) => highlight(code, lang)),
  );

  blocks.forEach((_, idx) => {
    html = html
      .replace(`<p>CODEBLOCK_PLACEHOLDER_${idx}</p>`, highlighted[idx])
      .replace(`CODEBLOCK_PLACEHOLDER_${idx}`, highlighted[idx]);
  });

  return html;
}
