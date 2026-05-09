import * as React from "react";
import { cn } from "@/lib/utils";

/* ── Context ───────────────────────────────────────────── */

interface SelectContextValue {
  value: string;
  displayLabel: string;
  onValueChange: (v: string, label: string) => void;
  open: boolean;
  setOpen: (v: boolean) => void;
  registerItem: (value: string, label: string) => void;
}

const SelectContext = React.createContext<SelectContextValue>({
  value: "",
  displayLabel: "",
  onValueChange: () => {},
  open: false,
  setOpen: () => {},
  registerItem: () => {},
});

/* ── Root ──────────────────────────────────────────────── */

interface SelectProps {
  value: string;
  onValueChange: (v: string) => void;
  children: React.ReactNode;
  disabled?: boolean;
}

function Select({ value, onValueChange, children, disabled }: SelectProps) {
  const [open, setOpen] = React.useState(false);
  const labelsRef = React.useRef<Map<string, string>>(new Map());
  const [displayLabel, setDisplayLabel] = React.useState("");

  const registerItem = React.useCallback((itemValue: string, label: string) => {
    labelsRef.current.set(itemValue, label);
    // If this item matches the current value, update display label
    if (itemValue === value) {
      setDisplayLabel(label);
    }
  }, [value]);

  // Update display label whenever value changes
  React.useEffect(() => {
    const label = labelsRef.current.get(value);
    if (label) {
      setDisplayLabel(label);
    } else {
      setDisplayLabel("");
    }
  }, [value]);

  return (
    <SelectContext.Provider
      value={{
        value,
        displayLabel,
        onValueChange: (v: string, label: string) => {
          if (!disabled) {
            onValueChange(v);
            setDisplayLabel(label);
            setOpen(false);
          }
        },
        open,
        setOpen: (v: boolean) => {
          if (!disabled) setOpen(v);
        },
        registerItem,
      }}
    >
      <div className="relative">{children}</div>
    </SelectContext.Provider>
  );
}

/* ── Trigger ───────────────────────────────────────────── */

const SelectTrigger = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement>
>(({ className, children, ...props }, ref) => {
  const ctx = React.useContext(SelectContext);
  return (
    <button
      ref={ref}
      type="button"
      className={cn(
        "flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      onClick={() => ctx.setOpen(!ctx.open)}
      {...props}
    >
      {children}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="ml-2 opacity-50"
      >
        <path d="m6 9 6 6 6-6" />
      </svg>
    </button>
  );
});
SelectTrigger.displayName = "SelectTrigger";

/* ── Value ─────────────────────────────────────────────── */

function SelectValue({ placeholder }: { placeholder?: string }) {
  const ctx = React.useContext(SelectContext);
  return (
    <span className={!ctx.displayLabel && placeholder ? "text-muted-foreground" : ""}>
      {ctx.displayLabel || placeholder || ""}
    </span>
  );
}

/* ── Content (dropdown) ────────────────────────────────── */

const SelectContent = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
  const ctx = React.useContext(SelectContext);
  const contentRef = React.useRef<HTMLDivElement>(null);

  // Close on outside click
  React.useEffect(() => {
    if (!ctx.open) return;
    const handler = (e: MouseEvent) => {
      if (
        contentRef.current &&
        !contentRef.current.contains(e.target as Node)
      ) {
        ctx.setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [ctx.open]);

  if (!ctx.open) return null;

  return (
    <div
      ref={(node) => {
        (contentRef as React.MutableRefObject<HTMLDivElement | null>).current =
          node;
        if (typeof ref === "function") ref(node);
        else if (ref) (ref as React.MutableRefObject<HTMLDivElement | null>).current = node;
      }}
      className={cn(
        "absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
});
SelectContent.displayName = "SelectContent";

/* ── Item ──────────────────────────────────────────────── */

interface SelectItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
}

const SelectItem = React.forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, value, children, ...props }, ref) => {
    const ctx = React.useContext(SelectContext);
    const isSelected = ctx.value === value;

    // Extract text content for label registration
    const textContent = React.useMemo(() => {
      const extractText = (node: React.ReactNode): string => {
        if (typeof node === "string" || typeof node === "number") return String(node);
        if (Array.isArray(node)) return node.map(extractText).join("");
        if (React.isValidElement(node) && node.props.children) {
          return extractText(node.props.children);
        }
        return "";
      };
      return extractText(children);
    }, [children]);

    // Register this item's value → label mapping
    React.useEffect(() => {
      ctx.registerItem(value, textContent);
    }, [value, textContent]);

    return (
      <div
        ref={ref}
        role="option"
        aria-selected={isSelected}
        className={cn(
          "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 px-2 text-sm outline-none hover:bg-accent hover:text-accent-foreground",
          isSelected && "bg-accent text-accent-foreground font-medium",
          className,
        )}
        onClick={() => ctx.onValueChange(value, textContent)}
        {...props}
      >
        {children}
      </div>
    );
  },
);
SelectItem.displayName = "SelectItem";

export { Select, SelectTrigger, SelectValue, SelectContent, SelectItem };
