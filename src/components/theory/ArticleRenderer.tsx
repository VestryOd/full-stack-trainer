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

/**
 * Server-side: parse markdown + highlight code blocks. Returns HTML string.
 *
 * `topicId` turns the `./04-file.md` links the articles use into real routes.
 * Without it the href ships verbatim and resolves against the current article's
 * own path, which 404s.
 */
export async function renderArticleHtml(content: string, topicId?: string): Promise<string> {
  const cleaned = stripVerifiedComment(content);
  return renderMarkdownWithShiki(cleaned, topicId);
}

async function renderMarkdownWithShiki(source: string, topicId?: string): Promise<string> {
  // Pass 1: extract code blocks → placeholders
  const blocks: Array<{ lang: string; code: string }> = [];
  const withPlaceholders = source.replace(
    /```(\w+)?\n?([\s\S]*?)```/g,
    (_, lang: string | undefined, code: string) => {
      const idx = blocks.push({ lang: lang ?? 'text', code: code.trim() }) - 1;
      // Trailing `_END` delimiter keeps placeholders unambiguous: without it
      // `..._1` is a substring of `..._10`, so replacing block 1 would corrupt
      // block 10 (duplicated code + a stray leftover digit).
      return `CODEBLOCK_PLACEHOLDER_${idx}_END`;
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
  renderer.link = function ({ href, title, text }) {
    // `./07-streams-and-backpressure.md` → `/theory/nodejs/07-streams-and-backpressure`
    const sameTopic = topicId && /^\.\/([\w-]+)\.md$/.exec(href);
    const target = sameTopic ? `/theory/${topicId}/${sameTopic[1]}` : href;
    const titleAttr = title ? ` title="${title}"` : '';
    return `<a href="${target}"${titleAttr}>${text}</a>`;
  };

  marked.setOptions({ gfm: true, breaks: false });
  let html = await marked(withPlaceholders, { renderer, async: false }) as string;

  // Pass 3: highlight code blocks
  const highlighted = await Promise.all(
    blocks.map(({ lang, code }) => highlight(code, lang)),
  );

  blocks.forEach((_, idx) => {
    const token = `CODEBLOCK_PLACEHOLDER_${idx}_END`;
    // Function replacers so `$` sequences in highlighted code (e.g. `${...}`
    // template literals) are inserted verbatim, not treated as replacement
    // patterns by String.prototype.replace.
    html = html
      .replace(`<p>${token}</p>`, () => highlighted[idx])
      .replace(token, () => highlighted[idx]);
  });

  return html;
}
