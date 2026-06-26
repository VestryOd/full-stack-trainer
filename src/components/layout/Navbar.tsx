'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Menu } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { useLocale } from '@/context/LocaleContext';
import { LocaleSwitcher } from './LocaleSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { Button } from '@/components/ui/button';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from '@/components/ui/sheet';

const NAV_LINKS = [
  { href: '/theory',     key: 'nav.theory' },
  { href: '/questions',  key: 'nav.questions' },
  { href: '/quiz',       key: 'nav.quiz' },
  { href: '/tasks',      key: 'nav.tasks' },
  { href: '/interview',  key: 'nav.interview' },
] as const;

export function Navbar() {
  const pathname = usePathname();
  const { t2 } = useLocale();
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container flex h-14 items-center">
        <Link href="/" className="mr-6 flex items-center gap-2">
          <span className="font-bold text-primary text-lg">FST</span>
          <span className="hidden text-sm text-muted-foreground sm:inline">Full Stack Trainer</span>
        </Link>

        <nav className="hidden flex-1 items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-colors hover:bg-accent hover:text-accent-foreground',
                pathname.startsWith(link.href)
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground',
              )}
            >
              {t2(link.key)}
            </Link>
          ))}
        </nav>

        <div className="flex flex-1 items-center justify-end gap-2">
          <LocaleSwitcher />
          <ThemeToggle />

          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" className="md:hidden">
                <Menu className="h-5 w-5" />
                <span className="sr-only">Open menu</span>
              </Button>
            </SheetTrigger>
            <SheetContent side="right">
              <SheetHeader>
                <SheetTitle>Navigation</SheetTitle>
              </SheetHeader>
              <nav className="mt-6 flex flex-col gap-2">
                {NAV_LINKS.map((link) => (
                  <Link
                    key={link.href}
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className={cn(
                      'px-3 py-2 text-sm font-medium rounded-md transition-colors hover:bg-accent',
                      pathname.startsWith(link.href)
                        ? 'bg-accent text-accent-foreground'
                        : 'text-foreground',
                    )}
                  >
                    {t2(link.key)}
                  </Link>
                ))}
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </header>
  );
}
