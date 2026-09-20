export function SectionHeading({ id, title, intro }: { id: string; title: string; intro: string }) {
  return (
    <div className="flex max-w-2xl flex-col gap-4">
      <h2 id={`${id}-title`} className="text-h2 text-fg">
        {title}
      </h2>
      <p className="text-body-lg text-fg-muted">{intro}</p>
    </div>
  );
}
