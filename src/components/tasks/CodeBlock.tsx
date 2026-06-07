import { highlight } from '@/lib/highlight';
import { CopyButton } from './CopyButton';

interface CodeBlockProps {
  code: string;
  lang?: string;
  showCopy?: boolean;
  showLanguageLabel?: boolean;
}

export async function CodeBlock({
  code,
  lang = 'typescript',
  showCopy = true,
  showLanguageLabel = true,
}: CodeBlockProps) {
  const html = await highlight(code, lang);
  return (
    <div className="relative group rounded-md overflow-hidden border border-border">
      {showLanguageLabel && (
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-muted/50">
          <span className="font-mono text-xs text-muted-foreground">{lang}</span>
          {showCopy && <CopyButton text={code} />}
        </div>
      )}
      {!showLanguageLabel && showCopy && (
        <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity z-10">
          <CopyButton text={code} />
        </div>
      )}
      <div
        className="overflow-x-auto text-sm"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}
