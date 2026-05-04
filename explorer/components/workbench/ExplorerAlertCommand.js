import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "../ui/button";
import { copyTextToClipboard } from "../../lib/clipboard";

export default function ExplorerAlertCommand({ command }) {
  const normalizedCommand = String(command || "").trim();
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState("");

  useEffect(() => {
    setCopied(false);
    setCopyError("");
  }, [normalizedCommand]);

  useEffect(() => {
    if (!copied) {
      return undefined;
    }
    const timeout = globalThis.setTimeout(() => setCopied(false), 1600);
    return () => globalThis.clearTimeout(timeout);
  }, [copied]);

  if (!normalizedCommand) {
    return null;
  }

  async function handleCopyCommand() {
    try {
      await copyTextToClipboard(normalizedCommand);
      setCopied(true);
      setCopyError("");
    } catch (error) {
      setCopied(false);
      setCopyError(error instanceof Error ? error.message : "Copy failed");
    }
  }

  return (
    <div className="mt-3">
      <div className="flex min-w-0 items-center gap-2 rounded-md bg-muted px-2.5 py-2">
        <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap text-xs leading-5 text-foreground">
          {normalizedCommand}
        </code>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          className="text-muted-foreground hover:text-foreground"
          onClick={handleCopyCommand}
          aria-label={copied ? "Copied rebuild command" : "Copy rebuild command"}
          title={copied ? "Copied" : "Copy rebuild command"}
        >
          {copied ? <Check className="size-3.5" aria-hidden="true" /> : <Copy className="size-3.5" aria-hidden="true" />}
        </Button>
      </div>
      {copyError ? (
        <p className="mt-1 text-xs text-destructive">{copyError}</p>
      ) : null}
    </div>
  );
}
