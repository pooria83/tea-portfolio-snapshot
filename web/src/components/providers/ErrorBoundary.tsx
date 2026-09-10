"use client";

import { Component, type ReactNode, type ErrorInfo } from "react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

type Props = {
  children: ReactNode;
  fallback?: ReactNode;
};

export function ErrorBoundary({ children, fallback }: Props) {
  const t = useTranslations("common");

  return (
    <ErrorBoundaryClass
      fallback={fallback}
      title={t("errorTitle")}
      message={t("unexpectedError")}
      retryLabel={t("retry")}
    >
      {children}
    </ErrorBoundaryClass>
  );
}

type ClassProps = Props & {
  title: string;
  message: string;
  retryLabel: string;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

class ErrorBoundaryClass extends Component<ClassProps, State> {
  constructor(props: ClassProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (process.env.NODE_ENV === "development") {
      console.error("ErrorBoundary caught:", error, info);
    }
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-4 p-8">
          <h2 className="text-xl font-bold">{this.props.title}</h2>
          <p className="text-muted-foreground text-sm">
            {this.state.error?.message ?? this.props.message}
          </p>
          <Button onClick={this.handleRetry}>{this.props.retryLabel}</Button>
        </div>
      );
    }

    return this.props.children;
  }
}
