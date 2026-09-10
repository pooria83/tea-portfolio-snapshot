import dynamic from "next/dynamic";
import type { ComponentType } from "react";

type DynamicOptions = {
  ssr?: boolean;
  loading?: () => React.ReactNode;
};

export function lazyImport<T extends ComponentType<object>>(
  importFn: () => Promise<{ default: T }>,
  options: DynamicOptions = {},
) {
  const dynamicOptions: Record<string, unknown> = {
    ssr: options.ssr ?? false,
  };
  if (options.loading) dynamicOptions.loading = options.loading;
  return dynamic(importFn, dynamicOptions);
}
