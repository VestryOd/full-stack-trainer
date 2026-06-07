'use client';

interface ArticleContentProps {
  html: string;
}

/** Client component: renders pre-built article HTML from the server. */
export function ArticleContent({ html }: ArticleContentProps) {
  return (
    <div
      className="article-body"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
