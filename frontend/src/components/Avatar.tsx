import { initials } from "../lib/auth";
import { cx } from "../lib/format";
import type { User } from "../lib/types";

const SIZES = { sm: "size-8 text-xs", md: "size-10 text-sm", lg: "size-20 text-2xl" };

/** The user's initials on the brand gradient */
export function UserAvatar({ user, size = "sm", className }: { user: Pick<User, "name" | "email">; size?: keyof typeof SIZES; className?: string }) {
  return (
    <span
      aria-hidden
      className={cx(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-deep-gradient font-semibold tracking-wide text-white ring-2 ring-card",
        SIZES[size],
        className,
      )}
    >
      {initials(user)}
    </span>
  );
}
