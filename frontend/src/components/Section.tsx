import { useState, type ReactNode } from "react";

/** A labeled, collapsible section to group the dashboard into readable zones. */
export function Section({
  title, subtitle, children, defaultOpen = true,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="section">
      <button className="section-head" onClick={() => setOpen((o) => !o)}>
        <span className="section-chevron">{open ? "▾" : "▸"}</span>
        <span className="section-title">{title}</span>
        {subtitle && <span className="section-sub">{subtitle}</span>}
      </button>
      {open && <div className="section-body">{children}</div>}
    </section>
  );
}
