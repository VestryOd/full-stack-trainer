'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface SolutionSpoilerProps {
  children: React.ReactNode;
}

export function SolutionSpoiler({ children }: SolutionSpoilerProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border rounded-md">
      <Button
        variant="ghost"
        className="w-full justify-between rounded-md"
        onClick={() => setOpen((v) => !v)}
      >
        <span>View Solution</span>
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
      </Button>
      {open && <div className="p-4 border-t">{children}</div>}
    </div>
  );
}
