import { useState } from "react";

import type {
  ParticipantForumPostRead,
} from "../types/participant";

interface Props {
  post: ParticipantForumPostRead;
}

function formatTimestamp(value: string): string {
  const parsed = new Date(value);

  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function avatarLabel(value: string): string {
  const clean = value.trim();

  if (!clean) {
    return "U";
  }

  return clean.slice(-2).toUpperCase();
}

export function CommunityPostCard({

  post,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = post.display_text.length > 420;

  return (
    <article className="terminal-post-card">
      <header className="terminal-post-card__header">
        <span
          className="terminal-post-card__avatar"
          aria-hidden="true"
        >
          {avatarLabel(post.author_id)}
        </span>

        <div className="terminal-post-card__identity">
          <strong>{post.source_label}</strong>
          <span>{post.author_id}</span>
        </div>

        <time dateTime={post.created_at}>
          {formatTimestamp(post.created_at)}
        </time>
      </header>

      <p
        className={`terminal-post-card__body ${
          !expanded && canExpand
            ? "terminal-post-card__body--collapsed"
            : ""
        }`}
      >
        {post.display_text}
      </p>

      {canExpand && (
        <button
          type="button"
          className="terminal-post-card__expand"
          aria-expanded={expanded}
          onClick={() =>
            setExpanded((current) => !current)
          }
        >
          {expanded ? "Show less" : "Read more"}
        </button>
      )}
    </article>
  );
}
