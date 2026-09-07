import type { ReactNode, SVGProps } from "react";

type IconProps = Omit<SVGProps<SVGSVGElement>, "children">;

function BaseIcon({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      focusable="false"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.9"
      viewBox="0 0 24 24"
      {...props}
    >
      {children}
    </svg>
  );
}

export function PhoneIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M21.5 16.6v2.7a2.2 2.2 0 0 1-2.4 2.2A17.3 17.3 0 0 1 2.5 4.9 2.2 2.2 0 0 1 4.7 2.5h2.7a2.2 2.2 0 0 1 2.2 1.9c.1 1 .4 2 .8 2.9a2.2 2.2 0 0 1-.5 2.3L8.8 10.7a13.2 13.2 0 0 0 4.5 4.5l1.1-1.1a2.2 2.2 0 0 1 2.3-.5c.9.4 1.9.7 2.9.8a2.2 2.2 0 0 1 1.9 2.2Z" />
    </BaseIcon>
  );
}

export function LocationIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <path d="M20 10c0 5.5-8 11.5-8 11.5S4 15.5 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </BaseIcon>
  );
}

export function EmailIcon(props: IconProps) {
  return (
    <BaseIcon {...props}>
      <rect height="15" rx="2" width="19" x="2.5" y="4.5" />
      <path d="m4 6 8 6 8-6" />
    </BaseIcon>
  );
}
