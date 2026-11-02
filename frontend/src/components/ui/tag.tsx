interface TagProps {
  children: React.ReactNode;
  /** Renders a remove button when set. */
  onRemove?: () => void;
  removeLabel?: string;
}

export function Tag({ children, onRemove, removeLabel = "Remove" }: TagProps) {
  return (
    <span className="inline-flex h-7 items-center gap-2 rounded border border-border px-2 text-[13px]">
      {children}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label={removeLabel} className="text-muted-foreground hover:text-foreground">
          ×
        </button>
      )}
    </span>
  );
}
