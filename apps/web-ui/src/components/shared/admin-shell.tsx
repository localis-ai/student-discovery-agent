'use client';

import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { Bot, Database, Menu } from 'lucide-react';
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet';
import { cn } from '@/lib/utils/cn';
import { IconButton } from './icon-button';

const NAV = [
  { key: 'agent', href: '/admin/agent', label: 'Agent', icon: Bot, match: (path: string) => path.startsWith('/admin/agent') },
  { key: 'knowledge', href: '/admin/knowledge', label: 'Knowledge Base', icon: Database, match: (path: string) => path.startsWith('/admin/knowledge') },
] as const;

export interface AdminShellProps {
  children: React.ReactNode;
  account?: React.ReactNode;
  /** Nested group under "Knowledge Base" (the open knowledge base's sections); it decides itself when to render. */
  knowledgeNav?: React.ReactNode;
}

const FOCUS = 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

/** Logo and wordmark, the same pairing as the Studio sign-in page. */
function Brand({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <Link href="/admin/agent" onClick={onNavigate} className={cn('flex items-center gap-2.5 rounded-md px-2 py-1', FOCUS)}>
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border bg-card p-1">
        <Image src="/Logo-IHRD.png" alt="" width={24} height={24} className="h-full w-full object-contain" />
      </span>
      <span className="text-base font-semibold text-brand">Agent Studio</span>
    </Link>
  );
}

function SidebarBody({ pathname, account, knowledgeNav, onNavigate }: {
  pathname: string; account?: React.ReactNode; knowledgeNav?: React.ReactNode; onNavigate?: () => void;
}) {
  return (
    <div className="flex h-full flex-col gap-4 px-3 py-4">
      <Brand onNavigate={onNavigate} />
      <nav aria-label="Điều hướng chính" className="flex min-h-0 flex-col gap-0.5 overflow-y-auto">
        {NAV.map(({ key, href, label, icon: Icon, match }) => {
          const inSection = match(pathname);
          // Inside a knowledge base the nested item is the current page; the parent only stays highlighted.
          const current = inSection && pathname === href;
          return (
            <div key={key}>
              <Link
                href={href}
                onClick={onNavigate}
                aria-current={current ? 'page' : undefined}
                className={cn(
                  'relative flex h-9 items-center gap-2.5 rounded-md px-3 text-sm transition-colors', FOCUS,
                  // The bar marks the section you are in, whether or not a nested item is the current page.
                  inSection && 'before:absolute before:inset-y-1.5 before:left-0 before:w-0.5 before:rounded-full before:bg-primary',
                  current && 'bg-primary-subtle font-medium text-primary',
                  inSection && !current && 'font-medium text-primary hover:bg-primary-subtle',
                  !inSection && 'text-sidebar-foreground hover:bg-primary-subtle',
                )}
              >
                <Icon className={cn('h-4 w-4', inSection ? 'text-primary' : 'text-muted-foreground')} aria-hidden />
                {label}
              </Link>
              {key === 'knowledge' && knowledgeNav}
            </div>
          );
        })}
      </nav>
      {account && <div className="mt-auto border-t pt-3">{account}</div>}
    </div>
  );
}

export function AdminShell({ children, account, knowledgeNav }: AdminShellProps) {
  const pathname = usePathname() ?? '';
  const [open, setOpen] = useState(false);
  // Any navigation (including links inside `knowledgeNav`) closes the mobile menu.
  useEffect(() => setOpen(false), [pathname]);
  return (
    <div className="flex min-h-screen bg-background">
      <aside className="sticky top-0 hidden h-screen w-[232px] shrink-0 border-r bg-sidebar md:block">
        <SidebarBody pathname={pathname} account={account} knowledgeNav={knowledgeNav} />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 items-center gap-2 border-b bg-sidebar px-3 md:hidden">
          <IconButton label="Mở menu" side="right" onClick={() => setOpen(true)} aria-expanded={open}>
            <Menu className="h-4 w-4" aria-hidden />
          </IconButton>
          <Brand />
        </header>
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetContent side="left" className="w-[260px] bg-sidebar p-0">
            <SheetTitle className="sr-only">Menu</SheetTitle>
            <SidebarBody pathname={pathname} account={account} knowledgeNav={knowledgeNav} onNavigate={() => setOpen(false)} />
          </SheetContent>
        </Sheet>
        <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
