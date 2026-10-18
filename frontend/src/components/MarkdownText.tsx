import type { ReactNode } from "react";

const INLINE_PATTERN = /(\*\*[\s\S]+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`)/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  INLINE_PATTERN.lastIndex = 0;
  while ((match = INLINE_PATTERN.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    const nodeKey = `${keyPrefix}-${key++}`;
    if (token.startsWith("**")) {
      nodes.push(
        <strong key={nodeKey} className="font-semibold">
          {renderInline(token.slice(2, -2), nodeKey)}
        </strong>,
      );
    } else if (token.startsWith("*")) {
      nodes.push(<em key={nodeKey}>{token.slice(1, -1)}</em>);
    } else {
      nodes.push(
        <code
          key={nodeKey}
          className="rounded bg-slate-200 px-1 py-0.5 font-mono text-xs"
        >
          {token.slice(1, -1)}
        </code>,
      );
    }
    lastIndex = match.index + token.length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

function renderBlocks(content: string): ReactNode[] {
  const lines = content.split("\n");
  const blocks: ReactNode[] = [];
  let key = 0;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    const bulletMatch = /^[-*]\s+/.exec(trimmed);
    if (bulletMatch) {
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^[-*]\s+/, ""));
        i++;
      }
      const listKey = `ul-${key++}`;
      blocks.push(
        <ul key={listKey} className="list-disc space-y-1 pl-4">
          {items.map((item, idx) => (
            <li key={`${listKey}-${idx}`}>{renderInline(item, `${listKey}-${idx}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+[.)]\s+/.test(trimmed)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+[.)]\s+/.test(lines[i].trim())) {
        items.push(lines[i].trim().replace(/^\d+[.)]\s+/, ""));
        i++;
      }
      const listKey = `ol-${key++}`;
      blocks.push(
        <ol key={listKey} className="list-decimal space-y-1 pl-4">
          {items.map((item, idx) => (
            <li key={`${listKey}-${idx}`}>{renderInline(item, `${listKey}-${idx}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    const headingMatch = /^(#{1,4})\s+(.*)$/.exec(trimmed);
    if (headingMatch) {
      blocks.push(
        <p key={`h-${key++}`} className="font-semibold">
          {renderInline(headingMatch[2], `h-${key}`)}
        </p>,
      );
      i++;
      continue;
    }

    const paragraphLines: string[] = [trimmed];
    i++;
    while (
      i < lines.length &&
      lines[i].trim() &&
      !/^[-*]\s+/.test(lines[i].trim()) &&
      !/^\d+[.)]\s+/.test(lines[i].trim()) &&
      !/^#{1,4}\s+/.test(lines[i].trim())
    ) {
      paragraphLines.push(lines[i].trim());
      i++;
    }
    const pKey = `p-${key++}`;
    blocks.push(
      <p key={pKey}>
        {paragraphLines.map((text, idx) => (
          <span key={`${pKey}-${idx}`}>
            {idx > 0 && <br />}
            {renderInline(text, `${pKey}-${idx}`)}
          </span>
        ))}
      </p>,
    );
  }

  return blocks;
}

export default function MarkdownText({ content }: { content: string }) {
  return <div className="space-y-2">{renderBlocks(content)}</div>;
}
