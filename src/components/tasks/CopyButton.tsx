'use client';

import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import { useLocale } from '@/context/LocaleContext';

interface CopyButtonProps {
  text: string;
}

export function CopyButton({ text }: CopyButtonProps) {
  const { t2 } = useLocale();
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <button
      onClick={handleCopy}
      aria-label={copied ? t2('tasks.copied') : t2('tasks.copy')}
      className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground transition-colors rounded px-1.5 py-0.5 hover:bg-muted"
    >
      {copied ? (
        <>
          <Check className="h-3 w-3 text-green-500" />
          <span className="text-green-500">{t2('tasks.copied')}</span>
        </>
      ) : (
        <>
          <Copy className="h-3 w-3" />
          <span>{t2('tasks.copy')}</span>
        </>
      )}
    </button>
  );
}
